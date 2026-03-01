"""
GEDOS Copilot context — analyze AX Tree for proactive suggestions and warnings.
Full Copilot Mode: detect opportunities and risks.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from tools.ax_tree import get_ax_tree

logger = logging.getLogger(__name__)

# Substrings that suggest an error or risk (window titles, UI text)
ERROR_RISK_KEYWORDS = (
    "error", "exception", "failed", "failure", "erro", "falha",
    "warning", "aviso", "traceback", "crash", "timeout",
)

# App name -> suggested action (lowercase match)
APP_SUGGESTIONS = {
    "terminal": "Quer que eu execute algum comando no Terminal?",
    "iterm": "Quer que eu execute algum comando?",
    "vscode": "Quer que eu faça commit, rode testes ou busque algo?",
    "visual studio code": "Quer que eu faça commit, rode testes ou busque algo?",
    "xcode": "Quer que eu rode o build ou faça algo no projeto?",
    "cursor": "Quer que eu execute um comando ou faça commit?",
    "safari": "Quer que eu pesquise ou abra uma página?",
    "chrome": "Quer que eu pesquise ou abra uma página?",
    "finder": "Quer que eu liste arquivos ou abra algo?",
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

    # Warnings: error-like content on screen
    if warnings_enabled and app_name:
        for kw in ERROR_RISK_KEYWORDS:
            if any(kw in t for t in all_text):
                hints.append(CopilotHint(
                    kind="warning",
                    message=f"Parece que há algo relacionado a \"{kw}\" na tela. Quer que eu ajude a investigar?",
                    app=app_name,
                ))
                break

    # Suggestions: based on active app
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
            # Generic when app changed
            hints.append(CopilotHint(
                kind="suggestion",
                message=f"Você está em {app_name}. Quer que eu faça algo?",
                app=app_name,
            ))

    return hints
