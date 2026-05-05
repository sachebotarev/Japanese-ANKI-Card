#!/usr/bin/env python3
"""Генерация заметок Записи/<тема>/<Слово>.md по JSON-карточкам (см. docs/zapisi-spec.md)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "Карточки"
IMAGES = ROOT / "Картинки"
AUDIO = ROOT / "Произношение"
ZAPISI = ROOT / "Записи"
REPORT = ROOT / "docs" / "zapisi-generation-report.md"

DECK = "Японские слова"

REQUIRED = (
    "Слово",
    "Чтение",
    "Перевод",
    "Пример",
    "Пример без слова",
    "Пример перевод",
    "Заметки",
    "Кандзи-разбор",
    "Показать фуригану",
    "Теги",
)

STUDY_SPAN = re.compile(
    r"<span\s+class=['\"]study-word['\"]>([^<]*)</span>",
    re.IGNORECASE,
)
BR_SPLIT = re.compile(r"<br\s*/?>", re.IGNORECASE)


def split_three(text: str) -> tuple[list[str] | None, str | None]:
    text = (text or "").strip()
    if not text:
        return None, "пустое поле примеров"
    parts = [p.strip() for p in BR_SPLIT.split(text)]
    if len(parts) != 3:
        return None, f"нужно ровно 3 фрагмента по <br>, получено {len(parts)}"
    return parts, None


def html_to_md_line(s: str) -> str:
    s = STUDY_SPAN.sub(lambda m: f"**{m.group(1)}**", s)
    s = re.sub(r"<[^>]+>", "", s)
    return s.strip()


def yaml_tags(tags: object) -> str:
    if not isinstance(tags, list):
        return "  []"
    lines: list[str] = []
    for t in tags:
        s = str(t)
        if any(c in s for c in (":", '"', "\n")) or "・" in s or s.startswith((" ", "'", '"')):
            lines.append(f"  - {json.dumps(s, ensure_ascii=False)}")
        else:
            lines.append(f"  - {s}")
    return "\n".join(lines) if lines else "  []"


def find_image(topic: str, word: str) -> tuple[str | None, str | None]:
    base = IMAGES / topic / word
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        p = base.with_suffix(ext)
        if p.is_file():
            return ext[1:], None
    return None, f"нет файла Картинки/{topic}/{word}.(png|jpg|…)"


def check_audio(topic: str, word: str) -> str | None:
    d = AUDIO / topic
    need = [
        d / f"{word}_слово.mp3",
        d / f"{word}_пример_1.mp3",
        d / f"{word}_пример_2.mp3",
        d / f"{word}_пример_3.mp3",
    ]
    for p in need:
        if not p.is_file():
            return f"нет файла {p.relative_to(ROOT)}"
    return None


def build_markdown(
    data: dict,
    topic: str,
    word: str,
    img_ext: str,
    ex1: tuple[str, str],
    ex2: tuple[str, str],
    ex3: tuple[str, str],
) -> str:
    rel_json = f"Карточки/{topic}/{word}.json"
    furigana = str(data.get("Показать фуригану", "N")).strip()

    body = [
        "---",
        f"карточка: {rel_json}",
        f"колода_anki: {DECK}",
        f"тема: {topic}",
        "tags:",
        yaml_tags(data.get("Теги")),
        f'показать_фуригану: "{furigana}"',
        "---",
        "",
        f"# {word}",
        "",
        str(data["Чтение"]).strip(),
        "",
        str(data["Перевод"]).strip(),
        "",
        f"![[Произношение/{topic}/{word}_слово.mp3]]",
        "",
        f"![[Картинки/{topic}/{word}.{img_ext}]]",
        "",
        "## Примеры",
        "",
    ]

    for i, (jp, ru) in enumerate((ex1, ex2, ex3), start=1):
        body.extend(
            [
                f"### Пример {i}",
                "",
                f"![[Произношение/{topic}/{word}_пример_{i}.mp3]]",
                "",
                jp,
                "",
                ru,
                "",
            ]
        )

    body.extend(
        [
            "## Заметки",
            "",
            str(data["Заметки"]).strip(),
            "",
            "## Кандзи-разбор",
            "",
            str(data["Кандзи-разбор"]).strip(),
            "",
        ]
    )
    return "\n".join(body)


def process_card(json_path: Path) -> tuple[str, str | None]:
    """Возвращает ('ok'|'skip', причина при skip)."""
    rel = json_path.relative_to(CARDS)
    topic = rel.parts[0]
    word = rel.stem

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return "skip", f"не читается JSON: {e}"

    for key in REQUIRED:
        if key not in data:
            return "skip", f"нет поля «{key}»"

    pe, err = split_three(str(data["Пример"]))
    if err:
        return "skip", f"Пример: {err}"
    pb, err = split_three(str(data["Пример без слова"]))
    if err:
        return "skip", f"Пример без слова: {err}"
    pr, err = split_three(str(data["Пример перевод"]))
    if err:
        return "skip", f"Пример перевод: {err}"

    pairs: list[tuple[str, str]] = []
    for i in range(3):
        pairs.append(
            (
                html_to_md_line(pe[i]),
                html_to_md_line(pr[i]),
            )
        )

    img_ext, err = find_image(topic, word)
    if err:
        return "skip", err

    err = check_audio(topic, word)
    if err:
        return "skip", err

    md = build_markdown(data, topic, word, img_ext, pairs[0], pairs[1], pairs[2])
    out = ZAPISI / topic / f"{word}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    return "ok", None


def main() -> int:
    ok = 0
    skipped: list[tuple[str, str]] = []

    if len(sys.argv) > 1:
        card_paths: list[Path] = []
        for raw in sys.argv[1:]:
            p = (ROOT / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
            if not p.is_file():
                print(f"[skip] файл не найден: {raw}", file=sys.stderr)
                continue
            try:
                p.relative_to(CARDS)
            except ValueError:
                print(f"[skip] не внутри Карточки/: {p}", file=sys.stderr)
                continue
            card_paths.append(p)
        for json_path in sorted(card_paths):
            status, reason = process_card(json_path)
            rel = json_path.relative_to(ROOT)
            if status == "ok":
                ok += 1
            else:
                skipped.append((str(rel), reason or "?"))
        print(f"OK: {ok}, skip: {len(skipped)} (режим отдельных путей — отчёт {REPORT.relative_to(ROOT)} не обновлялся)")
        for path, reason in skipped:
            print(f"  [{path}] {reason}", file=sys.stderr)
        return 0

    for json_path in sorted(CARDS.rglob("*.json")):
        status, reason = process_card(json_path)
        rel = json_path.relative_to(ROOT)
        if status == "ok":
            ok += 1
        else:
            skipped.append((str(rel), reason or "?"))

    lines = [
        "# Отчёт: генерация Записи из карточек",
        "",
        f"- Успешно записано заметок: **{ok}**",
        f"- Пропущено (без создания файла): **{len(skipped)}**",
        "",
        "## Пропуски с причинами",
        "",
    ]
    for path, reason in skipped:
        lines.append(f"- `{path}` — {reason}")
    lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")

    print(f"OK: {ok}, skip: {len(skipped)}, report: {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
