"""Configuration management for waybar-openusage."""

import json
import os
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "waybar-openusage"
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "waybar-openusage"
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "waybar-openusage"

DEFAULT_CONFIG = {
    "enabled_plugins": ["claude", "cursor", "copilot"],
    "plugin_order": ["claude", "cursor", "copilot", "codex", "windsurf", "gemini",
                     "amp", "kimi", "zai", "minimax", "jetbrains-ai-assistant",
                     "opencode-go", "factory", "antigravity"],
    "refresh_interval_minutes": 15,
    "display_mode": "used",  # "used" or "left"
    "waybar_max_length": 50,
    "http_api_enabled": True,
    "http_api_port": 6736,
}


def ensure_dirs():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    ensure_dirs()
    config_file = CONFIG_DIR / "config.json"
    config = dict(DEFAULT_CONFIG)
    if config_file.exists():
        try:
            with open(config_file) as f:
                user_config = json.load(f)
            config.update(user_config)
        except (json.JSONDecodeError, OSError):
            pass
    return config


def save_config(config: dict[str, Any]):
    ensure_dirs()
    config_file = CONFIG_DIR / "config.json"
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)


def load_cache() -> dict[str, Any]:
    ensure_dirs()
    cache_file = CACHE_DIR / "usage-cache.json"
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_cache(cache: dict[str, Any]):
    ensure_dirs()
    cache_file = CACHE_DIR / "usage-cache.json"
    with open(cache_file, "w") as f:
        json.dump(cache, f, indent=2)
