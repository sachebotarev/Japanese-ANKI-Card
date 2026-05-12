#!/usr/bin/env python3
"""
Одноразовая миграция тем (май 2026): переименование папок и перенос карточек,
обновление поля Теги в JSON и путей в Записи/*.md.

Запуск из корня репозитория:
  python3 scripts/migrate_themes_2026_05.py
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Имена тем-папок (должны совпадать с подкаталогом в Карточки/).
THEME_DIRS: frozenset[str] = frozenset(
    {
        "Глаголы",
        "Счётные суффиксы",
        "Гардероб",
        "Канцелярия",
        "Вопросительные слова",
        "Прилагательные_い",
        "Прилагательные_な",
        "Учёба",
        "Наречия",
        "Анатомия",
        "Здоровье",
        "Календарь",
        "Работа",
        "География",
        "Общение",
        "Семья",
        "Профессии",
        "Погода",
        "Катакана",
        "Финансы",
        "Почта",
        "Покупки",
        "Жильё",
        "Быт",
        "Транспорт",
        "Продукты",
        "Спорт",
        "Традиции",
        "Медиа",
        "Достопримечательности",
        "Природа",
        "Правопорядок",
    }
)

# Старые имена папок, которые нужно вычистить из Теги (заменяются на актуальную папку).
LEGACY_THEME_TAGS: frozenset[str] = frozenset(
    {
        "Одежда и аксессуары",
        "Части тела",
        "Здоровье и состояние",
        "Время и календарь",
        "Страны",
        "Покупки и сервис",
        "Дом и помещения",
        "Техника и медиа",
        "Повседневность",
        "Существительные",
    }
)


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _move_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    _ensure_dir(dst.parent)
    shutil.move(str(src), str(dst))
    return True


def move_word_bundle(word: str, old_theme: str, new_theme: str) -> None:
    """Перенос JSON, картинок, mp3 и заметки Записи для одного слова."""
    subs = ["Карточки", "Картинки", "Произношение", "Записи"]
    for sub in subs:
        old_base = ROOT / sub / old_theme
        new_base = ROOT / sub / new_theme
        if sub == "Карточки":
            src = old_base / f"{word}.json"
            dst = new_base / f"{word}.json"
            if src.exists():
                _ensure_dir(new_base)
                shutil.move(str(src), str(dst))
        elif sub == "Записи":
            for ext in (".md",):
                src = old_base / f"{word}{ext}"
                dst = new_base / f"{word}{ext}"
                if src.exists():
                    _ensure_dir(new_base)
                    shutil.move(str(src), str(dst))
        elif sub == "Картинки":
            if not old_base.exists():
                continue
            for p in old_base.iterdir():
                if p.is_file() and p.stem == word:
                    _ensure_dir(new_base)
                    shutil.move(str(p), str(new_base / p.name))
        elif sub == "Произношение":
            if not old_base.exists():
                continue
            prefix = f"{word}_"
            for p in old_base.iterdir():
                if p.is_file() and p.name.startswith(prefix) and p.suffix.lower() == ".mp3":
                    _ensure_dir(new_base)
                    shutil.move(str(p), str(new_base / p.name))


def rename_theme_folder(old: str, new: str) -> None:
    for sub in ("Карточки", "Картинки", "Произношение", "Записи"):
        a = ROOT / sub / old
        b = ROOT / sub / new
        if a.exists():
            if b.exists():
                raise RuntimeError(f"Целевая папка уже существует: {b}")
            _ensure_dir(b.parent)
            shutil.move(str(a), str(b))


def remove_empty_dir(path: Path) -> None:
    if path.is_dir() and not any(path.iterdir()):
        path.rmdir()


def fix_json_theme_tag(json_path: Path) -> None:
    theme = json_path.parent.name
    if theme not in THEME_DIRS:
        return
    data = json.loads(json_path.read_text(encoding="utf-8"))
    tags = list(data.get("Теги") or [])
    tags = [t for t in tags if t not in THEME_DIRS or t == theme]
    tags = [t for t in tags if t not in LEGACY_THEME_TAGS]
    if theme not in tags:
        tags.insert(0, theme)
    data["Теги"] = tags
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fix_zapisi_file(md_path: Path) -> None:
    theme = md_path.parent.name
    if theme not in THEME_DIRS:
        return
    word = md_path.stem
    json_path = ROOT / "Карточки" / theme / f"{word}.json"
    if not json_path.exists():
        return
    data = json.loads(json_path.read_text(encoding="utf-8"))
    tags = list(data.get("Теги") or [])

    text = md_path.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^карточка:\s*.+$", f"карточка: Карточки/{theme}/{word}.json", text)
    text = re.sub(r"(?m)^тема:\s*.+$", f"тема: {theme}", text)
    text = re.sub(r"Произношение/[^/\]]+/", f"Произношение/{theme}/", text)
    text = re.sub(r"Картинки/[^/\]]+/", f"Картинки/{theme}/", text)
    tags_block = "tags:\n" + "\n".join(f"  - {t}" for t in tags) + "\n"
    text = re.sub(r"(?m)^tags:\n(?:  - .*\n)+", tags_block, text)
    md_path.write_text(text, encoding="utf-8")


def rebuild_slova_from_cards() -> None:
    slova = ROOT / "Слова"
    _ensure_dir(slova)
    cards_root = ROOT / "Карточки"
    valid: set[str] = set()
    for theme_dir in sorted(cards_root.iterdir(), key=lambda p: p.name):
        if not theme_dir.is_dir() or theme_dir.name.startswith("."):
            continue
        valid.add(theme_dir.name)
        words = sorted([p.stem for p in theme_dir.glob("*.json") if p.is_file()])
        (slova / theme_dir.name).write_text(
            "\n".join(words) + ("\n" if words else ""),
            encoding="utf-8",
        )
    for f in slova.iterdir():
        if f.is_file() and f.name not in valid:
            f.unlink()


def main() -> None:
    # 1) Новые темы — каталоги
    for t in (
        "Финансы",
        "Почта",
        "Быт",
        "Транспорт",
        "Продукты",
        "Спорт",
        "Традиции",
        "Достопримечательности",
        "Природа",
        "Правопорядок",
    ):
        for sub in ("Карточки", "Картинки", "Произношение", "Записи"):
            _ensure_dir(ROOT / sub / t)

    # 2) Сначала целиком переименуем «Техника и медиа» → «Медиа»
    if (ROOT / "Карточки" / "Техника и медиа").exists():
        rename_theme_folder("Техника и медиа", "Медиа")

    # 3) Вынос из «Покупки и сервис»
    for w in ("銀行", "口座"):
        move_word_bundle(w, "Покупки и сервис", "Финансы")
    move_word_bundle("郵便局", "Покупки и сервис", "Почта")

    # 4) Переименования целых папок
    pairs = [
        ("Одежда и аксессуары", "Гардероб"),
        ("Части тела", "Анатомия"),
        ("Здоровье и состояние", "Здоровье"),
        ("Время и календарь", "Календарь"),
        ("Страны", "География"),
        ("Дом и помещения", "Жильё"),
    ]
    for old, new in pairs:
        if (ROOT / "Карточки" / old).exists():
            rename_theme_folder(old, new)

    if (ROOT / "Карточки" / "Покупки и сервис").exists():
        rename_theme_folder("Покупки и сервис", "Покупки")

    # 5) Из «Повседневность»
    for w in ("机", "椅子", "引っ越し"):
        move_word_bundle(w, "Повседневность", "Быт")
    transport = (
        "タクシー",
        "バス",
        "地下鉄",
        "急行",
        "新幹線",
        "普通",
        "特急",
        "番線",
        "自転車",
        "船",
        "車",
        "電車",
        "飛行機",
        "駅",
    )
    for w in transport:
        move_word_bundle(w, "Повседневность", "Транспорт")
    for w in ("パン", "卵", "果物", "肉", "野菜", "魚"):
        move_word_bundle(w, "Повседневность", "Продукты")
    for w in ("サッカー", "テニス"):
        move_word_bundle(w, "Повседневность", "Спорт")
    move_word_bundle("花見", "Повседневность", "Традиции")
    move_word_bundle("写真", "Повседневность", "Медиа")
    move_word_bundle("たばこ", "Повседневность", "Покупки")
    move_word_bundle("期待", "Повседневность", "Здоровье")

    # 6) Из «Существительные»
    move_word_bundle("二足", "Существительные", "Счётные суффиксы")
    move_word_bundle("耳鼻科", "Существительные", "Здоровье")
    move_word_bundle("石油", "Существительные", "Природа")
    move_word_bundle("大阪城", "Существительные", "Достопримечательности")
    move_word_bundle("新大阪", "Существительные", "Транспорт")
    move_word_bundle("甲子園", "Существительные", "Спорт")
    move_word_bundle("中米", "Существительные", "География")
    move_word_bundle("首都", "Существительные", "География")
    move_word_bundle("日常系", "Существительные", "Медиа")
    for w in ("犯人", "持ち主", "場合"):
        move_word_bundle(w, "Существительные", "Правопорядок")

    # 7) Пустые старые каталоги
    for sub in ("Карточки", "Картинки", "Произношение", "Записи"):
        for dead in ("Повседневность", "Существительные"):
            d = ROOT / sub / dead
            if d.exists():
                try:
                    remove_empty_dir(d)
                except OSError:
                    pass

    # 8) Обновить Теги во всех JSON
    for jp in ROOT.glob("Карточки/**/*.json"):
        if jp.is_file():
            fix_json_theme_tag(jp)

    # 9) Обновить пути в Записи
    for md in ROOT.glob("Записи/**/*.md"):
        if md.is_file():
            fix_zapisi_file(md)

    # 10) Пересобрать Слова/ из имён JSON
    rebuild_slova_from_cards()

    print("Миграция тем завершена.")


if __name__ == "__main__":
    main()
