# VN Detail — сайт детейлінг-студії у Вінниці

Прев'ю: https://vndetailing.pages.dev/ · фінальний домен: https://vndetail.com/
Хостинг — Cloudflare Pages (автодеплой з гілки main), заявки з форми — у Telegram.

- Дані сайту (послуги, ціни, контакти, FAQ, відгуки): `clients/vndetail.json`; дизайн: `template.html`.
- Після правок: `python3 build.py clients/vndetail.json --out index.html`, потім коміт і push.
- Нові фото: покласти `_src/unsplash/photo-vn-<назва>.jpg` → `python3 tools/optimize-images.py` (потрібен Pillow з AVIF).
- Форма: `functions/api/estimate.js` → `lib/estimate-core.mjs` → Telegram. Змінні в Cloudflare: `TELEGRAM_BOT_TOKEN` (Secret), `TELEGRAM_CHAT_ID`.
- Cloudflare: Build command `bash tools/cf-build.sh`, Build output directory `public`.
