#!/bin/bash

# Find python interpreter
PYTHON_BIN=$(command -v python3 || command -v python)

# Base directories
USER_HOME="$HOME"
AUTOSTART_DIR="$USER_HOME/.config/autostart"
DESKTOP_FILE="$AUTOSTART_DIR/metrix.desktop"

# Ensure directory exists
mkdir -p "$AUTOSTART_DIR"

# Create .desktop entry
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Metrix Server
Comment=Automatic startup of Metrix Server Commander
Exec=$PYTHON_BIN $USER_HOME/system/metrix/metrix_server.py
X-GNOME-Autostart-enabled=true
Terminal=false
EOF

chmod +x "$DESKTOP_FILE"

echo "Autostart installed:"
echo "  $DESKTOP_FILE"
echo ""
echo "It will start automatically at next login into your graphical session."
    