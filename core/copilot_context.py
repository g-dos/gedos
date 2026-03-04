"""
GEDOS Copilot context — analyze AX Tree for proactive suggestions and warnings.
Full Copilot Mode: detect opportunities and risks.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.behavior_tracker import get_active_patterns
from core.config import load_config
from interfaces.i18n import t
from tools.ax_tree import get_ax_tree

logger = logging.getLogger(__name__)

DEFAULT_COPILOT_SENSITIVITY_SECONDS: dict[str, float] = {
    "high": 10.0,
    "medium": 30.0,
    "low": 120.0,
}

ERROR_RISK_KEYWORDS = (
    "error", "exception", "failed", "failure", "erro", "falha",
    "warning", "aviso", "traceback", "crash", "timeout",
)

@dataclass
class CopilotHint:
    """A suggestion or warning to send to the user."""
    kind: str  # "suggestion" | "warning"
    message: str
    app: Optional[str] = None
    task_hint: Optional[str] = None  # Suggested /task payload for "Run" button
    source: str = "generic"


def get_copilot_sensitivity_seconds() -> dict[str, float]:
    """Return Copilot cooldowns from config with sane defaults."""
    values = dict(DEFAULT_COPILOT_SENSITIVITY_SECONDS)
    try:
        configured = ((load_config().get("copilot") or {}).get("sensitivity") or {})
    except Exception:
        configured = {}
    for key in ("high", "medium", "low"):
        try:
            if key in configured:
                values[key] = max(float(configured[key]), 1.0)
        except (TypeError, ValueError):
            logger.warning("Invalid copilot sensitivity value for %s: %r", key, configured.get(key))
    return values


def _minutes_from_trigger(trigger: str, now: datetime) -> Optional[float]:
    """Return the absolute minute delta for a time-based trigger."""
    if not trigger.startswith("time:") or "@" not in trigger:
        return None
    try:
        payload = trigger[5:]
        day_name, hhmm = payload.split("@", 1)
        if day_name.lower() != now.strftime("%A").lower():
            return None
        hour_text, minute_text = hhmm.split(":", 1)
        target_minutes = int(hour_text) * 60 + int(minute_text)
        current_minutes = now.hour * 60 + now.minute
        return abs(current_minutes - target_minutes)
    except Exception:
        return None


def _pattern_matches(pattern, app_name: str, last_task: str, now: datetime) -> bool:
    """Return whether a learned pattern matches the current context."""
    trigger = (pattern.trigger or "").strip().lower()
    if pattern.type == "time_based":
        delta = _minutes_from_trigger(trigger, now)
        return delta is not None and delta <= 15
    if pattern.type == "context_based":
        return trigger == f"app:{app_name.lower().strip()}"
    if pattern.type == "workflow_based":
        return trigger == f"after:{last_task.lower().strip()}"
    return False


def analyze_context(
    max_buttons: int = 20,
    warnings_enabled: bool = True,
    suggestions_enabled: bool = True,
    lang: str = "en",
    tree: Optional[dict] = None,
    user_id: Optional[str] = None,
    last_task: Optional[str] = None,
    current_time: Optional[datetime] = None,
) -> list[CopilotHint]:
    """
    Analyze current AX Tree and return list of hints (suggestions and/or warnings).
    """
    hints: list[CopilotHint] = []
    if tree is None:
        try:
            tree = get_ax_tree(max_buttons=max_buttons, max_text_fields=5)
        except Exception as e:
            logger.debug("copilot analyze_context: %s", e)
            return hints

    if tree.get("error"):
        return hints

    app_name = (tree.get("app") or "").strip()
    now = current_time or datetime.utcnow()
    normalized_last_task = " ".join((last_task or "").strip().lower().split())
    all_text: list[str] = []
    all_window_titles: list[str] = []

    for w in tree.get("windows") or []:
        title = (w.get("title") or "").strip()
        if title:
            all_window_titles.append(title)
            all_text.append(title.lower())
    for b in tree.get("buttons") or []:
        title = (b.get("title") or "").strip()
        if title:
            all_text.append(title.lower())

    idle_seconds = int(
        tree.get("idle_seconds")
        or tree.get("idle_time_seconds")
        or 0
    )
    idle_minutes = int(tree.get("idle_minutes") or 0)

    if warnings_enabled and app_name and any(any(kw in text for kw in ERROR_RISK_KEYWORDS) for text in all_text):
        if "terminal" in app_name.lower() or "iterm" in app_name.lower():
            hints.append(CopilotHint(
                kind="warning",
                message=t("copilot_hint_terminal_error", lang),
                app=app_name,
                task_hint="fix the error shown in terminal",
            ))
        else:
            hints.append(CopilotHint(
                kind="warning",
                message=t("copilot_hint_warning_generic", lang),
                app=app_name,
                task_hint="investigate the error on screen",
            ))

    if suggestions_enabled and app_name:
        if user_id:
            for pattern in get_active_patterns(str(user_id)):
                if pattern.confidence < 0.6:
                    continue
                if not _pattern_matches(pattern, app_name, normalized_last_task, now):
                    continue
                hints.append(
                    CopilotHint(
                        kind="suggestion",
                        message=t("copilot_hint_pattern", lang, action=pattern.action),
                        app=app_name,
                        task_hint=pattern.action,
                        source="pattern",
                    )
                )
        app_lower = app_name.lower()
        window_text = " ".join(title.lower() for title in all_window_titles)

        if "vscode" in app_lower or "visual studio code" in app_lower:
            hints.append(CopilotHint(kind="suggestion", message=t("copilot_hint_vscode", lang), app=app_name, task_hint="run tests and check git status"))
        elif "terminal" in app_lower or "iterm" in app_lower:
            hints.append(CopilotHint(kind="suggestion", message=t("copilot_hint_terminal", lang), app=app_name, task_hint="run a command"))
        elif any(browser in app_lower for browser in ("safari", "chrome", "firefox", "edge")):
            if "pull request" in window_text or " /pull/" in window_text or " pr #" in window_text:
                hints.append(CopilotHint(kind="suggestion", message=t("copilot_hint_github_pr", lang), app=app_name, task_hint="summarize this PR"))
            else:
                hints.append(CopilotHint(kind="suggestion", message=t("copilot_hint_browser", lang), app=app_name))
        elif "finder" in app_lower:
            hints.append(CopilotHint(kind="suggestion", message=t("copilot_hint_finder", lang), app=app_name, task_hint="list files in current directory"))
        else:
            hints.append(CopilotHint(kind="suggestion", message=t("copilot_hint_generic", lang, app=app_name), app=app_name))

    if suggestions_enabled and (idle_seconds >= 600 or idle_minutes >= 10):
        hints.append(CopilotHint(
            kind="suggestion",
            message=t("copilot_hint_idle", lang),
            app=app_name or None,
            task_hint="check if there is anything to do",
        ))

    return hints
