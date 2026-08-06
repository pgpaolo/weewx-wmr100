#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="3.5.2-gp2"
BASENAME="weewx-wmr100-wmr88-hardened-$VERSION"
OUT_DIR="${1:-$ROOT_DIR/dist}"
STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT HUP INT TERM

mkdir -p "$OUT_DIR" "$STAGE_DIR/$BASENAME"

(
    cd "$ROOT_DIR"
    tar \
      --exclude='./.git' \
      --exclude='./dist' \
      --exclude='__pycache__' \
      --exclude='*.pyc' \
      --exclude='SHA256SUMS.txt' \
      -cf - .
) | tar -xf - -C "$STAGE_DIR/$BASENAME"

find "$STAGE_DIR/$BASENAME" -type f -exec touch -d '2026-08-06 12:00:00 UTC' {} +
find "$STAGE_DIR/$BASENAME" -type d -exec touch -d '2026-08-06 12:00:00 UTC' {} +

ARCHIVE="$OUT_DIR/$BASENAME.zip"
rm -f "$ARCHIVE" "$ARCHIVE.sha256"
(
    cd "$STAGE_DIR"
    zip -X -q -r "$ARCHIVE" "$BASENAME"
)
sha256sum "$ARCHIVE" > "$ARCHIVE.sha256"

echo "Created $ARCHIVE"
cat "$ARCHIVE.sha256"
