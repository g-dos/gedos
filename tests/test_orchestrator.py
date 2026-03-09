"""Tests for core.orchestrator routing and execution logic."""

import sys
import types

import pytest

import core.behavior_tracker as behavior_tracker
import core.orchestrator as orchestrator
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
    monkeypatch.setattr(
        "core.orchestrator.run_single_step_task",
        lambda task, language=None, **kwargs: {"success": True, "result": "ok", "agent_used": "terminal"},
    )
    monkeypatch.setattr(behavior_tracker, "start_background_tracker", lambda: None)
    monkeypatch.setattr(behavior_tracker, "observe", lambda task, user_id, context: calls.append((task, user_id, context)))

    result = run_task("echo learned", user_id="123", context={"current_app": "Terminal"})

    assert result["success"] is True
    assert calls == [("echo learned", "123", {"current_app": "Terminal"})]


def test_run_terminal_returns_command_output(monkeypatch):
    class _Result:
        success = True
        stdout = "ok-output"
        stderr = ""

    terminal_mod = types.ModuleType("agents.terminal_agent")
    terminal_mod.run_shell = lambda task, **kwargs: _Result()
    monkeypatch.setitem(sys.modules, "agents.terminal_agent", terminal_mod)

    security_mod = types.ModuleType("core.security")

    class SecurityError(Exception):
        pass

    security_mod.SecurityError = SecurityError
    monkeypatch.setitem(sys.modules, "core.security", security_mod)

    out = orchestrator._run_terminal("echo ok")
    assert out["success"] is True
    assert out["agent_used"] == "terminal"
    assert "ok-output" in out["result"]


def test_run_gui_uses_gui_agent_click_path(monkeypatch):
    gui_mod = types.ModuleType("agents.gui_agent")
    gui_mod.click_button = lambda name, **kwargs: True
    gui_mod.get_screen_summary = lambda **kwargs: {"app": "Finder", "buttons": []}
    monkeypatch.setitem(sys.modules, "agents.gui_agent", gui_mod)

    out = orchestrator._run_gui("click ok")
    assert out["success"] is True
    assert out["agent_used"] == "gui"
    assert "Clicked the button." in out["result"]


def test_run_web_uses_web_agent_navigate(monkeypatch):
    class _WebResult:
        def __init__(self):
            self.success = True
            self.message = "navigated"
            self.title = "Example"
            self.url = "https://example.com"
            self.content_preview = "preview"

    web_mod = types.ModuleType("agents.web_agent")
    web_mod.navigate = lambda url, **kwargs: _WebResult()
    web_mod.search_google = lambda query, **kwargs: _WebResult()
    web_mod.WebResult = _WebResult
    monkeypatch.setitem(sys.modules, "agents.web_agent", web_mod)
    monkeypatch.setattr(orchestrator, "SCRAPLING_AVAILABLE", False)

    out = orchestrator._run_web("open https://example.com")
    assert out["success"] is True
    assert out["agent_used"] == "web"
    assert "Title: Example" in out["result"]


def test_run_llm_returns_reply_with_semantic_context(monkeypatch):
    llm_mod = types.ModuleType("core.llm")
    llm_mod.complete = lambda prompt, max_tokens=1024, language=None, **kwargs: f"reply::{prompt}"
    monkeypatch.setitem(sys.modules, "core.llm", llm_mod)

    class _Semantic:
        def get_relevant_context(self, task):
            return "previous result"

    out = orchestrator._run_llm("what is this", language="en", semantic_memory=_Semantic())
    assert out["success"] is True
    assert out["agent_used"] == "llm"
    assert "reply::Relevant context:" in out["result"]


def test_route_task_keyword_matrix():
    assert _route_task("open safari") == "gui"
    assert _route_task("open https://example.com") == "web"
    assert _route_task("navigate to example.com") == "web"
    assert _route_task("click the save button") == "gui"
    assert _route_task("/ask explain recursion") == "llm"
    assert _route_task("pwd") == "terminal"


