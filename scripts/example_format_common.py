"""Общие функции формата трёх примеров (<br>) для карточек JSON."""
from __future__ import annotations

import json
import re
from pathlib import Path

BR_SPLIT = re.compile(r"<br\s*/?>", re.I)
SPAN = re.compile(
    r"<span\s+class=['\"]study-word['\"]>\s*([^<]*?)\s*</span>",
    re.IGNORECASE,
)


def count_example_parts(text: str | None) -> int:
    if not text or not isinstance(text, str):
        return 0
    return len([p.strip() for p in BR_SPLIT.split(text.strip()) if p.strip()])


def is_triple_format(data: dict) -> bool:
    return (
        count_example_parts(str(data.get("Пример"))) == 3
        and count_example_parts(str(data.get("Пример без слова"))) == 3
        and count_example_parts(str(data.get("Пример перевод"))) == 3
    )


def blankify(example_html: str) -> str:
    return SPAN.sub("_____", example_html)


def four_sounds(word: str) -> str:
    return (
        f"[sound:{word}_слово.mp3]"
        f"[sound:{word}_пример_1.mp3]"
        f"[sound:{word}_пример_2.mp3]"
        f"[sound:{word}_пример_3.mp3]"
    )


def russian_prompt_from_third_ru(third_ru: str) -> str:
    """Промпт картинки на русском по смыслу третьего предложения (спецификация cards-spec)."""
    t = third_ru.replace("\n", " ").strip()
    if len(t) > 400:
        t = t[:397] + "…"
    return (
        "Иллюстрация учебная, 512×512, без японских подписей: "
        f"{t} Главный визуальный акцент — изучаемое слово/смысл карточки."
    )


def load_card(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_card(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def apply_example_patch(path: Path, patch: dict, *, overwrite_img: bool = True) -> None:
    """
    patch: ключи «Пример», «Пример перевод», опционально «Картинка», «Произношение».
    «Пример без слова» строится автоматически.
    """
    data = load_card(path)
    word = str(data["Слово"])
    if "Пример" not in patch or "Пример перевод" not in patch:
        raise ValueError("patch needs Пример и Пример перевод")
    ex = patch["Пример"]
    ru = patch["Пример перевод"]
    data["Пример"] = ex
    data["Пример без слова"] = blankify(ex)
    data["Пример перевод"] = ru
    if overwrite_img:
        _, _, ru3 = [p.strip() for p in BR_SPLIT.split(ru.strip())]
        if "Картинка" in patch and patch["Картинка"]:
            data["Картинка"] = str(patch["Картинка"])
        else:
            data["Картинка"] = russian_prompt_from_third_ru(ru3)
    if patch.get("Произношение"):
        data["Произношение"] = str(patch["Произношение"])
    else:
        data["Произношение"] = four_sounds(word)
    save_card(path, data)
