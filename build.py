#!/usr/bin/env python3
"""Збирає сайт клієнта з template.html і JSON-файлу з даними.

    python3 build.py clients/detailingrv.json --out index.html
"""
import argparse
import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TAG = re.compile(r"\{\{(\{?)\s*([#^/]?)\s*([^}]+?)\s*\}?\}\}")


# ---------- фото ----------
# Unsplash-id ("photo-…"): якщо в images/photos/ є оптимізовані копії (tools/optimize-images.py),
# сайт бере їх (AVIF + WebP, різні ширини); інакше — адаптивні посилання на Unsplash.
# Власне фото клієнта (img/назва.jpg) лишається як є.
LOCAL = ROOT / "images" / "photos"
USED = set()  # локальні файли, які треба скопіювати поруч із сайтом клієнта


def _unsplash(photo):
    return isinstance(photo, str) and photo.startswith("photo-")


def _local(photo, widths, ext):
    """[(ширина, шлях)] наявних локальних копій або None, якщо немає жодної.
    Вертикальні фото клієнта бувають вужчі за 1600 px, тож беремо ті ширини, що є."""
    if not _unsplash(photo):
        return None
    found = [(w, f"images/photos/{photo}-{w}.{ext}") for w in widths]
    found = [(w, p) for w, p in found if (ROOT / p).exists()]
    if not found:
        return None
    USED.update(p for _, p in found)
    return found


# ---------- дані з адмінки (Pages CMS) ----------
# У JSON фото лежать як шляхи до файлів (так CMS показує прев'ю):
#   images/photos/photo-vn-polish-1200.webp  -> id "photo-vn-polish" (уся лінійка ширин)
#   images/uploads/моє-фото.jpg              -> id "photo-up-<slug>", якщо tools/optimize-uploads.py
#                                               уже зробив копії; інакше файл як є
UPLOADS = ROOT / "images" / "uploads"
LADDER_RE = re.compile(r"^images/photos/(photo-[\w-]+?)-\d+\.(?:webp|avif)$")


def up_id(path):
    """Стабільний id для завантаженого фото: photo-up-<латиниця/цифри> + короткий хеш шляху."""
    import hashlib
    stem = re.sub(r"[^a-z0-9]+", "-", Path(path).stem.lower()).strip("-")[:40]
    return f"photo-up-{stem + '-' if stem else ''}{hashlib.md5(Path(path).name.encode()).hexdigest()[:6]}"


def norm_photo(photo):
    if not isinstance(photo, str) or not photo:
        return photo
    p = photo.strip().lstrip("/")
    m = LADDER_RE.match(p)
    if m:
        return m.group(1)
    if p.startswith("images/uploads/"):
        pid = up_id(p)
        return pid if list(LOCAL.glob(pid + "-*.webp")) else p
    return photo


def gal_entry(photo):
    """Фото з галереї послуги -> {src: велике, th: мініатюра} для data-gal."""
    pid = norm_photo(photo)
    if _unsplash(pid):
        local = _local(pid, [480, 800, 1200, 1600], "webp")
        if local:
            return {"src": local[-1][1], "th": local[0][1]}
        return None
    if isinstance(pid, str) and pid:
        path = pid.lstrip("/")
        return {"src": path, "th": path} if (ROOT / path).exists() else None
    return None


def gal_json(photos):
    if isinstance(photos, str):
        photos = [photos]
    items = [g for g in (gal_entry(x) for x in photos or []) if g]
    return json.dumps(items, ensure_ascii=False) if items else ""


NB_WORDS = r"(?:і|й|у|в|з|із|зі|та|а|до|за|на|не|ні|по|від|для|як|що|чи|бо|о|об)"