def test_run_multi_step_task_executes_all_steps(monkeypatch):
    from core.task_planner import TaskPlan, TaskStep

    monkeypatch.setattr(
        "core.task_planner.plan_task",
        lambda task, language=None, **kwargs: TaskPlan(
            original_task=task,
            steps=[
                TaskStep(agent="terminal", action="echo step1"),
                TaskStep(agent="web", action="open https://example.com"),
            ],
            is_multi_step=True,
        ),
    )
    monkeypatch.setattr(
        orchestrator,
        "_execute_single_step",
        lambda agent, action, step_obj=None, language=None, semantic_memory=None, **kwargs: {
            "success": True,
            "result": f"{agent}:{action}",
            "agent_used": agent,
        },
    )

    out = orchestrator._run_multi_step_task("do two steps")
    assert out["success"] is True
    assert out["steps_completed"] == 2
    assert "Step 1:" in out["result"]
    assert "Step 2:" in out["result"]
    assert out["agent_used"].startswith("multi-step")


def test_run_multi_step_task_graceful_on_step_failure(monkeypatch):
    from core.task_planner import TaskPlan, TaskStep

    monkeypatch.setattr(
        "core.task_planner.plan_task",
        lambda task, language=None, **kwargs: TaskPlan(
            original_task=task,
            steps=[
                TaskStep(agent="terminal", action="ok"),
                TaskStep(agent="terminal", action="fail"),
            ],
            is_multi_step=True,
        ),
    )

    def _exec(agent, action, step_obj=None, language=None, semantic_memory=None, **kwargs):
        if action == "fail":
            return {"success": False, "result": "boom", "agent_used": "terminal"}
        return {"success": True, "result": "ok", "agent_used": "terminal"}

    monkeypatch.setattr(orchestrator, "_execute_single_step", _exec)

    out = orchestrator._run_multi_step_task("do steps")
    assert out["success"] is False
    assert out["steps_completed"] == 2
    assert "boom" in out["result"]


def test_run_multi_step_task_returns_error_on_planner_exception(monkeypatch):
    def _boom(task, language=None, **kwargs):
        raise RuntimeError("planner broke")

    monkeypatch.setattr("core.task_planner.plan_task", _boom)
    out = orchestrator._run_multi_step_task("do stuff")
    assert out["success"] is False
    assert out["agent_used"] == "planner"
    assert "Multi-step planning error:" in out["result"]


def test_run_task_handles_import_error_fallback(monkeypatch):
    monkeypatch.setattr(orchestrator, "SEMANTIC_MEMORY_AVAILABLE", False)
    monkeypatch.setattr(orchestrator, "_observe_completed_task", lambda *args, **kwargs: [])

    def _raise_import(task):
        raise ImportError("planner missing")

    monkeypatch.setattr("core.task_planner._is_multi_step_task", _raise_import)
    monkeypatch.setattr(
        orchestrator,
        "_run_single_step_with_optional_semantic",
        lambda task, language=None, semantic_memory=None, **kwargs: {
            "success": True,
            "result": "fallback single",
            "agent_used": "terminal",
        },
    )

    out = orchestrator.run_task("echo x", user_id="1")
    assert out["success"] is True
    assert out["result"] == "fallback single"
    assert out["new_patterns"] == []


def test_run_task_returns_orchestrator_error_on_unexpected_exception(monkeypatch):
    monkeypatch.setattr(orchestrator, "SEMANTIC_MEMORY_AVAILABLE", False)
    monkeypatch.setattr(
        "core.task_planner._is_multi_step_task",
        lambda task, **kwargs: (_ for _ in ()).throw(RuntimeError("bad route")),
    )
    out = orchestrator.run_task("echo x")
    assert out["success"] is False
    assert out["agent_used"] == "orchestrator"
    assert "Task routing error:" in out["result"]


