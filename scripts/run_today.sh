#!/bin/sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
EDITION_DATE=${1:-$(TZ=Asia/Shanghai date +%F)}
SEED_PATH=${2:-"$PROJECT_DIR/data/seeds/$EDITION_DATE.json"}
RULES_PATH=${3:-"$PROJECT_DIR/data/platform_rules/$EDITION_DATE.json"}

PYTHONPATH="$PROJECT_DIR/src" python3 -m ai_news_agent doctor
if [ "${AI_NEWS_FORCE:-0}" = "1" ]; then
  PYTHONPATH="$PROJECT_DIR/src" python3 -m ai_news_agent run \
    --date "$EDITION_DATE" \
    --seed "$SEED_PATH" \
    --platform-rules "$RULES_PATH" \
    --provider codex \
    --force
else
  PYTHONPATH="$PROJECT_DIR/src" python3 -m ai_news_agent run \
    --date "$EDITION_DATE" \
    --seed "$SEED_PATH" \
    --platform-rules "$RULES_PATH" \
    --provider codex
fi
