#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
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
PREFERRED_SPEAKER_NAME = "Anneli-nsfw"
FALLBACK_SPEAKER_NAME = "まお"
DEFAULT_STYLE_NAME = "ノーマル"
DEFAULT_SPEED_SCALE = 0.9
HTML_TAG_RE = re.compile(r"<[^>]+>")


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
            "Имя голоса. По умолчанию: сначала пытается использовать "
            f"{PREFERRED_SPEAKER_NAME}, если он доступен, иначе {FALLBACK_SPEAKER_NAME}."
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


def resolve_voice(engine_url: str, speaker_name: str | None, style_name: str | None) -> tuple[str, str]:
    chosen_style = style_name or DEFAULT_STYLE_NAME
    if speaker_name:
        return speaker_name, chosen_style

    speakers = request_json(f"{engine_url.rstrip('/')}/speakers")
    available_names = {speaker.get("name") for speaker in speakers}
    if PREFERRED_SPEAKER_NAME in available_names:
        return PREFERRED_SPEAKER_NAME, chosen_style
    return FALLBACK_SPEAKER_NAME, chosen_style


def pick_style_id(engine_url: str, speaker_name: str, style_name: str) -> int:
    speakers = request_json(f"{engine_url.rstrip('/')}/speakers")
    for speaker in speakers:
        if speaker.get("name") != speaker_name:
            continue
        for style in speaker.get("styles", []):
            if style.get("name") == style_name:
                return int(style["id"])
        available = ", ".join(style["name"] for style in speaker.get("styles", []))
        raise RuntimeError(
            f"У голоса '{speaker_name}' нет стиля '{style_name}'. Доступно: {available}"
        )

    available = ", ".join(speaker.get("name", "<без имени>") for speaker in speakers)
    raise RuntimeError(f"Голос '{speaker_name}' не найден. Доступно: {available}")


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
    return f"[sound:{word}_слово.mp3][sound:{word}_пример.mp3]"


def process_card(card_path: Path, engine_url: str, style_id: int, write_json: bool, force: bool) -> None:
    payload = load_json(card_path)
    word = str(payload["Слово"]).strip()
    example = strip_example_markup(str(payload["Пример"]))

    relative = card_path.relative_to(CARDS_DIR)
    topic = relative.parts[0]
    output_dir = PRONUNCIATION_DIR / topic
    output_dir.mkdir(parents=True, exist_ok=True)

    word_mp3 = output_dir / f"{word}_слово.mp3"
    example_mp3 = output_dir / f"{word}_пример.mp3"

    if force or not word_mp3.exists():
        generate_audio(engine_url, style_id, word, word_mp3)
        print(f"Сгенерировано: {word_mp3.relative_to(ROOT_DIR)}")
    else:
        print(f"Пропуск, файл уже есть: {word_mp3.relative_to(ROOT_DIR)}")

    if force or not example_mp3.exists():
        generate_audio(engine_url, style_id, example, example_mp3)
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
        speaker_name, style_name = resolve_voice(
            args.engine_url,
            args.speaker,
            args.style,
        )
        print(f"Голос: {speaker_name} | Стиль: {style_name}")
        style_id = pick_style_id(args.engine_url, speaker_name, style_name)
        for card_path in cards:
            retry = False
            while True:
                try:
                    process_card(
                        card_path=card_path,
                        engine_url=args.engine_url,
                        style_id=style_id,
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
                    speaker_name, style_name = resolve_voice(
                        args.engine_url,
                        args.speaker,
                        args.style,
                    )
                    style_id = pick_style_id(args.engine_url, speaker_name, style_name)
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
