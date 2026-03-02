"""
GEDOS Language detection — detect user language and cache per user.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_LANG = "en"


def detect_language(text: str) -> str:
    """
    Detect language of text using langdetect.
    Returns ISO 639-1 code (e.g. "en", "pt", "es").
    Default: "en" if detection fails or text is too short.
    """
    if not text or not text.strip() or len(text.strip()) < 3:
        return _DEFAULT_LANG
    try:
        import langdetect
        raw = langdetect.detect(text.strip())
        if raw and len(raw) >= 2:
            return raw[:2].lower()
    except Exception as e:
        logger.debug("Language detection failed: %s", e)
    return _DEFAULT_LANG


def get_and_update_user_language(user_id: str, text: str) -> str:
    """
    Detect language from text, update cache if changed, return current language.
    """
    detected = detect_language(text)
    try:
        from core.memory import get_user_language as _get_cached, set_user_language as _set
        cached = _get_cached(user_id)
        if cached != detected:
            _set(user_id, detected)
            return detected
        return cached if cached else detected
    except Exception as e:
        logger.warning("Failed to update user language cache: %s", e)
        return detected
