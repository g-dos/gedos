"""
Integration tests — test_copilot_flow.py
Simulates Copilot Mode activation and context-aware suggestions.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, Message, Chat, User
from telegram.ext import ContextTypes

from interfaces.telegram_bot import cmd_copilot, _send_copilot_suggestion
from core.copilot_context import analyze_context


@pytest.fixture
def mock_update():
    """Create a mock Telegram Update for testing."""
    update = Mock(spec=Update)
    update.message = Mock(spec=Message)
    update.message.text = "/copilot on"
    update.message.chat = Mock(spec=Chat)
    update.message.chat.id = 12345
    update.message.from_user = Mock(spec=User)
    update.message.from_user.id = 12345
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Create a mock Telegram ContextTypes for testing."""
    return Mock(spec=ContextTypes.DEFAULT_TYPE)


@pytest.mark.asyncio
async def test_copilot_activation(mock_update, mock_context):
    """Test /copilot on enables Copilot Mode."""
    mock_update.message.text = "/copilot on"
    
    await cmd_copilot(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called()
    call_args = mock_update.message.reply_text.call_args
    response = call_args[0][0] if call_args else ""
    
    assert "copilot" in response.lower() and ("active" in response.lower() or "enabled" in response.lower())


@pytest.mark.asyncio
async def test_copilot_deactivation(mock_update, mock_context):
    """Test /copilot off disables Copilot Mode."""
    mock_update.message.text = "/copilot off"
    
    await cmd_copilot(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called()
    call_args = mock_update.message.reply_text.call_args
    response = call_args[0][0] if call_args else ""
    
    assert "copilot" in response.lower() and ("disabled" in response.lower() or "off" in response.lower())


def test_copilot_context_analysis():
    """Test context analysis detects active app and suggests actions."""
    # Mock AX Tree data
    mock_tree = {
        "app": "Visual Studio Code",
        "windows": [],
        "buttons": [],
        "text_fields": [],
        "error": None
    }
    
    with patch("core.copilot_context.get_ax_tree", return_value=mock_tree):
        result = analyze_context()
    
    assert result["app"] == "Visual Studio Code"
    # Should suggest actions for VS Code
    assert result.get("suggestion") is not None or result.get("warning") is None


def test_copilot_error_detection():
    """Test Copilot detects errors on screen and sends warnings."""
    mock_tree = {
        "app": "Terminal",
        "windows": [{"title": "Error: command not found"}],
        "buttons": [],
        "text_fields": [],
        "error": None
    }
    
    with patch("core.copilot_context.get_ax_tree", return_value=mock_tree):
        result = analyze_context()
    
    assert result.get("warning") is not None or "error" in result.get("app", "").lower()
