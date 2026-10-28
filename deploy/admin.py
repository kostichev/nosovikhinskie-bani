#!/usr/bin/env python3
"""Носовихинские бани — админка сайта (цены, расписание, меню, контакты, баннер, FAQ).

Слушает 127.0.0.1:8096, nginx отдаёт её по адресу /admin/.
Данные: /var/lib/nosbani/site.json. После сохранения сайт пересобирается (nosbani-rebuild).
Только стандартная библиотека Python.

Команды:
  nosbani-admin serve            — запуск (делает systemd)
  nosbani-admin passwd [логин]   — задать пароль (по умолчанию логин admin)
  nosbani-admin users            — список логинов
"""
import json, os, re, sys, time, hmac, hashlib, secrets, shutil, subprocess, getpass, threading, html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from urllib.parse import parse_qs

PORT = 8096
DATA = "/var/lib/nosbani/site.json"
HIST = "/var/lib/nosbani/history"
AUTH = "/etc/nosbani/admin.json"
DEFAULT = "/var/www/nosbani/build/data/site.json"
REBUILD = "/usr/local/bin/nosbani-rebuild"
LOCK = threading.Lock()


# ---------------------------------------------------------------- пароли и сессии
def auth_load():
    try:
        return json.load(open(AUTH))
    except Exception:
        return {"users": {}, "secret": secrets.token_hex(32)}


def auth_save(a):
    os.makedirs(os.path.dirname(AUTH), exist_ok=True)
    old = os.umask(0o077)
    json.dump(a, open(AUTH, "w"))
    os.umask(old); os.chmod(AUTH, 0o600)


def pw_hash(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 240000).hex()


def check_pw(user, pw):
    u = auth_load()["users"].get(user)
    return bool(u) and hmac.compare_digest(u["hash"], pw_hash(pw, u["salt"]))


def make_token(user):
    a = auth_load(); exp = str(int(time.time()) + 12 * 3600)
    sig = hmac.new(a["secret"].encode(), f"{user}|{exp}".encode(), "sha256").hexdigest()
    return f"{user}|{exp}|{sig}"


def check_token(tok):
    try:
        user, exp, sig = tok.split("|")
        a = auth_load()
        good = hmac.new(a["secret"].encode(), f"{user}|{exp}".encode(), "sha256").hexdigest()
        return user if hmac.compare_digest(sig, good) and int(exp) > time.time() and user in a["users"] else None
    except Exception:
        return None


FAILS = {}
def too_many(ip):
    now = time.time(); f = [t for t in FAILS.get(ip, []) if now - t < 900]; FAILS[ip] = f
    return len(f) >= 6


# ---------------------------------------------------------------- данные
def load_data():
    if not os.path.exists(DATA):
        os.makedirs(os.path.dirname(DATA), exist_ok=True); shutil.copy(DEFAULT, DATA)
    return json.load(open(DATA, encoding="utf-8"))


def clean(v, n=400):
    return re.sub(r"[<>\x00-\x08\x0b-\x1f]", "", str(v if v is not None else "")).strip()[:n]


def num(v, lo=0, hi=1_000_000):
    try:
        x = int(round(float(str(v).replace(" ", "").replace(" ", "").replace(",", "."))))
    except Exception:
        raise ValueError(f"не число: {v!r}")
    if not lo <= x <= hi:
        raise ValueError(f"число вне диапазона: {x}")
    return x


