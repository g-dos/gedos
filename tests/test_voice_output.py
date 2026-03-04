"""Tests for voice output synthesis, delivery, and command integration."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import interfaces.telegram_bot as telegram_bot
from agents.terminal_agent import TerminalResult
from tools.voice import synthesize_speech
from tools.voice_output import send_voice_response, text_to_speech_safe


def _update(text: str, chat_id: int = 12345):
    update = MagicMock()
    update.message = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.chat = MagicMock()
    update.message.chat.id = chat_id
    update.message.from_user = MagicMock()
    update.message.from_user.id = chat_id
    update.effective_chat = update.message.chat
    update.effective_user = update.message.from_user
    return update


@pytest.fixture(autouse=True)
def allow_authorized_chat():
    with patch("interfaces.telegram_bot._ignore_if_unauthorized", return_value=False):
        with patch("interfaces.telegram_bot._user_lang", return_value="en"):
            yield


def test_synthesize_speech_returns_bytes_when_gtts_succeeds():
    class FakeTTS:
        def __init__(self, text, lang):
            self.text = text
            self.lang = lang

        def write_to_fp(self, fp):
            fp.write(b"fake-mp3")

    class FakeAudio:
        def export(self, fp, format, codec):
            assert format == "ogg"
            assert codec == "libopus"
            fp.write(b"fake-ogg")

    fake_gtts = ModuleType("gtts")
    fake_gtts.gTTS = FakeTTS
    fake_pydub = ModuleType("pydub")
    fake_pydub.AudioSegment = type(
        "FakeAudioSegment",
        (),
        {"from_file": staticmethod(lambda fp, format: FakeAudio())},
    )

    with patch.dict(sys.modules, {"gtts": fake_gtts, "pydub": fake_pydub}):
        result = synthesize_speech("Hello world", "en")

    assert result == b"fake-ogg"


def test_synthesize_speech_returns_none_on_gtts_failure():
    class FakeTTS:
        def __init__(self, text, lang):
            self.text = text
            self.lang = lang

        def write_to_fp(self, fp):
            raise RuntimeError("tts failed")

    fake_gtts = ModuleType("gtts")
    fake_gtts.gTTS = FakeTTS
    fake_pydub = ModuleType("pydub")
    fake_pydub.AudioSegment = type(
        "FakeAudioSegment",
        (),
        {"from_file": staticmethod(lambda fp, format: None)},
    )

    with patch.dict(sys.modules, {"gtts": fake_gtts, "pydub": fake_pydub}):
        result = synthesize_speech("Hello world", "en")

    assert result is None


@pytest.mark.asyncio
async def test_send_voice_response_sends_voice_message_when_bytes_returned():
    bot = AsyncMock()

    with patch("tools.voice_output.synthesize_speech", return_value=b"ogg-bytes"):
        sent_voice = await send_voice_response(bot, 12345, "Hello world", "en")

    assert sent_voice is True
    bot.send_chat_action.assert_called_once()
    bot.send_voice.assert_awaited_once()
    bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_voice_response_sends_text_when_synthesis_fails():
    bot = AsyncMock()

    with patch("tools.voice_output.synthesize_speech", return_value=None):
        sent_voice = await send_voice_response(bot, 12345, "Hello world", "en")

    assert sent_voice is False
    bot.send_chat_action.assert_called_once()
    bot.send_message.assert_awaited_once_with(chat_id=12345, text="Hello world")


def test_text_to_speech_safe_strips_markdown_correctly():
    text = """# Title

```python
print("secret")
```

**Hello** [world](https://example.com)! 😀
- item one
"""

    cleaned = text_to_speech_safe(text)

    assert "print" not in cleaned
    assert "https://example.com" not in cleaned
    assert "**" not in cleaned
    assert "```" not in cleaned
    assert "Hello world!" in cleaned


def test_text_to_speech_safe_truncates_at_500_chars_at_sentence_boundary():
    text = "A" * 300 + ". " + ("B" * 300) + "."

    cleaned = text_to_speech_safe(text)

    assert len(cleaned) <= 500
    assert cleaned.endswith(".")
    assert "B" * 300 not in cleaned


@pytest.mark.asyncio
async def test_voice_on_sets_voice_output_enabled_true_in_db():
    update = _update("/voice on")
    context = MagicMock()
    context.bot = AsyncMock()

    with patch("interfaces.telegram_bot.set_voice_output") as set_voice:
        with patch("interfaces.telegram_bot._maybe_send_voice_response", new=AsyncMock(return_value=True)):
            await telegram_bot.cmd_voice(update, context)

    set_voice.assert_called_once_with("12345", True)


@pytest.mark.asyncio
async def test_voice_off_sets_voice_output_enabled_false_in_db():
    update = _update("/voice off")

    with patch("interfaces.telegram_bot.set_voice_output") as set_voice:
        await telegram_bot.cmd_voice(update, None)

    set_voice.assert_called_once_with("12345", False)
    update.message.reply_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_task_completion_sends_voice_when_enabled():
    update = _update("/task ls")
    context = MagicMock()
    context.bot = AsyncMock()
    result = TerminalResult(command="ls", success=True, stdout="file1", stderr="", return_code=0)

    with patch("interfaces.telegram_bot._check_rate_limit", return_value=True):
        with patch("interfaces.telegram_bot.is_destructive_command", return_value=False):
            with patch("interfaces.telegram_bot.run_shell", return_value=result):
                with patch("interfaces.telegram_bot.get_voice_output", return_value=True):
                    with patch("interfaces.telegram_bot.send_voice_response", new=AsyncMock()) as send_voice:
                        with patch("interfaces.telegram_bot.add_conversation"):
                            with patch("interfaces.telegram_bot.memory_add_task"):
                                with patch("interfaces.telegram_bot._maybe_notify_new_patterns", new=AsyncMock()):
                                    with patch("interfaces.telegram_bot._learn_patterns_for_task", return_value=[]):
                                        await telegram_bot.cmd_task(update, context)

    send_voice.assert_awaited_once()
    update.message.reply_text.assert_awaited()


@pytest.mark.asyncio
async def test_task_completion_sends_text_when_voice_disabled():
    update = _update("/task ls")
    context = MagicMock()
    context.bot = AsyncMock()
    result = TerminalResult(command="ls", success=True, stdout="file1", stderr="", return_code=0)

    with patch("interfaces.telegram_bot._check_rate_limit", return_value=True):
        with patch("interfaces.telegram_bot.is_destructive_command", return_value=False):
            with patch("interfaces.telegram_bot.run_shell", return_value=result):
                with patch("interfaces.telegram_bot.get_voice_output", return_value=False):
                    with patch("interfaces.telegram_bot.send_voice_response", new=AsyncMock()) as send_voice:
                        with patch("interfaces.telegram_bot.add_conversation"):
                            with patch("interfaces.telegram_bot.memory_add_task"):
                                with patch("interfaces.telegram_bot._maybe_notify_new_patterns", new=AsyncMock()):
                                    with patch("interfaces.telegram_bot._learn_patterns_for_task", return_value=[]):
                                        await telegram_bot.cmd_task(update, context)

    send_voice.assert_not_called()
    update.message.reply_text.assert_awaited()
