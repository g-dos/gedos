"""Smoke tests for core.orchestrator routing logic."""

import core.behavior_tracker as behavior_tracker

from core.orchestrator import _route_task, run_task


def test_route_terminal():
    assert _route_task("ls -la") == "terminal"
    assert _route_task("git status") == "terminal"
    assert _route_task("echo hello") == "terminal"


def test_route_web():
    assert _route_task("navigate to google.com") == "web"
    assert _route_task("open https://github.com") == "web"
    assert _route_task("search python") == "web"


def test_route_gui():
    assert _route_task("click the button OK") == "gui"
    assert _route_task("click on Cancel") == "gui"


def test_route_llm():
    assert _route_task("what is Python") == "llm"
    assert _route_task("explain recursion") == "llm"
    assert _route_task("/ask what is recursion") == "llm"


def test_run_task_terminal():
    result = run_task("echo smoke_test")
    assert result["success"] is True
    assert result["agent_used"] == "terminal"
    assert "smoke_test" in result["result"]


def test_run_task_observes_successful_task(monkeypatch):
    calls = []
    monkeypatch.setattr("core.task_planner._is_multi_step_task", lambda task: False)
    monkeypatch.setattr("core.orchestrator.run_single_step_task", lambda task, language=None: {"success": True, "result": "ok", "agent_used": "terminal"})
    monkeypatch.setattr(behavior_tracker, "start_background_tracker", lambda: None)
    monkeypatch.setattr(behavior_tracker, "observe", lambda task, user_id, context: calls.append((task, user_id, context)))

    result = run_task("echo learned", user_id="123", context={"current_app": "Terminal"})

    assert result["success"] is True
    assert calls == [("echo learned", "123", {"current_app": "Terminal"})]
