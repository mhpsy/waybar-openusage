"""OpenCode Go provider plugin — 5h, weekly, monthly spend limits."""

import json
import sqlite3
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

from waybar_openusage.plugin_base import (
    PluginOutput, ProgressLine, BadgeLine, ProviderPlugin,
)

log = logging.getLogger("waybar-openusage")

AUTH_FILE = Path.home() / ".local" / "share" / "opencode" / "auth.json"
DB_FILE = Path.home() / ".local" / "share" / "opencode" / "opencode.db"


def _load_auth():
    if not AUTH_FILE.exists():
        return None
    try:
        data = json.loads(AUTH_FILE.read_text())
        return data.get("opencode-go")
    except (json.JSONDecodeError, OSError):
        return None


def _query_costs(hours: int) -> float:
    if not DB_FILE.exists():
        return 0.0
    try:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        since_str = since.isoformat()
        conn = sqlite3.connect(str(DB_FILE))
        cur = conn.execute(
            "SELECT COALESCE(SUM(cost), 0) FROM message "
            "WHERE provider_id = 'opencode-go' AND created_at >= ?",
            (since_str,),
        )
        row = cur.fetchone()
        conn.close()
        return float(row[0]) if row else 0.0
    except Exception as e:
        log.warning(f"OpenCode Go DB query failed: {e}")
        return 0.0


class OpenCodeGoPlugin(ProviderPlugin):
    id = "opencode-go"
    name = "OpenCode Go"
    brand_color = "#059669"

    def probe(self) -> PluginOutput:
        auth = _load_auth()
        if not auth:
            raise RuntimeError("Not logged in. Run `opencode auth` to authenticate.")

        lines = []

        limits = auth.get("limits", {})
        five_h_limit = limits.get("five_hour", 0)
        weekly_limit = limits.get("weekly", 0)
        monthly_limit = limits.get("monthly", 0)

        five_h_cost = _query_costs(5)
        weekly_cost = _query_costs(7 * 24)
        monthly_cost = _query_costs(30 * 24)

        if five_h_limit > 0:
            pct = min(100, (five_h_cost / five_h_limit) * 100)
            lines.append(ProgressLine(
                label="5h spend",
                used=round(pct, 1),
                limit=100,
                format={"kind": "percent"},
                period_duration_ms=5 * 60 * 60 * 1000,
            ))

        if weekly_limit > 0:
            pct = min(100, (weekly_cost / weekly_limit) * 100)
            lines.append(ProgressLine(
                label="Weekly spend",
                used=round(pct, 1),
                limit=100,
                format={"kind": "percent"},
                period_duration_ms=7 * 24 * 60 * 60 * 1000,
            ))

        if monthly_limit > 0:
            pct = min(100, (monthly_cost / monthly_limit) * 100)
            lines.append(ProgressLine(
                label="Monthly spend",
                used=round(pct, 1),
                limit=100,
                format={"kind": "percent"},
                period_duration_ms=30 * 24 * 60 * 60 * 1000,
            ))

        if not lines:
            lines.append(BadgeLine(label="Status", text="No usage data", color="#a3a3a3"))

        return PluginOutput(provider_id=self.id, display_name=self.name, lines=lines)
