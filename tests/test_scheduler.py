"""
Tests for scheduler: parsing, create, list, delete, trigger schedule.
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from core.memory import init_db
from core.scheduler import (
    _parse_natural_time,
    create_schedule,
    get_scheduled_task_by_id,
    list_user_schedules,
    parse_schedule_command,
    parse_schedule_expression,
    remove_schedule,
)


class TestParseScheduleExpression:
    """Natural-language schedule parsing."""

    @pytest.mark.parametrize(
        ("expr", "expected_type", "expected_times", "expected_days", "expected_interval"),
        [
            ("every day at 9am", "daily", ["09:00"], None, None),
            ("every day at 9:30am", "daily", ["09:30"], None, None),
            ("daily at 9am", "daily", ["09:00"], None, None),
            ("every morning at 9", "daily", ["09:00"], None, None),
            ("every weekday at 9am", "weekly", ["09:00"], ["monday", "tuesday", "wednesday", "thursday", "friday"], None),
            ("every monday at 9am", "weekly", ["09:00"], ["monday"], None),
            ("every monday and friday", "weekly", ["09:00"], ["monday", "friday"], None),
            ("every hour", "interval", [], None, 60),
            ("every 30 minutes", "interval", [], None, 30),
            ("every 2 hours", "interval", [], None, 120),
            ("every friday at 5pm", "weekly", ["17:00"], ["friday"], None),
            ("every night at midnight", "daily", ["00:00"], None, None),
            ("every sunday at noon", "weekly", ["12:00"], ["sunday"], None),
            ("weekdays at 8am", "weekly", ["08:00"], ["monday", "tuesday", "wednesday", "thursday", "friday"], None),
            ("twice a day at 9am and 6pm", "daily", ["09:00", "18:00"], None, None),
        ],
    )
    def test_supported_recurring_expressions(self, expr, expected_type, expected_times, expected_days, expected_interval):
        result = parse_schedule_expression(expr, "UTC")
        assert result is not None
        assert result["type"] == expected_type
        assert result["times"] == expected_times
        assert result["days"] == expected_days
        assert result["interval_minutes"] == expected_interval
        assert result["human_readable"]

    @pytest.mark.parametrize(
        "expr",
        [
            "once tomorrow at 3pm",
            "once at 14:30",
            "in 30 minutes",
            "in 2 hours",
            "next monday at 10am",
        ],
    )
    def test_supported_one_time_expressions(self, expr):
        result = parse_schedule_expression(expr, "UTC")
        assert result is not None
        assert result["type"] == "once"
        assert isinstance(result["run_at"], datetime)
        assert result["human_readable"].startswith("Once at")


class TestParseScheduleCommand:
    """Command parsing from /schedule."""

    def test_explicit_daily(self):
        result = parse_schedule_command('/schedule daily 09:00 "check HN"', user_tz="UTC")
        assert result["frequency"] == "daily"
        assert result["time"] == "09:00"
        assert result["task"] == "check HN"

    def test_explicit_once(self):
        result = parse_schedule_command('/schedule once 14:30 "remind me"', user_tz="UTC")
        assert result["frequency"] == "once"
        assert result["time"] == "14:30"
        assert result["schedule_date"] is not None

    def test_explicit_weekly(self):
        result = parse_schedule_command('/schedule weekly monday 09:00 "report"', user_tz="UTC")
        assert result["frequency"] == "weekly"
        assert result["day_of_week"] == "monday"
        assert result["time"] == "09:00"

    def test_nl_every_day_at_9am(self):
        result = parse_schedule_command('/schedule every day at 9am "check HN"', user_tz="UTC")
        assert result["frequency"] == "daily"
        assert result["time"] == "09:00"
        assert result["human_readable"] == "Every day at 9:00 AM"

    def test_nl_interval(self):
        result = parse_schedule_command('/schedule every 30 minutes "refresh cache"', user_tz="UTC")
        assert result["frequency"] == "interval"
        assert result["interval_minutes"] == 30

    def test_invalid_returns_none(self):
        assert parse_schedule_command('/schedule invalid', user_tz="UTC") is None


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

    def test_named_time(self):
        assert _parse_natural_time("midnight") == "00:00"


class TestSchedulerCRUD:
    """Test create, list, delete schedules."""

    def test_create_and_list(self):
        init_db()
        task = create_schedule("test_user_1", "daily", "09:00", "check HN", timezone="UTC")
        assert task.id is not None
        assert task.task_description == "check HN"
        schedules = list_user_schedules("test_user_1")
        assert len(schedules) >= 1
        assert any(s.task_description == "check HN" for s in schedules)
        remove_schedule(task.id)

    def test_remove_schedule(self):
        init_db()
        task = create_schedule("test_user_2", "daily", "09:00", "test task", timezone="UTC")
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
        task = create_schedule("12345", "daily", "09:00", "triggered task", timezone="UTC")
        try:
            with patch("interfaces.telegram_bot._execute_task_autonomously", new_callable=AsyncMock) as mock_exec:
                mock_exec.return_value = {"success": True}
                from core.scheduler import _execute_scheduled_task

                await _execute_scheduled_task(task.id)
                mock_exec.assert_called_once_with(task="triggered task", user_id=12345)
        finally:
            remove_schedule(task.id)
