"""
GEDOS AX Tree — macOS Accessibility Tree reader.
Extracts structured UI data (buttons, fields, menus, windows) as JSON without vision APIs.
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import atomacos
    from atomacos.AXClasses import NativeUIElement
    from atomacos.errors import AXError, AXErrorAPIDisabled
    _ATOMACOS_AVAILABLE = True
except ImportError:
    _ATOMACOS_AVAILABLE = False
    NativeUIElement = None  # type: ignore


def _element_to_dict(element: Any) -> Optional[dict[str, Any]]:
    """Convert an atomacos element to a serializable dict with role, title, frame."""
    if not _ATOMACOS_AVAILABLE or element is None:
        return None
    try:
        role = getattr(element, "AXRole", None)
        title = getattr(element, "AXTitle", None) or getattr(element, "AXDescription", None)
        role = str(role) if role else "unknown"
        title = str(title) if title else ""

        frame = None
        pos = getattr(element, "AXPosition", None)
        size = getattr(element, "AXSize", None)
        if pos is not None and size is not None:
            try:
                frame = {
                    "x": float(pos[0]) if hasattr(pos, "__getitem__") else float(getattr(pos, "x", 0)),
                    "y": float(pos[1]) if hasattr(pos, "__getitem__") else float(getattr(pos, "y", 0)),
                    "width": float(size[0]) if hasattr(size, "__getitem__") else float(getattr(size, "width", 0)),
                    "height": float(size[1]) if hasattr(size, "__getitem__") else float(getattr(size, "height", 0)),
                }
            except (TypeError, IndexError, AttributeError, ValueError):
                pass
        if frame is None:
            axframe = getattr(element, "AXFrame", None)
            if axframe is not None:
                try:
                    if hasattr(axframe, "__getitem__") and len(axframe) >= 4:
                        frame = {"x": float(axframe[0]), "y": float(axframe[1]), "width": float(axframe[2]), "height": float(axframe[3])}
                    elif hasattr(axframe, "origin") and hasattr(axframe, "size"):
                        frame = {"x": float(axframe.origin.x), "y": float(axframe.origin.y), "width": float(axframe.size.width), "height": float(axframe.size.height)}
                except (TypeError, AttributeError, ValueError):
                    pass

        out: dict[str, Any] = {"role": role, "title": title}
        if frame:
            out["frame"] = frame
        return out
    except Exception as e:
        logger.debug("ax_tree: skip element %s", e)
        return None


def get_frontmost_app_name() -> Optional[str]:
    """Return the localized name of the frontmost application, or None if unavailable."""
    if not _ATOMACOS_AVAILABLE:
        return None
    try:
        app = NativeUIElement.getFrontmostApp()
        return app.getLocalizedName()
    except (AXError, AXErrorAPIDisabled, ValueError) as e:
        logger.warning("get_frontmost_app_name: %s", e)
        return None


def get_ax_tree(max_buttons: int = 50, max_text_fields: int = 20) -> dict[str, Any]:
    """
    Get structured AX tree for the frontmost application.
    Returns a dict with app name, windows, buttons, and text fields (for JSON/Telegram).
    """
    result: dict[str, Any] = {
        "app": None,
        "windows": [],
        "buttons": [],
        "text_fields": [],
        "error": None,
    }
    if not _ATOMACOS_AVAILABLE:
        result["error"] = "atomacos not available"
        return result

    try:
        app = NativeUIElement.getFrontmostApp()
        result["app"] = app.getLocalizedName()
    except AXErrorAPIDisabled:
        result["error"] = "Accessibility API disabled. Enable in System Preferences > Security & Privacy > Accessibility."
        return result
    except (AXError, ValueError) as e:
        result["error"] = str(e)
        return result

    try:
        # Windows
        for win in app.windows()[:10]:
            d = _element_to_dict(win)
            if d:
                result["windows"].append(d)

        # Buttons (recursive)
        for btn in app.buttonsR()[:max_buttons]:
            d = _element_to_dict(btn)
            if d and (d.get("title") or d.get("role")):
                result["buttons"].append(d)

        # Text fields
        try:
            for tf in app.textFieldsR()[:max_text_fields]:
                d = _element_to_dict(tf)
                if d:
                    result["text_fields"].append(d)
        except Exception:
            pass

    except Exception as e:
        result["error"] = str(e)

    return result


def get_ax_tree_json(max_buttons: int = 50, max_text_fields: int = 20) -> str:
    """Return the AX tree as a JSON string."""
    return json.dumps(get_ax_tree(max_buttons=max_buttons, max_text_fields=max_text_fields), ensure_ascii=False, indent=2)


def find_button_by_title(title_substring: str) -> Optional[dict[str, Any]]:
    """
    Find the first button in the frontmost app whose title contains the given substring.
    Returns element dict with frame for clicking, or None.
    """
    if not _ATOMACOS_AVAILABLE:
        return None
    try:
        app = NativeUIElement.getFrontmostApp()
        low = title_substring.lower()
        for btn in app.buttonsR():
            d = _element_to_dict(btn)
            if d and low in (d.get("title") or "").lower():
                return d
    except Exception as e:
        logger.warning("find_button_by_title: %s", e)
    return None
