"""
Integration tests — test_copilot_flow.py
Simulates Copilot Mode activation and context-aware suggestions.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, Message, Chat, User
from telegram.ext import ContextTypes

from interfaces.telegram_bot import cmd_copilot
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


@pytest.fixture(autouse=True)
def allow_authorized_chat():
    """Pilot/Copilot integration tests are not auth tests; bypass auth gate."""
    with patch("interfaces.telegram_bot._ignore_if_unauthorized", return_value=False):
        yield


@pytest.mark.asyncio
async def test_copilot_activation(mock_update, mock_context):
    """Test /copilot on enables Copilot Mode."""
    mock_update.message.text = "/copilot on"
    
    await cmd_copilot(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called()
    call_args = mock_update.message.reply_text.call_args
    response = call_args[0][0] if call_args else ""
    
    assert "copilot" in response.lower() and "on" in response.lower()


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
    
    assert isinstance(result, list)
    assert any(hint.app == "Visual Studio Code" for hint in result)
    assert any(hint.kind == "suggestion" for hint in result)


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
    
    assert isinstance(result, list)
    assert any(hint.kind == "warning" for hint in result)
