"""
Integration tests — test_pilot_flow.py
Simulates full Pilot Mode task execution via mocked Telegram.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from telegram import Update, Message, Chat, User
from telegram.ext import ContextTypes

from interfaces.telegram_bot import cmd_task, cmd_status, cmd_stop
import interfaces.telegram_bot as telegram_bot


@pytest.fixture
def mock_update():
    """Create a mock Telegram Update for testing."""
    update = Mock(spec=Update)
    update.message = Mock(spec=Message)
    update.message.text = "/task ls -la"
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
async def test_pilot_task_terminal_command(mock_update, mock_context):
    """Test Pilot Mode executing a terminal command."""
    mock_update.message.text = "/task echo hello"
    
    await cmd_task(mock_update, mock_context)
    
    # Verify response was sent
    mock_update.message.reply_text.assert_called()
    call_args = mock_update.message.reply_text.call_args
    response = call_args[0][0] if call_args else ""
    
    assert "hello" in response.lower() or "completed" in response.lower()


@pytest.mark.asyncio
async def test_pilot_task_status(mock_update, mock_context):
    """Test /status command returns current task state."""
    await cmd_status(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called()
    call_args = mock_update.message.reply_text.call_args
    response = call_args[0][0] if call_args else ""
    
    assert "idle" in response.lower() or "running" in response.lower()


@pytest.mark.asyncio
async def test_pilot_task_cancellation(mock_update, mock_context):
    """Test /stop command sets cancellation flag."""
    telegram_bot._task_status = "running"
    
    # Stop the task
    await cmd_stop(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called()
    responses = [call[0][0] for call in mock_update.message.reply_text.call_args_list]
    
    assert any("cancel" in r.lower() or "stop" in r.lower() for r in responses)
    telegram_bot._task_status = "idle"
    telegram_bot._task_cancelled = False


@pytest.mark.asyncio
async def test_pilot_empty_task(mock_update, mock_context):
    """Test /task with no description returns usage hint."""
    mock_update.message.text = "/task"
    
    await cmd_task(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called()
    call_args = mock_update.message.reply_text.call_args
    response = call_args[0][0] if call_args else ""
    
    assert "usage" in response.lower() or "description" in response.lower()
