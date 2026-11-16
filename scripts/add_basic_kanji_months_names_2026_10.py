#!/usr/bin/env python3
"""Проверенные шаблоны для месяцев и японских фамилий из Basic Kanji Books."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = {x["word"]: x for x in json.loads((ROOT / "docs/basic-kanji-books-missing-tango-2026-10-01.json").read_text())}
KANJI = json.loads((ROOT / "docs/basic-kanji-books-kanji-meanings-ru.json").read_text())

# месяц: именительный, предложный, подсказка
MONTHS = {
    "一月": ("январь", "январе", "первый месяц после новогодних праздников"),
    "二月": ("февраль", "феврале", "месяц перед мартом"),
    "三月": ("март", "марте", "месяц перед апрелем"),
    "四月": ("апрель", "апреле", "месяц после марта"),
    "五月": ("май", "мае", "месяц перед июнем"),
    "六月": ("июнь", "июне", "первый месяц лета"),
    "七月": ("июль", "июле", "месяц после июня"),
    "八月": ("август", "августе", "последний месяц лета"),
    "九月": ("сентябрь", "сентябре", "первый месяц осени"),
    "十月": ("октябрь", "октябре", "месяц перед ноябрём"),
    "十一月": ("ноябрь", "ноябре", "месяц после октября"),
    "十二月": ("декабрь", "декабре", "последний месяц года"),
}

NAMES = {
    "金田": "Канеда", "木村": "Кимура", "田中": "Танака",
    "山田": "Ямада", "山下": "Ямасита", "山川": "Ямакава",
    "土田": "Цутида", "小林": "Кобаяси", "山本": "Ямамото",
    "竹田": "Такэда", "糸山": "Итояма", "石川": "Исикава",
    "高橋": "Такахаси",
}


def make(word, translation, topic, hint, jp, ru, tags, notes):
    source = SOURCE[word]
    assert len(jp) == len(ru) == 3
    for s in jp:
        assert s.count("{w}") == 1 and s.endswith("。")
    chars = list(dict.fromkeys(re.findall(r"[一-龯]", word)))
    breakdown = "; ".join(f"{c} — {KANJI[c]['ru']}" for c in chars)
    return {
        "Слово": word,
        "Перевод": translation,
        "Чтение": source["reading"],
        "Подсказка": hint,
        "Пример": "<br>".join(s.replace("{w}", f"<span class='study-word'>{word}</span>") for s in jp),
        "Пример без слова": "<br>".join(s.replace("{w}", "_____") for s in jp),
        "Пример перевод": "<br>".join(ru),
        "Картинка": ("Anime illustration, square 1:1, 512x512. "
                     f"Scene: {ru[2]} Central visual focus: {translation}. "
                     "No text, no letters, no signs, no watermark."),
        "Произношение": "",
        "Заметки": notes,
        "Кандзи-разбор": breakdown,
        "Показать фуригану": "N",
        "Теги": [topic, *tags, *source["tags"]],
    }


def main():
    cards = []
    for word, (nom, prep, hint) in MONTHS.items():
        if word not in SOURCE:
            continue
        number = list(MONTHS).index(word) + 1
        jp = ["私は{w}に旅行します。", "来年の{w}には試験があります。", "来年の{w}に旅行できるように、今からお金をためています。"]
        ru = [f"Я отправлюсь в путешествие в {prep}.",
              f"В {prep} следующего года у меня будет экзамен.",
              f"Я уже сейчас коплю деньги, чтобы в {prep} следующего года поехать в путешествие."]
        cards.append(make(word, nom, "Календарь", f"Это {hint}.", jp, ru,
                          ["名詞", "N5"], f"Название {number}-го месяца года. Для указания времени действия употребляется частица に."))
    for word, ru_name in NAMES.items():
        if word not in SOURCE:
            continue
        jp = ["{w}さんが来ました。", "{w}さんは私の友達です。", "{w}さんが来る前に、部屋を片づけて、お茶を用意しました。"]
        ru = [f"Пришёл человек по фамилии {ru_name}.",
              f"Мой друг носит фамилию {ru_name}.",
              f"Перед приходом гостя по фамилии {ru_name} я убрал комнату и приготовил чай."]
        chars = [KANJI[c]["ru"].split(",")[0] for c in word]
        hint = f"Представьте фамилию, составленную из образов: {chars[0]} и {chars[1]}."
        cards.append(make(word, ru_name, "География", hint, jp, ru,
                          ["人名", "名詞", "N5"], "Японская фамилия. さん — вежливое обращение после имени или фамилии."))
    for card in cards:
        topic, word = card["Теги"][0], card["Слово"]
        out = ROOT / "Карточки" / topic / f"{word}.json"
        if out.exists():
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        words = ROOT / "Слова" / topic
        lines = set(words.read_text(encoding="utf-8").splitlines()) if words.exists() else set()
        lines.add(word)
        words.write_text("\n".join(sorted(x.strip() for x in lines if x.strip())) + "\n", encoding="utf-8")
    print("Карточек в проверенной группе:", len(cards))


if __name__ == "__main__":
    main()
