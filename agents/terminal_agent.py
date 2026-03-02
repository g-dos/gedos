"""
GEDOS Terminal Agent — executes shell commands, git, python, npm, CLI tools.
Captures stdout/stderr and returns structured result.
"""

import logging
import shlex
import subprocess
from dataclasses import dataclass
from typing import Optional

from core.config import get_agent_config
from core.retry import retry_with_backoff

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30


@dataclass
class TerminalResult:
    """Result of a terminal command execution."""
    success: bool
    stdout: str
    stderr: str
    return_code: int
    command: str


def _exec_command(
    command: str,
    cwd: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
) -> TerminalResult:
    """Single-attempt command execution via shlex."""
    parts = shlex.split(command)
    if not parts:
        return TerminalResult(success=False, stdout="", stderr="Empty command.", return_code=-1, command=command)
    try:
        proc = subprocess.run(
            parts, cwd=cwd, capture_output=True, text=True,
            timeout=timeout_seconds or DEFAULT_TIMEOUT,
        )
        logger.info("Command %s -> code %s", command[:80], proc.returncode)
        return TerminalResult(
            success=proc.returncode == 0,
            stdout=proc.stdout or "", stderr=proc.stderr or "",
            return_code=proc.returncode, command=command,
        )
    except subprocess.TimeoutExpired:
        t = timeout_seconds or DEFAULT_TIMEOUT
        logger.warning("Command timed out after %ss: %s", t, command[:80])
        return TerminalResult(success=False, stdout="", stderr=f"Command timed out ({t}s).", return_code=-1, command=command)
    except FileNotFoundError:
        logger.warning("Command not found: %s", command[:80])
        return TerminalResult(success=False, stdout="", stderr=f"Command not found: {shlex.split(command)[0]}", return_code=127, command=command)
    except Exception as e:
        logger.exception("Command failed: %s", command[:80])
        return TerminalResult(success=False, stdout="", stderr=f"Command execution error: {e}", return_code=-1, command=command)


def run_command(
    command: str,
    cwd: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
    max_retries: Optional[int] = None,
) -> TerminalResult:
    """
    Execute a shell command safely with optional retry.
    Only retries on transient failures (timeout, execution error).
    Command-not-found and empty commands are not retried.
    """
    cfg = get_agent_config("terminal")
    t = timeout_seconds or cfg.get("timeout", DEFAULT_TIMEOUT)
    retries = max_retries if max_retries is not None else cfg.get("max_retries", 1)

    result = _exec_command(command, cwd=cwd, timeout_seconds=t)
    if result.success or retries <= 1 or result.return_code == 127:
        return result

    if "timed out" in result.stderr.lower() or "execution error" in result.stderr.lower():
        for attempt in range(2, retries + 1):
            logger.warning("Retrying command (attempt %d/%d): %s", attempt, retries, command[:80])
            result = _exec_command(command, cwd=cwd, timeout_seconds=t)
            if result.success:
                return result
    return result


def _exec_shell(
    command: str,
    cwd: Optional[str] = None,
    timeout_seconds: int = DEFAULT_TIMEOUT,
) -> TerminalResult:
    """Single-attempt shell execution."""
    try:
        proc = subprocess.run(
            command, shell=True, cwd=cwd, capture_output=True, text=True,
            timeout=timeout_seconds,
        )
        return TerminalResult(
            success=proc.returncode == 0,
            stdout=proc.stdout or "", stderr=proc.stderr or "",
            return_code=proc.returncode, command=command,
        )
    except subprocess.TimeoutExpired:
        return TerminalResult(success=False, stdout="", stderr=f"Command timed out ({timeout_seconds}s).", return_code=-1, command=command)
    except Exception as e:
        return TerminalResult(success=False, stdout="", stderr=f"Command execution error: {e}", return_code=-1, command=command)


