"""
GEDOS proactive engine — central coordinator for proactive notifications.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, UTC, timedelta
import logging
import threading
from typing import Callable, Optional

from core.config import load_config
from core.memory import Context, Conversation, Task, get_owner, get_session

logger = logging.getLogger(__name__)

_VALID_CATEGORIES = {"screen", "system", "github", "idle", "briefing"}
_VALID_PRIORITIES = {"low", "medium", "high"}
_DEDUP_WINDOW = timedelta(minutes=10)
_GLOBAL_COOLDOWN = timedelta(seconds=30)
_SINKS: dict[str, Callable[[str, str, str, str], None]] = {}
_LAST_SENT_AT: dict[str, datetime] = {}
_RECENT_MESSAGES: dict[tuple[str, str], deque[datetime]] = {}
_LOCK = threading.Lock()


@dataclass(frozen=True, slots=True)
class ProactiveEvent:
    """Structured proactive notification payload."""

    user_id: str
    message: str
    category: str
    priority: str


def register_sink(name: str, callback: Callable[[str, str, str, str], None]) -> None:
    """Register a delivery sink by name."""
    with _LOCK:
        _SINKS[name] = callback


def unregister_sink(name: str) -> None:
    """Remove a delivery sink by name."""
    with _LOCK:
        _SINKS.pop(name, None)


def known_user_ids() -> list[str]:
    """Best-effort list of known local users/chats for proactive checks."""
    users: list[str] = []
    seen: set[str] = set()
    owner = get_owner()
    if owner and owner.chat_id not in seen:
        users.append(owner.chat_id)
        seen.add(owner.chat_id)
    try:
        with get_session() as session:
            for model, field in (
                (Conversation, Conversation.user_id),
                (Task, Task.user_id),
                (Context, Context.user_id),
            ):
                rows = session.query(field).filter(field.is_not(None)).distinct().all()
                for (value,) in rows:
                    key = str(value).strip()
                    if key and key not in seen:
                        users.append(key)
                        seen.add(key)
    except Exception:
        logger.exception("Failed to enumerate proactive users")
    return users


def _effective_cooldown(user_id: str) -> timedelta:
    """Resolve the effective cooldown for a user using Copilot sensitivity."""
    values = {"high": 10.0, "medium": 30.0, "low": 120.0}
    try:
        configured = ((load_config().get("copilot") or {}).get("sensitivity") or {})
        for key in ("high", "medium", "low"):
            if key in configured:
                values[key] = max(float(configured[key]), 1.0)
    except Exception:
        pass
    sensitivity = "medium"
    try:
        from interfaces.telegram_bot import _copilot_sensitivity_per_user

        if str(user_id).isdigit():
            sensitivity = _copilot_sensitivity_per_user.get(int(user_id), "medium")
    except Exception:
        sensitivity = "medium"
    seconds = max(30.0, float(values.get(sensitivity, values["medium"])))
    return timedelta(seconds=seconds)


def _is_duplicate(user_id: str, message: str, now: datetime) -> bool:
    """Return whether the same message was recently sent to the same user."""
    key = (str(user_id), message.strip())
    entries = _RECENT_MESSAGES.setdefault(key, deque())
    cutoff = now - _DEDUP_WINDOW
    while entries and entries[0] < cutoff:
        entries.popleft()
    if entries:
        return True
    entries.append(now)
    return False


def notify(user_id: str, message: str, category: str, priority: str) -> bool:
    """Attempt to deliver a proactive notification, respecting cooldown and dedupe."""
    normalized_user = str(user_id).strip()
    normalized_message = (message or "").strip()
    if not normalized_user or not normalized_message:
        return False
    if category not in _VALID_CATEGORIES or priority not in _VALID_PRIORITIES:
        logger.warning("Ignoring invalid proactive event: category=%s priority=%s", category, priority)
        return False

    now = datetime.now(UTC)
    event = ProactiveEvent(normalized_user, normalized_message, category, priority)
    with _LOCK:
        last_sent = _LAST_SENT_AT.get(event.user_id)
        if last_sent and (now - last_sent) < _effective_cooldown(event.user_id):
            return False
        if _is_duplicate(event.user_id, event.message, now):
            return False
        sinks = list(_SINKS.values())
        if not sinks:
            return False
        _LAST_SENT_AT[event.user_id] = now

    delivered = False
    for sink in sinks:
        try:
            sink(event.user_id, event.message, event.category, event.priority)
            delivered = True
        except Exception:
            logger.exception("Proactive sink failed")
    return delivered