def typo(text, tag="b"):
    """Текст з адмінки -> HTML: **жирне**, нерозривні пробіли після коротких слів і в цінах."""
    if not isinstance(text, str):
        return text
    t = re.sub(r"\*\*(.+?)\*\*", rf"<{tag}>\1</{tag}>", text)
    t = re.sub(rf"(?i)(?<![\w-])({NB_WORDS}) (?=\S)", "\\1\u00a0", t)
    t = re.sub(r"(\d) (?=\d{3}\b)", "\\1\u00a0", t)
    t = re.sub(r"(\d) (?=грн)", "\\1\u00a0", t)
    t = re.sub(r" (—|–)", "\u00a0\\1", t)
    return t


def from_cms(data):
    """Нормалізує дані, які клієнт міг змінити в адмінці: фото, типографіка, значення за замовчуванням."""
    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == "photo" or k.endswith("_img"):
                    x[k] = norm_photo(v)
                else:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(data)
    for i, pr in enumerate(data.get("problems", [])):
        pr["gal"] = gal_json(pr.get("gallery"))
        pr.setdefault("pos", "50% 50%")
        pr["title"], pr["desc"] = typo(pr.get("title", "")), typo(pr.get("desc", ""))
        sol = pr.setdefault("solution", {})
        for k in ("h", "t", "time", "price"):
            sol[k] = typo(sol.get(k, ""))
        sol["tip"] = typo(sol.get("tip", ""), "b")
    for pk in data.get("packages", []):
        pk["gal"] = gal_json(pk.get("gallery"))
        pk.setdefault("pos", "50% 50%")
        pk["cta"] = pk.get("cta") or "Записатись"
        pk["goal"] = typo(pk.get("goal", ""))
        pk["items"] = [typo(x) for x in pk.get("items") or []]
        pk["price"] = typo(pk.get("price", ""))
    used = set()
    for i, r in enumerate(data.get("results", [])):
        kind = r.get("kind") or f"r{i}"
        while kind in used:
            kind += "x"
        used.add(kind)
        r["kind"] = kind
        r.setdefault("pos", "50% 50%")
        r.setdefault("mpos", r["pos"])
        r["before"], r["after"] = typo(r.get("before", "")), typo(r.get("after", ""))
    rv = data.get("reviews", {})
    for it in rv.get("items", []):
        it.setdefault("meta", [{"k": "Джерело", "v": "Google Maps"}])
        it["text"] = typo(it.get("text", ""))
    for q in data.get("faq", []):
        q["q"], q["a"] = typo(q.get("q", "")), typo(q.get("a", ""), "strong")
        q["chips"] = [re.sub(r"</b>\s+", "</b>", typo(c)) for c in q.get("chips") or [] if c]
    h = data.get("hours", {})
    if h.get("days") is not None:
        h["days"] = sorted({int(x) for x in h["days"] if str(x).strip().isdigit()})
    c = data.get("contacts", {})
    if c.get("phone"):
        digits = re.sub(r"\D", "", c["phone"])
        c["phone_tel"] = "+38" + digits[-10:] if len(digits) >= 10 else c.get("phone_tel", "")
    tg = c.get("telegram")
    if isinstance(tg, dict) and tg.get("url"):
        tg["handle"] = "@" + tg["url"].rstrip("/").rsplit("/", 1)[-1]
    vb = c.get("viber")
    if isinstance(vb, dict):
        d = re.sub(r"\D", "", vb.get("phone") or "")
        if len(d) >= 10:
            vb["url"] = "viber://chat?number=%2B38" + d[-10:]
        else:
            c.pop("viber")  # порожній номер — рядок Viber не показуємо
    return data


def _img_args(arg):
    parts = [p for p in arg.split(";") if p]
    fit = "nofit" not in parts
    sizes = [tuple(p.split(",")) for p in parts if p != "nofit"]
    return sizes, fit


def _img_url(photo, w, q, fit):
    url = f"https://images.unsplash.com/{photo}?w={w}&q={q}&auto=format"
    return url + "&fit=crop" if fit else url


