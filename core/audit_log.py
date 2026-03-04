"""
GEDOS audit logging (JSONL).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from threading import Lock
from typing import Any

_LOCK = Lock()
_MAX_BYTES = 10 * 1024 * 1024
_RETENTION_DAYS = 30


def _audit_dir() -> Path:
    path = Path.home() / ".gedos"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _current_log_path() -> Path:
    return _audit_dir() / "audit.log"


def _all_log_paths() -> list[Path]:
    directory = _audit_dir()
    files = list(directory.glob("audit*.log"))
    if _current_log_path() not in files:
        files.append(_current_log_path())
    return sorted(files, key=lambda item: item.stat().st_mtime if item.exists() else 0.0, reverse=True)


def _rotate_if_needed(path: Path) -> None:
    if not path.exists():
        return
    if path.stat().st_size <= _MAX_BYTES:
        return
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    rotated = path.with_name(f"audit-{stamp}.log")
    path.rename(rotated)


def _prune_old_logs() -> None:
    cutoff = datetime.now(UTC) - timedelta(days=_RETENTION_DAYS)
    for log_path in _all_log_paths():
        if log_path == _current_log_path():
            continue
        try:
            modified = datetime.fromtimestamp(log_path.stat().st_mtime, UTC)
        except OSError:
            continue
        if modified < cutoff:
            try:
                log_path.unlink(missing_ok=True)
            except OSError:
                continue


def log_action(action: str, details: dict[str, Any], user_id: str, result: str) -> None:
    """Append one JSONL audit row, rotating and pruning logs when needed."""
    payload = {
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "action": str(action or "").strip(),
        "user_id": str(user_id or "unknown").strip() or "unknown",
        "details": details or {},
        "result": str(result or "").strip() or "unknown",
    }
    with _LOCK:
        path = _current_log_path()
        _rotate_if_needed(path)
        _prune_old_logs()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


def read_recent_actions(limit: int = 20) -> list[dict[str, Any]]:
    """Read the latest N JSONL entries across current and rotated files."""
    entries: list[dict[str, Any]] = []
    with _LOCK:
        for path in _all_log_paths():
            if not path.exists():
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in reversed(lines):
                text = line.strip()
                if not text:
                    continue
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    entries.append(parsed)
                if len(entries) >= max(1, int(limit)):
                    return entries[: max(1, int(limit))]
    return entries[: max(1, int(limit))]
