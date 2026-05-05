#!/usr/bin/env python3
"""
Синхронизация JSON-карточек с Anki через AnkiConnect (порт по умолчанию 8765).

Для каждой карточки в Карточки/<тема>/<Слово>.json находит заметку в колоде «Японские слова»
по точному совпадению поля «Слово», затем при необходимости загружает mp3 из Произношение/<тема>/,
обновляет все текстовые поля и заменяет набор тегов на содержимое поля Теги в JSON.

  ANKI_CONNECT_URL=http://127.0.0.1:8765 python3 scripts/sync_json_to_anki_connect.py
  python3 scripts/sync_json_to_anki_connect.py --dry-run --limit 10
  python3 scripts/sync_json_to_anki_connect.py --if-tag みんな初級I-第02課 --create-missing
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
MODEL = "Японские слова"

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


def upload_sound_files(url: str, topic: str, pronunciation: str) -> None:
    """Загружает озвучку из Произношение/<тема>/ в collection.media Anki."""
    for fname in sound_filenames(str(pronunciation)):
        mp3_path = ROOT / "Произношение" / topic / fname
        if not mp3_path.is_file():
            sys.stderr.write(
                f"[warn] Нет аудио ({mp3_path.relative_to(ROOT)} — поле синхронизируется без файла).\n"
            )
            continue
        b64 = base64.standard_b64encode(mp3_path.read_bytes()).decode("ascii")
        invoke(url, "storeMediaFile", filename=fname, data=b64)


def json_tag_list(data: dict) -> list[str]:
    out: list[str] = []
    for t in data.get("Теги", []) or []:
        s = str(t).strip()
        if s and s not in out:
            out.append(s)
    return out


def note_fields_payload(data: dict) -> dict[str, str]:
    fields: dict[str, str] = {}
    for k in FIELD_ORDER:
        val = data.get(k)
        fields[k] = "" if val is None else str(val)
    return fields


def create_note_from_json(url: str, topic: str, data: dict, dry_run: bool) -> tuple[str | None, str | None]:
    """Создаёт новую заметку во всех полях из JSON и загружает mp3 из репозитория."""
    word = str(data.get("Слово", "")).strip()
    if not word:
        return None, "пустое Слово"
    if dry_run:
        return f"<dry-{word}>", None

    upload_sound_files(url, topic, str(data.get("Произношение", "")))

    note_spec: dict[str, object] = {
        "deckName": DECK,
        "modelName": MODEL,
        "fields": note_fields_payload(data),
        "options": {"allowDuplicate": False},
        "tags": json_tag_list(data),
    }
    nid = invoke(url, "addNote", note=note_spec)
    if nid is None:
        return None, "addNote вернул null (вероятный дубликат или конфликт полей)"
    return str(int(nid)), None


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

    upload_sound_files(url, topic, str(data.get("Произношение", "")))

    invoke(url, "updateNoteFields", note={"id": nid, "fields": note_fields_payload(data)})

    info = invoke(url, "notesInfo", notes=[nid])
    note = info[0] if isinstance(info, list) and info else {}
    prev = note.get("tags") or []
    if prev:
        invoke(url, "removeTags", notes=[nid], tags=" ".join(prev))
    tag_list_in = json_tag_list(data)
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
    ap.add_argument(
        "--if-tag",
        metavar="TAG",
        help="Обрабатывать только JSON, у которых в списке «Теги» есть указанное значение.",
    )
    ap.add_argument(
        "--create-missing",
        action="store_true",
        help=(
            "Если заметки в колоде нет, создать её через addNote "
            "(только вместе с --if-tag, чтобы случайно не создать сотни карточек)."
        ),
    )
    args = ap.parse_args()

    if args.create_missing and not args.if_tag:
        print(
            "--create-missing можно использовать только с --if-tag.",
            file=sys.stderr,
        )
        return 2

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
        if args.if_tag:
            card_tags = {str(t).strip() for t in (parsed.get("Теги") or [])}
            card_tags.discard("")
            if args.if_tag not in card_tags:
                continue
        todo.append((p, topic, parsed))
    if args.limit > 0:
        todo = todo[: args.limit]

    ok = missing = errs = added = 0
    for p, topic, data in todo:
        rel = p.relative_to(ROOT).as_posix()
        nid, err = sync_note(args.anki_connect_url, topic, data, args.dry_run)
        if err:
            if err.startswith("нет заметки") and args.create_missing:
                nid_new, cerr = create_note_from_json(args.anki_connect_url, topic, data, args.dry_run)
                if cerr:
                    print(f"[{rel}] не создана заметка: {cerr}", file=sys.stderr)
                    errs += 1
                else:
                    added += 1
                    print(f"[{rel}] создано nid={nid_new}")
                continue
            print(f"[{rel}] {err}", file=sys.stderr)
            if err.startswith("нет заметки"):
                missing += 1
            else:
                errs += 1
            continue
        ok += 1

    msg = (
        f"Обновлено: {ok}, создано: {added}, заметки не найдены: {missing}, прочих ошибок: {errs}"
        + (" (dry-run)" if args.dry_run else "")
    )
    print(msg)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
