#!/usr/bin/env python3
"""Генерирует временный Quartz-контент напрямую из JSON-карточек."""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "Карточки"
IMAGES = ROOT / "Картинки"
AUDIO = ROOT / "Произношение"
CONTENT = ROOT / "quartz_content"
BR_SPLIT = re.compile(r"<br\s*/?>", re.IGNORECASE)
STUDY_SPAN = re.compile(
    r"<span\s+class=['\"]study-word['\"]>(.*?)</span>", re.IGNORECASE | re.DOTALL
)
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def quartz_path_segment(segment: str) -> str:
    return (
        segment.replace(" ", "-")
        .replace("&", "-and-")
        .replace("%", "-percent")
        .replace("?", "")
        .replace("#", "")
    )


def default_raw_base() -> str:
    try:
        origin = subprocess.check_output(
            ["git", "-C", str(ROOT), "remote", "get-url", "origin"], text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        origin = ""
    match = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", origin)
    if match:
        return f"https://raw.githubusercontent.com/{match.group(1)}/{match.group(2)}/main"
    return "https://raw.githubusercontent.com/sachebotarev/Japanese-ANKI-Card/main"


def raw_url(base: str, relative: Path) -> str:
    encoded = "/".join(quote(part, safe="") for part in relative.parts)
    return f"{base.rstrip('/')}/{encoded}"


def yaml_string(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def split_three(value: object) -> list[str]:
    parts = [part.strip() for part in BR_SPLIT.split(str(value or "").strip())]
    if len(parts) != 3 or not all(parts):
        raise ValueError(f"ожидалось три непустых примера по <br>, получено {len(parts)}")
    return parts


def example_to_markdown(value: str) -> str:
    value = STUDY_SPAN.sub(lambda match: f"**{match.group(1)}**", value)
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip()


def find_image(topic: str, basename: str) -> Path | None:
    for extension in IMAGE_EXTENSIONS:
        candidate = IMAGES / topic / f"{basename}{extension}"
        if candidate.is_file():
            return candidate
    return None


def audio_player(base: str, topic: str, filename: str) -> str | None:
    path = AUDIO / topic / filename
    if not path.is_file():
        return None
    url = raw_url(base, path.relative_to(ROOT))
    return f'<audio controls src="{url}" style="max-width:100%;width:28em;"></audio>'


def build_card_page(json_path: Path, data: dict, base: str) -> tuple[str, int]:
    relative = json_path.relative_to(CARDS)
    if len(relative.parts) != 2:
        raise ValueError("карточка должна лежать в Карточки/<тема>/")
    topic, basename = relative.parent.name, json_path.stem
    word = str(data.get("Слово", "")).strip()
    reading = str(data.get("Чтение", "")).strip()
    translation = str(data.get("Перевод", "")).strip()
    if not word or not reading or not translation:
        raise ValueError("нет обязательного поля Слово, Чтение или Перевод")
    examples = split_three(data.get("Пример"))
    translations = split_three(data.get("Пример перевод"))
    tags = data.get("Теги") if isinstance(data.get("Теги"), list) else []

    lines = [
        "---",
        f"title: {yaml_string(word)}",
        f"description: {yaml_string(f'{reading} — {translation}')}",
        f"source_json: {yaml_string(str(json_path.relative_to(ROOT)))}",
        f"topic: {yaml_string(topic)}",
        "tags:",
        *([f"  - {yaml_string(tag)}" for tag in tags] or ["  []"]),
        f"show_furigana: {yaml_string(data.get('Показать фуригану', 'N'))}",
        "---",
        "",
        f"# {word}",
        "",
        reading,
        "",
        translation,
        "",
    ]
    media_count = 0
    player = audio_player(base, topic, f"{basename}_слово.mp3")
    if player:
        lines.extend([player, ""])
        media_count += 1
    image_path = find_image(topic, basename)
    if image_path:
        lines.extend([f"![]({raw_url(base, image_path.relative_to(ROOT))})", ""])
        media_count += 1

    lines.extend(["## Примеры", ""])
    for index, (jp, ru) in enumerate(zip(examples, translations), start=1):
        lines.extend([f"### Пример {index}", ""])
        player = audio_player(base, topic, f"{basename}_пример_{index}.mp3")
        if player:
            lines.extend([player, ""])
            media_count += 1
        lines.extend([example_to_markdown(jp), "", example_to_markdown(ru), ""])

    notes = str(data.get("Заметки", "")).strip()
    if notes:
        lines.extend(["## Заметки", "", notes, ""])
    kanji = str(data.get("Кандзи-разбор", "")).strip()
    if kanji:
        lines.extend(["## Кандзи-разбор", "", kanji, ""])
    lines.extend(["[↑ Оглавление темы](index)", ""])
    return "\n".join(lines), media_count


def generate_card_pages(base: str) -> tuple[int, int, int]:
    generated = skipped = media = 0
    for json_path in sorted(CARDS.rglob("*.json")):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            page, page_media = build_card_page(json_path, data, base)
            output = CONTENT / json_path.relative_to(CARDS).with_suffix(".md")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(page, encoding="utf-8")
            generated += 1
            media += page_media
        except (OSError, json.JSONDecodeError, ValueError) as error:
            skipped += 1
            print(f"[skip] {json_path.relative_to(ROOT)}: {error}", file=sys.stderr)
    return generated, skipped, media


def write_theme_indices() -> list[str]:
    topics: list[str] = []
    for topic_dir in sorted(path for path in CONTENT.iterdir() if path.is_dir()):
        if topic_dir.name == "Темы":
            continue
        topics.append(topic_dir.name)
        cards = sorted(path for path in topic_dir.glob("*.md") if path.name != "index.md")
        lines = [
            "---",
            f"title: {yaml_string(topic_dir.name)}",
            f"description: {yaml_string(f'Подборка слов по теме {topic_dir.name}')}",
            "tags:",
            '  - "тема-оглавление"',
            "---",
            "",
            "[← Все темы](../Темы/)",
            "",
            f"## Слова по теме ({len(cards)})",
            "",
            *(f"- [{path.stem}]({path.name})" for path in cards),
            "",
        ]
        (topic_dir / "index.md").write_text("\n".join(lines), encoding="utf-8")
    return topics


def write_navigation(topics: list[str], card_count: int) -> None:
    rows = "\n".join(
        f"| [{topic}]({quartz_path_segment(topic)}/) | Слова и примеры по теме |"
        for topic in topics
    ) or "| *(нет тем)* | |"
    bullets = "\n".join(f"- [{topic}]({quartz_path_segment(topic)}/)" for topic in topics)
    (CONTENT / "index.md").write_text(
        f"""---
title: Японские карточки
description: Учебные карточки по японскому языку с примерами и озвучкой.
---

> [!abstract] Что это за сайт
> Библиотека из **{card_count}** японских карточек. Используйте темы, поиск и теги.

## Как заниматься

1. [Откройте список тем →](Темы/)
2. Выберите слово и прочитайте три примера.
3. Прослушайте озвучку и повторите фразы вслух.
4. Для повторения по уровню используйте [индекс тегов](tags/).

## Темы ({len(topics)})

| Тема | Что внутри |
| ---- | ---------- |
{rows}

<details>
<summary>Показать темы списком</summary>

{bullets}

</details>
""",
        encoding="utf-8",
    )
    themes = CONTENT / "Темы"
    themes.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "title: Темы",
        "description: Каталог тем для изучения японских слов.",
        "---",
        "",
        "## Каталог тем",
        "",
        *(f"- [{topic}](../{quartz_path_segment(topic)}/)" for topic in topics),
        "",
    ]
    (themes / "index.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    if not CARDS.is_dir():
        print("Нет каталога Карточки/", file=sys.stderr)
        return 1
    base = os.environ.get("QUARTZ_RAW_BASE", "").strip() or default_raw_base()
    if CONTENT.exists():
        shutil.rmtree(CONTENT)
    CONTENT.mkdir(parents=True)
    generated, skipped, media = generate_card_pages(base)
    topics = write_theme_indices()
    write_navigation(topics, generated)
    print(
        f"Quartz content: карточек={generated}, пропущено={skipped}, "
        f"тем={len(topics)}, медиа-вставок={media}, raw={base}"
    )
    return 1 if skipped else 0


if __name__ == "__main__":
    sys.exit(main())
