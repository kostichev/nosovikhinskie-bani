#!/usr/bin/env python3
"""Разовые правки данных от разработчика поверх данных админки.
Каждая правка применяется один раз и только если клиент сам не поменял это значение."""
import json, os, sys, shutil, time
DATA, PATCHES = sys.argv[1], sys.argv[2]
DONE = os.path.join(os.path.dirname(DATA), "patches-applied")
done = set(open(DONE).read().split()) if os.path.exists(DONE) else set()
patches = json.load(open(PATCHES)) if os.path.exists(PATCHES) else []
todo = [p for p in patches if p["id"] not in done]
if not todo: sys.exit(0)
d = json.load(open(DATA))
def walk(obj, path):
    for k in path[:-1]:
        if isinstance(k, dict):
            (kk, vv), = k.items(); obj = next(x for x in obj if x.get(kk) == vv)
        else: obj = obj[k]
    return obj, path[-1]
changed = False
for p in todo:
    for s in p["set"]:
        try:
            o, k = walk(d, s["path"])
            if o.get(k) == s["from"]: o[k] = s["to"]; changed = True
        except Exception: pass
    if "menu" in p:  # меню целиком; стоп-лист (скрытые блюда) сохраняем
        hidden = {i["name"] for m in d.get("menu", []) for c in m["cats"] for i in c["items"] if i.get("hidden")}
        new = json.loads(json.dumps(p["menu"]))
        for m in new:
            for c in m["cats"]:
                for i in c["items"]:
                    if i["name"] in hidden: i["hidden"] = True
                    else: i.pop("hidden", None)
        d["menu"] = new; changed = True
    for a in p.get("add", []):
        try:
            lst = d
            for k in a["path"]: lst = lst[k]
            if any(x.get("id") == a["value"]["id"] for x in lst): continue
            ids = [x.get("id") for x in lst]
            lst.insert(ids.index(a["after"]) + 1 if a.get("after") in ids else len(lst), a["value"]); changed = True
        except Exception: pass
    done.add(p["id"]); print(time.strftime("%F %T"), "правка данных", p["id"])
if changed:
    hist = os.path.join(os.path.dirname(DATA), "history"); os.makedirs(hist, exist_ok=True)
    shutil.copy2(DATA, os.path.join(hist, time.strftime("%Y%m%d-%H%M%S") + "-dev.json"))
    tmp = DATA + ".tmp"; json.dump(d, open(tmp, "w"), ensure_ascii=False, indent=1); os.replace(tmp, DATA)
open(DONE, "w").write("\n".join(sorted(done)) + "\n")
