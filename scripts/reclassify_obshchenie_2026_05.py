#!/usr/bin/env python3
"""
Переклассификация карточек из Общение по таксономии (май 2026).

  python3 scripts/reclassify_obshchenie_2026_05.py
  python3 scripts/reclassify_obshchenie_2026_05.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = "Общение"

sys.path.insert(0, str(ROOT / "scripts"))
from migrate_themes_2026_05 import (  # noqa: E402
    fix_json_theme_tag,
    fix_zapisi_file,
    move_word_bundle,
    rebuild_slova_from_cards,
)

# Оставляем в Общение: приветствия, формулы вежливости, местоимения, представления, речевые маркеры.
STAY: frozenset[str] = frozenset(
    {
        "〜について",
        "あなた",
        "あのう",
        "あの人",
        "あの方",
        "いいと思う",
        "いらっしゃい",
        "いらっしゃいませ",
        "お先に失礼します",
        "お先に失礼す",
        "お腹がすきます",
        "お邪魔します",
        "お邪魔す",
        "から来ました",
        "こちらこそ",
        "こちらは〜さんです",
        "じゃ",
        "すみません",
        "そうですか",
        "そうですね。",
        "そちら",
        "どういたしまして。",
        "どうも",
        "どうもありがとうございました。",
        "なるほど",
        "ほら",
        "ようこそ",
        "人",
        "他",
        "会話",
        "伝言",
        "出身",
        "初めまして",
        "名前",
        "喉が渇きます",
        "大変ですね",
        "失礼します",
        "実は将来",
        "少々",
        "少々お待ちください",
        "強いと思う",
        "彼",
        "彼ち",
        "彼女",
        "招待",
        "挨拶",
        "私",
        "答え",
        "約束",
        "紹介",
        "自分",
        "良いですね",
        "言葉",
        "話",
        "質問",
    }
)

# Явные переносы (слово -> тема). Остальное классифицируется эвристиками ниже.
EXPLICIT: dict[str, str] = {
    "お腹": "Анатомия",
    "喉": "Анатомия",
    "手": "Анатомия",
    "お皿": "Еда",
    "お菓子": "Еда",
    "きゅうり": "Еда",
    "ご飯": "Еда",
    "さつまいも": "Еда",
    "じゃがいも": "Еда",
    "なす": "Еда",
    "はし": "Еда",
    "ほうれん草": "Еда",
    "まめ": "Еда",
    "みかん": "Еда",
    "人参": "Еда",
    "味": "Еда",
    "塩": "Еда",
    "夕食": "Еда",
    "料理": "Еда",
    "油": "Еда",
    "注文": "Еда",
    "玉葱": "Еда",
    "生": "Еда",
    "白菜": "Еда",
    "鍋": "Еда",
    "食べ物": "Еда",
    "食事": "Еда",
    "食器": "Еда",
    "お金": "Финансы",
    "経済": "Финансы",
    "お婆さん": "Семья",
    "お子さん": "Семья",
    "お爺さん": "Семья",
    "ご両親": "Семья",
    "ご主人": "Семья",
    "ご兄弟": "Семья",
    "一人っ子": "Семья",
    "両親": "Семья",
    "双子": "Семья",
    "叔母": "Семья",
    "叔母さん": "Семья",
    "叔父": "Семья",
    "叔父さん": "Семья",
    "妹さん": "Семья",
    "姪": "Семья",
    "娘": "Семья",
    "娘さん": "Семья",
    "子供": "Семья",
    "孫": "Семья",
    "少女": "Семья",
    "少年": "Семья",
    "弟さん": "Семья",
    "従兄弟": "Семья",
    "息子": "Семья",
    "息子さん": "Семья",
    "甥": "Семья",
    "祖母": "Семья",
    "祖父": "Семья",
    "親戚": "Семья",
    "いす": "Жилище",
    "上": "Жилище",
    "下": "Жилище",
    "冷蔵庫": "Жилище",
    "前": "Жилище",
    "右": "Жилище",
    "外": "Жилище",
    "家具": "Жилище",
    "寮": "Жилище",
    "左": "Жилище",
    "箱": "Жилище",
    "籠": "Жилище",
    "袋": "Жилище",
    "隅": "Жилище",
    "階": "Жилище",
    "お守り": "Традиции",
    "お花見": "Традиции",
    "教会": "Традиции",
    "看護師": "Профессии",
    "警官": "Профессии",
    "切手": "Почта",
    "封筒": "Почта",
    "年賀状": "Почта",
    "葉書": "Почta",
}

# fix typo
EXPLICIT["葉書"] = "Почта"

HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("Еда", ("еда", "ест", "блюд", "рис", "овощ", "фрукт", "сладост", "пищ", "напит", "кухн", "готов", "варён", "мяс", "рыб", "суп", "вкус", "соль", "ужин", "завтрак", "обед", "посуд", "тарел", "палочк")),
    ("Семья", ("семь", "родит", "брат", "сестр", "дед", "баб", "муж", "жена", "ребён", "дет", "супруг", "сын", "доч", "плем", "родствен", "тёт", "дяд", "внук", "близнец")),
    ("Финансы", ("деньг", "банк", "цен", "руб", "стоим", "эконом", "финанс", "скидк", "бесплат")),
    ("Работа", ("работ", "офис", "компани", "началь", "департ", "командиров", "дедлайн", "крайний срок")),
    ("Образование", ("школ", "учеб", "урок", "студ", "универс", "образован", "граммат", "литератур", "истори", "биолог", "инжен", "политик", "изобраз", "читател", "новичок", "задач", "упражн")),
    ("Медицина", ("боль", "врач", "лечен", "больниц", "здоров", "лекар", "апте", "болезн", "самочув", "пластыр", "обезбол", "глазн")),
    ("Транспорт", ("поезд", "автоб", "метро", "станц", "билет", "машин", "дорог", "транспорт", "самол", "аэропорт", "пассаж", "парков", "светофор", "автомоб")),
    ("Жилище", ("комнат", "дом", "кварт", "этаж", "двер", "окн", "мебел", "стул", "холодиль", "короб", "корзин", "мешок", "угол")),
    ("Быт", ("повседн", "быт", "жизнь", "образ жиз", "подготов", "опыт", "багаж", "игруш", "номер", "метод", "причин", "недостат")),
    ("Электроника", ("компьютер", "интернет", "телефон", "электрон", "микровол", "батар", "словар")),
    ("Эмоции", ("эмоц", "чувств", "мечт", "желан", "устал", "сон")),
    ("Спорт", ("спорт", "плаvan", "плаван", "футбол", "тенnis")),
    ("Торговля", ("магаз", "покуп", "продав", "товар", "распрод", "выпуск в прод")),
    ("География", ("стран", "город", "море", "океан", "префект", "район")),
    ("Природа", ("живот", "птиц", "цветок", "небо", "сакур", "слон", "коралл", "вулкан")),
    ("Погода", ("погод", "облач", "температ", "пасмур")),
    ("Право", ("полиц", "преступ", "закон")),
    ("Туризм", ("музей", "выставк", "ботанич")),
    ("Календарь", ("зима", "весн", "лето", "осен", "будущ", "прошл", "впервые", "канун", "следующ")),
    ("Канцелярия", ("бумаг", "ластик", "чернов", "ножниц", "конверт", "марк")),
    ("Одежда", ("одеж", "носк", "кольц", "космет", "цвет", "пугов")),
    ("Традиции", ("талисман", "оберег", "ханами", "церков")),
    ("Дружба", ("друг", "подруг")),
]

NA_ADJ_SUFFIX = ("な", "だめ", "ハンサム")
I_ADJ_WORDS = {
    "いい", "しょっぱい", "ちょうどいい", "低い", "優しい", "冷たい", "危ない", "古い", "同じ", "塩辛い",
    "多い", "大きい", "安い", "小さい", "弱い", "強い", "忙しい", "悪い", "新しい", "暑い", "柔らかい",
    "楽しい", "汚い", "濃い", "甘い", "痛い", "白い", "美味しい", "肌寒い", "苦い", "薄い", "赤い",
    "辛い", "遠い", "酢っぽい", "難しい", "青い", "面白い", "高い",
}
NA_ADJ_WORDS = {
    "だめ", "ハンサム", "上手な", "下手な", "人気な", "基本的な", "大変な", "奇妙な", "嫌いな", "暇な",
    "残念な", "簡単な", "素敵な",
}


def classify_word(word: str, data: dict) -> str:
    if word in STAY:
        return OLD
    if word in EXPLICIT:
        return EXPLICIT[word]
    tags = set(str(t) for t in (data.get("Теги") or []))
    tr = (str(data.get("Перевод") or "") + " " + str(data.get("Заметки") or "")).lower()

    if word in I_ADJ_WORDS or "形容詞" in tags and "な" not in str(tags):
        if word.endswith("い") or word in I_ADJ_WORDS:
            return "Прилагательные_い"
    if word in NA_ADJ_WORDS or word.endswith("な") or word in ("だめ", "ハンサム"):
        return "Прилагательные_な"

    if any(t in tags for t in ("動詞", "サ変動詞", "глагол")) or (
        (word.endswith("る") or word.endswith("ます") or word.endswith("す"))
        and word not in STAY
        and not word.endswith("な")
    ):
        if word in ("散歩",):
            return "Глаголы"
        if re.search(r"(する|ます|ない|て|た|る)$", word) and "名詞" not in tags:
            return "Глаголы"

    if "副詞" in tags or word in ("これから", "そして", "だけ", "もう少し", "中から", "以外", "外に", "多少", "大体", "早く", "歩いて", "色々", "近く"):
        return "Наречия"

    if word in ("疑問詞",):
        return "Вопросительные слова"
    if word in ("副詞", "名詞", "形容詞", "文型", "１から３の名前から", "例", "二行目", "初心者", "問題"):
        return "Образование"
    if any(w in tr for w in ("термин", "часть речи", "граммат")):
        return "Образование"

    for theme, keys in HINTS:
        if any(k in tr for k in keys):
            return theme

    if word.endswith("館") or word.endswith("博物"):
        return "Туризм"
    if word.endswith("口") and len(word) <= 3:
        return "Транспорт"

    return OLD


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src_dir = ROOT / "Карточки" / OLD
    cards = sorted(src_dir.glob("*.json"))
    moves: dict[str, str] = {}
    stay: list[str] = []

    for p in cards:
        data = json.loads(p.read_text(encoding="utf-8"))
        word = str(data.get("Слово", "")).strip()
        target = classify_word(word, data)
        if target == OLD:
            stay.append(word)
        else:
            dst = ROOT / "Карточки" / target / f"{word}.json"
            if dst.exists():
                print(f"[skip] {word}: уже есть в {target}", file=sys.stderr)
                stay.append(word)
                continue
            moves[word] = target

    print(f"Перенос: {len(moves)}, остаётся в {OLD}: {len(stay)}")

    if args.dry_run:
        from collections import Counter
        c = Counter(moves.values())
        for t, n in sorted(c.items()):
            print(f"  {t}: {n}")
        return 0

    for word, target in sorted(moves.items()):
        move_word_bundle(word, OLD, target)
        jp = ROOT / "Карточки" / target / f"{word}.json"
        fix_json_theme_tag(jp)
        md = ROOT / "Записи" / target / f"{word}.md"
        if md.exists():
            fix_zapisi_file(md)

    for jp in ROOT.glob("Карточки/**/*.json"):
        if jp.is_file():
            fix_json_theme_tag(jp)
    for md in ROOT.glob("Записи/**/*.md"):
        if md.is_file():
            fix_zapisi_file(md)

    rebuild_slova_from_cards()

    # обновить чеклист картинок
    missing_script = ROOT / "scripts" / "sync_anki_deck_to_json.py"
    if missing_script.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("sync_anki", missing_script)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.write_missing_images_md()

    report = ROOT / "docs" / "reclassify-obshchenie-report.md"
    lines = [f"# Переклассификация {OLD}", "", f"Перенесено: **{len(moves)}**.", f"Осталось в {OLD}: **{len(stay)}**.", ""]
    from collections import Counter
    c = Counter(moves.values())
    for t in sorted(c):
        lines.append(f"- {t}: {c[t]}")
    lines.append("")
    lines.append("## Остались в Общение")
    lines.append("")
    for w in sorted(stay):
        lines.append(f"- `{w}`")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Отчёт: {report.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
