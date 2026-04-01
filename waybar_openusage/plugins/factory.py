"""Factory / Droid provider plugin — standard, premium tokens."""

import json
import time
import logging
import base64
from pathlib import Path

import requests

from waybar_openusage.plugin_base import (
    PluginOutput, ProgressLine, BadgeLine, ProviderPlugin,
)

log = logging.getLogger("waybar-openusage")

USAGE_URL = "https://api.factory.ai/api/organization/subscription/usage"
REFRESH_URL = "https://api.workos.com/user_management/authenticate"

AUTH_FILE = Path.home() / ".factory" / "auth.json"
AUTH_ENCRYPTED_V2 = Path.home() / ".factory" / "auth.v2.file"
AUTH_ENCRYPTED_V2_KEY = Path.home() / ".factory" / "auth.v2.key"


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


def _load_auth():
    # Try plaintext first
    if AUTH_FILE.exists():
        try:
            data = json.loads(AUTH_FILE.read_text())
            if data.get("access_token"):
                return data
        except (json.JSONDecodeError, OSError):
            pass

    # Try encrypted v2 (requires cryptography library)
    if AUTH_ENCRYPTED_V2.exists() and AUTH_ENCRYPTED_V2_KEY.exists():
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            key = AUTH_ENCRYPTED_V2_KEY.read_bytes()
            encrypted = AUTH_ENCRYPTED_V2.read_bytes()
            # First 12 bytes = nonce, rest = ciphertext
            nonce = encrypted[:12]
            ciphertext = encrypted[12:]
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
            data = json.loads(plaintext)
            if data.get("access_token"):
                return data
        except Exception as e:
            log.warning(f"Factory v2 decryption failed: {e}")

    return None


def _needs_refresh(auth_data):
    token = auth_data.get("access_token")
    if not token:
        return True
    payload = _jwt_decode_payload(token)
    if not payload or not payload.get("exp"):
        return True
    return time.time() > payload["exp"] - 300


class FactoryPlugin(ProviderPlugin):
    id = "factory"
    name = "Factory"
    brand_color = "#f59e0b"

    def probe(self) -> PluginOutput:
        auth = _load_auth()
        if not auth or not auth.get("access_token"):
            raise RuntimeError("Not logged in. Sign in via Factory/Droid app.")

        access_token = auth["access_token"]

        resp = requests.get(USAGE_URL, headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }, timeout=10)

        if not resp.ok:
            raise RuntimeError(f"Usage request failed (HTTP {resp.status_code}).")

        data = resp.json()
        lines = []
        plan = None

        usage = data.get("usage") or data
        plan_name = data.get("planName") or data.get("plan")
        if plan_name:
            plan = str(plan_name).replace("_", " ").title()

        for key, label in [("standard", "Standard"), ("premium", "Premium")]:
            item = usage.get(key)
            if not item:
                continue
            used = item.get("used", 0)
            limit = item.get("limit", 0) or item.get("total", 0)
            if isinstance(used, (int, float)) and isinstance(limit, (int, float)) and limit > 0:
                lines.append(ProgressLine(
                    label=f"{label} tokens",
                    used=used,
                    limit=limit,
                    format={"kind": "count", "suffix": "tokens"},
                ))

        if not lines:
            lines.append(BadgeLine(label="Status", text="No usage data", color="#a3a3a3"))

        return PluginOutput(provider_id=self.id, display_name=self.name, plan=plan, lines=lines)
