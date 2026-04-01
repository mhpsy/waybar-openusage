"""Cursor provider plugin — credits, total usage, auto, API, on-demand."""

import json
import sqlite3
import logging
import base64
from pathlib import Path

import requests

from waybar_openusage.plugin_base import (
    PluginOutput, ProgressLine, TextLine, BadgeLine, ProviderPlugin,
)

log = logging.getLogger("waybar-openusage")

# Linux path for Cursor's state DB
STATE_DB = Path.home() / ".config" / "Cursor" / "User" / "globalStorage" / "state.vscdb"
BASE_URL = "https://api2.cursor.sh"
USAGE_URL = BASE_URL + "/aiserver.v1.DashboardService/GetCurrentPeriodUsage"
PLAN_URL = BASE_URL + "/aiserver.v1.DashboardService/GetPlanInfo"
CREDITS_URL = BASE_URL + "/aiserver.v1.DashboardService/GetCreditGrantsBalance"
REFRESH_URL = BASE_URL + "/oauth/token"
REST_USAGE_URL = "https://cursor.com/api/usage"
STRIPE_URL = "https://cursor.com/api/auth/stripe"
CLIENT_ID = "KbZUR41cY7W6zRSdpSUJ7I7mLYBKOCmB"


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
        log.warning(f"Cursor sqlite read failed for {key}: {e}")
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


def _load_auth():
    access_token = _read_state_value("cursorAuth/accessToken")
    refresh_token = _read_state_value("cursorAuth/refreshToken")
    return access_token, refresh_token


def _refresh_token(refresh_tok: str) -> str | None:
    if not refresh_tok:
        return None
    try:
        resp = requests.post(REFRESH_URL, json={
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": refresh_tok,
        }, timeout=15)
        if resp.status_code in (400, 401):
            raise RuntimeError("Session expired. Sign in via Cursor app.")
        if not resp.ok:
            return None
        body = resp.json()
        if body.get("shouldLogout"):
            raise RuntimeError("Session expired. Sign in via Cursor app.")
        return body.get("access_token")
    except requests.RequestException as e:
        log.error(f"Cursor refresh exception: {e}")
        return None


def _connect_post(url: str, token: str) -> requests.Response:
    return requests.post(url, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Connect-Protocol-Version": "1",
    }, json={}, timeout=10)


def _build_session_token(access_token: str) -> tuple[str, str] | None:
    payload = _jwt_decode_payload(access_token)
    if not payload or not payload.get("sub"):
        return None
    parts = str(payload["sub"]).split("|")
    user_id = parts[1] if len(parts) > 1 else parts[0]
    if not user_id:
        return None
    session = f"{user_id}%3A%3A{access_token}"
    return user_id, session


def _fmt_dollars(cents) -> float:
    if isinstance(cents, (int, float)):
        return round(cents / 100, 2)
    return 0.0


