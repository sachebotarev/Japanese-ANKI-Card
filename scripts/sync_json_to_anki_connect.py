#!/usr/bin/env python3
"""
Синхронизация JSON-карточек с Anki через AnkiConnect (порт по умолчанию 8765).

Для каждой карточки в Карточки/<тема>/<Слово>.json находит заметку в колоде «Японские слова»
по точному совпадению поля «Слово», затем при необходимости загружает mp3 из Произношение/<тема>/,
обновляет все текстовые поля и заменяет набор тегов на содержимое поля Теги в JSON.

  ANKI_CONNECT_URL=http://127.0.0.1:8765 python3 scripts/sync_json_to_anki_connect.py
  python3 scripts/sync_json_to_anki_connect.py --dry-run --limit 10
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "Карточки"
DECK = "Японские слова"

SOUND_FILES_RE = re.compile(r"\[sound:([^\]]+)\]")

# Как у MCP model_field_names для «Японские слова»
FIELD_ORDER = [
    "Слово",
    "Чтение",
    "Перевод",
    "Подсказка",
    "Пример",
    "Пример без слова",
    "Пример перевод",
    "Картинка",
    "Произношение",
    "Заметки",
    "Кандзи-разбор",
    "Показать фуригану",
]


def invoke(url: str, action: str, **params: object) -> object:
    body = json.dumps({"action": action, "version": 6, "params": params}, ensure_ascii=False).encode(
        "utf-8"
    )
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    err = payload.get("error")
    if err:
        raise RuntimeError(f"{action}: {err}")
    return payload.get("result")


def sound_filenames(pronunciation: str) -> list[str]:
    return sorted({m.group(1) for m in SOUND_FILES_RE.finditer(pronunciation or "")})


def sync_note(url: str, topic: str, data: dict, dry_run: bool) -> tuple[str | None, str | None]:
    word = str(data.get("Слово", "")).strip()
    if not word:
        return None, "пустое Слово"
    esc = word.replace('"', '\\"').replace("`", "").replace("|", "\\|")
    q = f'deck:"{DECK}" "Слово:{esc}"'
    nids = invoke(url, "findNotes", query=q)
    if not nids:
        return None, f"нет заметки для «{word}»"
    if len(nids) > 1:
        sys.stderr.write(
            f"[warn] «{word}»: несколько заметок ({len(nids)}), обновляется первая ({nids[0]}).\n"
        )
    nid = nids[0]
    if dry_run:
        return str(nid), None

    for fname in sound_filenames(str(data.get("Произношение", ""))):
        mp3_path = ROOT / "Произношение" / topic / fname
        if not mp3_path.is_file():
            sys.stderr.write(
                f"[warn] Пропуск загрузки аудио ({mp3_path.relative_to(ROOT)} отсутствует) — поле всё же обновится.\n"
            )
            continue
        b64 = base64.standard_b64encode(mp3_path.read_bytes()).decode("ascii")
        invoke(url, "storeMediaFile", filename=fname, data=b64)

    fields: dict[str, str] = {}
    for k in FIELD_ORDER:
        val = data.get(k)
        fields[k] = "" if val is None else str(val)
    invoke(url, "updateNoteFields", note={"id": nid, "fields": fields})

    info = invoke(url, "notesInfo", notes=[nid])
    note = info[0] if isinstance(info, list) and info else {}
    prev = note.get("tags") or []
    if prev:
        invoke(url, "removeTags", notes=[nid], tags=" ".join(prev))
    tag_list_in = []
    for t in data.get("Теги", []) or []:
        s = str(t).strip()
        if s and s not in tag_list_in:
            tag_list_in.append(s)
    if tag_list_in:
        invoke(url, "addTags", notes=[nid], tags=" ".join(tag_list_in))

    return str(nid), None


def main() -> int:
    ap = argparse.ArgumentParser(description="Протолкнуть JSON в Anki через AnkiConnect")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument(
        "--anki-connect-url",
        default=os.environ.get("ANKI_CONNECT_URL", "http://127.0.0.1:8765"),
    )
    args = ap.parse_args()

    try:
        invoke(args.anki_connect_url, "version")
    except (urllib.error.URLError, RuntimeError, OSError, TimeoutError) as exc:
        print(f"Не подключиться к AnkiConnect ({args.anki_connect_url}): {exc}", file=sys.stderr)
        return 1

    todo: list[tuple[Path, str, dict]] = []
    for p in sorted(CARDS.rglob("*.json")):
        rel = p.relative_to(ROOT)
        topic = rel.parts[1]
        try:
            with p.open(encoding="utf-8") as f:
                parsed = json.load(f)
        except json.JSONDecodeError as e:
            print(f"[skip] {rel}: {e}", file=sys.stderr)
            continue
        todo.append((p, topic, parsed))
    if args.limit > 0:
        todo = todo[: args.limit]

    ok = missing = errs = 0
    for p, topic, data in todo:
        rel = p.relative_to(ROOT).as_posix()
        nid, err = sync_note(args.anki_connect_url, topic, data, args.dry_run)
        if err:
            print(f"[{rel}] {err}", file=sys.stderr)
            if err.startswith("нет заметки"):
                missing += 1
            else:
                errs += 1
            continue
        ok += 1

    msg = (
        f"Успешно: {ok}, заметки не найдены в колоде: {missing}, прочих ошибок: {errs}"
        + (" (dry-run)" if args.dry_run else "")
    )
    print(msg)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
