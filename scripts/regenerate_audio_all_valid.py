#!/usr/bin/env python3
"""Перегенерировать озвучку с --force для всех карточек в новом формате (3 примера через <br>)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "Карточки"
GEN = ROOT / "scripts" / "generate_aivis_audio.py"


def main() -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    from generate_aivis_audio import parse_examples  # type: ignore

    paths: list[Path] = []
    for p in sorted(CARDS.rglob("*.json")):
        raw = p.read_text(encoding="utf-8")
        import json

        data = json.loads(raw)
        try:
            parse_examples(str(data.get("Пример", "")))
        except Exception:
            continue
        paths.append(p)

    print(f"Карточек с валидными 3 примерами: {len(paths)} из {len(list(CARDS.rglob('*.json')))}")
    failures: list[Path] = []
    for i, p in enumerate(paths, start=1):
        r = subprocess.run(
            [sys.executable, str(GEN), "--force", "--write-json", str(p)],
            cwd=str(ROOT),
        )
        if r.returncode != 0:
            failures.append(p)
        if i % 20 == 0:
            print(f"… {i}/{len(paths)}", flush=True)
    if failures:
        print("Ошибки:", len(failures), file=sys.stderr)
        for fp in failures[:30]:
            print(" ", fp.relative_to(ROOT), file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
