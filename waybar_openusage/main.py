"""Main entry point for waybar-openusage."""

import argparse
import json
import logging
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from waybar_openusage.config import load_config, save_cache, load_cache
from waybar_openusage.plugins import get_plugin, ALL_PLUGINS
from waybar_openusage.plugin_base import PluginOutput
from waybar_openusage.formatter import to_waybar_json
from waybar_openusage.http_api import start_server, update_cache

log = logging.getLogger("waybar-openusage")


def probe_all(config: dict) -> list[PluginOutput]:
    enabled = config.get("enabled_plugins", [])
    order = config.get("plugin_order", list(ALL_PLUGINS.keys()))
    outputs = []

    # Probe enabled plugins in parallel
    plugin_instances = {}
    for pid in order:
        if pid in enabled:
            plugin = get_plugin(pid)
            if plugin:
                plugin_instances[pid] = plugin

    with ThreadPoolExecutor(max_workers=min(len(plugin_instances), 8)) as executor:
        future_to_pid = {}
        for pid, plugin in plugin_instances.items():
            future = executor.submit(plugin.safe_probe)
            future_to_pid[future] = pid

        results = {}
        for future in as_completed(future_to_pid):
            pid = future_to_pid[future]
            try:
                results[pid] = future.result()
            except Exception as e:
                results[pid] = PluginOutput(
                    provider_id=pid,
                    display_name=pid.title(),
                    error=str(e),
                )

    # Maintain order
    for pid in order:
        if pid in results:
            outputs.append(results[pid])

    return outputs


def run_once(config: dict) -> str:
    outputs = probe_all(config)

    # Update HTTP API cache
    enabled = config.get("enabled_plugins", [])
    order = config.get("plugin_order", list(ALL_PLUGINS.keys()))
    update_cache(outputs, order, enabled)

    # Save to disk cache
    cache_data = {}
    for output in outputs:
        cache_data[output.provider_id] = output.to_dict()
    save_cache(cache_data)

    return to_waybar_json(outputs, config)


def run_continuous(config: dict):
    """Run in continuous mode for Waybar (output JSON, then wait, repeat)."""
    interval = config.get("refresh_interval_minutes", 15) * 60

    # Start HTTP API if enabled
    if config.get("http_api_enabled", True):
        port = config.get("http_api_port", 6736)
        try:
            start_server(port)
        except Exception as e:
            log.warning(f"Failed to start HTTP API: {e}")

    # SIGUSR1 triggers an immediate refresh
    refresh_event = threading.Event()
    signal.signal(signal.SIGUSR1, lambda *_: refresh_event.set())

    while True:
        try:
            output = run_once(config)
            print(output, flush=True)
        except Exception as e:
            # Output error state to Waybar
            error_output = json.dumps({
                "text": "󰚩 ⚠",
                "tooltip": f"Error: {e}",
                "class": "error",
                "percentage": 0,
            })
            print(error_output, flush=True)

        # Wait for interval or SIGUSR1
        refresh_event.wait(timeout=interval)
        refresh_event.clear()


def run_waybar(config: dict):
    """Run in Waybar exec mode (single output, exit)."""
    # Start HTTP API if enabled
    if config.get("http_api_enabled", True):
        port = config.get("http_api_port", 6736)
        try:
            start_server(port)
        except Exception:
            pass

    output = run_once(config)
    print(output)


def list_plugins():
    """List all available plugins."""
    for pid, cls in ALL_PLUGINS.items():
        plugin = cls()
        print(f"  {pid:25s} {plugin.name}")


def main():
    parser = argparse.ArgumentParser(
        description="Track AI coding subscription usage in Waybar",
    )
    parser.add_argument(
        "--mode", choices=["once", "continuous", "list"],
        default="once",
        help="Run mode: once (single output), continuous (for waybar exec), list (show plugins)",
    )
    parser.add_argument(
        "--plugins", nargs="*",
        help="Override enabled plugins (e.g. --plugins claude cursor)",
    )
    parser.add_argument(
        "--interval", type=int,
        help="Override refresh interval in minutes",
    )
    parser.add_argument(
        "--no-api", action="store_true",
        help="Disable the local HTTP API server",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose logging to stderr",
    )
    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stderr,
    )

    if args.mode == "list":
        print("Available plugins:")
        list_plugins()
        return

    config = load_config()

    # Apply CLI overrides
    if args.plugins is not None:
        config["enabled_plugins"] = args.plugins
    if args.interval is not None:
        config["refresh_interval_minutes"] = args.interval
    if args.no_api:
        config["http_api_enabled"] = False

    # Handle SIGTERM/SIGINT gracefully
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

    if args.mode == "continuous":
        run_continuous(config)
    else:
        run_waybar(config)


if __name__ == "__main__":
    main()
