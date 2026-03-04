#!/usr/bin/env python3
"""
GEDOS — entrypoint.
Starts the Telegram bot and runs until interrupted.
"""

__version__ = "0.9.12"

import argparse
import logging
import os
from typing import Optional
import sys
import threading

import requests
from rich.console import Console
from rich.traceback import install as install_rich_traceback

from core.config import has_telegram_token, load_config

console = Console()
install_rich_traceback(show_locals=False)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gedos",
        description="Gedos — autonomous AI agent for macOS",
    )
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"gedos v{__version__}",
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["pilot", "copilot"],
        default=None,
        help="startup mode (overrides config.yaml)",
    )
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="start Gedos as an MCP server over stdio",
    )
    parser.add_argument(
        "--webhook",
        action="store_true",
        help="start the GitHub webhook server alongside the Telegram bot",
    )
    parser.add_argument(
        "command",
        nargs="*",
        help=argparse.SUPPRESS,
    )
    return parser


def _banner(mode: str, config: dict) -> None:
    """Print the required ASCII banner and startup mode line."""
    llm = (config.get("llm") or {})
    model = llm.get("model", "llama3.3")
    banner = (
        "__                   __          \n"
        "\\ \\  ____ ____  ____/ /___  _____\n"
        " \\ \\/ __ `/ _ \\/ __  / __ \\/ ___/\n"
        " / / /_/ /  __/ /_/ / /_/ (__  ) \n"
        "/_/\\__, /\\___/\\__,_/\\____/____/  \n"
        "  /____/\n"
    )
    console.print(banner)
    mode_label = "CLI" if mode == "cli" else "Telegram"
    console.print(f"Mode: {mode_label} | LLM: {model} | v{__version__}")


def _runtime_mode(args, _config: dict) -> str:
    """Resolve the startup mode based on flags and configured Telegram token."""
    if args.mcp:
        return "mcp"
    if not has_telegram_token():
        return "cli"
    return "telegram"


def _register_proactive_sink(active_mode: str) -> None:
    """Register the best delivery sink for proactive notifications."""
    from core.proactive_engine import register_sink

    if active_mode == "cli":
        def _cli_sink(user_id: str, message: str, category: str, priority: str) -> None:
            console.print(f"\n[cyan]{message}[/]\n> ", end="")

        register_sink("cli", _cli_sink)
        return

    if active_mode == "telegram":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            return

        def _telegram_sink(user_id: str, message: str, category: str, priority: str) -> None:
            if not str(user_id).isdigit():
                return
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": int(user_id), "text": message[:4000]},
                timeout=15,
            )

        register_sink("telegram", _telegram_sink)


def _start_proactive_watchers(active_mode: str) -> None:
    """Start the proactive engine and all background watcher threads."""
    if active_mode not in {"cli", "telegram"}:
        return
    from core.watchers.github_watcher import run_github_watcher
    from core.watchers.idle_watcher import run_idle_watcher
    from core.watchers.morning_briefing import run_morning_briefing_watcher
    from core.watchers.system_watcher import run_system_watcher

    _register_proactive_sink(active_mode)
    watchers = (
        ("gedos-system-watcher", run_system_watcher),
        ("gedos-github-watcher", run_github_watcher),
        ("gedos-idle-watcher", run_idle_watcher),
        ("gedos-morning-briefing", run_morning_briefing_watcher),
    )
    for name, target in watchers:
        thread = threading.Thread(target=target, name=name, daemon=True)
        thread.start()
    logging.getLogger(__name__).info("✅ Proactive engine started (4 watchers active)")


def main() -> int:
    """Initialize logging, parse CLI args, and run the Telegram bot."""
    parser = _build_parser()
    args = parser.parse_args()
    cli_command = " ".join(getattr(args, "command", [])).strip() if hasattr(args, "command") else ""

    try:
        config = load_config()
    except FileNotFoundError as e:
        console.print(f"[red bold]Error:[/] {e}")
        return 1

    active_mode = _runtime_mode(args, config)
    if active_mode == "telegram":
        # Validate API keys before starting the Telegram interface
        from core.security import validate_api_keys
        if not validate_api_keys(config):
            console.print("[red bold]Error:[/] Missing required API keys. Check .env file.")
            return 1

        if args.mode:
            config.setdefault("modes", {})["pilot"] = args.mode == "pilot"
            config.setdefault("modes", {})["copilot"] = args.mode == "copilot"

    level_name = (config.get("logging") or {}).get("level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=level,
    )

    if active_mode in {"telegram", "cli"}:
        _banner(active_mode, config)

    from core.memory_profiler import log_memory_stats
    from core.memory import cleanup_all_users, init_db as memory_init_db

    memory_init_db()
    cleanup_all_users()
    log_memory_stats("startup")
    logger = logging.getLogger(__name__)
    logger.info("Gedos v%s starting (%s mode)", __version__, active_mode)

    try:
        if args.mcp:
            from core.mcp_server import run_mcp_server
            run_mcp_server()
        elif active_mode == "cli":
            from interfaces.cli import run_cli

            _start_proactive_watchers(active_mode)
            run_cli(initial_command=cli_command or None)
        else:
            if args.webhook:
                from core.github_webhook import get_webhook_status, run_github_webhook_server

                webhook_thread = threading.Thread(
                    target=run_github_webhook_server,
                    name="gedos-github-webhook",
                    daemon=True,
                )
                webhook_thread.start()
                webhook_status = get_webhook_status()
                logger.info("GitHub webhook listening on port %s", webhook_status["port"])
            _start_proactive_watchers(active_mode)
            from interfaces.telegram_bot import run_polling
            run_polling()
    except KeyboardInterrupt:
        if not args.mcp:
            console.print("\n[yellow]Gedos stopped.[/]")
    except Exception as e:
        if not args.mcp:
            console.print(f"\n[red bold]Fatal error:[/] {e}")
        logger.exception("Fatal error")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
