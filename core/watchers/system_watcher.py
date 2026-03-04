"""
GEDOS system watcher — monitors system health and emits proactive notifications.
"""

from __future__ import annotations

from datetime import datetime, UTC
import logging
import threading
from typing import Optional

import psutil

from core.proactive_engine import known_user_ids, notify

logger = logging.getLogger(__name__)
SYSTEM_WATCHER_INTERVAL_SECONDS = 60
_HIGH_CPU_STREAK: dict[int, int] = {}


def _pick_user_id() -> Optional[str]:
    users = known_user_ids()
    return users[0] if users else None


def _top_cpu_process() -> tuple[Optional[psutil.Process], float]:
    best_proc: Optional[psutil.Process] = None
    best_cpu = 0.0
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "create_time", "status"]):
        try:
            cpu = float(proc.info.get("cpu_percent") or 0.0)
            if cpu > best_cpu:
                best_cpu = cpu
                best_proc = proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return best_proc, best_cpu


def _maybe_notify_system_health() -> None:
    user_id = _pick_user_id()
    if not user_id:
        return

    memory = psutil.virtual_memory()
    if memory.percent >= 90:
        notify(user_id, f"⚠️ Memory at {int(memory.percent)}%. Want me to find what's using it?", "system", "high")

    disk = psutil.disk_usage("/")
    if disk.percent >= 90:
        notify(user_id, f"⚠️ Disk at {int(disk.percent)}%. Want me to find what's taking space?", "system", "high")

    proc, cpu = _top_cpu_process()
    if proc is not None:
        if cpu >= 90:
            _HIGH_CPU_STREAK[proc.pid] = _HIGH_CPU_STREAK.get(proc.pid, 0) + 1
        else:
            _HIGH_CPU_STREAK.pop(proc.pid, None)
        if _HIGH_CPU_STREAK.get(proc.pid, 0) >= 5:
            name = proc.info.get("name") or f"PID {proc.pid}"
            notify(user_id, f"⚠️ {name} is using {int(cpu)}% CPU. Want me to restart it?", "system", "high")

        try:
            runtime_seconds = max(0, int(datetime.now(UTC).timestamp() - float(proc.info.get("create_time") or 0.0)))
            quiet = cpu < 1.0
            if runtime_seconds >= 1800 and quiet:
                minutes = runtime_seconds // 60
                name = proc.info.get("name") or f"PID {proc.pid}"
                notify(user_id, f"⚠️ {name} has been running for {minutes} minutes. Still needed?", "system", "medium")
        except (psutil.NoSuchProcess, psutil.AccessDenied, OverflowError, ValueError):
            pass


def run_system_watcher(stop_event: Optional[threading.Event] = None) -> None:
    """Run the system watcher loop in the current thread."""
    stopper = stop_event or threading.Event()
    try:
        psutil.cpu_percent(interval=None)
    except Exception:
        pass
    while not stopper.wait(SYSTEM_WATCHER_INTERVAL_SECONDS):
        try:
            _maybe_notify_system_health()
        except Exception:
            logger.exception("System watcher failed")
