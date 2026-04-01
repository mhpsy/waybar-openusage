"""Waybar output formatter — generates JSON for Waybar custom module."""

import json
from datetime import datetime, timezone

from waybar_openusage.plugin_base import PluginOutput, ProgressLine, TextLine, BadgeLine


def _progress_bar(fraction: float, width: int = 10) -> str:
    """Smooth progress bar using partial block characters."""
    full_blocks = int(fraction * width)
    remainder = (fraction * width) - full_blocks

    # Partial block chars: ▏▎▍▌▋▊▉█
    partials = " ▏▎▍▌▋▊▉█"
    partial_idx = int(remainder * 8)
    partial_char = partials[partial_idx] if full_blocks < width else ""

    filled = "█" * full_blocks
    empty_count = width - full_blocks - (1 if partial_char.strip() else 0)
    empty = "░" * max(0, empty_count)

    return filled + partial_char + empty


def _format_resets_at(resets_at: str | None) -> str:
    if not resets_at:
        return ""
    try:
        if isinstance(resets_at, (int, float)):
            dt = datetime.fromtimestamp(resets_at / 1000, tz=timezone.utc)
        else:
            dt = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
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


def _format_line_value(line) -> str:
    if isinstance(line, ProgressLine):
        fmt_kind = line.format.get("kind", "percent")
        if fmt_kind == "percent":
            return f"{line.used:.0f}%"
        elif fmt_kind == "dollars":
            return f"${line.used:.2f}/${line.limit:.2f}"
        elif fmt_kind == "count":
            suffix = line.format.get("suffix", "")
            return f"{line.used:.0f}/{line.limit:.0f} {suffix}".strip()
        return f"{line.used}/{line.limit}"
    elif isinstance(line, TextLine):
        return line.value
    elif isinstance(line, BadgeLine):
        return line.text
    return ""


def _usage_color(fraction: float) -> str:
    if fraction >= 0.9:
        return "#f38ba8"   # red (catppuccin)
    if fraction >= 0.7:
        return "#f9e2af"   # yellow
    if fraction >= 0.4:
        return "#89dceb"   # sky
    return "#a6e3a1"       # green


def format_tooltip(outputs: list[PluginOutput], display_mode: str = "used") -> str:
    """Generate a rich pango-markup tooltip for Waybar."""
    sections = []

    for output in outputs:
        if output.error and not any(not isinstance(l, BadgeLine) for l in output.lines):
            header = f"<b>{output.display_name}</b>"
            if output.plan:
                header += f"  <span color='#6c7086'>{output.plan}</span>"
            sections.append(f"{header}\n  <span color='#f38ba8'>{output.error}</span>")
            continue

        header = f"<b>{output.display_name}</b>"
        if output.plan:
            header += f"  <span color='#6c7086'>{output.plan}</span>"

        line_strs = []
        for line in output.lines:
            if isinstance(line, ProgressLine):
                fraction = line.fraction
                if display_mode == "left":
                    fraction = 1.0 - fraction

                bar = _progress_bar(fraction)
                value = _format_line_value(line)
                reset_str = _format_resets_at(line.resets_at)
                color = _usage_color(line.fraction)

                s = f"  <span color='{color}'>{bar}</span>  {line.label}  <b>{value}</b>"
                if reset_str:
                    s += f"  <span color='#585b70'>⟳ {reset_str}</span>"
                line_strs.append(s)

            elif isinstance(line, TextLine):
                line_strs.append(f"  <span color='#cdd6f4'>{line.label}</span>  {line.value}")

            elif isinstance(line, BadgeLine):
                color = line.color or "#a6adc8"
                line_strs.append(f"  <span color='{color}'>⬤ {line.text}</span>")

        sections.append(header + "\n" + "\n".join(line_strs))

    if not sections:
        return "No usage data"

    # Add a thin separator between sections
    return ("\n<span color='#313244'>─────────────────────────</span>\n").join(sections)


def format_waybar_text(outputs: list[PluginOutput], max_length: int = 50) -> str:
    """Generate the short text shown on the Waybar bar."""
    parts = []
    for output in outputs:
        primary = output.primary_progress
        if primary:
            parts.append(f"{output.display_name} {primary.used:.0f}%")
        elif output.error:
            parts.append(f"{output.display_name} !")

    if not parts:
        return "--"

    text = "  ".join(parts)
    if len(text) > max_length:
        text = text[:max_length - 1] + "…"
    return text


def format_waybar_class(outputs: list[PluginOutput]) -> str:
    """Generate CSS class based on highest usage level."""
    max_fraction = 0.0
    has_error = False
    for output in outputs:
        if output.error:
            has_error = True
        primary = output.primary_progress
        if primary:
            max_fraction = max(max_fraction, primary.fraction)

    if has_error and max_fraction == 0:
        return "error"
    if max_fraction >= 0.9:
        return "critical"
    if max_fraction >= 0.7:
        return "warning"
    return "normal"


def format_waybar_percentage(outputs: list[PluginOutput]) -> int:
    """Return the highest usage percentage across all providers."""
    max_pct = 0
    for output in outputs:
        primary = output.primary_progress
        if primary:
            max_pct = max(max_pct, int(primary.percent))
    return max_pct


def to_waybar_json(outputs: list[PluginOutput], config: dict) -> str:
    """Generate the final JSON output for Waybar custom module."""
    max_length = config.get("waybar_max_length", 50)
    display_mode = config.get("display_mode", "used")

    result = {
        "text": format_waybar_text(outputs, max_length),
        "tooltip": format_tooltip(outputs, display_mode),
        "class": format_waybar_class(outputs),
        "percentage": format_waybar_percentage(outputs),
    }
    return json.dumps(result)
