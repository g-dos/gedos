"""
GEDOS CLI Mode — local interactive shell when Telegram is not configured.
"""

from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import subprocess
from typing import Optional

from agents.web_agent import navigate
from core.config import (
    get_gedos_md_path,
    has_telegram_token,
    load_gedos_profile,
    update_config,
    write_env_value,
)
from core.llm import complete
from core.memory import add_context, get_owner, get_recent_context, get_recent_tasks, init_db
from core.orchestrator import clear_stop, request_stop, run_task_with_langgraph
from tools.voice_output import play_voice_response_locally

logger = logging.getLogger(__name__)

CLI_USER_ID = "cli"


def _latest_cli_profile() -> dict[str, str]:
    """Return the most recent stored CLI profile."""
    entries = get_recent_context(type_name="cli_profile", limit=20)
    for entry in entries:
        if entry.data.get("user_id") == CLI_USER_ID:
            return {
                "name": entry.data.get("name", "").strip(),
                "refer_as": entry.data.get("refer_as", "").strip(),
            }
    profile = load_gedos_profile()
    return {
        "name": str(profile.get("name") or "").strip(),
        "refer_as": str(profile.get("refer_as") or "").strip(),
    }


def _is_first_run() -> bool:
    """Treat missing Telegram token + no owner + no stored CLI profile as first run."""
    if has_telegram_token():
        return False
    if get_owner() is not None:
        return False
    profile = _latest_cli_profile()
    return not bool(profile.get("name"))


def _ollama_running() -> bool:
    """Check whether the local Ollama HTTP endpoint responds."""
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except Exception:
        return False


