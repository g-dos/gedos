"""
GEDOS GUI Agent — coordinates AX Tree + mouse + keyboard for GUI control.
Finds elements via AX Tree and performs clicks / typing.
"""

import logging
from typing import Optional

from core.config import get_agent_config
from core.retry import retry_with_backoff
from tools.ax_tree import find_button_by_title, get_ax_tree
from tools.mouse import click_at_center, move, click
from tools import keyboard

logger = logging.getLogger(__name__)


def click_button(title_substring: str, max_retries: Optional[int] = None) -> bool:
    """
    Find a button in the frontmost app whose title contains title_substring,
    then click at its center. Retries on failure (AX Tree may need time).
    """
    cfg = get_agent_config("gui")
    retries = max_retries if max_retries is not None else cfg.get("max_retries", 3)

    def _attempt() -> bool:
        el = find_button_by_title(title_substring)
        if not el or "frame" not in el:
            raise LookupError(f"Button not found: {title_substring!r}")
        return click_at_center(el["frame"])

    try:
        return retry_with_backoff(_attempt, max_attempts=retries, base_delay=0.5, label=f"click_button({title_substring!r})")
    except LookupError:
        logger.warning("click_button: no button found for %r after %d attempts", title_substring, retries)
        return False


def get_screen_summary() -> dict:
    """Return a short summary of the current screen (app, windows, buttons) for reports."""
    return get_ax_tree(max_buttons=30, max_text_fields=10)


def type_into_focused(text: str) -> bool:
    """Type text into the currently focused element (e.g. text field)."""
    return keyboard.type_text(text)


def press_key(key: str) -> bool:
    """Press a key (enter, tab, esc, etc.)."""
    return keyboard.press(key)


def hotkey(*keys: str) -> bool:
    """Press a key combination (e.g. command+c)."""
    return keyboard.hotkey(*keys)
