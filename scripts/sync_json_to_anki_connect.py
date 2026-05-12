#!/usr/bin/env python3
"""
Синхронизация JSON-карточек с Anki через AnkiConnect (порт по умолчанию 8765).

Для каждой карточки в Карточки/<тема>/<Слово>.json находит заметку в колоде «Японские слова»
по точному совпадению поля «Слово», затем при необходимости загружает mp3 из Произношение/<тема>/,
обновляет поля и заменяет набор тегов на содержимое поля Теги в JSON.

При обновлении существующей заметки соблюдаются правила из docs/anki-sync.md (раздел
«Правила обновления карточек»): при совпадении «Пример» сохраняются заполненное
«Произношение» и картинка в «Картинка», если она уже не промпт.

  ANKI_CONNECT_URL=http://127.0.0.1:8765 python3 scripts/sync_json_to_anki_connect.py
  python3 scripts/sync_json_to_anki_connect.py --dry-run --limit 10
  python3 scripts/sync_json_to_anki_connect.py --if-tag みんな初級I-第02課 --create-missing
  python3 scripts/sync_json_to_anki_connect.py --create-all-missing
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
HTML_TAG_RE = re.compile(r"<[^>]+>")
IMG_SRC_RE = re.compile(r'src\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
NOTES_INFO_BATCH = 250


def _example_normalized(text: str) -> str:
    """Сравнение примеров по смыслу текста без HTML (см. docs/anki-sync.md)."""
    s = HTML_TAG_RE.sub("", text or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _picture_field_has_image(html: str) -> bool:
    """Поле «Картинка» в Anki уже с картинкой, а не промпт (anki-sync.md)."""
    h = (html or "").strip().lower()
    if not h:
        return False
    if "<img" in h:
        return True
    if "japanese_words_" in h:
        return True
    if re.search(r"\.(png|jpe?g|webp|gif)\b", h, re.I):
        return True
    return False


def _note_fields_map(note_info_item: dict) -> dict[str, str]:
    """notesInfo[0] -> плоский dict полей."""
    out: dict[str, str] = {}
    raw = (note_info_item or {}).get("fields") or {}
    for name, meta in raw.items():
        if isinstance(meta, dict) and "value" in meta:
            out[name] = str(meta.get("value") or "")
        else:
            out[name] = str(meta or "")
    return out


def _merge_fields_respecting_anki_sync_rules(
    anki_fields: dict[str, str], json_data: dict
) -> dict[str, str]:
    """
    Полный набор полей для updateNoteFields: база из JSON,
    но Картинка и Произношение сохраняются из Anki, если Пример совпадает
    и выполнены условия из docs/anki-sync.md.
    """
    merged = note_fields_payload(json_data)
    j_ex = merged.get("Пример", "")
    a_ex = anki_fields.get("Пример", "") or ""
    if _example_normalized(a_ex) != _example_normalized(j_ex):
        return merged
    # Пример совпадает — особые случаи для озвучки и картинки
    a_pron = (anki_fields.get("Произношение") or "").strip()
    if a_pron:
        merged["Произношение"] = a_pron
    a_pic = anki_fields.get("Картинка") or ""
    if _picture_field_has_image(a_pic):
        merged["Картинка"] = a_pic
    return merged

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


def upload_card_image_media(url: str, topic: str, data: dict) -> None:
    """Копирует файл из Картинки/<тема>/ в collection.media под именем из <img src>."""
    pic_html = str(data.get("Картинка") or "")
    m = IMG_SRC_RE.search(pic_html)
    if not m:
        return
    media_fname = m.group(1).strip()
    if not media_fname or re.search(r"[\s/]", media_fname):
        return
    word = str(data.get("Слово", "")).strip()
    if not word:
        return
    base = ROOT / "Картинки" / topic / word
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        src = base.with_suffix(ext)
        if not src.is_file():
            continue
        b64 = base64.standard_b64encode(src.read_bytes()).decode("ascii")
        invoke(url, "storeMediaFile", filename=media_fname, data=b64)
        return
    sys.stderr.write(
        f"[warn] Нет локальной картинки для «{word}» ({base}.png|jpg…).\n"
    )


def words_present_in_deck(url: str) -> set[str]:
    """Все значения поля «Слово» в колоде (для --create-all-missing)."""
    nids: list = invoke(url, "findNotes", query=f'deck:"{DECK}"') or []
    out: set[str] = set()
    for i in range(0, len(nids), NOTES_INFO_BATCH):
        chunk = nids[i : i + NOTES_INFO_BATCH]
        infos = invoke(url, "notesInfo", notes=chunk) or []
        for ni in infos:
            fm = _note_fields_map(ni)
            w = (fm.get("Слово") or "").strip()
            if w:
                out.add(w)
    return out


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


def create_note_from_json(
    url: str, topic: str, data: dict, dry_run: bool, *, allow_duplicate: bool = False
) -> tuple[str | None, str | None]:
    """Создаёт новую заметку во всех полях из JSON и загружает mp3 из репозитория."""
    word = str(data.get("Слово", "")).strip()
    if not word:
        return None, "пустое Слово"
    if dry_run:
        return f"<dry-{word}>", None

    upload_card_image_media(url, topic, data)
    upload_sound_files(url, topic, str(data.get("Произношение", "")))

    note_spec: dict[str, object] = {
        "deckName": DECK,
        "modelName": MODEL,
        "fields": note_fields_payload(data),
        "options": {"allowDuplicate": allow_duplicate},
        "tags": json_tag_list(data),
    }
    try:
        nid = invoke(url, "addNote", note=note_spec)
    except RuntimeError as exc:
        err_s = str(exc).lower()
        if "duplicate" in err_s or "duplicat" in err_s:
            return None, f"addNote: дубликат ({exc})"
        raise
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

    info_before = invoke(url, "notesInfo", notes=[nid])
    note0 = info_before[0] if isinstance(info_before, list) and info_before else {}
    anki_fields = _note_fields_map(note0)
    fields_to_write = _merge_fields_respecting_anki_sync_rules(anki_fields, data)

    upload_sound_files(url, topic, str(fields_to_write.get("Произношение", "")))

    invoke(url, "updateNoteFields", note={"id": nid, "fields": fields_to_write})

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
    ap.add_argument(
        "--create-all-missing",
        action="store_true",
        help=(
            "Один раз загрузить список «Слово» из колоды, затем создать через addNote "
            "только те JSON, для которых в колоде ещё нет заметки. Не обновляет существующие. "
            "Опционально сузить список через --if-tag. Несовместимо с --create-missing."
        ),
    )
    args = ap.parse_args()

    if args.create_missing and args.create_all_missing:
        print("Нельзя одновременно --create-missing и --create-all-missing.", file=sys.stderr)
        return 2

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

    if args.create_all_missing:
        present = words_present_in_deck(args.anki_connect_url)
        n_in_deck = len(present)
        to_create: list[tuple[Path, str, dict]] = []
        for p, topic, data in todo:
            w = str(data.get("Слово", "")).strip()
            if not w or w in present:
                continue
            to_create.append((p, topic, data))
        added = failed = 0
        for p, topic, data in to_create:
            rel = p.relative_to(ROOT).as_posix()
            if args.dry_run:
                print(f"[dry-run] создать: {rel} «{data.get('Слово')}»")
                added += 1
                continue
            nid_new, cerr = create_note_from_json(args.anki_connect_url, topic, data, False)
            if cerr and (
                "дубликат" in (cerr or "").lower() or "duplicate" in (cerr or "").lower()
            ):
                nid2, cerr2 = create_note_from_json(
                    args.anki_connect_url, topic, data, False, allow_duplicate=True
                )
                if not cerr2:
                    nid_new, cerr = nid2, None
                    sys.stderr.write(
                        f"[{rel}] вторая попытка с allowDuplicate=True (nid={nid_new})\n"
                    )
                else:
                    cerr = f"{cerr}; повтор с allowDuplicate: {cerr2}"
            if cerr:
                failed += 1
                sys.stderr.write(f"[{rel}] не создана: {cerr}\n")
            else:
                added += 1
                w = str(data.get("Слово", "")).strip()
                if w:
                    present.add(w)
                print(f"[{rel}] создано nid={nid_new}")
        print(
            f"Режим --create-all-missing: уникальных «Слово» в колоде было: {n_in_deck}, "
            f"JSON без заметки: {len(to_create)}, создано: {added}, ошибок: {failed}"
            + (" (dry-run)" if args.dry_run else "")
        )
        return 1 if failed else 0

    ok = missing = errs = added = 0
    for p, topic, data in todo:
        rel = p.relative_to(ROOT).as_posix()
        nid, err = sync_note(args.anki_connect_url, topic, data, args.dry_run)
        if err:
            if err.startswith("нет заметки") and args.create_missing:
                nid_new, cerr = create_note_from_json(args.anki_connect_url, topic, data, args.dry_run)
                if cerr and (
                    "дубликат" in (cerr or "").lower() or "duplicate" in (cerr or "").lower()
                ):
                    nid2, cerr2 = create_note_from_json(
                        args.anki_connect_url, topic, data, args.dry_run, allow_duplicate=True
                    )
                    if not cerr2:
                        nid_new, cerr = nid2, None
                    else:
                        cerr = f"{cerr}; allowDuplicate: {cerr2}"
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
