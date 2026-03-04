"""Tests for the Gedos MCP server."""

from types import SimpleNamespace

import core.mcp_server as mcp_server


class FakeFastMCP:
    """Minimal FastMCP stand-in for unit tests."""

    def __init__(self, name: str, instructions: str):
        self.name = name
        self.instructions = instructions
        self.tools: dict[str, object] = {}
        self.tool_descriptions: dict[str, str] = {}
        self._mcp_server = SimpleNamespace(version=None)

    def tool(self, name: str, description: str):
        """Capture registered MCP tools."""

        def decorator(func):
            self.tools[name] = func
            self.tool_descriptions[name] = description
            return func

        return decorator


def _build_server(monkeypatch) -> FakeFastMCP:
    """Create an MCP server with the SDK replaced by a fake implementation."""
    monkeypatch.setattr(mcp_server, "_ensure_mcp_sdk", lambda: FakeFastMCP)
    monkeypatch.setattr(mcp_server, "_server_version", lambda: "0.9.4")
    return mcp_server.create_mcp_server()


def test_mcp_server_initializes_correctly(monkeypatch):
    server = _build_server(monkeypatch)

    assert server.name == "gedos"
    assert server._mcp_server.version == "0.9.4"
    assert set(server.tools) == {
        "run_terminal_command",
        "open_application",
        "browse_web",
        "read_screen",
        "ask_llm",
        "get_task_history",
    }


def test_run_terminal_command_tool_returns_output(monkeypatch):
    server = _build_server(monkeypatch)
    monkeypatch.setattr(mcp_server, "sanitize_command", lambda command: (True, "ok"))
    monkeypatch.setattr(
        mcp_server,
        "run_shell",
        lambda command: SimpleNamespace(success=True, stdout="hello\n", stderr=""),
    )
    monkeypatch.setattr(mcp_server, "_record_task", lambda *args, **kwargs: None)

    result = server.tools["run_terminal_command"]("echo hello")

    assert "$ echo hello" in result
    assert "hello" in result


def test_open_application_tool_calls_gui_open(monkeypatch):
    server = _build_server(monkeypatch)
    calls: list[tuple[object, ...]] = []

    def fake_run(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(mcp_server.subprocess, "run", fake_run)
    monkeypatch.setattr(mcp_server, "_record_task", lambda *args, **kwargs: None)

    result = server.tools["open_application"]("Visual Studio Code")

    assert result == "Opened application: Visual Studio Code"
    assert calls == [(["open", "-a", "Visual Studio Code"],)]


def test_browse_web_tool_calls_web_agent(monkeypatch):
    server = _build_server(monkeypatch)
    monkeypatch.setattr(mcp_server, "sanitize_url", lambda url: url)
    monkeypatch.setattr(
        mcp_server,
        "navigate",
        lambda url: SimpleNamespace(success=True, url=url, title="Example", content_preview="nav preview", message=""),
    )
    monkeypatch.setattr(
        mcp_server,
        "get_page_content",
        lambda max_chars=4000: SimpleNamespace(
            success=True,
            title="Example Domain",
            url="https://example.com",
            content_preview="Example page summary",
            message="",
        ),
    )
    monkeypatch.setattr(mcp_server, "_record_task", lambda *args, **kwargs: None)

    result = server.tools["browse_web"]("https://example.com")

    assert "Title: Example Domain" in result
    assert "URL: https://example.com" in result
    assert "Example page summary" in result


def test_read_screen_tool_returns_non_empty_string(monkeypatch):
    server = _build_server(monkeypatch)
    monkeypatch.setattr(
        mcp_server,
        "get_ax_tree",
        lambda max_buttons=25, max_text_fields=10: {"app": "Finder", "error": None},
    )
    monkeypatch.setattr(mcp_server, "_record_task", lambda *args, **kwargs: None)

    result = server.tools["read_screen"]()

    assert isinstance(result, str)
    assert result.strip()
    assert '"app": "Finder"' in result


def test_ask_llm_tool_calls_llm_with_mock_response(monkeypatch):
    server = _build_server(monkeypatch)
    calls: list[tuple[str, int]] = []

    def fake_complete(question: str, max_tokens: int = 0):
        calls.append((question, max_tokens))
        return "Mock LLM response"

    monkeypatch.setattr(mcp_server, "complete", fake_complete)
    monkeypatch.setattr(mcp_server, "_record_task", lambda *args, **kwargs: None)

    result = server.tools["ask_llm"]("What is Gedos?")

    assert result == "Mock LLM response"
    assert calls == [("What is Gedos?", 1024)]


def test_get_task_history_tool_returns_list_from_memory(monkeypatch):
    server = _build_server(monkeypatch)
    monkeypatch.setattr(
        mcp_server,
        "get_recent_tasks",
        lambda limit=10: [
            SimpleNamespace(
                status="completed",
                description="Run tests",
                agent_used="mcp-terminal",
                result="64 passed",
            ),
            SimpleNamespace(
                status="failed",
                description="Open missing app",
                agent_used="mcp-gui",
                result="App not found",
            ),
        ],
    )

    result = server.tools["get_task_history"]()

    assert "- [completed] Run tests | agent=mcp-terminal | result=64 passed" in result
    assert "- [failed] Open missing app | agent=mcp-gui | result=App not found" in result