def _ollama_has_model() -> bool:
    """Check whether at least one Ollama model is available."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return False
    if result.returncode != 0:
        return False
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return len(lines) > 1


def _ensure_llm_available() -> None:
    """Guide the user through a local or remote LLM setup when needed."""
    if _ollama_running() and _ollama_has_model():
        return

    while True:
        print(
            "❌ No LLM configured.\n"
            "\n"
            "Choose how to proceed:\n"
            "[1] Install Ollama (local, free, private)\n"
            "    brew install ollama && ollama pull llama3.2\n"
            "[2] Use Claude API (requires API key)\n"
            "[3] Use OpenAI API (requires API key)\n"
            "\n"
            "Enter choice [1/2/3]: ",
            end="",
            flush=True,
        )
        choice = input().strip()
        if choice == "1":
            print("brew install ollama && ollama pull llama3.2")
            input("Press Enter after installing Ollama to re-check.")
            if _ollama_running() and _ollama_has_model():
                write_env_value("LLM_PROVIDER", "ollama")
                return
            continue
        if choice == "2":
            api_key = input("ANTHROPIC_API_KEY > ").strip()
            if api_key:
                write_env_value("LLM_PROVIDER", "claude")
                write_env_value("ANTHROPIC_API_KEY", api_key)
                return
            continue
        if choice == "3":
            api_key = input("OPENAI_API_KEY > ").strip()
            if api_key:
                write_env_value("LLM_PROVIDER", "openai")
                write_env_value("OPENAI_API_KEY", api_key)
                return


def _permission_level_to_config(choice: str) -> tuple[str, bool]:
    """Map onboarding permission choice to persisted values."""
    if choice == "2":
        return ("full_access", False)
    return ("default", True)


def _gedos_md_template(name: str, refer_as: str, permission_level: str) -> str:
    """Return the default GEDOS.md content."""
    return (
        "# GEDOS.md — Your personal Gedos configuration\n"
        "# Gedos reads this file on every startup.\n"
        "\n"
        "## About you\n"
        f"name: {name}\n"
        f"refer_as: {refer_as}\n"
        "\n"
        "## Preferences\n"
        "language: auto\n"
        "response_style: concise\n"
        "timezone: auto\n"
        "\n"
        "## Permissions\n"
        f"level: {permission_level}\n"
        "\n"
        "## Context\n"
        "# Tell Gedos about yourself and your work.\n"
        "# The more context here, the better the suggestions.\n"
        "\n"
        "## Blocked commands\n"
        "# Commands Gedos will never run.\n"
    )


def _ensure_gedos_md(name: str, refer_as: str, permission_level: str) -> Path:
    """Create ~/.gedos/GEDOS.md if it does not exist."""
    path = get_gedos_md_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(_gedos_md_template(name, refer_as, permission_level), encoding="utf-8")
    return path


def _run_onboarding() -> None:
    """Run the first-time CLI onboarding flow."""
    _ensure_llm_available()

    name = ""
    while not name:
        name = input("What's your name? > ").strip()

    print(
        "How should Gedos refer to you?\n"
        f"[1] {name}\n"
        f"[2] Custom title (e.g. Master {name})\n"
        "[3] Just 'you'\n"
        "Choice [1/2/3]: ",
        end="",
        flush=True,
    )
    refer_choice = input().strip()
    if refer_choice == "2":
        refer_as = input("Custom title > ").strip() or name
    elif refer_choice == "3":
        refer_as = "you"
    else:
        refer_as = name

    print(
        "Choose permission level:\n"
        "[1] Default (recommended) — destructive commands require approval\n"
        "[2] Full Access (Elevated Risk) — no restrictions\n"
        "Choice [1/2]: ",
        end="",
        flush=True,
    )
    permission_choice = input().strip()
    permission_level, strict_shell = _permission_level_to_config(permission_choice)

    print(
        "Enable Pilot Mode via Telegram? (optional)\n"
        "Add your bot token to enable remote autonomous execution.\n"
        "Token (or press Enter to skip): ",
        end="",
        flush=True,
    )
    token = input().strip()
    if token:
        write_env_value("TELEGRAM_BOT_TOKEN", token)

    gedos_md_path = _ensure_gedos_md(name, refer_as, permission_level)
    print("Open GEDOS.md to customize your experience? [y/N]: ", end="", flush=True)
    if input().strip().lower() == "y":
        subprocess.run(["open", str(gedos_md_path)], check=False)

    add_context(
        "cli_profile",
        {"user_id": CLI_USER_ID, "name": name, "refer_as": refer_as},
        user_id=CLI_USER_ID,
    )
    update_config({"security": {"strict_shell": strict_shell}})
    print(f"Welcome, {name}. CLI Mode is ready.")


def _help_text() -> str:
    """Return CLI help text."""
    return (
        "Commands:\n"
        "/help - show this help\n"
        "/task <description> - run a task\n"
        "/ask <question> - ask the LLM\n"
        "/web <url> - open a web page\n"
        "/memory - recent task history\n"
        "/voice on|off|status - CLI voice output\n"
        "/stop - request stop\n"
        "/exit - quit"
    )


def _format_web_result(url: str) -> str:
    """Navigate to a URL and format the result."""
    result = navigate(url)
    if not result.success:
        return result.message
    parts = [result.message]
    if result.title:
        parts.append(f"Title: {result.title}")
    if result.url:
        parts.append(f"URL: {result.url}")
    if result.content_preview:
        preview = result.content_preview[:500]
        if len(result.content_preview) > 500:
            preview += "..."
        parts.append(preview)
    return "\n".join(parts)


def _run_command(command: str, voice_enabled: bool) -> tuple[str, bool]:
    """Execute one CLI command and return (response, updated_voice_enabled)."""
    text = (command or "").strip()
    if not text:
        return ("", voice_enabled)
    if text == "/help":
        return (_help_text(), voice_enabled)
    if text == "/exit":
        raise EOFError
    if text == "/stop":
        request_stop()
        return ("⛔ Stopped.", voice_enabled)
    if text == "/voice on":
        play_voice_response_locally("Voice mode enabled. I'll respond by voice from now on.", "en")
        return ("Voice mode enabled. I'll respond by voice from now on.", True)
    if text == "/voice off":
        return ("Voice mode disabled. I'll respond in text only.", False)
    if text == "/voice status":
        return ("Voice mode is on." if voice_enabled else "Voice mode is off.", voice_enabled)
    if text == "/memory":
        tasks = get_recent_tasks(limit=10, user_id=CLI_USER_ID)
        if not tasks:
            return ("No tasks in history.", voice_enabled)
        lines = ["Recent tasks:"]
        for task in tasks:
            lines.append(f"- [{task.status}] {task.description[:80]}")
        return ("\n".join(lines), voice_enabled)
    if text.startswith("/ask "):
        return (complete(text[5:].strip(), language="en"), voice_enabled)
    if text.startswith("/web "):
        return (_format_web_result(text[5:].strip()), voice_enabled)

    task = text[6:].strip() if text.startswith("/task ") else text
    clear_stop()
    result = run_task_with_langgraph(
        task,
        language="en",
        user_id=CLI_USER_ID,
        context={"time": datetime.utcnow()},
    )
    return (result.get("result") or "No result.", voice_enabled)


def run_cli(initial_command: Optional[str] = None) -> None:
    """Start interactive CLI mode."""
    init_db()
    profile = _latest_cli_profile()
    if _is_first_run():
        _run_onboarding()
        profile = _latest_cli_profile()
    else:
        name = profile.get("name") or "there"
        print(f"Hey {name} 👋")

    voice_enabled = False
    pending_initial = (initial_command or "").strip()

    while True:
        try:
            if pending_initial:
                command = pending_initial
                pending_initial = ""
            else:
                command = input("> ")
            response, voice_enabled = _run_command(command, voice_enabled)
            if response:
                print(response)
                if voice_enabled:
                    play_voice_response_locally(response, "en")
        except EOFError:
            print("Goodbye.")
            break
        except KeyboardInterrupt:
            print("\nGoodbye.")
            break
        except Exception as exc:
            logger.exception("CLI command failed")
            print(f"Error: {exc}")
