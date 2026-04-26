# Scripts

`generate_aivis_audio.py` генерирует локальные MP3 через `AivisSpeech` и сохраняет их в `Произношение/` по правилам проекта. Для карточек нового формата он делает 4 файла: слово и три примера из многострочного поля `Пример`.

`import_card_image.py` берёт уже сгенерированную картинку карточки, копирует её в `Картинки/<тема>/`, копирует в `collection.media` Anki и может обновить поле `Картинка` в JSON до `<img src="...">`.

Примеры:

```bash
python3 scripts/generate_aivis_audio.py 'Карточки/Глаголы/乾かす.json'
python3 scripts/generate_aivis_audio.py --write-json 'Карточки/Глаголы/乾かす.json'
python3 scripts/generate_aivis_audio.py --all-empty --write-json
```

По умолчанию скрипт случайно выбирает голос из доступных в локальном `AivisSpeech`, которые поддерживают стиль `ノーマル`.

Пример импорта картинки:

```bash
python3 scripts/import_card_image.py 'Карточки/Кандзи/口座.json' \
  '/Users/chebotarev/.codex/generated_images/.../image.png' \
  --write-json
```
