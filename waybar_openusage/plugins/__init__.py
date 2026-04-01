"""Provider plugins for waybar-openusage."""

from waybar_openusage.plugins.claude import ClaudePlugin
from waybar_openusage.plugins.cursor import CursorPlugin
from waybar_openusage.plugins.copilot import CopilotPlugin
from waybar_openusage.plugins.codex import CodexPlugin
from waybar_openusage.plugins.windsurf import WindsurfPlugin
from waybar_openusage.plugins.gemini import GeminiPlugin
from waybar_openusage.plugins.amp import AmpPlugin
from waybar_openusage.plugins.kimi import KimiPlugin
from waybar_openusage.plugins.zai import ZaiPlugin
from waybar_openusage.plugins.minimax import MiniMaxPlugin
from waybar_openusage.plugins.jetbrains import JetBrainsPlugin
from waybar_openusage.plugins.opencode_go import OpenCodeGoPlugin
from waybar_openusage.plugins.factory import FactoryPlugin

ALL_PLUGINS = {
    "claude": ClaudePlugin,
    "cursor": CursorPlugin,
    "copilot": CopilotPlugin,
    "codex": CodexPlugin,
    "windsurf": WindsurfPlugin,
    "gemini": GeminiPlugin,
    "amp": AmpPlugin,
    "kimi": KimiPlugin,
    "zai": ZaiPlugin,
    "minimax": MiniMaxPlugin,
    "jetbrains-ai-assistant": JetBrainsPlugin,
    "opencode-go": OpenCodeGoPlugin,
    "factory": FactoryPlugin,
}


def get_plugin(plugin_id: str):
    cls = ALL_PLUGINS.get(plugin_id)
    if cls:
        return cls()
    return None
