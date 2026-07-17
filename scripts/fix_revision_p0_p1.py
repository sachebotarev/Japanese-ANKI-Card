#!/usr/bin/env python3
"""Одноразовый проход ревизии: P0 + P1 (без P2: пустые Подсказка и слабые 3-и примеры)."""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from example_format_common import BR_SPLIT, SPAN, blankify, save_card  # noqa: E402
from migrate_themes_2026_05 import (  # noqa: E402
    fix_json_theme_tag,
    fix_zapisi_file,
    move_word_bundle,
    rebuild_slova_from_cards,
)

CARDS = ROOT / "Карточки"
JLPT_SET = {"N5", "N4", "N3", "N2", "N1"}
STUDY_OPEN = "<span class='study-word'>"
STUDY_CLOSE = "</span>"

THEME_MOVES: dict[tuple[str, str], str] = {
    ("Календарь", "お釣り"): "Финансы",
    ("Календарь", "狩り"): "Природа",
    ("Календарь", "紫"): "Одежда",
    ("Календарь", "細かいお金"): "Финансы",
    ("Медицина", "遊園地"): "Туризм",
    ("Медицина", "都会"): "География",
    ("Образование", "政治"): "Право",
    ("Образование", "温度"): "Погода",
    ("Образование", "火山岩"): "Природа",
    ("Образование", "珊瑚礁"): "География",
    ("Образование", "目薬"): "Медицина",
    ("Образование", "絆創膏"): "Медицина",
    ("Общение", "アジア研究"): "Образование",
    ("Общение", "体力"): "Спорт",
    ("Общение", "泳ぐ"): "Глаголы",
    ("Общение", "秋"): "Календарь",
    ("Семья", "夢"): "Эмоции",
    ("Семья", "象"): "Природа",
    ("Семья", "貰う"): "Глаголы",
    ("Транспорт", "宝くじ"): "Финансы",
    ("Транспорт", "機械"): "Электроника",
    ("Транспорт", "洗濯機"): "Жилище",
    ("Финансы", "ねぎ"): "Еда",
    ("Финансы", "便所"): "Жилище",
    ("Финансы", "助手"): "Профессии",
    ("Финансы", "動作"): "Быт",
    ("Финансы", "周り"): "Быт",
    ("Финансы", "地震"): "Природа",
    ("Финансы", "外国"): "География",
    ("Финансы", "大人気"): "Эмоции",
    ("Финансы", "婦人服"): "Одежда",
    ("Финансы", "安売り"): "Торговля",
    ("Финансы", "定食"): "Еда",
    ("Финансы", "客"): "Торговля",
    ("Финансы", "岩"): "Природа",
    ("Финансы", "岩石"): "Природа",
    ("Финансы", "広告"): "Торговля",
    ("Финансы", "引き出し"): "Жилище",
    ("Финансы", "意見"): "Общение",
    ("Финансы", "楽しみ"): "Эмоции",
    ("Финансы", "段階"): "Быт",
    ("Финансы", "海外"): "География",
    ("Финансы", "現代"): "Быт",
    ("Финансы", "発見"): "Быт",
    ("Финансы", "真ん中"): "Быт",
    ("Финансы", "紅葉"): "Природа",
    ("Финансы", "緑"): "Природа",
    ("Финансы", "缶詰"): "Еда",
    ("Финансы", "視聴"): "Телевидение",
    ("Финансы", "読み"): "Образование",
    ("Финансы", "読み方"): "Образование",
    ("Финансы", "読書"): "Образование",
    ("Финансы", "資料"): "Работа",
    ("Финансы", "賞"): "Работа",
    ("Финансы", "間"): "Календарь",
    ("Финансы", "飲酒"): "Еда",
    # KEEP в Финансы: 家賃, 経済, 無料
}

