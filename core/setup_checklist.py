"""
GEDOS setup checklist utilities.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Optional

from core.config import get_gedos_md_path, has_telegram_token, load_config, read_env_file
from core.memory import get_engine
from tools.ax_tree import get_ax_tree


@dataclass(frozen=True, slots=True)
class ChecklistItem:
    """One setup checklist result row."""

    label: str
    passed: bool
    fix: Optional[str] = None
    countable: bool = True


def _check_python() -> ChecklistItem:
    ok = sys.version_info >= (3, 12)
    version = ".".join(str(part) for part in sys.version_info[:3])
    if ok:
        return ChecklistItem(label=f"Python {version}", passed=True)
    return ChecklistItem(
        label=f"Python {version} (requires 3.12+)",
        passed=False,
        fix="Install Python 3.12+: brew install python@3.12",
    )


def _check_gedos_installed() -> ChecklistItem:
    entrypoint = Path(__file__).resolve().parent.parent / "gedos.py"
    if entrypoint.exists():
        return ChecklistItem(label="Gedos installed", passed=True)
    return ChecklistItem(label="Gedos installed", passed=False, fix="Install Gedos in this repository first.")


def _check_database() -> ChecklistItem:
    try:
        engine = get_engine()
        db_path = Path(engine.url.database or "")
        readable = db_path.exists() and os.access(db_path, os.R_OK)
        if readable:
            return ChecklistItem(label="gedos.db initialized", passed=True)
        return ChecklistItem(
            label="gedos.db initialized",
            passed=False,
            fix=f"Run Gedos once to initialize DB at {db_path}",
        )
    except Exception as exc:
        return ChecklistItem(label="gedos.db initialized", passed=False, fix=f"DB check failed: {exc}")


def _ollama_model_name() -> Optional[str]:
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) <= 1:
        return None
    first = lines[1].split()
    return first[0] if first else None


def _check_ollama() -> ChecklistItem:
    try:
        health = subprocess.run(
            ["curl", "-s", "http://localhost:11434"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        reachable = health.returncode == 0 and bool((health.stdout or "").strip())
    except Exception:
        reachable = False
    if not reachable:
        return ChecklistItem(
            label="Ollama reachable at localhost:11434",
            passed=False,
            fix="Start Ollama: ollama serve",
        )
    model = _ollama_model_name()
    if not model:
        return ChecklistItem(
            label="Ollama running (no model pulled)",
            passed=False,
            fix="Pull a model: ollama pull llama3.2",
        )
    return ChecklistItem(label=f"Ollama running ({model})", passed=True)


def _check_ffmpeg() -> ChecklistItem:
    if shutil.which("ffmpeg"):
        return ChecklistItem(label="ffmpeg available", passed=True)
    return ChecklistItem(
        label="ffmpeg not found — voice output disabled",
        passed=False,
        fix="brew install ffmpeg",
    )


def _check_accessibility() -> ChecklistItem:
    tree = get_ax_tree(max_buttons=1, max_text_fields=1, use_cache=False)
    if tree.get("error"):
        return ChecklistItem(
            label="Accessibility permissions not granted",
            passed=False,
            fix="System Settings -> Privacy -> Accessibility -> Terminal",
        )
    return ChecklistItem(label="Accessibility permissions granted", passed=True)


def _check_telegram() -> ChecklistItem:
    if has_telegram_token():
        return ChecklistItem(label="Telegram configured (Pilot Mode active)", passed=True)
    return ChecklistItem(
        label="TELEGRAM_BOT_TOKEN not set",
        passed=False,
        fix="Add TELEGRAM_BOT_TOKEN to ~/.gedos/.env",
    )


def _check_gedos_md() -> ChecklistItem:
    path = get_gedos_md_path()
    if path.exists():
        return ChecklistItem(label=f"GEDOS.md found at {path}", passed=True)
    return ChecklistItem(label=f"GEDOS.md not found at {path}", passed=False, fix="Run onboarding to create GEDOS.md")


def _check_github_token() -> ChecklistItem:
    env_vars = read_env_file()
    token = os.getenv("GITHUB_TOKEN") or env_vars.get("GITHUB_TOKEN", "")
    if token.strip():
        return ChecklistItem(label="GITHUB_TOKEN configured (Self-healing CI enabled)", passed=True, countable=False)
    return ChecklistItem(
        label="GITHUB_TOKEN not set — Self-healing CI disabled",
        passed=False,
        fix="Add GITHUB_TOKEN to ~/.gedos/.env",
        countable=False,
    )


def _check_cloud_api_keys() -> ChecklistItem:
    env_vars = read_env_file()
    anthropic = (os.getenv("ANTHROPIC_API_KEY") or env_vars.get("ANTHROPIC_API_KEY", "")).strip()
    openai = (os.getenv("OPENAI_API_KEY") or env_vars.get("OPENAI_API_KEY", "")).strip()
    if anthropic or openai:
        return ChecklistItem(label="Cloud LLM API key configured", passed=True, countable=False)
    return ChecklistItem(
        label="ANTHROPIC_API_KEY / OPENAI_API_KEY not set (optional)",
        passed=False,
        fix="Add ANTHROPIC_API_KEY or OPENAI_API_KEY to ~/.gedos/.env",
        countable=False,
    )


def collect_setup_checklist() -> list[ChecklistItem]:
    """Return all checklist rows in display order."""
    # Touch config once so invalid config surfaces during checklist.
    load_config()
    return [
        _check_python(),
        _check_gedos_installed(),
        _check_database(),
        _check_ollama(),
        _check_ffmpeg(),
        _check_accessibility(),
        _check_telegram(),
        _check_gedos_md(),
        _check_github_token(),
        _check_cloud_api_keys(),
    ]


def format_setup_checklist() -> str:
    """Render checklist output in a Telegram/CLI-friendly text block."""
    items = collect_setup_checklist()
    lines = ["🔍 Gedos Setup Checklist", "━━━━━━━━━━━━━━━━━━━━━━━━"]
    passed_count = 0
    total_count = 0
    for item in items:
        icon = "✅" if item.passed else "⚠️ "
        lines.append(f"{icon} {item.label}")
        if not item.passed and item.fix:
            lines.append(f"    Fix: {item.fix}")
        if item.countable:
            total_count += 1
            if item.passed:
                passed_count += 1
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"{passed_count}/{total_count} checks passing")
    return "\n".join(lines)
