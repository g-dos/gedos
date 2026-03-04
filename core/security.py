"""
GEDOS security utilities — input sanitization and validation.
"""

import os
import logging
import re
import shlex
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_EXECUTABLES = {
    "git", "python", "python3", "pytest", "pip", "ls", "cat", "echo", "mkdir",
    "touch", "cp", "mv", "cd", "pwd", "find", "grep", "curl", "brew", "npm", "node",
    "open", "which", "env", "export", "source", "playwright", "ollama",
}
BLOCKED_SUBSTRINGS = {";", "&&", "||", "|", ">>", "`", "$", "(", ")", "{", "}", "\n", "#"}
BLOCKED_TOKEN_OPERATORS = {">", ">>", "<"}
BLOCKED_TERMS = {
    "rm", "sudo", "su", "chmod", "chown", "eval", "exec", "dd", "mkfs",
    "kill", "killall", "shutdown", "reboot",
}
BLOCKED_COMPOUND_PATTERNS = (
    "curl|sh",
    "wget|sh",
)
DESTRUCTIVE_PATTERNS = [
    r"\brm\b",
    r"\bmv\b",
    r"\bpip install\b",
    r"\bgit push\b",
    r"\bgit commit\b",
    r"\bdeploy\b",
    r"\bsudo\b",
    r"\bchmod\b",
    r"\bchown\b",
]
_SAFE_PIP_SPEC_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-\[\]=<>]*$")
_DANGEROUS_GIT_FLAGS = {
    "--exec-path",
    "--upload-pack",
    "--receive-pack",
    "--no-replace-objects",
    "--super-prefix",
    "--bare",
}


class SecurityError(RuntimeError):
    """Raised when a command is blocked by a security policy."""
    pass


def get_allowed_executables(config: Optional[dict] = None) -> set[str]:
    """Return the configured allowlist for shell execution."""
    if config is None:
        try:
            from core.config import load_config
            config = load_config()
        except Exception:
            config = {}
    configured = ((config.get("security") or {}).get("allowed_executables") or [])
    if configured:
        return {str(item).strip() for item in configured if str(item).strip()}
    return set(DEFAULT_ALLOWED_EXECUTABLES)


def sanitize_command(command: str) -> tuple[bool, str]:
    """
    Validate a command against a strict allowlist and blocked token set.
    Returns (is_safe, reason).
    """
    if not command or not command.strip():
        return False, "Empty command."

    if "\x00" in command:
        return False, "null byte detected"
    if any(ord(char) < 32 and char not in ("\t",) for char in command):
        return False, "non-printable characters detected"

    cmd = command.strip()

    low = cmd.lower()
    for pattern in BLOCKED_COMPOUND_PATTERNS:
        if pattern in low.replace(" ", ""):
            reason = f"Blocked dangerous pattern: {pattern}"
            logger.warning("%s in command: %s", reason, cmd[:80])
            return False, reason

    for operator in BLOCKED_SUBSTRINGS:
        if operator in cmd:
            reason = f"Blocked dangerous token: {operator}"
            logger.warning("%s in command: %s", reason, cmd[:80])
            return False, reason

    try:
        parts = shlex.split(cmd)
    except ValueError as exc:
        reason = f"Command parsing failed: {exc}"
        logger.warning("%s", reason)
        return False, reason

    if not parts:
        return False, "Empty command."

    executable = parts[0]
    if executable not in get_allowed_executables():
        reason = f"Executable not allowed: {executable}"
        logger.warning("%s", reason)
        return False, reason

    for token in parts:
        if token in BLOCKED_TOKEN_OPERATORS:
            reason = f"Blocked dangerous token: {token}"
            logger.warning("%s in command: %s", reason, cmd[:80])
            return False, reason
        if token.lower() in BLOCKED_TERMS:
            reason = f"Blocked dangerous token: {token}"
            logger.warning("%s in command: %s", reason, cmd[:80])
            return False, reason

    if executable == "pip":
        return _validate_pip_command(parts, cmd)
    if executable == "git":
        return _validate_git_command(parts, cmd)

    return True, "ok"


