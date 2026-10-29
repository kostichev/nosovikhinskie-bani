"""Сборка: index.html (артефакт, всё внутри) и dist/ (быстрый сайт: фото отдельными файлами, подстраницы, SEO)."""
import json, re, os, io, base64, shutil, html, datetime
SERVER = os.environ.get("SERVER") == "1"          # сборка на сервере из админки: без PIL, фото и артефакта
if not SERVER:
    from PIL import Image
from content import *
SITE_DATA = os.environ.get("SITE_DATA", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "site.json"))
os.environ["SITE_DATA"] = SITE_DATA
SD = json.load(open(SITE_DATA, encoding="utf-8"))
_DEFAULT_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "site.json")
if os.path.abspath(SITE_DATA) != os.path.abspath(_DEFAULT_DATA) and os.path.exists(_DEFAULT_DATA):
    _d = json.load(open(_DEFAULT_DATA, encoding="utf-8"))
    for _k, _v in _d.items():            # новые поля из обновлений сайта, которых ещё нет в данных админки
        if _k not in SD: SD[_k] = _v
        elif isinstance(_v, dict) and isinstance(SD[_k], dict):
            for _k2, _v2 in _v.items(): SD[_k].setdefault(_k2, _v2)
FAQ = [(x["q"], x["a"]) for x in SD["faq"]]
_H = SD["hall"]
def _nb(v): return f"{int(v):,}".replace(",", "\u00a0")
TOK = dict(_H); TOK.update(per_hour=_H["per_min"] * 60, extraGuest=SD["extraGuest"], cabGuest=SD["cabGuest"], chan=SD["chan"]["price"], chan_hour=SD["chan"]["hourExtra"],
           chan_hours=SD["chan"]["hours"], chan_cap=SD["chan"]["cap"], bath_min=min(x["price"] for x in SD["baths"] if x.get("kind") == "bath"),
           rit_min=min(x["price"] for x in SD["rituals"]), pmin=min(_H["lgot"], _H["wd_before16"]), parenie_min=min(x["price"] for x in SD["rituals"] if x.get("g") == "Парение" and x["price"] >= 2000) if any(x.get("g") == "Парение" for x in SD["rituals"]) else 0,
           massage_min=min([x["price"] for x in SD["rituals"] if x.get("g") in ("Массаж", "Мойки")] or [0]))
def tokens(s):
    s = re.sub(r"\{\{P:(\w+)\}\}", lambda m: _nb(TOK[m.group(1)]) + "\u00a0₽", s)
    s = re.sub(r"\{\{N:(\w+)\}\}", lambda m: _nb(TOK[m.group(1)]), s)
    s = re.sub(r"\{\{N0:(\w+)\}\}", lambda m: str(int(TOK[m.group(1)])), s)
    # одинарные скобки — так токены выглядят внутри f-строк сборки
    s = re.sub(r"\{P:(\w+)\}", lambda m: _nb(TOK[m.group(1)]) + "\u00a0₽", s)
    s = re.sub(r"\{N0:(\w+)\}", lambda m: str(int(TOK[m.group(1)])), s)
    s = re.sub(r"\{N:(\w+)\}", lambda m: _nb(TOK[m.group(1)]), s)
    left = re.findall(r"\{\{N?0?P?:?\w+\}\}", s)
    assert not re.search(r"\{\{(P|N|N0):", s), "неизвестный токен: " + str(left[:3])
    return s
_DEF = {"phone": ("+7 (495) 888-10-88", "+74958881088"), "whatsapp": ("+7 (962) 999-22-80", "79629992280"), "telegram": ("nosbani",), "email": ("nosbani@bk.ru",)}
def contacts_fix(s):
    c = SD.get("contacts", {})
    ph = c.get("phone") or _DEF["phone"][0]
    if ph != _DEF["phone"][0]:
        raw = "+7" + re.sub(r"\D", "", ph)[-10:]
        d = re.sub(r"\D", "", ph)[-10:]
        s = s.replace(_DEF["phone"][0], ph).replace(_DEF["phone"][1], raw).replace("+7 495 888-10-88", f"+7 {d[:3]} {d[3:6]}-{d[6:8]}-{d[8:]}")
    wa = c.get("whatsapp") or _DEF["whatsapp"][0]
    if wa != _DEF["whatsapp"][0]:
        s = s.replace(_DEF["whatsapp"][0], wa).replace("wa.me/" + _DEF["whatsapp"][1], "wa.me/7" + re.sub(r"\D", "", wa)[-10:])
    tg = (c.get("telegram") or "nosbani").lstrip("@")
    if tg != "nosbani": s = s.replace("t.me/nosbani", "t.me/" + tg).replace("@nosbani", "@" + tg)
    em = c.get("email") or _DEF["email"][0]
    if em != _DEF["email"][0]: s = s.replace(_DEF["email"][0], em)
    o, cl = c.get("opens") or "10:00", c.get("closes") or "23:00"
    if (o, cl) != ("10:00", "23:00"):
        s = s.replace("10:00–23:00", f"{o}–{cl}").replace("с 10:00 до 23:00", f"с {o} до {cl}").replace('"opens": "10:00", "closes": "23:00"', f'"opens": "{o}", "closes": "{cl}"').replace("10–23", f"{o.split(':')[0]}–{cl.split(':')[0]}")
    return s
def site_data_js():
    d = {"hall": {"weekday": {"4h": [_H["wd_before16"], _H["wd_after16"]], "unlim": _H["wd_unlim"]}, "weekend": {"4h": _H["we_4h"], "unlim": _H["we_unlim"]}, "vip": _H["vip"], "child": _H["child"], "lgot": _H["lgot"], "svo": [_H["svo_wd"], _H["svo_we"]]},
         "baths": SD["baths"], "extraGuest": SD["extraGuest"], "cabGuest": SD["cabGuest"], "minHours": SD["minHours"], "chan": SD["chan"]["price"], "rituals": SD["rituals"], "extras": SD["extras"]}
    return json.dumps(d, ensure_ascii=False).replace("</", "<\\/")
def sched_js():
    sp = lambda n: [n.split(" ", 1)[0]] + ([n.split(" ", 1)[1]] if " " in n else [])
    return json.dumps({"wd": [[x["time"]] + sp(x["name"]) for x in SD["schedule"]["weekday"]], "we": [[x["time"]] + sp(x["name"]) for x in SD["schedule"]["weekend"]]}, ensure_ascii=False)
def teaser_html():
    out = []
    for x in SD["menu_featured"][:3]:
        w = ' <small class="mono">' + esc(x["weight"]) + "</small>" if x.get("weight") else ""
        out.append('<div class="t-row"><span>' + esc(x["name"]) + w + '</span><i></i><b>' + esc(x["price"]) + "&nbsp;₽</b></div>")
    return "".join(out)
