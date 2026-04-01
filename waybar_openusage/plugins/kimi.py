"""Kimi Code provider plugin — session, weekly."""

import json
import time
import logging
from pathlib import Path

import requests

from waybar_openusage.plugin_base import (
    PluginOutput, ProgressLine, BadgeLine, ProviderPlugin,
)

log = logging.getLogger("waybar-openusage")

CRED_FILE = Path.home() / ".kimi" / "credentials" / "kimi-code.json"
USAGE_URL = "https://api.kimi.com/coding/v1/usages"
REFRESH_URL = "https://auth.kimi.com/api/oauth/token"


def _load_credentials():
    if not CRED_FILE.exists():
        return None
    try:
        return json.loads(CRED_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _needs_refresh(creds):
    expires_at = creds.get("expires_at")
    if not expires_at:
        return True
    return time.time() > expires_at - 300


def _refresh_token(creds):
    refresh_tok = creds.get("refresh_token")
    if not refresh_tok:
        return None
    try:
        resp = requests.post(REFRESH_URL, json={
            "grant_type": "refresh_token",
            "refresh_token": refresh_tok,
        }, timeout=15)
        if not resp.ok:
            return None
        body = resp.json()
        new_token = body.get("access_token")
        if not new_token:
            return None
        creds["access_token"] = new_token
        if body.get("refresh_token"):
            creds["refresh_token"] = body["refresh_token"]
        if isinstance(body.get("expires_in"), (int, float)):
            creds["expires_at"] = int(time.time() + body["expires_in"])
        try:
            CRED_FILE.write_text(json.dumps(creds, indent=2))
        except OSError:
            pass
        return new_token
    except requests.RequestException:
        return None


class KimiPlugin(ProviderPlugin):
    id = "kimi"
    name = "Kimi Code"
    brand_color = "#6366f1"

    def probe(self) -> PluginOutput:
        creds = _load_credentials()
        if not creds or not creds.get("access_token"):
            raise RuntimeError("Not logged in. Sign in via Kimi Code app.")

        access_token = creds["access_token"]

        if _needs_refresh(creds):
            refreshed = _refresh_token(creds)
            if refreshed:
                access_token = refreshed

        resp = requests.get(USAGE_URL, headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }, timeout=10)

        if resp.status_code == 401:
            refreshed = _refresh_token(creds)
            if refreshed:
                resp = requests.get(USAGE_URL, headers={
                    "Authorization": f"Bearer {refreshed}",
                    "Accept": "application/json",
                }, timeout=10)

        if not resp.ok:
            raise RuntimeError(f"Usage request failed (HTTP {resp.status_code}).")

        data = resp.json()
        lines = []

        five_hour = data.get("five_hour") or data.get("session")
        if five_hour and isinstance(five_hour.get("utilization"), (int, float)):
            lines.append(ProgressLine(
                label="Session",
                used=five_hour["utilization"],
                limit=100,
                format={"kind": "percent"},
                resets_at=five_hour.get("resets_at"),
                period_duration_ms=5 * 60 * 60 * 1000,
            ))

        seven_day = data.get("seven_day") or data.get("weekly")
        if seven_day and isinstance(seven_day.get("utilization"), (int, float)):
            lines.append(ProgressLine(
                label="Weekly",
                used=seven_day["utilization"],
                limit=100,
                format={"kind": "percent"},
                resets_at=seven_day.get("resets_at"),
                period_duration_ms=7 * 24 * 60 * 60 * 1000,
            ))

        if not lines:
            lines.append(BadgeLine(label="Status", text="No usage data", color="#a3a3a3"))

        return PluginOutput(provider_id=self.id, display_name=self.name, lines=lines)
