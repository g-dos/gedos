"""
GEDOS Orchestrator — LangGraph task planning and routing to Terminal, GUI, Web agents.
"""

import logging
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

AgentKind = Literal["terminal", "gui", "web", "llm"]


def _route_task(task: str) -> AgentKind:
    """Decide which agent should handle the task (heuristic)."""
    low = task.lower().strip()
    
    # Priority: GUI commands that mention specific apps (safari, chrome, firefox, etc.)
    if any(app in low for app in ("safari", "chrome", "firefox", "edge")) and any(cmd in low for cmd in ("open", "abrir", "launch")):
        return "gui"
    
    if any(low.startswith(p) for p in ("navegar", "navigate", "buscar no google", "search ")) or ("http" in low and "open" not in low) or (".com" in low and "open" not in low):
        return "web"
    if any(k in low for k in ("clicar", "click", "botão", "botao", "button")):
        return "gui"
    if any(k in low for k in ("perguntar", "ask", "o que é", "o que e", "what is", "explique", "explain", "resuma", "summarize")) or low.startswith("/ask"):
        return "llm"
    return "terminal"


def _run_terminal(task: str) -> dict[str, Any]:
    """Execute task via terminal agent (lazy import)."""
    from agents.terminal_agent import run_shell, TerminalResult

    r = run_shell(task)
    out = (r.stdout or "").strip() or "(no output)"
    err = (r.stderr or "").strip()
    if len(out) > 3000:
        out = out[:3000] + "\n... (truncated)"
    msg = out
    if err:
        msg += f"\n\nstderr:\n{err[:300]}"
    return {"success": r.success, "result": msg, "agent_used": "terminal"}


def _run_gui(task: str) -> dict[str, Any]:
    """Execute task via GUI agent (lazy import)."""
    from agents.gui_agent import click_button, get_screen_summary
    import subprocess
    import time
    import re

    low = task.lower()
    
    # Handle compound commands like "open safari and go to github.com"
    if any(app in low for app in ("safari", "chrome", "firefox", "edge")) and ("go to" in low or "navigate to" in low):
        # Extract app name
        app_name = None
        for app in ("safari", "chrome", "firefox", "edge"):
            if app in low:
                app_name = app.capitalize()
                break
        
        # Extract URL
        url = None
        url_pattern = r'([a-zA-Z0-9-]+\.(?:com|org|net|edu|gov|io|co|br|uk|de|fr)[/\w\-\.]*)'
        url_match = re.search(url_pattern, task)
        if url_match:
            url = url_match.group(1)
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
        
        if app_name and url:
            try:
                # Open the app
                subprocess.run(["open", "-a", app_name], check=True)
                time.sleep(2)  # Wait for app to open
                
                # Open URL in the app
                subprocess.run(["open", url], check=True)
                
                return {
                    "success": True, 
                    "result": f"Opened {app_name} and navigated to {url}", 
                    "agent_used": "gui"
                }
            except subprocess.CalledProcessError as e:
                return {
                    "success": False,
                    "result": f"Failed to open {app_name}: {str(e)}",
                    "agent_used": "gui"
                }
    
    # Handle simple app opening like "open safari"
    for app in ("safari", "chrome", "firefox", "edge", "finder", "terminal", "vscode", "code"):
        if f"open {app}" in low or f"abrir {app}" in low:
            app_map = {
                "safari": "Safari",
                "chrome": "Google Chrome", 
                "firefox": "Firefox",
                "edge": "Microsoft Edge",
                "finder": "Finder",
                "terminal": "Terminal",
                "vscode": "Visual Studio Code",
                "code": "Visual Studio Code"
            }
            app_name = app_map.get(app, app.capitalize())
            try:
                subprocess.run(["open", "-a", app_name], check=True)
                return {
                    "success": True,
                    "result": f"Opened {app_name}",
                    "agent_used": "gui"
                }
            except subprocess.CalledProcessError as e:
                return {
                    "success": False,
                    "result": f"Failed to open {app_name}: {str(e)}",
                    "agent_used": "gui"
                }

    # Original button clicking logic
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
    
    # Fallback: show screen summary
    summary = get_screen_summary()
    err = summary.get("error")
    if err:
        return {"success": False, "result": err, "agent_used": "gui"}
    app = summary.get("app") or "?"
    btns = summary.get("buttons") or []
    lines = [f"App: {app}", "Buttons: " + ", ".join((b.get("title") or b.get("role") or "?") for b in btns[:15])]
    return {"success": True, "result": "\n".join(lines), "agent_used": "gui"}


def _run_web(task: str) -> dict[str, Any]:
    """Execute task via web agent (lazy import)."""
    from agents.web_agent import navigate, search_google, WebResult

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
    
    # Extract URL from task - handle complex commands like "open safari and go to github.com"
    url = task.strip()
    for p in ("navegar para ", "navigate to ", "abrir ", "open "):
        if p in low:
            after_prefix = low.split(p, 1)[-1].strip()
            # Look for URL patterns in the text after prefix
            import re
            # Find URLs: domain.com, domain.org, domain.net, etc.
            url_pattern = r'([a-zA-Z0-9-]+\.(?:com|org|net|edu|gov|io|co|br|uk|de|fr)[/\w\-\.]*)'
            url_match = re.search(url_pattern, after_prefix)
            if url_match:
                url = url_match.group(1)
            else:
                # Fallback: use everything after prefix
                url = after_prefix
            break
    
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    r = navigate(url)
    return _web_result_to_dict(r)


def _web_result_to_dict(r) -> dict[str, Any]:
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
    """Execute task via LLM (lazy import)."""
    from core.llm import complete as llm_complete

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