def f_src(photo, arg):
    if not _unsplash(photo):
        return photo
    sizes, fit = _img_args(arg)
    w, q = sizes[0]
    local = _local(photo, [w for w, _ in sizes], "webp")
    if local:
        return next((p for lw, p in local if lw == w), local[-1][1])
    return _img_url(photo, w, q, fit)


def f_srcset(photo, arg):
    if not _unsplash(photo):
        return ""
    sizes, fit = _img_args(arg)
    local = _local(photo, [w for w, _ in sizes], "webp")
    if local:
        return ", ".join(f"{p} {w}w" for w, p in local)
    return ", ".join(f"{_img_url(photo, w, q, fit)} {w}w" for w, q in sizes)


def f_avifset(photo, arg):
    """srcset у форматі AVIF для <source>; порожньо, якщо локальних копій немає (браузер пропустить source)."""
    sizes, _ = _img_args(arg)
    local = _local(photo, [w for w, _ in sizes], "avif")
    return ", ".join(f"{p} {w}w" for w, p in local) if local else ""


def f_step(i, arg):
    step, dec = arg.split(",")
    return f"{i * float(step):.{int(dec)}f}"


FILTERS = {"src": f_src, "srcset": f_srcset, "avifset": f_avifset, "step": f_step}


# ---------- мінімальний шаблонізатор у стилі Mustache ----------
def parse(src):
    root, stack, pos = [], [], 0
    cur = root
    for m in TAG.finditer(src):
        if m.start() > pos:
            cur.append(src[pos:m.start()])
        raw, kind, name = m.group(1) == "{", m.group(2), m.group(3)
        if kind in "#^" and kind:
            node = {"kind": kind, "name": name, "body": []}
            cur.append(node)
            stack.append((cur, node))
            cur = node["body"]
        elif kind == "/":
            cur, node = stack.pop()
            if node["name"] != name:
                raise ValueError(f"секція {{{{#{node['name']}}}}} закрита як {{{{/{name}}}}}")
        else:
            cur.append({"kind": "var", "name": name, "raw": raw})
        pos = m.end()
    if stack:
        raise ValueError(f"незакрита секція {{{{#{stack[-1][1]['name']}}}}}")
    cur.append(src[pos:])
    return root


_MISSING = object()


def lookup(ctx, path):
    if path == ".":
        return ctx[-1]
    head, *rest = path.split(".")
    for frame in reversed(ctx):
        if isinstance(frame, dict) and head in frame:
            val = frame[head]
            break
    else:
        raise KeyError(f"у даних немає «{path}»")
    for key in rest:
        val = val[int(key)] if isinstance(val, list) else val.get(key, _MISSING)
        if val is _MISSING:
            raise KeyError(f"у даних немає «{path}»")
    return val


def value(ctx, expr):
    name, *filters = expr.split("|")
    val = lookup(ctx, name)
    for flt in filters:
        fname, _, arg = flt.partition(":")
        val = FILTERS[fname](val, arg)
    return val


def render(nodes, ctx):
    out = []
    for n in nodes:
        if isinstance(n, str):
            out.append(n)
        elif n["kind"] == "var":
            val = value(ctx, n["name"])
            out.append(str(val) if n["raw"] else html.escape(str(val)))
        else:
            try:
                val = lookup(ctx, n["name"])
            except KeyError:
                val = None  # необов'язкові поля (tag, gift…) можна не вказувати
            if n["kind"] == "^":
                if not val:
                    out.append(render(n["body"], ctx))
            elif isinstance(val, list):
                for i, item in enumerate(val):
                    meta = {"@i": i, "@n": i + 1, "@first": i == 0, "@last": i == len(val) - 1}
                    out.append(render(n["body"], ctx + [meta, item]))
            elif val:
                out.append(render(n["body"], ctx + [val] if isinstance(val, dict) else ctx))
    return "".join(out)


