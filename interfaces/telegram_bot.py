"""
GEDOS Telegram interface — Pilot and Copilot mode.
Handles /task, /status, /stop, /copilot, /memory, /web, /ask.
"""

import logging
from typing import Optional
from collections import defaultdict
from time import time

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from core.config import get_telegram_token, pilot_enabled, load_config
from core.copilot_context import analyze_context
from core.memory import (
    add_conversation,
    add_task as memory_add_task,
    get_recent_tasks,
    init_db as memory_init_db,
    get_recent_conversations,
    get_user_language,
)
from interfaces.i18n import t
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

# Error recovery state for multi-step tasks
_pending_step_decision: dict[int, dict] = {}  # {user_id: {step_info, callback}}

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


def _check_rate_limit(user_id: int) -> bool:
    """Check and update rate limit tracker for a user.

    Returns True if the user is allowed to execute a command, False if rate limit exceeded.
    """
    now = time()
    window_start = now - RATE_LIMIT_WINDOW
    timestamps = _rate_limit_tracker[user_id]
    # Remove timestamps outside the window
    valid = [t for t in timestamps if t >= window_start]
    _rate_limit_tracker[user_id] = valid
    if len(valid) >= RATE_LIMIT_MAX:
        return False
    valid.append(now)
    _rate_limit_tracker[user_id] = valid
    return True


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


def _user_lang(update: Update, text: Optional[str] = None) -> str:
    """Get user language. If text provided, detect and update cache. Else use cached."""
    uid = _user_id(update)
    if uid is None:
        return "en"
    if text:
        from tools.language import get_and_update_user_language
        return get_and_update_user_language(str(uid), text)
    return get_user_language(str(uid)) or "en"


async def _execute_step_with_recovery(step, step_num: int, steps_count: int, progress_msg, uid: Optional[int], update: Update, lang: str = "en") -> dict:
    """
    Execute a step with retry logic and user decision on failure.
    """
    import asyncio
    from core.orchestrator import _execute_single_step
    
    await progress_msg.edit_text(f"🔄 Step {step_num}/{steps_count}: {step.action[:50]}...")
    result = _execute_single_step(step.agent, step.action, step_obj=step, language=lang)

    if result.get('success', False):
        return result

    first_error = result.get('result', 'Unknown error')[:100]
    await progress_msg.edit_text(t("step_retry", lang, n=step_num, t=steps_count))

    retry_result = _execute_single_step(step.agent, step.action, step_obj=step, language=lang)
    
    # If retry succeeded, return success
    if retry_result.get('success', False):
        return retry_result
    
    retry_error = retry_result.get('result', 'Unknown error')[:100]
    decision_message = t("step_failed_continue", lang, n=step_num, err=retry_error)
    
    await progress_msg.edit_text(decision_message)
    
    # Set up user decision awaiting
    decision_future = asyncio.Future()
    
    async def handle_decision(continue_task: bool):
        if continue_task:
            decision_future.set_result({"success": False, "result": retry_error, "agent_used": step.agent})
        else:
            decision_future.set_result({"success": False, "result": retry_error, "cancelled": True})
    
    # Store the decision callback
    if uid is not None:
        _pending_step_decision[uid] = {
            "step_info": step,
            "callback": handle_decision
        }
    
    # Wait for user decision (with timeout)
    try:
        decision_result = await asyncio.wait_for(decision_future, timeout=300.0)  # 5 minute timeout
        return decision_result
    except asyncio.TimeoutError:
        # Clean up pending decision and continue
        if uid is not None and uid in _pending_step_decision:
            del _pending_step_decision[uid]
        return {"success": False, "result": "Decision timeout - continuing", "agent_used": step.agent}