class CursorPlugin(ProviderPlugin):
    id = "cursor"
    name = "Cursor"
    brand_color = "#00d4aa"

    def probe(self) -> PluginOutput:
        access_token, refresh_token = _load_auth()
        if not access_token and not refresh_token:
            raise RuntimeError("Not logged in. Sign in via Cursor app.")

        if access_token:
            payload = _jwt_decode_payload(access_token)
            if payload and payload.get("exp"):
                import time
                if time.time() > payload["exp"] - 300:
                    refreshed = _refresh_token(refresh_token)
                    if refreshed:
                        access_token = refreshed

        if not access_token:
            refreshed = _refresh_token(refresh_token)
            if not refreshed:
                raise RuntimeError("Not logged in. Sign in via Cursor app.")
            access_token = refreshed

        usage_resp = _connect_post(USAGE_URL, access_token)
        if usage_resp.status_code in (401, 403):
            refreshed = _refresh_token(refresh_token)
            if refreshed:
                access_token = refreshed
                usage_resp = _connect_post(USAGE_URL, access_token)
        if usage_resp.status_code in (401, 403):
            raise RuntimeError("Token expired. Sign in via Cursor app.")
        if not usage_resp.ok:
            raise RuntimeError(f"Usage request failed (HTTP {usage_resp.status_code}).")

        usage = usage_resp.json()

        # Get plan info
        plan_name = ""
        try:
            plan_resp = _connect_post(PLAN_URL, access_token)
            if plan_resp.ok:
                plan_data = plan_resp.json()
                plan_info = plan_data.get("planInfo", {})
                plan_name = plan_info.get("planName", "")
        except Exception:
            pass

        lines = []
        plan = plan_name.replace("_", " ").title() if plan_name else None

        pu = usage.get("planUsage")
        if not pu and usage.get("enabled") is not False:
            # Enterprise/team fallback
            session = _build_session_token(access_token)
            if session:
                user_id, session_tok = session
                try:
                    rest_resp = requests.get(
                        f"{REST_USAGE_URL}?user={user_id}",
                        headers={"Cookie": f"WorkosCursorSessionToken={session_tok}"},
                        timeout=10,
                    )
                    if rest_resp.ok:
                        rest_data = rest_resp.json()
                        gpt4 = rest_data.get("gpt-4", {})
                        if gpt4.get("maxRequestUsage", 0) > 0:
                            lines.append(ProgressLine(
                                label="Requests",
                                used=gpt4.get("numRequests", 0),
                                limit=gpt4["maxRequestUsage"],
                                format={"kind": "count", "suffix": "requests"},
                                period_duration_ms=30 * 24 * 60 * 60 * 1000,
                            ))
                except Exception:
                    pass

            if lines:
                return PluginOutput(provider_id=self.id, display_name=self.name, plan=plan, lines=lines)
            raise RuntimeError("No active Cursor subscription.")

        if not pu:
            raise RuntimeError("No active Cursor subscription.")

        # Credits
        try:
            credits_resp = _connect_post(CREDITS_URL, access_token)
            if credits_resp.ok:
                cg = credits_resp.json()
                if cg.get("hasCreditGrants"):
                    total = int(cg.get("totalCents", 0))
                    used = int(cg.get("usedCents", 0))
                    if total > 0:
                        lines.append(ProgressLine(
                            label="Credits",
                            used=_fmt_dollars(used),
                            limit=_fmt_dollars(total),
                            format={"kind": "dollars"},
                        ))
        except Exception:
            pass

        # Total usage
        billing_period_ms = 30 * 24 * 60 * 60 * 1000
        cycle_start = usage.get("billingCycleStart")
        cycle_end = usage.get("billingCycleEnd")
        if cycle_start and cycle_end:
            try:
                billing_period_ms = int(cycle_end) - int(cycle_start)
            except (ValueError, TypeError):
                pass

        resets_at = None
        if cycle_end:
            try:
                from datetime import datetime, timezone
                resets_at = datetime.fromtimestamp(int(cycle_end) / 1000, tz=timezone.utc).isoformat()
            except (ValueError, TypeError):
                pass

        has_limit = isinstance(pu.get("limit"), (int, float)) and pu["limit"] > 0
        has_percent = isinstance(pu.get("totalPercentUsed"), (int, float))

        if has_limit:
            total_spend = pu.get("totalSpend")
            if isinstance(total_spend, (int, float)):
                plan_used = total_spend
            else:
                plan_used = pu["limit"] - pu.get("remaining", 0)

            norm_plan = (plan_name or "").lower()
            if norm_plan == "team":
                lines.append(ProgressLine(
                    label="Total usage",
                    used=_fmt_dollars(plan_used),
                    limit=_fmt_dollars(pu["limit"]),
                    format={"kind": "dollars"},
                    resets_at=resets_at,
                    period_duration_ms=billing_period_ms,
                ))
            else:
                pct = (plan_used / pu["limit"]) * 100 if pu["limit"] > 0 else 0
                lines.append(ProgressLine(
                    label="Total usage",
                    used=round(pct, 1),
                    limit=100,
                    format={"kind": "percent"},
                    resets_at=resets_at,
                    period_duration_ms=billing_period_ms,
                ))
        elif has_percent:
            lines.append(ProgressLine(
                label="Total usage",
                used=round(pu["totalPercentUsed"], 1),
                limit=100,
                format={"kind": "percent"},
                resets_at=resets_at,
                period_duration_ms=billing_period_ms,
            ))

        # Auto usage
        auto_pct = pu.get("autoPercentUsed")
        if isinstance(auto_pct, (int, float)):
            lines.append(ProgressLine(
                label="Auto usage",
                used=round(auto_pct, 1),
                limit=100,
                format={"kind": "percent"},
                resets_at=resets_at,
                period_duration_ms=billing_period_ms,
            ))

        # API usage
        api_pct = pu.get("apiPercentUsed")
        if isinstance(api_pct, (int, float)):
            lines.append(ProgressLine(
                label="API usage",
                used=round(api_pct, 1),
                limit=100,
                format={"kind": "percent"},
                resets_at=resets_at,
                period_duration_ms=billing_period_ms,
            ))

        # On-demand
        su = usage.get("spendLimitUsage")
        if su:
            limit_val = su.get("individualLimit") or su.get("pooledLimit") or 0
            remaining = su.get("individualRemaining") or su.get("pooledRemaining") or 0
            if limit_val > 0:
                used_val = limit_val - remaining
                lines.append(ProgressLine(
                    label="On-demand",
                    used=_fmt_dollars(used_val),
                    limit=_fmt_dollars(limit_val),
                    format={"kind": "dollars"},
                ))

        if not lines:
            lines.append(BadgeLine(label="Status", text="No usage data", color="#a3a3a3"))

        return PluginOutput(provider_id=self.id, display_name=self.name, plan=plan, lines=lines)
