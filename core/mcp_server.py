"""
GEDOS MCP server — exposes local Mac capabilities as MCP tools.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from typing import Optional

from agents.terminal_agent import run_shell
from agents.web_agent import get_page_content, navigate
from core.config import load_config
from core.llm import complete
from core.memory import add_task as memory_add_task
from core.memory import get_recent_tasks
from core.memory import init_db as memory_init_db
from core.security import SecurityError, sanitize_command, sanitize_url
from tools.ax_tree import get_ax_tree

logger = logging.getLogger(__name__)


def _ensure_mcp_sdk():
    """Import the MCP SDK only when MCP mode is requested."""
    if sys.version_info < (3, 10):
        raise RuntimeError(
            "MCP mode requires Python 3.10+ because the mcp SDK does not support "
            f"Python {sys.version_info.major}.{sys.version_info.minor}."
        )
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError(
            "MCP SDK not installed. Install with 'pip install mcp' using a Python 3.10+ interpreter."
        ) from exc
    return FastMCP


def _server_version() -> str:
    """Read the configured Gedos version."""
    config = load_config()
    return str(config.get("version") or "0.0.0")


def _record_task(description: str, success: bool, agent_used: str, result: str) -> None:
    """Persist MCP-executed tasks into the shared memory layer."""
    try:
        memory_add_task(
            description=description,
            status="completed" if success else "failed",
            agent_used=agent_used,
            result=result[:1000],
        )
    except Exception:
        logger.exception("Failed to record MCP task")


def _format_terminal_output(command: str, success: bool, stdout: str, stderr: str) -> str:
    """Format terminal output for MCP responses."""
    out = (stdout or "").strip()
    err = (stderr or "").strip()
    parts = [f"$ {command}"]
    if out:
        parts.append(out)
    if err:
        parts.append(f"stderr:\n{err}")
    if not out and not err:
        parts.append("(no output)")
    if not success:
        parts.append("status: failed")
    return "\n\n".join(parts)


def _format_screen_tree() -> str:
    """Return the current AX tree as structured text."""
    tree = get_ax_tree(max_buttons=25, max_text_fields=10)
    return json.dumps(tree, indent=2, ensure_ascii=True)


def create_mcp_server():
    """Create the Gedos MCP server and register tools."""
    FastMCP = _ensure_mcp_sdk()
    version = _server_version()
    server = FastMCP(
        name="gedos",
        instructions=(
            f"Gedos MCP server v{version}. Use these tools to operate the local Mac "
            "through terminal, apps, browser, AX tree, local LLM, and task history."
        ),
    )
    if hasattr(server, "_mcp_server"):
        server._mcp_server.version = version

    @server.tool(
        name="run_terminal_command",
        description="Execute a shell command on the local Mac and return stdout and stderr.",
    )
    def run_terminal_command(command: str) -> str:
        is_safe, reason = sanitize_command(command)
        if not is_safe:
            result_text = f"Command blocked by safety checks: {reason}"
            _record_task(f"[mcp] terminal: {command}", False, "mcp-terminal", result_text)
            return result_text
        safe_command = command.strip()
        try:
            result = run_shell(safe_command)
        except SecurityError as exc:
            result_text = f"Command blocked by safety checks: {exc}"
            _record_task(f"[mcp] terminal: {safe_command}", False, "mcp-terminal", result_text)
            return result_text
        result_text = _format_terminal_output(
            safe_command,
            result.success,
            result.stdout,
            result.stderr,
        )
        _record_task(f"[mcp] terminal: {safe_command}", result.success, "mcp-terminal", result_text)
        return result_text

    @server.tool(
        name="open_application",
        description="Open a macOS application by its visible app name using the open -a command.",
    )
    def open_application(app_name: str) -> str:
        clean_name = app_name.strip()
        if not clean_name:
            result_text = "Application name is required."
            _record_task("[mcp] open app", False, "mcp-gui", result_text)
            return result_text
        try:
            subprocess.run(
                ["open", "-a", clean_name],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
            result_text = f"Opened application: {clean_name}"
            _record_task(f"[mcp] open app: {clean_name}", True, "mcp-gui", result_text)
            return result_text
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or str(exc)).strip()
            result_text = f"Failed to open application '{clean_name}': {stderr}"
            _record_task(f"[mcp] open app: {clean_name}", False, "mcp-gui", result_text)
            return result_text
        except Exception as exc:
            result_text = f"Failed to open application '{clean_name}': {exc}"
            _record_task(f"[mcp] open app: {clean_name}", False, "mcp-gui", result_text)
            return result_text

    @server.tool(
        name="browse_web",
        description="Open a URL in the browser automation agent and return a page summary.",
    )
    def browse_web(url: str) -> str:
        safe_url = sanitize_url(url)
        if not safe_url:
            result_text = "URL blocked by safety checks."
            _record_task(f"[mcp] web: {url}", False, "mcp-web", result_text)
            return result_text

        nav = navigate(safe_url)
        if not nav.success:
            result_text = f"Failed to load {safe_url}: {nav.message}"
            _record_task(f"[mcp] web: {safe_url}", False, "mcp-web", result_text)
            return result_text

        content = get_page_content(max_chars=4000)
        if not content.success:
            result_text = f"Loaded {nav.url or safe_url}, but could not read page content: {content.message}"
            _record_task(f"[mcp] web: {safe_url}", False, "mcp-web", result_text)
            return result_text

        parts = [
            f"Title: {content.title or nav.title or '(unknown)'}",
            f"URL: {content.url or nav.url or safe_url}",
            "Content:",
            content.content_preview or nav.content_preview or "(no content)",
        ]
        result_text = "\n".join(parts)
        _record_task(f"[mcp] web: {safe_url}", True, "mcp-web", result_text)
        return result_text

    @server.tool(
        name="read_screen",
        description="Read the current macOS accessibility tree and return structured screen state.",
    )
    def read_screen() -> str:
        result_text = _format_screen_tree()
        success = '"error": null' in result_text
        _record_task("[mcp] read screen", success, "mcp-ax", result_text)
        return result_text

    @server.tool(
        name="ask_llm",
        description="Send a question to the configured local or cloud LLM and return the response text.",
    )
    def ask_llm(question: str) -> str:
        clean_question = question.strip()
        if not clean_question:
            result_text = "Question is required."
            _record_task("[mcp] ask llm", False, "mcp-llm", result_text)
            return result_text
        result_text = complete(clean_question, max_tokens=1024)
        _record_task(f"[mcp] ask llm: {clean_question[:120]}", True, "mcp-llm", result_text)
        return result_text

    @server.tool(
        name="get_task_history",
        description="Return recent Gedos task history from the shared memory database.",
    )
    def get_task_history() -> str:
        tasks = get_recent_tasks(limit=10)
        if not tasks:
            return "No task history available."
        lines = []
        for task in tasks:
            result_preview = (task.result or "").strip().replace("\n", " ")
            if len(result_preview) > 120:
                result_preview = result_preview[:120] + "..."
            lines.append(
                f"- [{task.status}] {task.description[:80]} | agent={task.agent_used or 'unknown'} | result={result_preview or '(none)'}"
            )
        return "\n".join(lines)

    return server


def run_mcp_server() -> None:
    """Start the Gedos MCP server on stdio transport."""
    memory_init_db()
    server = create_mcp_server()
    logger.info("Starting Gedos MCP server over stdio")
    server.run(transport="stdio")
