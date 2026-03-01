"""
GEDOS Telegram interface — Pilot and Copilot mode.
Handles /task, /status, /stop, /copilot, /memory, /web, /ask.
"""

import logging
from typing import Optional
from collections import defaultdict
from time import time

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from core.config import get_telegram_token, pilot_enabled, load_config
from core.copilot_context import analyze_context
from core.memory import (
    add_conversation,
    add_task as memory_add_task,
    get_recent_tasks,
    init_db as memory_init_db,
    get_recent_conversations,
)
from core.orchestrator import run_task_with_langgraph
from agents.terminal_agent import run_shell, TerminalResult
from agents.gui_agent import click_button
from tools.ax_tree import get_ax_tree

logger = logging.getLogger(__name__)

_current_task: Optional[str] = None
_task_status: str = "idle"
_task_cancelled: bool = False

_copilot_active: dict[int, bool] = {}
_last_app_per_user: dict[int, str] = {}
_last_copilot_message_per_user: dict[int, str] = {}

# Rate limiting: {user_id: [timestamp1, timestamp2, ...]}
_rate_limit_tracker: dict[int, list[float]] = defaultdict(list)
RATE_LIMIT_MAX = 10  # max commands per minute
RATE_LIMIT_WINDOW = 60.0  # seconds

_SHELL_SAFE_PREFIXES = (
    "ls", "pwd", "whoami", "date", "git ", "cat ", "echo ", "which ",
    "node ", "npm ", "python", "python3", "cd ", "head ", "tail ", "wc ",
)


def _looks_like_shell_command(payload: str) -> bool:
    line = payload.strip()
    if "\n" in line or len(line) > 500:
        return False
    low = line.lower()
    return any(low.startswith(p) for p in _SHELL_SAFE_PREFIXES) or low in ("ls", "pwd", "whoami", "date")


def _format_ax_tree(tree: dict) -> str:
    err = tree.get("error")
    if err:
        return f"Error: {err}"
    app = tree.get("app") or "?"
    lines = [f"App: {app}"]
    for w in (tree.get("windows") or [])[:5]:
        title = (w.get("title") or "").strip() or "(untitled)"
        lines.append(f"  Window: {title}")
    btns = tree.get("buttons") or []
    if btns:
        lines.append("Buttons: " + ", ".join((b.get("title") or b.get("role") or "?") for b in btns[:15]))
    return "\n".join(lines)


def _format_terminal_result(r: TerminalResult) -> str:
    out = (r.stdout or "").strip() or "(no output)"
    err = (r.stderr or "").strip()
    if len(out) > 3500:
        out = out[:3500] + "\n... (truncated)"
    if r.success:
        msg = f"✅ {r.command[:80]}\n\n{out}"
    elif r.return_code == 127:
        msg = f"❌ Command not found: {r.command[:80]}"
    elif "timed out" in err.lower():
        msg = f"⏱ {err}"
    else:
        msg = f"❌ {r.command[:80]} (code {r.return_code})\n\n{out}"
    if err and "timed out" not in err.lower():
        msg += f"\n\nstderr:\n{err[:500]}"
    return msg


