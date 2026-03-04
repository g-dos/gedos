#!/usr/bin/env python3
"""
GEDOS — entrypoint.
Starts the Telegram bot and runs until interrupted.
"""

__version__ = "0.9.6.2"

import argparse
import logging
import sys
import threading

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.traceback import install as install_rich_traceback

from core.config import load_config

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
        version=f"gedos {__version__}",
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
    return parser


def _banner(mode: str, config: dict) -> None:
    """Print a rich startup banner."""
    llm = (config.get("llm") or {})
    provider = llm.get("provider", "ollama")
    model = llm.get("model", "llama3.3")

    title = Text()
    title.append("GEDOS", style="bold cyan")
    title.append(f"  v{__version__}", style="dim")

    lines = Text()
    lines.append("Mode    ", style="bold")
    lines.append(mode.capitalize(), style="green" if mode == "pilot" else "yellow")
    lines.append("\n")
    lines.append("LLM     ", style="bold")
    lines.append(f"{provider} ({model})", style="dim")
    lines.append("\n")
    lines.append("Status  ", style="bold")
    lines.append("● Starting...", style="green")

    console.print(Panel(lines, title=title, border_style="cyan", expand=False))


def main() -> int:
    """Initialize logging, parse CLI args, and run the Telegram bot."""
    parser = _build_parser()
    args = parser.parse_args()

    try:
        config = load_config()
    except FileNotFoundError as e:
        console.print(f"[red bold]Error:[/] {e}")
        return 1

    if args.mcp:
        active_mode = "mcp"
    else:
        # Validate API keys before starting the Telegram interface
        from core.security import validate_api_keys
        if not validate_api_keys(config):
            console.print("[red bold]Error:[/] Missing required API keys. Check .env file.")
            return 1

        if args.mode:
            config.setdefault("modes", {})["pilot"] = args.mode == "pilot"
            config.setdefault("modes", {})["copilot"] = args.mode == "copilot"

        modes = config.get("modes") or {}
        if modes.get("copilot"):
            active_mode = "copilot"
        elif modes.get("pilot", True):
            active_mode = "pilot"
        else:
            active_mode = "pilot"

    level_name = (config.get("logging") or {}).get("level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=level,
    )

    if not args.mcp:
        _banner(active_mode, config)

    from core.memory_profiler import log_memory_stats
    log_memory_stats("startup")
    logger = logging.getLogger(__name__)
    logger.info("Gedos v%s starting (%s mode)", __version__, active_mode)

    try:
        if args.mcp:
            from core.mcp_server import run_mcp_server
            run_mcp_server()
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
