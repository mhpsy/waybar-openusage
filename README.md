# waybar-openusage

**English** | [中文](README-zh.md)

Track all your AI coding subscriptions in Waybar. Built for Hyprland / Sway and other Wayland compositors.

> **Origin**: This project is a Linux port of [OpenUsage](https://github.com/robinebers/openusage) — a macOS menu bar app built with Tauri (Rust + React). Since the original only supports macOS, this project rewrites its core logic (plugin system, data fetching, HTTP API) in Python so it can run as a Waybar custom module on Linux.

## Relationship to OpenUsage

| | [OpenUsage](https://github.com/robinebers/openusage) | waybar-openusage |
|---|---|---|
| Platform | macOS (Tauri) | Linux (Waybar) |
| Language | Rust + TypeScript + QuickJS | Python |
| Display | macOS menu bar | Waybar custom module |
| Plugin system | QuickJS sandbox | Python modules |
| HTTP API | `127.0.0.1:6736` | `127.0.0.1:6736` (compatible) |
| Credentials | macOS Keychain + files | Files + gh CLI |

All provider API endpoints, authentication logic, and data parsing are ported from the original project's plugin implementations, adapted for Linux file paths and credential sources.

## Features

- **At a glance** — All your AI tool usage in your Waybar
- **Auto-refresh** — Configurable interval (default 15 min), click to refresh immediately
- **Rich tooltips** — Color-coded progress bars, reset countdowns, multi-line details
- **Local HTTP API** — Compatible with OpenUsage API format, other apps can read your usage data
- **Concurrent probing** — Multiple providers fetched in parallel

## Supported Providers

| Provider | Data | Auth |
|----------|------|------|
| **Claude** | Session / Weekly / Sonnet / Extra usage | `~/.claude/.credentials.json` |
| **Cursor** | Credits / Total / Auto / API / On-demand | `~/.config/Cursor/` SQLite |
| **Copilot** | Premium / Chat / Completions | `gh auth token` |
| **Codex** | Session / Weekly / Credits | `~/.config/codex/auth.json` |
| **Windsurf** | Prompt credits / Flex credits | `~/.config/Windsurf/` SQLite |
| **Gemini** | Pro / Flash quota | `~/.gemini/oauth_creds.json` |
| **Amp** | Free balance / Bonus / Credits | `~/.local/share/amp/secrets.json` |
| **Kimi Code** | Session / Weekly | `~/.kimi/credentials/kimi-code.json` |
| **Z.ai** | Session / Weekly / Web searches | `ZAI_API_KEY` env var |
| **MiniMax** | Session prompts | `MINIMAX_API_KEY` env var |
| **JetBrains AI** | Quota / Remaining | `~/.config/JetBrains/` XML |
| **OpenCode Go** | 5h / Weekly / Monthly spend | `~/.local/share/opencode/` SQLite |
| **Factory/Droid** | Standard / Premium tokens | `~/.factory/auth.json` |

## Installation

### Requirements

- Python >= 3.11
- `requests` (installed automatically)
- Optional: `cryptography` (for Factory encrypted auth)

### Install

```bash
git clone https://github.com/mhpsy/waybar-openusage.git
cd waybar-openusage
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Or use the install script:

```bash
chmod +x install.sh
./install.sh
```

### Verify

```bash
# List all available providers
waybar-openusage --mode list

# Test with Claude
waybar-openusage --mode once --plugins claude -v
```

## Waybar Setup

### 1. Add module definition

In `~/.config/waybar/config.jsonc`:

```jsonc
// Add "custom/openusage" to modules-right
"modules-right": [
    // ... other modules ...
    "custom/openusage",
    "custom/exit"
],

"custom/openusage": {
    "exec": "/path/to/waybar-openusage/.venv/bin/waybar-openusage --mode continuous",
    "return-type": "json",
    "restart-interval": 5,
    "tooltip": false,
    "format": "{}",
    "max-length": 50,
    "on-click": "/path/to/waybar-openusage/.venv/bin/waybar-openusage-popup show",
    "on-click-right": "/path/to/waybar-openusage/.venv/bin/waybar-openusage-popup hide",
    "on-click-middle": "pkill -SIGUSR1 -f 'waybar-openusage --mode' || true"
}
```

> Replace `/path/to/` with your actual install path.
>
> Requires `swaync` as notification daemon (default on most Hyprland setups).

### 2. Add styles

In `~/.config/waybar/style.css`:

```css
#custom-openusage {
    background-color: @bg;
    color: @fg;
    border-radius: 15px;
    padding: 4px 12px;
    margin: 6px 4px;
}

#custom-openusage.warning {
    color: #f9e2af;
}

