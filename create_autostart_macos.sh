#!/bin/bash

PLIST=~/Library/LaunchAgents/com.metrix.server.plist
PYTHON_BIN=$(command -v python3 || command -v python)
USER_HOME="$HOME"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN"
        "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.metrix.server</string>

    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>$USER_HOME/system/metrix/metrix_server.py</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>WorkingDirectory</key>
    <string>$USER_HOME/system/metrix</string>

    <key>StandardOutPath</key>
    <string>$USER_HOME/system/metrix/metrix.log</string>

    <key>StandardErrorPath</key>
    <string>$USER_HOME/system/metrix/metrix.err</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST"

echo "macOS autostart installed and loaded."
