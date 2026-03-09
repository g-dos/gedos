"""
GEDOS morning briefing watcher — sends a daily kickoff summary.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
import os
import threading
from typing import Optional

from github import Github

from core.behavior_tracker import get_active_patterns
from core.memory import get_recent_tasks
from core.proactive_engine import known_user_ids, notify

logger = logging.getLogger(__name__)
MORNING_BRIEFING_INTERVAL_SECONDS = 60
_LAST_BRIEFING_DAY: dict[str, str] = {}


def _start_hour_for_user(user_id: str) -> int:
    """Use a learned morning time or default to 09:00."""
    candidates: list[int] = []
    for pattern in get_active_patterns(str(user_id)):
        trigger = (pattern.trigger or "").lower()
        if not trigger.startswith("time:") or "@" not in trigger:
            continue
        try:
            hour = int(trigger.split("@", 1)[1].split(":", 1)[0])
        except (TypeError, ValueError):
            continue
        if 5 <= hour <= 12:
            candidates.append(hour)
    return min(candidates) if candidates else 9


def _github_summary() -> tuple[int, int, str]:
    """Return (open_prs, open_issues, ci_status)."""
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        return 0, 0, "unknown"
    try:
        client = Github(token)
        open_prs = 0
        open_issues = 0
        ci_status = "green"
        for repo in client.get_user().get_repos(sort="updated", direction="desc")[:5]:
            open_prs += repo.get_pulls(state="open").totalCount
            open_issues += sum(1 for issue in repo.get_issues(state="open")[:20] if not issue.pull_request)
            try:
                latest = next(iter(repo.get_workflow_runs(status="completed")[:1]), None)
            except Exception:
                latest = None
            if latest and latest.conclusion == "failure":
                ci_status = "failing"
        return open_prs, open_issues, ci_status
    except Exception:
        logger.debug("Morning briefing GitHub summary unavailable")
        return 0, 0, "unknown"


def _build_briefing(user_id: str) -> str:
    """Build the morning summary text."""
    tasks = get_recent_tasks(limit=50, user_id=str(user_id))
    since = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    completed = sum(1 for task in tasks if task.status == "completed" and task.created_at >= since)
    scheduled = sum(1 for task in tasks if task.agent_used == "scheduler" and task.created_at >= since)
    open_prs, open_issues, ci_status = _github_summary()
    name = "there"
    try:
        from core.config import load_gedos_profile

        name = str(load_gedos_profile().get("name") or "there")
    except Exception:
        name = "there"
    return (
        f"☀️ Good morning {name}.\n\n"
        "Yesterday:\n"
        f"✅ {completed} tasks completed\n"
        f"✅ {scheduled} scheduled tasks ran\n\n"
        "Today:\n"
        f"• {open_prs} open PRs\n"
        f"• CI status: {ci_status}\n"
        f"• {open_issues} new issues\n\n"
        "Anything to start with?"
    )


def run_morning_briefing_watcher(stop_event: Optional[threading.Event] = None) -> None:
    """Run the daily morning briefing loop."""
    stopper = stop_event or threading.Event()
    while not stopper.wait(MORNING_BRIEFING_INTERVAL_SECONDS):
        try:
            now = datetime.now()
            for user_id in known_user_ids():
                target_hour = _start_hour_for_user(user_id)
                day_key = now.strftime("%Y-%m-%d")
                if now.hour == target_hour and now.minute < 15 and _LAST_BRIEFING_DAY.get(user_id) != day_key:
                    if notify(user_id, _build_briefing(user_id), "briefing", "medium"):
                        _LAST_BRIEFING_DAY[user_id] = day_key
        except Exception:
            logger.exception("Morning briefing watcher failed")
