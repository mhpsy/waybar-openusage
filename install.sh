#!/usr/bin/env bash
set -euo pipefail

echo "=== waybar-openusage installer ==="

# Install Python package
echo "[1/3] Installing waybar-openusage..."
pip install --user -e . 2>/dev/null || pip install -e .

# Create default config if it doesn't exist
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/waybar-openusage"
CONFIG_FILE="$CONFIG_DIR/config.json"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "[2/3] Creating default config at $CONFIG_FILE..."
    mkdir -p "$CONFIG_DIR"
    cat > "$CONFIG_FILE" << 'CONF'
{
  "enabled_plugins": ["claude", "cursor", "copilot"],
  "plugin_order": [
    "claude", "cursor", "copilot", "codex", "windsurf", "gemini",
    "amp", "kimi", "zai", "minimax", "jetbrains-ai-assistant",
    "opencode-go", "factory"
  ],
  "refresh_interval_minutes": 15,
  "display_mode": "used",
  "icon": "󰚩",
  "waybar_max_length": 40,
  "http_api_enabled": true,
  "http_api_port": 6736
}
CONF
else
    echo "[2/3] Config already exists at $CONFIG_FILE, skipping."
fi

# Show Waybar config snippet
echo "[3/3] Done!"
echo ""
echo "=== Add this to your Waybar config (~/.config/waybar/config.jsonc): ==="
echo ""
cat << 'WAYBAR'
"custom/openusage": {
    "exec": "waybar-openusage --mode continuous",
    "return-type": "json",
    "interval": "once",
    "tooltip": true,
    "format": "{}",
    "on-click": "waybar-openusage --mode once | jq -r .tooltip | notify-send -u low 'OpenUsage' \"$(cat)\"",
    "on-click-right": "xdg-open ~/.config/waybar-openusage/config.json"
}
WAYBAR
echo ""
echo "=== Add this to your Waybar style.css: ==="
echo ""
cat << 'CSS'
#custom-openusage {
    padding: 0 8px;
    color: #cdd6f4;
}
#custom-openusage.warning {
    color: #f9e2af;
}
#custom-openusage.critical {
    color: #f38ba8;
}
#custom-openusage.error {
    color: #a6adc8;
}
CSS
echo ""
echo "Then restart Waybar: killall waybar && waybar &"
