"""MiniMax provider plugin — session prompts."""

import os
import logging

import requests

from waybar_openusage.plugin_base import (
    PluginOutput, ProgressLine, BadgeLine, ProviderPlugin,
)

log = logging.getLogger("waybar-openusage")

GLOBAL_URLS = [
    "https://api.minimax.io/v1/api/openplatform/coding_plan/remains",
    "https://api.minimaxi.com/v1/api/openplatform/coding_plan/remains",
]
CN_URLS = [
    "https://api.minimaxi.com/v1/api/openplatform/coding_plan/remains",
    "https://api.minimax.io/v1/api/openplatform/coding_plan/remains",
]


def _load_api_key() -> tuple[str | None, bool]:
    cn_key = os.environ.get("MINIMAX_CN_API_KEY")
    if cn_key:
        return cn_key, True
    key = os.environ.get("MINIMAX_API_KEY") or os.environ.get("MINIMAX_API_TOKEN")
    if key:
        return key, False
    return None, False


class MiniMaxPlugin(ProviderPlugin):
    id = "minimax"
    name = "MiniMax"
    brand_color = "#8b5cf6"

    def probe(self) -> PluginOutput:
        api_key, is_cn = _load_api_key()
        if not api_key:
            raise RuntimeError("Set MINIMAX_API_KEY or MINIMAX_CN_API_KEY environment variable.")

        urls = CN_URLS if is_cn else GLOBAL_URLS
        resp = None
        for url in urls:
            try:
                resp = requests.get(url, headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                }, timeout=10)
                if resp.ok:
                    break
            except requests.RequestException:
                continue

        if not resp or not resp.ok:
            raise RuntimeError("Usage request failed. Check API key and connection.")

        data = resp.json()
        lines = []

        result = data.get("data") or data.get("result") or data
        remains = result.get("remains") or result.get("remaining")
        total = result.get("total") or result.get("limit")

        if isinstance(remains, (int, float)) and isinstance(total, (int, float)) and total > 0:
            used = total - remains
            lines.append(ProgressLine(
                label="Session",
                used=used,
                limit=total,
                format={"kind": "count", "suffix": "prompts"},
            ))

        if not lines:
            lines.append(BadgeLine(label="Status", text="No usage data", color="#a3a3a3"))

        return PluginOutput(provider_id=self.id, display_name=self.name, lines=lines)