def _user_id(update: Update) -> Optional[int]:
    if update.effective_user:
        return update.effective_user.id
    return None


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    uid = _user_id(update)
    
    # Check if first time user (no conversation history)
    if uid is not None:
        from core.memory import get_recent_conversations, init_db
        init_db()
        convos = get_recent_conversations(str(uid), limit=1)
        is_first_time = len(convos) == 0
    else:
        is_first_time = True

    if is_first_time:
        # Onboarding flow for new users
        welcome = (
            "👋 Welcome to Gedos!\n\n"
            "I'm your autonomous AI agent for macOS. I can execute terminal commands, "
            "control your GUI, browse the web, and answer questions using a local LLM.\n\n"
            "**Choose your mode:**\n\n"
            "🤖 **Pilot Mode** — Fully autonomous. Send me a task, leave, and I'll execute and report back.\n"
            "   Example: `/task git status`\n\n"
            "👥 **Copilot Mode** — Proactive assistant. I monitor your screen and suggest actions in real-time.\n"
            "   Enable with: `/copilot on`\n\n"
            "**Quick Start:**\n"
            "• `/task <description>` — Run any task\n"
            "• `/web <url>` — Browse the web\n"
            "• `/ask <question>` — Ask the LLM\n"
            "• `/help` — Full command list\n"
            "• `/ping` — Health check\n\n"
            "Try it now: `/task ls -la` or `/ask what is Python?`"
        )
        await update.message.reply_text(welcome)
        if uid is not None:
            add_conversation(str(uid), "/start", "First time onboarding sent")
    else:
        # Returning user
        welcome = (
            "Hi, I'm Gedos. Your autonomous agent on Mac.\n\n"
            "**Pilot Mode** — Send a task and I'll execute it.\n"
            "**Copilot Mode** — `/copilot on` — proactive suggestions.\n\n"
            "Commands:\n"
            "- `/task <description>` — Run a task\n"
            "- `/status` — Task status\n"
            "- `/stop` — Stop execution\n"
            "- `/copilot on|off` — Copilot Mode\n"
            "- `/memory` — Task history\n"
            "- `/web <url>` — Browse the web\n"
            "- `/ask <question>` — Ask the LLM\n"
            "- `/ping` — Health check\n"
            "- `/help` — List commands"
        )
        await update.message.reply_text(welcome)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    uid = _user_id(update)
    is_copilot_on = _copilot_active.get(uid, False) if uid is not None else False

    if is_copilot_on:
        # Copilot Mode help
        help_text = (
            "**Copilot Mode Active** 👥\n\n"
            "I'm monitoring your screen and will send proactive suggestions and warnings.\n\n"
            "**Commands:**\n"
            "/copilot off — Disable Copilot\n"
            "/task <description> — Run a task manually\n"
            "/status — Current task status\n"
            "/stop — Stop running task\n"
            "/memory — Task history\n"
            "/web <url> — Browse the web\n"
            "/ask <question> — Ask the LLM\n"
            "/ping — Health check\n\n"
            "**How Copilot works:**\n"
            "• Checks screen every 10 seconds\n"
            "• Detects active app (Terminal, VS Code, Safari, etc.)\n"
            "• Warns if errors appear on screen\n"
            "• Suggests next actions based on context"
        )
    else:
        # Pilot Mode help
        help_text = (
            "**Pilot Mode** 🤖\n\n"
            "Send me tasks and I'll execute them autonomously.\n\n"
            "**Commands:**\n"
            "/start — Welcome message\n"
            "/task <description> — Run a task\n"
            "/status — Current task status\n"
            "/stop — Stop running task\n"
            "/copilot on — Enable Copilot Mode\n"
            "/memory — Task history\n"
            "/web <url> — Browse the web\n"
            "/ask <question> — Ask the LLM\n"
            "/ping — Health check\n\n"
            "**Examples:**\n"
            "`/task ls -la`\n"
            "`/task git status`\n"
            "`/task navigate to google.com`\n"
            "`/ask what is Python?`\n\n"
            "Enable Copilot for real-time assistance: `/copilot on`"
        )
    await update.message.reply_text(help_text)


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _current_task, _task_status, _task_cancelled
    if not update.message or not update.message.text:
        return

    uid = _user_id(update)
    if uid is not None and not _check_rate_limit(uid):
        await update.message.reply_text("⚠️ Rate limit exceeded. Max 10 commands per minute.")
        return

    text = update.message.text.strip()
    payload = text[5:].strip() if text.lower().startswith("/task") else text
    if not payload:
        await update.message.reply_text("Usage: /task <task description>")
        return

    uid = _user_id(update)
    _current_task = payload
    _task_status = "running"
    _task_cancelled = False
    logger.info("Task received: %s", payload[:100])

    low = payload.lower()
    if any(kw in low for kw in ("list elements", "screen elements", "listar elementos", "ax tree", "what do you see", "o que você vê")):
        _task_status = "idle"
        tree = get_ax_tree(max_buttons=25, max_text_fields=10)
        reply = _format_ax_tree(tree)
        await update.message.reply_text(reply)
        if uid is not None:
            add_conversation(str(uid), payload, reply)
            memory_add_task(description=payload, status="completed", agent_used="gui", result=reply[:500])
        return

    if "clicar" in low or "click" in low:
        btn_name = None
        for prefix in ("clicar no botão ", "clicar no botao ", "click no botão ", "click no botao ",
                        "click the ", "click on ", "clicar no ", "click no ", "click "):
            if prefix in low:
                rest = low.split(prefix, 1)[-1].strip()
                btn_name = rest.split()[0] if rest else None
                break
        if not btn_name and len(payload.split()) >= 2:
            btn_name = payload.split()[-1].strip(".,")
        if btn_name:
            ok = click_button(btn_name)
            _task_status = "idle"
            reply = "Clicked the button." if ok else f"Button '{btn_name}' not found."
            await update.message.reply_text(reply)
            if uid is not None:
                add_conversation(str(uid), payload, reply)
                memory_add_task(description=payload, status="completed", agent_used="gui", result=reply)
            return

    if _looks_like_shell_command(payload):
        if _task_cancelled:
            _task_status = "idle"
            await update.message.reply_text("⚠️ Task cancelled.")
            return
        result = run_shell(payload)
        _task_status = "idle"
        reply = _format_terminal_result(result)
        await update.message.reply_text(reply)
        if uid is not None:
            add_conversation(str(uid), payload, reply[:500])
            memory_add_task(description=payload, status="completed" if result.success else "failed", agent_used="terminal", result=reply[:1000])
        return

    # Send progress message for long tasks
    progress_msg = await update.message.reply_text("⏳ Task started, executing...")
    try:
        if _task_cancelled:
            _task_status = "idle"
            await progress_msg.edit_text("⚠️ Task cancelled.")
            return
        out = run_task_with_langgraph(payload)
        if _task_cancelled:
            _task_status = "idle"
            await progress_msg.edit_text("⚠️ Task cancelled.")
            return
    except Exception as e:
        logger.exception("Orchestrator failed for task: %s", payload[:80])
        _task_status = "idle"
        reply = f"Execution error: {str(e)[:300]}"
        await progress_msg.edit_text(reply)
        if uid is not None:
            add_conversation(str(uid), payload, reply[:500])
            memory_add_task(description=payload, status="failed", agent_used="orchestrator", result=reply[:500])
        return
    _task_status = "idle"
    reply = out.get("result") or "No result."
    if len(reply) > 4000:
        reply = reply[:4000] + "\n... (truncated)"
    await progress_msg.edit_text(reply)
    if uid is not None:
        add_conversation(str(uid), payload, reply[:500])
        memory_add_task(description=payload, status="completed" if out.get("success") else "failed", agent_used=out.get("agent_used"), result=reply[:1000])
    return


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    global _current_task, _task_status
    if _task_status == "idle" or not _current_task:
        await update.message.reply_text("No task running.")
        return
    status_msg = f"Status: {_task_status}\nTask: {_current_task[:150]}"
    if len(_current_task) > 150:
        status_msg += "..."
    await update.message.reply_text(status_msg)


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _task_status, _task_cancelled
    if not update.message:
        return
    if _task_status == "running":
        _task_cancelled = True
        _task_status = "stopped"
        logger.info("Task cancellation requested")
        await update.message.reply_text("⚠️ Task cancellation requested. Will stop at next checkpoint.")
    else:
        await update.message.reply_text("No task is currently running.")


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Health check: /ping."""
    if update.message:
        await update.message.reply_text("pong")


async def cmd_copilot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggle Copilot Mode: /copilot on | /copilot off."""
    if not update.message or not update.message.text:
        return
    uid = _user_id(update)
    if uid is None:
        return
    text = update.message.text.strip().lower()
    if " off" in text or text.endswith("off"):
        _copilot_active[uid] = False
        await update.message.reply_text("Copilot Mode off.")
    else:
        _copilot_active[uid] = True
        await update.message.reply_text("Copilot Mode on. I'll monitor context and suggest when relevant.")


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent tasks from memory."""
    if not update.message:
        return
    tasks = get_recent_tasks(limit=10)
    if not tasks:
        await update.message.reply_text("No tasks in history.")
        return
    lines = ["Recent tasks:"]
    for t in tasks:
        lines.append(f"- [{t.status}] {t.description[:50]}..." if len(t.description) > 50 else f"- [{t.status}] {t.description}")
    await update.message.reply_text("\n".join(lines))


async def cmd_web(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Navigate to URL: /web https://example.com or /web example.com."""
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    url = text[5:].strip() if text.lower().startswith("/web") else text
    if not url:
        await update.message.reply_text("Usage: /web <url>")
        return
    from agents.web_agent import navigate
    r = navigate(url)
    if r.success:
        msg = f"Page loaded: {r.title or r.url}\n{r.url}"
        if r.content_preview:
            msg += "\n\n" + (r.content_preview[:500] + "..." if len(r.content_preview) > 500 else r.content_preview)
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text(f"Error: {r.message}")