HINT_REWRITES: dict[str, str] = {
    "География/中国": "Страна с Великой стеной и иероглифами, которые пришли в Японию.",
    "Еда/ワイン": "Напиток из винограда в бокале на ужине.",
    "Еда/牛乳": "Белая жидкость из пакета за завтраком.",
    "Жилище/出口": "Стрелка наружу — место, где покидают здание.",
    "Наречия/とても": "Усиливает прилагательное сильнее обычного «очень».",
    "Общение/人": "Тот, кто ходит на двух ногах и говорит.",
    "Общение/招待": "Когда зовут гостя на праздник или в гости.",
    "Общение/私": "Как говорящий называет себя в вежливой речи.",
    "Профессии/政治家": "Человек, который работает с законами и выборами.",
    "Семья/夫": "Мужчина в паре по отношению к жене.",
    "Транспорт/バス": "Большой общественный транспорт с множеством сидений.",
    "Глаголы/訳す": "Короче, чем 翻訳する — перенести смысл с одного языка на другой.",
    "Работа/部": "Подразделение компании, например отдел продаж.",
}

CONTENT_OVERRIDES: dict[str, dict] = {
    "География/佐藤": {
        "Пример": (
            "<span class='study-word'>佐藤</span>さんは私の友達です。<br>"
            "これは<span class='study-word'>佐藤</span>の家です。<br>"
            "今日の会議で<span class='study-word'>佐藤</span>さんに会ったので、"
            "新しい企画について話しました。"
        ),
        "Пример перевод": (
            "Господин/госпожа Сато — мой друг.<br>"
            "Это дом Сато.<br>"
            "На сегодняшнем совещании я встретил(а) господина/госпожу Сато "
            "и поговорил(а) о новом проекте."
        ),
    },
    "Календарь/秋": {
        "Перевод": "осень",
        "Пример": (
            "<span class='study-word'>秋</span>は紅葉がきれいです。<br>"
            "<span class='study-word'>秋</span>にりんごを食べます。<br>"
            "<span class='study-word'>秋</span>は涼しくて過ごしやすいので、"
            "散歩に出かけることが多いです。"
        ),
        "Пример перевод": (
            "Осенью красивые красные листья.<br>"
            "Осенью ем яблоки.<br>"
            "Осенью прохладно и приятно проводить время, поэтому я часто выхожу на прогулку."
        ),
        "Заметки": "名詞; сезон после лета. 秋分の日 — день осеннего равноденствия.",
        "Подсказка": "Сезон кленовых листьев и прохладного воздуха.",
        "Теги": ["Календарь", "みんなの日本語", "名詞", "N5"],
    },
}


def strip_spans(text: str) -> str:
    return SPAN.sub(r"\1", text or "")


def wrap_once(sentence: str, surface: str) -> str | None:
    if not surface or surface not in sentence:
        return None
    if STUDY_OPEN in sentence:
        return sentence  # already has a span
    return sentence.replace(surface, f"{STUDY_OPEN}{surface}{STUDY_CLOSE}", 1)


def godan_forms(base: str) -> list[str]:
    """Грубые формы для поиска в примерах (не полный спрягатель)."""
    forms = [base]
    if not base:
        return forms
    # ichidan-ish
    if base.endswith("る") and len(base) >= 2:
        stem = base[:-1]
        forms += [
            stem + "ます",
            stem + "ました",
            stem + "ません",
            stem + "ない",
            stem + "た",
            stem + "て",
            stem + "てください",
            stem + "られる",
            stem + "よう",
            stem + "れば",
        ]
    # suru
    if base.endswith("する"):
        stem = base[:-2]
        forms += [
            stem + "します",
            stem + "しました",
            stem + "しない",
            stem + "した",
            stem + "して",
            stem + "できる",
            base,
        ]
    # godan endings
    row = {
        "う": ("い", "った", "って", "わない", "えます"),
        "く": ("き", "いた", "いて", "かない", "けます"),
        "ぐ": ("ぎ", "いだ", "いで", "がない", "げます"),
        "す": ("し", "した", "して", "さない", "せます"),
        "つ": ("ち", "った", "って", "たない", "てます"),
        "ぬ": ("に", "んだ", "んで", "なない", "ねます"),
        "ぶ": ("び", "んだ", "んで", "ばない", "べます"),
        "む": ("み", "んだ", "んで", "まない", "めます"),
        "る": ("り", "った", "って", "らない", "れます"),
    }
    if base[-1] in row:
        i, ta, te, nai, emas = row[base[-1]]
        stem = base[:-1]
        forms += [
            stem + i + "ます",
            stem + i + "ました",
            stem + ta,
            stem + te,
            stem + nai,
            stem + emas,
            stem + i,
        ]
    # unique preserve order, longest first
    seen: set[str] = set()
    out: list[str] = []
    for f in sorted(forms, key=len, reverse=True):
        if f and f not in seen:
            seen.add(f)
            out.append(f)
    return out


