"""Smoke tests for core.orchestrator routing logic."""

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