async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask the LLM: /ask your question."""
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    question = text[4:].strip() if text.lower().startswith("/ask") else text
    if not question:
        await update.message.reply_text("Usage: /ask <question>")
        return
    from core.llm import complete
    reply = complete(question, max_tokens=1024)
    if len(reply) > 4000:
        reply = reply[:4000] + "\n... (truncated)"
    await update.message.reply_text(reply)


async def _copilot_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job: full Copilot — analyze context, send suggestions and warnings."""
    try:
        config = load_config()
        copilot_cfg = config.get("copilot") or {}
        suggestions_ok = copilot_cfg.get("suggestions", True)
        warnings_ok = copilot_cfg.get("warnings", True)
        if not suggestions_ok and not warnings_ok:
            return
        hints = analyze_context(warnings_enabled=warnings_ok, suggestions_enabled=suggestions_ok)
        if not hints:
            return
        hint = next((h for h in hints if h.kind == "warning"), hints[0])
        msg = f"Copilot: {hint.message}"
        app_name = hint.app or ""
        for uid, active in list(_copilot_active.items()):
            if not active:
                continue
            last_msg = _last_copilot_message_per_user.get(uid)
            if last_msg == msg:
                continue
            last_app = _last_app_per_user.get(uid)
            if hint.kind == "suggestion" and last_app == app_name:
                continue
            if app_name:
                _last_app_per_user[uid] = app_name
            try:
                await context.bot.send_message(chat_id=uid, text=msg)
                _last_copilot_message_per_user[uid] = msg
            except Exception:
                pass
    except Exception as e:
        logger.debug("Copilot job: %s", e)


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler — logs errors and recovers gracefully."""
    logger.error("Telegram error: %s", context.error, exc_info=context.error)
    if isinstance(update, Update) and update.message:
        try:
            await update.message.reply_text("An internal error occurred. Please try again.")
        except Exception:
            pass


def build_application() -> Application:
    token = get_telegram_token()
    config = load_config()
    telegram_cfg = config.get("telegram") or {}

    builder = Application.builder().token(token)
    builder.connect_timeout(telegram_cfg.get("connect_timeout", 30.0))
    builder.read_timeout(telegram_cfg.get("read_timeout", 30.0))
    builder.write_timeout(telegram_cfg.get("write_timeout", 30.0))
    app = builder.build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("task", cmd_task))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("copilot", cmd_copilot))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("web", cmd_web))
    app.add_handler(CommandHandler("ask", cmd_ask))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_error_handler(_error_handler)

    copilot_cfg = config.get("copilot") or {}
    interval = copilot_cfg.get("check_interval", 10)
    if app.job_queue and interval > 0:
        app.job_queue.run_repeating(_copilot_job, interval=interval, first=interval)

    return app


def run_polling() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    memory_init_db()
    if not pilot_enabled():
        logger.warning("Pilot mode is disabled in config.")
    app = build_application()
    logger.info("Gedos Telegram bot starting (polling)...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        poll_interval=1.0,
        timeout=30,
    )