# ---------- похідні значення, які зручніше рахувати тут, ніж писати руками ----------
def _minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def _week(hours):
    """Графік на 7 днів (0 = неділя): [відкриття, закриття, "9:00", "20:00"] або None.
    Або однаковий час на всі робочі дні (open/close/days), або свій для кожного дня (week)."""
    week = hours.get("week") or [
        [hours["open"], hours["close"]] if d in hours["days"] else None for d in range(7)
    ]
    days = [[_minutes(o), _minutes(c), o.lstrip("0"), c] if o else None for o, c in (d or (None, None) for d in week)]
    return {"week": days, "daily": all(days) and len({tuple(d) for d in days}) == 1}


def _pairs(data, client_dir):
    """results[].pair = "images/before-after/<категорія>": шукаємо before/after.webp (або jpg/png)."""
    for r in data.get("results", []):
        if r.get("before_img") and r.get("after_img"):
            found = {}
            for side in ("before", "after"):
                ref = r[side + "_img"]
                if _unsplash(ref):  # завантажене з адмінки й оптимізоване
                    local = _local(ref, [800, 1200, 1600], "webp")
                    if local:
                        found[side] = local[-1][1]
                        found[side + "_set"] = ", ".join(f"{p} {w}w" for w, p in local)
                        continue
                    ref = ""
                ref = ref.lstrip("/")
                if ref and (ROOT / ref).exists():
                    small = (ROOT / ref).with_name(Path(ref).stem + "-800.webp")
                    found[side] = ref
                    found[side + "_set"] = f"{ref} 1600w" + (f", {Path(ref).parent}/{small.name} 800w" if small.exists() else "")
                    USED.add(ref)
            if "before" in found and "after" in found:
                r["real"] = found
            else:
                r["_drop"] = True  # пара з адмінки без обох фото — не показуємо порожню вкладку
                print(f"увага: «{r.get('label')}» — немає фото до/після, вкладку пропущено")
            continue
        folder = r.get("pair")
        if not folder:
            r["_drop"] = True
            print(f"увага: «{r.get('label')}» — немає фото до/після, вкладку пропущено")
            continue
        found = {}
        for side in ("before", "after"):
            for base in (ROOT, client_dir):
                hit = next((p for p in sorted((base / folder).glob(side + ".*")) if p.suffix.lower() in (".webp", ".jpg", ".jpeg", ".png")), None)
                if hit:
                    rel = f"{folder}/{hit.name}"
                    small = hit.with_name(side + "-800.webp")
                    found[side] = rel
                    found[side + "_set"] = f"{rel} 1600w" + (f", {folder}/{small.name} 800w" if small.exists() else "")
                    if base == ROOT:
                        USED.add(rel)
                        if small.exists():
                            USED.add(f"{folder}/{small.name}")
                    break
        if "before" in found and "after" in found:
            r["real"] = found
        else:
            print(f"увага: у {folder} немає before/after — показую фото з ефектом «до»")


def _strip(h):
    return html.unescape(re.sub(r"<[^>]+>", "", h)).strip()


