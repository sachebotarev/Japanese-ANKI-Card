#!/usr/bin/env python3
"""Карточки длительностей, сумм и количеств из Basic Kanji Books."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = {x["word"]: x for x in json.loads((ROOT / "docs/basic-kanji-books-missing-tango-2026-10-01.json").read_text())}
KANJI = json.loads((ROOT / "docs/basic-kanji-books-kanji-meanings-ru.json").read_text())

DURATIONS = {
    "一年": "один год", "二年": "два года", "三年": "три года",
    "四年": "четыре года", "五年": "пять лет", "六年": "шесть лет",
    "七年": "семь лет", "八年": "восемь лет", "十年": "десять лет",
    "一か月": "один месяц", "一週間": "одну неделю",
}
MONEY = {
    "百円": "сто иен", "千円": "тысячу иен",
    "五千円": "пять тысяч иен", "一万円": "десять тысяч иен",
}
BARE = {
    "二百": "двести", "三百": "триста", "六百": "шестьсот",
    "八百": "восемьсот", "九百": "девятьсот", "三千": "три тысячи",
}
FRACTIONS = {
    "二分の一": "половину", "三分の一": "треть", "四分の三": "три четверти",
}
BOTTLES = {"一本": "одна бутылка", "二本": "две бутылки", "三本": "три бутылки"}


def card(word, translation, topic, hint, jp, ru, notes, level="N5"):
    if word not in SOURCE:
        return None
    assert len(jp) == len(ru) == 3
    assert all(s.count("{w}") == 1 and s.endswith("。") for s in jp)
    chars = list(dict.fromkeys(re.findall(r"[一-龯]", word)))
    breakdown = "; ".join(f"{c} — {KANJI[c]['ru']}" for c in chars)
    return {
        "Слово": word, "Перевод": translation, "Чтение": SOURCE[word]["reading"],
        "Подсказка": hint,
        "Пример": "<br>".join(s.replace("{w}", f"<span class='study-word'>{word}</span>") for s in jp),
        "Пример без слова": "<br>".join(s.replace("{w}", "_____") for s in jp),
        "Пример перевод": "<br>".join(ru),
        "Картинка": ("Anime illustration, square 1:1, 512x512. "
                     f"Scene: {ru[2]} Central visual focus: {translation}. "
                     "No text, no letters, no signs, no watermark."),
        "Произношение": "", "Заметки": notes, "Кандзи-разбор": breakdown,
        "Показать фуригану": "N", "Теги": [topic, "名詞", level, *SOURCE[word]["tags"]],
    }


def build_cards():
    cards = []
    for word, duration in DURATIONS.items():
        cards.append(card(word, duration, "Календарь", "Подумайте о промежутке между двумя датами.",
                          ["私は{w}日本語を勉強しました。", "友達は{w}日本に住んでいます。",
                           "私は{w}日本語を勉強したので、前よりよく話せるようになりました。"],
                          [f"Я изучал японский {duration}.", f"Мой друг живёт в Японии уже {duration}.",
                           f"Поскольку я изучал японский {duration}, я научился говорить лучше, чем раньше."],
                          "Длительность с числительным и единицей времени. После такой группы частицу длительности обычно не ставят."))
    for word, amount in MONEY.items():
        cards.append(card(word, amount, "Финансы", "Представьте цену на ценнике или сумму в кошельке.",
                          ["この本は{w}です。", "昨日、{w}の本を買いました。",
                           "この本が{w}だったので、買って、友達に見せました。"],
                          [f"Эта книга стоит {amount}.", f"Вчера я купил книгу за {amount}.",
                           f"Так как эта книга стоила {amount}, я купил её и показал другу."],
                          "Сумма с 円 — денежной единицей Японии. В ценах после суммы часто ставится です."))
    for word, number in BARE.items():
        cards.append(card(word, number, "Счётные суффиксы", "Представьте подсчёт коробок на складе.",
                          ["箱が{w}個あります。", "この倉庫には箱が{w}個あります。",
                           "箱が{w}個あったので、数を確認して、紙に書きました。"],
                          [f"Есть {number} коробок.", f"На этом складе {number} коробок.",
                           f"Поскольку коробок было {number}, я проверил количество и записал его на бумаге."],
                          "Числительное сочетается со счётным суффиксом 個 для отдельных предметов."))
    for word, part in FRACTIONS.items():
        cards.append(card(word, part, "Счётные суффиксы", "Вспомните, как разделить пирог на равные части.",
                          ["ケーキの{w}を食べました。", "弟はケーキの{w}を食べました。",
                           "ケーキの{w}を食べたので、残りは弟にあげました。"],
                          [f"Я съел {part} пирога.", f"Младший брат съел {part} пирога.",
                           f"Так как я съел {part} пирога, оставшееся отдал младшему брату."],
                          "Дробь читается в порядке: знаменатель + 分の + числитель.", level="N4"))
    for word, bottles in BOTTLES.items():
        if word == "一本":
            jp3 = "水を{w}買ったので、友達と分けて飲みました。"
            ru3 = "Я купил одну бутылку воды, поэтому мы с другом выпили её вместе."
        else:
            jp3 = "水を{w}買ったので、一本を友達にあげて、残りを家に持って帰りました。"
            ru3 = f"Я купил воду, всего {bottles}, поэтому одну бутылку отдал другу, а остальные отнёс домой."
        cards.append(card(word, bottles, "Счётные суффиксы", "Подумайте о длинных предметах на полке.",
                          ["水を{w}買いました。", "昨日、水を{w}買いました。", jp3],
                          [f"Я купил воду: {bottles}.", f"Вчера я купил воду: {bottles}.",
                           ru3],
                          "Счётный суффикс 本 используют для длинных предметов и бутылок. Чтение меняется после некоторых чисел."))
    return [c for c in cards if c]


def main():
    cards = build_cards()
    for c in cards:
        word, topic = c["Слово"], c["Теги"][0]
        out = ROOT / "Карточки" / topic / f"{word}.json"
        if out.exists():
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(c, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        words = ROOT / "Слова" / topic
        lines = set(words.read_text(encoding="utf-8").splitlines()) if words.exists() else set()
        lines.add(word)
        words.write_text("\n".join(sorted(x.strip() for x in lines if x.strip())) + "\n", encoding="utf-8")
    print("Карточек в группе:", len(cards))


if __name__ == "__main__":
    main()
