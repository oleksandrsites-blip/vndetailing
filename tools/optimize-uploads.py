#!/usr/bin/env python3
"""Фото, завантажені клієнтом через адмінку (images/uploads/), -> оптимізовані копії для сайту.

    python3 tools/optimize-uploads.py

images/uploads/<будь-яка назва>.jpg -> images/photos/photo-up-<slug>-{480,800,1200,1600,2000}.webp (+ .avif, якщо Pillow вміє)
Запускається під час збірки на Cloudflare (tools/cf-build.sh). Якщо Pillow немає — нічого не робить,
і сайт показує оригінал файлу (важчий, але робочий).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from build import up_id  # noqa: E402

LADDER = [480, 800, 1200, 1600, 2000]
EXT = {".jpg", ".jpeg", ".png", ".webp"}

try:
    from PIL import Image, ImageOps
except ImportError:
    print("optimize-uploads: Pillow не встановлено — пропускаю, фото підуть як є")
    sys.exit(0)


def main():
    src = ROOT / "images" / "uploads"
    out = ROOT / "images" / "photos"
    out.mkdir(parents=True, exist_ok=True)
    files = [f for f in sorted(src.glob("*")) if f.suffix.lower() in EXT] if src.is_dir() else []
    avif_ok = True
    for f in files:
        pid = up_id(f"images/uploads/{f.name}")
        if (out / f"{pid}-480.webp").exists():
            continue
        try:
            im = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
        except Exception as e:  # битий файл не повинен ламати збірку
            print(f"optimize-uploads: не вдалось відкрити {f.name}: {e}")
            continue
        widths = [w for w in LADDER if w <= im.width] or [LADDER[0]]
        for w in widths:
            r = im if im.width <= w else im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
            r.save(out / f"{pid}-{w}.webp", "WEBP", quality=72, method=4)
            if avif_ok:
                try:
                    r.save(out / f"{pid}-{w}.avif", "AVIF", quality=52, speed=6)
                except Exception:
                    avif_ok = False
                    print("optimize-uploads: AVIF недоступний — лише WebP")
        print(f"optimize-uploads: {f.name} -> {pid} ({', '.join(map(str, widths))})")
    print(f"optimize-uploads: готово, файлів {len(files)}")


if __name__ == "__main__":
    main()
