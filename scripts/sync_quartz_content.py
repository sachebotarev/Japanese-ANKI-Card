#!/usr/bin/env python3
"""
Копирует Записи/ в quartz/content/Записи и заменяет Obsidian-вставки ![[...]]
на абсолютные raw.githubusercontent.com URL (картинки — markdown image, аудио — <audio>).

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
QUARTZ_CONTENT = ROOT / "quartz" / "content"

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


# Маркер в конце заметки: только копия в quartz/content, исходные Записи/ не трогаем.
NAV_THEME_MARKER = "<!-- quartz-nav-to-theme-index -->"


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
            f"title: «{topic}» — карточки",
            "tags:",
            "  - тема-оглавление",
            "---",
            "",
            "[← Все темы записи](../index)",
            "",
            f"Оглавление темы **{topic}**: ссылки ниже участвуют в **графе связей** на сайте (Quartz берёт рёбра только из markdown, а не из авто-списка папки).",
            "",
            "## Заметки",
            "",
        ]
        for p in card_paths:
            stem = p.stem
            lines.append(f"- [{stem}]({stem}.md)")
        lines.append("")
        (topic_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")

        footer = (
            f"\n\n{NAV_THEME_MARKER}\n\n"
            f"[↑ К списку карточек темы «{topic}»](index)\n"
        )
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

    dest_zapisi = QUARTZ_CONTENT / "Записи"
    shutil.copytree(ZAPISI, dest_zapisi)

    for md in dest_zapisi.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        new = replace_wikilinks(text, base)
        if new != text:
            md.write_text(new, encoding="utf-8")

    write_theme_indices_and_card_nav(dest_zapisi)

    topics = sorted(d.name for d in dest_zapisi.iterdir() if d.is_dir())
    # Имена папок с пробелами («Части тела») в URL у Quartz — с дефисом («Части-тела»).
    topic_rows = "\n".join(
        f"| [{t}](Записи/{quartz_path_segment(t)}/) | Откройте папку — список карточек по теме |"
        for t in topics
    )
    if not topic_rows:
        topic_rows = "| *(нет подпапок в Записи)* | |"
    topic_bullets = "\n".join(f"- [{t}](Записи/{quartz_path_segment(t)}/)" for t in topics)

    index = QUARTZ_CONTENT / "index.md"
    index.write_text(
        f"""---
title: Японские карточки
description: >-
  Заметки для Anki и изучения японского: темы, примеры, картинки и озвучка.
  Исходники в репозитории Japanese ANKI Card (папка Записи).
---

> [!abstract] Как пользоваться этим сайтом
> Здесь только **учебные заметки** из папки `Записи/`: слова, грамматика, примеры. Картинки и mp3 подгружаются с **raw.githubusercontent.com** (медиа лежит в репозитории, на сайт не дублируется).
> Используйте **поиск** (иконка в шапке) — быстрее всего найти слово или тему.

## С чего начать

1. [Обзор всех тем →](Записи/) — список разделов по части речи и тематике.
2. Откройте нужную тему в таблице ниже и переходите к отдельным словам.
3. Карточки Anki, JSON и полный пайплайн — в [репозитории на GitHub](https://github.com/sachebotarev/Japanese-ANKI-Card) (папки `Карточки/`, `docs/`).

## Темы ({len(topics)})

| Раздел | Куда ведёт |
| ------ | ---------- |
{topic_rows}

<details>
<summary>В виде списка</summary>

{topic_bullets}

</details>

---

> [!tip] Редактирование
> Меняйте `.md` в **`Записи/`** локально (например, в Obsidian), делайте commit и push в ветку `main` — GitHub Actions пересоберёт сайт за несколько минут.
""",
        encoding="utf-8",
    )

    idx = QUARTZ_CONTENT / "Записи" / "index.md"
    lines = [
        "---",
        "title: Записи по темам",
        "description: Оглавление разделов — глаголы, существительные и другие темы.",
        "---",
        "",
        "> [!info] Навигация",
        "> Каждая строка — папка с заметками-карточками. Внутри файлы по отдельным словам.",
        "",
        "## Темы",
        "",
    ]
    for t in topics:
        lines.append(f"- [{t}]({quartz_path_segment(t)}/)")
    lines.append("")
    idx.write_text("\n".join(lines), encoding="utf-8")

    print(f"Скопировано и обработано: {dest_zapisi}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
