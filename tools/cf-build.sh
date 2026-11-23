#!/bin/bash
# Збірка для Cloudflare Pages: у папку public/ потрапляє тільки сам сайт.
# Службові файли (build.py, template.html, clients/, tools/, lib/) назовні не видно.
# Налаштування в Cloudflare: Build command = bash tools/cf-build.sh, Build output directory = public
#
# Сайт щоразу збирається з clients/vndetail.json — це той файл, який клієнт редагує в адмінці (Pages CMS).
set -e
cd "$(dirname "$0")/.."

# фото з адмінки: оптимізуємо, якщо вдасться поставити Pillow; якщо ні — сайт покаже оригінали
python3 -m pip install --quiet --disable-pip-version-check pillow 2>/dev/null || echo "pillow не встановився — фото без оптимізації"
python3 tools/optimize-uploads.py || echo "optimize-uploads впав — фото без оптимізації"

python3 build.py clients/vndetail.json --out index.html

rm -rf public && mkdir -p public
cp index.html 404.html robots.txt sitemap.xml _headers public/
cp -r fonts public/
mkdir -p public/images && cp -r images/photos images/brand images/before-after public/images/
[ -d images/uploads ] && cp -r images/uploads public/images/
find public -name '*.md' -delete
echo "готово: $(find public -type f | wc -l) файлів у public/"
