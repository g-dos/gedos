"""
Tests for scheduler: create, list, delete, trigger schedule.
"""
import pytest
from unittest.mock import patch, AsyncMock

from core.scheduler import (
    parse_schedule_command,
    create_schedule,
    list_user_schedules,
    remove_schedule,
    get_scheduled_task_by_id,
    _parse_natural_time,
)
from core.memory import init_db


class TestParseSchedule:
    """Test schedule command parsing."""

    def test_explicit_daily(self):
        r = parse_schedule_command('/schedule daily 09:00 "check HN"')
        assert r == {"frequency": "daily", "time": "09:00", "day_of_week": None, "task": "check HN"}

    def test_explicit_once(self):
        r = parse_schedule_command('/schedule once 14:30 "remind me"')
        assert r == {"frequency": "once", "time": "14:30", "day_of_week": None, "task": "remind me"}

    def test_explicit_weekly(self):
        r = parse_schedule_command('/schedule weekly monday 09:00 "report"')
        assert r == {"frequency": "weekly", "time": "09:00", "day_of_week": "monday", "task": "report"}

    def test_nl_every_day_at_9am(self):
        r = parse_schedule_command('/schedule every day at 9am "check HN"')
        assert r["frequency"] == "daily"
        assert r["time"] == "09:00"
        assert r["task"] == "check HN"

    def test_nl_tomorrow_at_3pm(self):
        r = parse_schedule_command('/schedule tomorrow at 3pm "remind me"')
        assert r["frequency"] == "once"
        assert r["time"] == "15:00"
        assert "schedule_date" in r

    def test_nl_every_monday_at_9am(self):
        r = parse_schedule_command('/schedule every monday at 9am "report"')
        assert r["frequency"] == "weekly"
        assert r["day_of_week"] == "monday"
        assert r["time"] == "09:00"

    def test_invalid_returns_none(self):
        assert parse_schedule_command('/schedule invalid') is None


class TestParseNaturalTime:
    """Test natural time parsing."""

    def test_9am(self):
        assert _parse_natural_time("9am") == "09:00"

    def test_3pm(self):
        assert _parse_natural_time("3pm") == "15:00"

    def test_9_30am(self):
        assert _parse_natural_time("9:30am") == "09:30"

    def test_12pm(self):
        assert _parse_natural_time("12pm") == "12:00"


class TestSchedulerCRUD:
    """Test create, list, delete schedules."""

    def test_create_and_list(self):
        init_db()
        task = create_schedule("test_user_1", "daily", "09:00", "check HN")
        assert task.id is not None
        assert task.task_description == "check HN"
        schedules = list_user_schedules("test_user_1")
        assert len(schedules) >= 1
        assert any(s.task_description == "check HN" for s in schedules)
        remove_schedule(task.id)  # cleanup

    def test_remove_schedule(self):
        init_db()
        task = create_schedule("test_user_2", "daily", "09:00", "test task")
        task_id = task.id
        assert remove_schedule(task_id) is True
        assert get_scheduled_task_by_id(task_id) is None

    def test_remove_nonexistent(self):
        init_db()
        assert remove_schedule(99999) is False


class TestSchedulerTrigger:
    """Test schedule trigger (mock execution)."""

    @pytest.mark.asyncio
    async def test_trigger_executes_task(self):
        init_db()
        task = create_schedule("12345", "daily", "09:00", "triggered task")
        try:
            with patch("interfaces.telegram_bot._execute_task_autonomously", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = {"success": True}
                from core.scheduler import _execute_scheduled_task
                await _execute_scheduled_task(task.id)
                mock_exec.assert_called_once_with(task="triggered task", user_id=12345)
        finally:
            remove_schedule(task.id)
