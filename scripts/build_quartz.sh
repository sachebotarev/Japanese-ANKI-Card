#!/usr/bin/env bash
# Сборка сайта ванильным Quartz, без вендорённого форка в репозитории.
#
# Что делает:
#   1) Клонирует апстрим Quartz в .quartz-build/ (по умолчанию зафиксирован тег).
#   2) Накатывает поверх клона наш оверлей quartz_overlay/ (конфиг, layout,
#      кастомный MyGraph). Никакие исходники Quartz не модифицируются.
#   3) Готовит quartz_content/ из Записи/ скриптом sync_quartz_content.py.
#   4) Ставит зависимости и собирает сайт. Артефакты — в quartz_content/public/.
#
# Использование:
#   scripts/build_quartz.sh                # обычная сборка
#   scripts/build_quartz.sh --serve        # dev-сервер на http://localhost:8080
#
# Переменные окружения:
#   QUARTZ_VERSION    — git ref апстрима (тег/ветка/SHA). По умолчанию v4.5.2.
#   QUARTZ_REPO       — git URL апстрима. По умолчанию jackyzha0/quartz на GitHub.
#   QUARTZ_RAW_BASE   — пробрасывается в sync_quartz_content.py (необязательно).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/.quartz-build"
OVERLAY_DIR="$ROOT_DIR/quartz_overlay"
CONTENT_DIR="$ROOT_DIR/quartz_content"
SITE_DIR="$ROOT_DIR/quartz_site"
QUARTZ_VERSION="${QUARTZ_VERSION:-v4.5.2}"
QUARTZ_REPO="${QUARTZ_REPO:-https://github.com/jackyzha0/quartz.git}"

if [[ ! -d "$OVERLAY_DIR" ]]; then
  echo "[build_quartz] нет каталога $OVERLAY_DIR" >&2
  exit 1
fi

echo "[build_quartz] клонирую $QUARTZ_REPO@$QUARTZ_VERSION → $BUILD_DIR"
rm -rf "$BUILD_DIR"
git clone --depth 1 --branch "$QUARTZ_VERSION" "$QUARTZ_REPO" "$BUILD_DIR"

echo "[build_quartz] накатываю оверлей $OVERLAY_DIR"
cp -R "$OVERLAY_DIR/." "$BUILD_DIR/"

echo "[build_quartz] подготавливаю quartz_content/ из Записи/"
python3 "$ROOT_DIR/scripts/sync_quartz_content.py"

pushd "$BUILD_DIR" >/dev/null

echo "[build_quartz] npm ci"
npm ci

rm -rf "$SITE_DIR"
echo "[build_quartz] quartz build -d $CONTENT_DIR -o $SITE_DIR"
if [[ "${1:-}" == "--serve" ]]; then
  npx quartz build --serve -d "$CONTENT_DIR" -o "$SITE_DIR"
else
  npx quartz build -d "$CONTENT_DIR" -o "$SITE_DIR" --verbose
fi

popd >/dev/null

echo "[build_quartz] готово: $SITE_DIR"
