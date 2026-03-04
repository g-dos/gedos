"""
GEDOS idle watcher — tracks user activity and end-of-day moments.
"""

from __future__ import annotations

from datetime import datetime
import logging
import threading
from typing import Optional

from core.behavior_tracker import get_active_patterns
from core.proactive_engine import known_user_ids, notify

logger = logging.getLogger(__name__)
IDLE_WATCHER_INTERVAL_SECONDS = 60
_LAST_INPUT_AT: dict[str, datetime] = {}
_LAST_END_OF_DAY_SENT: dict[str, str] = {}


def record_user_input(user_id: Optional[str]) -> None:
    """Update the last known input timestamp for a user."""
    if not user_id:
        return
    _LAST_INPUT_AT[str(user_id)] = datetime.now()


def _default_end_of_day_hour(user_id: str) -> int:
    """Use learned time patterns or 18:00 as the end-of-day default."""
    candidates = []
    for pattern in get_active_patterns(str(user_id)):
        trigger = (pattern.trigger or "").lower()
        if not trigger.startswith("time:") or "@" not in trigger:
            continue
        try:
            hour_text = trigger.split("@", 1)[1].split(":", 1)[0]
            hour = int(hour_text)
        except (TypeError, ValueError):
            continue
        if hour >= 15:
            candidates.append(hour)
    return max(candidates) if candidates else 18


def run_idle_watcher(stop_event: Optional[threading.Event] = None) -> None:
    """Run the idle watcher loop in the current thread."""
    stopper = stop_event or threading.Event()
    while not stopper.wait(IDLE_WATCHER_INTERVAL_SECONDS):
        try:
            now = datetime.now()
            for user_id in known_user_ids():
                last_input = _LAST_INPUT_AT.get(user_id)
                if last_input and (now - last_input).total_seconds() >= 600:
                    notify(user_id, "You seem idle. Anything you want me to handle?", "idle", "low")

                end_hour = _default_end_of_day_hour(user_id)
                day_key = now.strftime("%Y-%m-%d")
                if now.hour >= end_hour and _LAST_END_OF_DAY_SENT.get(user_id) != day_key:
                    sent = notify(user_id, "End of day. Want me to run the deploy before you leave?", "idle", "medium")
                    if sent:
                        _LAST_END_OF_DAY_SENT[user_id] = day_key
        except Exception:
            logger.exception("Idle watcher failed")
