#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname -- "$SCRIPT_DIR")
EDITION=${1:-}
PORT=${2:-4173}
OUTPUTS_DIR="$PROJECT_DIR/outputs"

if [ -n "$EDITION" ] && [ ! -f "$OUTPUTS_DIR/$EDITION/review.html" ]; then
  echo "Review page not found at $OUTPUTS_DIR/$EDITION/review.html" >&2
  exit 1
fi

PYTHONPATH="$PROJECT_DIR/src" python3 -c 'import sys; from pathlib import Path; from ai_news_agent.preview import write_archive_index; write_archive_index(Path(sys.argv[1]))' "$OUTPUTS_DIR"

if [ -n "$EDITION" ]; then
  echo "Open http://127.0.0.1:$PORT/$EDITION/review.html"
else
  echo "Open http://127.0.0.1:$PORT/review.html"
fi
exec python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$OUTPUTS_DIR"