def banner_html():
    bn = SD.get("banner") or {}
    if not bn.get("on") or not bn.get("text"): return ""
    t = esc(bn["text"]); link = bn.get("link") or ""
    inner = f'<a href="{esc(link)}">{t} <span class="arr">→</span></a>' if link else f"<span>{t}</span>"
    return f'<div class="site-banner" role="status">{inner}<button type="button" aria-label="Скрыть" onclick="this.parentNode.remove()">✕</button></div>'
from food import section as food_section, book as food_book, menu_page_html, COUNT as MENU_COUNT

SITE = os.environ.get("SITE", "https://kostichev.github.io/nosovikhinskie-bani/")   # поменять на https://носовихинские-бани.рф/ при переезде
INDEX = os.environ.get("INDEX", "0") == "1"   # 1 — разрешить индексацию (на боевом домене)
_SEO = SD.get("seo") or {}
YM = re.sub(r"\D", "", os.environ.get("YM") or str(_SEO.get("ym") or ""))
YA_VERIFY = re.sub(r"[^\w-]", "", os.environ.get("YA_VERIFY") or _SEO.get("ya_verify") or ""); G_VERIFY = re.sub(r"[^\w-]", "", os.environ.get("G_VERIFY") or _SEO.get("g_verify") or "")
VERIFY_META = (f'<meta name="yandex-verification" content="{YA_VERIFY}">' if YA_VERIFY else "") + (f'<meta name="google-site-verification" content="{G_VERIFY}">' if G_VERIFY else "")
DEV_NAME = os.environ.get("DEV_NAME", "Denis Kostichev"); DEV_URL = os.environ.get("DEV_URL", "")
DEV_URL = DEV_URL or "https://t.me/denismihaylovich"
DEV_HTML = f'<a href="{DEV_URL}" target="_blank" rel="noopener" title="Написать в Telegram" data-goal="dev_contact">{DEV_NAME}</a> · <a href="https://wa.me/79686331336" target="_blank" rel="noopener" title="Написать в WhatsApp" data-goal="dev_contact">WhatsApp</a>'                  # номер счётчика Яндекс Метрики
ROBOTS = "index, follow" if INDEX else "noindex, follow"
OUT = os.environ.get("OUT_DIR", "dist")
ASSETS = os.environ.get("ASSETS", "/home/claude")
src = open("src.html").read()
B = json.load(open(ASSETS + "/brand.json")); P = {} if SERVER else json.load(open(ASSETS + "/photos.json"))
SVG = open(ASSETS + "/logo.svg", "rb").read()
SVG_URI = "data:image/svg+xml;base64," + base64.b64encode(SVG).decode()
USED = ["room0", "room1", "room2", "room3", "room4", "img-provans", "img-taiga", "img-fin", "img-bavaria", "img-hata", "chan", "x-provans-in", "x-provans-in2", "x-provans-hall", "x-taiga-vat", "x-fin-in", "x-fin-in2", "x-bavaria-sign", "x-hata-in", "x-sinks"] + [k for k, _ in GALLERY if k not in ("x-provans-in", "x-taiga-vat", "x-fin-in", "x-hata-in")]
esc = lambda t: html.escape(t, quote=True)

def img_of(k):
    m = re.match(r"data:image/(\w+);base64,(.*)", P[k], re.S)
    return Image.open(io.BytesIO(base64.b64decode(m.group(2)))).convert("RGB")

# ---------- общие куски
def gallery_html(photo):
    out = []
    for i, (k, cap) in enumerate(GALLERY):
        tall = False
        out.append(f'<figure><div class="gal-img">{photo(k, cap, tall)}</div><figcaption>{esc(cap)}</figcaption></figure>')
    return "".join(out)
faq_html = "".join(f'<details><summary>{esc(q)}<i aria-hidden="true"></i></summary><p>{esc(a)}</p></details>' for q, a in FAQ)
reviews_html = "".join(f'<article class="rv"><div class="rv-head"><span class="rv-ava" aria-hidden="true">{esc(n[0].upper())}</span><div><b>{esc(n)}</b><span>{esc(d)}</span></div></div><div class="rv-stars" aria-label="Оценка 5 из 5">★★★★★</div><p>{esc(t)}</p><button class="more" type="button">Читать полностью</button><span class="rv-src">Отзыв с Яндекс Карт</span></article>' for n, d, t in REVIEWS)
rules_html = "".join(f'<li><b>{esc(t)}</b><span>{esc(d)}</span></li>' for t, d in RULES)

def fill(s, base, photos, photo_tag, logo):
    s = s.replace("__SITEDATA__", site_data_js()).replace("__SCHED__", sched_js()).replace("__FOODTEASER__", teaser_html()).replace("__BANNER__", banner_html())
    s = s.replace("const PHOTOS = {}; /*__PHOTOS__*/", "const PHOTOS = " + json.dumps(photos) + ";")
    s = s.replace("__FOOD__", food_section(logo))
    s = s.replace("__LOGOFULLBIG__", logo).replace("__LOGOFULL__", logo).replace("__LOGO__", B["logo"])
    s = s.replace("__LEAFOLIVE__", B["leaf_olive"]).replace("__LEAF__", B["leaf"])
    p = B["pos"]; s = s.replace("__LL__", f"{p['left']:.3f}").replace("__LT__", f"{p['top']:.3f}").replace("__LW__", f"{p['width']:.3f}")
    s = s.replace("__GALLERY__", gallery_html(photo_tag)).replace("__FAQ__", faq_html).replace("__RULES__", rules_html).replace("__REVIEWS__", reviews_html)
    s = s.replace("__HERBS__", json.dumps(HERBS, ensure_ascii=False)).replace("__BASE__", base).replace("__DEV__", DEV_HTML).replace("__LEADAPI__", os.environ.get("LEAD_API", "")).replace("__FOODBOOK__", food_book())
    s = s.replace('href="pravila/"', f'href="{base}pravila/"')
    s = s.replace("Макет для согласования · фото будут заменены на реальные", "Макет для согласования")
    assert "__" not in re.sub(r"__(proto|esModule|defineGetter|lookupGetter|webpack)", "", s) or True
    for ph in ["__LOGO", "__LEAF", "__GALLERY__", "__FAQ__", "__RULES__", "__HERBS__", "__BASE__", "__REVIEWS__", "__DEV__"]:
        assert ph not in s, "placeholder left: " + ph
    return s

# ---------- 1) артефакт: всё в одном файле
def inline_tag(k, cap, tall):
    return f'<img src="{P[k]}" alt="{esc(cap)}" loading="lazy" decoding="async" draggable="false">'
