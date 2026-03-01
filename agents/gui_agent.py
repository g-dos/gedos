"""
GEDOS GUI Agent — coordinates AX Tree + mouse + keyboard for GUI control.
Finds elements via AX Tree and performs clicks / typing.
"""

import logging
from typing import Optional

from tools.ax_tree import find_button_by_title, get_ax_tree
from tools.mouse import click_at_center, move, click
from tools import keyboard

logger = logging.getLogger(__name__)


def click_button(title_substring: str) -> bool:
    """
    Find a button in the frontmost app whose title contains title_substring,
    then click at its center. Returns True if found and clicked.
    """
    el = find_button_by_title(title_substring)
    if not el or "frame" not in el:
        logger.warning("click_button: no button found for %r", title_substring)
        return False
    return click_at_center(el["frame"])


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
