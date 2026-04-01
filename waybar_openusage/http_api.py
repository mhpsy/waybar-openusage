"""Local HTTP API server — compatible with OpenUsage API on 127.0.0.1:6736."""

import json
import logging
import threading
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

from waybar_openusage.plugin_base import PluginOutput

log = logging.getLogger("waybar-openusage")

_cache: dict[str, dict] = {}
_cache_lock = threading.Lock()
_plugin_order: list[str] = []
_enabled_plugins: list[str] = []


def update_cache(outputs: list[PluginOutput], plugin_order: list[str], enabled: list[str]):
    global _plugin_order, _enabled_plugins
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with _cache_lock:
        _plugin_order = plugin_order
        _enabled_plugins = enabled
        for output in outputs:
            if not output.error:
                entry = output.to_dict()
                entry["fetchedAt"] = now
                _cache[output.provider_id] = entry


def get_cached_usage() -> list[dict]:
    with _cache_lock:
        result = []
        for pid in _plugin_order:
            if pid in _enabled_plugins and pid in _cache:
                result.append(_cache[pid])
        return result


def get_cached_provider(provider_id: str) -> dict | None:
    with _cache_lock:
        return _cache.get(provider_id)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default HTTP logging

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        path = self.path.rstrip("/")

        if path == "/v1/usage":
            data = get_cached_usage()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
            return

        if path.startswith("/v1/usage/"):
            provider_id = path[len("/v1/usage/"):]
            if not provider_id:
                self.send_response(404)
                self._cors_headers()
                self.end_headers()
                return
            entry = get_cached_provider(provider_id)
            if entry:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps(entry).encode())
            else:
                self.send_response(204)
                self._cors_headers()
                self.end_headers()
            return

        self.send_response(404)
        self._cors_headers()
        self.end_headers()


def start_server(port: int = 6736):
    server = HTTPServer(("127.0.0.1", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info(f"HTTP API listening on 127.0.0.1:{port}")
    return server
