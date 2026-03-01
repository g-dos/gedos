"""
Integration tests — test_orchestrator_routing.py
Verifies that Orchestrator routes tasks to the correct agent.
"""

import pytest
from core.orchestrator import _route_task, run_task_with_langgraph


def test_route_to_terminal():
    """Test terminal commands are routed to Terminal Agent."""
    assert _route_task("ls -la") == "terminal"
    assert _route_task("git status") == "terminal"
    assert _route_task("python --version") == "terminal"


def test_route_to_gui():
    """Test GUI tasks are routed to GUI Agent."""
    assert _route_task("click OK") == "gui"
    assert _route_task("click the button Save") == "gui"
    assert _route_task("clicar no botão Cancel") == "gui"


def test_route_to_web():
    """Test web tasks are routed to Web Agent."""
    assert _route_task("navigate to google.com") == "web"
    assert _route_task("open https://github.com") == "web"
    assert _route_task("search Python documentation") == "web"


def test_route_to_llm():
    """Test questions are routed to LLM Agent."""
    assert _route_task("/ask what is Python?") == "llm"
    assert _route_task("what is recursion") == "llm"
    assert _route_task("explain machine learning") == "llm"


def test_langgraph_terminal_execution():
    """Test full LangGraph execution for a terminal task."""
    result = run_task_with_langgraph("echo test")
    
    assert result["success"] is True or result.get("result") is not None
    assert result.get("agent_used") == "terminal"


def test_langgraph_llm_execution():
    """Test full LangGraph execution for an LLM task."""
    result = run_task_with_langgraph("/ask what is 2+2")
    
    assert result.get("agent_used") == "llm"
    assert result.get("result") is not None
