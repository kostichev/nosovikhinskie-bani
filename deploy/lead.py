#!/usr/bin/env python3
"""Носовихинские бани — приём заявок с сайта.

Слушает 127.0.0.1:8095, nginx проксирует сюда POST /api/lead.
Каждая заявка: сохраняется в журнал → уходит в MAX (бот) → уходит на почту.
Только стандартная библиотека Python, без зависимостей.

Команды:
  nosbani-lead serve      — запуск сервиса (делает systemd)
  nosbani-lead setup      — пошаговая настройка MAX и почты
  nosbani-lead whoami     — показать ID тех, кто написал боту (для MAX_USERS)
  nosbani-lead test       — отправить тестовую заявку
  nosbani-lead last [N]   — последние заявки из журнала
"""
import json, os, re, ssl, sys, time, smtplib, threading, getpass
import urllib.request, urllib.error
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ENV = "/etc/nosbani/lead.env"
LOG = "/var/lib/nosbani/leads.jsonl"
PORT = 8095
MAX_HOSTS = ["https://platform-api2.max.ru", "https://platform-api.max.ru"]


def load_env():
    cfg = {"MAIL_TO": "nosbani@bk.ru", "SMTP_HOST": "smtp.mail.ru", "SMTP_PORT": "465", "SMTP_USER": "nosbani@bk.ru"}
    try:
        for line in open(ENV, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"')
    except FileNotFoundError:
        pass
    return cfg


def save_env(cfg):
    os.makedirs(os.path.dirname(ENV), exist_ok=True)
    old = os.umask(0o077)
    with open(ENV, "w", encoding="utf-8") as f:
        f.write("# Настройки заявок Носовихинских бань. Менять командой: nosbani-lead setup\n")
        for k in ["MAX_TOKEN", "MAX_USERS", "MAX_CHATS", "MAIL_TO", "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS"]:
            f.write(f'{k}="{cfg.get(k, "")}"\n')
    os.umask(old)
    os.chmod(ENV, 0o600)


# ---------------------------------------------------------------- MAX
def max_call(cfg, method, path, body=None):
    err = None
    for host in MAX_HOSTS:
        req = urllib.request.Request(host + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None,
                                     headers={"Authorization": cfg["MAX_TOKEN"], "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15, context=ssl.create_default_context()) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"MAX {e.code}: {e.read()[:300].decode('utf-8', 'replace')}")
        except Exception as e:  # сертификат/сеть — пробуем запасной адрес
            err = e
    raise RuntimeError(f"MAX недоступен: {err}")


def ids(s):
    return [x for x in re.split(r"[\s,;]+", s or "") if re.fullmatch(r"-?\d+", x)]


def send_max(cfg, text):
    if not cfg.get("MAX_TOKEN"):
        return "MAX не настроен"
    targets = [("user_id", i) for i in ids(cfg.get("MAX_USERS"))] + [("chat_id", i) for i in ids(cfg.get("MAX_CHATS"))]
    if not targets:
        return "MAX: нет получателей"
    errs = []
    for k, v in targets:
        try:
            max_call(cfg, "POST", f"/messages?{k}={v}", {"text": text[:3900]})
        except Exception as e:
            errs.append(str(e))
        time.sleep(0.6)
    return "; ".join(errs) or "ok"


# ---------------------------------------------------------------- почта
def send_mail(cfg, subject, text):
    if not (cfg.get("SMTP_USER") and cfg.get("SMTP_PASS")):
        return "почта не настроена"
    m = EmailMessage()
    m["Subject"] = subject
    m["From"] = formataddr(("Сайт Носовихинских бань", cfg["SMTP_USER"]))
    m["To"] = cfg.get("MAIL_TO") or "nosbani@bk.ru"
    m["Message-ID"] = make_msgid(domain="nosbani.local")
    m.set_content(text)
    port = int(cfg.get("SMTP_PORT") or 465)
    try:
        if port == 465:
            s = smtplib.SMTP_SSL(cfg["SMTP_HOST"], port, timeout=20, context=ssl.create_default_context())
        else:
            s = smtplib.SMTP(cfg["SMTP_HOST"], port, timeout=20); s.starttls(context=ssl.create_default_context())
        s.login(cfg["SMTP_USER"], cfg["SMTP_PASS"]); s.send_message(m); s.quit()
        return "ok"
    except Exception as e:
        return f"почта: {e}"


# ---------------------------------------------------------------- заявка
def clean(v, n=300):
    return re.sub(r"[\x00-\x08\x0b-\x1f<>]", "", str(v or "")).strip()[:n]


def format_lead(d):
    rows = [f"🔥 Новая заявка с сайта · {clean(d.get('code'), 20)}", ""]
    rows.append(f"Услуга: {clean(d.get('service'))}")
    if d.get("when"): rows.append(f"Когда: {clean(d.get('when'))}")
    if d.get("guests"): rows.append(f"Гости: {clean(d.get('guests'))}")
    items = d.get("items") or []
    if isinstance(items, list) and items:
        rows += ["", "Состав:"] + [f"• {clean(i, 160)}" for i in items[:20]]
    if d.get("total"): rows.append(f"Итого: {clean(d.get('total'), 40)} (предоплата 50% после подтверждения)")
    rows += ["", f"Имя: {clean(d.get('name'), 80)}", f"Телефон: {clean(d.get('phone'), 30)}"]
    if d.get("comment"): rows.append(f"Комментарий: {clean(d.get('comment'), 600)}")
    rows += ["", "Перезвоните гостю для подтверждения брони."]
    return "\n".join(rows)


def deliver(d):
    cfg = load_env()
    text = format_lead(d)
    res_max = send_max(cfg, text)
    res_mail = send_mail(cfg, f"Заявка {clean(d.get('code'), 20)}: {clean(d.get('service'), 60)} — {clean(d.get('name'), 40)}", text)
    log({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "lead": d, "max": res_max, "mail": res_mail})
    print(time.strftime("%F %T"), d.get("code"), "max:", res_max, "| mail:", res_mail, flush=True)


def log(rec):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    old = os.umask(0o077)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.umask(old)


HITS = {}
def limited(ip):
    now = time.time(); h = [t for t in HITS.get(ip, []) if now - t < 600]
    HITS[ip] = h + [now]
    return len(h) >= 8


class H(BaseHTTPRequestHandler):
    def _out(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        if self.path.split("?")[0] != "/api/lead":
            return self._out(404, {"ok": False})
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 16000:
            return self._out(413, {"ok": False})
        try:
            d = json.loads(self.rfile.read(n))
            assert isinstance(d, dict)
        except Exception:
            return self._out(400, {"ok": False, "error": "bad json"})
        ip = self.headers.get("X-Real-IP") or self.client_address[0]
        if d.get("website"):                      # скрытое поле-ловушка для ботов
            return self._out(200, {"ok": True})
        if limited(ip):
            return self._out(429, {"ok": False, "error": "Слишком много заявок подряд"})
        phone = re.sub(r"\D", "", str(d.get("phone", "")))
        if len(phone) != 11 or len(clean(d.get("name"))) < 2:
            return self._out(422, {"ok": False, "error": "Проверьте имя и телефон"})
        d["ip"] = ip
        threading.Thread(target=deliver, args=(d,), daemon=True).start()   # гость не ждёт почту
        self._out(200, {"ok": True})

    def do_GET(self):
        self._out(200 if self.path == "/api/lead/ping" else 404, {"ok": self.path == "/api/lead/ping"})

    def log_message(self, *a):
        pass


# ---------------------------------------------------------------- команды
def cmd_setup():
    cfg = load_env()
    print("\n=== Настройка заявок Носовихинских бань ===\nEnter — оставить как есть.\n")
    def ask(k, title, secret=False):
        cur = cfg.get(k, "")
        shown = ("••••" + cur[-4:]) if (secret and cur) else cur
        v = (getpass.getpass if secret else input)(f"{title} [{shown}]: ").strip()
        if v: cfg[k] = v
    print("— MAX —")
    ask("MAX_TOKEN", "Токен бота MAX (business.max.ru → Чат-боты → бот → Настройки)", True)
    if cfg.get("MAX_TOKEN") and not cfg.get("MAX_USERS"):
        print("  Чтобы узнать ID администраторов: каждый пишет боту в MAX «старт», затем запустите  nosbani-lead whoami")
    ask("MAX_USERS", "ID администраторов в MAX через запятую")
    ask("MAX_CHATS", "ID группового чата MAX (если бот добавлен в группу), иначе пусто")
    print("\n— Почта —")
    ask("MAIL_TO", "Куда слать заявки")
    ask("SMTP_HOST", "SMTP-сервер отправителя")
    ask("SMTP_PORT", "Порт SMTP")
    ask("SMTP_USER", "Ящик-отправитель (например nosbani@bk.ru)")
    ask("SMTP_PASS", "Пароль для внешних приложений этого ящика", True)
    save_env(cfg)
    print(f"\nСохранено в {ENV}. Теперь проверьте:  nosbani-lead test\n")


def cmd_whoami():
    cfg = load_env()
    if not cfg.get("MAX_TOKEN"):
        sys.exit("Сначала укажите токен: nosbani-lead setup")
    me = max_call(cfg, "GET", "/me")
    print(f"Бот: {me.get('name') or me.get('first_name')} (@{me.get('username')})\n")
    up = max_call(cfg, "GET", "/updates?limit=100&timeout=0")
    seen = set()
    for u in up.get("updates", []):
        msg = u.get("message") or {}
        user = u.get("user") or msg.get("sender") or {}
        chat = u.get("chat_id") or (msg.get("recipient") or {}).get("chat_id")
        ctype = (msg.get("recipient") or {}).get("chat_type", "")
        key = (user.get("user_id"), chat)
        if key in seen: continue
        seen.add(key)
        print(f"• {user.get('name') or user.get('first_name', '')}: user_id={user.get('user_id')}  chat_id={chat} {ctype}")
    try:
        chats = max_call(cfg, "GET", "/chats?count=50").get("chats", [])
    except Exception as e:
        chats = []
    for c in chats:
        if c.get("type") != "dialog":
            print(f"• Группа «{c.get('title', '')}»: chat_id={c.get('chat_id')}  ← это число впишите в «ID группового чата»")
            seen.add(("chat", c.get("chat_id")))
    if not seen:
        print("Пока никто не писал боту и бот не состоит в группах. Напишите ему в MAX «старт» и повторите команду.")


def cmd_test():
    d = {"code": "НБ-ТЕСТ", "service": "Отдельная баня «Прованс»", "when": "сегодня, 19:00 · 3 ч", "guests": "4 взрослых",
         "items": ["Баня «Прованс» × 3 ч — 9 000 ₽", "Парение «Бодрящий» — 2 500 ₽"], "total": "11 500 ₽",
         "name": "Тестовая заявка", "phone": "+7 (999) 000-00-00", "comment": "Проверка уведомлений — можно удалить"}
    cfg = load_env(); text = format_lead(d)
    print("MAX:  ", send_max(cfg, text))
    print("Почта:", send_mail(cfg, "Тест заявок с сайта Носовихинских бань", text))


def cmd_last(n=10):
    try:
        lines = open(LOG, encoding="utf-8").read().splitlines()[-n:]
    except FileNotFoundError:
        return print("Заявок пока нет.")
    for l in lines:
        r = json.loads(l); d = r["lead"]
        print(f"{r['t']}  {d.get('code')}  {d.get('service')}  {d.get('name')}  {d.get('phone')}  [MAX: {r['max']} | почта: {r['mail']}]")


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if c == "serve":
        ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
    elif c == "setup": cmd_setup()
    elif c == "whoami": cmd_whoami()
    elif c == "test": cmd_test()
    elif c == "last": cmd_last(int(sys.argv[2]) if len(sys.argv) > 2 else 10)
    else: print(__doc__)
