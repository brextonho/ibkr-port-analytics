#!/usr/bin/env bash
# Install (or refresh) the host crontab entry for scheduled ingestion
# (PRD §5.4). The cron expression in config/config.yaml (ingestion.cron) is
# the source of truth; this script mirrors it into the crontab. Re-run after
# changing the cadence — e.g. weekly → daily is a one-key config change.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG="$REPO/config/config.yaml"
if [ ! -f "$CONFIG" ]; then
  CONFIG="$REPO/config/config.example.yaml"
  echo "note: config/config.yaml not found, reading cadence from config.example.yaml"
fi

if [ ! -f "$REPO/.env" ]; then
  echo "WARNING: $REPO/.env does not exist — the scheduled run will fail until" >&2
  echo "         you create it (FLEX_TOKEN, FLEX_QUERY_ID; see .env.example)." >&2
fi

CRON_EXPR="$(cd "$REPO" && uv run python -c "
import yaml, sys
print(yaml.safe_load(open('$CONFIG'))['ingestion']['cron'])
")"

DOCKER_BIN="$(command -v docker)"
if [ -z "$DOCKER_BIN" ]; then
  echo "ERROR: docker not found on PATH" >&2
  exit 1
fi

MARKER="# ibkr-port-analytics-ingestion"
LOG="$REPO/ingestion-cron.log"
LINE="$CRON_EXPR cd $REPO && $DOCKER_BIN compose run --rm ingestion >> $LOG 2>&1 $MARKER"

# replace any previous marked entry, keep everything else
{ crontab -l 2>/dev/null | grep -v "$MARKER" || true; echo "$LINE"; } | crontab -

echo "installed crontab entry:"
echo "  $LINE"
echo
echo "notes:"
echo "  - Docker Desktop must be running at fire time (macOS)."
echo "  - logs append to $LOG"
echo "  - remove with: crontab -l | grep -v '$MARKER' | crontab -"
