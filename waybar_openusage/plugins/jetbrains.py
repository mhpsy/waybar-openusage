"""JetBrains AI Assistant provider plugin — quota remaining."""

import json
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from waybar_openusage.plugin_base import (
    PluginOutput, ProgressLine, TextLine, BadgeLine, ProviderPlugin,
)

log = logging.getLogger("waybar-openusage")

# Linux path patterns
JETBRAINS_CONFIG_BASE = Path.home() / ".config" / "JetBrains"
QUOTA_FILE = "options/AIAssistantQuotaManager2.xml"

# Known IDE directory prefixes
IDE_PREFIXES = [
    "IntelliJIdea", "PyCharm", "WebStorm", "PhpStorm",
    "CLion", "GoLand", "Rider", "DataGrip", "RubyMine",
    "AndroidStudio", "DataSpell", "Fleet", "RustRover",
]


def _find_quota_file() -> Path | None:
    if not JETBRAINS_CONFIG_BASE.exists():
        return None
    # Find most recent IDE config dir
    best = None
    best_version = ""
    try:
        for entry in JETBRAINS_CONFIG_BASE.iterdir():
            if not entry.is_dir():
                continue
            for prefix in IDE_PREFIXES:
                if entry.name.startswith(prefix):
                    quota_path = entry / QUOTA_FILE
                    if quota_path.exists() and entry.name > best_version:
                        best = quota_path
                        best_version = entry.name
                    break
    except OSError:
        pass
    return best


def _parse_quota_xml(path: Path) -> dict | None:
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        for component in root.iter("component"):
            if component.get("name") == "AIAssistantQuotaManager2":
                for option in component.iter("option"):
                    if option.get("name") == "quotaInfo":
                        value = option.get("value", "")
                        if value:
                            return json.loads(value)
    except (ET.ParseError, json.JSONDecodeError, OSError) as e:
        log.warning(f"JetBrains quota parse failed: {e}")
    return None


class JetBrainsPlugin(ProviderPlugin):
    id = "jetbrains-ai-assistant"
    name = "JetBrains AI"
    brand_color = "#fc801d"

    def probe(self) -> PluginOutput:
        quota_file = _find_quota_file()
        if not quota_file:
            raise RuntimeError("No JetBrains IDE with AI Assistant found.")

        quota = _parse_quota_xml(quota_file)
        if not quota:
            raise RuntimeError("No quota data found in JetBrains config.")

        lines = []

        maximum = quota.get("maximum", 0)
        current = quota.get("current", 0)
        available = quota.get("available")

        # Scale credits (JetBrains stores them * 100000)
        scale = 100000
        if isinstance(maximum, (int, float)) and maximum > 0:
            max_scaled = maximum / scale
            current_scaled = current / scale if isinstance(current, (int, float)) else 0

            lines.append(ProgressLine(
                label="Quota",
                used=round(current_scaled, 1),
                limit=round(max_scaled, 1),
                format={"kind": "count", "suffix": "credits"},
                resets_at=quota.get("until"),
            ))

            if isinstance(available, (int, float)):
                avail_scaled = available / scale
                lines.append(TextLine(
                    label="Remaining",
                    value=f"{avail_scaled:.1f} credits",
                ))

        if not lines:
            lines.append(BadgeLine(label="Status", text="No usage data", color="#a3a3a3"))

        return PluginOutput(provider_id=self.id, display_name=self.name, lines=lines)
