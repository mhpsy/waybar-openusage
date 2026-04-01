"""GitHub Copilot provider plugin — premium, chat, completions."""

import json
import logging
import subprocess
from pathlib import Path

import requests

from waybar_openusage.plugin_base import (
    PluginOutput, ProgressLine, BadgeLine, ProviderPlugin,
)

log = logging.getLogger("waybar-openusage")

USAGE_URL = "https://api.github.com/copilot_internal/user"

# Linux paths for gh CLI token
GH_HOSTS_FILE = Path.home() / ".config" / "gh" / "hosts.yml"


def _load_token() -> str | None:
    # Try gh CLI config
    try:
        if GH_HOSTS_FILE.exists():
            text = GH_HOSTS_FILE.read_text()
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("oauth_token:"):
                    token = stripped.split(":", 1)[1].strip()
                    if token:
                        return token
    except OSError:
        pass

    # Try `gh auth token` command
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


def _fetch_usage(token: str) -> requests.Response:
    return requests.get(USAGE_URL, headers={
        "Authorization": f"token {token}",
        "Accept": "application/json",
        "Editor-Version": "vscode/1.96.2",
        "Editor-Plugin-Version": "copilot-chat/0.26.7",
        "User-Agent": "GitHubCopilotChat/0.26.7",
        "X-Github-Api-Version": "2025-04-01",
    }, timeout=10)


class CopilotPlugin(ProviderPlugin):
    id = "copilot"
    name = "Copilot"
    brand_color = "#6e40c9"

    def probe(self) -> PluginOutput:
        token = _load_token()
        if not token:
            raise RuntimeError("Not logged in. Run `gh auth login` first.")

        resp = _fetch_usage(token)
        if resp.status_code in (401, 403):
            raise RuntimeError("Token invalid. Run `gh auth login` to re-authenticate.")
        if not resp.ok:
            raise RuntimeError(f"Usage request failed (HTTP {resp.status_code}).")

        data = resp.json()
        lines = []
        plan = None

        if data.get("copilot_plan"):
            plan = data["copilot_plan"].replace("_", " ").title()

        # Paid tier: quota_snapshots
        snapshots = data.get("quota_snapshots")
        if snapshots:
            premium = snapshots.get("premium_interactions")
            if premium and isinstance(premium.get("percent_remaining"), (int, float)):
                used_pct = min(100, max(0, 100 - premium["percent_remaining"]))
                lines.append(ProgressLine(
                    label="Premium",
                    used=round(used_pct, 1),
                    limit=100,
                    format={"kind": "percent"},
                    resets_at=data.get("quota_reset_date"),
                    period_duration_ms=30 * 24 * 60 * 60 * 1000,
                ))

            chat = snapshots.get("chat")
            if chat and isinstance(chat.get("percent_remaining"), (int, float)):
                used_pct = min(100, max(0, 100 - chat["percent_remaining"]))
                lines.append(ProgressLine(
                    label="Chat",
                    used=round(used_pct, 1),
                    limit=100,
                    format={"kind": "percent"},
                    resets_at=data.get("quota_reset_date"),
                    period_duration_ms=30 * 24 * 60 * 60 * 1000,
                ))

        # Free tier
        lq = data.get("limited_user_quotas")
        mq = data.get("monthly_quotas")
        if lq and mq:
            reset_date = data.get("limited_user_reset_date")
            for label, key in [("Chat", "chat"), ("Completions", "completions")]:
                remaining = lq.get(key)
                total = mq.get(key)
                if isinstance(remaining, (int, float)) and isinstance(total, (int, float)) and total > 0:
                    used_pct = min(100, max(0, round((total - remaining) / total * 100)))
                    lines.append(ProgressLine(
                        label=label,
                        used=used_pct,
                        limit=100,
                        format={"kind": "percent"},
                        resets_at=reset_date,
                        period_duration_ms=30 * 24 * 60 * 60 * 1000,
                    ))

        if not lines:
            lines.append(BadgeLine(label="Status", text="No usage data", color="#a3a3a3"))

        return PluginOutput(provider_id=self.id, display_name=self.name, plan=plan, lines=lines)
