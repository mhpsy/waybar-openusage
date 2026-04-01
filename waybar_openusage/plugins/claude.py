"""Claude provider plugin — session, weekly, extra usage, local token usage."""

import json
import time
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from waybar_openusage.plugin_base import (
    PluginOutput, ProgressLine, TextLine, BadgeLine, ProviderPlugin,
)

log = logging.getLogger("waybar-openusage")

CRED_FILE = Path.home() / ".claude" / ".credentials.json"
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
REFRESH_URL = "https://platform.claude.com/v1/oauth/token"
CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
SCOPES = "user:profile user:inference user:sessions:claude_code user:mcp_servers"
REFRESH_BUFFER_S = 5 * 60


def _load_credentials():
    if not CRED_FILE.exists():
        return None
    try:
        data = json.loads(CRED_FILE.read_text())
        oauth = data.get("claudeAiOauth")
        if oauth and oauth.get("accessToken"):
            return {"oauth": oauth, "full_data": data}
    except (json.JSONDecodeError, OSError) as e:
        log.warning(f"Claude credentials read failed: {e}")
    return None


def _save_credentials(full_data):
    try:
        CRED_FILE.write_text(json.dumps(full_data, separators=(",", ":")))
    except OSError as e:
        log.error(f"Failed to write Claude credentials: {e}")


def _needs_refresh(oauth):
    expires_at = oauth.get("expiresAt")
    if not expires_at:
        return True
    return time.time() * 1000 > expires_at - REFRESH_BUFFER_S * 1000


def _refresh_token(oauth, full_data):
    refresh_tok = oauth.get("refreshToken")
    if not refresh_tok:
        return None
    try:
        resp = requests.post(REFRESH_URL, json={
            "grant_type": "refresh_token",
            "refresh_token": refresh_tok,
            "client_id": CLIENT_ID,
            "scope": SCOPES,
        }, timeout=15)
        if resp.status_code in (400, 401):
            body = resp.json() if resp.text else {}
            if body.get("error") == "invalid_grant":
                raise RuntimeError("Session expired. Run `claude` to log in again.")
            raise RuntimeError("Token expired. Run `claude` to log in again.")
        if not resp.ok:
            return None
        body = resp.json()
        new_token = body.get("access_token")
        if not new_token:
            return None
        oauth["accessToken"] = new_token
        if body.get("refresh_token"):
            oauth["refreshToken"] = body["refresh_token"]
        if isinstance(body.get("expires_in"), (int, float)):
            oauth["expiresAt"] = int(time.time() * 1000 + body["expires_in"] * 1000)
        full_data["claudeAiOauth"] = oauth
        _save_credentials(full_data)
        return new_token
    except requests.RequestException as e:
        log.error(f"Claude refresh exception: {e}")
        return None


def _fetch_usage(access_token: str) -> requests.Response:
    return requests.get(USAGE_URL, headers={
        "Authorization": f"Bearer {access_token.strip()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "anthropic-beta": "oauth-2025-04-20",
        "User-Agent": "claude-code/2.1.69",
    }, timeout=10)


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


class ClaudePlugin(ProviderPlugin):
    id = "claude"
    name = "Claude"
    brand_color = "#d97706"

    def probe(self) -> PluginOutput:
        creds = _load_credentials()
        if not creds:
            raise RuntimeError("Not logged in. Run `claude` to authenticate.")

        oauth = creds["oauth"]
        full_data = creds["full_data"]
        access_token = oauth["accessToken"]

        if _needs_refresh(oauth):
            refreshed = _refresh_token(oauth, full_data)
            if refreshed:
                access_token = refreshed

        resp = _fetch_usage(access_token)
        if resp.status_code == 401:
            refreshed = _refresh_token(oauth, full_data)
            if refreshed:
                access_token = refreshed
                resp = _fetch_usage(access_token)
        if resp.status_code in (401, 403):
            raise RuntimeError("Token expired. Run `claude` to log in again.")
        if not resp.ok:
            raise RuntimeError(f"Usage request failed (HTTP {resp.status_code}).")

        data = resp.json()
        lines = []
        plan = None

        sub_type = oauth.get("subscriptionType")
        if sub_type:
            plan = sub_type.replace("_", " ").title()
            rlt = str(oauth.get("rateLimitTier", ""))
            import re
            m = re.search(r"(\d+)x", rlt)
            if m:
                plan += f" {m.group(1)}x"

        five_hour = data.get("five_hour")
        if five_hour and isinstance(five_hour.get("utilization"), (int, float)):
            lines.append(ProgressLine(
                label="Session",
                used=five_hour["utilization"],
                limit=100,
                format={"kind": "percent"},
                resets_at=five_hour.get("resets_at"),
                period_duration_ms=5 * 60 * 60 * 1000,
            ))

        seven_day = data.get("seven_day")
        if seven_day and isinstance(seven_day.get("utilization"), (int, float)):
            lines.append(ProgressLine(
                label="Weekly",
                used=seven_day["utilization"],
                limit=100,
                format={"kind": "percent"},
                resets_at=seven_day.get("resets_at"),
                period_duration_ms=7 * 24 * 60 * 60 * 1000,
            ))

        sonnet = data.get("seven_day_sonnet")
        if sonnet and isinstance(sonnet.get("utilization"), (int, float)):
            lines.append(ProgressLine(
                label="Sonnet",
                used=sonnet["utilization"],
                limit=100,
                format={"kind": "percent"},
                resets_at=sonnet.get("resets_at"),
                period_duration_ms=7 * 24 * 60 * 60 * 1000,
            ))

        extra = data.get("extra_usage")
        if extra and extra.get("is_enabled"):
            used = extra.get("used_credits")
            limit = extra.get("monthly_limit")
            if isinstance(used, (int, float)) and isinstance(limit, (int, float)) and limit > 0:
                lines.append(ProgressLine(
                    label="Extra usage",
                    used=round(used / 100, 2),
                    limit=round(limit / 100, 2),
                    format={"kind": "dollars"},
                ))
            elif isinstance(used, (int, float)) and used > 0:
                lines.append(TextLine(label="Extra usage", value=f"${used / 100:.2f}"))

        if not lines:
            lines.append(BadgeLine(label="Status", text="No usage data", color="#a3a3a3"))

        return PluginOutput(
            provider_id=self.id,
            display_name=self.name,
            plan=plan,
            lines=lines,
        )
