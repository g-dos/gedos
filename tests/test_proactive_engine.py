"""Tests for proactive engine and proactive watchers."""

from __future__ import annotations

from datetime import datetime, timedelta, UTC
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import interfaces.telegram_bot as telegram_bot

from core import proactive_engine
from core.watchers import github_watcher, idle_watcher, morning_briefing, system_watcher


def setup_function() -> None:
    proactive_engine._SINKS.clear()
    proactive_engine._LAST_SENT_AT.clear()
    proactive_engine._RECENT_MESSAGES.clear()
    system_watcher._HIGH_CPU_STREAK.clear()
    github_watcher._SEEN_ISSUES.clear()
    github_watcher._SEEN_PULLS.clear()
    github_watcher._SEEN_RUNS.clear()
    github_watcher._SEEN_REVIEW_REQUESTS.clear()
    idle_watcher._LAST_INPUT_AT.clear()
    idle_watcher._LAST_END_OF_DAY_SENT.clear()
    morning_briefing._LAST_BRIEFING_DAY.clear()
    telegram_bot._copilot_sensitivity_per_user.clear()


def _register_test_sink(messages: list[tuple[str, str, str, str]]) -> None:
    proactive_engine.register_sink("test", lambda user_id, message, category, priority: messages.append((user_id, message, category, priority)))


def test_notify_sends_message_when_cooldown_has_passed():
    messages: list[tuple[str, str, str, str]] = []
    _register_test_sink(messages)

    sent = proactive_engine.notify("123", "hello", "screen", "medium")

    assert sent is True
    assert messages == [("123", "hello", "screen", "medium")]


def test_notify_deduplicates_same_message_within_ten_minutes():
    messages: list[tuple[str, str, str, str]] = []
    _register_test_sink(messages)
    proactive_engine.notify("123", "hello", "screen", "medium")
    proactive_engine._LAST_SENT_AT["123"] = datetime.now(UTC) - timedelta(minutes=11)

    sent = proactive_engine.notify("123", "hello", "screen", "medium")

    assert sent is False
    assert len(messages) == 1


def test_notify_respects_global_cooldown_of_thirty_seconds():
    messages: list[tuple[str, str, str, str]] = []
    _register_test_sink(messages)
    proactive_engine._LAST_SENT_AT["123"] = datetime.now(UTC) - timedelta(seconds=10)

    sent = proactive_engine.notify("123", "new message", "system", "medium")

    assert sent is False
    assert messages == []


def test_notify_respects_copilot_sensitivity_setting():
    messages: list[tuple[str, str, str, str]] = []
    _register_test_sink(messages)
    telegram_bot._copilot_sensitivity_per_user[123] = "low"
    proactive_engine._LAST_SENT_AT["123"] = datetime.now(UTC) - timedelta(seconds=31)

    with patch("core.proactive_engine.load_config", return_value={"copilot": {"sensitivity": {"high": 10, "medium": 30, "low": 120}}}):
        sent = proactive_engine.notify("123", "new message", "system", "medium")

    assert sent is False
    assert messages == []


def test_high_priority_bypasses_low_medium_cooldown():
    messages: list[tuple[str, str, str, str]] = []
    _register_test_sink(messages)
    telegram_bot._copilot_sensitivity_per_user[123] = "low"
    proactive_engine._LAST_SENT_AT["123"] = datetime.now(UTC) - timedelta(seconds=31)

    with patch("core.proactive_engine.load_config", return_value={"copilot": {"sensitivity": {"high": 10, "medium": 30, "low": 120}}}):
        sent = proactive_engine.notify("123", "urgent", "system", "high")

    assert sent is True
    assert messages == [("123", "urgent", "system", "high")]


def test_system_watcher_triggers_on_cpu_above_ninety():
    proc = SimpleNamespace(pid=77, info={"name": "python", "cpu_percent": 95.0, "create_time": datetime.now(UTC).timestamp()})
    system_watcher._HIGH_CPU_STREAK[77] = 4

    with patch("core.watchers.system_watcher.known_user_ids", return_value=["123"]):
        with patch("core.watchers.system_watcher.psutil.virtual_memory", return_value=SimpleNamespace(percent=40)):
            with patch("core.watchers.system_watcher.psutil.disk_usage", return_value=SimpleNamespace(percent=50)):
                with patch("core.watchers.system_watcher._top_cpu_process", return_value=(proc, 95.0)):
                    with patch("core.watchers.system_watcher.notify") as notify_mock:
                        system_watcher._maybe_notify_system_health()

    assert any("CPU" in call.args[1] for call in notify_mock.call_args_list)


def test_system_watcher_triggers_on_disk_above_ninety():
    proc = SimpleNamespace(pid=77, info={"name": "python", "cpu_percent": 1.0, "create_time": datetime.now(UTC).timestamp()})
    with patch("core.watchers.system_watcher.known_user_ids", return_value=["123"]):
        with patch("core.watchers.system_watcher.psutil.virtual_memory", return_value=SimpleNamespace(percent=40)):
            with patch("core.watchers.system_watcher.psutil.disk_usage", return_value=SimpleNamespace(percent=91)):
                with patch("core.watchers.system_watcher._top_cpu_process", return_value=(proc, 1.0)):
                    with patch("core.watchers.system_watcher.notify") as notify_mock:
                        system_watcher._maybe_notify_system_health()

    assert any("Disk at 91%" in call.args[1] for call in notify_mock.call_args_list)


