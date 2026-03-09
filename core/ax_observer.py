"""
Event-driven macOS Accessibility observer for Gedos.

This module replaces frequent AX polling with native AXObserver
subscriptions to accessibility notifications for the frontmost app.

Requirements:
    pip install pyobjc-framework-ApplicationServices pyobjc-framework-Cocoa

Notes:
    - macOS only.
    - On unsupported platforms or missing dependencies, this module
      degrades gracefully and public APIs become safe no-ops/fallbacks.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

try:
    import ApplicationServices as AS
    from AppKit import NSWorkspace

    AX_OBSERVER_AVAILABLE = True
except Exception:
    AS = None  # type: ignore[assignment]
    NSWorkspace = None  # type: ignore[assignment]
    AX_OBSERVER_AVAILABLE = False

logger = logging.getLogger(__name__)

AX_NOTIFICATIONS = [
    "AXFocusedWindowChanged",
    "AXFocusedUIElementChanged",
    "AXValueChanged",
    "AXTitleChanged",
    "AXSelectedTextChanged",
    "AXUIElementDestroyed",
]


class AXObserver:
    """Observe frontmost app AX notifications and emit change callbacks."""

    def __init__(self, on_change: Callable[[str, Optional[int]], None]) -> None:
        self.on_change = on_change
        self._observer = None
        self._current_pid: Optional[int] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._run_loop = None
        self._run_loop_source = None
        self._app_element = None

    def start(self) -> None:
        """Start observer watch loop in a daemon background thread."""
        if self._running:
            return
        self._running = True
        if not AX_OBSERVER_AVAILABLE:
            return
        self._thread = threading.Thread(target=self._watch_loop, name="gedos-ax-observer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop observer and clean any active run-loop source."""
        self._running = False
        self._teardown_observer()

    def _watch_loop(self) -> None:
        """Track frontmost pid and register AX notifications when it changes."""
        if not AX_OBSERVER_AVAILABLE:
            return

        while self._running:
            try:
                pid = self._frontmost_pid()
                if pid is not None and pid != self._current_pid:
                    self._switch_to_pid(pid)
                if self._run_loop and hasattr(AS, "CFRunLoopRunInMode"):
                    mode = getattr(AS, "kCFRunLoopDefaultMode", None)
                    if mode is not None:
                        AS.CFRunLoopRunInMode(mode, 0.05, False)
            except Exception:
                logger.exception("AX observer watch loop error")
            time.sleep(0.5)

    def _frontmost_pid(self) -> Optional[int]:
        if not AX_OBSERVER_AVAILABLE:
            return None
        try:
            app = NSWorkspace.sharedWorkspace().frontmostApplication()
            if app is None:
                return None
            pid = app.processIdentifier()
            return int(pid)
        except Exception:
            logger.exception("Failed to resolve frontmost pid")
            return None

    def _switch_to_pid(self, pid: int) -> None:
        self._teardown_observer()
        if not AX_OBSERVER_AVAILABLE:
            return
        try:
            create_result = AS.AXObserverCreate(pid, self._ax_callback)
            observer = self._extract_created_observer(create_result)
            if observer is None:
                logger.debug("AXObserverCreate returned no observer for pid=%s", pid)
                return
            app_element = AS.AXUIElementCreateApplication(pid)
            for notification in AX_NOTIFICATIONS:
                try:
                    AS.AXObserverAddNotification(observer, app_element, notification, None)
                except Exception:
                    logger.debug("Failed to subscribe notification=%s pid=%s", notification, pid)

            run_loop = AS.CFRunLoopGetCurrent() if hasattr(AS, "CFRunLoopGetCurrent") else None
            run_loop_source = AS.AXObserverGetRunLoopSource(observer)
            mode = getattr(AS, "kCFRunLoopDefaultMode", None)
            if run_loop is not None and run_loop_source is not None and mode is not None:
                AS.CFRunLoopAddSource(run_loop, run_loop_source, mode)

            self._observer = observer
            self._app_element = app_element
            self._run_loop = run_loop
            self._run_loop_source = run_loop_source
            self._current_pid = pid
        except Exception:
            logger.exception("Failed to switch AX observer to pid=%s", pid)
            self._teardown_observer()

    @staticmethod
    def _extract_created_observer(create_result):
        """
        Normalize AXObserverCreate return shape across pyobjc variants.

        Known patterns:
            - observer
            - (error_code, observer)
        """
        if isinstance(create_result, tuple):
            if len(create_result) >= 2:
                err, observer = create_result[0], create_result[1]
                if err == 0 and observer is not None:
                    return observer
                return None
            if create_result:
                return create_result[0]
            return None
        return create_result

    def _teardown_observer(self) -> None:
        if not AX_OBSERVER_AVAILABLE:
            self._observer = None
            self._app_element = None
            self._run_loop = None
            self._run_loop_source = None
            self._current_pid = None
            return
        try:
            if self._observer is not None and self._app_element is not None:
                for notification in AX_NOTIFICATIONS:
                    try:
                        AS.AXObserverRemoveNotification(self._observer, self._app_element, notification)
                    except Exception:
                        pass
            if self._run_loop is not None and self._run_loop_source is not None:
                mode = getattr(AS, "kCFRunLoopDefaultMode", None)
                if mode is not None and hasattr(AS, "CFRunLoopRemoveSource"):
                    AS.CFRunLoopRemoveSource(self._run_loop, self._run_loop_source, mode)
        except Exception:
            logger.exception("Failed to teardown AX observer")
        finally:
            self._observer = None
            self._app_element = None
            self._run_loop = None
            self._run_loop_source = None
            self._current_pid = None

    def _ax_callback(self, observer, element, notification, user_info) -> None:
        """Forward AX notification events to the on_change callback."""
        del observer, element, user_info
        try:
            self.on_change(str(notification), self._current_pid)
        except Exception:
            logger.exception("AX callback handler failed")


def get_frontmost_app_name() -> str:
    """Return frontmost app name or empty string when unavailable."""
    if not AX_OBSERVER_AVAILABLE:
        return ""
    try:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return ""
        name = app.localizedName()
        return str(name or "")
    except Exception:
        logger.exception("Failed to resolve frontmost app name")
        return ""

