"""
GEDOS Voice Output — send Telegram voice responses with text fallback.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import tempfile
from io import BytesIO
from typing import Any

from telegram.constants import ChatAction

from core.config import load_config
from tools.voice import synthesize_speech

logger = logging.getLogger(__name__)


def text_to_speech_safe(text: str) -> str:
    """
    Normalize rich text into concise plain text for speech output.

    Strips common Markdown formatting, code blocks, links, and emoji,
    then truncates to 500 chars on a sentence boundary when possible.
    """
    cleaned = text or ""
    cleaned = re.sub(r"```.*?```", " ", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = cleaned.replace("**", " ").replace("*", " ").replace("`", " ")
    cleaned = cleaned.replace("#", " ").replace("[", " ").replace("]", " ")
    cleaned = cleaned.replace("(", " ").replace(")", " ")
    cleaned = re.sub(r"^[\s>*\-•]+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) <= 500:
        return cleaned
    candidate = cleaned[:500].rstrip()
    sentence_end = max(candidate.rfind("."), candidate.rfind("!"), candidate.rfind("?"))
    if sentence_end >= 250:
        return candidate[: sentence_end + 1].strip()
    space_break = candidate.rfind(" ")
    if space_break >= 250:
        return candidate[:space_break].strip()
    return candidate


async def send_voice_response(bot: Any, chat_id: int, text: str, language: str) -> bool:
    """
    Send a Telegram voice message when synthesis succeeds, otherwise send text.

    Args:
        bot: Telegram bot instance.
        chat_id: Target Telegram chat id.
        text: Response text to speak/send.
        language: Preferred language code for TTS.

    Returns:
        True when a voice message was sent, False when text fallback was used.
    """
    config = load_config()
    voice_cfg = config.get("voice") or {}
    max_length = int(voice_cfg.get("max_text_length", 500) or 500)
    payload = (text or "").strip()
    if not payload:
        return False

    trimmed = text_to_speech_safe(payload[:max_length])
    if not trimmed:
        return False
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)

    audio_bytes = synthesize_speech(trimmed, language)
    if not audio_bytes:
        await bot.send_message(chat_id=chat_id, text=trimmed)
        return False

    voice_file = BytesIO(audio_bytes)
    voice_file.name = "gedos-response.ogg"

    try:
        await bot.send_voice(chat_id=chat_id, voice=voice_file)
        return True
    except Exception:
        logger.exception("Telegram voice delivery failed, falling back to text")
        await bot.send_message(chat_id=chat_id, text=trimmed)
        return False


def play_voice_response_locally(text: str, language: str) -> bool:
    """
    Speak a response through the local macOS speaker using afplay.

    Returns False silently if synthesis or playback fails.
    """
    payload = text_to_speech_safe(text)
    if not payload:
        return False

    try:
        from gtts import gTTS
    except ImportError:
        logger.warning("gTTS not installed for local voice playback")
        return False

    normalized_language = (language or "en").strip().lower()[:2] or "en"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            temp_path = tmp.name
        gTTS(text=payload, lang=normalized_language).save(temp_path)
        subprocess.run(["afplay", temp_path], check=True)
        return True
    except Exception:
        logger.exception("Local voice playback failed")
        return False
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                logger.debug("Failed to remove temporary voice file: %s", temp_path)
