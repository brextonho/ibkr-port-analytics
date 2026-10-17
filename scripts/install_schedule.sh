#!/usr/bin/env bash
# Schedule a live pull Tuesday–Saturday at 20:00 (your Mac's local time) with
# macOS launchd. Unlike cron, launchd runs a pull missed while the Mac was
# asleep once it wakes. A pull IB isn't ready for fails safely and the next
# one fills the gap (14-day overlap).
#
#   ./scripts/install_schedule.sh            install or refresh
#   ./scripts/install_schedule.sh --remove   uninstall
set -euo pipefail

LABEL="com.ibkr-portfolio.ingest"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
UV="$(command -v uv || true)"

launchctl bootout "gui/$UID/$LABEL" 2>/dev/null || true
if [ "${1:-}" = "--remove" ]; then
  rm -f "$PLIST"
  echo "removed $LABEL"
  exit 0
fi

[ -n "$UV" ] || { echo "ERROR: uv not found on PATH" >&2; exit 1; }
[ -f "$REPO/.env" ] || echo "WARNING: $REPO/.env is missing — scheduled pulls will fail until you create it" >&2

days=""
for weekday in 2 3 4 5 6; do  # launchd: 0 = Sunday, so 2–6 = Tuesday–Saturday
  days+="<dict><key>Weekday</key><integer>$weekday</integer><key>Hour</key><integer>20</integer><key>Minute</key><integer>0</integer></dict>"
done

mkdir -p "$(dirname "$PLIST")"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>WorkingDirectory</key><string>$REPO</string>
  <key>ProgramArguments</key><array><string>$UV</string><string>run</string><string>portfolio</string><string>ingest</string></array>
  <key>StartCalendarInterval</key><array>$days</array>
  <key>StandardOutPath</key><string>$REPO/ingest.log</string>
  <key>StandardErrorPath</key><string>$REPO/ingest.log</string>
</dict></plist>
PLIST

launchctl bootstrap "gui/$UID" "$PLIST"
echo "installed $LABEL: Tue–Sat 20:00, log in $REPO/ingest.log"
echo "run now:   launchctl kickstart gui/$UID/$LABEL"