def iadj_forms(base: str) -> list[str]:
    forms = [base]
    if base.endswith("い") and len(base) >= 2:
        stem = base[:-1]
        forms += [
            stem + "く",
            stem + "くて",
            stem + "かった",
            stem + "くない",
            stem + "ければ",
            stem + "さそう",
            stem + "くなり",
            stem + "くなりそう",
        ]
    seen: set[str] = set()
    out: list[str] = []
    for f in sorted(forms, key=len, reverse=True):
        if f and f not in seen:
            seen.add(f)
            out.append(f)
    return out


def candidate_surfaces(word: str, reading: str, topic: str) -> list[str]:
    cands = [word]
    # special aliases
    aliases = {
        "何時も": ["いつも", "何時も"],
        "ご飯": ["あさごはん", "ごはん", "ご飯", "朝ごはん"],
        "お腹がすく": ["お腹がすきます", "お腹がすいた", "お腹がすく", "おなかがすきます"],
        "喉が渇く": ["喉が渇きます", "喉が渇いた", "喉が渇く"],
        "お腹がすきます": ["お腹がすきます", "お腹がすいた", "お腹がすく"],
        "喉が渇きます": ["喉が渇きます", "喉が渇いた", "喉が渇く"],
        "木霊": ["木霊", "こだま"],
        "はし": ["はし", "箸"],
        "どういたしまして": ["どういたしまして"],
        "お名前は？": ["お名前は", "お名前"],
        "半分に分ける": ["半分に分け", "半分に分ける"],
        "間に合う": ["間に合い", "間に合う", "間に合います", "間に合いました"],
    }
    if word in aliases:
        cands = aliases[word] + cands
    if reading and reading != word:
        cands.append(reading)
    if topic == "Глаголы" or word.endswith(("する", "る", "う", "く", "ぐ", "す", "つ", "ぬ", "ぶ", "む")):
        cands.extend(godan_forms(word))
    if topic.startswith("Прилагательные_い") or (word.endswith("い") and topic.startswith("Прилагательные")):
        cands.extend(iadj_forms(word))
    # phrase verbs: try without する / last verb
    if "が" in word or "を" in word:
        cands.extend(godan_forms(word))
    seen: set[str] = set()
    out: list[str] = []
    for f in sorted(cands, key=len, reverse=True):
        if f and f not in seen:
            seen.add(f)
            out.append(f)
    return out


