"""
GEDOS Telegram interface — Pilot and Copilot mode.
Handles /task, /status, /stop, /copilot, /memory, /web, /ask.
"""

import asyncio
from datetime import datetime
import logging
import secrets
from typing import Optional
from collections import defaultdict
from time import perf_counter
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

from core.config import get_gedos_md_path, get_telegram_token, pilot_enabled, load_config, update_config
from core.copilot_context import analyze_context, get_copilot_sensitivity_seconds
from core.behavior_tracker import observe, start_background_tracker
from core.memory import (
    add_conversation,
    add_allowed_chat,
    add_task as memory_add_task,
    delete_pattern,
    delete_all_patterns,
    get_custom_permissions,
    get_permission_level,
    get_voice_output,
    get_patterns,
    get_recent_tasks,
    get_owner,
    init_db as memory_init_db,
    get_recent_conversations,
    get_user_language,
    list_allowed_chats,
    remove_allowed_chat,
    set_custom_permissions,
    set_permission_level,
    set_voice_output,
    set_owner,
    update_pattern_preferences,
)
from interfaces.i18n import t
from core.orchestrator import clear_stop, is_stop_requested, request_stop, run_task_with_langgraph
from agents.terminal_agent import run_shell, TerminalResult
from agents.gui_agent import click_button
from core.security import (
    SecurityError,
    get_allowed_chat_ids,
    get_command_permission_action,
    get_pairing_code,
    is_destructive_command,
)
from tools.ax_tree import get_ax_tree
from tools.voice_output import send_voice_response, text_to_speech_safe

logger = logging.getLogger(__name__)

_current_task: Optional[str] = None
_task_status: str = "idle"
_task_cancelled: bool = False

_copilot_active: dict[int, bool] = {}
_last_app_per_user: dict[int, str] = {}
_last_copilot_message_per_user: dict[int, str] = {}
_last_copilot_suggestion_at_per_user: dict[int, float] = {}
_copilot_sensitivity_per_user: dict[int, str] = {}

# Error recovery state for multi-step tasks
_pending_step_decision: dict[int, dict] = {}  # {user_id: {step_info, callback}}
_pending_plan_decision: dict[int, asyncio.Future] = {}
_pending_destructive_decision: dict[int, asyncio.Future] = {}
_pending_pattern_decision: dict[int, dict] = {}
_pending_custom_permission_flow: dict[int, dict] = {}
_unauthorized_chat_log_at: dict[str, float] = {}
_generated_pairing_code: Optional[str] = None
_pattern_index_per_user: dict[int, list[str]] = {}

