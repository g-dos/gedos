"""
GEDOS Terminal Agent — executes shell commands, git, python, npm, CLI tools.
Captures stdout/stderr and returns structured result.
"""

import logging
import shlex
import subprocess
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TerminalResult:
    """Result of a terminal command execution."""
    success: bool
    stdout: str
    stderr: str
    return_code: int
    command: str


def run_command(
    command: str,
    cwd: Optional[str] = None,
    timeout_seconds: Optional[int] = 60,
) -> TerminalResult:
    """
    Execute a shell command safely. Uses shlex to split the command string.
    Returns stdout, stderr, and return code.
    """
    try:
        parts = shlex.split(command)
        if not parts:
            return TerminalResult(
                success=False,
                stdout="",
                stderr="Empty command.",
                return_code=-1,
                command=command,
            )
        proc = subprocess.run(
            parts,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        out = proc.stdout or ""
        err = proc.stderr or ""
        success = proc.returncode == 0
        logger.info("Command %s -> code %s", command[:80], proc.returncode)
        return TerminalResult(
            success=success,
            stdout=out,
            stderr=err,
            return_code=proc.returncode,
            command=command,
        )
    except subprocess.TimeoutExpired:
        logger.warning("Command timed out: %s", command[:80])
        return TerminalResult(
            success=False,
            stdout="",
            stderr="Command timed out.",
            return_code=-1,
            command=command,
        )
    except Exception as e:
        logger.exception("Command failed: %s", command[:80])
        return TerminalResult(
            success=False,
            stdout="",
            stderr=str(e),
            return_code=-1,
            command=command,
        )


def run_shell(command: str, cwd: Optional[str] = None) -> TerminalResult:
    """
    Execute command via system shell (e.g. for pipelines and redirections).
    Prefer run_command for single commands when possible.
    """
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return TerminalResult(
            success=proc.returncode == 0,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            return_code=proc.returncode,
            command=command,
        )
    except subprocess.TimeoutExpired:
        return TerminalResult(
            success=False,
            stdout="",
            stderr="Command timed out.",
            return_code=-1,
            command=command,
        )
    except Exception as e:
        return TerminalResult(
            success=False,
            stdout="",
            stderr=str(e),
            return_code=-1,
            command=command,
        )
