"""
GEDOS GitHub watcher — polls GitHub for repo activity and CI status changes.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Optional

from github import Github

from core.proactive_engine import known_user_ids, notify

logger = logging.getLogger(__name__)
GITHUB_WATCHER_INTERVAL_SECONDS = 300
_SEEN_ISSUES: set[int] = set()
_SEEN_PULLS: set[int] = set()
_SEEN_RUNS: dict[tuple[str, int], str] = {}
_SEEN_REVIEW_REQUESTS: set[tuple[str, int]] = set()


def _pick_user_id() -> Optional[str]:
    users = known_user_ids()
    return users[0] if users else None


def _client() -> Optional[Github]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        return None
    return Github(token)


def _watched_repos(client: Github):
    """Return a small set of recent repos to poll."""
    repos = []
    try:
        for repo in client.get_user().get_repos(sort="updated", direction="desc")[:5]:
            repos.append(repo)
    except Exception:
        logger.exception("Failed to list GitHub repos for watcher")
    return repos


def _poll_repo(repo, user_id: str) -> None:
    """Poll one repository and emit notifications for new activity."""
    full_name = repo.full_name
    for issue in repo.get_issues(state="open", sort="created", direction="desc")[:10]:
        if issue.pull_request:
            continue
        if issue.id in _SEEN_ISSUES:
            continue
        _SEEN_ISSUES.add(issue.id)
        notify(user_id, f"📌 New issue opened in {full_name}: #{issue.number} {issue.title}", "github", "medium")

    for pr in repo.get_pulls(state="open", sort="created", direction="desc")[:10]:
        if pr.id not in _SEEN_PULLS:
            _SEEN_PULLS.add(pr.id)
            notify(user_id, f"🔀 New PR opened in {full_name}: #{pr.number} {pr.title}", "github", "medium")
        review_key = (full_name, pr.number)
        if pr.requested_reviewers and review_key not in _SEEN_REVIEW_REQUESTS:
            _SEEN_REVIEW_REQUESTS.add(review_key)
            notify(user_id, f"👀 Review requested on {full_name} PR #{pr.number}. Want me to summarize it?", "github", "medium")

    try:
        for run in repo.get_workflow_runs(status="completed")[:10]:
            key = (full_name, run.id)
            previous = _SEEN_RUNS.get(key)
            _SEEN_RUNS[key] = run.conclusion or ""
            if previous is None and run.conclusion == "failure":
                notify(user_id, f"❌ CI failed in {full_name}: {run.name}", "github", "high")
    except Exception:
        logger.debug("Workflow polling unavailable for %s", full_name)


def run_github_watcher(stop_event: Optional[threading.Event] = None) -> None:
    """Run the GitHub watcher loop in the current thread."""
    client = _client()
    if client is None:
        return
    stopper = stop_event or threading.Event()
    while not stopper.wait(GITHUB_WATCHER_INTERVAL_SECONDS):
        try:
            user_id = _pick_user_id()
            if not user_id:
                continue
            for repo in _watched_repos(client):
                _poll_repo(repo, user_id)
        except Exception:
            logger.exception("GitHub watcher failed")
