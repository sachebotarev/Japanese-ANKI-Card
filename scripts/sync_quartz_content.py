#!/usr/bin/env python3
"""
Копирует Записи/ в quartz_content/ (темы на верхнем уровне) и заменяет
Obsidian-вставки ![[...]] на абсолютные raw.githubusercontent.com URL
(картинки — markdown image, аудио — <audio>).

Содержимое уходит в quartz_content/ в корне репозитория, а сборка ванильным
Quartz запускается с флагом `-d ../quartz_content` из временного клона апстрима
(см. scripts/build_quartz.sh). Каталог quartz_content/ — сборочный артефакт,
коммитить его не нужно (он в .gitignore).

Переменные окружения:
  QUARTZ_RAW_BASE — префикс без завершающего слэша, например
    https://raw.githubusercontent.com/sachebotarev/Japanese-ANKI-Card/main
  По умолчанию подставляется репозиторий из git remote origin и ветка main.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
ZAPISI = ROOT / "Записи"
QUARTZ_CONTENT = ROOT / "quartz_content"

WIKI = re.compile(r"!\[\[([^\]]+)\]\]")

AUDIO_EXT = (".mp3", ".m4a", ".wav", ".ogg", ".opus")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")


def quartz_path_segment(segment: str) -> str:
    """
    Один сегмент пути в ссылках как у Quartz (см. quartz/util/path.ts → sluggify):
    пробелы → «-», иначе SPA/статик не совпадают с папкой «Части тела» на диске.
    """
    return (
        segment.replace(" ", "-")
        .replace("&", "-and-")
        .replace("%", "-percent")
        .replace("?", "")
        .replace("#", "")
    )


def default_raw_base() -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(ROOT), "remote", "get-url", "origin"],
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        out = ""
    # https://github.com/user/repo.git или git@github.com:user/repo.git
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", out)
    if m:
        user, repo = m.group(1), m.group(2)
        return f"https://raw.githubusercontent.com/{user}/{repo}/main"
    return "https://raw.githubusercontent.com/sachebotarev/Japanese-ANKI-Card/main"


def raw_url(base: str, inner: str) -> str:
    inner = inner.strip().replace("\\", "/")
    segs = [quote(s, safe="") for s in inner.split("/") if s]
    return f"{base.rstrip('/')}/{'/'.join(segs)}"


def replace_wikilinks(text: str, base: str) -> str:
    def repl(m: re.Match[str]) -> str:
        inner = m.group(1).strip()
        url = raw_url(base, inner)
        low = inner.lower()
        if any(low.endswith(ext) for ext in AUDIO_EXT):
            return f'<audio controls src="{url}" style="max-width:100%;width:28em;"></audio>'
        if any(low.endswith(ext) for ext in IMAGE_EXT):
            return f"![]({url})"
        # неизвестное расширение — как картинку
        return f"![]({url})"

    return WIKI.sub(repl, text)


# Маркер в конце заметки: только в копии quartz_content/, исходные Записи/ не трогаем.
NAV_THEME_MARKER = "<!-- quartz-nav-to-theme-index -->"


def yaml_plain_title(title: str) -> str:
    """Строка `title: ...` для frontmatter (в кавычках — безопасно для любых имён папок)."""
    esc = title.replace('"', '\\"')
    return f'title: "{esc}"'


def write_theme_indices_and_card_nav(dest_zapisi: Path) -> None:
    """
    Страницы папок в Quartz (FolderContent) рендерятся в JSX — ссылки из списка файлов
    не попадают в AST и не попадают в граф. Добавляем настоящий index.md в каждую тему
    со списком markdown-ссылок и ссылку «к оглавлению темы» на каждой карточке.
    """
    for topic_dir in sorted(dest_zapisi.iterdir(), key=lambda p: p.name):
        if not topic_dir.is_dir():
            continue
        topic = topic_dir.name
        card_paths = sorted(
            p for p in topic_dir.glob("*.md") if p.name.lower() != "index.md"
        )

        lines = [
            "---",
            yaml_plain_title(topic),
            f'description: "Подборка слов и примеров по теме {topic}"',
            "tags:",
            "  - тема-оглавление",
            "---",
            "",
            "[← Все темы](../index)",
            "",
            f"Тема **{topic}** — это словарь для практики в реальных фразах.",
            "Открывайте слова по одному: чтение → перевод → пример → озвучка.",
            "",
            "### Как заниматься с этой темой",
            "",
            "1. Выберите 5-10 слов из списка ниже.",
            "2. Для каждого слова прочитайте все 3 примера и повторите их вслух.",
            "3. Вернитесь к теме завтра и проверьте, что запомнилось без подсказки.",
            "",
            "## Слова по теме",
            "",
        ]
        for p in card_paths:
            stem = p.stem
            lines.append(f"- [{stem}]({stem}.md)")
        lines.append("")
        (topic_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")

        footer = f"\n\n{NAV_THEME_MARKER}\n\n[↑ Оглавление темы](index)\n"
        for p in card_paths:
            text = p.read_text(encoding="utf-8")
            if NAV_THEME_MARKER in text:
                continue
            p.write_text(text + footer, encoding="utf-8")


def main() -> int:
    import os

    if not ZAPISI.is_dir():
        print("Нет каталога Записи/", file=sys.stderr)
        return 1

    base = os.environ.get("QUARTZ_RAW_BASE", "").strip() or default_raw_base()
    print(f"QUARTZ_RAW_BASE={base}")

    if QUARTZ_CONTENT.exists():
        shutil.rmtree(QUARTZ_CONTENT)
    QUARTZ_CONTENT.mkdir(parents=True)

    # Публичные URL тем должны быть короткими: /Кандзи/, /Глаголы/, ...
    # поэтому копируем содержимое Записи/ сразу в корень контента.
    shutil.copytree(ZAPISI, QUARTZ_CONTENT, dirs_exist_ok=True)

    for md in QUARTZ_CONTENT.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        new = replace_wikilinks(text, base)
        if new != text:
            md.write_text(new, encoding="utf-8")

    write_theme_indices_and_card_nav(QUARTZ_CONTENT)

    topics = sorted(d.name for d in QUARTZ_CONTENT.iterdir() if d.is_dir())
    # Имена папок с пробелами («Части тела») в URL у Quartz — с дефисом («Части-тела»).
    topic_rows = "\n".join(
        f"| [{t}]({quartz_path_segment(t)}/) | Слова и примеры по теме |" for t in topics
    )
    if not topic_rows:
        topic_rows = "| *(нет подпапок в Записи)* | |"
    topic_bullets = "\n".join(f"- [{t}]({quartz_path_segment(t)}/)" for t in topics)

    index = QUARTZ_CONTENT / "index.md"
    index.write_text(
        f"""---
