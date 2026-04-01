"""Gemini provider plugin — pro, flash quota."""

import json
import time
import logging
import base64
from pathlib import Path

import requests

from waybar_openusage.plugin_base import (
    PluginOutput, ProgressLine, TextLine, BadgeLine, ProviderPlugin,
)

log = logging.getLogger("waybar-openusage")

OAUTH_CREDS = Path.home() / ".gemini" / "oauth_creds.json"
QUOTA_URL = "https://cloudcode-pa.googleapis.com/v1internal:retrieveUserQuota"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# Gemini CLI OAuth client credentials (public, embedded in npm package)
CLIENT_ID = "776949946489-j1mckv2b0q7vqcqvjgk2bnrjl3d0a0ri.apps.googleusercontent.com"
CLIENT_SECRET = "d-FL95Q19q7MQmFpd7hHD0Ty"


def _load_credentials():
    if not OAUTH_CREDS.exists():
        return None
    try:
        data = json.loads(OAUTH_CREDS.read_text())
        if data.get("access_token"):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return None


def _needs_refresh(creds):
    expiry = creds.get("expiry_date")
    if not expiry:
        return True
    return time.time() * 1000 > expiry - 5 * 60 * 1000


def _refresh_token(creds):
    refresh_tok = creds.get("refresh_token")
    if not refresh_tok:
        return None
    try:
        resp = requests.post(TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_tok,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        }, timeout=15)
        if not resp.ok:
            return None
        body = resp.json()
        new_token = body.get("access_token")
        if not new_token:
            return None
        creds["access_token"] = new_token
        if isinstance(body.get("expires_in"), (int, float)):
            creds["expiry_date"] = int(time.time() * 1000 + body["expires_in"] * 1000)
        try:
            OAUTH_CREDS.write_text(json.dumps(creds, indent=2))
        except OSError:
            pass
        return new_token
    except requests.RequestException:
        return None


def _jwt_decode_payload(token: str) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return None


class GeminiPlugin(ProviderPlugin):
    id = "gemini"
    name = "Gemini"
    brand_color = "#4285f4"

    def probe(self) -> PluginOutput:
        creds = _load_credentials()
        if not creds:
            raise RuntimeError("Not logged in. Run `gemini auth` to authenticate.")

        access_token = creds["access_token"]

        if _needs_refresh(creds):
            refreshed = _refresh_token(creds)
            if refreshed:
                access_token = refreshed

        # Get user email from id_token
        email = None
        id_token = creds.get("id_token")
        if id_token:
            payload = _jwt_decode_payload(id_token)
            if payload:
                email = payload.get("email")

        resp = requests.post(QUOTA_URL, headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }, json={}, timeout=10)

        if resp.status_code == 401:
            refreshed = _refresh_token(creds)
            if refreshed:
                access_token = refreshed
                resp = requests.post(QUOTA_URL, headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                }, json={}, timeout=10)

        if not resp.ok:
            raise RuntimeError(f"Quota request failed (HTTP {resp.status_code}).")

        data = resp.json()
        lines = []
        plan = None

        quotas = data.get("quotas") or data.get("userQuota") or {}

        # Try to extract tier info
        tier = data.get("tier") or data.get("accountType")
        if tier:
            plan = str(tier).replace("_", " ").title()

        # Parse quota entries
        for key, label in [("pro", "Pro"), ("flash", "Flash"), ("thinking", "Thinking")]:
            quota = quotas.get(key)
            if not quota:
                continue
            used = quota.get("used", 0)
            limit = quota.get("limit", 0) or quota.get("total", 0)
            if isinstance(used, (int, float)) and isinstance(limit, (int, float)) and limit > 0:
                pct = min(100, (used / limit) * 100)
                lines.append(ProgressLine(
                    label=label,
                    used=round(pct, 1),
                    limit=100,
                    format={"kind": "percent"},
                    resets_at=quota.get("resetsAt"),
                ))

        if email:
            lines.append(TextLine(label="Account", value=email))

        if not lines:
            lines.append(BadgeLine(label="Status", text="No usage data", color="#a3a3a3"))

        return PluginOutput(provider_id=self.id, display_name=self.name, plan=plan, lines=lines)
