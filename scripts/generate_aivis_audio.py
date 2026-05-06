#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
CARDS_DIR = ROOT_DIR / "Карточки"
PRONUNCIATION_DIR = ROOT_DIR / "Произношение"

DEFAULT_ENGINE_URL = "http://127.0.0.1:10101"
DEFAULT_STYLE_NAME = "ノーマル"
DEFAULT_SPEED_SCALE = 0.9

# Разрешённые голоса (точное имя speaker в ответе /speakers локального Engine).
ALLOWED_TTS_SPEAKERS: tuple[str, ...] = (
    "阿井田 茂",
    "にせ",
    "花音",
    "みちのくあいり",
)
HTML_TAG_RE = re.compile(r"<[^>]+>")
EXAMPLE_SPLIT_RE = re.compile(r"\s*<br\s*/?>\s*|\r?\n")
NEW_FORMAT_EXAMPLE_COUNT = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Генерирует MP3-файлы произношения через локальный AivisSpeech "
            "для карточек проекта Japanese ANKI Card."
        )
    )
    parser.add_argument(
        "cards",
        nargs="*",
        help="Пути к JSON-карточкам. Если не указаны, используйте --all-empty.",
    )
    parser.add_argument(
        "--all-empty",
        action="store_true",
        help="Обработать все JSON-карточки с пустым полем 'Произношение'.",
    )
    parser.add_argument(
        "--engine-url",
        default=DEFAULT_ENGINE_URL,
        help=f"URL AivisSpeech Engine. По умолчанию: {DEFAULT_ENGINE_URL}",
    )
    parser.add_argument(
        "--engine-path",
        help="Путь к исполняемому файлу AivisSpeech Engine (run / run.exe).",
    )
    parser.add_argument(
        "--speaker",
        help=(
            "Имя голоса только из белого списка в скрипте. Если не указано, перед "
            "каждым сохранением MP3 (слово и каждый пример) голос случайно выбирается "
            "среди разрешённых голосов, установленных в Engine для данного стиля."
        ),
    )
    parser.add_argument(
        "--style",
        help=f"Имя стиля. По умолчанию: {DEFAULT_STYLE_NAME}",
    )
    parser.add_argument(
        "--write-json",
        action="store_true",
        help="Записать в JSON поле 'Произношение' со ссылками [sound:...].",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Перегенерировать аудио даже если файлы уже существуют.",
    )
    parser.add_argument(
        "--startup-timeout",
        type=int,
        default=240,
        help="Сколько секунд ждать запуска AivisSpeech Engine. По умолчанию: 240.",
    )
    return parser.parse_args()


def strip_example_markup(text: str) -> str:
    return html.unescape(HTML_TAG_RE.sub("", text)).strip()


def parse_examples(raw_text: str) -> list[str]:
    examples = [strip_example_markup(line) for line in EXAMPLE_SPLIT_RE.split(raw_text)]
    examples = [line for line in examples if line]
    if len(examples) != NEW_FORMAT_EXAMPLE_COUNT:
        raise RuntimeError(
            "Поле 'Пример' должно содержать ровно 3 непустых примера, "
            "разделённых тегом <br>."
        )
    return examples


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def request_bytes(url: str, *, method: str = "GET", data: bytes | None = None, headers: dict | None = None) -> bytes:
    request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def request_json(url: str, *, method: str = "GET", data: bytes | None = None, headers: dict | None = None) -> object:
    return json.loads(request_bytes(url, method=method, data=data, headers=headers).decode("utf-8"))


def engine_is_ready(engine_url: str) -> bool:
    try:
        request_bytes(f"{engine_url.rstrip('/')}/version")
        return True
    except Exception:
        return False