title: Японские карточки
description: >-
  Учебные заметки по японскому языку: слова, чтение, примеры и озвучка.
  Используйте темы, поиск и теги, чтобы быстро находить нужную лексику.
---

> [!abstract] Что это за сайт
> Это библиотека учебных карточек по японскому языку.
> На странице каждого слова есть чтение, перевод, три примера и озвучка.
> Если хотите начать быстрее, используйте поиск в шапке сайта.

## Как заниматься

1. [Откройте список тем →](Темы/)
2. Выберите тему и зайдите в слово.
3. Сначала прочитайте пример, затем прослушайте озвучку и повторите вслух.
4. Для повторения по уровню используйте теги (например, `N5`) или [индекс тегов](tags/).

## Выберите цель

### Хочу учить новые слова

- Начните с [каталога тем](Темы/) и выберите 1 тему.
- Откройте 5-10 слов, прочитайте примеры и прослушайте озвучку.
- Повторите слова вслух, затем переходите к следующей теме.

### Хочу повторять по уровню (например, N5)

- Откройте [индекс тегов](tags/).
- Выберите нужный тег уровня (`N5`, `N4` и т.д.).
- Повторяйте слова из этого списка и отмечайте трудные для себя.

### Хочу тренировать аудирование

- Откройте страницу слова в любой теме.
- Сначала включите озвучку примера, не подглядывая в текст.
- Затем проверьте себя по японской фразе и переводу.

## Темы ({len(topics)})

| Тема | Что внутри |
| ---- | ---------- |
{topic_rows}

<details>
<summary>Показать темы списком</summary>

{topic_bullets}

</details>

---

> [!tip] Как лучше запоминать
> Проходите 5-10 слов за раз: чтение → пример → озвучка → повторение вслух.
> Возвращайтесь к теме через день и проверяйте, какие слова уже узнаются без подсказки.
""",
        encoding="utf-8",
    )

    idx = QUARTZ_CONTENT / "Темы" / "index.md"
    idx.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "title: Темы",
        "description: Каталог тем для изучения слов с примерами и озвучкой.",
        "---",
        "",
        "> [!abstract] С чего начать",
        "> Выберите тему по своей цели: разговор, повседневные слова, грамматика или подготовка к JLPT.",
        "> Внутри каждой темы — список слов с переводом, примерами и озвучкой.",
        "",
        "## Как выбрать тему",
        "",
        "- Если хотите быстрее заговорить — начните с `Общение` и `Повседневность`.",
        "- Если готовитесь к экзамену — выбирайте темы и слова по тегам уровня (`N5`, `N4`).",
        "- Если тяжело запоминать — берите одну тему и учите по 5-10 слов в день.",
        "",
        "## Каталог тем",
        "",
    ]
    for t in topics:
        lines.append(f"- [{t}](../{quartz_path_segment(t)}/)")
    lines.append("")
    idx.write_text("\n".join(lines), encoding="utf-8")

    print(f"Скопировано и обработано: {QUARTZ_CONTENT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