def run_shell(
    command: str,
    cwd: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
    max_retries: Optional[int] = None,
) -> TerminalResult:
    """
    Execute command via system shell with optional retry.
    Prefer run_command for single commands when possible.
    """
    cfg = get_agent_config("terminal")
    t = timeout_seconds or cfg.get("timeout", DEFAULT_TIMEOUT)
    retries = max_retries if max_retries is not None else cfg.get("max_retries", 1)

    result = _exec_shell(command, cwd=cwd, timeout_seconds=t)
    if result.success or retries <= 1:
        return result

    if "timed out" in result.stderr.lower() or "execution error" in result.stderr.lower():
        for attempt in range(2, retries + 1):
            logger.warning("Retrying shell (attempt %d/%d): %s", attempt, retries, command[:80])
            result = _exec_shell(command, cwd=cwd, timeout_seconds=t)
            if result.success:
                return result
    return result


def _correct_command_with_llm(failed_command: str, error_output: str) -> str:
    """
    Use LLM to suggest a corrected command based on the error.
    
    Args:
        failed_command: The command that failed
        error_output: The error message from the failed command
        
    Returns:
        Suggested corrected command
    """
    try:
        from core.config import get_llm_client
        
        prompt = f"""The following terminal command failed:
Command: {failed_command}
Error: {error_output}

Provide ONLY a corrected command that would fix this error. Return just the command, no explanation or formatting."""

        llm = get_llm_client()
        if hasattr(llm, 'invoke'):
            response = llm.invoke(prompt)
        else:
            response = llm(prompt)
            
        corrected = str(response).strip()
        # Clean up common LLM response formatting
        if corrected.startswith('```'):
            lines = corrected.split('\n')
            corrected = '\n'.join(line for line in lines if not line.startswith('```'))
        
        return corrected.strip() or failed_command
        
    except Exception as e:
        logger.warning(f"LLM correction failed: {e}")
        return failed_command


def execute_step(step) -> dict[str, str]:
    """
    Execute a structured task step using the terminal agent with self-correction.
    
    Args:
        step: TaskStep object with agent, action, expected_result fields
        
    Returns:
        Dict with success, result, agent_used fields
    """
    try:
        from typing import Any
        
        # First attempt
        result = run_shell(step.action)
        
        # If successful, return immediately
        if result.success:
            out = (result.stdout or "").strip() or "(no output)"
            if len(out) > 1000:
                out = out[:1000] + "\n... (truncated)"
            return {
                "success": True,
                "result": out,
                "agent_used": "terminal",
                "command": step.action
            }
        
        # Command failed, try self-correction
        error_output = result.stderr or result.stdout or "Unknown error"
        logger.info(f"Command failed, attempting self-correction: {step.action}")
        
        corrected_command = _correct_command_with_llm(step.action, error_output)
        
        # Only retry if LLM suggested a different command
        if corrected_command != step.action:
            logger.info(f"Retrying with corrected command: {corrected_command}")
            corrected_result = run_shell(corrected_command)
            
            if corrected_result.success:
                out = (corrected_result.stdout or "").strip() or "(no output)"
                if len(out) > 1000:
                    out = out[:1000] + "\n... (truncated)"
                return {
                    "success": True,
                    "result": f"Self-corrected: {out}",
                    "agent_used": "terminal",
                    "command": corrected_command,
                    "original_command": step.action
                }
        
        # Format original error for user
        out = (result.stdout or "").strip() or "(no output)"
        err = (result.stderr or "").strip()
        if len(out) > 1000:
            out = out[:1000] + "\n... (truncated)"
        
        msg = out
        if err:
            msg += f"\nstderr: {err[:200]}"
            
        return {
            "success": False,
            "result": msg,
            "agent_used": "terminal",
            "command": step.action
        }
        
    except Exception as e:
        logger.exception("Terminal step execution failed")
        return {
            "success": False,
            "result": f"Terminal execution error: {str(e)[:300]}",
            "agent_used": "terminal",
            "command": getattr(step, 'action', 'unknown')
        }
