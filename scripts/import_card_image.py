#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
CARDS_DIR = ROOT_DIR / "Карточки"
IMAGES_DIR = ROOT_DIR / "Картинки"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Копирует готовую картинку карточки в проект и в media Anki, "
            "а при необходимости обновляет поле 'Картинка' в JSON."
        )
    )
    parser.add_argument("card_json", help="Путь к JSON-карточке.")
    parser.add_argument("source_image", help="Путь к исходному изображению.")
    parser.add_argument(
        "--anki-media-dir",
        help=(
            "Путь к collection.media Anki. Если не указан, "
            "скрипт попытается найти его автоматически."
        ),
    )
    parser.add_argument(
        "--media-prefix",
        default="japanese_words_",
        help="Префикс имени файла в media Anki. По умолчанию: japanese_words_",
    )
    parser.add_argument(
        "--write-json",
        action="store_true",
        help="Обновить поле 'Картинка' в JSON на <img src=\"...\">.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def resolve_card_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = (ROOT_DIR / path).resolve()
    if not path.exists():
        raise SystemExit(f"Файл карточки не найден: {raw_path}")
    return path


def resolve_source_image(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (ROOT_DIR / path).resolve()
    if not path.exists():
        raise SystemExit(f"Файл изображения не найден: {raw_path}")
    return path


def detect_anki_media_dir(explicit: str | None) -> Path:
    if explicit:
        media_dir = Path(explicit).expanduser()
        if media_dir.exists():
            return media_dir
        raise SystemExit(f"Директория media Anki не найдена: {explicit}")

    anki_root = Path("~/Library/Application Support/Anki2").expanduser()
    if not anki_root.exists():
        raise SystemExit(
            "Не удалось найти директорию Anki2. Укажите --anki-media-dir вручную."
        )

    candidates = sorted(anki_root.glob("*/collection.media"))
    if not candidates:
        raise SystemExit(
            "Не удалось автоматически найти collection.media. Укажите --anki-media-dir."
        )
    if len(candidates) == 1:
        return candidates[0]

    # Предпочитаем первый профиль с непустым именем; если профилей несколько,
    # лучше явно показать пользователю выбранный путь, чем молча ошибиться.
    return candidates[0]


def main() -> int:
    args = parse_args()
    card_path = resolve_card_path(args.card_json)
    source_image = resolve_source_image(args.source_image)
    media_dir = detect_anki_media_dir(args.anki_media_dir)

    payload = load_json(card_path)
    word = str(payload["Слово"]).strip()

    try:
        relative = card_path.relative_to(CARDS_DIR)
    except ValueError as exc:
        raise SystemExit(
            f"Карточка должна находиться внутри {CARDS_DIR}"
        ) from exc
    topic = relative.parts[0]

    suffix = source_image.suffix.lower() or ".png"
    project_dir = IMAGES_DIR / topic
    project_dir.mkdir(parents=True, exist_ok=True)
    project_image = project_dir / f"{word}{suffix}"
    shutil.copy2(source_image, project_image)

    media_filename = f"{args.media_prefix}{word}{suffix}"
    media_path = media_dir / media_filename
    shutil.copy2(source_image, media_path)

    html = f'<img src="{media_filename}">'

    print(f"Карточка: {card_path.relative_to(ROOT_DIR)}")
    print(f"Локальная картинка: {project_image.relative_to(ROOT_DIR)}")
    print(f"Media Anki: {media_path}")
    print(f"HTML для поля Картинка: {html}")

    if args.write_json:
        payload["Картинка"] = html
        save_json(card_path, payload)
        print(f"Обновлён JSON: {card_path.relative_to(ROOT_DIR)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
