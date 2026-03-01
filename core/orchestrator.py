"""
GEDOS Orchestrator — LangGraph task planning and routing to Terminal, GUI, Web agents.
"""

import logging
from typing import Any, Literal, Optional

from agents.terminal_agent import run_shell, TerminalResult
from agents.gui_agent import click_button, get_screen_summary
from agents.web_agent import navigate, search_google, get_page_content, WebResult
from tools.ax_tree import get_ax_tree
from core.llm import complete as llm_complete

logger = logging.getLogger(__name__)

AgentKind = Literal["terminal", "gui", "web", "llm"]


def _route_task(task: str) -> AgentKind:
    """Decide which agent should handle the task (heuristic)."""
    low = task.lower().strip()
    if any(low.startswith(p) for p in ("navegar", "navigate", "abrir ", "open ", "buscar no google", "search ")) or "http" in low or ".com" in low:
        return "web"
    if any(k in low for k in ("clicar", "click", "botão", "botao", "button")):
        return "gui"
    if any(k in low for k in ("perguntar", "ask", "o que é", "o que e", "what is", "explique", "explain", "resuma", "summarize")) or low.startswith("/ask"):
        return "llm"
    return "terminal"


def _run_terminal(task: str) -> dict[str, Any]:
    """Execute task via terminal agent."""
    r = run_shell(task)
    return {"success": r.success, "result": _format_terminal(r), "agent_used": "terminal"}


def _format_terminal(r: TerminalResult) -> str:
    out = (r.stdout or "").strip() or "(no output)"
    err = (r.stderr or "").strip()
    if len(out) > 3000:
        out = out[:3000] + "\n... (truncated)"
    msg = out
    if err:
        msg += f"\n\nstderr:\n{err[:300]}"
    return msg


def _run_gui(task: str) -> dict[str, Any]:
    """Execute task via GUI agent (click button or report screen)."""
    low = task.lower()
    btn_name = None
    for prefix in ("clicar no botão ", "clicar no botao ", "click no botão ", "click no botao ",
                    "click the ", "click on ", "clicar no ", "click no ", "click "):
        if prefix in low:
            rest = low.split(prefix, 1)[-1].strip()
            btn_name = rest.split()[0] if rest else None
            break
    if not btn_name and len(task.split()) >= 2:
        btn_name = task.split()[-1].strip(".,")
    if btn_name:
        ok = click_button(btn_name)
        return {"success": ok, "result": "Clicked the button." if ok else f"Button '{btn_name}' not found.", "agent_used": "gui"}
    summary = get_screen_summary()
    err = summary.get("error")
    if err:
        return {"success": False, "result": err, "agent_used": "gui"}
    app = summary.get("app") or "?"
    btns = summary.get("buttons") or []
    lines = [f"App: {app}", "Buttons: " + ", ".join((b.get("title") or b.get("role") or "?") for b in btns[:15])]
    return {"success": True, "result": "\n".join(lines), "agent_used": "gui"}


def _run_web(task: str) -> dict[str, Any]:
    """Execute task via web agent."""
    low = task.lower()
    if "google" in low or "buscar" in low or "search" in low:
        for p in ("buscar ", "busca ", "search ", "pesquisar "):
            if p in low:
                q = low.split(p, 1)[-1].strip()
                if q:
                    r = search_google(q)
                    return _web_result_to_dict(r)
        r = search_google(task)
        return _web_result_to_dict(r)
    url = task.strip()
    for p in ("navegar para ", "navigate to ", "abrir ", "open "):
        if p in low:
            url = low.split(p, 1)[-1].strip()
            break
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    r = navigate(url)
    return _web_result_to_dict(r)


def _web_result_to_dict(r: WebResult) -> dict[str, Any]:
    if not r.success:
        return {"success": False, "result": r.message, "agent_used": "web"}
    parts = [r.message]
    if r.title:
        parts.append(f"Title: {r.title}")
    if r.url:
        parts.append(f"URL: {r.url}")
    if r.content_preview:
        preview = r.content_preview[:1500] + "..." if len(r.content_preview) > 1500 else r.content_preview
        parts.append(preview)
    return {"success": True, "result": "\n".join(parts), "agent_used": "web"}


def _run_llm(task: str) -> dict[str, Any]:
    """Execute task via LLM (answer question)."""
    reply = llm_complete(task, max_tokens=1024)
    return {"success": True, "result": reply, "agent_used": "llm"}


def run_task(task: str) -> dict[str, Any]:
    """
    Route and execute a single task. Returns dict with success, result, agent_used.
    """
    agent = _route_task(task)
    logger.info("Orchestrator routing task to %s: %s", agent, task[:80])
    for attempt in range(2):
        try:
            if agent == "terminal":
                return _run_terminal(task)
            if agent == "gui":
                return _run_gui(task)
            if agent == "web":
                return _run_web(task)
            if agent == "llm":
                return _run_llm(task)
        except Exception as e:
            logger.warning("Orchestrator attempt %s failed: %s", attempt + 1, e)
            if attempt == 1:
                logger.exception("Orchestrator execution failed")
                return {"success": False, "result": str(e)[:500], "agent_used": agent}
    return {"success": False, "result": "Unknown agent.", "agent_used": "none"}


def run_task_with_langgraph(task: str) -> dict[str, Any]:
    """
    Run task through a minimal LangGraph workflow (route -> execute).
    State flows: task -> route -> execute -> result.
    """
    try:
        from typing import TypedDict
        from langgraph.graph import StateGraph, START, END

        class State(TypedDict):
            task: str
            result: str
            agent_used: str
            success: bool

        def route(state: State) -> State:
            agent = _route_task(state["task"])
            return {"agent_used": agent}

        def execute(state: State) -> State:
            agent = state["agent_used"]
            if agent == "terminal":
                out = _run_terminal(state["task"])
            elif agent == "gui":
                out = _run_gui(state["task"])
            elif agent == "web":
                out = _run_web(state["task"])
            elif agent == "llm":
                out = _run_llm(state["task"])
            else:
                out = {"success": False, "result": "?", "agent_used": agent}
            return {"success": out["success"], "result": out.get("result") or "", "agent_used": out.get("agent_used") or agent}

        graph = StateGraph(State)
        graph.add_node("route", route)
        graph.add_node("execute", execute)
        graph.add_edge(START, "route")
        graph.add_edge("route", "execute")
        graph.add_edge("execute", END)
        compiled = graph.compile()
        initial: State = {"task": task, "result": "", "agent_used": "", "success": False}
        final = compiled.invoke(initial)
        return {"success": final["success"], "result": final["result"], "agent_used": final["agent_used"]}
    except ImportError:
        return run_task(task)
    except Exception as e:
        logger.exception("LangGraph run failed: %s", e)
        return run_task(task)
