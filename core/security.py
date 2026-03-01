"""
GEDOS security utilities — input sanitization and validation.
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Blacklisted shell characters and patterns
DANGEROUS_PATTERNS = [
    r";.*rm\s+-rf",  # rm -rf after semicolon
    r"&&.*rm\s+-rf",  # rm -rf after &&
    r"\|.*rm\s+-rf",  # rm -rf after pipe
    r">\s*/dev/",  # Redirect to /dev/*
    r"curl.*\|\s*sh",  # Pipe curl to shell
    r"wget.*\|\s*sh",  # Pipe wget to shell
]


def sanitize_command(command: str) -> Optional[str]:
    """
    Sanitize user input for shell execution.
    Returns None if command is dangerous, otherwise returns sanitized command.
    """
    if not command or not command.strip():
        return None
    
    cmd = command.strip()
    
    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, cmd, re.IGNORECASE):
            logger.warning("Blocked dangerous command: %s", cmd[:50])
            return None
    
    # Block raw shell injection attempts
    if ";;" in cmd or "$()" in cmd or "`" in cmd:
        logger.warning("Blocked potential shell injection: %s", cmd[:50])
        return None
    
    return cmd


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
