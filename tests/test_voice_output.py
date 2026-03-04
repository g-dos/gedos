"""Tests for voice output delivery."""

from unittest.mock import AsyncMock, patch

import pytest

from tools.voice_output import send_voice_response


@pytest.mark.asyncio
async def test_send_voice_response_sends_voice_when_synthesis_succeeds():
    bot = AsyncMock()

    with patch("tools.voice_output.synthesize_speech", return_value=b"ogg-bytes"):
        sent_voice = await send_voice_response(bot, 12345, "Hello world", "en")

    assert sent_voice is True
    bot.send_chat_action.assert_called_once()
    bot.send_voice.assert_awaited_once()
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_voice_response_falls_back_to_text_when_synthesis_fails():
    bot = AsyncMock()

    with patch("tools.voice_output.synthesize_speech", return_value=None):
        sent_voice = await send_voice_response(bot, 12345, "Hello world", "en")

    assert sent_voice is False
    bot.send_chat_action.assert_called_once()
    bot.send_message.assert_awaited_once_with(chat_id=12345, text="Hello world")
