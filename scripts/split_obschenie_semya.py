#!/usr/bin/env python3
"""
Выделение темы «Семья» из «Общение»: перенос карточек, медиа, Записей;
нормализация Теги в JSON и пересборка Слова/.

Запуск из корня репозитория:
  python3 scripts/split_obschenie_semya.py
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
)

# Родство и домашний круг (彼・彼ち・彼女 остаются в «Общение»).
FAMILY_WORDS: tuple[str, ...] = (
    "お兄さん",
    "お姉さん",
    "お母さん",
    "お父さん",
    "主人",
    "兄",
    "兄弟",
    "夫",
    "夫人",
    "夫妻",
    "夫婦",
    "奥",
    "奥さん",
    "妹",
    "妻",
    "姉",
    "姉妹",
    "子弟",
    "家族",
    "弟",
    "母",
    "母親",
    "父",
    "父母",
    "父親",
    "長兄",
)


def main() -> None:
    for w in FAMILY_WORDS:
        move_word_bundle(w, "Общение", "Семья")

    for jp in ROOT.glob("Карточки/**/*.json"):
        if jp.is_file():
            fix_json_theme_tag(jp)

    for md in ROOT.glob("Записи/**/*.md"):
        if md.is_file():
            fix_zapisi_file(md)

    rebuild_slova_from_cards()
    print("Тема «Семья» выделена из «Общение».")


if __name__ == "__main__":
    main()