def test_system_watcher_does_not_trigger_below_threshold():
    proc = SimpleNamespace(pid=77, info={"name": "python", "cpu_percent": 10.0, "create_time": datetime.now(UTC).timestamp()})
    with patch("core.watchers.system_watcher.known_user_ids", return_value=["123"]):
        with patch("core.watchers.system_watcher.psutil.virtual_memory", return_value=SimpleNamespace(percent=40)):
            with patch("core.watchers.system_watcher.psutil.disk_usage", return_value=SimpleNamespace(percent=50)):
                with patch("core.watchers.system_watcher._top_cpu_process", return_value=(proc, 10.0)):
                    with patch("core.watchers.system_watcher.notify") as notify_mock:
                        system_watcher._maybe_notify_system_health()

    notify_mock.assert_not_called()


def test_github_watcher_triggers_on_new_issue():
    issue = SimpleNamespace(id=10, number=3, title="Broken build", pull_request=None)
    initial_repo = SimpleNamespace(
        full_name="g-dos/gedos",
        get_issues=lambda **kwargs: [],
        get_pulls=lambda **kwargs: [],
        get_workflow_runs=lambda **kwargs: [],
    )
    repo = SimpleNamespace(
        full_name="g-dos/gedos",
        get_issues=lambda **kwargs: [issue],
        get_pulls=lambda **kwargs: [],
        get_workflow_runs=lambda **kwargs: [],
    )
    with patch("core.watchers.github_watcher.notify") as notify_mock:
        github_watcher._poll_repo(initial_repo, "123")
        github_watcher._poll_repo(repo, "123")

    notify_mock.assert_called_once()
    assert "New issue opened" in notify_mock.call_args.args[1]


def test_github_watcher_triggers_on_ci_failure():
    run = SimpleNamespace(id=44, conclusion="failure", name="CI")
    repo = SimpleNamespace(
        full_name="g-dos/gedos",
        get_issues=lambda **kwargs: [],
        get_pulls=lambda **kwargs: [],
        get_workflow_runs=lambda **kwargs: [run],
    )
    with patch("core.watchers.github_watcher.notify") as notify_mock:
        github_watcher._poll_repo(repo, "123")

    notify_mock.assert_called_once()
    assert "CI failed" in notify_mock.call_args.args[1]


def test_github_watcher_skips_silently_when_no_github_token():
    stop_event = MagicMock()
    stop_event.wait.return_value = True
    with patch("core.watchers.github_watcher._client", return_value=None):
        with patch("core.watchers.github_watcher.notify") as notify_mock:
            github_watcher.run_github_watcher(stop_event=stop_event)

    notify_mock.assert_not_called()


def test_idle_watcher_triggers_after_ten_minutes_of_no_input():
    stop_event = MagicMock()
    stop_event.wait.side_effect = [False, True]
    idle_watcher._LAST_INPUT_AT["123"] = datetime.now() - timedelta(minutes=11)

    with patch("core.watchers.idle_watcher.known_user_ids", return_value=["123"]):
        with patch("core.watchers.idle_watcher._default_end_of_day_hour", return_value=23):
            with patch("core.watchers.idle_watcher.notify") as notify_mock:
                idle_watcher.run_idle_watcher(stop_event=stop_event)

    notify_mock.assert_called_once()
    assert "You seem idle" in notify_mock.call_args.args[1]


def test_idle_watcher_does_not_trigger_before_ten_minutes():
    stop_event = MagicMock()
    stop_event.wait.side_effect = [False, True]
    idle_watcher._LAST_INPUT_AT["123"] = datetime.now() - timedelta(minutes=5)

    with patch("core.watchers.idle_watcher.known_user_ids", return_value=["123"]):
        with patch("core.watchers.idle_watcher._default_end_of_day_hour", return_value=23):
            with patch("core.watchers.idle_watcher.notify") as notify_mock:
                idle_watcher.run_idle_watcher(stop_event=stop_event)

    notify_mock.assert_not_called()


def test_morning_briefing_sends_at_correct_time():
    stop_event = MagicMock()
    stop_event.wait.side_effect = [False, True]

    class FakeDateTime:
        @classmethod
        def now(cls):
            return datetime(2026, 3, 4, 9, 5, 0)

        @classmethod
        def utcnow(cls):
            return datetime(2026, 3, 4, 9, 5, 0)

    with patch("core.watchers.morning_briefing.datetime", FakeDateTime):
        with patch("core.watchers.morning_briefing.known_user_ids", return_value=["123"]):
            with patch("core.watchers.morning_briefing._start_hour_for_user", return_value=9):
                with patch("core.watchers.morning_briefing._build_briefing", return_value="briefing"):
                    with patch("core.watchers.morning_briefing.notify", return_value=True) as notify_mock:
                        morning_briefing.run_morning_briefing_watcher(stop_event=stop_event)

    notify_mock.assert_called_once_with("123", "briefing", "briefing", "medium")


def test_morning_briefing_uses_behavior_tracker_pattern_if_available():
    patterns = [SimpleNamespace(trigger="time:monday@08:00")]
    with patch("core.watchers.morning_briefing.get_active_patterns", return_value=patterns):
        assert morning_briefing._start_hour_for_user("123") == 8


def test_morning_briefing_falls_back_to_nine_am_default():
    with patch("core.watchers.morning_briefing.get_active_patterns", return_value=[]):
        assert morning_briefing._start_hour_for_user("123") == 9
