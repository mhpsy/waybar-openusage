"""Amp provider plugin — free balance, bonus, credits."""

import json
import logging
from pathlib import Path

import requests

from waybar_openusage.plugin_base import (
    PluginOutput, ProgressLine, TextLine, BadgeLine, ProviderPlugin,
)

log = logging.getLogger("waybar-openusage")

SECRETS_FILE = Path.home() / ".local" / "share" / "amp" / "secrets.json"
API_URL = "https://ampcode.com/api/internal"


def _load_api_key() -> str | None:
    if not SECRETS_FILE.exists():
        return None
    try:
        data = json.loads(SECRETS_FILE.read_text())
        return data.get("apiKey@https://ampcode.com/")
    except (json.JSONDecodeError, OSError):
        return None


class AmpPlugin(ProviderPlugin):
    id = "amp"
    name = "Amp"
    brand_color = "#ff6b35"

    def probe(self) -> PluginOutput:
        api_key = _load_api_key()
        if not api_key:
            raise RuntimeError("Not logged in. Sign in via Amp app.")

        resp = requests.post(API_URL, headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }, json={
            "method": "userDisplayBalanceInfo",
            "params": {},
        }, timeout=10)

        if resp.status_code in (401, 403):
            raise RuntimeError("Token invalid. Sign in via Amp app.")
        if not resp.ok:
            raise RuntimeError(f"Usage request failed (HTTP {resp.status_code}).")

        data = resp.json()
        result = data.get("result", data)
        lines = []
        plan = None

        # Free balance
        free = result.get("freeBalance") or result.get("free")
        if free:
            used = free.get("used", 0)
            limit = free.get("limit", 0) or free.get("total", 0)
            if isinstance(used, (int, float)) and isinstance(limit, (int, float)) and limit > 0:
                lines.append(ProgressLine(
                    label="Free",
                    used=used,
                    limit=limit,
                    format={"kind": "percent"},
                    resets_at=free.get("resetsAt"),
                ))

        # Bonus
        bonus = result.get("bonus") or result.get("bonusBalance")
        if bonus:
            pct = bonus.get("percent") or bonus.get("percentage")
            if isinstance(pct, (int, float)):
                lines.append(TextLine(label="Bonus", value=f"{pct}%"))

        # Credits
        credits_val = result.get("credits") or result.get("creditBalance")
        if credits_val:
            if isinstance(credits_val, (int, float)):
                lines.append(TextLine(label="Credits", value=str(credits_val)))
            elif isinstance(credits_val, dict):
                remaining = credits_val.get("remaining", credits_val.get("balance"))
                if remaining is not None:
                    lines.append(TextLine(label="Credits", value=str(remaining)))

        if not lines:
            lines.append(BadgeLine(label="Status", text="No usage data", color="#a3a3a3"))

        return PluginOutput(provider_id=self.id, display_name=self.name, plan=plan, lines=lines)
