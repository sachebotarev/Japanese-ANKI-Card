#!/usr/bin/env python3
"""Create Basic Kanji Books text cards with the authenticated cloud Codex model."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/basic-kanji-books-missing-tango-2026-10-01.json"
ERRORS = ROOT / "docs/basic-kanji-books-cloud-errors-2026-10-01.jsonl"
KANJI = json.loads((ROOT / "docs/basic-kanji-books-kanji-meanings-ru.json").read_text())
TOPICS = sorted(p.name for p in (ROOT / "Слова").iterdir() if p.is_file())
MODEL = "gpt-5.5"
ALIASES = {
    "子ども": "子供", "小人": "子供", "小さ": "小さい", "大き": "大きい",
    "何ですか。": "何ですか", "買物": "買い物",
}
NORMALIZE = {"結婚 する": "結婚する"}
SPAN = re.compile(r"<span class=['\"]study-word['\"]>([^<]+)</span>")


def existing_words() -> set[str]:
    out = set()
    for path in (ROOT / "Карточки").glob("*/*.json"):
        try:
            out.add(json.loads(path.read_text())["Слово"])
        except (KeyError, ValueError):
            continue
    return out


def pending() -> list[dict]:
    existing = existing_words()
    seen = set()
    result = []
    for original in json.loads(SOURCE.read_text()):
        word = original["word"]
        if word in seen:
            continue
        seen.add(word)
        if word in existing or word in ALIASES and ALIASES[word] in existing or "～" in word:
            continue
        item = {**original, "word": NORMALIZE.get(word, word)}
        if item["word"] not in existing:
            result.append(item)
    return result


def schema(count: int) -> dict:
    card = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "word": {"type": "string"}, "translation": {"type": "string"},
            "hint": {"type": "string", "description": "Короткая русская мнемоника без ответа"},
            "topic": {"type": "string", "enum": TOPICS},
            "pos": {"type": "string", "enum": ["noun", "verb", "i_adjective", "na_adjective", "adverb", "other"]},
            "level": {"type": "string", "enum": ["N5", "N4", "N3", "N2", "N1"]},
            "conjugation": {"type": "string", "enum": ["", "五段", "一段", "不規則"]},
            "jp": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
            "ru": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
            "notes": {"type": "string", "description": "Одно или два предложения НА РУССКОМ языке о значении и употреблении"},
        },
        "required": ["word", "translation", "hint", "topic", "pos", "level", "conjugation", "jp", "ru", "notes"],
    }
    return {"type": "object", "additionalProperties": False,
            "properties": {"cards": {"type": "array", "items": card, "minItems": count, "maxItems": count}},
            "required": ["cards"]}


def prompt(items: list[dict]) -> str:
    source = [{"word": x["word"], "reading": x["reading"], "meaning_en": x["meaning_en"]} for x in items]
    return f"""Составь по одной качественной карточке японской лексики для КАЖДОГО элемента списка. Верни только JSON по заданной схеме, порядок сохрани.

Список: {json.dumps(source, ensure_ascii=False)}

