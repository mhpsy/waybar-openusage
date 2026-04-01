"""Codex (OpenAI) provider plugin — session, weekly, credits."""

import json
import os
import time
import logging
from pathlib import Path

import requests

from waybar_openusage.plugin_base import (
    PluginOutput, ProgressLine, TextLine, BadgeLine, ProviderPlugin,
)

log = logging.getLogger("waybar-openusage")

REFRESH_URL = "https://auth.openai.com/oauth/token"
USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
REFRESH_BUFFER_S = 5 * 60


def _find_auth_file() -> Path | None:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        p = Path(codex_home) / "auth.json"
        if p.exists():
            return p
    for candidate in [
        Path.home() / ".config" / "codex" / "auth.json",
        Path.home() / ".codex" / "auth.json",
    ]:
        if candidate.exists():
            return candidate
    return None


def _load_auth():
    auth_file = _find_auth_file()
    if not auth_file:
        return None
    try:
        data = json.loads(auth_file.read_text())
        if data.get("access_token"):
            return {"data": data, "path": auth_file}
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _save_auth(auth_data, path):
    try:
        path.write_text(json.dumps(auth_data, separators=(",", ":")))
    except OSError as e:
        log.error(f"Failed to write Codex auth: {e}")


def _needs_refresh(auth_data):
    expires_at = auth_data.get("expires_at")
    if not expires_at:
        return True
    return time.time() > expires_at - REFRESH_BUFFER_S


def _refresh_token(auth_data, path):
    refresh_tok = auth_data.get("refresh_token")
    if not refresh_tok:
        return None
    try:
        resp = requests.post(REFRESH_URL, json={
            "grant_type": "refresh_token",
            "refresh_token": refresh_tok,
            "client_id": "app_codex",
        }, timeout=15)
        if not resp.ok:
            return None
        body = resp.json()
        new_token = body.get("access_token")
        if not new_token:
            return None
        auth_data["access_token"] = new_token
        if body.get("refresh_token"):
            auth_data["refresh_token"] = body["refresh_token"]
        if body.get("id_token"):
            auth_data["id_token"] = body["id_token"]
        if isinstance(body.get("expires_in"), (int, float)):
            auth_data["expires_at"] = int(time.time() + body["expires_in"])
        _save_auth(auth_data, path)
        return new_token
    except requests.RequestException:
        return None


def _fmt_tokens(n: int) -> str:
    a = abs(n)
    sign = "-" if n < 0 else ""
    for threshold, divisor, suffix in [(1e9, 1e9, "B"), (1e6, 1e6, "M"), (1e3, 1e3, "K")]:
        if a >= threshold:
            scaled = a / divisor
            if scaled >= 10:
                return f"{sign}{round(scaled)}{suffix}"
            return f"{sign}{scaled:.1f}{suffix}".replace(".0" + suffix, suffix)
    return f"{sign}{round(a)}"


class CodexPlugin(ProviderPlugin):
    id = "codex"
    name = "Codex"
    brand_color = "#10a37f"

    def probe(self) -> PluginOutput:
        auth = _load_auth()
        if not auth:
            raise RuntimeError("Not logged in. Run `codex` to authenticate.")

        data = auth["data"]
        path = auth["path"]
        access_token = data["access_token"]

        if _needs_refresh(data):
            refreshed = _refresh_token(data, path)
            if refreshed:
                access_token = refreshed

        resp = requests.get(USAGE_URL, headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }, timeout=10)

        if resp.status_code == 401:
            refreshed = _refresh_token(data, path)
            if refreshed:
                access_token = refreshed
                resp = requests.get(USAGE_URL, headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                }, timeout=10)

        if not resp.ok:
            raise RuntimeError(f"Usage request failed (HTTP {resp.status_code}).")

        usage = resp.json()
        lines = []
        plan = None

        five_hour = usage.get("five_hour")
        if five_hour and isinstance(five_hour.get("utilization"), (int, float)):
            lines.append(ProgressLine(
                label="Session",
                used=five_hour["utilization"],
                limit=100,
                format={"kind": "percent"},
                resets_at=five_hour.get("resets_at"),
                period_duration_ms=5 * 60 * 60 * 1000,
            ))

        seven_day = usage.get("seven_day")
        if seven_day and isinstance(seven_day.get("utilization"), (int, float)):
            lines.append(ProgressLine(
                label="Weekly",
                used=seven_day["utilization"],
                limit=100,
                format={"kind": "percent"},
                resets_at=seven_day.get("resets_at"),
                period_duration_ms=7 * 24 * 60 * 60 * 1000,
            ))

        credits_info = usage.get("credits")
        if credits_info and isinstance(credits_info.get("remaining"), (int, float)):
            lines.append(TextLine(
                label="Credits",
                value=str(credits_info["remaining"]),
            ))

        if not lines:
            lines.append(BadgeLine(label="Status", text="No usage data", color="#a3a3a3"))

        return PluginOutput(provider_id=self.id, display_name=self.name, plan=plan, lines=lines)