def _jsonld(data):
    """Структуровані дані для Google: детейлінг-студія (AutoRepair) і блок питань (FAQPage)."""
    site = data.get("site_url", "").rstrip("/")
    c, h = data["contacts"], data["hours"]
    names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    week = h.get("week") or [[h["open"], h["close"]] if d in h["days"] else None for d in range(7)]
    hours = [{"@type": "OpeningHoursSpecification", "dayOfWeek": names[d], "opens": w[0], "closes": w[1]} for d, w in enumerate(week) if w]
    # усі ціни «від»: і з карток послуг, і з додаткових
    raw = [p.get("price", "") for p in data.get("packages", [])] + [p["solution"].get("price", "") for p in data.get("problems", [])]
    prices = [int(re.sub(r"\D", "", x)) for x in raw if re.sub(r"\D", "", x)]
    biz = {
        "@type": "AutoRepair",
        "name": data["brand"],
        "description": data["seo"]["description"],
        "telephone": c["phone_tel"],
        "address": {"@type": "PostalAddress", "addressLocality": data.get("city", "Рівне"), "addressCountry": "UA", **({"streetAddress": c["street"]} if c.get("street") else {})},
        "areaServed": data.get("city", "Рівне"),
        "openingHoursSpecification": hours,
        "sameAs": [v["url"] for k, v in c.items() if k != "map" and isinstance(v, dict) and str(v.get("url", "")).startswith("http")] + [m["url"] for m in c.get("more", [])],
    }
    if prices:
        biz["priceRange"] = f"{min(prices)}–{max(prices)} грн"
    if site:
        biz.update({"@id": site + "/#business", "url": site + "/", "image": data["_"]["og_image"]})
        if data.get("brand_assets"):
            biz["logo"] = f"{site}/{data['brand_assets']}/apple-touch-icon.png"
    faq = {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": _strip(q["q"]), "acceptedAnswer": {"@type": "Answer", "text": _strip(q["a"])}}
        for q in data.get("faq", [])]}
    out = json.dumps({"@context": "https://schema.org", "@graph": [biz, faq]}, ensure_ascii=False)
    return out.replace("</", "<\\/")


def derive(data):
    # на телефоні в рядок заголовка вміщається ~14 символів, довший переноситься
    for line in data["hero"]["title"]:
        text = html.unescape(re.sub(r"<[^>]+>", "", line["text"]))
        if len(text) + text.count("-") > 14:  # по дефісу браузер теж переносить
            print(f"увага: рядок заголовка «{text}» на телефоні перенесеться — скоротіть (до ~14 символів, дефіс рахується за два)")
    og = data["seo"]["og_image"]
    hex_ = data["accent"].lstrip("#")
    hours = data["hours"]
    data["_"] = {
        "accent_rgb": ",".join(str(int(hex_[i:i + 2], 16)) for i in (0, 2, 4)),
        "accent_url": "%23" + hex_,
        "solutions": json.dumps([p["solution"] for p in data["problems"]], ensure_ascii=False),
        "caps": json.dumps([[r["before"], r["after"]] for r in data["results"]], ensure_ascii=False),
        "hours": json.dumps(_week(hours), ensure_ascii=False),
        # OG-картинка: відносний шлях → повна адреса (Telegram, Facebook тощо потребують абсолютного URL)
        "og_image": og if og.startswith("http") or not data.get("site_url") else data["site_url"].rstrip("/") + "/" + og.lstrip("/"),
        # головне фото лежить локально → preload замість preconnect до Unsplash
        "local_photos": bool(_unsplash(data["hero"]["photo"]) and (LOCAL / f"{data['hero']['photo']}-1200.webp").exists()),
    }
    data["_"]["jsonld"] = _jsonld(data)
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("client", help="JSON-файл клієнта, напр. clients/detailingrv.json")
    ap.add_argument("--out", help="куди записати сайт (типово sites/<назва-файлу>/index.html)")
    args = ap.parse_args()

    client = Path(args.client)
    data = json.loads(client.read_text(encoding="utf-8"))
    data = from_cms(data)
    _pairs(data, client.with_suffix(""))
    data["results"] = [r for r in data.get("results", []) if not r.get("_drop")]
    data = derive(data)
    page = render(parse((ROOT / "template.html").read_text(encoding="utf-8")), [data])

    out = Path(args.out) if args.out else ROOT / "sites" / client.stem / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")

    # власні фото клієнта: clients/<клієнт>/ копіюється поруч із сайтом
    assets = client.with_suffix("")
    if assets.is_dir():
        shutil.copytree(assets, out.parent, dirs_exist_ok=True)
    # локальні фото (images/…) — поруч із сайтом клієнта; для index.html у корені вони вже на місці
    if out.parent.resolve() != ROOT:
        for rel in sorted(USED):
            dst = out.parent / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, dst)
    print(f"готово: {out}")


if __name__ == "__main__":
    main()
