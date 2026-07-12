#!/bin/zsh
set -euo pipefail

LABEL="com.component-supply-radar.daily"
SCRIPT_DIR="${0:A:h}"
REPO_ROOT="${SCRIPT_DIR:h}"
UV_BIN="$(command -v uv)"
AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$AGENTS_DIR/$LABEL.plist"
LOG_DIR="$REPO_ROOT/data/logs"

PLIST_CONTENT=$(< /dev/stdin) <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$UV_BIN</string><string>run</string><string>component-supply-radar</string>
    <string>run-daily</string>
  </array>
  <key>WorkingDirectory</key><string>$REPO_ROOT</string>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>30</integer></dict>
  <key>StandardOutPath</key><string>$LOG_DIR/daily.out.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/daily.err.log</string>
</dict>
</plist>
EOF

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  print -r -- "$PLIST_CONTENT"
  exit 0
fi

mkdir -p "$AGENTS_DIR" "$LOG_DIR"
launchctl bootout "gui/$(id -u)" "$PLIST_PATH" >/dev/null 2>&1 || true
print -r -- "$PLIST_CONTENT" > "$PLIST_PATH"
plutil -lint "$PLIST_PATH"
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
print "已安裝每日 07:30 排程：$PLIST_PATH"
