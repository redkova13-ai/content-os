# publisher

`publish.py` выкладывает один пост («слот») в Instagram, Threads, VK и Telegram.

```
python3 publisher/publish.py SLOT.json                                   # dry run (по умолчанию)
python3 publisher/publish.py SLOT.json --only ig,vk                      # только часть площадок
python3 publisher/publish.py SLOT.json --publish --approval APPROVED.json  # настоящая публикация
```

## Правило: dry run / publish

- **Без `--publish` ничего не публикуется.** Скрипт проверяет файлы и лимиты, создаёт
  контейнеры Instagram/Threads и ждёт статуса `FINISHED` (они невидимы, пока не вызван
  `media_publish` / `threads_publish`), загружает фото/PDF в VK (приватно, `wall.post` не
  вызывается), собирает запросы Telegram, но не отправляет их. Печатает JSON-отчёт по площадкам.
- **`--publish` требует файл одобрения GATE 2** (`{"asset_id": ..., "approved_by": ..., "approved_at": ...}`),
  `asset_id` должен совпадать со слотом. Если хоть одна площадка не прошла проверку — не
  публикуется ничего.
- Порядок публикации: ig → threads → vk → tg. Ошибка на одной площадке не останавливает остальные.
- Токены IG/Threads/VK подставляет прокси; Telegram берёт `TELEGRAM_BOT_TOKEN` из окружения.
  Токены нигде не печатаются.
- Картинки для IG/Threads конвертируются в JPEG и пушатся в `media/<asset_id>/` этого репозитория
  (raw.githubusercontent.com служит хостингом). Тестовые файлы потом удалять отдельным коммитом.

## SLOT.json

```json
{
  "asset_id": "w41-1-ne-hochu",
  "kind": "carousel",
  "media": {
    "slides_dir": "runs/2026-W41/09/c1_ne_hochu",
    "image": "cover.png",
    "video": "reel.mp4",
    "cover": "reel_cover.png",
    "document": "dnevnik.pdf"
  },
  "ig":      {"caption_file": "ig.txt", "first_comment_file": "ig_comment.txt"},
  "tg":      {"text_file": "tg.txt", "attach_document": true},
  "vk":      {"text_file": "tg.txt"},
  "threads": {"text_file": "threads.txt"}
}
```

- Пути — абсолютные или относительно папки, где лежит SLOT.json. Вместо `*_file` можно
  написать текст прямо: `caption`, `text`, `first_comment`.
- Нет ключа площадки — площадка пропускается. Один и тот же текстовый файл можно дать нескольким площадкам.
- `kind`:

| kind | Instagram | Threads | VK | Telegram |
|---|---|---|---|---|
| `carousel` (`slides_dir`, `slide_*.png`) | карусель 2–10 | карусель 2–20 | фото (до 10 вложений вместе с PDF) | sendMediaGroup, затем текст |
| `image` (`image`) | фото | фото | фото | sendPhoto с подписью (≤1024), иначе фото + текст |
| `reels` (`video`, опц. `cover`) | Reels (resumable upload, share_to_feed) | видео | обложка + текст (видео в VK нужен user token) | sendVideo, затем текст |
| `story` (`image`, 1080×1920) | история | — | — | — |
| `text` | — | текст | текст | текст |

- `story` уходит только в Instagram (в TG/VK истории идут автокросспостом), остальные ключи игнорируются.
- `ig.first_comment_file` — первый комментарий, публикуется только после настоящего `media_publish`.
- `media.document` (PDF): в VK прикрепляется всегда, если указан (`"attach_document": false` — отключить);
  в Telegram — отдельным sendDocument, если `tg.attach_document: true`.
- Лимиты: подпись IG ≤ 2200 символов и ≤ 30 хештегов; Threads ≤ 500; Telegram ≤ 4096 (подпись ≤ 1024);
  VK ≤ 16000. Telegram — без parse_mode, превью ссылок отключены.

`publish_carousel.py` — старый скрипт только для карусели в Instagram, работает как раньше.
