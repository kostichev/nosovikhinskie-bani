# Рендер блока «Ресторан» и раскрывающегося меню (оверлей-книга) из menu.py
import html, re
import json as _json, os as _os
_SD = _json.load(open(_os.environ.get("SITE_DATA") or _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "data", "site.json"), encoding="utf-8"))
MENU = [(m["id"], m["title"], [(c["title"], [(i["name"], i.get("weight", ""), str(i["price"]), i.get("desc", "")) for i in c["items"] if not i.get("hidden")]) for c in m["cats"]]) for m in _SD["menu"]]
SIGNATURE = [(x["name"], x.get("weight", ""), str(x["price"])) for x in _SD["menu_featured"]]

esc = lambda t: html.escape(t, quote=True)
rub = lambda p: esc(p) + "&nbsp;₽"
COUNT = sum(len(items) for _, _, cats in MENU for _, items in cats)
NB = lambda s: s.replace(" / ", "&nbsp;/ ")

def slug(s):
    t = str.maketrans("абвгдеёжзийклмнопрстуфхцчшщъыьэюя", "abvgdeejziiklmnoprstufhccss_y_eua")
    return re.sub(r"[^a-z0-9]+", "-", s.lower().translate(t)).strip("-")[:24]

def item(n, w, p, d, i):
    meta = (f'<span class="mono">{esc(w)}</span>' if w else "") + (f"<span>{esc(d)}</span>" if d else "")
    return (f'<li style="--i:{min(i, 14)}"><div class="fd-row"><span class="fd-n">{esc(n)}</span><i></i><b>{NB(rub(p))}</b></div>'
            + (f'<div class="fd-meta">{meta}</div>' if meta else "") + "</li>")

def book():
    tabs = "".join(f'<button role="tab" type="button" class="fd-tab" data-tab="{k}" aria-selected="false">{esc(t)}</button>' for k, t, _ in MENU)
    toc, body = [], []
    for k, t, cats in MENU:
        toc.append(f'<ol class="fd-toc-l" data-tab="{k}">' + "".join(f'<li><button type="button" data-cat="fd-{slug(c)}">{esc(c)}<sup>{len(it)}</sup></button></li>' for c, it in cats) + "</ol>")
        secs = "".join(f'<section class="fd-cat" id="fd-{slug(c)}"><h3>{esc(c)}<sup>{len(it)}</sup></h3><ul class="fd-list">' + "".join(item(*x, i) for i, x in enumerate(it)) + "</ul></section>" for c, it in cats)
        adult = '<p class="fd-18">18+ · Алкогольные напитки продаются только совершеннолетним гостям.</p>' if k == "bar" else ""
        body.append(f'<div class="fd-pane" data-tab="{k}" role="tabpanel">{adult}{secs}</div>')
    return f'''<template id="fdTpl"><div class="fd" id="foodBook" role="dialog" aria-modal="true" aria-label="Меню ресторана" hidden>
  <div class="fd-bg" data-fd-close></div>
  <div class="fd-panel">
    <header class="fd-top">
      <div class="fd-title"><span class="mono">Носовихинские бани</span><b>Меню <em>ресторана</em></b></div>
      <div class="fd-tabs" role="tablist" aria-label="Разделы меню">{tabs}</div>
      <label class="fd-search"><svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="6"/><path d="M13 13l5 5"/></svg><input type="search" id="fdQ" placeholder="Найти блюдо или напиток" autocomplete="off" enterkeyhint="search"></label>
      <button type="button" class="x fd-x" data-fd-close aria-label="Закрыть меню">✕</button>
    </header>
    <div class="fd-body">
      <nav class="fd-toc" aria-label="Категории">{"".join(toc)}</nav>
      <div class="fd-scroll" id="fdScroll" data-lenis-prevent>
        {"".join(body)}
        <p class="fd-empty" hidden>Ничего не нашли. Спросите у официанта — возможно, это есть в баре.</p>
        <footer class="fd-foot"><span>Цены в рублях. Выход блюд указан в граммах.</span><span>Меню и цены могут меняться — уточняйте у официанта.</span></footer>
      </div>
    </div>
  </div>
</div></template>'''

def section(logo):
    chapters = []
    for n, (k, t, cats) in enumerate(MENU, 1):
        cnt = sum(len(it) for _, it in cats)
        names = ", ".join(c for c, _ in cats[:4]).lower() + ("…" if len(cats) > 4 else "")
        chapters.append(f'<button type="button" class="fd-ch" data-fd-open="{k}"><span class="mono">{n:02d}</span><b>{esc(t)}</b><small>{esc(names[:1].upper() + names[1:])}</small><span class="fd-ch-n">{cnt}<i>позиций</i></span><span class="arr" aria-hidden="true">→</span></button>')
    sig = "".join(f'<div class="t-row"><span>{esc(n)} <small class="mono">{esc(w)}</small></span><i></i><b>{NB(rub(p))}</b></div>' for n, w, p in SIGNATURE)
    return f'''<section class="food" id="menu" aria-labelledby="foodTitle">
    <div class="wrap">
      <div class="sh">
        <h2 id="foodTitle"><span class="reveal-line"><span>Ресторан</span></span><span class="reveal-line"><span><em>после пара</em></span></span></h2>
        <p>Русская кухня и мангал, раки, рулька, уха по-царски, травяной чай в больших чайниках и холодное пиво. Всё меню — одним касанием.</p>
      </div>
      <div class="fd-grid">
        <button type="button" class="fd-cover" data-fd-open="kitchen" aria-label="Открыть меню ресторана">
          <span class="fd-pages" aria-hidden="true"></span>
          <span class="fd-cover-in">
            <img src="{logo}" alt="" width="1200" height="490" loading="lazy" decoding="async">
            <span class="mono">Ресторан при банях</span>
            <b>Меню</b>
            <span class="fd-cover-sub">кухня · мангал · чай · бар</span>
            <span class="fd-cover-cta">Открыть меню <span class="arr">→</span></span>
            <span class="fd-cover-n mono">{COUNT} позиций</span>
          </span>
        </button>
        <div class="fd-side">
          <div class="fd-chs">{"".join(chapters)}</div>
          <div class="fd-sig"><span class="mono">Стоит попробовать</span>{sig}</div>
        </div>
      </div>
    </div>
  </section>'''

def menu_page_html():
    out = []
    for k, t, cats in MENU:
        out.append(f'<h2>{esc(t)}</h2>')
        if k == "bar": out.append('<p class="note">18+ · Алкогольные напитки продаются только совершеннолетним гостям.</p>')
        for c, it in cats:
            out.append(f'<h3 style="font:400 26px/1.2 var(--f-display);margin:26px 0 6px;color:var(--brass)">{esc(c)}</h3><table><tbody>'
                       + "".join(f'<tr><td><b style="font-weight:500;color:var(--bone)">{esc(n)}</b>{"<br><small>" + esc(d) + "</small>" if d else ""}</td><td style="white-space:nowrap">{esc(w)}</td><td style="white-space:nowrap"><b>{NB(rub(p))}</b></td></tr>' for n, w, p, d in it)
                       + "</tbody></table>")
    return "".join(out)