Русский язык — для translation, hint, ru и notes. Не копируй английский перевод автоматически, проверь значение по японскому слову и чтению. Используй словарную форму в поле word строго как во входе. Правила:
1. topic — одна существующая папка из списка {', '.join(TOPICS)}. Глаголы всегда Глаголы, наречия Наречия, и/на-прилагательные в своих грамматических папках. Фамилии и географические имена — География. Существительные классифицируй по применению.
2. pos: noun / verb / i_adjective / na_adjective / adverb / other. У глагола conjugation 五段, 一段 или 不規則, у остальных пусто. level — разумный уровень JLPT (N5–N1).
3. hint — короткая мнемоника по-русски без прямого раскрытия слова или его русского перевода. notes — не более двух полезных предложений СТРОГО НА РУССКОМ; японские слова и частицы можно цитировать внутри русской фразы. Для глагола укажи типичную частицу и управление. Японские предложения в notes запрещены.
4. jp — ровно три ЕСТЕСТВЕННЫХ японских предложения. Первое — короткое N5, второе — чуть сложнее, но не выше N5, третье — с двумя связанными конструкциями до N4 включительно (например причина + последовательность действий). В каждом японском примере ровно один раз оберни изучаемое слово или естественную спрягаемую форму в <span class='study-word'>...</span>. Для существительного используй точное написание слова, а не его чтение. Для глагола правильно спрягай форму (分ける→分けて, а не 分けるて). Никаких пробелов между японскими словами. Каждое предложение заканчивай 。. Не используй метаязыковые примеры о написании слова.
5. ru — ровно три точных русских перевода соответствующих японских примеров. Не выдумывай фактов о сезонах, погоде, населении или истории. Проверь, что перевод и японское предложение совпадают по смыслу.
6. Если исходная заметка содержит личное имя, используй его как имя/фамилию, не приписывай ему конкретную профессию или биографию. Если значение многозначно, выбери наиболее частотный смысл источника и отрази его в примерах.
"""


def cloud(items: list[dict]) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="bk-cloud-") as tmp:
        schema_path = Path(tmp) / "schema.json"
        output_path = Path(tmp) / "output.json"
        schema_path.write_text(json.dumps(schema(items.__len__()), ensure_ascii=False))
        cmd = ["codex", "exec", "-m", MODEL, "--sandbox", "read-only", "--ephemeral",
               "--output-schema", str(schema_path), "--output-last-message", str(output_path), "-"]
        run = subprocess.run(cmd, input=prompt(items), text=True, cwd=ROOT,
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=300)
        if run.returncode:
            raise RuntimeError(run.stderr[-1500:])
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        return payload["cards"]


def validate(generated: list[dict], items: list[dict]) -> None:
    if len(generated) != len(items):
        raise ValueError("Количество карточек не совпало")
    for c, item in zip(generated, items):
        word = item["word"]
        if c["word"] != word:
            raise ValueError(f"Неверное слово: {c['word']} != {word}")
        if c["topic"] not in TOPICS or len(c["jp"]) != 3 or len(c["ru"]) != 3:
            raise ValueError(f"Неверная структура: {word}")
        expected = {"verb": "Глаголы", "adverb": "Наречия", "i_adjective": "Прилагательные_い", "na_adjective": "Прилагательные_な"}.get(c["pos"])
        if expected and c["topic"] != expected:
            raise ValueError(f"Неверная тема {word}: {c['topic']}")
        if c["pos"] == "verb" and c["conjugation"] not in {"五段", "一段", "不規則"}:
            raise ValueError(f"Нет спряжения: {word}")
        for jp, ru in zip(c["jp"], c["ru"]):
            spans = SPAN.findall(jp)
            if len(spans) != 1 or not jp.endswith("。") or not ru.strip():
                raise ValueError(f"Неверный пример {word}: {jp}")
            if c["pos"] in {"noun", "adverb", "other"} and spans[0] != word:
                raise ValueError(f"Не точная форма {word}: {spans[0]}")
        if any(not str(c[k]).strip() for k in ("translation", "hint", "notes")):
            raise ValueError(f"Пустое поле: {word}")
        if sum("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in c["notes"]) < 10 or "。" in c["notes"]:
            raise ValueError(f"Заметки должны быть по-русски: {word}")


def as_card(c: dict, item: dict) -> dict:
    word = c["word"]
    chars = list(dict.fromkeys(re.findall(r"[一-龯]", word)))
    breakdown = "; ".join(f"{ch} — {KANJI[ch]['ru']}" for ch in chars) if chars else "Кандзи нет."
    tags = [c["topic"]]
    if c["pos"] == "noun": tags.append("名詞")
    if c["pos"] == "verb": tags.extend(["動詞", f"動詞・{c['conjugation']}"])
    if c["pos"] == "i_adjective": tags.append("イ形容詞")
    if c["pos"] == "na_adjective": tags.append("ナ形容詞")
    tags.extend([c["level"], *item["tags"]])
    blanks = [SPAN.sub("_____", x) for x in c["jp"]]
    return {
        "Слово": word, "Перевод": c["translation"], "Чтение": item["reading"],
        "Подсказка": c["hint"], "Пример": "<br>".join(c["jp"]),
        "Пример без слова": "<br>".join(blanks), "Пример перевод": "<br>".join(c["ru"]),
        "Картинка": ("Anime illustration, square 1:1, 512x512. "
                     f"Scene: {c['ru'][2]} Visual focus: {c['translation']}. "
                     "No text, no letters, no signs, no watermark."),
        "Произношение": "", "Заметки": c["notes"], "Кандзи-разбор": breakdown,
        "Показать фуригану": "N", "Теги": list(dict.fromkeys(tags)),
    }


def write(cards: list[dict]) -> None:
    words_by_topic = {}
    for c in cards:
        topic, word = c["Теги"][0], c["Слово"]
        path = ROOT / "Карточки" / topic / f"{word}.json"
        if path.exists():
            raise FileExistsError(path)
    for c in cards:
        topic, word = c["Теги"][0], c["Слово"]
        path = ROOT / "Карточки" / topic / f"{word}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n")
        words_by_topic.setdefault(topic, set()).add(word)
    for topic, new in words_by_topic.items():
        path = ROOT / "Слова" / topic
        old = set(path.read_text().splitlines()) if path.exists() else set()
        path.write_text("\n".join(sorted({x.strip() for x in old | new if x.strip()})) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()
    items = pending()
    if args.limit:
        items = items[:args.limit]
    print(f"К обработке: {len(items)}", flush=True)
    done = 0

    def process(batch: list[dict]) -> None:
        nonlocal done
        last_error = ""
        for _ in range(2):
            try:
                generated = cloud(batch)
                validate(generated, batch)
                write([as_card(c, item) for c, item in zip(generated, batch)])
                done += len(batch)
                print(f"Готово: {done}/{len(items)} — {batch[0]['word']} … {batch[-1]['word']}", flush=True)
                return
            except Exception as exc:
                last_error = str(exc)
        if len(batch) > 1:
            mid = len(batch) // 2
            process(batch[:mid])
            process(batch[mid:])
        else:
            with ERRORS.open("a", encoding="utf-8") as out:
                out.write(json.dumps({"word": batch[0]["word"], "error": last_error}, ensure_ascii=False) + "\n")
            print(f"ОШИБКА: {batch[0]['word']}: {last_error}", flush=True)

    for start in range(0, len(items), args.batch_size):
        process(items[start:start + args.batch_size])


if __name__ == "__main__":
    main()
