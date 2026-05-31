#!/usr/bin/env python3
"""
Нормализация глагольных карточек: словарная форма в поле «Слово» и «Чтение»,
объединение дубликатов (ます-форма, ／, 出来る/できる, 先る/咲く).

Запуск из корня репозитория:
  python3 scripts/normalize_verb_dictionary_form.py --dry-run
  python3 scripts/normalize_verb_dictionary_form.py
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME = "Глаголы"
CARDS_DIR = ROOT / "Карточки" / THEME
WORDS_FILE = ROOT / "Слова" / THEME

# Слово остаётся как есть (это уже словарная форма, не ます-спряжение).
DICT_FORM_EXCEPTIONS = frozenset({"覚ます"})

# Явное слияние синонимов / опечаток -> каноническая словарная форма.
ALIAS_TO_CANONICAL: dict[str, str] = {
    "出来る": "できる",
    "先る": "咲く",
}

IMG_RE = re.compile(r"<img", re.I)
SOUND_RE = re.compile(r"\[sound:")


SPECIAL_MASU_TO_DICT: dict[str, str] = {
    "見ます": "見る",
    "来ます": "来る",
    "います": "いる",
}


def masu_to_dict(word: str, tags: list[str]) -> str:
    if word in DICT_FORM_EXCEPTIONS:
        return word
    if word in SPECIAL_MASU_TO_DICT:
        return SPECIAL_MASU_TO_DICT[word]
    if word.endswith("します") and word != "します":
        return word.replace("します", "する")
    if not word.endswith("ます"):
        return word
    tagset = set(tags)
    stem = word[:-2]
    if _tagset_has(tags, "一段"):
        return stem + "る"
    if _tagset_has(tags, "サ変", "する"):
        return word.replace("ます", "する")
    if stem.endswith("い"):
        return stem[:-1] + "う"
    if stem.endswith("き"):
        return stem[:-1] + "く"
    if stem.endswith("ぎ"):
        return stem[:-1] + "ぐ"
    if stem.endswith("し"):
        return stem[:-1] + "す"
    if stem.endswith("ち"):
        return stem[:-1] + "つ"
    if stem.endswith("に"):
        return stem[:-1] + "ぬ"
    if stem.endswith("び"):
        return stem[:-1] + "ぶ"
    if stem.endswith("み"):
        return stem[:-1] + "む"
    if stem.endswith("り"):
        return stem[:-1] + "る"
    # Учебные глаголы без тега класса: по умолчанию 一段
    return stem + "る"


def _tagset_has(tags: list[str], *needles: str) -> bool:
    for t in tags:
        ts = str(t)
        for n in needles:
            if n in ts:
                return True
    return False


def masu_reading_to_dict(reading: str, tags: list[str]) -> str:
    if not reading.endswith("ます"):
        return reading
    stem = reading[:-2]
    if _tagset_has(tags, "一段"):
        return stem + "る"
    if _tagset_has(tags, "サ変", "する"):
        return reading.replace("ます", "する")
    if stem.endswith("い"):
        return stem[:-1] + "う"
    if stem.endswith("き"):
        return stem[:-1] + "く"
    if stem.endswith("ぎ"):
        return stem[:-1] + "ぐ"
    if stem.endswith("し"):
        return stem[:-1] + "す"
    if stem.endswith("ち"):
        return stem[:-1] + "つ"
    if stem.endswith("に"):
        return stem[:-1] + "ぬ"
    if stem.endswith("び"):
        return stem[:-1] + "ぶ"
    if stem.endswith("み"):
        return stem[:-1] + "む"
    if stem.endswith("り"):
        return stem[:-1] + "る"
    return stem + "る"


def canonical_word(raw: str, tags: list[str]) -> str:
    w = raw.strip()
    for sep in ("／", "・", "/", "、"):
        if sep in w:
            w = w.split(sep)[0].strip()
    if w in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[w]
    if w.endswith("ます") and w not in DICT_FORM_EXCEPTIONS:
        return masu_to_dict(w, tags)
    return w


def has_image(val: str) -> bool:
    v = val or ""
    return bool(IMG_RE.search(v) or "japanese_words_" in v)


def is_prompt(val: str) -> bool:
    v = (val or "").strip()
    return v.startswith("Иллюстрация") or (bool(v) and not has_image(v))


def quality_score(data: dict) -> int:
    s = 0
    if (data.get("Подсказка") or "").strip():
        s += 3
    if (data.get("Заметки") or "").strip():
        s += 3
    kb = (data.get("Кандзи-разбор") or "").strip()
    if kb and not kb.startswith("—"):
        s += 2
    ex = data.get("Пример") or ""
    if ex.count("<br>") >= 2:
        s += 4
    if "study-word" in ex:
        s += 2
    pic = data.get("Картинка") or ""
    if has_image(pic):
        s += 6
    elif pic and not is_prompt(pic):
        s += 1
    if SOUND_RE.search(data.get("Произношение") or ""):
        s += 3
    tags = data.get("Теги") or []
    s += sum(1 for t in tags if str(t).startswith("みんな"))
    s += sum(1 for t in tags if re.match(r"^N\d", str(t)))
    s += sum(1 for t in tags if str(t).startswith("動詞"))
    return s


def merge_tags(a: list, b: list) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in list(a) + list(b):
        ts = str(t).strip()
        if ts and ts not in seen:
            seen.add(ts)
            out.append(ts)
    return out


def pick_text(primary: str, secondary: str) -> str:
    p, s = (primary or "").strip(), (secondary or "").strip()
    if len(p) >= len(s):
        return primary or secondary or ""
    return secondary or primary or ""


def merge_cards(cards: list[dict]) -> dict:
    """cards: list of (source_word, data) sorted by quality desc."""
    cards = sorted(cards, key=lambda x: quality_score(x[1]), reverse=True)
    base_word, merged = cards[0]
    tags = merged.get("Теги") or []
    for _, other in cards[1:]:
        tags = merge_tags(tags, other.get("Теги") or [])
        for field in (
            "Перевод",
            "Подсказка",
            "Пример",
            "Пример без слова",
            "Пример перевод",
            "Заметки",
            "Кандзи-разбор",
        ):
            if not (merged.get(field) or "").strip() or (
                field == "Кандзи-разбор"
                and (merged.get(field) or "").strip().startswith("—")
            ):
                merged[field] = pick_text(merged.get(field, ""), other.get(field, ""))
            elif field in ("Пример", "Пример без слова", "Пример перевод"):
                if quality_score({**merged, field: other.get(field)}) > quality_score(merged):
                    merged[field] = other.get(field) or merged.get(field)
        if not has_image(merged.get("Картинка") or "") and has_image(other.get("Картинка") or ""):
            merged["Картинка"] = other["Картинка"]
        if not SOUND_RE.search(merged.get("Произношение") or "") and SOUND_RE.search(
            other.get("Произношение") or ""
        ):
            merged["Произношение"] = other["Произношение"]
        if other.get("Показать фуригану") == "Y" and merged.get("Показать фуригану") != "Y":
            merged["Показать фуригану"] = "Y"

    target = canonical_word(base_word, tags)
    merged["Слово"] = target
    merged["Теги"] = tags
    reading = (merged.get("Чтение") or "").strip()
    if reading.endswith("ます") and target not in DICT_FORM_EXCEPTIONS:
        merged["Чтение"] = masu_reading_to_dict(reading, tags)
    elif target == "できる" and reading in ("できます", "出来る"):
        merged["Чтение"] = "できる"
    return merged


def fix_reading(data: dict) -> bool:
    w = data.get("Слово", "")
    r = (data.get("Чтение") or "").strip()
    tags = data.get("Теги") or []
    if w in DICT_FORM_EXCEPTIONS:
        return False
    if w == "できる" and r in ("できます", "出来る", "できます"):
        if r != "できる":
            data["Чтение"] = "できる"
            return True
        return False
    if not r.endswith("ます"):
        return False
    if w.endswith("ます") and w not in DICT_FORM_EXCEPTIONS:
        return False
    new_r = masu_reading_to_dict(r, tags)
    if new_r != r:
        data["Чтение"] = new_r
        return True
    return False


def fix_media_refs(data: dict, old_words: list[str], new_word: str) -> None:
    for field in ("Произношение", "Картинка"):
        val = data.get(field) or ""
        for old in old_words:
            if old == new_word:
                continue
            val = val.replace(f"{old}_", f"{new_word}_")
            val = val.replace(f"japanese_words_{old}.", f"japanese_words_{new_word}.")
            val = val.replace(f"[sound:{old}.mp3]", f"[sound:{new_word}.mp3]")
        data[field] = val


def rename_media(old_word: str, new_word: str, dry_run: bool) -> None:
    if old_word == new_word:
        return
    for sub, exts in (
        ("Картинки", (".png", ".jpg", ".jpeg", ".webp")),
        ("Произношение", (".mp3",)),
    ):
        folder = ROOT / sub / THEME
        if not folder.exists():
            continue
        for p in folder.iterdir():
            if not p.name.startswith(old_word + "_") and p.stem != old_word:
                continue
            suffix = p.name[len(old_word) :]
            dst = folder / f"{new_word}{suffix}"
            if dry_run:
                print(f"  [dry-run] media {p.name} -> {dst.name}")
            elif dst.exists():
                p.unlink()
            else:
                shutil.move(str(p), str(dst))
    zap = ROOT / "Записи" / THEME / f"{old_word}.md"
    zap_new = ROOT / "Записи" / THEME / f"{new_word}.md"
    if zap.exists() and not zap_new.exists():
        if dry_run:
            print(f"  [dry-run] zapisi {zap.name} -> {zap_new.name}")
        else:
            shutil.move(str(zap), str(zap_new))


def delete_bundle(word: str, dry_run: bool) -> None:
    paths = [
        CARDS_DIR / f"{word}.json",
        ROOT / "Записи" / THEME / f"{word}.md",
    ]
    for p in paths:
        if p.exists():
            if dry_run:
                print(f"  [dry-run] delete {p.relative_to(ROOT)}")
            else:
                p.unlink()
    for sub, pattern in (
        ("Картинки", f"{word}.png"),
        ("Произношение", f"{word}_*"),
    ):
        folder = ROOT / sub / THEME
        if not folder.exists():
            continue
        if pattern.endswith("*"):
            for p in folder.glob(pattern):
                if dry_run:
                    print(f"  [dry-run] delete {p.relative_to(ROOT)}")
                else:
                    p.unlink()
        else:
            p = folder / pattern
            if p.exists():
                if dry_run:
                    print(f"  [dry-run] delete {p.relative_to(ROOT)}")
                else:
                    p.unlink()


def update_words_file(canonical_words: set[str], removed: set[str], dry_run: bool) -> None:
    if not WORDS_FILE.exists():
        return
    lines = WORDS_FILE.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        w = line.strip()
        if not w:
            continue
        cw = canonical_word(w, [])
        if w in removed or cw in removed:
            continue
        if cw in seen:
            continue
        seen.add(cw)
        out.append(cw)
    for w in sorted(canonical_words):
        if w not in seen:
            out.append(w)
            seen.add(w)
    out.sort()
    text = "\n".join(out) + "\n"
    if dry_run:
        print(f"[dry-run] Слова/Глаголы: {len(lines)} -> {len(out)} строк")
    else:
        WORDS_FILE.write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    by_target: dict[str, list[tuple[str, dict]]] = {}
    for p in sorted(CARDS_DIR.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        src = data.get("Слово", p.stem)
        tags = data.get("Теги") or []
        tgt = canonical_word(src, tags)
        by_target.setdefault(tgt, []).append((src, data))

    removed_words: set[str] = set()
    written: list[tuple[str, dict]] = []

    for target, group in sorted(by_target.items()):
        if len(group) == 1:
            src, data = group[0]
            changed = False
            if data.get("Слово") != target:
                data["Слово"] = target
                changed = True
            if fix_reading(data):
                changed = True
            if src != target:
                removed_words.add(src)
                fix_media_refs(data, [src], target)
                rename_media(src, target, args.dry_run)
            if changed or src != target:
                written.append((target, data))
                if not args.dry_run:
                    out = CARDS_DIR / f"{target}.json"
                    out.write_text(
                        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    if src != target and (CARDS_DIR / f"{src}.json").exists():
                        (CARDS_DIR / f"{src}.json").unlink()
            continue

        print(f"Merge {len(group)} -> {target}:")
        for src, d in group:
            print(f"  - {src} (score={quality_score(d)})")
        merged = merge_cards(group)
        old_srcs = [src for src, _ in group if src != target]
        fix_media_refs(merged, old_srcs + [s for s, _ in group], target)
        written.append((target, merged))
        for src, _ in group:
            if src != target:
                removed_words.add(src)
        if not args.dry_run:
            (CARDS_DIR / f"{target}.json").write_text(
                json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        for src, _ in group:
            if src != target:
                if not args.dry_run and (CARDS_DIR / f"{src}.json").exists():
                    (CARDS_DIR / f"{src}.json").unlink()
                delete_bundle(src, args.dry_run)

    # Удалить осиротевшие медиа дубликатов (не трогаем слова, переименованные в канон)
    for w in sorted(removed_words):
        tgt = canonical_word(w, [])
        if tgt != w:
            continue
        delete_bundle(w, args.dry_run)

    canonical = set(by_target.keys())
    update_words_file(canonical, removed_words, args.dry_run)

    report = ROOT / "docs" / "normalize-verbs-dict-form-report.md"
    lines = [
        "# Нормализация глаголов в словарную форму",
        "",
        f"- Групп после слияния: {len(by_target)}",
        f"- Удалено форм: {len(removed_words)}",
        "",
        "## Удалённые / объединённые формы",
        "",
    ]
    for w in sorted(removed_words):
        tgt = canonical_word(w, [])
        lines.append(f"- `{w}` → `{tgt}`")
    lines += ["", "## Обновлённые карточки (чтение/слово)", ""]
    for target, data in written:
        lines.append(f"- `{target}` — чтение `{data.get('Чтение')}`")
    if args.dry_run:
        print("[dry-run] отчёт не записан")
    else:
        report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Отчёт: {report}")

    print(f"Готово: {len(removed_words)} форм удалено/объединено, {len(written)} карточек обновлено.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
