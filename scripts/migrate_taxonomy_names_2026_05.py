#!/usr/bin/env python3
"""
Перенос и переименование папок тем под таксономию (docs/theme-taxonomy.md).

Не трогает: Глаголы, Наречия, Прилагательные_い, Прилагательные_на.

Запуск из корня репозитория:
  python3 scripts/migrate_taxonomy_names_2026_05.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from migrate_themes_2026_05 import (
    ROOT,
    fix_json_theme_tag,
    fix_zapisi_file,
    move_word_bundle,
    rebuild_slova_from_cards,
    rename_theme_folder,
    remove_empty_dir,
    _ensure_dir,
)

# --- Переносы по смыслу ---
MEDIA_TO: dict[str, tuple[str, ...]] = {
    "Кинематограф": ("映画", "日常系"),
    "Телевидение": ("テレビ", "ビデオ", "ラジオ"),
    "Фотография": ("カメラ", "写真"),
    "Электроника": ("コンピューター", "電話", "時計"),
}

HEALTH_TO = {
    "Медицина": ("耳鼻科", "病院", "病気", "体温計"),
    "Эмоции": ("期待", "気分", "気持ち"),
}

FRIENDS_TO_DRUZHBA = ("友だち", "友人", "友情", "友達", "親友")

RENAMES: tuple[tuple[str, str], ...] = (
    ("Учёба", "Образование"),
    ("Покупки", "Торговля"),
    ("Продукты", "Еда"),
    ("Жильё", "Жилище"),
    ("Гардероб", "Одежда"),
    ("Правопорядок", "Право"),
    ("Достопримечательности", "Туризм"),
)


def main() -> None:
    new_themes = (
        "Дружба",
        "Кинематограф",
        "Телевидение",
        "Фотография",
        "Электроника",
        "Медицина",
        "Эмоции",
    )
    for t in new_themes:
        for sub in ("Карточки", "Картинки", "Произношение", "Записи"):
            _ensure_dir(ROOT / sub / t)

    for theme, words in MEDIA_TO.items():
        for w in words:
            move_word_bundle(w, "Медиа", theme)

    for theme, words in HEALTH_TO.items():
        for w in words:
            move_word_bundle(w, "Здоровье", theme)

    for w in FRIENDS_TO_DRUZHBA:
        move_word_bundle(w, "Общение", "Дружба")

    for old, new in RENAMES:
        if (ROOT / "Карточки" / old).exists():
            rename_theme_folder(old, new)

    for dead in ("Медиа", "Здоровье"):
        d = ROOT / "Карточки" / dead
        if d.exists() and not any(d.glob("*.json")):
            for sub in ("Карточки", "Картинки", "Произношение", "Записи"):
                p = ROOT / sub / dead
                if p.is_dir():
                    try:
                        remove_empty_dir(p)
                    except OSError:
                        pass

    for jp in ROOT.glob("Карточки/**/*.json"):
        if jp.is_file():
            fix_json_theme_tag(jp)

    for md in ROOT.glob("Записи/**/*.md"):
        if md.is_file():
            fix_zapisi_file(md)

    rebuild_slova_from_cards()
    print("Миграция имён тем по таксономии завершена.")


if __name__ == "__main__":
    main()