def validate(d, base):
    """Приводит присланные данные к безопасному виду. Структура — как в base (текущих данных)."""
    out = dict(base)
    c = d.get("contacts", {})
    out["contacts"] = {k: clean(c.get(k, base["contacts"].get(k, "")), 60) for k in base["contacts"]}
    for k in ("opens", "closes"):
        if not re.fullmatch(r"\d{1,2}:\d{2}", out["contacts"][k]): raise ValueError("время работы в формате 10:00")
    bn = d.get("banner", {})
    out["banner"] = {"on": bool(bn.get("on")), "text": clean(bn.get("text"), 160), "link": clean(bn.get("link"), 200)}
    if out["banner"]["link"] and not re.match(r"^(https?://|/|#|tel:)", out["banner"]["link"]): raise ValueError("ссылка баннера должна начинаться с https:// или /")
    out["hall"] = {k: num(d["hall"].get(k, v)) for k, v in base["hall"].items()}
    baths = []
    for old, new in zip(base["baths"], d.get("baths", [])):
        x = dict(old)
        x.update(name=clean(new.get("name"), 40) or old["name"], badge=clean(new.get("badge"), 40), d=clean(new.get("d"), 300), price=num(new.get("price")), base=num(new.get("base"), 1, 50))
        if "cap" in old: x["cap"] = num(new.get("cap", old["cap"]), 1, 60)
        if "hourExtra" in old: x["hourExtra"] = num(new.get("hourExtra", old["hourExtra"]))
        if "pkg" in old: x["pkg"] = num(new.get("pkg", old["pkg"]), 1, 24)
        baths.append(x)
    out["baths"] = baths
    for k in ("extraGuest", "cabGuest"): out[k] = num(d.get(k, base[k]))
    out["minHours"] = num(d.get("minHours", base["minHours"]), 1, 12)
    ch = d.get("chan", {}); out["chan"] = {"price": num(ch.get("price")), "hours": num(ch.get("hours"), 1, 24), "cap": num(ch.get("cap"), 1, 30), "hourExtra": num(ch.get("hourExtra"))}
    rit, seen = [], set()
    for i, r in enumerate(d.get("rituals", [])[:60]):
        name = clean(r.get("name"), 60)
        if not name: continue
        rid = re.sub(r"[^a-z0-9]", "", str(r.get("id") or "")) or f"r{i}"
        while rid in seen: rid += "x"
        seen.add(rid)
        rit.append({"id": rid, "g": clean(r.get("g"), 30) or "Парение", "name": name, "time": clean(r.get("time"), 40), "price": num(r.get("price")), "d": clean(r.get("d"), 300), **({"top": 1} if r.get("top") else {})})
    if not rit: raise ValueError("нужна хотя бы одна услуга")
    out["rituals"] = rit
    ex = []
    for i, e in enumerate(d.get("extras", [])[:20]):
        if clean(e.get("name")):
            ex.append({"id": re.sub(r"[^a-z0-9]", "", str(e.get("id") or "")) or f"e{i}", "name": clean(e.get("name"), 60), "price": num(e.get("price") or 0), "note": clean(e.get("note"), 80)})
    out["extras"] = ex
    sch = {}
    for k in ("weekday", "weekend"):
        lst = []
        for x in d.get("schedule", {}).get(k, [])[:20]:
            t = clean(x.get("time"), 5)
            if not re.fullmatch(r"\d{2}:\d{2}", t): raise ValueError(f"время пара в формате 09:30, а не «{t}»")
            if clean(x.get("name"), 40): lst.append({"time": t, "name": clean(x.get("name"), 40)})
        sch[k] = sorted(lst, key=lambda x: x["time"])
    out["schedule"] = sch
    menu = []
    for m, mb in zip(d.get("menu", []), base["menu"]):
        cats = []
        for c in m.get("cats", [])[:40]:
            items = [{"name": clean(i.get("name"), 90), "weight": clean(i.get("weight"), 30), "price": clean(i.get("price"), 30), "desc": clean(i.get("desc"), 300), **({"hidden": True} if i.get("hidden") else {})}
                     for i in c.get("items", [])[:80] if clean(i.get("name"))]
            if clean(c.get("title")) and items: cats.append({"title": clean(c.get("title"), 50), "items": items})
        menu.append({"id": mb["id"], "title": mb["title"], "cats": cats})
    out["menu"] = menu
    out["menu_featured"] = [{"name": clean(x.get("name"), 60), "weight": clean(x.get("weight"), 30), "price": clean(x.get("price"), 30)} for x in d.get("menu_featured", [])[:8] if clean(x.get("name"))]
    out["faq"] = [{"q": clean(x.get("q"), 200), "a": clean(x.get("a"), 1200)} for x in d.get("faq", [])[:30] if clean(x.get("q")) and clean(x.get("a"))]
    s = d.get("seo", {})
    out["seo"] = {"ym": re.sub(r"\D", "", str(s.get("ym", "")))[:12], "ya_verify": re.sub(r"[^\w-]", "", str(s.get("ya_verify", "")))[:80], "g_verify": re.sub(r"[^\w-]", "", str(s.get("g_verify", "")))[:80]}
    return out


def save_and_build(newd, user):
    with LOCK:
        os.makedirs(HIST, exist_ok=True)
        if os.path.exists(DATA):
            shutil.copy(DATA, f"{HIST}/{time.strftime('%Y%m%d-%H%M%S')}-{re.sub(r'[^a-z0-9]', '', user)}.json")
            for f in sorted(os.listdir(HIST))[:-60]: os.remove(os.path.join(HIST, f))
        tmp = DATA + ".tmp"; json.dump(newd, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace(tmp, DATA)
        r = subprocess.run([REBUILD], capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            raise RuntimeError("сайт не пересобрался: " + (r.stderr or r.stdout)[-600:])


# ---------------------------------------------------------------- HTTP
PAGE = open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "admin.html"), encoding="utf-8").read() if os.path.exists(os.path.join(os.path.dirname(os.path.realpath(__file__)), "admin.html")) else ""
LOGIN = """<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Вход — админка</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0d0b08;color:#ece7da;font:16px/1.5 system-ui,sans-serif}form{display:grid;gap:12px;width:min(340px,90vw);padding:28px;border:1px solid rgba(236,231,218,.15);border-radius:18px;background:#15120e}
h1{margin:0 0 6px;font:400 28px Georgia,serif}input{padding:12px 14px;border-radius:10px;border:1px solid rgba(236,231,218,.2);background:#0d0b08;color:#ece7da;font:inherit}button{padding:12px;border:0;border-radius:999px;background:#a6b74b;color:#141109;font:600 15px system-ui;cursor:pointer}p{margin:0;color:#e07a48;font-size:14px}</style></head>
<body><form method="post" action="/admin/login"><h1>Админка сайта</h1><input name="u" placeholder="Логин" value="admin" autocomplete="username"><input name="p" type="password" placeholder="Пароль" autocomplete="current-password" autofocus>%ERR%<button>Войти</button></form></body></html>"""