async def _run_task_with_progress_updates(task: str, progress_msg, uid: Optional[int], update: Update, lang: str = "en") -> dict:
    """
    Execute a multi-step task with real-time progress updates to Telegram.
    """
    global _task_status, _task_cancelled
    
    try:
        from core.task_planner import plan_task
        from core.orchestrator import _execute_single_step
        
        plan = plan_task(task, language=lang)
        
        if not plan.is_multi_step or not plan.steps:
            from core.orchestrator import run_single_step_task
            return run_single_step_task(task, language=lang)

        steps_count = len(plan.steps)
        await progress_msg.edit_text(t("planning_complete", lang, n=steps_count))
        
        results = []
        overall_success = True
        agents_used = []
        
        # Execute each step with progress updates
        for i, step in enumerate(plan.steps):
            if _task_cancelled:
                _task_status = "idle"
                await progress_msg.edit_text(f"⚠️ Task cancelled at step {i+1}/{steps_count}.")
                return {"success": False, "result": "Task cancelled by user", "agent_used": "cancelled"}
            
            step_num = i + 1
            
            # Update progress before step
            step_desc = step.action[:50] + ("..." if len(step.action) > 50 else "")
            await progress_msg.edit_text(f"🔄 Step {step_num}/{steps_count}: {step_desc}")
            
            result = await _execute_step_with_recovery(
                step, step_num, steps_count, progress_msg, uid, update, lang
            )
            agents_used.append(result.get('agent_used', step.agent))
            
            if result.get('cancelled', False):
                _task_status = "idle"
                await progress_msg.edit_text(t("task_cancelled_user", lang, n=step_num, t=steps_count))
                return {"success": False, "result": "Task cancelled by user", "agent_used": "cancelled"}
            
            # Update progress after step
            if result.get('success', False):
                step_result = result.get('result', 'Completed')[:100]
                await progress_msg.edit_text(f"✅ Step {step_num}/{steps_count}: {step_result}")
                results.append(f"Step {step_num}: ✅ {step_result}")
            else:
                step_error = result.get('result', 'Unknown error')[:100]
                results.append(f"Step {step_num}: ❌ {step_error}")
                overall_success = False
        
        # Final summary
        _task_status = "idle"
        success_count = sum(1 for r in results if "✅" in r)
        failure_count = len(results) - success_count
        
        summary = (t("task_completed", lang) if overall_success else t("task_finished_errors", lang)) + "\n\n"
        summary += f"Steps: {success_count} successful, {failure_count} failed\n\n"
        summary += "\n".join(results)
        
        if len(summary) > 4000:
            summary = summary[:4000] + "\n... (truncated)"
            
        await progress_msg.edit_text(summary)
        
        # Store in memory
        if uid is not None:
            add_conversation(str(uid), task, summary[:500])
            agents_summary = ", ".join(set(agents_used))
            memory_add_task(
                description=task, 
                status="completed" if overall_success else "failed", 
                agent_used=f"multi-step ({agents_summary})", 
                result=summary[:1000]
            )
        
        return {
            "success": overall_success,
            "result": summary,
            "agent_used": f"multi-step ({', '.join(set(agents_used))})",
            "steps_completed": len(results)
        }
        
    except Exception as e:
        logger.exception("Multi-step task execution failed")
        error_msg = f"Multi-step planning error: {str(e)[:300]}"
        await progress_msg.edit_text(f"❌ {error_msg}")
        return {"success": False, "result": error_msg, "agent_used": "planner"}


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
            "/schedule — Create scheduled tasks\n"
            "/schedules — List active schedules\n" 
            "/unschedule <id> — Remove a schedule\n"
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
            "/schedule — Create scheduled tasks\n"
            "/schedules — List active schedules\n"
            "/unschedule <id> — Remove a schedule\n"
            "/ping — Health check\n\n"
            "**Examples:**\n"
            "`/task ls -la`\n"
            "`/task git status`\n"
            "`/task navigate to google.com`\n"
            "`/ask what is Python?`\n"
            "`/schedule daily 09:00 \"check HN and summarize\"`\n"
            "`/schedule weekly monday 14:00 \"backup files\"`\n\n"
            "Enable Copilot for real-time assistance: `/copilot on`"
        )
    await update.message.reply_text(help_text)


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _current_task, _task_status, _task_cancelled
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    lang = _user_lang(update, text)
    uid = _user_id(update)
    if uid is not None and not _check_rate_limit(uid):
        await update.message.reply_text(t("rate_limit", lang))
        return

    payload = text[5:].strip() if text.lower().startswith("/task") else text
    if not payload:
        await update.message.reply_text(t("usage_task", lang))
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

    # Check if this is a multi-step task for enhanced progress reporting
    try:
        from core.task_planner import _is_multi_step_task
        is_multi_step = _is_multi_step_task(payload)
    except ImportError:
        is_multi_step = False

    if is_multi_step:
        progress_msg = await update.message.reply_text(t("planning", lang))
        try:
            if _task_cancelled:
                _task_status = "idle"
                await progress_msg.edit_text(t("task_cancelled", lang))
                return

            out = await _run_task_with_progress_updates(payload, progress_msg, uid, update, lang)
            
        except Exception as e:
            logger.exception("Multi-step task failed: %s", payload[:80])
            _task_status = "idle"
            reply = f"Multi-step execution error: {str(e)[:300]}"
            await progress_msg.edit_text(reply)
            if uid is not None:
                add_conversation(str(uid), payload, reply[:500])
                memory_add_task(description=payload, status="failed", agent_used="orchestrator", result=reply[:500])
            return
    else:
        progress_msg = await update.message.reply_text(t("task_started", lang))
        try:
            if _task_cancelled:
                _task_status = "idle"
                await progress_msg.edit_text(t("task_cancelled", lang))
                return
            out = run_task_with_langgraph(payload, language=lang)
            if _task_cancelled:
                _task_status = "idle"
                await progress_msg.edit_text(t("task_cancelled", lang))
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
    lang = _user_lang(update)
    global _current_task, _task_status
    if _task_status == "idle" or not _current_task:
        await update.message.reply_text(t("no_task_running", lang))
        return
    status_msg = f"Status: {_task_status}\nTask: {_current_task[:150]}"
    if len(_current_task) > 150:
        status_msg += "..."
    await update.message.reply_text(status_msg)


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _task_status, _task_cancelled
    if not update.message:
        return
    lang = _user_lang(update)
    if _task_status == "running":
        _task_cancelled = True
        _task_status = "stopped"
        logger.info("Task cancellation requested")
        await update.message.reply_text(t("task_cancelled", lang))
    else:
        await update.message.reply_text(t("no_task_running", lang))


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Health check: /ping."""
    if update.message:
        lang = _user_lang(update)
        await update.message.reply_text(t("pong", lang))


async def cmd_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user decision to continue after step failure."""
    uid = _user_id(update)
    lang = _user_lang(update)
    if uid is None or uid not in _pending_step_decision:
        await update.message.reply_text(t("no_pending_decision", lang))
        return
    
    # Get the pending decision and continue execution
    decision_info = _pending_step_decision.pop(uid)
    await decision_info["callback"](True)  # Continue with next step


