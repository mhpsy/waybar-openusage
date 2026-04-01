"""Z.ai provider plugin — session, weekly, web searches."""

import os
import logging

import requests

from waybar_openusage.plugin_base import (
    PluginOutput, ProgressLine, BadgeLine, ProviderPlugin,
)

log = logging.getLogger("waybar-openusage")

SUBSCRIPTION_URL = "https://api.z.ai/api/biz/subscription/list"
QUOTA_URL = "https://api.z.ai/api/monitor/usage/quota/limit"


def _load_api_key() -> str | None:
    return os.environ.get("ZAI_API_KEY") or os.environ.get("GLM_API_KEY")


class ZaiPlugin(ProviderPlugin):
    id = "zai"
    name = "Z.ai"
    brand_color = "#2563eb"

    def probe(self) -> PluginOutput:
        api_key = _load_api_key()
        if not api_key:
            raise RuntimeError("Set ZAI_API_KEY or GLM_API_KEY environment variable.")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

        resp = requests.get(QUOTA_URL, headers=headers, timeout=10)
        if not resp.ok:
            raise RuntimeError(f"Usage request failed (HTTP {resp.status_code}).")

        data = resp.json()
        lines = []
        plan = None

        # Try subscription info
        try:
            sub_resp = requests.get(SUBSCRIPTION_URL, headers=headers, timeout=10)
            if sub_resp.ok:
                sub_data = sub_resp.json()
                subs = sub_data.get("data") or sub_data.get("result") or []
                if isinstance(subs, list) and subs:
                    plan = subs[0].get("planName") or subs[0].get("name")
        except Exception:
            pass

        quotas = data.get("data") or data.get("result") or data

        session = quotas.get("session") or quotas.get("five_hour")
        if session and isinstance(session.get("utilization"), (int, float)):
            lines.append(ProgressLine(
                label="Session",
                used=session["utilization"],
                limit=100,
                format={"kind": "percent"},
                resets_at=session.get("resets_at"),
                period_duration_ms=5 * 60 * 60 * 1000,
            ))

        weekly = quotas.get("weekly") or quotas.get("seven_day")
        if weekly and isinstance(weekly.get("utilization"), (int, float)):
            lines.append(ProgressLine(
                label="Weekly",
                used=weekly["utilization"],
                limit=100,
                format={"kind": "percent"},
                resets_at=weekly.get("resets_at"),
                period_duration_ms=7 * 24 * 60 * 60 * 1000,
            ))

        web_searches = quotas.get("web_searches") or quotas.get("webSearches")
        if web_searches:
            used = web_searches.get("used", 0)
            limit = web_searches.get("limit", 0)
            if isinstance(used, (int, float)) and isinstance(limit, (int, float)) and limit > 0:
                lines.append(ProgressLine(
                    label="Web searches",
                    used=used,
                    limit=limit,
                    format={"kind": "count", "suffix": "searches"},
                ))

        if not lines:
            lines.append(BadgeLine(label="Status", text="No usage data", color="#a3a3a3"))

        return PluginOutput(provider_id=self.id, display_name=self.name, plan=plan, lines=lines)
