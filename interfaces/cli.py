"""
GEDOS CLI Mode — local interactive shell when Telegram is not configured.
"""

from __future__ import annotations

from datetime import datetime
import json
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
from core.audit_log import read_recent_actions
from core.audit_log import log_action
from core.llm import complete
from core.memory import (
    add_context,
    cleanup_old_data,
    delete_user_data,
    get_custom_permissions,
    delete_all_patterns,
    delete_pattern,
    export_user_data,
    get_owner,
    get_patterns,
    get_permission_level,
    get_recent_context,
    get_recent_tasks,
    init_db,
    set_custom_permissions,
    set_permission_level,
)
from core.orchestrator import clear_stop, request_stop, run_task_with_langgraph
from core.setup_checklist import format_setup_checklist
from core.security import get_command_permission_action
from core.watchers.idle_watcher import record_user_input
from tools.voice_output import play_voice_response_locally

logger = logging.getLogger(__name__)

CLI_USER_ID = "cli"
_CLI_TASK_STATUS = "idle"
_CLI_CURRENT_TASK = ""
_CLI_COPILOT_ACTIVE = False
_CLI_COPILOT_SENSITIVITY = "medium"
_MAX_CLI_INPUT = 4000


def _sanitize_profile_value(value: str) -> str:
    """Keep profile values single-line and compact for GEDOS.md."""
    cleaned = " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())
    return cleaned[:120]


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


_CUSTOM_PERMISSION_FIELDS = (
    ("terminal_destructive", "Terminal — destructive commands (rm, mv, git push)?"),
    ("web_browsing", "Web browsing?"),
    ("filesystem_writes", "File system writes?"),
    ("package_install", "Install packages (pip, npm, brew)?"),
    ("github_operations", "GitHub operations (push, PR, commit)?"),
)


def _prompt_custom_permissions() -> dict[str, str]:
    """Collect granular permission choices in CLI mode."""
    choices = {"a": "allow", "c": "confirm", "b": "block"}
    permissions: dict[str, str] = {}
    for key, label in _CUSTOM_PERMISSION_FIELDS:
        while True:
            print(
                f"{label}\n"
                "  [A] Always allow  [C] Confirm each time  [B] Always block\n"
                "  > ",
                end="",
                flush=True,
            )
            answer = input().strip().lower()
            if answer in choices:
                permissions[key] = choices[answer]
                break
    print("✅ Custom permissions saved.\n   You can edit anytime with /permissions")
    return permissions


