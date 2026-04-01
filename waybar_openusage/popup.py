"""Click-to-toggle popup for waybar-openusage using notify-send."""

import json
import os
import subprocess
import sys
from pathlib import Path

from waybar_openusage.config import CACHE_DIR, load_config, load_cache
from waybar_openusage.plugins import get_plugin, ALL_PLUGINS
from waybar_openusage.plugin_base import PluginOutput, ProgressLine, TextLine, BadgeLine

LOCK_FILE = CACHE_DIR / "popup.lock"


def _progress_bar(fraction: float, width: int = 15) -> str:
    filled = round(fraction * width)
    empty = width - filled
    return "█" * filled + "░" * empty


def _format_resets_at(resets_at) -> str:
    if not resets_at:
        return ""
    try:
        from datetime import datetime, timezone
        if isinstance(resets_at, (int, float)):
            dt = datetime.fromtimestamp(resets_at / 1000, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(str(resets_at).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = dt - now
        total_seconds = int(delta.total_seconds())
        if total_seconds <= 0:
            return "now"
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if hours > 24:
            days = hours // 24
            return f"{days}d {hours % 24}h"
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
    except (ValueError, TypeError, OSError):
        return ""


def _build_plain_text(cache: dict, config: dict) -> str:
    """Build plain-text popup content from cache."""
    enabled = config.get("enabled_plugins", [])
    order = config.get("plugin_order", list(ALL_PLUGINS.keys()))
    sections = []

    for pid in order:
        if pid not in enabled or pid not in cache:
            continue
        entry = cache[pid]
        name = entry.get("displayName", pid)
        plan = entry.get("plan", "")
        error = entry.get("error")

        header = f"━━ {name}"
        if plan:
            header += f"  ({plan})"
        header += " ━━"

        lines_strs = []
        if error:
            lines_strs.append(f"  ⚠ {error}")
        else:
            for line in entry.get("lines", []):
                ltype = line.get("type")
                if ltype == "progress":
                    used = line.get("used", 0)
                    limit = line.get("limit", 100)
                    fraction = min(1.0, used / limit) if limit > 0 else 0
                    bar = _progress_bar(fraction)

                    fmt = line.get("format", {})
                    kind = fmt.get("kind", "percent")
                    if kind == "percent":
                        value = f"{used:.0f}%"
                    elif kind == "dollars":
                        value = f"${used:.2f}/${limit:.2f}"
                    elif kind == "count":
                        suffix = fmt.get("suffix", "")
                        value = f"{used:.0f}/{limit:.0f} {suffix}".strip()
                    else:
                        value = f"{used}/{limit}"

                    reset_str = _format_resets_at(line.get("resetsAt"))
                    s = f"  {bar}  {line.get('label', '')}: {value}"
                    if reset_str:
                        s += f"  (resets {reset_str})"
                    lines_strs.append(s)

                elif ltype == "text":
                    lines_strs.append(f"  {line.get('label', '')}: {line.get('value', '')}")

                elif ltype == "badge":
                    lines_strs.append(f"  ● {line.get('text', '')}")

        sections.append(header + "\n" + "\n".join(lines_strs))

    return "\n\n".join(sections) if sections else "No usage data"


def _is_popup_visible() -> bool:
    return LOCK_FILE.exists()


def _show_popup(text: str):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Show notification
    subprocess.run([
        "notify-send",
        "--app-name=openusage",
        "--urgency=low",
        "AI Usage",
        text,
    ], capture_output=True, timeout=3)
    LOCK_FILE.write_text("1")


def _hide_popup():
    # Dismiss via swaync
    subprocess.run(["swaync-client", "--close-latest"],
                   capture_output=True, timeout=3)
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()


def toggle():
    """Toggle the usage popup on/off."""
    config = load_config()
    cache = load_cache()

    if _is_popup_visible():
        _hide_popup()
    else:
        text = _build_plain_text(cache, config)
        _show_popup(text)


def main():
    toggle()


if __name__ == "__main__":
    main()
