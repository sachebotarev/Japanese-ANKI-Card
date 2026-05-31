#!/usr/bin/env python3
"""
Импорт недостающих заметок колоды «Японские слова» из AnkiConnect в Карточки/<тема>/<Слово>.json.

- Приводит примеры к формату «3 × <br>» (см. docs/cards-spec.md).
- Поле «Картинка» — текстовый промпт (без генерации файлов).
- Обновляет Слова/<тема> и docs/next-pass-cards-missing-images.md.

  python3 scripts/sync_anki_deck_to_json.py
  python3 scripts/sync_anki_deck_to_json.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "Карточки"
WORDS = ROOT / "Слова"
IMAGES = ROOT / "Картинки"
REPORT = ROOT / "docs" / "anki-import-report.md"
MISSING_IMG = ROOT / "docs" / "next-pass-cards-missing-images.md"
DECK = "Японские слова"

HTML_TAG = re.compile(r"<[^>]+>")
BR_SPLIT = re.compile(r"<br\s*/?>", re.IGNORECASE)
SPAN = re.compile(
    r"<span\s+class=['\"]study-word['\"]>\s*([^<]*?)\s*</span>",
    re.IGNORECASE,
)
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")

POS_TO_TOPIC = {
    "動詞": "Глаголы",
    "動詞・五段": "Глаголы",
    "動詞・一段": "Глаголы",
    "動詞・サ変": "Глаголы",
    "動詞・する": "Глаголы",
    "副詞": "Наречия",
    "形容詞・い": "Прилагательные_い",
    "形容動詞": "Прилагательные_な",
    "形容詞・な": "Прилагательные_な",
    "助数詞": "Счётные суффиксы",
}

NOUN_HINTS: dict[str, tuple[str, ...]] = {
    "Еда": ("еда", "ест", "пищ", "блюд", "рестор", "кухн", "напит", "чай", "кофе", "рис", "рыб", "мяс", "суп", "хлеб"),
    "Транспорт": ("поезд", "автоб", "метро", "станц", "билет", "машин", "дорог", "транспорт", "самол"),
    "Жилище": ("комнат", "дом", "кварт", "этаж", "ванн", "двер", "окн", "кухн"),
    "Образование": ("школ", "универс", "учеб", "урок", "экзам", "студ", "учит", "класс", "библиот"),
    "Работа": ("работ", "офис", "компани", "началь", "департ", "зарплат"),
    "Календарь": ("день", "недел", "месяц", "год", "время", "час", "утр", "вечер", "сегодня", "завтра"),
    "Медицина": ("боль", "врач", "лечен", "больниц", "здоров", "лекар"),
    "Спорт": ("спорт", "футбол", "тенnis", "теннис", "игр"),
    "Финансы": ("деньг", "банк", "цен", "стоим", "руб", "ен"),
    "Одежда": ("одеж", "рубаш", "брюк", "плать", "обув"),
    "География": ("стран", "город", "япон", "росси", "америк"),
    "Семья": ("семь", "родит", "отец", "мать", "брат", "сестр", "дет"),
    "Дружба": ("друг", "подруг"),
    "Электроника": ("компьютер", "интернет", "телефон", "электрон"),
    "Торговля": ("магаз", "покуп", "продав", "товар"),
    "Погода": ("погод", "дожд", "снег", "ветер", "жар", "холод"),
    "Традиции": ("праздн", "храм", "традиц", "обряд"),
    "Кинематограф": ("фильм", "кино", "актёр"),
    "Телевидение": ("телевиз", "радио", "програм"),
}

QUESTION_PREFIXES = (
    "どう", "何", "なに", "なん", "いつ", "どこ", "だれ", "誰", "どれ", "どの",
    "いくら", "いくつ", "なぜ", "どちら", "どっち", "おいくつ",
)


def invoke(url: str, action: str, **params):
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        body = json.loads(resp.read())
    if body.get("error"):
        raise RuntimeError(body["error"])
    return body.get("result")


def strip_html(text: str) -> str:
    text = re.sub(r"</div>\s*<div[^>]*>", "\n", text or "", flags=re.IGNORECASE)
    text = BR_SPLIT.sub("\n", text)
    text = HTML_TAG.sub("", text)
    return text.replace("&nbsp;", " ").replace("\r", "").strip()


def parse_parts(text: str) -> list[str]:
    parts = [p.strip() for p in strip_html(text).split("\n") if p.strip()]
    return parts


def pad_three(parts: list[str]) -> list[str]:
    if not parts:
        return ["", "", ""]
    while len(parts) < 3:
        parts.append(parts[-1])
    return parts[:3]


def masu_to_dict(word: str, tags: list[str]) -> str:
    """Грубая нормализация -ます в словарную форму для глаголов."""
    if word.endswith("します"):
        return word  # устойчивые выражения и する-глаголы оставляем как есть
    if not word.endswith("ます"):
        return word
    tagset = set(tags)
    stem = word[:-2]
    if "動詞・一段" in tagset or "一段" in tagset:
        return stem + "る"
    if "動詞・サ変" in tagset or "動詞・する" in tagset or word == "します":
        return "する" if word == "します" else word.replace("します", "する")
    # 五段: ...います -> ...う, ...きます -> ...く, ...
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
    return word


def clean_word(raw: str, tags: list[str], existing: set[str]) -> str:
    s = strip_html(raw)
    for sep in ("・", "／", "/", "、", ",", "，"):
        if sep in s:
            s = s.split(sep)[0].strip()
    s = re.sub(r"\s+", "", s)
    s = s.strip("~[]() ")
    s = re.sub(r"^\[お\]", "お", s)
    if s.endswith("ます"):
        dict_form = masu_to_dict(s, tags)
        if dict_form in existing:
            return ""
        s = dict_form
    elif any(t.startswith("動詞") for t in tags) or "глагол" in tags:
        if s in existing:
            return ""
    return s


def wrap_study(word: str, sentence: str) -> str:
    if SPAN.search(sentence):
        return sentence
    if word and word in sentence:
        return sentence.replace(word, f"<span class='study-word'>{word}</span>", 1)
    return sentence


def blankify(example_html: str) -> str:
    return SPAN.sub("_____", example_html)


def russian_prompt(third_ru: str) -> str:
    t = third_ru.replace("\n", " ").strip()
    if len(t) > 400:
        t = t[:397] + "…"
    return (
        "Иллюстрация учебная, 512×512, без японских подписей: "
        f"{t} Главный визуальный акцент — изучаемое слово/смысл карточки."
    )


def load_word_themes() -> dict[str, str]:
    out: dict[str, str] = {}
    for f in WORDS.iterdir():
        if not f.is_file():
            continue
        theme = f.name
        for ln in f.read_text(encoding="utf-8").splitlines():
            w = ln.strip()
            if w:
                out[w] = theme
    return out


def repo_words() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for p in CARDS.rglob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        w = str(d.get("Слово", "")).strip()
        if w:
            out[w] = p
    return out


def classify_topic(word: str, tags: list[str], translation: str, word_themes: dict[str, str]) -> str:
    folders = {p.name for p in CARDS.iterdir() if p.is_dir()}
    if word in word_themes:
        return word_themes[word]
    for t in tags:
        if t in folders:
            return t
    for t in tags:
        if t in POS_TO_TOPIC:
            return POS_TO_TOPIC[t]
    if any(t.startswith("動詞") for t in tags) or "глагол" in tags:
        return "Глаголы"
    if "副詞" in tags:
        return "Наречия"
    if any(word.startswith(p) for p in QUESTION_PREFIXES) or word.endswith("？"):
        return "Вопросительные слова"
    if "名詞" in tags or "名詞・頻度:10" in tags:
        tr = strip_html(translation).lower()
        for topic, hints in NOUN_HINTS.items():
            if any(h in tr for h in hints):
                return topic
        if "表現" in tags or "Genki" in tags:
            return "Общение"
        return "Общение"
    if "形容詞・い" in tags or "い-прилагательное" in tags:
        return "Прилагательные_い"
    if "な-прилагательное" in tags or "形容動詞" in tags:
        return "Прилагательные_な"
    if "表現" in tags or "Genki" in tags or "TRY!" in tags:
        return "Общение"
    return "Общение"


def merge_tags(topic: str, anki_tags: list[str]) -> list[str]:
    skip = {"leech", "marked", "Ангелина"}
    out: list[str] = []
    seen: set[str] = set()
    for t in [topic, *anki_tags]:
        t = str(t).strip()
        if not t or t in skip or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def has_local_image(topic: str, word: str) -> bool:
    d = IMAGES / topic
    for ext in IMG_EXT:
        if (d / f"{word}{ext}").is_file():
            return True
    return False


def build_json(note: dict, word_themes: dict[str, str], existing: dict[str, Path]) -> tuple[str, dict] | None:
    fields = {k: v.get("value", "") for k, v in note.get("fields", {}).items()}
    tags = note.get("tags") or []
    raw_word = fields.get("Слово", "")
    word = clean_word(raw_word, tags, set(existing.keys()))
    if not word:
        return None

    topic = classify_topic(word, tags, fields.get("Перевод", ""), word_themes)
    jp_parts = pad_three(parse_parts(fields.get("Пример", "")))
    ru_parts = pad_three(parse_parts(fields.get("Пример перевод", "")))

    ex_lines = [wrap_study(word, jp_parts[i]) for i in range(3)]
    example = "<br>".join(ex_lines)
    example_blank = blankify(example)
    example_ru = "<br>".join(ru_parts)

    furigana = fields.get("Показать фуригану", "N").strip() or "N"
    if furigana not in ("Y", "N"):
        furigana = "N"

    data = {
        "Слово": word,
        "Чтение": strip_html(fields.get("Чтение", "")) or word,
        "Перевод": strip_html(fields.get("Перевод", "")),
        "Подсказка": strip_html(fields.get("Подсказка", "")),
        "Пример": example,
        "Пример без слова": example_blank,
        "Пример перевод": example_ru,
        "Картинка": russian_prompt(ru_parts[2]),
        "Произношение": "",
        "Заметки": strip_html(fields.get("Заметки", "")),
        "Кандзи-разбор": strip_html(fields.get("Кандзи-разбор", "")),
        "Показать фуригану": furigana,
        "Теги": merge_tags(topic, tags),
    }
    return topic, data


def update_word_file(topic: str, word: str) -> None:
    path = WORDS / topic
    lines: list[str] = []
    if path.is_file():
        lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if word not in lines:
        lines.append(word)
    lines = sorted(set(lines))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_missing_images_md() -> int:
    by_topic: dict[str, list[tuple[str, str]]] = defaultdict(list)
    total = 0
    for p in sorted(CARDS.rglob("*.json")):
        rel = p.relative_to(CARDS)
        topic = rel.parts[0]
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        word = str(d.get("Слово", "")).strip()
        if not word:
            continue
        if has_local_image(topic, word):
            continue
        by_topic[topic].append((word, f"Карточки/{topic}/{word}.json"))
        total += 1

    lines = [
        "# Карточки без локальной картинки",
        "",
        f"Осталось без картинки: **{total}**.",
        "",
        "Список сделан как рабочий чеклист: после генерации картинки для слова можно заменить `[ ]` на `[x]` или удалить строку. "
        "Ожидаемый файл: `Картинки/<тема>/<Слово>.(png|jpg|jpeg|webp)`.",
        "",
    ]
    for topic in sorted(by_topic):
        lines.append(f"## {topic} ({len(by_topic[topic])})")
        lines.append("")
        for word, json_path in sorted(by_topic[topic]):
            lines.append(f"- [ ] `{word}` — `{json_path}`")
        lines.append("")

    MISSING_IMG.write_text("\n".join(lines), encoding="utf-8")
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--anki-connect-url",
        default=os.environ.get("ANKI_CONNECT_URL", "http://127.0.0.1:8765"),
    )
    args = ap.parse_args()

    try:
        invoke(args.anki_connect_url, "version")
    except (urllib.error.URLError, RuntimeError, OSError, TimeoutError) as exc:
        print(f"AnkiConnect недоступен: {exc}", file=sys.stderr)
        return 1

    existing = repo_words()
    word_themes = load_word_themes()
    nids = invoke(args.anki_connect_url, "findNotes", query=f'deck:"{DECK}"') or []

    created = skipped = errors = 0
    report_lines = ["# Импорт из Anki", ""]

    for i in range(0, len(nids), 250):
        chunk = nids[i : i + 250]
        for note in invoke(args.anki_connect_url, "notesInfo", notes=chunk):
            built = build_json(note, word_themes, existing)
            if not built:
                skipped += 1
                continue
            topic, data = built
            word = data["Слово"]
            if word in existing:
                continue
            out = CARDS / topic / f"{word}.json"
            if out.exists():
                skipped += 1
                continue
            if args.dry_run:
                print(f"[dry-run] {topic}/{word}.json")
                created += 1
                continue
            try:
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                update_word_file(topic, word)
                existing[word] = out
                created += 1
            except OSError as exc:
                errors += 1
                report_lines.append(f"- ERROR `{word}`: {exc}")

    if not args.dry_run:
        missing_img = write_missing_images_md()
        report_lines.extend(
            [
                f"- Создано JSON: **{created}**",
                f"- Пропущено: **{skipped}**",
                f"- Ошибок: **{errors}**",
                f"- В чеклисте без картинки: **{missing_img}**",
                "",
            ]
        )
        REPORT.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"created={created} skipped={skipped} errors={errors}" + (" (dry-run)" if args.dry_run else ""))
    if not args.dry_run:
        print(f"report: {REPORT.relative_to(ROOT)}")
        print(f"missing images: {MISSING_IMG.relative_to(ROOT)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
