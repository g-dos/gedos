"""
GEDOS Voice Output — send Telegram voice responses with text fallback.
"""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Any

from telegram.constants import ChatAction

from core.config import load_config
from tools.voice import synthesize_speech

logger = logging.getLogger(__name__)


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

    trimmed = payload[:max_length]
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