def find_engine_executable(explicit_path: str | None) -> Path | None:
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(Path(explicit_path).expanduser())
    candidates.extend(
        [
            Path("/Applications/AivisSpeech.app/Contents/Resources/AivisSpeech-Engine/run"),
            Path("~/Applications/AivisSpeech.app/Contents/Resources/AivisSpeech-Engine/run").expanduser(),
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def start_engine_if_needed(engine_url: str, engine_path: str | None, startup_timeout: int) -> tuple[subprocess.Popen | None, Path | None]:
    if engine_is_ready(engine_url):
        return None, None

    executable = find_engine_executable(engine_path)
    if executable is None:
        raise RuntimeError(
            "AivisSpeech Engine не запущен и исполняемый файл не найден. "
            "Установите AivisSpeech или передайте --engine-path."
        )

    log_file = Path(tempfile.gettempdir()) / f"aivis-engine-{int(time.time())}.log"
    log_handle = log_file.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [str(executable)],
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    log_handle.close()

    deadline = time.time() + startup_timeout
    while time.time() < deadline:
        if engine_is_ready(engine_url):
            return process, log_file
        if process.poll() is not None:
            tail = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()[-20:]
            raise RuntimeError(
                "AivisSpeech Engine завершился во время запуска.\n"
                + "\n".join(tail)
            )
        time.sleep(1)

    raise RuntimeError(
        f"AivisSpeech Engine не успел подняться за {startup_timeout} секунд. "
        f"Лог: {log_file}"
    )


def stop_engine(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def resolve_cards(args: argparse.Namespace) -> list[Path]:
    if not args.cards and not args.all_empty:
        raise SystemExit("Укажите пути к карточкам или используйте --all-empty.")

    if args.cards and args.all_empty:
        raise SystemExit("Используйте либо список карточек, либо --all-empty.")

    if args.all_empty:
        result: list[Path] = []
        for path in sorted(CARDS_DIR.rglob("*.json")):
            try:
                payload = load_json(path)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Некорректный JSON в {path}: {exc}") from exc
            if not str(payload.get("Произношение", "")).strip():
                result.append(path)
        return result

    resolved: list[Path] = []
    for raw_path in args.cards:
        path = Path(raw_path)
        if not path.is_absolute():
            path = (ROOT_DIR / path).resolve()
        if not path.exists():
            raise SystemExit(f"Файл не найден: {raw_path}")
        resolved.append(path)
    return resolved


def speakers_by_name(engine_url: str) -> dict[str, dict]:
    payload = request_json(f"{engine_url.rstrip('/')}/speakers")
    if not isinstance(payload, list):
        raise RuntimeError("Неожиданный ответ /speakers.")
    mapping: dict[str, dict] = {}
    for item in payload:
        name = item.get("name")
        if isinstance(name, str) and name.strip():
            mapping[name] = item
    return mapping


def pick_style_id_from_speaker(speaker: dict, style_name: str) -> int:
    for style in speaker.get("styles", []):
        if style.get("name") == style_name:
            return int(style["id"])
    available = ", ".join(style.get("name", "") for style in speaker.get("styles", []))
    sp_name = speaker.get("name", "<без имени>")
    raise RuntimeError(
        f"У голоса '{sp_name}' нет стиля '{style_name}'. Доступно: {available}"
    )


def compatible_whitelist(
    speakers_map: dict[str, dict],
    *,
    style_name: str,
) -> list[str]:
    result: list[str] = []
    for allowed in ALLOWED_TTS_SPEAKERS:
        sp = speakers_map.get(allowed)
        if sp is None:
            continue
        if any(style.get("name") == style_name for style in sp.get("styles", [])):
            result.append(allowed)
    return result


def validate_explicit_whitelist(
    speakers_map: dict[str, dict],
    speaker_name: str,
    style_name: str,
) -> tuple[str, str]:
    if speaker_name not in ALLOWED_TTS_SPEAKERS:
        allowed = ", ".join(ALLOWED_TTS_SPEAKERS)
        raise RuntimeError(
            f"Голос '{speaker_name}' не из разрешённого списка. Разрешено: {allowed}"
        )
    sp = speakers_map.get(speaker_name)
    if sp is None:
        raise RuntimeError(
            f"Голос '{speaker_name}' указан проектом, но не установлен в AivisSpeech Engine."
        )
    pick_style_id_from_speaker(sp, style_name)
    return speaker_name, style_name


def run_ffmpeg(input_wav: Path, output_mp3: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("Не найден ffmpeg. Установите ffmpeg, чтобы сохранять MP3.")

    subprocess.run(
        [
            ffmpeg,
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_wav),
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(output_mp3),
        ],
        check=True,
    )


def generate_audio(engine_url: str, style_id: int, text: str, output_mp3: Path) -> None:
    query_params = urllib.parse.urlencode({"speaker": style_id, "text": text})
    query = request_json(f"{engine_url.rstrip('/')}/audio_query?{query_params}", method="POST")
    query["outputStereo"] = False
    query["speedScale"] = DEFAULT_SPEED_SCALE
    wav_bytes = request_bytes(
        f"{engine_url.rstrip('/')}/synthesis?speaker={style_id}",
        method="POST",
        data=json.dumps(query).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
        temp_wav.write(wav_bytes)
        temp_wav_path = Path(temp_wav.name)

    try:
        run_ffmpeg(temp_wav_path, output_mp3)
    finally:
        temp_wav_path.unlink(missing_ok=True)


def sound_tags(word: str) -> str:
    tags = [f"[sound:{word}_слово.mp3]"]
    for index in range(1, NEW_FORMAT_EXAMPLE_COUNT + 1):
        tags.append(f"[sound:{word}_пример_{index}.mp3]")
    return "".join(tags)


def process_card(
    card_path: Path,
    engine_url: str,
    *,
    fixed_speaker: str | None,
    style_name: str,
    write_json: bool,
    force: bool,
) -> None:
    payload = load_json(card_path)
    word = str(payload["Слово"]).strip()
    examples = parse_examples(str(payload["Пример"]))

    speakers_map = speakers_by_name(engine_url)
    random_pool: list[str] | None
    if fixed_speaker:
        validate_explicit_whitelist(speakers_map, fixed_speaker, style_name)
        random_pool = None
    else:
        random_pool = compatible_whitelist(speakers_map, style_name=style_name)
        if not random_pool:
            raise RuntimeError(
                f"Ни один голос из белого списка проекта не установлен в AivisSpeech Engine "
                f"или не поддерживает стиль «{style_name}». Ожидаются: "
                + ", ".join(ALLOWED_TTS_SPEAKERS)
            )
        missing = [n for n in ALLOWED_TTS_SPEAKERS if n not in speakers_map]
        if missing:
            print(
                "Предупреждение: в Engine не найдены голоса из белого списка: "
                + ", ".join(missing),
                file=sys.stderr,
            )

    def next_style_id() -> int:
        if fixed_speaker:
            speaker_name = fixed_speaker
        else:
            assert random_pool is not None
            speaker_name = random.choice(random_pool)
        sp = speakers_map[speaker_name]
        return pick_style_id_from_speaker(sp, style_name)

    relative = card_path.relative_to(CARDS_DIR)
    topic = relative.parts[0]
    output_dir = PRONUNCIATION_DIR / topic
    output_dir.mkdir(parents=True, exist_ok=True)

    word_mp3 = output_dir / f"{word}_слово.mp3"

    if force or not word_mp3.exists():
        generate_audio(engine_url, next_style_id(), word, word_mp3)
        print(f"Сгенерировано: {word_mp3.relative_to(ROOT_DIR)}")
    else:
        print(f"Пропуск, файл уже есть: {word_mp3.relative_to(ROOT_DIR)}")

    for index, example in enumerate(examples, start=1):
        example_mp3 = output_dir / f"{word}_пример_{index}.mp3"
        if force or not example_mp3.exists():
            generate_audio(engine_url, next_style_id(), example, example_mp3)
            print(f"Сгенерировано: {example_mp3.relative_to(ROOT_DIR)}")
        else:
            print(f"Пропуск, файл уже есть: {example_mp3.relative_to(ROOT_DIR)}")

    tags = sound_tags(word)
    print(f"Теги Anki: {tags}")

    if write_json:
        payload["Произношение"] = tags
        save_json(card_path, payload)
        print(f"Обновлён JSON: {card_path.relative_to(ROOT_DIR)}")


def main() -> int:
    args = parse_args()
    cards = resolve_cards(args)
    if not cards:
        print("Карточек для обработки не найдено.")
        return 0

    process = None
    log_path = None
    try:
        process, log_path = start_engine_if_needed(
            args.engine_url,
            args.engine_path,
            args.startup_timeout,
        )
        chosen_style = args.style or DEFAULT_STYLE_NAME
        if args.speaker:
            print(f"Голос: фиксирован «{args.speaker}» | Стиль: {chosen_style}")
        else:
            print(
                f"Голос: случайный из белого списка для каждой фразы | Стиль: {chosen_style}"
            )
        for card_path in cards:
            retry = False
            while True:
                try:
                    process_card(
                        card_path=card_path,
                        engine_url=args.engine_url,
                        fixed_speaker=args.speaker,
                        style_name=chosen_style,
                        write_json=args.write_json,
                        force=args.force,
                    )
                    break
                except (urllib.error.URLError, urllib.error.HTTPError) as exc:
                    if retry:
                        raise RuntimeError(
                            f"Не удалось обработать карточку {card_path}: {exc}"
                        ) from exc
                    print(
                        f"Предупреждение: потеряно соединение с AivisSpeech во время обработки "
                        f"{card_path.relative_to(ROOT_DIR)}. Перезапускаю engine и повторяю карточку...",
                        file=sys.stderr,
                    )
                    retry = True
                    stop_engine(process)
                    process, log_path = start_engine_if_needed(
                        args.engine_url,
                        args.engine_path,
                        args.startup_timeout,
                    )
        return 0
    except (urllib.error.URLError, urllib.error.HTTPError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        if log_path is not None and log_path.exists():
            print(f"Лог AivisSpeech Engine: {log_path}", file=sys.stderr)
        return 1
    finally:
        stop_engine(process)


if __name__ == "__main__":
    raise SystemExit(main())
