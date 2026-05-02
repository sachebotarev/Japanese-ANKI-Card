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

`sync_json_to_anki_connect.py` — отправка всех полей `Карточки/**/*.json`, тегов и локальных `[sound:…]` медиафайлов в Anki через AnkiConnect ([docs/anki-sync.md](../docs/anki-sync.md)).

`sync_zapisi_tags_from_cards.py` синхронизирует блок YAML **`теги:`** у существующих заметок `Записи/` из JSON после смены тегов в карточке.

Пример импорта картинки:

```bash
python3 scripts/import_card_image.py 'Карточки/Кандзи/口座.json' \
  '/Users/chebotarev/.codex/generated_images/.../image.png' \
  --write-json
```
