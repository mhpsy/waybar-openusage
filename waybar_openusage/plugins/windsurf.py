"""Windsurf provider plugin — daily/weekly quota, extra usage."""

import json
import sqlite3
import logging
from pathlib import Path

import requests

from waybar_openusage.plugin_base import (
    PluginOutput, ProgressLine, TextLine, BadgeLine, ProviderPlugin,
)

log = logging.getLogger("waybar-openusage")

# Linux path
STATE_DB = Path.home() / ".config" / "Windsurf" / "User" / "globalStorage" / "state.vscdb"
USAGE_URL = "https://server.self-serve.windsurf.com/exa.seat_management_pb.SeatManagementService/GetUserStatus"


def _read_state_value(key: str) -> str | None:
    if not STATE_DB.exists():
        return None
    try:
        conn = sqlite3.connect(str(STATE_DB))
        cur = conn.execute("SELECT value FROM ItemTable WHERE key = ? LIMIT 1", (key,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        log.warning(f"Windsurf sqlite read failed for {key}: {e}")
        return None


def _load_api_key() -> str | None:
    raw = _read_state_value("windsurfAuthStatus")
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data.get("apiKey")
    except (json.JSONDecodeError, TypeError):
        return None


class WindsurfPlugin(ProviderPlugin):
    id = "windsurf"
    name = "Windsurf"
    brand_color = "#36b5a0"

    def probe(self) -> PluginOutput:
        api_key = _load_api_key()
        if not api_key:
            raise RuntimeError("Not logged in. Sign in via Windsurf app.")

        resp = requests.post(USAGE_URL, headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Connect-Protocol-Version": "1",
        }, json={}, timeout=10)

        if resp.status_code in (401, 403):
            raise RuntimeError("Token invalid. Sign in via Windsurf app.")
        if not resp.ok:
            raise RuntimeError(f"Usage request failed (HTTP {resp.status_code}).")

        data = resp.json()
        lines = []
        plan = None

        user_status = data.get("userStatus", data)
        plan_name = user_status.get("planName") or user_status.get("plan")
        if plan_name:
            plan = plan_name.replace("_", " ").title()

        quotas = user_status.get("quotas") or user_status.get("usage") or {}

        # Prompt credits
        prompt_credits = quotas.get("promptCredits") or quotas.get("dailyQuota")
        if prompt_credits:
            used = prompt_credits.get("used", 0)
            limit = prompt_credits.get("limit", 0) or prompt_credits.get("total", 0)
            if isinstance(used, (int, float)) and isinstance(limit, (int, float)) and limit > 0:
                pct = min(100, (used / limit) * 100)
                lines.append(ProgressLine(
                    label="Prompt credits",
                    used=round(pct, 1),
                    limit=100,
                    format={"kind": "percent"},
                    resets_at=prompt_credits.get("resetsAt"),
                    period_duration_ms=24 * 60 * 60 * 1000,
                ))

        # Flex credits
        flex_credits = quotas.get("flexCredits") or quotas.get("weeklyQuota")
        if flex_credits:
            used = flex_credits.get("used", 0)
            limit = flex_credits.get("limit", 0) or flex_credits.get("total", 0)
            if isinstance(used, (int, float)) and isinstance(limit, (int, float)) and limit > 0:
                pct = min(100, (used / limit) * 100)
                lines.append(ProgressLine(
                    label="Flex credits",
                    used=round(pct, 1),
                    limit=100,
                    format={"kind": "percent"},
                    resets_at=flex_credits.get("resetsAt"),
                    period_duration_ms=7 * 24 * 60 * 60 * 1000,
                ))

        # Extra usage balance
        extra_balance = quotas.get("extraUsageBalance")
        if extra_balance and isinstance(extra_balance, (int, float)):
            lines.append(TextLine(label="Extra balance", value=f"${extra_balance / 100:.2f}"))

        if not lines:
            lines.append(BadgeLine(label="Status", text="No usage data", color="#a3a3a3"))

        return PluginOutput(provider_id=self.id, display_name=self.name, plan=plan, lines=lines)
