#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname -- "$SCRIPT_DIR")
EDITION=${1:-$(TZ=Asia/Shanghai date +%F)}
PORT=${2:-4173}
OUTPUT_DIR="$PROJECT_DIR/outputs/$EDITION"

if [ ! -f "$OUTPUT_DIR/review.html" ]; then
  echo "Review page not found at $OUTPUT_DIR/review.html" >&2
  exit 1
fi

echo "Open http://127.0.0.1:$PORT/review.html"
exec python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$OUTPUT_DIR"