# Rate limiting: {user_id: [timestamp1, timestamp2, ...]}
_rate_limit_tracker: dict[int, list[float]] = defaultdict(list)
RATE_LIMIT_MAX = 10  # max commands per minute
RATE_LIMIT_WINDOW = 60.0  # seconds
UNAUTHORIZED_LOG_WINDOW = 60.0
_SHELL_SAFE_PREFIXES = (
    "ls", "pwd", "whoami", "date", "git ", "cat ", "echo ", "which ",
    "node ", "npm ", "python", "python3", "cd ", "head ", "tail ", "wc ",
)
_STEP_ICONS = {
    "terminal": "🖥️",
    "web": "🌐",
    "gui": "🪟",
    "llm": "🧠",
}
_CUSTOM_PERMISSION_FIELDS = (
    ("terminal_destructive", "permissions_custom_prompt_terminal_destructive"),
    ("web_browsing", "permissions_custom_prompt_web_browsing"),
    ("filesystem_writes", "permissions_custom_prompt_filesystem_writes"),
    ("package_install", "permissions_custom_prompt_package_install"),
    ("github_operations", "permissions_custom_prompt_github_operations"),
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


def _format_ax_tree(tree: dict, lang: str = "en") -> str:
    err = tree.get("error")
    if err:
        return t("ax_error", lang, err=err)
    app = tree.get("app") or "?"
    lines = [t("ax_app", lang, app=app)]
    for w in (tree.get("windows") or [])[:5]:
        title = (w.get("title") or "").strip() or t("untitled", lang)
        lines.append(t("ax_window", lang, title=title))
    btns = tree.get("buttons") or []
    if btns:
        lines.append(t("ax_buttons", lang, buttons=", ".join((b.get("title") or b.get("role") or "?") for b in btns[:15])))
    return "\n".join(lines)


def _format_terminal_result(r: TerminalResult, lang: str = "en") -> str:
    out = (r.stdout or "").strip() or t("no_output", lang)
    err = (r.stderr or "").strip()
    if len(out) > 3500:
        out = out[:3500] + t("truncated_suffix", lang)
    if r.success:
        msg = t("terminal_success", lang, command=r.command[:80], output=out)
    elif r.return_code == 127:
        msg = t("terminal_not_found", lang, command=r.command[:80])
    elif "timed out" in err.lower():
        msg = t("terminal_timeout", lang, err=err)
    else:
        msg = t("terminal_failure", lang, command=r.command[:80], code=r.return_code, output=out)
    if err and "timed out" not in err.lower():
        msg += t("terminal_stderr", lang, err=err[:500])
    return msg


def _user_id(update: Update) -> Optional[int]:
    effective_user = getattr(update, "effective_user", None)
    effective_user_id = getattr(effective_user, "id", None)
    if isinstance(effective_user_id, int):
        return effective_user_id
    message = getattr(update, "message", None)
    if message:
        from_user = getattr(message, "from_user", None)
        from_user_id = getattr(from_user, "id", None)
        if isinstance(from_user_id, int):
            return from_user_id
    return None


def _chat_id(update: Update) -> Optional[int]:
    effective_chat = getattr(update, "effective_chat", None)
    effective_chat_id = getattr(effective_chat, "id", None)
    if isinstance(effective_chat_id, int):
        return effective_chat_id
    message = getattr(update, "message", None)
    if message:
        chat = getattr(message, "chat", None)
        chat_id = getattr(chat, "id", None)
        if isinstance(chat_id, int):
            return chat_id
    return None


def _authorized_chat_ids() -> set[str]:
    memory_init_db()
    owner = get_owner()
    allowed = {entry.chat_id for entry in list_allowed_chats()}
    env_allowed = get_allowed_chat_ids()
    if owner:
        allowed.add(owner.chat_id)
    allowed.update(env_allowed)
    return allowed


def _is_authorized_chat(chat_id: Optional[int]) -> bool:
    memory_init_db()
    if chat_id is None:
        return False
    owner = get_owner()
    if owner is None:
        return False
    return str(chat_id) in _authorized_chat_ids()


def _generated_claim_code() -> str:
    """Create and cache a one-time pairing code until the owner claims the bot."""
    global _generated_pairing_code
    if _generated_pairing_code is None:
        raw = secrets.token_hex(4).upper()
        _generated_pairing_code = f"{raw[:4]}-{raw[4:]}"
        message = (
            f"⚠️  No PAIRING_CODE set. Generated one-time code: {_generated_pairing_code}\n"
            f"Send /start {_generated_pairing_code} in Telegram to claim ownership."
        )
        logger.warning(message)
        print(message)
    return _generated_pairing_code


def _claim_pairing_code() -> Optional[str]:
    """Return the active pairing code for a fresh bot owner claim."""
    if get_owner() is not None:
        return None
    env_code = get_pairing_code()
    if env_code:
        return env_code
    return _generated_claim_code()


def _invalidate_generated_pairing_code() -> None:
    """Discard the in-memory one-time pairing code after owner claim."""
    global _generated_pairing_code
    _generated_pairing_code = None


def _should_log_unauthorized(chat_id: Optional[int]) -> bool:
    """Log unauthorized access at most once per chat per window."""
    key = str(chat_id) if chat_id is not None else "unknown"
    now = time()
    last_seen = _unauthorized_chat_log_at.get(key)
    if last_seen is not None and (now - last_seen) < UNAUTHORIZED_LOG_WINDOW:
        return False
    _unauthorized_chat_log_at[key] = now
    return True


def _ignore_if_unauthorized(update: Update, allow_unpaired_start: bool = False) -> bool:
    memory_init_db()
    chat_id = _chat_id(update)
    owner = get_owner()
    if owner is None:
        return not allow_unpaired_start
    if _is_authorized_chat(chat_id):
        return False
    if _should_log_unauthorized(chat_id):
        logger.warning("Ignoring unauthorized chat_id=%s", chat_id)
    return True


def _user_lang(update: Update, text: Optional[str] = None) -> str:
    """Get user language. If text provided, detect and update cache. Else use cached."""
    uid = _user_id(update)
    if uid is None:
        return "en"
    if text:
        from tools.language import get_and_update_user_language
        return get_and_update_user_language(str(uid), text)
    return get_user_language(str(uid)) or "en"


def _voice_enabled(chat_id: Optional[int]) -> bool:
    """Return whether voice output is enabled for the given chat."""
    if chat_id is None:
        return False
    return get_voice_output(str(chat_id))


def _voice_task_summary(text: str, lang: str) -> str:
    """Build a concise, speech-safe task completion message."""
    safe = text_to_speech_safe(text)
    prefix = t("voice_task_complete", lang)
    if not safe:
        return prefix
    if safe.lower().startswith(prefix.lower()):
        return safe
    return f"{prefix} {safe}"


def _permission_status_message(user_id: str, lang: str) -> str:
    """Return the current permission level message."""
    level = get_permission_level(str(user_id))
    if level is None:
        level = "default" if (load_config().get("security") or {}).get("strict_shell", True) else "full_access"
    if level == "full_access":
        return t("permissions_status_full", lang)
    if level == "custom":
        permissions = get_custom_permissions(str(user_id))
        lines = [t("permissions_status_custom", lang)]
        for key, _ in _CUSTOM_PERMISSION_FIELDS:
            lines.append(f"- {key}: {permissions.get(key, 'confirm')}")
        return "\n".join(lines)
    return t("permissions_status_default", lang)


def _set_permission_preference(user_id: str, level: str) -> None:
    """Persist permission level in config and user context."""
    requested = str(level).strip().lower()
    if requested in {"full", "full_access"}:
        normalized = "full_access"
    elif requested == "custom":
        normalized = "custom"
    else:
        normalized = "default"
    update_config({"security": {"strict_shell": normalized != "full_access"}})
    set_permission_level(str(user_id), normalized)


async def _prompt_permission_confirmation(update: Update, lang: str, detail: str) -> bool:
    """Ask for a one-off permission confirmation."""
    uid = _user_id(update)
    if uid is None or not update.message:
        return False
    await update.message.reply_text(t("permission_request_confirm", lang, detail=detail))
    future: asyncio.Future = asyncio.get_running_loop().create_future()
    _pending_destructive_decision[uid] = future
    try:
        return bool(await asyncio.wait_for(future, timeout=300.0))
    except asyncio.TimeoutError:
        return False
    finally:
        _pending_destructive_decision.pop(uid, None)


async def _start_custom_permissions_flow(update: Update, lang: str) -> None:
    """Begin the step-by-step custom permissions flow in Telegram."""
    uid = _user_id(update)
    chat_id = _chat_id(update)
    if uid is None or chat_id is None or not update.message:
        return
    _pending_custom_permission_flow[uid] = {
        "user_id": str(chat_id),
        "lang": lang,
        "index": 0,
        "values": {},
    }
    first_key = _CUSTOM_PERMISSION_FIELDS[0][1]
    await update.message.reply_text(t(first_key, lang))


def _format_demo_plan(plan) -> str:
    """Render the polished dry-run plan display."""
    lines = [f"📋 Task plan ({len(plan.steps)} steps):", "━━━━━━━━━━━━━━━━━━━━━━"]
    for index, step in enumerate(plan.steps, start=1):
        icon = _STEP_ICONS.get(step.agent, "•")
        lines.append(f"{index}. {icon}  {step.agent:<8} {step.action}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("[▶️ Run] [❌ Cancel]")
    return "\n".join(lines)


def _append_progress_line(progress_lines: list[str], line: str) -> str:
    """Append one timeline line and return the full rendered progress text."""
    progress_lines.append(line)
    return "\n".join(progress_lines)


async def _maybe_send_voice_response(
    context: Optional[ContextTypes.DEFAULT_TYPE],
    chat_id: Optional[int],
    text: str,
    lang: str,
) -> bool:
    """Send a voice response only when the user enabled voice mode."""
    if context is None or chat_id is None or not _voice_enabled(chat_id):
        return False
    bot = getattr(context, "bot", None)
    if bot is None:
        return False
    await send_voice_response(bot, chat_id, text, lang)
    return True


def _copilot_sensitivity(user_id: int) -> str:
    return _copilot_sensitivity_per_user.get(user_id, "medium")


def _copilot_cooldown_seconds(user_id: int) -> float:
    values = get_copilot_sensitivity_seconds()
    return values.get(_copilot_sensitivity(user_id), values["medium"])


def _copilot_sensitivity_label(user_id: int, lang: str) -> str:
    return t(f"copilot_sensitivity_{_copilot_sensitivity(user_id)}", lang)


def _pattern_trigger_label(pattern, lang: str) -> str:
    """Render a learned pattern trigger for human-readable output."""
    trigger = (pattern.trigger or "").strip()
    if trigger.startswith("time:") and "@" in trigger:
        try:
            payload = trigger[5:]
            day_name, hhmm = payload.split("@", 1)
            hour_text, minute_text = hhmm.split(":", 1)
            hour = int(hour_text)
            minute = int(minute_text)
            suffix = "am" if hour < 12 else "pm"
            display_hour = hour % 12 or 12
            time_label = f"{display_hour}{suffix}" if minute == 0 else f"{display_hour}:{minute:02d}{suffix}"
            return t("pattern_trigger_time", lang, day=day_name.title(), time=time_label)
        except Exception:
            return trigger
    if trigger.startswith("after:"):
        return t("pattern_trigger_after", lang, trigger=trigger[6:])
    if trigger.startswith("app:"):
        return t("pattern_trigger_app", lang, trigger=trigger[4:])
    return trigger


def _pattern_line(index: int, pattern, lang: str) -> str:
    """Format one pattern line for /patterns output."""
    return t(
        "patterns_item",
        lang,
        n=index,
        confidence=int(round((pattern.confidence or 0.0) * 100)),
        trigger=_pattern_trigger_label(pattern, lang),
        action=pattern.action,
    )


def _pattern_automation_message(pattern, lang: str) -> str:
    """Render the proactive confirmation message for a newly confirmed pattern."""
    return t(
        "pattern_confirmed",
        lang,
        trigger=_pattern_trigger_label(pattern, lang),
        action=pattern.action,
    )


def _schedule_pattern_automation(pattern, user_id: str) -> bool:
    """Best-effort convert a time-based learned pattern into an existing schedule."""
    if pattern.type != "time_based":
        return False
    trigger = (pattern.trigger or "").strip()
    if not trigger.startswith("time:") or "@" not in trigger:
        return False
    try:
        payload = trigger[5:]
        day_name, hhmm = payload.split("@", 1)
        from core.scheduler import create_schedule, start_scheduler

        start_scheduler()
        create_schedule(
            user_id=str(user_id),
            frequency="weekly",
            schedule_time=hhmm,
            task_description=pattern.action,
            day_of_week=day_name.lower(),
        )
        return True
    except Exception:
        logger.exception("Failed to create schedule from pattern %s", pattern.id)
        return False


async def _maybe_notify_new_patterns(update: Update, lang: str, patterns: list) -> None:
    """Send confirmation prompts for newly confirmed patterns."""
    if not update.message:
        return
    uid = _user_id(update)
    chat_id = _chat_id(update)
    if uid is None or chat_id is None:
        return
    for pattern in patterns:
        _pending_pattern_decision[uid] = {"pattern_id": pattern.id, "chat_id": str(chat_id)}
        await update.message.reply_text(_pattern_automation_message(pattern, lang))


def _localized_status_name(status: str, lang: str) -> str:
    return t(f"status_{status}", lang)


def _learn_patterns_for_task(task: str, chat_id: Optional[int], context: Optional[dict] = None) -> list:
    """Record a successful user task and return newly confirmed patterns."""
    if chat_id is None:
        return []
    try:
        return observe(task, str(chat_id), context or {"time": datetime.utcnow()})
    except Exception:
        logger.exception("Behavior tracker observe failed in Telegram task flow")
        return []


async def _execute_step_with_recovery(
    step,
    step_num: int,
    steps_count: int,
    progress_msg,
    uid: Optional[int],
    update: Update,
    lang: str = "en",
    progress_lines: Optional[list[str]] = None,
) -> dict:
    """
    Execute a step with retry logic and user decision on failure.
    """
    import asyncio
    from core.orchestrator import _execute_single_step
    
    result = _execute_single_step(step.agent, step.action, step_obj=step, language=lang)

    if result.get('success', False):
        return result

    if progress_lines is not None:
        await progress_msg.edit_text(_append_progress_line(progress_lines, f"⚠️ Retrying step {step_num}/{steps_count}..."))
    else:
        await progress_msg.edit_text(t("step_retry", lang, n=step_num, t=steps_count))

    retry_result = _execute_single_step(step.agent, step.action, step_obj=step, language=lang)
    
    # If retry succeeded, return success
    if retry_result.get('success', False):
        return retry_result
    
    retry_error = retry_result.get('result', t("unknown_error", lang))[:100]
    decision_message = t("step_failed_continue", lang, n=step_num, err=retry_error)
    
    if progress_lines is not None:
        await progress_msg.edit_text(_append_progress_line(progress_lines, f"❌ Step {step_num}/{steps_count}: {step.action} — {retry_error}"))
        await progress_msg.edit_text("\n".join(progress_lines + [decision_message]))
    else:
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
        return {"success": False, "result": t("decision_timeout", lang), "agent_used": step.agent}


async def _run_task_with_progress_updates(task: str, progress_msg, uid: Optional[int], update: Update, lang: str = "en") -> dict:
    """
    Execute a multi-step task with real-time progress updates to Telegram.
    """
    global _task_status, _task_cancelled
    
    try:
        from core.orchestrator import _execute_single_step
        from agents.terminal_agent import reset_step_cwd

        reset_step_cwd()
        try:
            from core.task_planner import plan_task
            plan = plan_task(task, language=lang)
        
            if not plan.is_multi_step or not plan.steps:
                from core.orchestrator import run_single_step_task
                return run_single_step_task(task, language=lang)

            steps_count = len(plan.steps)
            results = []
            overall_success = True
            agents_used = []
            progress_lines: list[str] = []
            start_time = perf_counter()
            
            # Execute each step with progress updates
            for i, step in enumerate(plan.steps):
                if _task_cancelled or is_stop_requested():
                    _task_status = "idle"
                    await progress_msg.edit_text(t("task_cancelled_at_step", lang, n=i + 1, t=steps_count))
                    return {"success": False, "result": t("task_cancelled", lang), "agent_used": "cancelled"}
                
                step_num = i + 1
                
                # Update progress before step
                await progress_msg.edit_text(
                    _append_progress_line(progress_lines, f"⚙️ Running step {step_num}/{steps_count}...")
                )
                
                result = await _execute_step_with_recovery(
                    step, step_num, steps_count, progress_msg, uid, update, lang, progress_lines
                )
                agents_used.append(result.get('agent_used', step.agent))
                
                if result.get('cancelled', False):
                    _task_status = "idle"
                    await progress_msg.edit_text(t("task_cancelled_user", lang, n=step_num, t=steps_count))
                    return {"success": False, "result": t("task_cancelled", lang), "agent_used": "cancelled"}
                
                # Update progress after step
                if result.get('success', False):
                    step_result = result.get('result', t("generic_completed", lang))[:100]
                    await progress_msg.edit_text(
                        _append_progress_line(
                            progress_lines,
                            f"✅ Step {step_num}/{steps_count}: {step.action} — {step_result}",
                        )
                    )
                    results.append(t("task_summary_success", lang, n=step_num, result=step_result))
                else:
                    step_error = result.get('result', t("unknown_error", lang))[:100]
                    await progress_msg.edit_text(
                        _append_progress_line(
                            progress_lines,
                            f"❌ Step {step_num}/{steps_count}: {step.action} — {step_error}",
                        )
                    )
                    results.append(t("task_summary_failure", lang, n=step_num, result=step_error))
                    overall_success = False
            
            # Final summary
            _task_status = "idle"
            success_count = sum(1 for r in results if "✅" in r)
            failure_count = len(results) - success_count
            
            summary = (t("task_completed", lang) if overall_success else t("task_finished_errors", lang)) + "\n\n"
            summary += t("task_summary_counts", lang, success=success_count, failed=failure_count) + "\n\n"
            summary += "\n".join(results)
            
            if len(summary) > 4000:
                summary = summary[:4000] + t("truncated_suffix", lang)

            elapsed = perf_counter() - start_time
            final_progress = "\n".join(progress_lines + [f"✓ Done in {elapsed:.1f}s"])
            await progress_msg.edit_text(final_progress)
            
            # Store in memory
            if uid is not None:
                add_conversation(str(uid), task, summary[:500])
                agents_summary = ", ".join(set(agents_used))
                task_user_id = _chat_id(update)
                memory_add_task(
                    description=task, 
                    status="completed" if overall_success else "failed", 
                    agent_used=f"multi-step ({agents_summary})", 
                    result=summary[:1000],
                    user_id=str(task_user_id) if task_user_id is not None else None,
                )
                new_patterns = _learn_patterns_for_task(task, task_user_id)
            else:
                new_patterns = []
            
            return {
                "success": overall_success,
                "result": summary,
                "agent_used": f"multi-step ({', '.join(set(agents_used))})",
                "steps_completed": len(results),
                "new_patterns": new_patterns,
            }
        finally:
            reset_step_cwd()
        
    except Exception as e:
        logger.exception("Multi-step task execution failed")
        error_msg = t("multi_step_planning_error", lang, err=str(e)[:300])
        await progress_msg.edit_text(f"❌ {error_msg}")
        return {"success": False, "result": error_msg, "agent_used": "planner"}


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if _ignore_if_unauthorized(update, allow_unpaired_start=True):
        return
    uid = _user_id(update)
    chat_id = _chat_id(update)
    lang = _user_lang(update)
    memory_init_db()

    owner = get_owner()
    if owner is None and chat_id is not None:
        pairing_code = _claim_pairing_code()
        parts = update.message.text.strip().split(maxsplit=1)
        provided_code = parts[1].strip() if len(parts) > 1 else ""
        if pairing_code and provided_code != pairing_code:
            await update.message.reply_text(t("pairing_required", lang))
            return
        set_owner(str(chat_id))
        _invalidate_generated_pairing_code()

    if uid is not None:
        from core.memory import get_recent_conversations, init_db
        init_db()
        convos = get_recent_conversations(str(uid), limit=1)
        is_first_time = len(convos) == 0
    else:
        is_first_time = True

    if is_first_time:
        welcome = t("start_first_time", lang)
        await update.message.reply_text(welcome)
        if uid is not None:
            add_conversation(str(uid), "/start", "First time onboarding sent")
    else:
        await update.message.reply_text(t("start_returning", lang))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or _ignore_if_unauthorized(update):
        return
    uid = _user_id(update)
    lang = _user_lang(update)
    is_copilot_on = _copilot_active.get(uid, False) if uid is not None else False

    if is_copilot_on:
        help_text = t("help_copilot", lang)
    else:
        help_text = t("help_pilot", lang)
    await update.message.reply_text(help_text)


async def cmd_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage voice output: on | off | status."""
    if not update.message or not update.message.text or _ignore_if_unauthorized(update):
        return
    text = update.message.text.strip()
    lang = _user_lang(update, text)
    chat_id = _chat_id(update)
    if chat_id is None:
        await update.message.reply_text(t("cannot_identify_user", lang))
        return

    parts = text.split(maxsplit=1)
    action = parts[1].strip().lower() if len(parts) > 1 else ""
    if action == "on":
        set_voice_output(str(chat_id), True)
        if not await _maybe_send_voice_response(context, chat_id, t("voice_enabled", lang), lang):
            await update.message.reply_text(t("voice_enabled", lang))
        return
    if action == "off":
        set_voice_output(str(chat_id), False)
        await update.message.reply_text(t("voice_disabled", lang))
        return
    if action == "status":
        key = "voice_status_on" if _voice_enabled(chat_id) else "voice_status_off"
        await update.message.reply_text(t(key, lang))
        return
    await update.message.reply_text(t("usage_voice", lang))


async def cmd_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage permission level in Telegram mode."""
    if not update.message or not update.message.text or _ignore_if_unauthorized(update):
        return
    text = update.message.text.strip()
    lang = _user_lang(update, text)
    chat_id = _chat_id(update)
    if chat_id is None:
        await update.message.reply_text(t("cannot_identify_user", lang))
        return

    parts = text.split()
    if len(parts) == 1:
        await update.message.reply_text(_permission_status_message(str(chat_id), lang))
        return

    action = parts[1].lower()
    if action == "default":
        _set_permission_preference(str(chat_id), "default")
        await update.message.reply_text(t("permissions_set_default", lang))
        return
    if action == "custom":
        _set_permission_preference(str(chat_id), "custom")
        await _start_custom_permissions_flow(update, lang)
        return
    if action == "full":
        if len(parts) < 3 or parts[2].lower() != "confirm":
            await update.message.reply_text(t("permissions_confirm_full", lang))
            return
        _set_permission_preference(str(chat_id), "full_access")
        await update.message.reply_text(t("permissions_set_full", lang))
        return

    await update.message.reply_text(t("usage_permissions", lang))


async def cmd_config(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tell the user where to edit GEDOS.md."""
    if not update.message or _ignore_if_unauthorized(update):
        return
    lang = _user_lang(update)
    await update.message.reply_text(t("config_open_instructions", lang, path=str(get_gedos_md_path())))


async def cmd_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _current_task, _task_status, _task_cancelled
    if not update.message or not update.message.text or _ignore_if_unauthorized(update):
        return

    text = update.message.text.strip()
    lang = _user_lang(update, text)
    uid = _user_id(update)
    chat_id = _chat_id(update)
    if uid is not None and not _check_rate_limit(uid):
        await update.message.reply_text(t("rate_limit", lang))
        return

    payload = text[5:].strip() if text.lower().startswith("/task") else text
    if not payload:
        await update.message.reply_text(t("usage_task", lang))
        return

    uid = _user_id(update)
    clear_stop()
    _current_task = payload
    _task_status = "running"
    _task_cancelled = False
    logger.info("Task received: %s", payload[:100])

    low = payload.lower()
    if any(kw in low for kw in ("list elements", "screen elements", "listar elementos", "ax tree", "what do you see", "o que você vê")):
        _task_status = "idle"
        tree = get_ax_tree(max_buttons=25, max_text_fields=10)
        reply = _format_ax_tree(tree, lang)
        await update.message.reply_text(reply)
        await _maybe_send_voice_response(context, chat_id, _voice_task_summary(reply, lang), lang)
        if uid is not None:
            add_conversation(str(uid), payload, reply)
            memory_add_task(description=payload, status="completed", agent_used="gui", result=reply[:500], user_id=str(chat_id) if chat_id is not None else None)
            await _maybe_notify_new_patterns(update, lang, _learn_patterns_for_task(payload, chat_id))
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
            reply = t("clicked_button", lang) if ok else t("button_not_found", lang, button=btn_name)
            await update.message.reply_text(reply)
            await _maybe_send_voice_response(context, chat_id, _voice_task_summary(reply, lang), lang)
            if uid is not None:
                add_conversation(str(uid), payload, reply)
                memory_add_task(description=payload, status="completed", agent_used="gui", result=reply, user_id=str(chat_id) if chat_id is not None else None)
                await _maybe_notify_new_patterns(update, lang, _learn_patterns_for_task(payload, chat_id))
            return

    if _looks_like_shell_command(payload):
        legacy_destructive = is_destructive_command(payload, user_id=str(chat_id) if chat_id is not None else None)
        permission_action = get_command_permission_action(payload, user_id=str(chat_id) if chat_id is not None else None)
        if permission_action == "block":
            _task_status = "idle"
            await update.message.reply_text(t("permission_blocked", lang))
            return
        if permission_action == "confirm" or legacy_destructive:
            if not await _prompt_permission_confirmation(update, lang, payload):
                _task_status = "idle"
                await update.message.reply_text(t("permission_request_denied", lang))
                return
        if _task_cancelled or is_stop_requested():
            _task_status = "idle"
            await update.message.reply_text(t("task_cancelled", lang))
            return
        try:
            result = run_shell(payload)
        except SecurityError as exc:
            _task_status = "idle"
            await update.message.reply_text(str(exc))
            return
        _task_status = "idle"
        reply = _format_terminal_result(result, lang)
        await update.message.reply_text(reply)
        await _maybe_send_voice_response(context, chat_id, _voice_task_summary(reply, lang), lang)
        if uid is not None:
            add_conversation(str(uid), payload, reply[:500])
            memory_add_task(description=payload, status="completed" if result.success else "failed", agent_used="terminal", result=reply[:1000], user_id=str(chat_id) if chat_id is not None else None)
            if result.success:
                await _maybe_notify_new_patterns(update, lang, _learn_patterns_for_task(payload, chat_id))
        return

    # Check if this is a multi-step task for enhanced progress reporting
    try:
        from core.task_planner import _is_multi_step_task
        is_multi_step = _is_multi_step_task(payload)
    except ImportError:
        is_multi_step = False

    if is_multi_step:
        from core.task_planner import plan_task
        plan = plan_task(payload, language=lang)
        if not plan.is_multi_step or not plan.steps:
            is_multi_step = False
        else:
            progress_msg = await update.message.reply_text(_format_demo_plan(plan))
            if not await _confirm_plan(uid, progress_msg, lang):
                _task_status = "idle"
                await progress_msg.edit_text(t("dry_run_cancelled", lang))
                return
        try:
            if _task_cancelled or is_stop_requested():
                _task_status = "idle"
                await progress_msg.edit_text(t("task_cancelled", lang))
                return

            out = await _run_task_with_progress_updates(payload, progress_msg, uid, update, lang)
            
        except Exception as e:
            logger.exception("Multi-step task failed: %s", payload[:80])
            _task_status = "idle"
            reply = t("multi_step_execution_error", lang, err=str(e)[:300])
            await progress_msg.edit_text(reply)
            if uid is not None:
                add_conversation(str(uid), payload, reply[:500])
                memory_add_task(description=payload, status="failed", agent_used="orchestrator", result=reply[:500], user_id=str(chat_id) if chat_id is not None else None)
            return
    else:
        progress_msg = await update.message.reply_text(t("task_started", lang))
        try:
            if _task_cancelled or is_stop_requested():
                _task_status = "idle"
                await progress_msg.edit_text(t("task_cancelled", lang))
                return
            out = run_task_with_langgraph(
                payload,
                language=lang,
                user_id=str(chat_id) if chat_id is not None else None,
                context={"time": datetime.utcnow()},
            )
            if _task_cancelled or is_stop_requested():
                _task_status = "idle"
                await progress_msg.edit_text(t("task_cancelled", lang))
                return
        except Exception as e:
            logger.exception("Orchestrator failed for task: %s", payload[:80])
            _task_status = "idle"
            reply = t("execution_error", lang, err=str(e)[:300])
            await progress_msg.edit_text(reply)
            if uid is not None:
                add_conversation(str(uid), payload, reply[:500])
                memory_add_task(description=payload, status="failed", agent_used="orchestrator", result=reply[:500], user_id=str(chat_id) if chat_id is not None else None)
            return
        _task_status = "idle"
        reply = out.get("result") or t("no_result", lang)
        if len(reply) > 4000:
            reply = reply[:4000] + t("truncated_suffix", lang)
        await progress_msg.edit_text(reply)
        await _maybe_send_voice_response(context, chat_id, _voice_task_summary(reply, lang), lang)
        if uid is not None:
            add_conversation(str(uid), payload, reply[:500])
            memory_add_task(description=payload, status="completed" if out.get("success") else "failed", agent_used=out.get("agent_used"), result=reply[:1000], user_id=str(chat_id) if chat_id is not None else None)
            await _maybe_notify_new_patterns(update, lang, list(out.get("new_patterns") or []))
    return


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or _ignore_if_unauthorized(update):
        return
    lang = _user_lang(update)
    global _current_task, _task_status
    if _task_status == "idle" or not _current_task:
        await update.message.reply_text(t("no_task_running", lang))
        return
    suffix = t("status_suffix", lang) if len(_current_task) > 150 else ""
    status_msg = t(
        "status_active",
        lang,
        status=_localized_status_name(_task_status, lang),
        task=_current_task[:150],
        suffix=suffix,
    )
    await update.message.reply_text(status_msg)


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _task_status, _task_cancelled
    if not update.message or _ignore_if_unauthorized(update):
        return
    lang = _user_lang(update)
    if _task_status in ("running", "stopped"):
        _task_cancelled = True
        _task_status = "stopped"
        request_stop()
        logger.info("Task cancellation requested")
        await update.message.reply_text(t("task_stopped", lang))
    else:
        await update.message.reply_text(t("no_task_running", lang))


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Health check: /ping."""
    if update.message:
        if _ignore_if_unauthorized(update):
            return
        lang = _user_lang(update)
        await update.message.reply_text(t("pong", lang))


async def cmd_github(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show GitHub webhook status or connection instructions."""
    if not update.message or not update.message.text or _ignore_if_unauthorized(update):
        return

    text = update.message.text.strip()
    lang = _user_lang(update, text)
    parts = text.split(maxsplit=1)
    action = parts[1].strip().lower() if len(parts) > 1 else ""

    from core.github_webhook import get_webhook_status

    status = get_webhook_status()
    if action == "status":
        key = "github_status_running" if status["running"] else "github_status_stopped"
        await update.message.reply_text(t(key, lang, port=status["port"]))
        return

    if action == "connect":
        await update.message.reply_text(t("github_connect", lang, port=status["port"]))
        return

    await update.message.reply_text(t("usage_github", lang))


async def cmd_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user decision to continue after step failure."""
    if _ignore_if_unauthorized(update):
        return
    uid = _user_id(update)
    lang = _user_lang(update)
    if uid is not None and uid in _pending_destructive_decision:
        future = _pending_destructive_decision.pop(uid)
        if not future.done():
            future.set_result(True)
        return
    if uid is not None and uid in _pending_plan_decision:
        future = _pending_plan_decision.pop(uid)
        if not future.done():
            future.set_result(True)
        return
    if uid is not None and uid in _pending_pattern_decision:
        decision = _pending_pattern_decision.pop(uid)
        pattern = update_pattern_preferences(decision["pattern_id"], decision["chat_id"], automated=True)
        if pattern:
            _schedule_pattern_automation(pattern, decision["chat_id"])
            await update.message.reply_text(t("pattern_automation_enabled", lang, action=pattern.action))
        return
    if uid is None or uid not in _pending_step_decision:
        await update.message.reply_text(t("no_pending_decision", lang))
        return
    
    # Get the pending decision and continue execution
    decision_info = _pending_step_decision.pop(uid)
    await decision_info["callback"](True)  # Continue with next step


async def cmd_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user decision to cancel after step failure."""
    if _ignore_if_unauthorized(update):
        return
    uid = _user_id(update)
    lang = _user_lang(update)
    if uid is not None and uid in _pending_destructive_decision:
        future = _pending_destructive_decision.pop(uid)
        if not future.done():
            future.set_result(False)
        return
    if uid is not None and uid in _pending_plan_decision:
        future = _pending_plan_decision.pop(uid)
        if not future.done():
            future.set_result(False)
        return
    if uid is not None and uid in _pending_pattern_decision:
        _pending_pattern_decision.pop(uid, None)
        await update.message.reply_text(t("pattern_automation_declined", lang))
        return
    if uid is None or uid not in _pending_step_decision:
        await update.message.reply_text(t("no_pending_decision", lang))
        return

    # Get the pending decision and cancel execution
    decision_info = _pending_step_decision.pop(uid)
    await decision_info["callback"](False)  # Cancel execution


async def cmd_never(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Suppress future suggestions for a newly confirmed pattern."""
    if _ignore_if_unauthorized(update):
        return
    uid = _user_id(update)
    lang = _user_lang(update)
    if uid is None or uid not in _pending_pattern_decision:
        await update.message.reply_text(t("no_pending_decision", lang))
        return
    decision = _pending_pattern_decision.pop(uid)
    update_pattern_preferences(decision["pattern_id"], decision["chat_id"], suppressed=True, automated=False)
    await update.message.reply_text(t("pattern_suppressed", lang))


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle non-command text only for pending interactive flows."""
    if not update.message or not update.message.text or _ignore_if_unauthorized(update):
        return
    uid = _user_id(update)
    if uid is None or uid not in _pending_custom_permission_flow:
        return
    state = _pending_custom_permission_flow[uid]
    choice = update.message.text.strip().lower()
    mapping = {"a": "allow", "c": "confirm", "b": "block"}
    lang = state["lang"]
    if choice not in mapping:
        await update.message.reply_text(t("permissions_custom_invalid_choice", lang))
        return
    field_key, _ = _CUSTOM_PERMISSION_FIELDS[state["index"]]
    state["values"][field_key] = mapping[choice]
    state["index"] += 1
    if state["index"] >= len(_CUSTOM_PERMISSION_FIELDS):
        set_custom_permissions(state["user_id"], state["values"])
        _pending_custom_permission_flow.pop(uid, None)
        await update.message.reply_text(t("permissions_set_custom", lang))
        await update.message.reply_text(t("permissions_custom_saved", lang))
        return
    next_prompt_key = _CUSTOM_PERMISSION_FIELDS[state["index"]][1]
    await update.message.reply_text(t(next_prompt_key, lang))


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
    if not update.message or not update.message.voice or _ignore_if_unauthorized(update):
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
        whisper_lang = lang if len(lang) == 2 else None

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            await file.download_to_drive(tmp_path)
            await status_msg.edit_text(t("voice_detected", lang, hint=whisper_lang or "auto"))
            transcribed, error = transcribe_audio(tmp_path, language_hint=whisper_lang)
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

        heard_msg = t("heard_executing", lang, text=payload)
        await status_msg.edit_text(heard_msg)
        await _maybe_send_voice_response(context, chat_id, heard_msg, lang)

        # Treat as /task command
        update.message.text = f"/task {payload}"
        await cmd_task(update, context)

    except Exception as e:
        logger.exception("Voice message handling failed")
        await status_msg.edit_text(t("transcription_failed", lang, err=str(e)[:150]))


async def cmd_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a scheduled task: /schedule daily 09:00 "check HN"."""
    if not update.message or not update.message.text or _ignore_if_unauthorized(update):
        return

    text = update.message.text.strip()
    lang = _user_lang(update, text)
    uid = _user_id(update)
    if uid is None:
        await update.message.reply_text(t("cannot_identify_user", lang))
        return
    
    try:
        from core.scheduler import (
            create_schedule,
            ensure_user_timezone,
            format_next_run,
            format_schedule_rule,
            parse_schedule_command,
            start_scheduler,
        )

        if text.lower() == "/schedule history":
            history = [task_entry for task_entry in get_recent_tasks(limit=20, user_id=str(uid)) if task_entry.agent_used == "scheduler"][:5]
            if not history:
                await update.message.reply_text("📋 Schedule history (last 5):\nNo completed scheduled runs yet.")
                return
            lines = ["📋 Schedule history (last 5):"]
            for task_entry in history:
                stamp = task_entry.created_at.strftime("%a %b") + f" {task_entry.created_at.day} at {task_entry.created_at.strftime('%I:%M %p').lstrip('0')}"
                icon = "✅" if task_entry.status == "completed" else "❌"
                lines.append(f"{icon} {task_entry.description} — {stamp}")
            await update.message.reply_text("\n".join(lines))
            return
        
        # Ensure scheduler is running
        start_scheduler()
        user_tz, tz_is_new = ensure_user_timezone(str(uid))
        
        # Parse the command
        schedule_data = parse_schedule_command(update.message.text, user_tz=user_tz)
        if not schedule_data:
            await update.message.reply_text(t("schedule_invalid_format", lang))
            return
        
        # Create the schedule
        task = create_schedule(
            user_id=str(uid),
            frequency=schedule_data['frequency'],
            schedule_time=schedule_data['time'],
            task_description=schedule_data['task'],
            day_of_week=schedule_data.get('day_of_week'),
            schedule_date=schedule_data.get('schedule_date'),
            schedule_times=schedule_data.get('times'),
            interval_minutes=schedule_data.get('interval_minutes'),
            timezone=user_tz,
        )

        rule = format_schedule_rule(task, user_tz=user_tz)
        next_run = format_next_run(task, user_tz=user_tz, detailed=True)
        confirm_msg = (
            "📅 Schedule confirmed:\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Task:      {task.task_description}\n"
            f"Runs:      {rule}\n"
            f"Timezone:  {user_tz}\n"
            f"Next run:  {next_run}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Saved as schedule #{task.id}"
        )
        if tz_is_new:
            confirm_msg = f"Detected timezone: {user_tz}. Is this correct? [Y/n]\n\n{confirm_msg}"
        await update.message.reply_text(confirm_msg)
        
        logger.info(f"User {uid} created schedule #{task.id}")
        
    except Exception as e:
        logger.exception("Failed to create schedule")
        await update.message.reply_text(t("schedule_create_failed", lang, err=str(e)[:200]))


async def cmd_schedules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all active schedules: /schedules."""
    if not update.message or _ignore_if_unauthorized(update):
        return

    lang = _user_lang(update)
    uid = _user_id(update)
    if uid is None:
        await update.message.reply_text(t("cannot_identify_user", lang))
        return

    try:
        from core.scheduler import ensure_user_timezone, format_next_run, format_schedule_rule, list_user_schedules

        user_tz, _ = ensure_user_timezone(str(uid))
        schedules = list_user_schedules(str(uid))

        if not schedules:
            await update.message.reply_text(t("no_schedules", lang))
            return

        lines = [f"📅 Active schedules ({len(schedules)}):", "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
        for task in schedules:
            lines.append(f"#{task.id}  {format_schedule_rule(task, user_tz=user_tz)}")
            lines.append(f"    {task.task_description}")
            lines.append(f"    Next: {format_next_run(task, user_tz=user_tz)}")
            lines.append("")
        if lines[-1] == "":
            lines.pop()
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("/unschedule <id> to remove")
        await update.message.reply_text("\n".join(lines))

    except Exception as e:
        logger.exception("Failed to list schedules")
        await update.message.reply_text(t("schedule_list_failed", lang, err=str(e)[:200]))


async def cmd_unschedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove a schedule: /unschedule 5."""
    if not update.message or not update.message.text or _ignore_if_unauthorized(update):
        return

    lang = _user_lang(update)
    uid = _user_id(update)
    if uid is None:
        await update.message.reply_text(t("cannot_identify_user", lang))
        return
    
    try:
        from core.scheduler import format_schedule_rule, remove_schedule, get_scheduled_task_by_id
        
        # Parse task ID from command
        parts = update.message.text.strip().split()
        if len(parts) != 2:
            await update.message.reply_text(t("schedule_usage_unschedule", lang))
            return
        
        try:
            task_id = int(parts[1])
        except ValueError:
            await update.message.reply_text(t("schedule_invalid_id", lang))
            return
        
        # Verify ownership
        task = get_scheduled_task_by_id(task_id)
        if not task:
            await update.message.reply_text(t("schedule_not_found", lang, id=task_id))
            return
        
        if task.user_id != str(uid):
            await update.message.reply_text(t("schedule_not_owner", lang))
            return
        
        if remove_schedule(task_id):
            await update.message.reply_text(f"✅ Removed: {format_schedule_rule(task)} — {task.task_description[:80]}")
            logger.info(f"User {uid} removed schedule #{task_id}")
        else:
            await update.message.reply_text(t("schedule_remove_failed", lang, id=task_id))
        
    except Exception as e:
        logger.exception("Failed to unschedule task")
        await update.message.reply_text(t("unschedule_failed", lang, err=str(e)[:200]))


async def _execute_task_autonomously(task: str, user_id: int) -> dict:
    """Execute a task autonomously (for scheduled tasks) and send result to user."""
    try:
        from core.orchestrator import run_task
        from core.memory import add_conversation
        
        logger.info(f"Executing scheduled task autonomously: {task[:50]}")

        lang = get_user_language(str(user_id)) or "en"
        result = run_task(task, language=lang)
        
        # Store conversation
        add_conversation(str(user_id), f"[SCHEDULED] {task}", str(result.get('result', t("generic_completed", lang))))
        memory_add_task(
            description=task,
            status="completed" if result.get("success", False) else "failed",
            agent_used="scheduler",
            result=str(result.get("result", t("generic_completed", lang)))[:1000],
            user_id=str(user_id),
        )
        
        # Send result to user via Telegram
        try:
            from telegram import Bot
            from core.config import get_telegram_token
            
            bot = Bot(token=get_telegram_token())
            
            if result.get('success', False):
                message = t("scheduled_task_completed", lang, task=task, result=result.get("result", t("generic_completed", lang))[:500])
            else:
                message = t("scheduled_task_failed", lang, task=task, result=result.get("result", t("unknown_error", lang))[:500])
            if get_voice_output(str(user_id)):
                await send_voice_response(bot, user_id, _voice_task_summary(message, lang), lang)
            else:
                await bot.send_message(chat_id=user_id, text=message)
            
        except Exception as e:
            logger.error(f"Failed to send scheduled task result to user {user_id}: {e}")
        
        return result
        
    except Exception as e:
        logger.exception(f"Failed to execute scheduled task: {task}")
        return {"success": False, "result": t("scheduled_task_execution_failed", "en", err=str(e)), "agent_used": "scheduler"}


async def cmd_copilot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage Copilot Mode: on | off | status | sensitivity."""
    if not update.message or not update.message.text or _ignore_if_unauthorized(update):
        return
    uid = _user_id(update)
    if uid is None:
        return
    lang = _user_lang(update)
    text = update.message.text.strip().lower()
    if " status" in text or text.endswith("status"):
        last_ts = _last_copilot_suggestion_at_per_user.get(uid)
        last_value = t("copilot_last_never", lang)
        if last_ts is not None:
            last_value = t("copilot_last_seconds_ago", lang, seconds=int(max(0, time() - last_ts)))
        await update.message.reply_text(
            t(
                "copilot_status",
                lang,
                active=t("copilot_state_active", lang) if _copilot_active.get(uid, False) else t("copilot_state_inactive", lang),
                sensitivity=_copilot_sensitivity_label(uid, lang),
                last=last_value,
            )
        )
        return
    if " sensitivity " in f" {text} ":
        requested = text.split("sensitivity", 1)[-1].strip().split()[0] if text.split("sensitivity", 1)[-1].strip() else ""
        if requested not in _COPILOT_SENSITIVITY_SECONDS:
            await update.message.reply_text(t("copilot_sensitivity_usage", lang))
            return
        _copilot_sensitivity_per_user[uid] = requested
        await update.message.reply_text(t("copilot_sensitivity_set", lang, sensitivity=t(f"copilot_sensitivity_{requested}", lang)))
        return
    if " off" in text or text.endswith("off"):
        _copilot_active[uid] = False
        await update.message.reply_text(t("copilot_off", lang))
    else:
        _copilot_active[uid] = True
        await update.message.reply_text(t("copilot_on", lang))


async def _send_copilot_suggestion(context: ContextTypes.DEFAULT_TYPE, user_id: int, message: str) -> None:
    """Send a Copilot suggestion message to a user."""
    lang = get_user_language(str(user_id)) or "en"
    if _voice_enabled(user_id):
        await send_voice_response(context.bot, user_id, message, lang)
        return
    await context.bot.send_message(chat_id=user_id, text=message)


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent tasks from memory."""
    if not update.message or _ignore_if_unauthorized(update):
        return
    lang = _user_lang(update)
    chat_id = _chat_id(update)
    if chat_id is None:
        await update.message.reply_text(t("cannot_identify_user", lang))
        return
    tasks = get_recent_tasks(limit=10, user_id=str(chat_id))
    if not tasks:
        await update.message.reply_text(t("memory_empty", lang))
        return
    lines = [t("memory_header", lang)]
    for task in tasks:
        if len(task.description) > 50:
            lines.append(t("memory_item_truncated", lang, status=task.status, description=task.description[:50]))
        else:
            lines.append(t("memory_item", lang, status=task.status, description=task.description))
    await update.message.reply_text("\n".join(lines))


async def cmd_patterns(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List active learned patterns for the requesting chat."""
    if not update.message or _ignore_if_unauthorized(update):
        return
    lang = _user_lang(update)
    chat_id = _chat_id(update)
    uid = _user_id(update)
    if chat_id is None or uid is None:
        await update.message.reply_text(t("cannot_identify_user", lang))
        return
    patterns = sorted(get_patterns(str(chat_id)), key=lambda pattern: pattern.confidence, reverse=True)
    if not patterns:
        _pattern_index_per_user[uid] = []
        await update.message.reply_text(t("patterns_empty", lang))
        return
    _pattern_index_per_user[uid] = [pattern.id for pattern in patterns]
    lines = [t("patterns_header", lang, n=len(patterns))]
    for index, pattern in enumerate(patterns, start=1):
        lines.append(_pattern_line(index, pattern, lang))
    await update.message.reply_text("\n".join(lines))


async def cmd_forget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear all stored learned data for the requesting chat."""
    if not update.message or not update.message.text or _ignore_if_unauthorized(update):
        return
    lang = _user_lang(update, update.message.text)
    chat_id = _chat_id(update)
    uid = _user_id(update)
    if chat_id is None:
        await update.message.reply_text(t("cannot_identify_user", lang))
        return
    parts = update.message.text.strip().split(maxsplit=1)
    if len(parts) < 2:
        await update.message.reply_text(t("usage_forget", lang))
        return
    arg = parts[1].strip().lower()
    if arg == "all":
        delete_all_patterns(str(chat_id))
        _pattern_index_per_user.pop(uid or 0, None)
        await update.message.reply_text(t("forget_cleared", lang))
        return
    if not arg.isdigit() or uid is None:
        await update.message.reply_text(t("usage_forget", lang))
        return
    index = int(arg)
    pattern_ids = _pattern_index_per_user.get(uid) or []
    if index < 1 or index > len(pattern_ids):
        await update.message.reply_text(t("pattern_not_found", lang, id=index))
        return
    pattern_id = pattern_ids[index - 1]
    if not delete_pattern(pattern_id, str(chat_id)):
        await update.message.reply_text(t("pattern_not_found", lang, id=index))
        return
    updated_ids = [pid for pid in pattern_ids if pid != pattern_id]
    _pattern_index_per_user[uid] = updated_ids
    await update.message.reply_text(t("pattern_removed", lang, id=index))


async def cmd_web(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Navigate to URL: /web https://example.com or /web example.com."""
    if not update.message or not update.message.text or _ignore_if_unauthorized(update):
        return
    text = update.message.text.strip()
    lang = _user_lang(update, text)
    url = text[5:].strip() if text.lower().startswith("/web") else text
    if not url:
        await update.message.reply_text(t("usage_web", lang))
        return
    chat_id = _chat_id(update)
    permission_action = get_command_permission_action("", user_id=str(chat_id) if chat_id is not None else None, category_override="web_browsing")
    if permission_action == "block":
        await update.message.reply_text(t("permission_blocked", lang))
        return
    if permission_action == "confirm":
        if not await _prompt_permission_confirmation(update, lang, url):
            await update.message.reply_text(t("permission_request_denied", lang))
            return
    from agents.web_agent import navigate
    r = navigate(url)
    if r.success:
        msg = t("web_page_loaded", lang, title=r.title or r.url, url=r.url)
        if r.content_preview:
            msg += "\n\n" + (r.content_preview[:500] + "..." if len(r.content_preview) > 500 else r.content_preview)
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text(t("web_error", lang, err=r.message))


async def cmd_ask(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask the LLM: /ask your question."""
    if not update.message or not update.message.text or _ignore_if_unauthorized(update):
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
        reply = reply[:4000] + t("truncated_suffix", lang)
    await update.message.reply_text(reply)
    await _maybe_send_voice_response(context, _chat_id(update), reply, lang)


async def _copilot_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job: full Copilot — analyze context, send suggestions and warnings."""
    try:
        config = load_config()
        copilot_cfg = config.get("copilot") or {}
        suggestions_ok = copilot_cfg.get("suggestions", True)
        warnings_ok = copilot_cfg.get("warnings", True)
        if not suggestions_ok and not warnings_ok:
            return
        tree = get_ax_tree(max_buttons=20, max_text_fields=5)
        if tree.get("error"):
            return
        for uid, active in list(_copilot_active.items()):
            if not active:
                continue
            lang = get_user_language(str(uid)) or "en"
            recent_tasks = get_recent_tasks(limit=1, user_id=str(uid))
            last_task = recent_tasks[0].description if recent_tasks else ""
            hints = analyze_context(
                warnings_enabled=warnings_ok,
                suggestions_enabled=suggestions_ok,
                lang=lang,
                tree=tree,
                user_id=str(uid),
                last_task=last_task,
                current_time=datetime.utcnow(),
            )
            if not hints:
                continue
            hint = next((h for h in hints if h.kind == "warning"), hints[0])
            if hint.kind == "suggestion":
                last_ts = _last_copilot_suggestion_at_per_user.get(uid)
                suggestion_cooldown = _copilot_cooldown_seconds(uid)
                if hint.source == "pattern":
                    suggestion_cooldown = max(suggestion_cooldown, 60.0)
                if last_ts is not None and (time() - last_ts) < suggestion_cooldown:
                    continue
            msg = hint.message
            last_msg = _last_copilot_message_per_user.get(uid)
            if last_msg == msg:
                continue
            app_name = hint.app or ""
            last_app = _last_app_per_user.get(uid)
            if hint.kind == "suggestion" and last_app == app_name:
                continue
            if app_name:
                _last_app_per_user[uid] = app_name
            try:
                await _send_copilot_suggestion(context, uid, msg)
                _last_copilot_message_per_user[uid] = msg
                if hint.kind == "suggestion":
                    _last_copilot_suggestion_at_per_user[uid] = time()
            except Exception:
                pass
    except Exception as e:
        logger.debug("Copilot job: %s", e)


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler — logs errors and recovers gracefully."""
    logger.error("Telegram error: %s", context.error, exc_info=context.error)
    if isinstance(update, Update) and update.message and not _ignore_if_unauthorized(update):
        try:
            lang = _user_lang(update)
            await update.message.reply_text(t("internal_error", lang))
        except Exception:
            pass


async def cmd_owner(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manage owner and allowed chats."""
    if not update.message or not update.message.text or _ignore_if_unauthorized(update):
        return

    chat_id = _chat_id(update)
    owner = get_owner()
    if owner and str(chat_id) != owner.chat_id:
        return

    lang = _user_lang(update, update.message.text)
    parts = update.message.text.strip().split()
    if len(parts) < 2:
        await update.message.reply_text(t("usage_owner", lang))
        return

    action = parts[1].lower()
    if action == "status":
        allowed = sorted(_authorized_chat_ids())
        await update.message.reply_text(
            t("owner_status", lang, owner=owner.chat_id if owner else "none", allowed=", ".join(allowed) or "none")
        )
        return
    if action == "allow" and len(parts) == 3:
        add_allowed_chat(parts[2])
        await update.message.reply_text(t("owner_allowed", lang, chat_id=parts[2]))
        return
    if action == "revoke" and len(parts) == 3:
        remove_allowed_chat(parts[2])
        await update.message.reply_text(t("owner_revoked", lang, chat_id=parts[2]))
        return
    await update.message.reply_text(t("usage_owner", lang))


def _full_access_mode() -> bool:
    """Treat non-strict shell mode as full-access mode."""
    config = load_config()
    return not (config.get("security") or {}).get("strict_shell", True)


async def _confirm_plan(uid: Optional[int], progress_msg, lang: str) -> bool:
    """Wait for user approval before running a multi-step plan."""
    if uid is None:
        return False
    if _full_access_mode():
        for seconds in range(5, 0, -1):
            await progress_msg.edit_text(t("dry_run_countdown", lang, seconds=seconds))
            await asyncio.sleep(1)
            if is_stop_requested():
                return False
        return True

    future: asyncio.Future = asyncio.get_running_loop().create_future()
    _pending_plan_decision[uid] = future
    try:
        return bool(await asyncio.wait_for(future, timeout=300.0))
    except asyncio.TimeoutError:
        return False
    finally:
        _pending_plan_decision.pop(uid, None)


async def _confirm_destructive_command(update: Update, lang: str, command: str) -> bool:
    """Require explicit confirmation before a destructive command."""
    if _full_access_mode():
        return True
    return await _prompt_permission_confirmation(update, lang, command)


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
    app.add_handler(CommandHandler("patterns", cmd_patterns))
    app.add_handler(CommandHandler("forget", cmd_forget))
    app.add_handler(CommandHandler("web", cmd_web))
    app.add_handler(CommandHandler("ask", cmd_ask))
    app.add_handler(CommandHandler("voice", cmd_voice))
    app.add_handler(CommandHandler("permissions", cmd_permissions))
    app.add_handler(CommandHandler("config", cmd_config))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("github", cmd_github))
    app.add_handler(CommandHandler("owner", cmd_owner))
    app.add_handler(CommandHandler("yes", cmd_yes))
    app.add_handler(CommandHandler("no", cmd_no))
    app.add_handler(CommandHandler("never", cmd_never))
    app.add_handler(CommandHandler("schedule", cmd_schedule))
    app.add_handler(CommandHandler("schedules", cmd_schedules))
    app.add_handler(CommandHandler("unschedule", cmd_unschedule))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice_message))
    app.add_error_handler(_error_handler)

    copilot_cfg = config.get("copilot") or {}
    interval = copilot_cfg.get("check_interval", 10)
    start_background_tracker(interval_seconds=max(interval, 30))
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