class H(BaseHTTPRequestHandler):
    def ip(self): return self.headers.get("X-Real-IP") or self.client_address[0]

    def user(self):
        c = SimpleCookie(self.headers.get("Cookie", ""))
        return check_token(c["nbadm"].value) if "nbadm" in c else None

    def send(self, code, body, ctype="text/html; charset=utf-8", extra=()):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        for k, v in [("Content-Type", ctype), ("Content-Length", str(len(b))), ("Cache-Control", "no-store"), ("X-Robots-Tag", "noindex, nofollow"),
                     ("X-Frame-Options", "DENY"), ("Referrer-Policy", "same-origin")] + list(extra):
            self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)

    def js(self, code, obj): self.send(code, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

    def body(self, limit=3_000_000):
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit: raise ValueError("слишком большой запрос")
        return self.rfile.read(n)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p in ("/admin", "/admin/"):
            if not self.user(): return self.send(200, LOGIN.replace("%ERR%", ""))
            return self.send(200, PAGE)
        if p == "/admin/api/data":
            if not self.user(): return self.js(401, {"error": "войдите заново"})
            d = load_data(); hist = sorted(os.listdir(HIST), reverse=True)[:30] if os.path.isdir(HIST) else []
            return self.js(200, {"data": d, "history": hist, "user": self.user()})
        self.send(404, "not found", "text/plain")

    def do_POST(self):
        p = self.path.split("?")[0]
        if p == "/admin/login":
            if too_many(self.ip()): return self.send(429, LOGIN.replace("%ERR%", "<p>Слишком много попыток. Подождите 15 минут.</p>"))
            f = parse_qs(self.body(4000).decode(errors="ignore"))
            u, pw = (f.get("u") or [""])[0].strip(), (f.get("p") or [""])[0]
            if check_pw(u, pw):
                secure = "; Secure" if self.headers.get("X-Forwarded-Proto") == "https" else ""
                return self.send(303, "", extra=[("Location", "/admin/"), ("Set-Cookie", f"nbadm={make_token(u)}; Path=/admin; HttpOnly; SameSite=Strict; Max-Age=43200{secure}")])
            FAILS.setdefault(self.ip(), []).append(time.time()); time.sleep(1)
            return self.send(401, LOGIN.replace("%ERR%", "<p>Неверный логин или пароль</p>"))
        if p == "/admin/logout":
            return self.send(303, "", extra=[("Location", "/admin/"), ("Set-Cookie", "nbadm=; Path=/admin; Max-Age=0")])
        user = self.user()
        if not user: return self.js(401, {"error": "войдите заново"})
        if self.headers.get("X-Requested-With") != "nbadmin": return self.js(403, {"error": "запрос отклонён"})
        try:
            if p == "/admin/api/save":
                d = json.loads(self.body())
                nd = validate(d, load_data()); save_and_build(nd, user)
                return self.js(200, {"ok": True, "data": nd})
            if p == "/admin/api/restore":
                name = os.path.basename(json.loads(self.body(2000)).get("name", ""))
                f = os.path.join(HIST, name)
                if not re.fullmatch(r"[\w-]+\.json", name) or not os.path.exists(f): return self.js(404, {"error": "нет такой версии"})
                nd = validate(json.load(open(f, encoding="utf-8")), load_data()); save_and_build(nd, user)
                return self.js(200, {"ok": True, "data": nd})
        except (ValueError, KeyError, TypeError) as e:
            return self.js(422, {"error": str(e)})
        except Exception as e:
            return self.js(500, {"error": str(e)[:500]})
        self.js(404, {"error": "нет такого действия"})

    def log_message(self, *a): pass


def cmd_passwd(user="admin"):
    if not re.fullmatch(r"[a-z0-9_.-]{2,32}", user): sys.exit("Логин: латиница, цифры, 2–32 символа")
    p1 = getpass.getpass(f"Новый пароль для «{user}» (минимум 8 символов): ")
    if len(p1) < 8: sys.exit("Слишком короткий пароль")
    if getpass.getpass("Повторите пароль: ") != p1: sys.exit("Пароли не совпали")
    a = auth_load(); salt = secrets.token_hex(16)
    a["users"][user] = {"salt": salt, "hash": pw_hash(p1, salt)}; auth_save(a)
    print(f"Готово. Вход: /admin/ , логин {user}")


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if c == "serve": ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
    elif c == "passwd": cmd_passwd(*(sys.argv[2:3]))
    elif c == "users": print("\n".join(auth_load()["users"]) or "нет пользователей — задайте пароль: nosbani-admin passwd")
    else: print(__doc__)
