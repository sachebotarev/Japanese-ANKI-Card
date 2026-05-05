#!/usr/bin/env python3
"""Одноразовая миграция: Карточки/Кандзи -> целевые темы + обновление тегов и Записи."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Слово (базовое имя файла) -> тема назначения. Дубликат 元気: только удалить из Кандзи.
DEST: dict[str, str] = {
    "お兄さん": "Общение",
    "お姉さん": "Общение",
    "お母さん": "Общение",
    "お父さん": "Общение",
    "主な": "Прилагательные_な",
    "主人": "Общение",
    "他": "Общение",
    "元学長": "Учёба",
    "元日": "Повседневность",
    "兄": "Общение",
    "兄弟": "Общение",
    "友人": "Общение",
    "友情": "Общение",
    "友達": "Общение",
    "天気": "Повседневность",
    "夫": "Общение",
    "夫人": "Общение",
    "夫妻": "Общение",
    "夫婦": "Общение",
    "奥": "Общение",
    "奥さん": "Общение",
    "妹": "Общение",
    "妻": "Общение",
    "姉": "Общение",
    "姉妹": "Общение",
    "子弟": "Общение",
    "弟": "Общение",
    "弟子": "Профессии",
    "彼": "Общение",
    "彼ち": "Общение",
    "彼女": "Общение",
    "所有する": "Глаголы",
    "持ち主": "Существительные",
    "有力な": "Прилагательные_な",
    "有名な": "Прилагательные_な",
    "朝食": "Повседневность",
    "母": "Общение",
    "母国": "Страны",
    "母親": "Общение",
    "気分": "Повседневность",
    "気持ち": "Повседневность",
    "父": "Общение",
    "父母": "Общение",
    "父親": "Общение",
    "病気": "Повседневность",
    "親友": "Общение",
    "長兄": "Общение",
    "雷": "Повседневность",
    "雷雲": "Повседневность",
}

def move_assets(word: str, dest: str) -> None:
    src_cards = ROOT / "Карточки" / "Кандзи" / f"{word}.json"
    dst_cards = ROOT / "Карточки" / dest / f"{word}.json"
    dst_cards.parent.mkdir(parents=True, exist_ok=True)
    if src_cards.exists():
        shutil.move(str(src_cards), str(dst_cards))

    k_img = ROOT / "Картинки" / "Кандзи"
    k_snd = ROOT / "Произношение" / "Кандзи"
    d_img = ROOT / "Картинки" / dest
    d_snd = ROOT / "Произношение" / dest
    d_img.mkdir(parents=True, exist_ok=True)
    d_snd.mkdir(parents=True, exist_ok=True)

    if k_img.exists():
        for p in k_img.glob(f"{word}.*"):
            tgt = d_img / p.name
            if tgt.exists():
                # не затираем существующий файл в целевой теме (напр. уже есть образ)
                continue
            shutil.move(str(p), str(tgt))
    if k_snd.exists():
        for p in k_snd.glob(f"{word}_*.mp3"):
            tgt = d_snd / p.name
            if tgt.exists():
                continue
            shutil.move(str(p), str(tgt))


def fix_tags(path: Path, theme: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    tags = data.get("Теги") or []
    new_tags = [theme if t == "Кандзи" else t for t in tags]
    if theme not in new_tags:
        new_tags.insert(0, theme)
    # сохранить порядок, убрать дубликаты
    seen: set[str] = set()
    dedup = []
    for t in new_tags:
        if t not in seen:
            seen.add(t)
            dedup.append(t)
    data["Теги"] = dedup
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def move_zapis(word: str, dest: str) -> None:
    z_old = ROOT / "Записи" / "Кандзи" / f"{word}.md"
    if not z_old.exists():
        return
    z_dir = ROOT / "Записи" / dest
    z_dir.mkdir(parents=True, exist_ok=True)
    txt = z_old.read_text(encoding="utf-8")
    txt = txt.replace("карточка: Карточки/Кандзи/", f"карточка: Карточки/{dest}/")
    txt = txt.replace("Карточки/Кандзи/", f"Карточки/{dest}/")
    txt = txt.replace("Картинки/Кандзи/", f"Картинки/{dest}/")
    txt = txt.replace("Произношение/Кандзи/", f"Произношение/{dest}/")
    txt = txt.replace("\nтема: Кандзи\n", f"\nтема: {dest}\n")
    txt = txt.replace("\n  - Кандзи\n", f"\n  - {dest}\n", 1)
    z_new = z_dir / f"{word}.md"
    z_new.write_text(txt, encoding="utf-8")
    z_old.unlink()


def drop_duplicate_genki() -> None:
    for sub in ("Карточки", "Картинки", "Произношение"):
        k = ROOT / sub / "Кандзи"
        if sub == "Карточки":
            p = k / "元気.json"
            if p.exists():
                p.unlink()
        elif sub == "Картинки":
            for p in list(k.glob("元気.*")):
                dup = ROOT / "Картинки" / "Прилагательные_な" / p.name
                if dup.exists():
                    p.unlink()
                else:
                    shutil.move(str(p), str(dup))
        else:
            for p in list(k.glob("元気_*.mp3")):
                dup = ROOT / "Произношение" / "Прилагательные_な" / p.name
                if dup.exists():
                    p.unlink()
                else:
                    shutil.move(str(p), str(dup))
    zp = ROOT / "Записи" / "Кандзи" / "元気.md"
    zd = ROOT / "Записи" / "Прилагательные_な" / "元気.md"
    if zp.exists():
        if zd.exists():
            zp.unlink()
        else:
            shutil.move(str(zp), str(zd))
            t = zd.read_text(encoding="utf-8")
            t = t.replace("Карточки/Кандзи/", "Карточки/Прилагательные_な/")
            t = t.replace("Картинки/Кандзи/", "Картинки/Прилагательные_な/")
            t = t.replace("Произношение/Кандзи/", "Произношение/Прилагательные_な/")
            t = t.replace("\nтема: Кандзи\n", "\nтема: Прилагательные_な\n")
            t = t.replace("\n  - Кандзи\n", "\n  - Прилагательные_な\n", 1)
            zd.write_text(t, encoding="utf-8")


def normalize_slova_words() -> list[str]:
    p = ROOT / "Слова" / "Кандзи"
    if not p.exists():
        return []
    lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return sorted(lines)


def merge_slova(kandzi_words: list[str]) -> None:
    by_dest: dict[str, list[str]] = {}
    for w in kandzi_words:
        if w == "元気":
            by_dest.setdefault("Прилагательные_な", []).append(w)
            continue
        d = DEST.get(w)
        if not d:
            raise SystemExit(f"Нет темы для слова из списка: {w}")
        by_dest.setdefault(d, []).append(w)

    for dest, additions in by_dest.items():
        sp = ROOT / "Слова" / dest
        if not sp.exists():
            sp.write_text("", encoding="utf-8")
        existing = [ln.strip() for ln in sp.read_text(encoding="utf-8").splitlines() if ln.strip()]
        merged = sorted(set(existing) | set(additions))
        sp.write_text("\n".join(merged) + "\n", encoding="utf-8")


def cleanup_empty_kandzi_dirs() -> None:
    for name in ("Карточки", "Картинки", "Произношение", "Записи"):
        d = ROOT / name / "Кандзи"
        if d.exists() and not any(d.iterdir()):
            d.rmdir()


def main() -> None:
    k_words = normalize_slova_words()
    # перенос карточек и медиа
    drop_duplicate_genki()

    for word, dest in sorted(DEST.items()):
        move_assets(word, dest)

    # теги в перенесённых json
    for word, dest in DEST.items():
        jp = ROOT / "Карточки" / dest / f"{word}.json"
        if jp.exists():
            fix_tags(jp, dest)

    for word in DEST:
        move_zapis(word, DEST[word])

    merge_slova(k_words)

    slova_kandzi = ROOT / "Слова" / "Кандзи"
    if slova_kandzi.exists():
        slova_kandzi.unlink()

    cleanup_empty_kandzi_dirs()

    leftover = list((ROOT / "Карточки" / "Кандзи").glob("*.json")) if (ROOT / "Карточки" / "Кандзи").exists() else []
    if leftover:
        raise SystemExit(f"Остались JSON в Карточки/Кандзи: {leftover}")

    print("Миграция завершена.")


if __name__ == "__main__":
    main()
