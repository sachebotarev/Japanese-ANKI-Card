# Scripts

`generate_aivis_audio.py` генерирует локальные MP3 через `AivisSpeech` и сохраняет их в `Произношение/` по правилам проекта. Для карточек нового формата он делает 4 файла: слово и три примера из многострочного поля `Пример`.

`import_card_image.py` берёт уже сгенерированную картинку карточки, копирует её в `Картинки/<тема>/`, копирует в `collection.media` Anki и может обновить поле `Картинка` в JSON до `<img src="...">`.

Примеры:

```bash
python3 scripts/generate_aivis_audio.py 'Карточки/Глаголы/乾かす.json'
python3 scripts/generate_aivis_audio.py --write-json 'Карточки/Глаголы/乾かす.json'
python3 scripts/generate_aivis_audio.py --all-empty --write-json
```

Разрешены только четыре голоса проекта (см. константу `ALLOWED_TTS_SPEAKERS` в скрипте и подробнее [docs/audio.md](../docs/audio.md)). Если `--speaker` не задан, перед записью каждого из четырёх MP3 голос случайно выбирается среди установленных в Engine голосов из этого списка, поддерживающих стиль (по умолчанию `ノーマル`). С ключом `--speaker` все четыре файла озвучиваются одним из разрешённых голосов.

`apply_minna_lesson_tags.py` добавляет тег урока Minna (`みんな初級I-第NN課` / `みんな初級II-第NN課`) по встроенному словарю для карточек с тегом `みんなの日本語` и тег **`みんな-教材外`** для остальной лексики (словарь уроков при необходимости правится в коде скрипта).

`regenerate_audio_all_valid.py` — повторная озвучка `--force --write-json` только для файлов с тремя примерами в `Пример` (как требует `generate_aivis_audio.py`).

`audit_example_format.py` — сколько карточек уже с тремя примерами по `<br>`, какие ещё нет (`docs/example-format-audit.md`).

`example_format_common.py` — общие функции формата (подходит для собственных скриптов).

```bash
python3 scripts/audit_example_format.py
```

`sync_json_to_anki_connect.py` — отправка всех полей `Карточки/**/*.json`, тегов и локальных `[sound:…]` медиафайлов в Anki через AnkiConnect ([docs/anki-sync.md](../docs/anki-sync.md)).

`sync_zapisi_tags_from_cards.py` синхронизирует блок YAML **`tags:`** у существующих заметок `Записи/` из JSON после смены тегов в карточке.

`sync_quartz_content.py` готовит контент для сайта: копирует `Записи/` → `quartz_content/Записи/` и заменяет Obsidian‑вставки `![[Картинки/...]]` и `![[Произношение/...]]` на raw URL GitHub. Каталог `quartz_content/` — сборочный артефакт (в `.gitignore`).

`build_quartz.sh` — локальная сборка ванильным Quartz: клонирует апстрим в `.quartz-build/`, накатывает `quartz_overlay/`, запускает `sync_quartz_content.py`, выполняет `npx quartz build -d ../quartz_content -o ../quartz_site` (либо `--serve` для dev‑сервера). Версию апстрима можно менять переменной `QUARTZ_VERSION` (по умолчанию `v4.5.2`); подробности — в [docs/quartz-site.md](../docs/quartz-site.md).

Пример импорта картинки:

```bash
python3 scripts/import_card_image.py 'Карточки/Повседневность/口座.json' \
  '/Users/chebotarev/.codex/generated_images/.../image.png' \
  --write-json
```
