"""Tests for /voice command integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import interfaces.telegram_bot as telegram_bot


@pytest.fixture(autouse=True)
def allow_authorized_chat():
    with patch("interfaces.telegram_bot._ignore_if_unauthorized", return_value=False):
        with patch("interfaces.telegram_bot._user_lang", return_value="en"):
            yield


def _update(text: str = "/voice on", chat_id: int = 12345):
    update = MagicMock()
    update.message = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.chat = MagicMock()
    update.message.chat.id = chat_id
    update.effective_chat = update.message.chat
    update.message.from_user = MagicMock()
    update.message.from_user.id = chat_id
    update.effective_user = update.message.from_user
    return update


@pytest.mark.asyncio
async def test_voice_on_enables_voice_and_sends_voice_confirmation():
    update = _update("/voice on")
    context = MagicMock()
    context.bot = AsyncMock()

    with patch("interfaces.telegram_bot.set_voice_output") as set_voice:
        with patch("interfaces.telegram_bot._maybe_send_voice_response", new=AsyncMock(return_value=True)) as send_voice:
            await telegram_bot.cmd_voice(update, context)

    set_voice.assert_called_once_with("12345", True)
    send_voice.assert_awaited_once()
    update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_voice_status_reports_current_setting():
    update = _update("/voice status")

    with patch("interfaces.telegram_bot._voice_enabled", return_value=True):
        await telegram_bot.cmd_voice(update, None)

    update.message.reply_text.assert_awaited_once()
    assert "voice mode is on" in str(update.message.reply_text.call_args).lower()


@pytest.mark.asyncio
async def test_ask_sends_voice_when_enabled():
    update = _update("/ask explain tests")
    context = MagicMock()
    context.bot = AsyncMock()

    with patch("interfaces.telegram_bot.complete", create=True, return_value="Here is the answer."):
        with patch("core.llm.complete", return_value="Here is the answer."):
            with patch("interfaces.telegram_bot._maybe_send_voice_response", new=AsyncMock(return_value=True)) as send_voice:
                await telegram_bot.cmd_ask(update, context)

    send_voice.assert_awaited_once()
