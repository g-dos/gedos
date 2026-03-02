"""
Tests for voice input: mock transcription, handler routing.
"""
import pytest
from unittest.mock import patch, AsyncMock

from tools.voice import transcribe_audio
from interfaces.telegram_bot import handle_voice_message, _is_background_noise_only


class TestTranscribeAudio:
    """Test transcription."""

    def test_file_not_found_returns_error(self):
        result, err = transcribe_audio("/nonexistent/path/file.ogg")
        assert result == ""
        assert err is not None
        assert "not found" in err.lower() or "pip install" in err.lower()

    def test_whisper_not_installed_returns_install_msg(self):
        # When whisper is not installed, we get install message (before or after file check)
        result, err = transcribe_audio("/tmp/nonexistent.ogg")
        assert result == ""
        assert err is not None
        assert "pip install" in err or "whisper" in err.lower() or "not found" in err.lower()


class TestBackgroundNoiseDetection:
    """Test _is_background_noise_only."""

    def test_short_text_is_noise(self):
        assert _is_background_noise_only("a") is True
        assert _is_background_noise_only("") is True

    def test_inaudible_marker(self):
        assert _is_background_noise_only("[inaudible]") is True
        assert _is_background_noise_only("something [silence] more") is True

    def test_real_command_not_noise(self):
        assert _is_background_noise_only("open VS Code and create hello.py") is False
        assert _is_background_noise_only("run the tests") is False


class TestVoiceHandlerRouting:
    """Test voice handler routes to task execution."""

    @pytest.mark.asyncio
    async def test_voice_routes_to_task_on_success(self):
        from unittest.mock import MagicMock
        from telegram import Update, Message, User, Chat, Voice

        mock_msg = MagicMock()
        mock_msg.voice = Voice(file_id="abc", file_unique_id="x", duration=5)
        mock_msg.chat = Chat(id=12345, type="private")
        mock_msg.from_user = User(id=12345, first_name="Test", is_bot=False)
        mock_msg.reply_text = AsyncMock(return_value=MagicMock(edit_text=AsyncMock()))
        mock_msg.text = None

        mock_update = MagicMock()
        mock_update.message = mock_msg
        mock_update.effective_chat = mock_msg.chat

        mock_ctx = AsyncMock()
        mock_file = AsyncMock()
        mock_file.download_to_drive = AsyncMock()
        mock_ctx.bot.get_file.return_value = mock_file
        mock_ctx.bot.send_chat_action = AsyncMock()

        with patch("tools.voice.transcribe_audio", return_value=("open VS Code", None)):
            with patch("interfaces.telegram_bot.cmd_task", new_callable=AsyncMock) as mock_cmd:
                with patch("interfaces.telegram_bot.add_conversation"):
                    with patch("interfaces.telegram_bot._check_rate_limit", return_value=True):
                        await handle_voice_message(mock_update, mock_ctx)
                        mock_cmd.assert_called_once()
                        assert mock_msg.text == "/task open VS Code"

    @pytest.mark.asyncio
    async def test_voice_rejects_too_long(self):
        from unittest.mock import MagicMock
        from telegram import Chat, User, Voice

        mock_msg = MagicMock()
        mock_msg.voice = Voice(file_id="x", file_unique_id="y", duration=90)
        mock_msg.chat = Chat(id=12345, type="private")
        mock_msg.from_user = User(id=12345, first_name="Test", is_bot=False)
        mock_msg.reply_text = AsyncMock()

        mock_update = MagicMock()
        mock_update.message = mock_msg
        mock_update.effective_chat = mock_msg.chat

        mock_ctx = AsyncMock()

        with patch("interfaces.telegram_bot._check_rate_limit", return_value=True):
            await handle_voice_message(mock_update, mock_ctx)
        mock_msg.reply_text.assert_called_once()
        call_args = str(mock_msg.reply_text.call_args)
        assert "60" in call_args or "long" in call_args.lower()
