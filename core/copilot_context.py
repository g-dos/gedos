"""
GEDOS Copilot context — analyze AX Tree for proactive suggestions and warnings.
Full Copilot Mode: detect opportunities and risks.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from tools.ax_tree import get_ax_tree

logger = logging.getLogger(__name__)

ERROR_RISK_KEYWORDS = (
    "error", "exception", "failed", "failure", "erro", "falha",
    "warning", "aviso", "traceback", "crash", "timeout",
)

APP_SUGGESTIONS = {
    "terminal": "Want me to run a command in Terminal?",
    "iterm": "Want me to run a command?",
    "vscode": "Want me to commit, run tests, or search for something?",
    "visual studio code": "Want me to commit, run tests, or search for something?",
    "xcode": "Want me to run the build or do something in the project?",
    "cursor": "Want me to run a command or commit?",
    "safari": "Want me to search or open a page?",
    "chrome": "Want me to search or open a page?",
    "finder": "Want me to list files or open something?",
}


@dataclass
class CopilotHint:
    """A suggestion or warning to send to the user."""
    kind: str  # "suggestion" | "warning"
    message: str
    app: Optional[str] = None


def analyze_context(
    max_buttons: int = 20,
    warnings_enabled: bool = True,
    suggestions_enabled: bool = True,
) -> list[CopilotHint]:
    """
    Analyze current AX Tree and return list of hints (suggestions and/or warnings).
    """
    hints: list[CopilotHint] = []
    try:
        tree = get_ax_tree(max_buttons=max_buttons, max_text_fields=5)
    except Exception as e:
        logger.debug("copilot analyze_context: %s", e)
        return hints

    if tree.get("error"):
        return hints

    app_name = (tree.get("app") or "").strip()
    all_text: list[str] = []

    for w in tree.get("windows") or []:
        t = (w.get("title") or "").strip()
        if t:
            all_text.append(t.lower())
    for b in tree.get("buttons") or []:
        t = (b.get("title") or "").strip()
        if t:
            all_text.append(t.lower())

    if warnings_enabled and app_name:
        for kw in ERROR_RISK_KEYWORDS:
            if any(kw in t for t in all_text):
                hints.append(CopilotHint(
                    kind="warning",
                    message=f"Detected something related to \"{kw}\" on screen. Want me to investigate?",
                    app=app_name,
                ))
                break

    if suggestions_enabled and app_name:
        app_lower = app_name.lower()
        for key, suggestion in APP_SUGGESTIONS.items():
            if key in app_lower:
                hints.append(CopilotHint(
                    kind="suggestion",
                    message=suggestion,
                    app=app_name,
                ))
                break
        else:
            hints.append(CopilotHint(
                kind="suggestion",
                message=f"You're in {app_name}. Want me to do something?",
                app=app_name,
            ))

    return hints