async def cmd_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user decision to cancel after step failure."""
    uid = _user_id(update)
    lang = _user_lang(update)
    if uid is None or uid not in _pending_step_decision:
        await update.message.reply_text(t("no_pending_decision", lang))
        return

    # Get the pending decision and cancel execution
    decision_info = _pending_step_decision.pop(uid)
    await decision_info["callback"](False)  # Cancel execution


def _is_background_noise_only(text: str) -> bool:
    """Check if transcription looks like background noise (inaudible, silence, etc.)."""
    t = (text or "").strip().lower()
    if len(t) < 3:
        return True
    noise_markers = ["[inaudible]", "[silence]", "[music]", "[noise]", "[applause]", "♪", "…"]
    if any(m in t for m in noise_markers):
        return True
    # Very short with no real words
    words = [w for w in t.split() if len(w) > 1]
    if len(words) < 2 and len(t) < 15:
        return True
    return False


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voice messages: transcribe and execute as /task."""
    if not update.message or not update.message.voice:
        return

    uid = _user_id(update)
    lang = _user_lang(update)  # Use cached until we have transcribed text
    if uid is not None and not _check_rate_limit(uid):
        await update.message.reply_text(t("rate_limit", lang))
        return

    voice = update.message.voice
    duration = getattr(voice, "duration", 0) or 0
    if duration <= 0:
        await update.message.reply_text(t("voice_empty", lang))
        return
    if duration > 60:
        await update.message.reply_text(t("voice_too_long", lang))
        return

    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    status_msg = await update.message.reply_text(t("transcribing", lang))

    try:
        import os
        import tempfile
        from tools.voice import transcribe_audio

        file = await context.bot.get_file(voice.file_id)

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            await file.download_to_drive(tmp_path)
            transcribed, error = transcribe_audio(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

        if error:
            await status_msg.edit_text(t("transcription_failed", lang, err=error))
            return

        if not transcribed or not transcribed.strip():
            await status_msg.edit_text(t("voice_unclear", lang))
            return

        if _is_background_noise_only(transcribed):
            await status_msg.edit_text(t("voice_noise", lang))
            return

        payload = transcribed.strip()
        lang = _user_lang(update, payload)  # Update lang from transcribed text

        if uid is not None:
            add_conversation(str(uid), f"[voice] {payload}", None)

        await status_msg.edit_text(t("heard_executing", lang, text=payload))

        # Treat as /task command
        update.message.text = f"/task {payload}"
        await cmd_task(update, context)

    except Exception as e:
        logger.exception("Voice message handling failed")
        await status_msg.edit_text(t("transcription_failed", lang, err=str(e)[:150]))


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a scheduled task: /schedule daily 09:00 "check HN"."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    lang = _user_lang(update, text)
    uid = _user_id(update)
    if uid is None:
        await update.message.reply_text(t("cannot_identify_user", lang))
        return
    
    try:
        from core.scheduler import parse_schedule_command, create_schedule, start_scheduler
        
        # Ensure scheduler is running
        start_scheduler()
        
        # Parse the command
        schedule_data = parse_schedule_command(update.message.text)
        if not schedule_data:
            help_text = (
                "❌ Invalid format. Use:\n\n"
                "**Explicit:**\n"
                "• `daily 09:00 \"check HN\"`\n"
                "• `once 14:30 \"remind me\"`\n"
                "• `weekly monday 09:00 \"report\"`\n\n"
                "**Natural language:**\n"
                "• `every day at 9am \"check HN\"`\n"
                "• `tomorrow at 3pm \"remind me\"`\n"
                "• `every monday at 9am \"report\"`"
            )
            await update.message.reply_text(help_text)
            return
        
        # Create the schedule
        task = create_schedule(
            user_id=str(uid),
            frequency=schedule_data['frequency'],
            schedule_time=schedule_data['time'],
            task_description=schedule_data['task'],
            day_of_week=schedule_data.get('day_of_week'),
            schedule_date=schedule_data.get('schedule_date'),
        )
        
        if task.frequency == "once":
            confirm_msg = t("scheduled_once", lang, time=task.schedule_time, task=task.task_description)
        elif task.frequency == "daily":
            confirm_msg = t("scheduled_daily", lang, time=task.schedule_time, task=task.task_description)
        elif task.frequency == "weekly":
            confirm_msg = t("scheduled_weekly", lang, day=task.day_of_week.title(), time=task.schedule_time, task=task.task_description)
        
        confirm_msg += f"\n\nSchedule ID: #{task.id}"
        await update.message.reply_text(confirm_msg)
        
        logger.info(f"User {uid} created schedule #{task.id}")
        
    except Exception as e:
        logger.exception("Failed to create schedule")
        await update.message.reply_text(f"❌ Failed to create schedule: {str(e)[:200]}")


async def cmd_schedules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all active schedules: /schedules."""
    if not update.message:
        return

    lang = _user_lang(update)
    uid = _user_id(update)
    if uid is None:
        await update.message.reply_text(t("cannot_identify_user", lang))
        return

    try:
        import io
        from rich.console import Console
        from rich.table import Table
        from core.scheduler import list_user_schedules

        schedules = list_user_schedules(str(uid))

        if not schedules:
            await update.message.reply_text(t("no_schedules", lang))
            return

        table = Table(title="📅 Your Schedules", show_header=True, header_style="bold")
        table.add_column("ID", style="cyan", width=4)
        table.add_column("When", style="green", width=22)
        table.add_column("Task", style="white", max_width=35)
        table.add_column("Last run", style="dim", width=12)

        for task in schedules:
            when = f"{task.schedule_time}"
            if task.frequency == "daily":
                when = f"Daily @ {task.schedule_time}"
            elif task.frequency == "weekly":
                when = f"{task.day_of_week.title()} @ {task.schedule_time}"
            elif task.frequency == "once":
                when = f"Once @ {task.schedule_time}"
            last_run = task.last_run.strftime("%m/%d %H:%M") if task.last_run else "—"
            table.add_row(str(task.id), when, task.task_description[:35], last_run)

        buf = io.StringIO()
        Console(file=buf, force_terminal=True, width=78).print(table)
        msg = buf.getvalue() + "\nUse /unschedule <id> to remove."
        await update.message.reply_text(msg)

    except Exception as e:
        logger.exception("Failed to list schedules")
        await update.message.reply_text(f"❌ Failed to list schedules: {str(e)[:200]}")


async def cmd_unschedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove a schedule: /unschedule 5."""
    if not update.message or not update.message.text:
        return

    lang = _user_lang(update)
    uid = _user_id(update)
    if uid is None:
        await update.message.reply_text(t("cannot_identify_user", lang))
        return
    
    try:
        from core.scheduler import remove_schedule, get_scheduled_task_by_id
        
        # Parse task ID from command
        parts = update.message.text.strip().split()
        if len(parts) != 2:
            await update.message.reply_text("❌ Usage: `/unschedule <id>`\nExample: `/unschedule 5`")
            return
        
        try:
            task_id = int(parts[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid ID. Use a number like `/unschedule 5`")
            return
        
        # Verify ownership
        task = get_scheduled_task_by_id(task_id)
        if not task:
            await update.message.reply_text(f"❌ Schedule #{task_id} not found.")
            return
        
        if task.user_id != str(uid):
            await update.message.reply_text(f"❌ You can only unschedule your own tasks.")
            return
        
        if remove_schedule(task_id):
            await update.message.reply_text(t("schedule_removed", lang, id=task_id, task=task.task_description[:50]))
            logger.info(f"User {uid} removed schedule #{task_id}")
        else:
            await update.message.reply_text(f"❌ Failed to remove schedule #{task_id}")
        
    except Exception as e:
        logger.exception("Failed to unschedule task")
        await update.message.reply_text(f"❌ Failed to unschedule: {str(e)[:200]}")


async def _execute_task_autonomously(task: str, user_id: int) -> dict:
    """Execute a task autonomously (for scheduled tasks) and send result to user."""
    try:
        from core.orchestrator import run_task
        from core.memory import add_conversation
        
        logger.info(f"Executing scheduled task autonomously: {task[:50]}")

        lang = get_user_language(str(user_id)) or "en"
        result = run_task(task, language=lang)
        
        # Store conversation
        add_conversation(str(user_id), f"[SCHEDULED] {task}", str(result.get('result', 'Completed')))
        
        # Send result to user via Telegram
        try:
            from telegram import Bot
            from core.config import get_telegram_token
            
            bot = Bot(token=get_telegram_token())
            
            if result.get('success', False):
                message = f"✅ Scheduled task completed:\n{task}\n\nResult: {result.get('result', 'Done')[:500]}"
            else:
                message = f"❌ Scheduled task failed:\n{task}\n\nError: {result.get('result', 'Unknown error')[:500]}"
            
            await bot.send_message(chat_id=user_id, text=message)
            
        except Exception as e:
            logger.error(f"Failed to send scheduled task result to user {user_id}: {e}")
        
        return result
        
    except Exception as e:
        logger.exception(f"Failed to execute scheduled task: {task}")
        return {"success": False, "result": f"Execution failed: {str(e)}", "agent_used": "scheduler"}


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


async def _send_copilot_suggestion(context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str) -> None:
    """Send a Copilot suggestion message to a user."""
    await context.bot.send_message(chat_id=user_id, text=message)


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
    lang = _user_lang(update, text)
    question = text[4:].strip() if text.lower().startswith("/ask") else text
    if not question:
        await update.message.reply_text(t("usage_ask", lang))
        return
    from core.llm import complete
    reply = complete(question, max_tokens=1024, language=lang)
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
            lang = _user_lang(update)
            await update.message.reply_text(t("internal_error", lang))
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
    app.add_handler(CommandHandler("yes", cmd_yes))
    app.add_handler(CommandHandler("no", cmd_no))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("schedules", cmd_schedules))
    app.add_handler(CommandHandler("unschedule", cmd_unschedule))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice_message))
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
    
    # Initialize scheduler
    try:
        from core.scheduler import start_scheduler
        start_scheduler()
        logger.info("Scheduler initialized")
    except Exception as e:
        logger.error(f"Failed to initialize scheduler: {e}")
    
    app = build_application()
    logger.info("Gedos Telegram bot starting (polling)...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        poll_interval=1.0,
        timeout=30,
    )