def test_request_and_clear_stop_event():
    orchestrator.clear_stop()
    assert orchestrator.is_stop_requested() is False
    orchestrator.request_stop()
    assert orchestrator.is_stop_requested() is True
    orchestrator.clear_stop()
    assert orchestrator.is_stop_requested() is False


def test_run_terminal_security_error(monkeypatch):
    security_mod = types.ModuleType("core.security")

    class SecurityError(Exception):
        pass

    security_mod.SecurityError = SecurityError
    monkeypatch.setitem(sys.modules, "core.security", security_mod)

    terminal_mod = types.ModuleType("agents.terminal_agent")
    terminal_mod.run_shell = lambda task, **kwargs: (_ for _ in ()).throw(SecurityError("blocked"))
    monkeypatch.setitem(sys.modules, "agents.terminal_agent", terminal_mod)

    out = orchestrator._run_terminal("rm -rf /")
    assert out["success"] is False
    assert out["result"] == "blocked"


def test_run_gui_compound_open_and_navigate(monkeypatch):
    gui_mod = types.ModuleType("agents.gui_agent")
    gui_mod.click_button = lambda name, **kwargs: False
    gui_mod.get_screen_summary = lambda **kwargs: {"app": "Safari", "buttons": []}
    monkeypatch.setitem(sys.modules, "agents.gui_agent", gui_mod)

    calls = []

    def _fake_run(cmd, check=True, **kwargs):
        calls.append(cmd)
        return object()

    monkeypatch.setattr("subprocess.run", _fake_run)
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    out = orchestrator._run_gui("open safari and go to github.com")
    assert out["success"] is True
    assert "Opened Safari and navigated to https://github.com" in out["result"]
    assert calls[0] == ["open", "-a", "Safari"]
    assert calls[1] == ["open", "https://github.com"]


def test_run_web_search_branch(monkeypatch):
    class _WebResult:
        success = True
        message = "results"
        title = ""
        url = ""
        content_preview = ""

    queries = []
    web_mod = types.ModuleType("agents.web_agent")
    web_mod.navigate = lambda url, **kwargs: _WebResult()
    web_mod.search_google = lambda query, **kwargs: (queries.append(query) or _WebResult())
    web_mod.WebResult = _WebResult
    monkeypatch.setitem(sys.modules, "agents.web_agent", web_mod)

    out = orchestrator._run_web("search retry decorator")
    assert out["success"] is True
    assert queries == ["retry decorator"]


def test_run_web_scrapling_branch(monkeypatch):
    class _WebResult:
        success = True
        message = "unused"
        title = ""
        url = ""
        content_preview = ""

    web_mod = types.ModuleType("agents.web_agent")
    web_mod.navigate = lambda url, **kwargs: _WebResult()
    web_mod.search_google = lambda query, **kwargs: _WebResult()
    web_mod.WebResult = _WebResult
    monkeypatch.setitem(sys.modules, "agents.web_agent", web_mod)

    monkeypatch.setattr(orchestrator, "SCRAPLING_AVAILABLE", True)
    monkeypatch.setattr(orchestrator, "scrape", lambda url, **kwargs: "scraped content")

    out = orchestrator._run_web("scrape example.com")
    assert out["success"] is True
    assert out["result"] == "scraped content"


def test_execute_single_step_step_obj_and_fallback_error(monkeypatch):
    terminal_mod = types.ModuleType("agents.terminal_agent")
    terminal_mod.execute_step = lambda step, **kwargs: {
        "success": True,
        "result": "step-executed",
        "agent_used": "terminal",
    }
    monkeypatch.setitem(sys.modules, "agents.terminal_agent", terminal_mod)

    step = types.SimpleNamespace(agent="terminal", action="echo ok")
    out = orchestrator._execute_single_step("terminal", "echo ok", step_obj=step)
    assert out["success"] is True
    assert out["result"] == "step-executed"

    monkeypatch.setattr(
        orchestrator,
        "_run_terminal",
        lambda action, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    err = orchestrator._execute_single_step("terminal", "echo bad")
    assert err["success"] is False
    assert "boom" in err["result"]
