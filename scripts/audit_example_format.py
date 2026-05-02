#!/usr/bin/env python3
"""Сводка по формату примеров (ровно 3 × <br>) для всех Карточки/**/*.json."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from example_format_common import count_example_parts, is_triple_format, load_card  # noqa: E402

REPORT = ROOT / "docs" / "example-format-audit.md"


def main() -> int:
    cards = sorted((ROOT / "Карточки").rglob("*.json"))
    ok = []
    bad: list[tuple[str, str]] = []
    for p in cards:
        rel = p.relative_to(ROOT)
        try:
            d = load_card(p)
        except Exception as e:
            bad.append((str(rel), f"read error: {e}"))
            continue
        if is_triple_format(d):
            ok.append(str(rel))
            continue
        pe = count_example_parts(str(d.get("Пример")))
        pb = count_example_parts(str(d.get("Пример без слова")))
        pr = count_example_parts(str(d.get("Пример перевод")))
        bad.append((str(rel), f"P={pe} B={pb} R={pr}"))

    lines = [
        "# Аудит формата примеров (`<br>` × 3)",
        "",
        f"- Всего карточек: **{len(cards)}**",
        f"- Уже в нужном формате: **{len(ok)}**",
        f"- Нуждаются в правке: **{len(bad)}**",
        "",
        "## Список карточек, которые ещё нужно привести к трём примерам",
        "",
    ]
    for rel, reason in bad:
        lines.append(f"- `{rel}` — {reason}")
    lines.append("")
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{REPORT.relative_to(ROOT)}: ok={len(ok)} bad={len(bad)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
