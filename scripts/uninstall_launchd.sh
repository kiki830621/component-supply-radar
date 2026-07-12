#!/bin/zsh
set -euo pipefail

LABEL="com.component-supply-radar.daily"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  print "DRY RUN：將移除 $PLIST_PATH"
  exit 0
fi

launchctl bootout "gui/$(id -u)" "$PLIST_PATH" >/dev/null 2>&1 || true
rm -f "$PLIST_PATH"
print "已移除每日排程：$PLIST_PATH"
