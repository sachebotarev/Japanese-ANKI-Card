#!/usr/bin/env python3
"""
Применить массив патчей формата примеров к JSON-карточкам.

Файл патча: JSON-массив объектов с ключами:
  path — «Карточки/<тема>/<Слово>.json»
  Пример, Пример перевод
  необязательно: Картинка, Произношение

По умолчанию карточки, у которых уже три фрагмента <br> во всех полях примеров, пропускаются.

Использование:
  python3 scripts/apply_example_patches_batch.py patches/generated_non_verbs_examples.json
  python3 scripts/apply_example_patches_batch.py --force file.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from example_format_common import (  # noqa: E402
    apply_example_patch,
    is_triple_format,
    load_card,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("patch_file", type=Path)
    ap.add_argument(
        "--force",
        action="store_true",
        help="Патчить даже если формат уже тройной",
    )
    args = ap.parse_args()

    data = json.loads(args.patch_file.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("Ожидается JSON-массив", file=sys.stderr)
        return 1

    skipped = 0
    applied = 0
    errors: list[str] = []

    for item in data:
        rel = item.get("path", "").strip()
        if not rel.startswith("Карточки/"):
            errors.append(f"некорректный path: {rel!r}")
            continue
        card_path = ROOT / rel
        if not card_path.is_file():
            errors.append(f"нет файла: {rel}")
            continue
        payload = load_card(card_path)
        if is_triple_format(payload) and not args.force:
            skipped += 1
            continue
        try:
            patch = {
                "Пример": item["Пример"],
                "Пример перевод": item["Пример перевод"],
            }
            if item.get("Картинка"):
                patch["Картинка"] = item["Картинка"]
            if item.get("Произношение"):
                patch["Произношение"] = item["Произношение"]
            apply_example_patch(card_path, patch)
            applied += 1
        except Exception as e:
            errors.append(f"{rel}: {e}")

    print(f"Применено: {applied}, пропущено (уже ок): {skipped}, ошибок: {len(errors)}")
    for line in errors[:40]:
        print(" ", line, file=sys.stderr)
    if len(errors) > 40:
        print(f" ... ещё {len(errors) - 40}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