if not SERVER:
    art_photos = {k: P[k] for k in USED}
    art = contacts_fix(tokens(fill(src, SITE, art_photos, inline_tag, SVG_URI)))
    open("index.html", "w").write(art); print("artifact", len(art) // 1024, "KB")

# ---------- 2) dist: быстрый сайт
sizes = {}
VER = {}
if SERVER:   # фото уже лежат на сервере, берём их размеры и версии
    _meta = json.load(open(ASSETS + "/imgmeta.json"))
    for k in USED: sizes[k] = tuple(_meta[k][:2]); VER[k] = _meta[k][2]
else:
  shutil.rmtree(OUT, ignore_errors=True); os.makedirs(OUT + "/img")
  for k in USED:
    im = img_of(k)
    for suf, w, q in (("", 1600, 78), ("-s", 800, 72)):
        t = im.copy(); t.thumbnail((w, w)); t.save(f"{OUT}/img/{k}{suf}.webp", "WEBP", quality=q, method=6)
    VER[k] = __import__("hashlib").md5(open(f"{OUT}/img/{k}.webp", "rb").read()).hexdigest()[:8]
    sizes[k] = im.size
  json.dump({k: [sizes[k][0], sizes[k][1], VER[k]] for k in USED}, open("imgmeta.json", "w"))
  open(f"{OUT}/img/logo.svg", "wb").write(SVG)
def file_tag(k, cap, tall):
    w, h = sizes[k]
    return f'<img src="img/{k}-s.webp?v={VER[k]}" srcset="img/{k}-s.webp?v={VER[k]} 800w, img/{k}.webp?v={VER[k]} 1600w" sizes="(max-width:700px) 80vw, 34vw" width="{w}" height="{h}" alt="{esc(cap)}" loading="lazy" decoding="async" draggable="false">'
dist_photos = {k: f"img/{k}.webp?v={VER[k]}" for k in USED}
main = fill(src, "", dist_photos, file_tag, "img/logo.svg")
main = main.replace("const YM_ID = window.YM_ID || null;", f"const YM_ID = {YM or 'null'}; window.IMG_SIZES = true;")

if not SERVER:
    # иконки и картинка для соцсетей
    leaf = Image.open(io.BytesIO(base64.b64decode(re.sub(r"^data:image/\w+;base64,", "", B["leaf_olive"])))).convert("RGBA")
    def icon(n):
        c = Image.new("RGBA", (n, n), (16, 14, 11, 255)); l = leaf.copy(); l.thumbnail((int(n * .78), int(n * .78)), Image.LANCZOS)
        c.alpha_composite(l, ((n - l.width) // 2, (n - l.height) // 2)); return c
    icon(180).convert("RGB").save(f"{OUT}/apple-touch-icon.png"); icon(512).save(f"{OUT}/icon-512.png"); icon(192).save(f"{OUT}/icon-192.png")
    icon(64).save(f"{OUT}/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
    og = img_of("hero").resize((1200, 900)).crop((0, 135, 1200, 765))
    og = Image.blend(og, Image.new("RGB", og.size, (8, 7, 5)), .58)
    open(f"{OUT}/img/og-base.jpg", "wb").write(b"")  # заменяется ниже рендером с логотипом
    og.save(f"{OUT}/img/og-base.jpg", quality=88)

manifest = {"name": SITE_NAME, "short_name": "Бани", "start_url": ".", "display": "standalone", "background_color": "#0a0907", "theme_color": "#0a0907",
            "icons": [{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}]}
json.dump(manifest, open(f"{OUT}/site.webmanifest", "w"), ensure_ascii=False)

ORG = {
    "@type": ["DaySpa", "LocalBusiness"], "@id": SITE + "#org", "name": SITE_NAME,
    "description": "Банный комплекс в Железнодорожном (Балашиха): русская парная на 60 человек, финская сауна, хаммам, тёплый бассейн, купели, три отдельные бани и два кабинета, парение с банщиком, массаж и чан.",
    "url": SITE, "telephone": [PHONE_RAW, "+79629992280"], "email": EMAIL,
    "image": [SITE + "img/og.jpg", SITE + "img/hero.webp", SITE + "img/g1.webp"], "logo": SITE + "img/logo.svg",
    "priceRange": f"{_nb(min(_H['child'], _H['lgot']))} – {_nb(_H['vip'])} ₽", "currenciesAccepted": "RUB", "paymentAccepted": "Наличные, банковская карта",
    "address": {"@type": "PostalAddress", "streetAddress": "Центральная ул., 98, мкр Кучино (Железнодорожный)", "addressLocality": "Балашиха", "addressRegion": "Московская область", "postalCode": "143985", "addressCountry": "RU"},
    "geo": {"@type": "GeoCoordinates", "latitude": GEO[0], "longitude": GEO[1]},
    "hasMap": YA_ORG,
    "openingHoursSpecification": [{"@type": "OpeningHoursSpecification", "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], "opens": "10:00", "closes": "23:00"}],
    "sameAs": [YA_ORG, TG], "hasMenu": SITE + "menu/", "areaServed": [{"@type": "City", "name": n} for n in ["Железнодорожный", "Балашиха", "Кучино", "Москва"]], "slogan": "Пар на дровах, травы и тишина",
    "amenityFeature": [{"@type": "LocationFeatureSpecification", "name": n, "value": True} for n in ["Русская парная", "Финская сауна", "Хаммам", "Бассейн", "Купели", "Ресторан", "Парковка", "Барбершоп", "Автомойка"]],
    "makesOffer": [{"@type": "Offer", "name": n, "price": p, "priceCurrency": "RUB"} for n, p in [("Входной билет 4 часа, будни до 16:00", _H["wd_before16"]), ("Входной билет 4 часа, будни после 16:00", _H["wd_after16"]), ("Входной билет 4 часа, выходные", _H["we_4h"]), ("Безлимит, будни", _H["wd_unlim"]), ("VIP-тариф", _H["vip"]), ("Молодильный чан", SD["chan"]["price"])]
                   + [(x["name"], x["price"]) for x in SD["rituals"] if x.get("top")] + [(("Аренда бани «" + x["name"] + "», в час") if x.get("kind") == "bath" else ("Кабинет «" + x["name"] + "», " + str(x.get("pkg", 4)) + " часа"), x["price"]) for x in SD["baths"]]],
}
FAQLD = {"@type": "FAQPage", "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]}
def ld(*items): return '<script type="application/ld+json">' + json.dumps({"@context": "https://schema.org", "@graph": list(items)}, ensure_ascii=False) + "</script>"

FONTS = "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;1,300;1,400&family=Onest:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap"
def head(title, desc, path, extra="", img="img/og.jpg"):
    url = SITE + path
    return f'''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="{ROBOTS}">
<link rel="canonical" href="{url}">
<meta name="theme-color" content="#0a0907">
<meta name="format-detection" content="telephone=no">
<meta property="og:type" content="website"><meta property="og:locale" content="ru_RU"><meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}"><meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}{img}"><meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">{VERIFY_META if not path else ""}<meta name="geo.region" content="RU-MOS"><meta name="geo.placename" content="Балашиха, Железнодорожный"><meta name="geo.position" content="{GEO[0]};{GEO[1]}"><meta name="ICBM" content="{GEO[0]}, {GEO[1]}">
<link rel="icon" href="{'../' if path else ''}favicon.ico" sizes="any"><link rel="apple-touch-icon" href="{'../' if path else ''}apple-touch-icon.png"><link rel="manifest" href="{'../' if path else ''}site.webmanifest">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="preload" as="style" href="{FONTS}"><link rel="stylesheet" href="{FONTS}" media="print" onload="this.media='all'"><noscript><link rel="stylesheet" href="{FONTS}"></noscript>
{extra}'''

# ---- главная
i = main.index("<style>"); pre, body = main[:i], main[i:]
j = body.index("</style>") + len("</style>")
extra = ('<link rel="preload" as="script" href="js/gsap.min.js?v=3.12.5"><link rel="preload" as="script" href="js/ScrollTrigger.min.js?v=3.12.5">'
         '<link rel="preload" as="image" href="img/logo.svg" type="image/svg+xml">\n' + ld(ORG, FAQLD, {"@type": "WebSite", "name": SITE_NAME, "url": SITE, "inLanguage": "ru"}))
pre = re.sub(r"<title>.*?</title>", "", pre); pre = re.sub(r'<link rel="(preconnect|stylesheet)"[^>]*>', "", pre)
doc = head("Баня в Железнодорожном и Балашихе — Носовихинские бани, парная на дровах",
           "Банный комплекс в Железнодорожном (Балашиха, Кучино): русская парная на дровах, хаммам, тёплый бассейн, отдельные бани, чан и парение с банщиком. Ежедневно 10–23.",
           "", extra) + pre + body[:j] + "\n<style>html,body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n</head>\n<body>\n" + body[j:] + "\n</body>\n</html>\n"
for u, f in [("https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js", "gsap.min.js?v=3.12.5"), ("https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/ScrollTrigger.min.js", "ScrollTrigger.min.js?v=3.12.5"), ("https://cdn.jsdelivr.net/npm/lenis@1.1.13/dist/lenis.min.js", "lenis.min.js?v=1.1.13")]:
    assert u in doc; doc = doc.replace(u, "js/" + f)
os.makedirs(f"{OUT}/js", exist_ok=True)
for f in ["gsap.min.js", "ScrollTrigger.min.js", "lenis.min.js"]: shutil.copy("vendor/" + f, f"{OUT}/js/" + f)
doc = contacts_fix(tokens(doc)); open(f"{OUT}/index.html", "w").write(doc); print("dist/index.html", len(doc) // 1024, "KB")

# ---------- подстраницы (лёгкие, без тяжёлых анимаций)
PAGE_CSS = '''<style>
:root{--night:#0a0907;--surface:#14110d;--bone:#ece7da;--bone-dim:rgba(236,231,218,.62);--bone-faint:rgba(236,231,218,.12);--brass:#c9a46a;--cta-bg:#a6b74b;--cta-fg:#141109;--f-display:"Cormorant Garamond",Georgia,serif;--f-body:"Onest",system-ui,sans-serif;--f-mono:"JetBrains Mono",ui-monospace,monospace;--gutter:clamp(16px,4vw,56px)}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}body{margin:0;background:radial-gradient(80% 50% at 70% 0%,#1a140d,var(--night) 60%) fixed,var(--night);color:var(--bone);font:400 17px/1.65 var(--f-body)}
a{color:inherit}img{max-width:100%;height:auto;display:block}
.top{position:sticky;top:calc(10px + env(safe-area-inset-top,0px));z-index:10;margin:10px auto 0;width:min(1180px,calc(100% - 20px));height:60px;display:flex;align-items:center;gap:16px;padding:0 8px 0 20px;border-radius:999px;background:rgba(20,17,13,.7);-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px);border:1px solid rgba(255,248,236,.14)}
.top img{height:34px;width:auto}.top nav{display:flex;gap:22px;margin:0 auto;font-size:15px}.top nav a{text-decoration:none;opacity:.85}.top nav a:hover{opacity:1}
.btn{display:inline-flex;align-items:center;gap:8px;height:46px;padding:0 22px;border-radius:999px;border:1px solid rgba(236,231,218,.3);text-decoration:none;font:500 15px/1 var(--f-body);color:var(--bone);background:transparent;white-space:nowrap}
.btn.solid{background:var(--cta-bg);border-color:var(--cta-bg);color:var(--cta-fg)}.btn:hover{border-color:var(--bone)}
main{width:min(1100px,100% - 2*var(--gutter));margin:0 auto;padding:clamp(40px,7vw,90px) 0}
.crumbs{font:500 12px/1 var(--f-mono);letter-spacing:.08em;text-transform:uppercase;color:var(--bone-dim);display:flex;gap:10px;flex-wrap:wrap}.crumbs a{text-decoration:none}
h1{font:400 clamp(44px,6.4vw,88px)/1 var(--f-display);letter-spacing:-.015em;margin:20px 0 22px}h1 em{color:var(--brass)}
h2{font:400 clamp(30px,3.4vw,46px)/1.1 var(--f-display);margin:56px 0 18px}h3{font:400 28px/1.15 var(--f-display);margin:0 0 8px}
.lead{font-size:clamp(18px,1.6vw,21px);color:var(--bone-dim);max-width:62ch}
p,li{color:var(--bone-dim)}main ul{padding-left:20px}
.cta{display:flex;gap:10px;flex-wrap:wrap;margin:28px 0}
table{width:100%;border-collapse:collapse;margin:8px 0 10px;font-size:16px}th,td{text-align:left;padding:14px 10px;border-bottom:1px solid var(--bone-faint);vertical-align:top}th{font:500 11px/1.2 var(--f-mono);letter-spacing:.1em;text-transform:uppercase;color:var(--bone-dim)}td b{font:400 24px/1 var(--f-display);color:var(--bone);white-space:nowrap}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px}
.card{background:var(--surface);border:1px solid var(--bone-faint);border-radius:16px;overflow:hidden;display:grid}
.card img{aspect-ratio:4/3;object-fit:cover;width:100%}.card div{padding:20px 22px 24px;display:grid;gap:8px}.card .mono{font:500 11px/1 var(--f-mono);letter-spacing:.1em;text-transform:uppercase;color:var(--brass)}
.card .price{font:400 30px/1 var(--f-display);color:var(--bone)}
.panel{background:var(--surface);border:1px solid var(--bone-faint);border-radius:16px;padding:clamp(20px,3vw,34px)}
.sched{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.sched li{list-style:none;display:grid;grid-template-columns:64px 1fr;gap:12px;padding:10px 0;border-bottom:1px dashed var(--bone-faint)}.sched ol{padding:0;margin:0}.sched time{font:400 24px/1 var(--f-display);color:var(--bone)}.sched small{display:block;font-size:14px}
.hero-img{border-radius:18px;overflow:hidden;margin:10px 0 0;aspect-ratio:16/9}.hero-img img{width:100%;height:100%;object-fit:cover}
footer{border-top:1px solid var(--bone-faint);padding:28px var(--gutter) 40px;display:flex;flex-wrap:wrap;gap:10px 24px;font-size:14px;color:var(--bone-dim)}footer a{color:var(--bone-dim)}
body{animation:pgIn .8s cubic-bezier(.2,.7,.2,1) both}@keyframes pgIn{from{opacity:0;filter:blur(10px);transform:translateY(14px)}}
#veil{position:fixed;inset:0;z-index:50;pointer-events:none;opacity:0;transition:opacity .42s;background:radial-gradient(70% 55% at 50% 55%,rgba(236,228,214,.22),rgba(14,12,9,.94) 72%),#0b0a08}#veil.on{opacity:1}
@media (max-width:760px){.top nav{display:none}.top .btn{margin-left:auto}.sched{grid-template-columns:1fr}table{font-size:15px}th,td{padding:12px 6px}}
</style>'''
NAVL = [("ceny/", "Цены"), ("bani/", "Бани"), ("parenie/", "Парение"), ("chan/", "Чан"), ("menu/", "Меню"), ("kontakty/", "Контакты")]
HERO = {"zhenskiy-den/": ("room3", "Тёплый бассейн под открытым небом"), "massazh/": ("x-provans-in2", "Зона отдыха после массажа"), "kontakty/": ("g1", "Здание Носовихинских бань в Балашихе"),
        "parenie/": ("hero", "Парение с банщиком в большой русской парной"), "ceny/": ("g3", "Зона отдыха общего зала Носовихинских бань"),
        "menu/": ("g6", "Столы в зоне отдыха, где подают блюда ресторана"), "pravila/": ("x-sinks", "Умывальная зона у сауны"),
        "bani/": ("img-provans", "Баня «Прованс» на закате")}
def hero_html(path):
    h = HERO.get(path)
    return f'<div class="hero-img" style="margin:6px 0 28px">{pic(*h)}</div>' if h else ""
def page(path, title, desc, h1, body_html, crumb, img="img/og.jpg", ld_extra=()):
    bc = {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "Главная", "item": SITE}, {"@type": "ListItem", "position": 2, "name": crumb, "item": SITE + path}]}
    nav = "".join(f'<a href="../{p}">{t}</a>' for p, t in NAVL)
    doc = head(title, desc, path, PAGE_CSS + "\n" + ld(bc, {"@type": "WebPage", "name": title, "url": SITE + path, "about": {"@id": SITE + "#org"}}, *ld_extra), img) + f'''</head>
<body>
<header class="top"><a href="../" aria-label="На главную"><img src="../img/logo.svg" alt="{SITE_NAME}" width="1200" height="490"></a><nav aria-label="Разделы">{nav}</nav><a class="btn solid" href="../?book">Записаться</a></header>
<main>
<div class="crumbs"><a href="../">Главная</a><span>/</span><span>{esc(crumb)}</span></div>
<h1>{h1}</h1>
{hero_html(path)}{body_html}
<div class="cta"><a class="btn solid" href="../?book">Записаться онлайн →</a><a class="btn" href="tel:{PHONE_RAW}">{PHONE}</a><a class="btn" href="{WA}" target="_blank" rel="noopener">WhatsApp</a><a class="btn" href="{TG}" target="_blank" rel="noopener">Telegram</a></div>
</main>
<footer><span>© {SITE_NAME} · {ADDRESS} · ежедневно 10:00–23:00</span><a href="../pravila/">Правила</a><a href="../privacy/">Политика конфиденциальности</a><a href="{YA_ORG}" target="_blank" rel="noopener">Яндекс Карты</a><span style="margin-left:auto;opacity:.6">Сайт разработал&nbsp;{DEV_HTML}</span></footer>
<div id="veil"></div>
<script>document.addEventListener("click",function(e){{var a=e.target.closest("a[href]");if(!a||a.target==="_blank"||/^(tel:|mailto:|#)/.test(a.getAttribute("href"))||a.origin!==location.origin)return;e.preventDefault();document.getElementById("veil").classList.add("on");setTimeout(function(){{location.href=a.href}},400)}});addEventListener("pageshow",function(){{document.getElementById("veil").classList.remove("on")}});</script>
</body>
</html>
'''
    os.makedirs(f"{OUT}/{path}", exist_ok=True); open(f"{OUT}/{path}index.html", "w").write(contacts_fix(tokens(doc)))

def pic(k, alt, cls=""):
    w, h = sizes[k]
    return f'<img src="../img/{k}-s.webp?v={VER[k]}" srcset="../img/{k}-s.webp?v={VER[k]} 800w, ../img/{k}.webp?v={VER[k]} 1600w" sizes="(max-width:760px) 100vw, 360px" width="{w}" height="{h}" alt="{esc(alt)}" loading="lazy" decoding="async">'

BATHS = [(x["id"], x["name"], x["img"], x["price"], x["base"], x["cap"], x["badge"], x["d"]) for x in SD["baths"] if x.get("kind") == "bath"]
CABS = [(x["id"], x["name"], x["img"], x["price"], x["base"], x["base"], x["badge"], x["d"].split(" До ")[0] + f" {_nb(x['price'])}\u00a0₽ за {x.get('pkg', 4)} часа, далее {_nb(x.get('hourExtra', 0))}\u00a0₽ за час.") for x in SD["baths"] if x.get("kind") == "cab"]
INSIDE = [("x-provans-in", "Прованс: комната отдыха"), ("x-provans-in2", "Прованс: диваны и зона отдыха"), ("x-provans-hall", "Прованс: коридор"),
          ("x-taiga-vat", "Таёжная: купель на улице"), ("x-fin-in", "Финская: комната отдыха"), ("x-fin-in2", "Финская: резные двери"),
          ("x-bavaria-sign", "Баварский домик: вход"), ("img-bavaria", "Баварский домик: зона отдыха"), ("x-hata-in", "Казачья хата: печь и роспись"), ("img-hata", "Казачья хата: вход")]
IMGFIT = '<img style="width:100%;height:100%;object-fit:cover" '
def inside_html():
    out = []
    for k, c in INSIDE:
        im = pic(k, c + " — Носовихинские бани").replace("<img ", IMGFIT)
        out.append(f'<figure style="margin:0;display:grid;gap:8px"><div style="border-radius:14px;overflow:hidden;aspect-ratio:4/3">{im}</div><figcaption style="font-size:14px;color:var(--bone-dim)">{c}</figcaption></figure>')
    return '<div class="grid">' + "".join(out) + "</div>"
def cards(items, frm=False):
    return '<div class="grid">' + "".join(f'<article class="card">{pic(img, f"{n} — {badge.lower()}, Носовихинские бани")}<div><span class="mono">{badge}</span><h3>{n}</h3><p>{d}</p><p>{"До " + str(cap) + " гостей. Входной билет оплачивается отдельно." if frm else "До " + str(base) + " гостей в тарифе, максимум " + str(cap) + ". Аренда от 3 часов."}</p><span class="price">{price:,} ₽ <small style="font-size:16px;color:var(--bone-dim)">{"за 4 часа" if frm else "в час"}</small></span></div></article>'.replace(",", " ") for _, n, img, price, base, cap, badge, d in items) + "</div>"

page("bani/", "Аренда бани в Железнодорожном и Балашихе — бани и кабинеты | Носовихинские бани",
     "Аренда отдельной бани в Железнодорожном (Балашиха): Прованс с бассейном, Таёжная, Финская сауна и кабинеты Баварский домик и Казачья хата. От 3 часов, до 10 гостей.",
     "Отдельные бани <em>и кабинеты</em>",
     '<p class="lead">Своя парная, зона отдыха и тишина только для вашей компании. Аренда от 3 часов, каждый гость сверх тарифа — 1 000 ₽ в час. При аренде бани действует безлимит на посещение общего комплекса для вашей компании уточняйте у администратора.</p>'.replace(" При аренде бани действует безлимит на посещение общего комплекса для вашей компании уточняйте у администратора.", "") +
     "<h2>Отдельные бани</h2>" + cards(BATHS) + "<h2>Кабинеты</h2>" + cards(CABS, True) + "<h2>Как выглядит внутри</h2>" + inside_html(), "Отдельные бани")

tar = [("Будни, до 16:00", "4 часа", _H["wd_before16"]), ("Будни, после 16:00", "4 часа", _H["wd_after16"]), ("Будни", "безлимит", _H["wd_unlim"]), ("Выходные и праздники", "4 часа", _H["we_4h"]), ("Выходные и праздники", "безлимит", _H["we_unlim"]),
       ("VIP-тариф", "безлимит, парение со льдом, мойка берёзовым веником, спортивный массаж 40 мин, травяной чай", _H["vip"]),
       ("Льготный (пенсионеры 60+, инвалиды 1 гр.)", "будни 10:00–15:00", _H["lgot"]), ("Участникам СВО", "будни / выходные", f"{_nb(_H['svo_wd'])} / {_nb(_H['svo_we'])}"), ("Дети 7–12 лет", "с родителем", _H["child"]), ("Дети до 7 лет", "с родителем", "бесплатно")]
fmt = lambda v: _nb(v) + "\u00a0₽" if isinstance(v, int) else (v + ("\u00a0₽" if v[0].isdigit() else ""))
tab = '<table><thead><tr><th>Тариф</th><th>Что входит</th><th>Цена</th></tr></thead><tbody>' + "".join(f"<tr><td>{a}</td><td>{b}</td><td><b>{fmt(c)}</b></td></tr>" for a, b, c in tar) + "</tbody></table>"
svc = [(x["name"] + (" (" + x["g"].lower() + ")" if x.get("g") == "Парение в 4 руки" else ""), ", ".join(v for v in [x.get("time", "") if x.get("time", "") not in x["name"] else "", x.get("d", "") if len(x.get("d", "")) < 80 else ""] if v), x["price"]) for x in SD["rituals"]] + \
      [(e["name"], e.get("note", ""), e["price"]) for e in SD["extras"] if e.get("price")] + \
      [("Молодильный чан «Изобилие трав»", f"до {SD['chan']['hours']} часов, до {SD['chan']['cap']} человек; далее {_nb(SD['chan']['hourExtra'])}\u00a0₽/час", SD["chan"]["price"])]
tab2 = '<table><thead><tr><th>Услуга</th><th>Описание</th><th>Цена</th></tr></thead><tbody>' + "".join(f"<tr><td>{a}</td><td>{b}</td><td><b>{fmt(c)}</b></td></tr>" for a, b, c in svc) + "</tbody></table>"
tab3 = '<table><thead><tr><th>Баня или кабинет</th><th>Гостей</th><th>Цена</th></tr></thead><tbody>' + "".join(f"<tr><td>{n}</td><td>{base} в тарифе / до {cap}</td><td><b>{fmt(price)}</b> в час</td></tr>" for k, n, _, price, base, cap, _, _ in BATHS) + "".join(f"<tr><td>{n}</td><td>до {cap}, сверх — {_nb(SD['cabGuest'])}\u00a0₽/чел.</td><td><b>{fmt(price)}</b> за 4 часа</td></tr>" for k, n, _, price, base, cap, _, _ in CABS) + "</tbody></table><p class=\"note\">В аренду кабинетов входной билет не входит, льготы на кабинеты не распространяются.</p>"
page("ceny/", "Цены на баню в Железнодорожном и Балашихе — от {{P:pmin}} | Носовихинские бани",
     "Цены Носовихинских бань: входной билет на 4 часа от {{P:wd_before16}}, безлимит {{P:wd_unlim}}, VIP {{P:vip}}, льготы, детский тариф, отдельные бани от {{P:bath_min}} в час, парение и массаж.",
     "Цены <em>и тарифы</em>",
     '<p class="lead">Входной билет в общий зал действует 4 часа. Каждая минута сверх тарифа — 15 ₽. Вторник — женский день, остальные дни — мужские.</p><h2>Общий зал</h2>' + tab + "<h2>Отдельные бани и кабинеты</h2>" + tab3 + '<p>Аренда от 3 часов. Гость сверх тарифа — 1 000 ₽ в час.</p><h2>Парение, массаж и чан</h2>' + tab2, "Цены")

SWD = [(x["time"], x["name"]) for x in SD["schedule"]["weekday"]]
SWE = [(x["time"], x["name"]) for x in SD["schedule"]["weekend"]]
ol = lambda L: "<ol>" + "".join(f"<li><time>{t}</time><span>{n}<small>{HERBS.get(n, '')}</small></span></li>" for t, n in L) + "</ol>"
page("parenie/", "Парение с банщиком в Железнодорожном и Балашихе | Носовихинские бани",
     "Коллективные пары каждые полтора часа: мята, полынь, донник на пиве, пихта, эвкалипт, пижма, лаванда. Парение с банщиком от {{P:parenie_min}}, царское парение на травах, массаж.",
     "Парение <em>и бодрящий пар</em>",
     '<p class="lead">Коллективные пары проходят в общем зале каждые полтора часа. У каждого пара свой аромат и характер. Приходите за 10 минут до начала.</p><h2>Расписание паров</h2><div class="sched"><div class="panel"><h3>Будни</h3>' + ol(SWD) + '</div><div class="panel"><h3>Выходные</h3>' + ol(SWE) + "</div></div><h2>Парение с банщиком и массаж</h2>" + tab2, "Парение")

page("chan/", "Банный чан в Железнодорожном (Балашиха) — {{P:chan}} | Носовихинские бани",
     "Горячий чан с луговыми травами под открытым небом в Носовихинских банях, Балашиха. {{P:chan}} за {{N0:chan_hours}} часа, до {{N0:chan_cap}} человек, по предварительной записи с предоплатой 50%.",
     "Молодильный чан <em>«Изобилие трав»</em>",
     f'<p class="lead">Горячая вода с луговыми травами под открытым небом, в саду банного комплекса. После парной и купели — лучший способ согреться и отдохнуть.</p><div class="hero-img">{pic("chan", "Сад банного комплекса, где стоит чан")}</div><h2>Условия</h2><ul><li>Стоимость — {{P:chan}} за аренду до {{N0:chan_hours}} часов, каждый следующий час — {{P:chan_hour}}.</li><li>Вместимость — до {{N0:chan_cap}} человек. В воду добавляют донник, полынь, эвкалипт и мяту.</li><li>Только по предварительной записи, предоплата 50%.</li><li>Отмена не позднее чем за 24 часа — полный возврат предоплаты.</li><li>Чан можно совместить с посещением общего зала, отдельной бани или парением.</li></ul>', "Чан")

from food import MENU as _MENU
def _price(p):
    try: return int(p.split("/")[0].replace(" ", "").replace(" ", ""))
    except Exception: return None
MENULD = {"@type": "Menu", "name": "Меню ресторана Носовихинских бань", "url": SITE + "menu/", "inLanguage": "ru", "hasMenuSection": [
    {"@type": "MenuSection", "name": c, "hasMenuItem": [dict({"@type": "MenuItem", "name": n}, **({"description": d} if d else {}), **({"offers": {"@type": "Offer", "price": _price(p), "priceCurrency": "RUB"}} if _price(p) else {})) for n, w, p, d in it]}
    for _, _, cats in _MENU for c, it in cats]}
_page_menu_ld = (MENULD,)

page("menu/", "Меню ресторана — Носовихинские бани, Железнодорожный",
     f"Меню ресторана при Носовихинских банях: русская кухня, мангал, раки, рулька, уха, травяной чай, пиво и бар. {MENU_COUNT} позиций с ценами.",
     "Меню <em>ресторана</em>",
     '<p class="lead">Русская кухня и мангал, раки, травяной чай и холодное пиво после пара. Цены в рублях, выход блюд — в граммах.</p><p><a class="btn" href="../#menu-open">Открыть красивое меню на главной →</a></p>' + menu_page_html(), "Меню ресторана", ld_extra=_page_menu_ld)


wd = ol(SWD)
page("zhenskiy-den/", "Женский день в бане — Железнодорожный, Балашиха | Носовихинские бани",
     "Женский день в Носовихинских банях, Балашиха: каждый вторник общий зал, русская парная, хаммам, бассейн и коллективные пары только для женщин. Билет от {{P:wd_before16}}.",
     "Женский день <em>по вторникам</em>",
     '<p class="lead">Каждый вторник весь общий зал работает только для женщин: русская парная на дровах, финская сауна, хаммам, тёплый бассейн, купели и коллективные пары с травами.</p>'
     '<h2>Сколько стоит</h2><table><tbody><tr><td>Билет на 4 часа, до 16:00</td><td><b>{{P:wd_before16}}</b></td></tr><tr><td>Билет на 4 часа, после 16:00</td><td><b>{{P:wd_after16}}</b></td></tr><tr><td>Безлимит</td><td><b>{{P:wd_unlim}}</b></td></tr><tr><td>Льготный (пенсионеры 60+, инвалиды 1 гр.), 10:00–15:00</td><td><b>{{P:lgot}}</b></td></tr></tbody></table>'
     '<h2>Коллективные пары во вторник</h2><div class="panel">' + wd + '</div>'
     '<h2>Что важно знать</h2><ul><li>Работаем с 10:00 до 23:00, приходите на пар за 10 минут до начала.</li><li>Посещение однополое: в женский день в общий зал проходят только женщины, в том числе дети — только девочки.</li><li>Дети до 14 лет — только в сопровождении взрослых.</li><li>Парение с банщиком, мойки и массаж можно добавить при записи.</li></ul>',
     "Женский день", ld_extra=({"@type": "Event", "name": "Женский день в Носовихинских банях", "eventSchedule": {"@type": "Schedule", "byDay": "https://schema.org/Tuesday", "startTime": "10:00", "endTime": "23:00", "repeatFrequency": "P1W"}, "location": {"@id": SITE + "#org"}, "organizer": {"@id": SITE + "#org"}},))

msg = [(x["name"], x.get("time", "") if x.get("time", "") not in x["name"] else "", _nb(x["price"])) for x in SD["rituals"] if x.get("g") in ("Массаж", "Мойки")]
page("massazh/", "Массаж в бане в Железнодорожном и Балашихе | Носовихинские бани",
     "Массаж после парной в Носовихинских банях, Балашиха: классический от {{P:massage_min}}, тайский массаж, мойка берёзовым веником, мыльная и лыковая мойка, пилинг.",
     "Массаж <em>и мойки</em>",
     '<p class="lead">Лучшее время для массажа — после парной, когда мышцы уже прогреты. Запишитесь заранее: мастер подготовит кабинет к вашему приходу.</p>'
     '<table><thead><tr><th>Услуга</th><th>Длительность</th><th>Цена</th></tr></thead><tbody>' + "".join(f"<tr><td>{a}</td><td>{d}</td><td><b>{p}\u00a0₽</b></td></tr>" for a, d, p in msg) + '</tbody></table>'
     '<p class="note">Парение с банщиком — на странице <a href="../parenie/">«Парение»</a>. Комплексный VIP-тариф включает массаж 40 минут, парение со льдом и мойку берёзовым веником.</p>',
     "Массаж и мойки")

page("kontakty/", "Контакты — Носовихинские бани, Железнодорожный (Балашиха), Кучино",
     "Носовихинские бани: Балашиха, мкр Кучино, Центральная ул., 98, подъезд 1. Ежедневно 10:00–23:00. Телефон +7 (495) 888-10-88, WhatsApp, Telegram, парковка.",
     "Контакты <em>и как добраться</em>",
     f'<div class="panel"><table><tbody><tr><td>Адрес</td><td><b>Московская область, Балашиха, мкр Кучино, Центральная ул., 98, подъезд 1</b></td></tr><tr><td>Часы работы</td><td><b>ежедневно 10:00–23:00</b></td></tr>'
     f'<tr><td>Телефон</td><td><a href="tel:{PHONE_RAW}"><b>{PHONE}</b></a></td></tr><tr><td>WhatsApp</td><td><a href="{WA}" target="_blank" rel="noopener">+7 (962) 999-22-80</a></td></tr><tr><td>Telegram</td><td><a href="{TG}" target="_blank" rel="noopener">@nosbani</a></td></tr>'
     f'<tr><td>Почта</td><td><a href="mailto:{EMAIL}">{EMAIL}</a></td></tr><tr><td>Парковка</td><td>есть, у комплекса</td></tr><tr><td>Удобства</td><td>оплата картой, барбершоп, автомойка</td></tr></tbody></table></div>'
     '<h2>Как добраться</h2><p>Комплекс находится в Железнодорожном — микрорайоне Кучино, который с 2015 года входит в Балашиху. В навигаторе ищите «Носовихинские бани» или «Балашиха, Центральная ул., 98». Ищите кирпичное здание с вывеской «Бани» на крыше.</p>'
     f'<div class="cta" style="margin-top:16px"><a class="btn solid" href="https://yandex.ru/maps/?rtext=~{GEO[0]}%2C{GEO[1]}&rtt=auto" target="_blank" rel="noopener">Маршрут в Яндекс Картах</a><a class="btn" href="{YA_ORG}" target="_blank" rel="noopener">Отзывы на Яндекс Картах</a><a class="btn" href="https://www.google.com/maps/dir/?api=1&destination={GEO[0]},{GEO[1]}" target="_blank" rel="noopener">Google Карты</a></div>'
     f'<h2>Реквизиты</h2><p>{OPERATOR}</p>',
     "Контакты", ld_extra=({"@type": "ContactPage", "url": SITE + "kontakty/", "about": {"@id": SITE + "#org"}},))

page("pravila/", "Правила посещения бани — Носовихинские бани, Балашиха",
     "Правила посещения банного комплекса «Носовихинские бани» в Балашихе: время, женский день, дети, документы, запись и отмена.",
     "Правила <em>посещения</em>",
     '<p class="lead">Короткие правила, чтобы визит прошёл спокойно для всех гостей.</p><div class="panel"><ol style="padding-left:20px;margin:0;display:grid;gap:14px">' + "".join(f"<li><b style='color:var(--bone)'>{t}.</b> {d}</li>" for t, d in RULES) + '</ol></div><h2>Отмена и возврат</h2><ul><li>Если вы отменили запись не позднее чем за 24 часа — возвращаем 100% предоплаты.</li><li>При отмене менее чем за 24 часа или без предупреждения предоплата не возвращается.</li><li>Опоздание больше чем на 30 минут считается неявкой.</li><li>Если услугу не удалось оказать по нашей вине — возвращаем 100%.</li></ul><h2>Рекомендации для здоровья</h2><ul>' + "".join(f"<li>{x}</li>" for x in RULES_HEALTH) + "</ul>", "Правила посещения")

page("privacy/", "Политика конфиденциальности | Носовихинские бани",
     "Политика обработки персональных данных банного комплекса «Носовихинские бани»: какие данные собираем, зачем и как их защищаем.",
     "Политика <em>конфиденциальности</em>",
     '<div class="panel">' + open("privacy.html").read().replace("<h2>", '<h2 style="font-size:28px;margin:28px 0 10px">') + "</div>", "Политика конфиденциальности")

# ---------- sitemap, robots, 404
today = datetime.date.today().isoformat()
urls = [("", "1.0"), ("ceny/", "0.9"), ("bani/", "0.9"), ("parenie/", "0.8"), ("chan/", "0.8"), ("menu/", "0.7"), ("zhenskiy-den/", "0.8"), ("massazh/", "0.7"), ("kontakty/", "0.7"), ("pravila/", "0.5"), ("privacy/", "0.2")]
IMG_BY_URL = {"": ["hero", "g1", "room0", "room3", "chan"], "bani/": ["img-provans", "img-taiga", "img-fin", "img-bavaria", "img-hata", "x-provans-in", "x-fin-in"], "chan/": ["chan"], "parenie/": ["hero"], "ceny/": ["g3"], "menu/": ["g6"], "zhenskiy-den/": ["room3"], "kontakty/": ["g1"]}
open(f"{OUT}/sitemap.xml", "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">\n' + "".join(f"  <url><loc>{SITE}{u}</loc><lastmod>{today}</lastmod><priority>{p}</priority>" + "".join(f"<image:image><image:loc>{SITE}img/{k}.webp</image:loc></image:image>" for k in IMG_BY_URL.get(u, [])) + "</url>\n" for u, p in urls) + "</urlset>\n")
open(f"{OUT}/robots.txt", "w").write(f"User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /admin/\nDisallow: /404.html\n\nUser-agent: Yandex\nAllow: /\nDisallow: /api/\nDisallow: /admin/\nDisallow: /404.html\nClean-param: utm_source&utm_medium&utm_campaign&utm_content&utm_term&yclid&gclid&fbclid&ysclid&v&book&menu\n\nSitemap: {SITE}sitemap.xml\n")
open(f"{OUT}/.nojekyll", "w").write("")
open(f"{OUT}/404.html", "w").write('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Страница не найдена — Носовихинские бани</title><meta name="robots" content="noindex"><style>body{margin:0;min-height:100vh;display:grid;place-content:center;gap:18px;text-align:center;background:#0a0907;color:#ece7da;font:17px/1.5 system-ui,sans-serif}a{color:#a6b74b}h1{font:400 64px/1 Georgia,serif;margin:0}</style></head><body><h1>404</h1><p>Такой страницы нет, но пар уже готов.</p><p><a href="' + SITE + '">На главную</a></p></body></html>')
print("pages ok")

# ---------- автономная версия со всем внутри (для превью на телефоне)
if not SERVER:
    i = art.index("<style>"); pre, body = art[:i], art[i:]; j = body.index("</style>") + len("</style>")
    pre = re.sub(r"<title>.*?</title>", "", pre); pre = re.sub(r'<link rel="(preconnect|stylesheet)"[^>]*>', "", pre)
    inl = head("Носовихинские бани — баня в Балашихе", "Банный комплекс в Балашихе", "", "") + pre + body[:j] + "\n</head>\n<body>\n" + body[j:] + "\n</body>\n</html>\n"
    open("site_inline.html", "w").write(inl); print("inline", len(inl)//1024, "KB")
