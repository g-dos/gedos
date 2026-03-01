"""
GEDOS mouse control — abstraction over PyAutoGUI + macOS Accessibility.
Click, move, drag.
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import pyautogui
    _PYAUTOGUI_AVAILABLE = True
except ImportError:
    _PYAUTOGUI_AVAILABLE = False
    pyautogui = None  # type: ignore


def move(x: float, y: float) -> bool:
    """Move mouse to (x, y). Returns True on success."""
    if not _PYAUTOGUI_AVAILABLE:
        logger.warning("PyAutoGUI not available")
        return False
    try:
        pyautogui.moveTo(x, y)
        return True
    except Exception as e:
        logger.warning("mouse.move: %s", e)
        return False


def click(x: Optional[float] = None, y: Optional[float] = None, button: str = "left") -> bool:
    """Click at (x, y) or current position. button: left, right, middle."""
    if not _PYAUTOGUI_AVAILABLE:
        return False
    try:
        if x is not None and y is not None:
            pyautogui.click(x, y, button=button)
        else:
            pyautogui.click(button=button)
        return True
    except Exception as e:
        logger.warning("mouse.click: %s", e)
        return False


def double_click(x: Optional[float] = None, y: Optional[float] = None) -> bool:
    """Double-click at (x, y) or current position."""
    if not _PYAUTOGUI_AVAILABLE:
        return False
    try:
        if x is not None and y is not None:
            pyautogui.doubleClick(x, y)
        else:
            pyautogui.doubleClick()
        return True
    except Exception as e:
        logger.warning("mouse.double_click: %s", e)
        return False


def position() -> Tuple[float, float]:
    """Return current (x, y) mouse position."""
    if not _PYAUTOGUI_AVAILABLE:
        return (0.0, 0.0)
    try:
        p = pyautogui.position()
        return (float(p[0]), float(p[1]))
    except Exception:
        return (0.0, 0.0)


def drag(start_x: float, start_y: float, end_x: float, end_y: float, duration: float = 0.2) -> bool:
    """Drag from (start_x, start_y) to (end_x, end_y)."""
    if not _PYAUTOGUI_AVAILABLE:
        return False
    try:
        pyautogui.moveTo(start_x, start_y)
        pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration)
        return True
    except Exception as e:
        logger.warning("mouse.drag: %s", e)
        return False


def click_at_center(frame: dict) -> bool:
    """
    Click at the center of a frame dict with keys x, y, width, height.
    Used with AX Tree element frames.
    """
    try:
        cx = frame["x"] + frame["width"] / 2
        cy = frame["y"] + frame["height"] / 2
        return click(cx, cy)
    except (KeyError, TypeError) as e:
        logger.warning("click_at_center: invalid frame %s", e)
        return False
