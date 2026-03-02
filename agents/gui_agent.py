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


def execute_step(step) -> dict[str, str]:
    """
    Execute a structured task step using the GUI agent.
    
    Args:
        step: TaskStep object with agent, action, expected_result fields
        
    Returns:
        Dict with success, result, agent_used fields
    """
    try:
        import subprocess
        import time
        import re
        
        action = step.action
        low = action.lower()
        
        # Handle app opening commands
        for app in ("safari", "chrome", "firefox", "edge", "finder", "terminal", "vscode", "code"):
            if f"open -a" in low and app in low:
                app_map = {
                    "safari": "Safari",
                    "chrome": "Google Chrome", 
                    "firefox": "Firefox",
                    "edge": "Microsoft Edge",
                    "finder": "Finder",
                    "terminal": "Terminal",
                    "vscode": "Visual Studio Code",
                    "code": "Visual Studio Code"
                }
                
                # Extract app name from command
                if "'" in action or '"' in action:
                    # Handle quoted app names like "open -a 'Visual Studio Code'"
                    import re
                    quoted_match = re.search(r"open -a ['\"]([^'\"]+)['\"]", action)
                    if quoted_match:
                        app_name = quoted_match.group(1)
                    else:
                        app_name = app_map.get(app, app.capitalize())
                else:
                    app_name = app_map.get(app, app.capitalize())
                
                try:
                    subprocess.run(["open", "-a", app_name], check=True)
                    return {
                        "success": True,
                        "result": f"Opened {app_name}",
                        "agent_used": "gui"
                    }
                except subprocess.CalledProcessError as e:
                    return {
                        "success": False,
                        "result": f"Failed to open {app_name}: {str(e)}",
                        "agent_used": "gui"
                    }
        
        # Handle button clicking
        if "click" in low:
            # Extract button name from action
            btn_name = None
            for prefix in ("click button ", "click the ", "click on ", "click "):
                if prefix in low:
                    rest = low.split(prefix, 1)[-1].strip()
                    btn_name = rest.split()[0] if rest else None
                    break
            
            if btn_name:
                success = click_button(btn_name)
                return {
                    "success": success,
                    "result": f"Clicked button '{btn_name}'" if success else f"Button '{btn_name}' not found",
                    "agent_used": "gui"
                }
        
        # Handle generic actions - try to execute as shell command for GUI operations
        try:
            import subprocess
            result = subprocess.run(action, shell=True, capture_output=True, text=True, timeout=30)
            return {
                "success": result.returncode == 0,
                "result": result.stdout.strip() or result.stderr.strip() or "Command executed",
                "agent_used": "gui"
            }
        except Exception as e:
            return {
                "success": False,
                "result": f"GUI action failed: {str(e)[:200]}",
                "agent_used": "gui"
            }
            
    except Exception as e:
        logger.exception("GUI step execution failed")
        return {
            "success": False,
            "result": f"GUI execution error: {str(e)[:300]}",
            "agent_used": "gui"
        }
