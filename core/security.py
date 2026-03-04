"""
GEDOS security utilities — input sanitization and validation.
"""

import os
import logging
import re
import shlex
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_EXECUTABLES = {
    "git", "python", "python3", "pytest", "pip", "ls", "cat", "echo", "mkdir",
    "touch", "cp", "mv", "cd", "pwd", "find", "grep", "curl", "brew", "npm", "node",
    "open", "which", "export", "source", "playwright", "ollama",
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
_BLOCKED_GIT_SINGLE_TOKENS = {
    "-c",
    "--config",
    "clone",
    "submodule",
    "archive",
    "bundle",
    "daemon",
    "instaweb",
    "p4",
    "svn",
}
_BLOCKED_GIT_TOKEN_SEQUENCES = (
    ("config", "--global"),
    ("config", "--system"),
    ("remote", "add"),
    ("bisect", "run"),
)
_BLOCKED_PYTHON_MODULES = {
    "http.server",
    "http",
    "smtpd",
    "smtp",
    "ftplib",
    "ftp",
    "socketserver",
    "xmlrpc",
    "pdb",
    "code",
    "cgi",
    "cgitb",
}
_SENSITIVE_SUFFIXES = (".env", ".pem", ".key", ".cert", ".p12", ".pfx", ".db", ".sqlite", ".sqlite3")
_SENSITIVE_SEARCH_PATTERNS = {"*.env", "*.key"}
_PROJECTS_ROOT = os.path.realpath(os.path.expanduser("~/projects"))
MAX_COMMAND_LENGTH = 1000


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


def sanitize_command(command: str, cwd: Optional[str] = None) -> tuple[bool, str]:
    """
    Validate a command against a strict allowlist and blocked token set.
    Returns (is_safe, reason).
    """
    if not command or not command.strip():
        return False, "Empty command."

    if len(command) > MAX_COMMAND_LENGTH:
        return False, f"command too long (max {MAX_COMMAND_LENGTH} chars)"

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
    if executable in {"python", "python3"}:
        return _validate_python_command(parts, cmd)
    if executable == "cat":
        return _validate_cat_command(parts, cmd, cwd)
    if executable == "find":
        return _validate_find_command(parts, cmd, cwd)
    if executable in {"cp", "mv"}:
        return _validate_copy_move_command(parts, cmd, cwd)
    if executable == "ls":
        return _validate_ls_command(parts, cmd, cwd)

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
    lowered = [token.lower() for token in parts[1:]]
    for index, token in enumerate(parts[1:]):
        low_token = lowered[index]
        if low_token in _BLOCKED_GIT_SINGLE_TOKENS:
            reason = f"Blocked dangerous git operation: {token}"
            logger.warning("%s in command: %s", reason, cmd[:80])
            return False, reason
        for sequence in _BLOCKED_GIT_TOKEN_SEQUENCES:
            if tuple(lowered[index:index + len(sequence)]) == sequence:
                reason = f"Blocked dangerous git operation: {' '.join(sequence)}"
                logger.warning("%s in command: %s", reason, cmd[:80])
                return False, reason
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


def _validate_python_command(parts: list[str], cmd: str) -> tuple[bool, str]:
    """Block unsafe Python module execution patterns."""
    for index, token in enumerate(parts[1:], start=1):
        if token != "-m" or index + 1 >= len(parts):
            continue
        module_name = parts[index + 1].strip().lower()
        if module_name in _BLOCKED_PYTHON_MODULES:
            reason = f"blocked Python module: {module_name}"
            logger.warning("%s in command: %s", reason, cmd[:80])
            return False, reason
    return True, "ok"


def _validate_cat_command(parts: list[str], cmd: str, cwd: Optional[str]) -> tuple[bool, str]:
    """Allow cat only for relative, non-sensitive project files."""
    targets = [token for token in parts[1:] if not token.startswith("-")]
    if not targets:
        return False, "cat requires a file path"
    for target in targets:
        if target.startswith(("/", "~")) or ".." in Path(target).parts:
            reason = f"Blocked cat path: {target}"
            logger.warning("%s in command: %s", reason, cmd[:80])
            return False, reason
        if _is_sensitive_path(target, cwd):
            reason = f"Blocked sensitive file path: {target}"
            logger.warning("%s in command: %s", reason, cmd[:80])
            return False, reason
    return True, "ok"


def _validate_find_command(parts: list[str], cmd: str, cwd: Optional[str]) -> tuple[bool, str]:
    """Allow find only within relative paths and non-sensitive patterns."""
    path_tokens: list[str] = []
    for token in parts[1:]:
        if token.startswith("-"):
            break
        path_tokens.append(token)
    if not path_tokens:
        path_tokens = ["."]

    for token in path_tokens:
        if token.startswith(("/", "~")) or ".." in Path(token).parts:
            reason = f"Blocked find path: {token}"
            logger.warning("%s in command: %s", reason, cmd[:80])
            return False, reason
        if _is_sensitive_path(token, cwd):
            reason = f"Blocked sensitive find path: {token}"
            logger.warning("%s in command: %s", reason, cmd[:80])
            return False, reason

    for token in parts[1:]:
        if token in _SENSITIVE_SEARCH_PATTERNS or token.lower().endswith((".env", ".key")):
            reason = f"Blocked sensitive find pattern: {token}"
            logger.warning("%s in command: %s", reason, cmd[:80])
            return False, reason
    return True, "ok"


def _validate_copy_move_command(parts: list[str], cmd: str, cwd: Optional[str]) -> tuple[bool, str]:
    """Restrict copy/move operations away from sensitive paths and destinations."""
    operands = [token for token in parts[1:] if not token.startswith("-")]
    if len(operands) < 2:
        return False, f"{parts[0]} requires source and destination paths"

    destination = operands[-1]
    sources = operands[:-1]
    for source in sources:
        if _is_sensitive_path(source, cwd):
            reason = f"Blocked sensitive source path: {source}"
            logger.warning("%s in command: %s", reason, cmd[:80])
            return False, reason
    if _is_sensitive_path(destination, cwd):
        reason = f"Blocked sensitive destination path: {destination}"
        logger.warning("%s in command: %s", reason, cmd[:80])
        return False, reason
    if not _is_safe_destination(destination, cwd):
        reason = f"Blocked destination path: {destination}"
        logger.warning("%s in command: %s", reason, cmd[:80])
        return False, reason
    return True, "ok"


def _validate_ls_command(parts: list[str], cmd: str, cwd: Optional[str]) -> tuple[bool, str]:
    """Allow ls for relative paths and ~/projects, but block sensitive system paths."""
    targets = [token for token in parts[1:] if not token.startswith("-")]
    for target in targets:
        if _is_sensitive_path(target, cwd):
            reason = f"Blocked sensitive ls path: {target}"
            logger.warning("%s in command: %s", reason, cmd[:80])
            return False, reason
        if target.startswith("/"):
            normalized = _normalize_path(target, cwd)
            if not normalized.startswith(_PROJECTS_ROOT):
                reason = f"Blocked absolute ls path: {target}"
                logger.warning("%s in command: %s", reason, cmd[:80])
                return False, reason
        if target.startswith("~"):
            normalized = _normalize_path(target, cwd)
            if not normalized.startswith(_PROJECTS_ROOT):
                reason = f"Blocked ls path outside ~/projects: {target}"
                logger.warning("%s in command: %s", reason, cmd[:80])
                return False, reason
    return True, "ok"


def _normalize_path(token: str, cwd: Optional[str]) -> str:
    """Normalize a token into an absolute real path."""
    base_dir = os.path.realpath(cwd or os.getcwd())
    expanded = os.path.expanduser(token)
    if os.path.isabs(expanded):
        return os.path.realpath(expanded)
    return os.path.realpath(os.path.join(base_dir, expanded))


def _has_sensitive_suffix(token: str) -> bool:
    """Return whether a path token targets a sensitive file type."""
    return token.lower().endswith(_SENSITIVE_SUFFIXES)


def _is_sensitive_path(token: str, cwd: Optional[str]) -> bool:
    """Detect paths that should never be accessed via terminal commands."""
    raw = token.strip()
    if not raw:
        return False
    if _has_sensitive_suffix(raw):
        return True

    parts = {part.lower() for part in Path(raw).parts}
    if parts.intersection({".ssh", ".aws", ".gnupg"}):
        return True

    if not raw.startswith(("/", "~")):
        return False

    normalized = _normalize_path(raw, cwd)
    home = os.path.expanduser("~")
    home_sensitive = (
        os.path.realpath(os.path.join(home, ".ssh")),
        os.path.realpath(os.path.join(home, ".aws")),
        os.path.realpath(os.path.join(home, ".gnupg")),
    )
    if normalized == os.path.realpath("/etc") or normalized.startswith(os.path.realpath("/etc") + os.sep):
        return True
    if normalized == os.path.realpath("/private") or normalized.startswith(os.path.realpath("/private") + os.sep):
        return True
    if normalized == os.path.realpath("/sys") or normalized.startswith(os.path.realpath("/sys") + os.sep):
        return True
    if normalized == os.path.realpath("/proc") or normalized.startswith(os.path.realpath("/proc") + os.sep):
        return True
    if normalized == os.path.realpath("/dev") or normalized.startswith(os.path.realpath("/dev") + os.sep):
        return True
    if any(normalized == prefix or normalized.startswith(prefix + os.sep) for prefix in home_sensitive):
        return True
    return False


def _is_safe_destination(token: str, cwd: Optional[str]) -> bool:
    """Restrict destinations to the current working tree or ~/projects."""
    normalized = _normalize_path(token, cwd)
    base_dir = os.path.realpath(cwd or os.getcwd())
    if normalized == base_dir or normalized.startswith(base_dir + os.sep):
        return True
    return normalized == _PROJECTS_ROOT or normalized.startswith(_PROJECTS_ROOT + os.sep)


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
    lowered = url_clean.lower()
    blocked_schemes = (
        "ftp://",
        "ftps://",
        "file://",
        "javascript:",
        "data:",
        "blob:",
        "chrome:",
        "about:",
        "vbscript:",
    )
    if lowered.startswith(blocked_schemes):
        logger.warning("Blocked unsafe URL scheme: %s", url_clean[:50])
        return None

    if "://" not in url_clean:
        url_clean = "https://" + url_clean

    parsed = urlparse(url_clean)
    if parsed.scheme not in {"http", "https"}:
        logger.warning("Blocked URL scheme: %s", parsed.scheme)
        return None
    if parsed.scheme == "http":
        logger.warning("Allowing insecure http URL: %s", url_clean[:50])

    # Block local/internal URLs
    host = (parsed.hostname or "").lower()
    if host in {"localhost", "127.0.0.1", "0.0.0.0"}:
        logger.warning("Blocked internal URL: %s", url_clean[:50])
        return None

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