def _validate_pip_command(parts: list[str], cmd: str) -> tuple[bool, str]:
    """Allow only `pip install <safe package spec>` with no local paths."""
    if len(parts) != 3 or parts[1] != "install":
        reason = "Only `pip install <package>` is allowed"
        logger.warning("%s: %s", reason, cmd[:80])
        return False, reason

    package_spec = parts[2]
    blocked_prefixes = ("../", "./", "/", "~", "file:")
    if package_spec.startswith(blocked_prefixes):
        reason = f"Blocked local pip path: {package_spec}"
        logger.warning("%s", reason)
        return False, reason
    if not _SAFE_PIP_SPEC_RE.fullmatch(package_spec):
        reason = f"Blocked pip package spec: {package_spec}"
        logger.warning("%s", reason)
        return False, reason
    return True, "ok"


def _validate_git_command(parts: list[str], cmd: str) -> tuple[bool, str]:
    """Block dangerous git flags and path-valued long options."""
    for token in parts[1:]:
        for flag in _DANGEROUS_GIT_FLAGS:
            if token == flag or token.startswith(flag + "="):
                reason = f"Blocked dangerous git flag: {flag}"
                logger.warning("%s in command: %s", reason, cmd[:80])
                return False, reason
        if token.startswith("--") and "=" in token:
            _, value = token.split("=", 1)
            if value.startswith(("/", "~", ".", "../")):
                reason = f"Blocked git path-valued option: {token}"
                logger.warning("%s", reason)
                return False, reason
    return True, "ok"


def is_destructive_command(command: str) -> bool:
    """Return whether a command matches a destructive pattern."""
    low = (command or "").strip().lower()
    return any(re.search(pattern, low) for pattern in DESTRUCTIVE_PATTERNS)


def get_allowed_chat_ids() -> set[str]:
    """Parse ALLOWED_CHAT_IDS from environment."""
    raw = os.getenv("ALLOWED_CHAT_IDS", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def get_pairing_code() -> Optional[str]:
    """Return the optional Telegram pairing code."""
    code = os.getenv("PAIRING_CODE", "").strip()
    return code or None


def sanitize_url(url: str) -> Optional[str]:
    """
    Sanitize URL for web navigation.
    Returns None if URL is dangerous, otherwise returns sanitized URL.
    """
    if not url or not url.strip():
        return None
    
    url_clean = url.strip()
    
    # Block local/internal URLs
    if any(x in url_clean.lower() for x in ("localhost", "127.0.0.1", "0.0.0.0", "file://")):
        logger.warning("Blocked internal URL: %s", url_clean[:50])
        return None
    
    # Validate http(s) protocol
    if not url_clean.startswith(("http://", "https://")):
        url_clean = "https://" + url_clean
    
    return url_clean


def validate_telegram_input(text: str, max_length: int = 4000) -> Optional[str]:
    """
    Validate general Telegram input.
    Returns None if input is invalid, otherwise returns validated text.
    """
    if not text or not text.strip():
        return None
    
    text = text.strip()
    
    if len(text) > max_length:
        logger.warning("Input too long: %d chars", len(text))
        return None
    
    return text


def validate_api_keys(config: dict) -> bool:
    """
    Validate that required API keys exist on startup.
    Returns True if all required keys are present, False otherwise.
    """
    telegram_token = config.get("telegram", {}).get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        logger.error("Missing TELEGRAM_BOT_TOKEN in config.yaml or .env")
        return False
    
    llm_provider = config.get("llm", {}).get("provider", "ollama")
    
    if llm_provider == "claude":
        claude_key = os.getenv("ANTHROPIC_API_KEY")
        if not claude_key:
            logger.error("LLM_PROVIDER=claude but ANTHROPIC_API_KEY not found in .env")
            return False
    elif llm_provider == "openai":
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            logger.error("LLM_PROVIDER=openai but OPENAI_API_KEY not found in .env")
            return False
    
    logger.info("API keys validated successfully")
    return True
