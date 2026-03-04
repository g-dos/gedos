"""Natural-language schedule parsing regression coverage."""

from datetime import datetime, timedelta

from core.scheduler import parse_schedule_command, parse_schedule_expression


def test_every_day_at_9am_parses_daily():
    result = parse_schedule_expression("every day at 9am", "UTC")
    assert result["type"] == "daily"
    assert result["times"] == ["09:00"]


def test_every_weekday_at_9am_parses_weekdays():
    result = parse_schedule_expression("every weekday at 9am", "UTC")
    assert result["type"] == "weekly"
    assert result["days"] == ["monday", "tuesday", "wednesday", "thursday", "friday"]


def test_every_monday_at_9am_parses_single_day():
    result = parse_schedule_expression("every monday at 9am", "UTC")
    assert result["type"] == "weekly"
    assert result["days"] == ["monday"]


def test_every_hour_parses_interval():
    result = parse_schedule_expression("every hour", "UTC")
    assert result["type"] == "interval"
    assert result["interval_minutes"] == 60


def test_every_30_minutes_parses_interval():
    result = parse_schedule_expression("every 30 minutes", "UTC")
    assert result["type"] == "interval"
    assert result["interval_minutes"] == 30


def test_once_tomorrow_at_3pm_parses_once():
    result = parse_schedule_expression("once tomorrow at 3pm", "UTC")
    tomorrow = datetime.now(result["run_at"].tzinfo).date() + timedelta(days=1)
    assert result["type"] == "once"
    assert result["run_at"].date() == tomorrow
    assert result["run_at"].strftime("%H:%M") == "15:00"


def test_in_30_minutes_parses_once():
    result = parse_schedule_expression("in 30 minutes", "UTC")
    now = datetime.now(result["run_at"].tzinfo)
    delta_seconds = (result["run_at"] - now).total_seconds()
    assert result["type"] == "once"
    assert 25 * 60 <= delta_seconds <= 35 * 60


def test_every_friday_at_5pm_parses_weekly():
    result = parse_schedule_expression("every friday at 5pm", "UTC")
    assert result["type"] == "weekly"
    assert result["days"] == ["friday"]
    assert result["times"] == ["17:00"]


def test_twice_a_day_parses_two_times():
    result = parse_schedule_expression("twice a day at 9am and 6pm", "UTC")
    assert result["type"] == "daily"
    assert result["times"] == ["09:00", "18:00"]


def test_daily_9am_broken_format_now_parses():
    result = parse_schedule_expression("daily 9am", "UTC")
    assert result["type"] == "daily"
    assert result["times"] == ["09:00"]


def test_daily_9am_command_with_task_now_parses():
    result = parse_schedule_command('/schedule daily 9am "check HN"', user_tz="UTC")
    assert result["frequency"] == "daily"
    assert result["times"] == ["09:00"]
    assert result["task"] == "check HN"


def test_unknown_format_returns_none_not_crash():
    result = parse_schedule_expression("bananas next eventually", "UTC")
    assert result is None
