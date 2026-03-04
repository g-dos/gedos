"""Schedule command UX coverage with mocked Telegram interactions."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import interfaces.telegram_bot as telegram_bot


def _update(text: str, user_id: int = 12345):
    update = MagicMock()
    update.message = MagicMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.message.chat = MagicMock()
    update.message.chat.id = user_id
    update.effective_chat = update.message.chat
    update.message.from_user = MagicMock()
    update.message.from_user.id = user_id
    update.effective_user = update.message.from_user
    return update


@pytest.fixture(autouse=True)
def _authorized():
    with patch("interfaces.telegram_bot._ignore_if_unauthorized", return_value=False):
        with patch("interfaces.telegram_bot._user_lang", return_value="en"):
            with patch("interfaces.telegram_bot._user_id", return_value=12345):
                yield


@pytest.mark.asyncio
async def test_schedule_confirmation_shows_human_readable_and_next_run():
    update = _update('/schedule every weekday at 9am "check HN and brief me"')
    task = SimpleNamespace(id=3, task_description="check HN and brief me")

    with patch("core.scheduler.start_scheduler"):
        with patch("core.scheduler.ensure_user_timezone", return_value=("America/Sao_Paulo", False)):
            with patch("core.scheduler.parse_schedule_command", return_value={"frequency": "weekly", "time": "09:00", "task": "check HN and brief me"}):
                with patch("core.scheduler.create_schedule", return_value=task):
                    with patch("core.scheduler.format_schedule_rule", return_value="Every weekday at 9:00 AM"):
                        with patch("core.scheduler.format_next_run", return_value="Tomorrow, Mon Mar 9 at 9:00 AM"):
                            await telegram_bot.cmd_schedule(update, None)

    message = update.message.reply_text.call_args.args[0]
    assert "📅 Schedule confirmed:" in message
    assert "Runs:      Every weekday at 9:00 AM" in message
    assert "Next run:  Tomorrow, Mon Mar 9 at 9:00 AM" in message
    assert "✅ Saved as schedule #3" in message


@pytest.mark.asyncio
async def test_schedule_invalid_format_returns_helpful_error():
    update = _update("/schedule bananas")

    with patch("core.scheduler.start_scheduler"):
        with patch("core.scheduler.ensure_user_timezone", return_value=("UTC", False)):
            with patch("core.scheduler.parse_schedule_command", return_value=None):
                await telegram_bot.cmd_schedule(update, None)

    message = update.message.reply_text.call_args.args[0]
    assert "Invalid format" in message


@pytest.mark.asyncio
async def test_schedules_shows_all_active_schedules_formatted():
    update = _update("/schedules")
    schedules = [
        SimpleNamespace(id=1, task_description="check HN and brief me"),
        SimpleNamespace(id=2, task_description="run tests and deploy if green"),
    ]

    with patch("core.scheduler.ensure_user_timezone", return_value=("America/Sao_Paulo", False)):
        with patch("core.scheduler.list_user_schedules", return_value=schedules):
            with patch("core.scheduler.format_schedule_rule", side_effect=["Every day at 9:00 AM", "Every Friday at 5:00 PM"]):
                with patch("core.scheduler.format_next_run", side_effect=["Tomorrow at 9:00 AM", "Friday Mar 7 at 5:00 PM"]):
                    await telegram_bot.cmd_schedules(update, None)

    message = update.message.reply_text.call_args.args[0]
    assert "📅 Active schedules (2):" in message
    assert "#1  Every day at 9:00 AM" in message
    assert "Next: Tomorrow at 9:00 AM" in message
    assert "#2  Every Friday at 5:00 PM" in message
    assert "/unschedule <id> to remove" in message


@pytest.mark.asyncio
async def test_schedules_shows_empty_message_when_none():
    update = _update("/schedules")

    with patch("core.scheduler.ensure_user_timezone", return_value=("UTC", False)):
        with patch("core.scheduler.list_user_schedules", return_value=[]):
            await telegram_bot.cmd_schedules(update, None)

    assert "No active schedules" in update.message.reply_text.call_args.args[0]


@pytest.mark.asyncio
async def test_unschedule_confirmation_shows_removed_details():
    update = _update("/unschedule 1")
    task = SimpleNamespace(id=1, task_description="check HN and brief me", user_id="12345")

    with patch("core.scheduler.get_scheduled_task_by_id", return_value=task):
        with patch("core.scheduler.remove_schedule", return_value=True):
            with patch("core.scheduler.format_schedule_rule", return_value="Every day at 9:00 AM"):
                await telegram_bot.cmd_unschedule(update, None)

    message = update.message.reply_text.call_args.args[0]
    assert message == "✅ Removed: Every day at 9:00 AM — check HN and brief me"


@pytest.mark.asyncio
async def test_schedule_history_shows_last_five_runs_with_status():
    update = _update("/schedule history")
    base = datetime(2026, 3, 9, 9, 0, tzinfo=UTC)
    history = [
        SimpleNamespace(description="check HN", status="completed", agent_used="scheduler", created_at=base),
        SimpleNamespace(description="run tests", status="failed", agent_used="scheduler", created_at=base - timedelta(days=1)),
    ]

    with patch("interfaces.telegram_bot.get_recent_tasks", return_value=history):
        await telegram_bot.cmd_schedule(update, None)

    message = update.message.reply_text.call_args.args[0]
    assert "📋 Schedule history (last 5):" in message
    assert "✅ check HN" in message
    assert "❌ run tests" in message


@pytest.mark.asyncio
async def test_timezone_detected_and_applied_correctly():
    update = _update('/schedule every day at 9am "check HN"')
    task = SimpleNamespace(id=7, task_description="check HN")

    with patch("core.scheduler.start_scheduler"):
        with patch("core.scheduler.ensure_user_timezone", return_value=("America/Sao_Paulo", True)):
            with patch("core.scheduler.parse_schedule_command", return_value={"frequency": "daily", "time": "09:00", "task": "check HN"}):
                with patch("core.scheduler.create_schedule", return_value=task):
                    with patch("core.scheduler.format_schedule_rule", return_value="Every day at 9:00 AM"):
                        with patch("core.scheduler.format_next_run", return_value="Tomorrow, Mon Mar 9 at 9:00 AM"):
                            await telegram_bot.cmd_schedule(update, None)

    message = update.message.reply_text.call_args.args[0]
    assert "Detected timezone: America/Sao_Paulo. Is this correct? [Y/n]" in message
    assert "Timezone:  America/Sao_Paulo" in message