#custom-openusage.critical {
    color: #f38ba8;
}

#custom-openusage.error {
    color: #a6adc8;
    font-style: italic;
}
```

### 3. Restart Waybar

```bash
killall waybar && waybar &
```

## Configuration

Config file: `~/.config/waybar-openusage/config.json`

```json
{
  "enabled_plugins": ["claude", "cursor", "copilot"],
  "plugin_order": [
    "claude", "cursor", "copilot", "codex", "windsurf", "gemini",
    "amp", "kimi", "zai", "minimax", "jetbrains-ai-assistant",
    "opencode-go", "factory"
  ],
  "refresh_interval_minutes": 15,
  "display_mode": "used",
  "http_api_enabled": true,
  "http_api_port": 6736
}
```

| Field | Description | Default |
|-------|-------------|---------|
| `enabled_plugins` | List of enabled providers | `["claude", "cursor", "copilot"]` |
| `plugin_order` | Display order | All providers |
| `refresh_interval_minutes` | Auto-refresh interval (minutes) | `15` |
| `display_mode` | `"used"` for usage / `"left"` for remaining | `"used"` |
| `http_api_enabled` | Enable local HTTP API | `true` |
| `http_api_port` | HTTP API port | `6736` |

## CLI Usage

```bash
# Single output (for testing)
waybar-openusage --mode once

# Continuous mode (for Waybar)
waybar-openusage --mode continuous

# List all available providers
waybar-openusage --mode list

# Specify providers
waybar-openusage --mode once --plugins claude cursor

# Custom refresh interval
waybar-openusage --mode continuous --interval 5

# Disable HTTP API
waybar-openusage --mode once --no-api

# Verbose logging to stderr
waybar-openusage --mode once -v
```

## Waybar Interaction

| Action | Behavior |
|--------|----------|
| **Left click** | Show usage details popup (notification) |
| **Right click** | Hide the popup |
| **Middle click** | Refresh data immediately |

The popup displays color-coded progress bars, usage percentages, and reset countdowns for each provider. It stays visible until dismissed with right click.

## Local HTTP API

Serves cached data at `127.0.0.1:6736`, compatible with the OpenUsage API format:

```bash
# All enabled providers
curl http://127.0.0.1:6736/v1/usage

# Single provider
curl http://127.0.0.1:6736/v1/usage/claude
```

Response example:

```json
[
  {
    "providerId": "claude",
    "displayName": "Claude",
    "plan": "Max 20x",
    "lines": [
      {
        "type": "progress",
        "label": "Session",
        "used": 21.0,
        "limit": 100,
        "format": { "kind": "percent" },
        "resetsAt": "2026-04-01T11:00:01Z",
        "periodDurationMs": 18000000
      }
    ],
    "fetchedAt": "2026-04-01T10:12:46Z"
  }
]
```

## Project Structure

```
waybar-openusage/
├── waybar_openusage/
│   ├── main.py           # Entry point, CLI args, continuous/once mode
│   ├── config.py          # Config management (XDG paths)
│   ├── plugin_base.py     # Plugin base class, data types
│   ├── formatter.py       # Waybar JSON output, tooltip rendering
│   ├── http_api.py        # Local HTTP API server
│   └── plugins/           # One file per provider
├── examples/
│   ├── waybar-config.jsonc
│   └── style.css
├── install.sh
├── pyproject.toml
└── LICENSE
```

## Credits

- [OpenUsage](https://github.com/robinebers/openusage) by [@robinebers](https://github.com/robinebers) — original project, all provider logic ported from here
- Inspired by [CodexBar](https://github.com/steipete/CodexBar) by [@steipete](https://github.com/steipete)

## License

[MIT](LICENSE)
