"""
GEDOS behavior tracker — learns repeated task patterns from task history.
"""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
import logging
import threading
from typing import Optional
from uuid import uuid4

from core.audit_log import log_action
from core.memory import (
    add_or_update_pattern,
    decay_patterns,
    get_patterns as memory_get_patterns,
    get_recent_tasks,
)

logger = logging.getLogger(__name__)

_SEEN_TASK_IDS: deque[int] = deque(maxlen=500)
_SEEN_TASK_SET: set[int] = set()
_TRACKER_THREAD: Optional[threading.Thread] = None
_STOP_TRACKER = threading.Event()
_TRACKER_LOCK = threading.Lock()


def _normalize_action(task: str) -> str:
    """Normalize task text into a stable action signature."""
    return " ".join((task or "").strip().lower().split())


def _remember_task(task_id: Optional[int]) -> bool:
    """Return True once for each seen task id."""
    if task_id is None:
        return False
    if task_id in _SEEN_TASK_SET:
        return False
    if len(_SEEN_TASK_IDS) == _SEEN_TASK_IDS.maxlen:
        dropped = _SEEN_TASK_IDS.popleft()
        _SEEN_TASK_SET.discard(dropped)
    _SEEN_TASK_IDS.append(task_id)
    _SEEN_TASK_SET.add(task_id)
    return True


def _upsert_pattern(user_id: str, pattern_type: str, trigger: str, action: str, seen_at: datetime):
    """Create or increment a pattern record and flag first confirmation."""
    from core.memory import get_session, Pattern

    with get_session() as session:
        existing = (
            session.query(Pattern)
            .filter(Pattern.user_id == str(user_id), Pattern.trigger == trigger, Pattern.action == action)
            .first()
        )
        if existing:
            next_occurrences = existing.occurrences + 1
            was_inactive = not existing.active
            add_or_update_pattern(
                {
                    "id": existing.id,
                    "user_id": existing.user_id,
                    "type": pattern_type,
                    "trigger": trigger,
                    "action": action,
                    "occurrences": next_occurrences,
                    "last_seen": max(existing.last_seen, seen_at),
                    "confidence": min(next_occurrences / 10.0, 1.0),
                    "active": next_occurrences >= 3,
                    "suppressed": existing.suppressed,
                    "automated": existing.automated,
                },
                session=session,
            )
            refreshed = (
                session.query(Pattern)
                .filter(Pattern.user_id == str(user_id), Pattern.trigger == trigger, Pattern.action == action)
                .first()
            )
            return refreshed, bool(refreshed and was_inactive and refreshed.active and not refreshed.suppressed)
        created = add_or_update_pattern(
            {
                "id": str(uuid4()),
                "user_id": str(user_id),
                "type": pattern_type,
                "trigger": trigger,
                "action": action,
                "occurrences": 1,
                "last_seen": seen_at,
                "confidence": 0.1,
                "active": False,
            },
            session=session,
        )
        return created, False


def get_active_patterns(user_id: str):
    """Return active non-suppressed patterns for a user."""
    patterns = memory_get_patterns(str(user_id), include_suppressed=True)
    return [pattern for pattern in patterns if not getattr(pattern, "suppressed", False)]


def observe(task: str, user_id: Optional[str], context: Optional[dict] = None) -> list:
    """Inspect a completed task and learn repeated patterns for that user."""
    if not user_id or not task:
        return []

    context = dict(context or {})
    action = _normalize_action(task)
    if not action:
        return []

    seen_at = context.get("time")
    if not isinstance(seen_at, datetime):
        seen_at = datetime.now(UTC).replace(tzinfo=None)

    decay_patterns(str(user_id))
    newly_confirmed = []

    weekday = seen_at.strftime("%A").lower()
    hour = seen_at.strftime("%H:00")
    pattern, confirmed = _upsert_pattern(str(user_id), "time_based", f"time:{weekday}@{hour}", action, seen_at)
    if confirmed:
        newly_confirmed.append(pattern)
        log_action(
            "pattern_detected",
            {"type": "time_based", "trigger": getattr(pattern, "trigger", f"time:{weekday}@{hour}"), "action": getattr(pattern, "action", action)},
            str(user_id),
            "confirmed",
        )

    current_app = " ".join(str(context.get("current_app") or "").strip().split())
    if current_app:
        pattern, confirmed = _upsert_pattern(str(user_id), "context_based", f"app:{current_app.lower()}", action, seen_at)
        if confirmed:
            newly_confirmed.append(pattern)
            log_action(
                "pattern_detected",
                {"type": "context_based", "trigger": getattr(pattern, "trigger", f"app:{current_app.lower()}"), "action": getattr(pattern, "action", action)},
                str(user_id),
                "confirmed",
            )

    preceding_task = _normalize_action(str(context.get("preceding_task") or ""))
    if preceding_task and preceding_task != action:
        pattern, confirmed = _upsert_pattern(str(user_id), "workflow_based", f"after:{preceding_task}", action, seen_at)
        if confirmed:
            newly_confirmed.append(pattern)
            log_action(
                "pattern_detected",
                {"type": "workflow_based", "trigger": getattr(pattern, "trigger", f"after:{preceding_task}"), "action": getattr(pattern, "action", action)},
                str(user_id),
                "confirmed",
            )
    return newly_confirmed


def observe_recent_history(limit: int = 100) -> int:
    """Scan recent completed tasks and learn patterns from history."""
    observed = 0
    tasks = get_recent_tasks(limit=limit)
    tasks_by_user: dict[str, list] = {}
    for task in reversed(tasks):
        if task.status != "completed" or not task.user_id:
            continue
        tasks_by_user.setdefault(task.user_id, []).append(task)

    for user_id, user_tasks in tasks_by_user.items():
        previous_task = None
        for task in user_tasks:
            if not _remember_task(task.id):
                previous_task = task
                continue
            observe(
                task.description,
                str(user_id),
                {
                    "time": task.created_at,
                    "preceding_task": previous_task.description if previous_task else "",
                },
            )
            observed += 1
            previous_task = task
    return observed


def _tracker_loop(interval_seconds: int) -> None:
    """Background loop that periodically scans recent task history."""
    while not _STOP_TRACKER.wait(interval_seconds):
        try:
            observed = observe_recent_history()
            if observed:
                logger.info("Behavior tracker observed %d tasks from history", observed)
        except Exception:
            logger.exception("Behavior tracker background scan failed")


def start_background_tracker(interval_seconds: int = 60) -> None:
    """Start the background behavior tracker if it is not already running."""
    global _TRACKER_THREAD
    with _TRACKER_LOCK:
        if _TRACKER_THREAD and _TRACKER_THREAD.is_alive():
            return
        _STOP_TRACKER.clear()
        _TRACKER_THREAD = threading.Thread(
            target=_tracker_loop,
            args=(max(5, int(interval_seconds)),),
            daemon=True,
            name="gedos-behavior-tracker",
        )
        _TRACKER_THREAD.start()


def stop_background_tracker(timeout_seconds: float = 1.0) -> None:
    """Stop the background tracker loop."""
    global _TRACKER_THREAD
    with _TRACKER_LOCK:
        if not _TRACKER_THREAD:
            return
        _STOP_TRACKER.set()
        _TRACKER_THREAD.join(timeout=timeout_seconds)
        _TRACKER_THREAD = None
