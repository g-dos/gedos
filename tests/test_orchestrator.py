"""Smoke tests for core.orchestrator routing logic."""

from core.orchestrator import _route_task, run_task


def test_route_terminal():
    assert _route_task("ls -la") == "terminal"
    assert _route_task("git status") == "terminal"
    assert _route_task("echo hello") == "terminal"


def test_route_web():
    assert _route_task("navegar para google.com") == "web"
    assert _route_task("abrir https://github.com") == "web"
    assert _route_task("buscar no google python") == "web"


def test_route_gui():
    assert _route_task("clicar no botão OK") == "gui"
    assert _route_task("click no botao Cancel") == "gui"


def test_route_llm():
    assert _route_task("perguntar o que é Python") == "llm"
    assert _route_task("explique recursão") == "llm"
    assert _route_task("/ask o que é recursão") == "llm"


def test_run_task_terminal():
    result = run_task("echo smoke_test")
    assert result["success"] is True
    assert result["agent_used"] == "terminal"
    assert "smoke_test" in result["result"]