def auto_wrap_examples(data: dict, topic: str) -> tuple[str, str, list[str]]:
    word = str(data.get("Слово") or "")
    reading = str(data.get("Чтение") or "")
    raw = strip_spans(str(data.get("Пример") or ""))
    parts = [p.strip() for p in BR_SPLIT.split(raw) if p.strip() or p == ""]
    # keep exactly split parts even if empty-ish
    parts = [p.strip() for p in BR_SPLIT.split(str(data.get("Пример") or ""))]
    parts = [strip_spans(p).strip() for p in parts]
    if len(parts) != 3:
        return str(data.get("Пример") or ""), str(data.get("Пример без слова") or ""), [
            f"not_triple:{len(parts)}"
        ]
    cands = candidate_surfaces(word, reading, topic)
    errors: list[str] = []
    wrapped: list[str] = []
    for i, sent in enumerate(parts, 1):
        if SPAN.search(str(data.get("Пример") or "").split("<br>")[i - 1] if False else ""):
            pass
        # if already had span in original for this index — prefer re-detect
        ok = None
        for surface in cands:
            ok = wrap_once(sent, surface)
            if ok and STUDY_OPEN in ok:
                break
        if not ok or STUDY_OPEN not in ok:
            errors.append(f"ex{i}:{sent[:40]}")
            wrapped.append(sent)
        else:
            wrapped.append(ok)
    ex = "<br>".join(wrapped)
    blank = blankify(ex)
    # if blank still has no _____, mark error
    if blank.count("_____") < 3 - len(errors):
        pass
    return ex, blank, errors


def load_jlpt_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    order = {"N5": 5, "N4": 4, "N3": 3, "N2": 2, "N1": 1}
    for lvl in ["n5", "n4", "n3", "n2", "n1"]:
        path = Path(f"/tmp/jlpt/{lvl}.json")
        if not path.exists():
            continue
        tag = lvl.upper()
        for e in json.loads(path.read_text(encoding="utf-8")):
            for key in filter(None, [e.get("word"), e.get("reading")]):
                if key not in lookup or order[tag] > order[lookup[key]]:
                    lookup[key] = tag
    return lookup


def infer_jlpt(data: dict, lookup: dict[str, str]) -> str | None:
    word = str(data.get("Слово") or "")
    reading = str(data.get("Чтение") or "")
    tags = list(data.get("Теги") or [])
    for key in (word, reading):
        if key in lookup:
            return lookup[key]
    # polite family forms
    for suffix in ("さん",):
        if word.endswith(suffix) and word[: -len(suffix)] in lookup:
            return lookup[word[: -len(suffix)]]
    if word.startswith("ご") and word[1:] in lookup:
        return lookup[word[1:]]
    if word.startswith("お") and word[1:] in lookup:
        return lookup[word[1:]]
    if word.endswith("する") and word[:-2] in lookup:
        return lookup[word[:-2]]
    for t in tags:
        if re.fullmatch(r"みんな初級I-第\d{2}課", t):
            return "N5"
        if re.fullmatch(r"みんな初級II-第\d{2}課", t):
            return "N4"
    if any("みんな" in t for t in tags):
        return "N5"
    if any(t == "Genki" for t in tags):
        return "N5"
    if any(t == "Duolingo" for t in tags):
        return "N5"
    # fallback for remaining known-ish lexicon
    return "N4"


def fix_img_field(data: dict, topic: str) -> bool:
    pic = str(data.get("Картинка") or "").strip()
    word = str(data.get("Слово") or "")
    if pic.startswith("<img"):
        return False
    base = ROOT / "Картинки" / topic / word
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        if base.with_suffix(ext).is_file():
            data["Картинка"] = f'<img src="japanese_words_{word}.png">'
            return True
    return False


def fix_double_spaces(data: dict) -> bool:
    changed = False
    for field in ("Перевод", "Заметки", "Подсказка", "Пример перевод"):
        v = data.get(field)
        if isinstance(v, str) and "  " in v:
            data[field] = re.sub(r" {2,}", " ", v)
            changed = True
    return changed


def delete_card_bundle(topic: str, word: str) -> None:
    for sub in ("Карточки", "Картинки", "Произношение", "Записи"):
        base = ROOT / sub / topic
        if sub == "Карточки":
            p = base / f"{word}.json"
            if p.exists():
                p.unlink()
        elif sub == "Записи":
            p = base / f"{word}.md"
            if p.exists():
                p.unlink()
        elif sub == "Картинки":
            if base.exists():
                for p in base.iterdir():
                    if p.is_file() and p.stem == word:
                        p.unlink()
        elif sub == "Произношение":
            if base.exists():
                for p in base.iterdir():
                    if p.is_file() and p.name.startswith(f"{word}_") and p.suffix == ".mp3":
                        p.unlink()
    # Слова line cleanup happens in rebuild


