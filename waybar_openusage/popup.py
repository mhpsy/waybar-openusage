"""Click-to-show / right-click-to-hide popup for waybar-openusage."""

import sys
import subprocess
from pathlib import Path

from waybar_openusage.config import CACHE_DIR, load_config, load_cache
from waybar_openusage.plugins import ALL_PLUGINS

LOCK_FILE = CACHE_DIR / "popup.lock"

# Bar fills notification width (~42 chars in JetBrainsMono 13px / 360px wide)
BAR_WIDTH = 28


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


def _usage_color(fraction: float) -> str:
    if fraction >= 0.9:
        return "#f38ba8"
    if fraction >= 0.7:
        return "#f9e2af"
    if fraction >= 0.4:
        return "#89dceb"
    return "#a6e3a1"


def _progress_bar(fraction: float, color: str = "#a6e3a1") -> str:
    filled = round(fraction * BAR_WIDTH)
    empty = BAR_WIDTH - filled
    bar_filled = "━" * filled
    bar_empty = "━" * empty
    return f"<span color='{color}'>{bar_filled}</span><span color='#313244'>{bar_empty}</span>"


def _build_markup(cache: dict, config: dict) -> str:
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

        header = f"<span color='#cdd6f4'><b>{name}</b></span>"
        if plan:
            header += f"  <span color='#6c7086'><i>{plan}</i></span>"

        line_strs = []
        if error:
            line_strs.append(f"  <span color='#f38ba8'>⚠ {error}</span>")
        else:
            for line in entry.get("lines", []):
                ltype = line.get("type")
                if ltype == "progress":
                    used = line.get("used", 0)
                    limit = line.get("limit", 100)
                    fraction = min(1.0, used / limit) if limit > 0 else 0
                    color = _usage_color(fraction)

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

                    label = line.get("label", "")
                    line_strs.append(
                        f"  <span color='#bac2de'>{label}</span>"
                        f"  <b><span color='{color}'>{value}</span></b>"
                    )
                    line_strs.append(f"  {_progress_bar(fraction, color)}")

                    reset_str = _format_resets_at(line.get("resetsAt"))
                    if reset_str:
                        line_strs.append(
                            f"  <span color='#585b70'>↻ resets in {reset_str}</span>"
                        )

                elif ltype == "text":
                    label = line.get("label", "")
                    val = line.get("value", "")
                    line_strs.append(
                        f"  <span color='#bac2de'>{label}</span>  {val}"
                    )

                elif ltype == "badge":
                    text = line.get("text", "")
                    bcolor = line.get("color") or "#a6adc8"
                    line_strs.append(f"  <span color='{bcolor}'>● {text}</span>")

        sections.append(header + "\n" + "\n".join(line_strs))

    if not sections:
        return "<span color='#6c7086'>No usage data</span>"

    sep = "\n<span color='#45475a'>╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌</span>\n"
    return sep.join(sections)


def _show(cache: dict, config: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # Dismiss any existing openusage notification first
    subprocess.run(["swaync-client", "--close-latest"], capture_output=True, timeout=3)
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()

    markup = _build_markup(cache, config)
    # -t 0 = no auto-dismiss
    subprocess.run([
        "notify-send",
        "--app-name=openusage",
        "--urgency=low",
        "-t", "0",
        "AI Usage",
        markup,
    ], capture_output=True, timeout=3)
    LOCK_FILE.write_text("1")


def _hide():
    subprocess.run(["swaync-client", "--close-latest"], capture_output=True, timeout=3)
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "toggle"
    config = load_config()
    cache = load_cache()

    if action == "show":
        _show(cache, config)
    elif action == "hide":
        _hide()
    else:
        # toggle
        if LOCK_FILE.exists():
            _hide()
        else:
            _show(cache, config)


if __name__ == "__main__":
    main()
