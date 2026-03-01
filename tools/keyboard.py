"""
GEDOS keyboard control — typing and shortcuts via PyAutoGUI.
"""

import logging
import time
from typing import List, Optional

logger = logging.getLogger(__name__)

try:
    import pyautogui
    _PYAUTOGUI_AVAILABLE = True
except ImportError:
    _PYAUTOGUI_AVAILABLE = False
    pyautogui = None  # type: ignore


def type_text(text: str, interval: Optional[float] = 0.02) -> bool:
    """Type a string with optional delay between keys."""
    if not _PYAUTOGUI_AVAILABLE:
        logger.warning("PyAutoGUI not available")
        return False
    try:
        pyautogui.write(text, interval=interval or 0)
        return True
    except Exception as e:
        logger.warning("keyboard.type_text: %s", e)
        return False


def press(key: str) -> bool:
    """Press a single key (e.g. 'enter', 'tab', 'esc')."""
    if not _PYAUTOGUI_AVAILABLE:
        return False
    try:
        pyautogui.press(key)
        return True
    except Exception as e:
        logger.warning("keyboard.press: %s", e)
        return False


def hotkey(*keys: str) -> bool:
    """Press a key combination (e.g. hotkey('command', 'c') for copy)."""
    if not _PYAUTOGUI_AVAILABLE:
        return False
    try:
        pyautogui.hotkey(*keys)
        return True
    except Exception as e:
        logger.warning("keyboard.hotkey: %s", e)
        return False


def type_with_modifiers(text: str, modifier: Optional[str] = None) -> bool:
    """Type text; if modifier is set (e.g. 'command'), type with modifier held."""
    if not modifier:
        return type_text(text)
    if not _PYAUTOGUI_AVAILABLE:
        return False
    try:
        with pyautogui.hold(modifier):
            pyautogui.write(text, interval=0.02)
        return True
    except Exception as e:
        logger.warning("keyboard.type_with_modifiers: %s", e)
        return False
