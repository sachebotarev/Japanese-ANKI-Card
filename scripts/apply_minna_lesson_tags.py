#!/usr/bin/env python3
"""
Добавляет в JSON-карточки тег урока Minna no Nihongo (формат см. docs/cards-spec.md)
или тег «みんな-教材外» для лексики вне учебника.

Номера уроков для слов из тегом «みんなの日本語» заданы вручную по типичному
расположению лексики в みんなの日本語初級 I / частично II; при необходимости поправьте словарь.

Использование:
  python3 scripts/apply_minna_lesson_tags.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS = ROOT / "Карточки"

# Словарь формы: голова записи карточки «Слово» -> (том «I»|«II», номер урока в этом томе)
# Источник: общеизвестное расположение тем в Minna Shokyu (初級); отдельные пункты можно уточнить под ваше издание.
MINNA_LESSON_BY_WORD: dict[str, tuple[str, int]] = {
    # L1–3
    "友だち": ("I", 1),
    "名前": ("I", 1),
    # L4 время
    "〜分": ("I", 4),
    "〜秒": ("I", 4),
    "時間": ("I", 4),
    "〜時間": ("I", 4),
    "〜日": ("I", 4),
    # L5 / передвижение и быт
    "来る": ("I", 5),
    "帰る": ("I", 5),
    # L6 (~ます базовые действия питание)
    "食べる": ("I", 6),
    "飲む": ("I", 6),
    "〜か月": ("I", 6),
    # L7 (〜ます доп., чтение-письмо-слух-речь)
    "読む": ("I", 7),
    "書く": ("I", 7),
    "聞く": ("I", 7),
    "話す": ("I", 7),
    "宿題": ("I", 7),
    # L4 утро/режим vs L5 образование часто смежны; базовые «встать-сон» связаны с L4
    "起きる": ("I", 4),
    # L8 давать–получать, покупки
    "買う": ("I", 8),
    "貸す": ("I", 8),
    # L9 вещи, количество 〜つ
    "〜つ": ("I", 9),
    "きれい": ("I", 9),
    # L10 люди
    "〜人": ("I", 10),
    # L11 います／あります, места и характеристика
    "好き": ("I", 11),
    "嫌い": ("I", 11),
    "近い": ("I", 11),
    "静か": ("I", 11),
    "元気": ("I", 11),
    "〜枚": ("I", 11),
    "〜冊": ("I", 11),
    "〜個": ("I", 11),
    "〜杯": ("I", 11),
    "〜本": ("I", 11),
    # L12 погода, самочувствие, степени
    "寒い": ("I", 12),
    "大丈夫": ("I", 12),
    "大変": ("I", 12),
    "〜階": ("I", 12),
    "止める": ("I", 12),
    "降る": ("I", 12),
    # L13 «что делать»: открыть/выключить и т.п.
    "開く": ("I", 13),
    "消す": ("I", 13),
    # L14 один вместе, частота, длительность
    "一緒": ("I", 14),
    "〜回": ("I", 14),
    "〜週間": ("I", 14),
    "持つ": ("I", 14),
    "決める": ("I", 14),
    "仕事": ("I", 14),
    # L15 описание действий окружения (座る／立つ／дверь)
    "座る": ("I", 15),
    "立つ": ("I", 15),
    "開ける": ("I", 15),
    "閉める": ("I", 15),
    "見せる": ("I", 15),
    "閉まる": ("I", 15),
    # L16 указания, давление на кнопку и др.
    "押す": ("I", 16),
    "待つ": ("I", 16),
    "〜番": ("I", 16),
    "早い": ("I", 16),
    # L17 описание качеств, торопиться
    "急ぐ": ("I", 17),
    "黒い": ("I", 17),
    "〜年": ("I", 17),
    "〜歳": ("I", 5),
    # L18 внешность, восприятие
    "短い": ("I", 18),
    "長い": ("I", 18),
    "若い": ("I", 18),
    "撮る": ("I", 18),
    "考える": ("I", 18),
    "明るい": ("I", 18),
    # L19 частота, мнение
    "ときどき": ("I", 19),
    "上手": ("I", 19),
    "下手": ("I", 19),
    # L20 просьбы, формальный стиль, полезность
    "教える": ("I", 20),
    "便利": ("I", 20),
    "有名": ("I", 20),
    "〜台": ("I", 20),
    "〜名": ("I", 20),
    # L21 помощь и похожее
    "手伝う": ("I", 21),
    "疲れる": ("I", 21),
    "〜匹": ("I", 21),
    "〜頭": ("I", 21),
    "被る": ("I", 17),
    # L22 дорога, счёт одёжды/мест
    "曲がる": ("I", 22),
    "謝る": ("I", 22),
    "頼む": ("I", 22),
    "〜か所": ("I", 22),
    "〜軒": ("I", 22),
    "〜着": ("I", 22),
    "〜足": ("I", 22),
    # L23 путешествия
    "〜泊": ("I", 23),
    # второй том (номер урока — в оглавлении 初級II)
    "進める": ("II", 8),
    "聞こえる": ("II", 12),
    "〜件": ("II", 3),
    "〜通": ("II", 6),
    "〜羽": ("II", 21),
}

OUTSIDE_TAG = "みんな-教材外"

# Удалять при перерасчёте, если меняют урок или тип
STRIP_TAG_RE = re.compile(r"^(みんな初級(?:I|II)-第\d{2}課|みんな-教材外)$")


def lesson_tag(vol: str, lesson: int) -> str:
    vol_label = "初級I" if vol == "I" else "初級II"
    return f"みんな{vol_label}-第{lesson:02d}課"


def normalize_tags(tags: list) -> list[str]:
    return [str(t) for t in tags if isinstance(t, (str, int, float)) and str(t).strip()]


def apply_to_card(path: Path, dry_run: bool) -> str | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    tags = normalize_tags(list(data.get("Теги", [])))
    word = str(data.get("Слово", "")).strip()
    stripped = [t for t in tags if not STRIP_TAG_RE.match(t)]
    changed = stripped != tags
    tags = stripped

    has_minna = "みんなの日本語" in tags
    if word in MINNA_LESSON_BY_WORD:
        vol, les = MINNA_LESSON_BY_WORD[word]
        new_lesson_tag = lesson_tag(vol, les)
    elif has_minna:
        # Fallback: сохранено в учебниковом трекере, но нет строки в словаре скрипта
        sys.stderr.write(
            f"[WARN] {path.relative_to(ROOT)}: «{word}» с тегом みんなの日本語, "
            "но нет в MINNA_LESSON_BY_WORD — пропуск тега урока.\n"
        )
        new_lesson_tag = None
    else:
        new_lesson_tag = OUTSIDE_TAG

    final_tags = tags[:]
    if new_lesson_tag and new_lesson_tag not in final_tags:
        final_tags.append(new_lesson_tag)

    order_changed = normalize_tags(tags) != normalize_tags(final_tags)
    # стабильный порядок: не сортируем весь список, только дописали в конец
    data["Теги"] = final_tags
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if order_changed or changed:
        if not dry_run:
            path.write_text(payload, encoding="utf-8")
        return "updated"
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Присвоить теги уроков Minna / みんな-教材外")
    ap.add_argument("--dry-run", action="store_true", help="только сообщить изменения без записи")
    args = ap.parse_args()
    n_updated = 0
    for p in sorted(CARDS.rglob("*.json")):
        if apply_to_card(p, dry_run=args.dry_run):
            print(p.relative_to(ROOT))
            n_updated += 1
    print(f"Готово. Обновлено файлов: {n_updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