def _gedos_md_template(name: str, refer_as: str, permission_level: str) -> str:
    """Return the default GEDOS.md content."""
    return (
        "# GEDOS.md — Your personal Gedos configuration\n"
        "# Gedos reads this file on every startup.\n"
        "\n"
        "## About you\n"
        f"name: {_sanitize_profile_value(name)}\n"
        f"refer_as: {_sanitize_profile_value(refer_as)}\n"
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
        name = _sanitize_profile_value(input("What's your name? > "))

    print(
        "📋 Privacy notice:\n"
        "Gedos stores data locally on your Mac in ~/.gedos/gedos.db:\n"
        "• Your name and preferences\n"
        "• Task history\n"
        "• Learned behavioral patterns\n"
        "\n"
        "When using Claude/OpenAI API: task content is sent to\n"
        "their servers. Using Ollama keeps everything local.\n"
        "\n"
        "Commands: /export (download your data) /deletedata (erase all)\n"
    )
    input("Press Enter to continue...")

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
        refer_as = _sanitize_profile_value(input("Custom title > ")) or name
    elif refer_choice == "3":
        refer_as = "you"
    else:
        refer_as = name

    print(
        "Choose permission level:\n"
        "[1] Default (recommended)\n"
        "    Destructive commands require approval.\n"
        "\n"
        "[2] Custom\n"
        "    You choose exactly what requires approval.\n"
        "\n"
        "[3] Full Access (Elevated Risk)\n"
        "    No restrictions. Use with caution.\n"
        "Choice [1/2/3]: ",
        end="",
        flush=True,
    )
    permission_choice = input().strip()
    permission_level = "default"
    strict_shell = True
    custom_permissions: dict[str, str] = {}
    if permission_choice == "2":
        permission_level = "custom"
        custom_permissions = _prompt_custom_permissions()
    elif permission_choice == "3":
        permission_level = "full_access"
        strict_shell = False

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

    gedos_md_path: Optional[Path] = None
    try:
        gedos_md_path = _ensure_gedos_md(name, refer_as, permission_level)
    except OSError as exc:
        logger.warning("Could not create GEDOS.md: %s", exc)
    if gedos_md_path is not None:
        print("Open GEDOS.md to customize your experience? [y/N]: ", end="", flush=True)
        if input().strip().lower() == "y":
            subprocess.run(["open", str(gedos_md_path)], check=False)

    add_context(
        "cli_profile",
        {"user_id": CLI_USER_ID, "name": name, "refer_as": refer_as},
        user_id=CLI_USER_ID,
    )
    update_config({"security": {"strict_shell": strict_shell}})
    set_permission_level(CLI_USER_ID, permission_level)
    if permission_level == "custom":
        set_custom_permissions(CLI_USER_ID, custom_permissions)
    print(f"Welcome, {name}. CLI Mode is ready.")


def _export_dir() -> Path:
    """Return the local directory used for privacy exports."""
    path = Path.home() / ".gedos" / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_export_file() -> Path:
    """Write a user-data export file and return its path."""
    payload = export_user_data(CLI_USER_ID)
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    target = _export_dir() / f"gedos-export-{stamp}.json"
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def _help_text() -> str:
    """Return the exact CLI help output requested for demo mode."""
    from gedos import __version__

    profile = _latest_cli_profile()
    name = profile.get("name") or "there"
    return (
        "╭─────────────────────────────────────────────────────╮\n"
        f"│  Gedos v{__version__} — CLI Mode                        │\n"
        f"│  Hey {name}".ljust(54) + "│\n"
        "╰─────────────────────────────────────────────────────╯\n"
        "\n"
        "TASKS\n"
        "  /task <description>     Run any task\n"
        "  /status                 Current task status\n"
        "  /stop                   Cancel running task\n"
        "\n"
        "WEB\n"
        "  /web <url>              Browse and summarize a URL\n"
        "\n"
        "LLM\n"
        "  /ask <question>         Ask your LLM directly\n"
        "\n"
        "SCHEDULE\n"
        "  /schedule <when> <task> Schedule a recurring task\n"
        "  /schedules              List active schedules\n"
        "  /unschedule <id>        Remove a schedule\n"
        "\n"
        "MEMORY\n"
        "  /memory                 Recent task history\n"
        "  /patterns               Learned behavioral patterns\n"
        "  /forget <id|all>        Remove learned patterns\n"
        "  /export                 Export your local data as JSON\n"
        "  /deletedata             Permanently erase your local data\n"
        "\n"
        "COPILOT\n"
        "  /copilot on|off         Toggle proactive suggestions\n"
        "  /copilot status         Status and sensitivity\n"
        "  /copilot sensitivity    high | medium | low\n"
        "\n"
        "GITHUB\n"
        "  /github status          Webhook server status\n"
        "  /github connect         Setup instructions\n"
        "\n"
        "VOICE\n"
        "  /voice on|off|status    Toggle voice responses\n"
        "\n"
        "SYSTEM\n"
        "  /permissions            View and edit permission level\n"
        "  /config                 Open GEDOS.md in editor\n"
        "  /checklist              Validate local Gedos setup\n"
        "  /auditlog               Show last 20 audit log entries\n"
        "  /ping                   Health check\n"
        "  /clear                  Clear screen\n"
        "  /exit                   Quit Gedos\n"
        "\n"
        "MCP\n"
        "  Run: gedos --mcp\n"
        "  Exposes your Mac to Claude, Cursor, and any MCP client.\n"
        "  See: docs/mcp.md\n"
        "\n"
        "PILOT MODE\n"
        "  Add TELEGRAM_BOT_TOKEN to ~/.gedos/.env\n"
        "  Restart Gedos to enable autonomous remote execution."
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


def _permission_status_text() -> str:
    """Return the current CLI permission level and explanation."""
    level = get_permission_level(CLI_USER_ID) or ("default" if load_gedos_profile().get("level", "default") == "default" else "full_access")
    if level == "full_access":
        return "Permission level: Full Access\nDestructive commands run without approval."
    if level == "custom":
        permissions = get_custom_permissions(CLI_USER_ID)
        lines = ["Permission level: Custom", "Granular rules:"]
        for key, _ in _CUSTOM_PERMISSION_FIELDS:
            lines.append(f"- {key}: {permissions.get(key, 'confirm')}")
        return "\n".join(lines)
    return "Permission level: Default\nDestructive commands require approval."


def _set_permission(level: str) -> str:
    """Persist a permission level change to config and memory."""
    if level in {"full", "full_access"}:
        normalized = "full_access"
    elif level == "custom":
        normalized = "custom"
    else:
        normalized = "default"
    strict_shell = normalized != "full_access"
    update_config({"security": {"strict_shell": strict_shell}})
    set_permission_level(CLI_USER_ID, normalized)
    if normalized == "custom":
        set_custom_permissions(CLI_USER_ID, _prompt_custom_permissions())
        return "Permission level set to Custom."
    return "Permission level set to Full Access." if normalized == "full_access" else "Permission level set to Default."


def _confirm_cli_permission(detail: str) -> bool:
    """Prompt once for a confirm-style permission in CLI mode."""
    answer = input(f"{detail}\n[A] Allow once  [D] Deny > ").strip().lower()
    allowed = answer in {"a", "allow", "y", "yes"}
    log_action(
        "permission_requested",
        {"detail": detail},
        CLI_USER_ID,
        "allow" if allowed else "deny",
    )
    return allowed


def _format_patterns() -> str:
    """Return a CLI rendering of learned patterns."""
    patterns = get_patterns(CLI_USER_ID)
    if not patterns:
        return "No patterns learned yet. Keep using Gedos!"
    lines = [f"Learned patterns ({len(patterns)}):"]
    for index, pattern in enumerate(patterns, start=1):
        confidence = int(round((pattern.confidence or 0.0) * 100))
        lines.append(f"{index}. [{confidence}%] {pattern.trigger} -> {pattern.action}")
    return "\n".join(lines)


def _handle_schedule_command(text: str) -> str:
    """CLI wrappers for schedule commands."""
    from core.scheduler import (
        create_schedule,
        format_next_run,
        format_schedule_rule,
        get_scheduled_task_by_id,
        list_user_schedules,
        parse_schedule_command,
        remove_schedule,
        start_scheduler,
    )

    if text == "/schedule history":
        history = [task for task in get_recent_tasks(limit=20, user_id=CLI_USER_ID) if task.agent_used == "scheduler"][:5]
        if not history:
            return "📋 Schedule history (last 5):\nNo completed scheduled runs yet."
        lines = ["📋 Schedule history (last 5):"]
        for task in history:
            stamp = task.created_at.strftime("%a %b") + f" {task.created_at.day} at {task.created_at.strftime('%I:%M %p').lstrip('0')}"
            icon = "✅" if task.status == "completed" else "❌"
            lines.append(f"{icon} {task.description} — {stamp}")
        return "\n".join(lines)
    if text.startswith("/schedule "):
        schedule_data = parse_schedule_command(text)
        if not schedule_data:
            return "Invalid schedule format."
        try:
            start_scheduler()
            task = create_schedule(
                user_id=CLI_USER_ID,
                frequency=schedule_data["frequency"],
                schedule_time=schedule_data["time"],
                task_description=schedule_data["task"],
                day_of_week=schedule_data.get("day_of_week"),
                schedule_date=schedule_data.get("schedule_date"),
                schedule_times=schedule_data.get("times"),
                interval_minutes=schedule_data.get("interval_minutes"),
            )
        except RuntimeError as exc:
            if "no running event loop" in str(exc).lower():
                return "Scheduling is unavailable in CLI mode right now. Start Telegram mode to run background schedules."
            raise
        return f"Scheduled #{task.id}: {schedule_data.get('human_readable', task.task_description)}"
    if text == "/schedules":
        tasks = list_user_schedules(CLI_USER_ID)
        if not tasks:
            return "No active schedules."
        lines = [f"📅 Active schedules ({len(tasks)}):", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
        for task in tasks:
            lines.append(f"#{task.id}  {format_schedule_rule(task)}")
            lines.append(f"    {task.task_description}")
            lines.append(f"    Next: {format_next_run(task)}")
            lines.append("")
        if lines[-1] == "":
            lines.pop()
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("/unschedule <id> to remove")
        return "\n".join(lines)
    parts = text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return "Usage: /unschedule <id>"
    task = get_scheduled_task_by_id(int(parts[1]))
    if not task or task.user_id != CLI_USER_ID:
        return f"Schedule #{parts[1]} not found."
    removed = remove_schedule(task.id)
    return f"✅ Removed: {format_schedule_rule(task)} — {task.task_description}" if removed else f"Failed to remove schedule #{task.id}"


def _run_command(command: str, voice_enabled: bool) -> tuple[str, bool]:
    """Execute one CLI command and return (response, updated_voice_enabled)."""
    global _CLI_TASK_STATUS, _CLI_CURRENT_TASK, _CLI_COPILOT_ACTIVE, _CLI_COPILOT_SENSITIVITY
    raw_command = command or ""
    if len(raw_command) > _MAX_CLI_INPUT:
        return (f"Input too long. Max {_MAX_CLI_INPUT} characters.", voice_enabled)
    if any(ord(char) < 32 and char not in ("\n", "\r", "\t") for char in raw_command):
        return ("Unsupported control characters in input.", voice_enabled)
    text = (command or "").strip()
    if not text:
        return ("", voice_enabled)
    if text == "/help":
        return (_help_text(), voice_enabled)
    if text == "/exit":
        raise EOFError
    if text == "/stop":
        if _CLI_TASK_STATUS == "idle" or not _CLI_CURRENT_TASK:
            return ("No task running.", voice_enabled)
        request_stop()
        _CLI_TASK_STATUS = "stopped"
        return ("⛔ Stopped.", voice_enabled)
    if text == "/status":
        if _CLI_TASK_STATUS == "idle" or not _CLI_CURRENT_TASK:
            return ("No task running.", voice_enabled)
        return (f"Status: {_CLI_TASK_STATUS}\nTask: {_CLI_CURRENT_TASK}", voice_enabled)
    if text == "/ping":
        return ("pong\nMCP: available (run with --mcp)", voice_enabled)
    if text == "/checklist":
        return (format_setup_checklist(), voice_enabled)
    if text == "/auditlog":
        entries = read_recent_actions(limit=20)
        if not entries:
            return ("No audit log entries yet.", voice_enabled)
        lines = ["📜 Audit log (last 20):"]
        for entry in entries:
            timestamp = str(entry.get("timestamp") or "?")
            action = str(entry.get("action") or "unknown")
            result = str(entry.get("result") or "unknown")
            details = entry.get("details") or {}
            details_text = ""
            if isinstance(details, dict):
                command_value = details.get("command")
                reason_value = details.get("reason")
                if command_value:
                    details_text = f" | {str(command_value)[:80]}"
                elif reason_value:
                    details_text = f" | {str(reason_value)[:80]}"
            lines.append(f"{timestamp} | {action} | {result}{details_text}")
        return ("\n".join(lines), voice_enabled)
    if text == "/clear":
        subprocess.run(["clear"], check=False)
        return ("", voice_enabled)
    if text == "/config":
        subprocess.run(["open", str(get_gedos_md_path())], check=False)
        return (f"Opened {get_gedos_md_path()}", voice_enabled)
    if text == "/permissions":
        return (_permission_status_text(), voice_enabled)
    if text == "/permissions custom":
        return (_set_permission("custom"), voice_enabled)
    if text == "/permissions default":
        return (_set_permission("default"), voice_enabled)
    if text == "/permissions full":
        confirmation = input("Full Access is high risk. Type FULL to confirm > ").strip()
        if confirmation.upper() != "FULL":
            return ("Permission change cancelled.", voice_enabled)
        return (_set_permission("full_access"), voice_enabled)
    if text == "/voice on":
        play_voice_response_locally("Voice mode enabled. I'll respond by voice from now on.", "en")
        return ("Voice mode enabled. I'll respond by voice from now on.", True)
    if text == "/voice off":
        return ("Voice mode disabled. I'll respond in text only.", False)
    if text == "/voice status":
        return ("Voice mode is on." if voice_enabled else "Voice mode is off.", voice_enabled)
    if text == "/export":
        cleanup_old_data(CLI_USER_ID)
        path = _write_export_file()
        return (f"Export saved to {path}", voice_enabled)
    if text == "/deletedata":
        confirmation = input(
            "⚠️ This will permanently delete:\n"
            "- All task history\n"
            "- All learned patterns\n"
            "- All preferences\n"
            "- Your owner registration\n"
            "This cannot be undone. Type DELETE to confirm:\n> "
        ).strip()
        if confirmation != "DELETE":
            return ("Data deletion cancelled.", voice_enabled)
        delete_user_data(CLI_USER_ID)
        return ("Your local Gedos data has been deleted.", False)
    if text == "/memory":
        tasks = get_recent_tasks(limit=10, user_id=CLI_USER_ID)
        if not tasks:
            return ("No tasks in history.", voice_enabled)
        lines = ["Recent tasks:"]
        for task in tasks:
            lines.append(f"- [{task.status}] {task.description[:80]}")
        return ("\n".join(lines), voice_enabled)
    if text == "/patterns":
        return (_format_patterns(), voice_enabled)
    if text == "/forget":
        return ("Usage: /forget <id|all>", voice_enabled)
    if text.startswith("/forget "):
        arg = text.split(maxsplit=1)[1].strip().lower()
        if arg == "all":
            delete_all_patterns(CLI_USER_ID)
            return ("All learned patterns cleared.", voice_enabled)
        patterns = get_patterns(CLI_USER_ID)
        if not arg.isdigit():
            return ("Usage: /forget <id|all>", voice_enabled)
        index = int(arg)
        if index < 1 or index > len(patterns):
            return (f"Pattern #{index} not found.", voice_enabled)
        removed = delete_pattern(patterns[index - 1].id, CLI_USER_ID)
        return (f"Pattern #{index} removed." if removed else f"Pattern #{index} not found.", voice_enabled)
    if text == "/task":
        return ("Usage: /task <task description>", voice_enabled)
    if text == "/ask":
        return ("Usage: /ask <question>", voice_enabled)
    if text == "/web":
        return ("Usage: /web <url>", voice_enabled)
    if text == "/schedule":
        return ("Usage: /schedule <when> \"<task>\"", voice_enabled)
    if text == "/unschedule":
        return ("Usage: /unschedule <id>", voice_enabled)
    if text.startswith("/copilot "):
        lower = text.lower()
        if lower == "/copilot on":
            _CLI_COPILOT_ACTIVE = True
            return ("Copilot Mode on. I'll monitor context and suggest when relevant.", voice_enabled)
        if lower == "/copilot off":
            _CLI_COPILOT_ACTIVE = False
            return ("Copilot Mode off.", voice_enabled)
        if lower == "/copilot status":
            active = "yes" if _CLI_COPILOT_ACTIVE else "no"
            return (f"Copilot status\nActive: {active}\nSensitivity: {_CLI_COPILOT_SENSITIVITY}\nLast suggestion: never", voice_enabled)
        if lower.startswith("/copilot sensitivity "):
            requested = lower.split("/copilot sensitivity ", 1)[1].strip()
            if requested in {"high", "medium", "low"}:
                _CLI_COPILOT_SENSITIVITY = requested
                return (f"Copilot sensitivity set to {requested}.", voice_enabled)
            return ("Usage: /copilot sensitivity high|medium|low", voice_enabled)
    if text.startswith("/github "):
        from core.github_webhook import get_webhook_status

        status = get_webhook_status()
        lower = text.lower()
        if lower == "/github status":
            if status["running"]:
                return (f"GitHub webhook: running on port {status['port']}", voice_enabled)
            return (f"GitHub webhook: stopped (configured port {status['port']})", voice_enabled)
        if lower == "/github connect":
            return (
                "Connect your repo in GitHub:\n"
                "1. Settings -> Webhooks -> Add webhook\n"
                f"2. Payload URL: http://your-mac-ip:{status['port']}/webhook\n"
                "3. Content type: application/json\n"
                "4. Events: Workflow runs\n"
                "5. Set the same GITHUB_WEBHOOK_SECRET locally\n"
                f"6. If needed, expose port {status['port']} with ngrok\n\n"
                "Full guide: docs/github-webhook.md",
                voice_enabled,
            )
    if text.startswith("/schedule ") or text in {"/schedules"} or text.startswith("/unschedule "):
        return (_handle_schedule_command(text), voice_enabled)
    if text.startswith("/ask "):
        reply = complete(text[5:].strip(), language="en").strip()
        return (reply or "No result.", voice_enabled)
    if text.startswith("/web "):
        web_action = get_command_permission_action("", user_id=CLI_USER_ID, category_override="web_browsing")
        if web_action == "block":
            return ("Web browsing is blocked by your custom permissions.", voice_enabled)
        if web_action == "confirm" and not _confirm_cli_permission("Web browsing requires approval. Continue?"):
            return ("Web browsing denied.", voice_enabled)
        return (_format_web_result(text[5:].strip()), voice_enabled)
    task = text[6:].strip() if text.startswith("/task ") else text
    if text.startswith("/") and not text.startswith("/task "):
        return ("Unknown command. Use /help.", voice_enabled)
    command_action = get_command_permission_action(task, user_id=CLI_USER_ID)
    if command_action == "block":
        return ("This command is blocked by your custom permissions.", voice_enabled)
    if command_action == "confirm" and _looks_like_shell_command(task):
        if not _confirm_cli_permission(f"Command requires approval:\n{task}"):
            return ("Command denied.", voice_enabled)
    clear_stop()
    _CLI_TASK_STATUS = "running"
    _CLI_CURRENT_TASK = task
    result = run_task_with_langgraph(
        task,
        language="en",
        user_id=CLI_USER_ID,
        context={"time": datetime.utcnow()},
    )
    _CLI_TASK_STATUS = "idle"
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
            record_user_input(CLI_USER_ID)
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
