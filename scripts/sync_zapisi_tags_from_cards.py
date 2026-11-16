#!/usr/bin/env python3
"""Обновляет в существующих заметках Записи/ только блок YAML «tags:» из JSON-карточки."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "Карточки"
ZAPISI = ROOT / "Записи"


def yaml_tags_line_block(tags: object) -> str:
    lines = []
    lines.append("tags:")
    if not isinstance(tags, list) or len(tags) == 0:
        lines.append("  []")
        return "\n".join(lines)
    for t in tags:
        s = str(t)
        if any(c in s for c in (":", '"', "\n")) or "・" in s or s.startswith((" ", "'", '"')):
            dumped = json.dumps(s, ensure_ascii=False)
            lines.append(f"  - {dumped}")
        elif s.startswith("〜") or "[" in s or "]" in s:
            lines.append(f"  - {json.dumps(s, ensure_ascii=False)}")
        else:
            lines.append(f"  - {s}")
    return "\n".join(lines)


def replace_tags_in_note(md_text: str, new_block: str) -> tuple[str, bool]:
    m = re.search(r"\n(?=tags:\n)", md_text)
    if not m:
        return md_text, False
    head = md_text[: m.start()]
    tail = md_text[m.start() + 1 :]
    lines = tail.splitlines(keepends=True)
    if not lines or not lines[0].startswith("tags:"):
        return md_text, False
    i = 1
    while i < len(lines) and (lines[i].startswith("  - ") or lines[i].startswith("  []")):
        i += 1
    rest = "".join(lines[i:])
    return head + "\n" + new_block + "\n" + rest, True


def main() -> int:
    updated = 0
    missing = []
    for p in sorted(ZAPISI.rglob("*.md")):
        if p.name.lower() == "index.md":
            continue
        topic = p.parent.name
        word = p.stem
        jc = CARDS / topic / f"{word}.json"
        if not jc.exists():
            missing.append(str(p.relative_to(ROOT)))
            continue
        data = json.loads(jc.read_text(encoding="utf-8"))
        tags = data.get("Теги", [])
        block = yaml_tags_line_block(tags)
        text = p.read_text(encoding="utf-8")
        new_text, ok = replace_tags_in_note(text, block)
        if ok and new_text != text:
            p.write_text(new_text, encoding="utf-8")
            updated += 1
    print(f"Обновлено заметок (только tags): {updated}")
    if missing:
        print(f"Нет JSON для {len(missing)} файлов заметок (пример: {missing[:5]})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