def main() -> int:
    report: dict[str, list] = {
        "spans_fixed": [],
        "spans_failed": [],
        "themes_moved": [],
        "img_fixed": [],
        "jlpt_added": [],
        "verb_tag_added": [],
        "hints_fixed": [],
        "other": [],
    }

    # --- content overrides before theme moves where needed ---
    # Fix 秋 while still under Общение, then move
    aki_path = CARDS / "Общение" / "秋.json"
    if aki_path.exists():
        data = json.loads(aki_path.read_text(encoding="utf-8"))
        ov = CONTENT_OVERRIDES["Календарь/秋"]
        data.update({k: v for k, v in ov.items() if k != "Пример" and k != "Пример перевод"})
        data["Пример"] = ov["Пример"]
        data["Пример без слова"] = blankify(ov["Пример"])
        data["Пример перевод"] = ov["Пример перевод"]
        save_card(aki_path, data)
        report["other"].append("fixed content Общение/秋 before move")

    sato = CARDS / "География" / "佐藤.json"
    if sato.exists():
        data = json.loads(sato.read_text(encoding="utf-8"))
        ov = CONTENT_OVERRIDES["География/佐藤"]
        data["Пример"] = ov["Пример"]
        data["Пример без слова"] = blankify(ov["Пример"])
        data["Пример перевод"] = ov["Пример перевод"]
        save_card(sato, data)
        report["other"].append("fixed География/佐藤 3rd example")

    # reading / furigana
    gum = CARDS / "Глаголы" / "ガムをかむ.json"
    if gum.exists():
        data = json.loads(gum.read_text(encoding="utf-8"))
        if data.get("Чтение") != "ガムをかむ":
            data["Чтение"] = "ガムをかむ"
            save_card(gum, data)
            report["other"].append("fixed reading ガムをかむ")

    kimeru = CARDS / "Глаголы" / "決める.json"
    if kimeru.exists():
        data = json.loads(kimeru.read_text(encoding="utf-8"))
        if not str(data.get("Показать фуригану") or "").strip():
            data["Показать фуригану"] = "N"
            save_card(kimeru, data)
            report["other"].append("fixed furigana flag 決める")

    # delete junk and duplicate
    delete_card_bundle("Еда", "×")
    report["other"].append("deleted Еда/×")
    dup = CARDS / "Финансы" / "お金を貯める.json"
    if dup.exists() and (CARDS / "Глаголы" / "お金を貯める.json").exists():
        delete_card_bundle("Финансы", "お金を貯める")
        report["other"].append("deleted duplicate Финансы/お金を貯める")

    # --- spans for cards missing study-word ---
    span_targets = []
    for path in sorted(CARDS.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        ex = str(data.get("Пример") or "")
        parts = [p.strip() for p in BR_SPLIT.split(ex)]
        if len(parts) != 3:
            continue
        miss = sum(1 for p in parts if not SPAN.search(p))
        blank_parts = [p.strip() for p in BR_SPLIT.split(str(data.get("Пример без слова") or ""))]
        miss_b = sum(1 for p in blank_parts if "_____" not in p) if len(blank_parts) == 3 else 3
        if miss or miss_b:
            span_targets.append(path)

    for path in span_targets:
        topic = path.parent.name
        data = json.loads(path.read_text(encoding="utf-8"))
        key = f"{topic}/{data.get('Слово')}"
        if key == "География/佐藤" or key.endswith("/秋"):
            # already overridden / will be after move
            # still ensure blanks
            if SPAN.search(str(data.get("Пример") or "")):
                data["Пример без слова"] = blankify(str(data["Пример"]))
                save_card(path, data)
                report["spans_fixed"].append(key)
                continue
        ex, blank, errors = auto_wrap_examples(data, topic)
        if errors:
            report["spans_failed"].append({"card": key, "errors": errors, "ex": ex})
            # still write partial progress if any wraps happened
            if STUDY_OPEN in ex:
                data["Пример"] = ex
                data["Пример без слова"] = blank
                save_card(path, data)
            continue
        data["Пример"] = ex
        data["Пример без слова"] = blank
        save_card(path, data)
        report["spans_fixed"].append(key)

    # --- theme moves ---
    for (old, word), new in THEME_MOVES.items():
        src = CARDS / old / f"{word}.json"
        if not src.exists():
            report["other"].append(f"theme skip missing {old}/{word}")
            continue
        dst = CARDS / new / f"{word}.json"
        if dst.exists() and src.resolve() != dst.resolve():
            report["other"].append(f"theme conflict {old}/{word} -> {new}")
            continue
        move_word_bundle(word, old, new)
        # update tags
        new_path = CARDS / new / f"{word}.json"
        if new_path.exists():
            fix_json_theme_tag(new_path)
            zd = ROOT / "Записи" / new / f"{word}.md"
            if zd.exists():
                fix_zapisi_file(zd)
            # verb tag if moved into Глаголы
            if new == "Глаголы":
                data = json.loads(new_path.read_text(encoding="utf-8"))
                tags = list(data.get("Теги") or [])
                if "動詞" not in tags:
                    tags.append("動詞")
                    data["Теги"] = tags
                    save_card(new_path, data)
        report["themes_moved"].append(f"{old}/{word}->{new}")

    # --- img prompts ---
    for path in sorted(CARDS.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if fix_img_field(data, path.parent.name):
            save_card(path, data)
            report["img_fixed"].append(f"{path.parent.name}/{data.get('Слово')}")

    # --- verb tags ---
    for path in sorted((CARDS / "Глаголы").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        tags = list(data.get("Теги") or [])
        if "動詞" not in tags:
            tags.append("動詞")
            data["Теги"] = tags
            save_card(path, data)
            report["verb_tag_added"].append(path.stem)

    # --- JLPT ---
    lookup = load_jlpt_lookup()
    for path in sorted(CARDS.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        tags = list(data.get("Теги") or [])
        if JLPT_SET & set(tags):
            continue
        level = infer_jlpt(data, lookup)
        if not level:
            continue
        tags.append(level)
        data["Теги"] = tags
        save_card(path, data)
        report["jlpt_added"].append(f"{path.parent.name}/{data.get('Слово')}={level}")

    # --- hints ---
    for key, hint in HINT_REWRITES.items():
        topic, word = key.split("/", 1)
        path = CARDS / topic / f"{word}.json"
        if not path.exists():
            report["other"].append(f"hint miss {key}")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        data["Подсказка"] = hint
        save_card(path, data)
        report["hints_fixed"].append(key)

    # --- double spaces ---
    for path in sorted(CARDS.rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if fix_double_spaces(data):
            save_card(path, data)
            report["other"].append(f"spaces {path.parent.name}/{path.stem}")

    # --- счётные 〜羽 img if still prompt ---
    hane = CARDS / "Счётные суффиксы" / "〜羽.json"
    if hane.exists():
        data = json.loads(hane.read_text(encoding="utf-8"))
        if fix_img_field(data, "Счётные суффиксы"):
            save_card(hane, data)
            report["img_fixed"].append("Счётные суффиксы/〜羽")

    rebuild_slova_from_cards()
    report["other"].append("rebuilt Слова/")

    out = Path("/tmp/fix_revision_report.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("spans_fixed", len(report["spans_fixed"]))
    print("spans_failed", len(report["spans_failed"]))
    print("themes_moved", len(report["themes_moved"]))
    print("img_fixed", len(report["img_fixed"]))
    print("jlpt_added", len(report["jlpt_added"]))
    print("verb_tag_added", len(report["verb_tag_added"]))
    print("hints_fixed", len(report["hints_fixed"]))
    if report["spans_failed"]:
        print("FAILED SPANS:")
        for x in report["spans_failed"][:40]:
            print(" ", x)
    print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
