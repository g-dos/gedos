"""
GEDOS Orchestrator — LangGraph task planning and routing to Terminal, GUI, Web agents.
Supports both single-step and multi-step task execution.
"""

import asyncio
import logging
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)

AgentKind = Literal["terminal", "gui", "web", "llm"]
_STOP_EVENT: Optional[asyncio.Event] = None


def _get_stop_event() -> asyncio.Event:
    """Return the shared stop event."""
    global _STOP_EVENT
    if _STOP_EVENT is None:
        _STOP_EVENT = asyncio.Event()
    return _STOP_EVENT


def request_stop() -> None:
    """Signal an immediate stop request."""
    _get_stop_event().set()


def clear_stop() -> None:
    """Reset the stop signal after handling it."""
    _get_stop_event().clear()


def is_stop_requested() -> bool:
    """Return whether a stop was requested."""
    return _get_stop_event().is_set()


def _route_task(task: str) -> AgentKind:
    """Decide which agent should handle the task (heuristic)."""
    low = task.lower().strip()
    
    # Priority: GUI commands that mention specific apps (safari, chrome, firefox, etc.)
    if any(app in low for app in ("safari", "chrome", "firefox", "edge")) and any(cmd in low for cmd in ("open", "abrir", "launch")):
        return "gui"

    if low.startswith("open http://") or low.startswith("open https://"):
        return "web"
    
    if any(low.startswith(p) for p in ("navegar", "navigate", "buscar no google", "search ")) or ("http" in low and "open" not in low) or (".com" in low and "open" not in low):
        return "web"
    if any(k in low for k in ("clicar", "click", "botão", "botao", "button")):
        return "gui"
    if any(k in low for k in ("perguntar", "ask", "o que é", "o que e", "what is", "explique", "explain", "resuma", "summarize")) or low.startswith("/ask"):
        return "llm"
    return "terminal"


def _run_terminal(task: str) -> dict[str, Any]:
    """Execute task via terminal agent (lazy import)."""
    if is_stop_requested():
        return {"success": False, "result": "Stopped.", "agent_used": "terminal"}
    from agents.terminal_agent import run_shell
    from core.security import SecurityError

    try:
        r = run_shell(task)
    except SecurityError as exc:
        return {"success": False, "result": str(exc), "agent_used": "terminal"}
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
    if is_stop_requested():
        return {"success": False, "result": "Stopped.", "agent_used": "gui"}
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
    if is_stop_requested():
        return {"success": False, "result": "Stopped.", "agent_used": "web"}
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


def _run_llm(task: str, language: Optional[str] = None) -> dict[str, Any]:
    """Execute task via LLM (lazy import)."""
    if is_stop_requested():
        return {"success": False, "result": "Stopped.", "agent_used": "llm"}
    from core.llm import complete as llm_complete

    reply = llm_complete(task, max_tokens=1024, language=language)
    return {"success": True, "result": reply, "agent_used": "llm"}


def _execute_single_step(agent: AgentKind, action: str, step_obj=None, language: Optional[str] = None) -> dict[str, Any]:
    """Execute a single step with the specified agent."""
    if is_stop_requested():
        return {"success": False, "result": "Stopped.", "agent_used": agent}
    logger.info("Executing step with %s: %s", agent, action[:80])

    # Try using the new execute_step method if step_obj is provided
    if step_obj:
        try:
            if agent == "terminal":
                from agents.terminal_agent import execute_step
                return execute_step(step_obj)
            elif agent == "gui":
                from agents.gui_agent import execute_step
                return execute_step(step_obj)
            elif agent == "web":
                from agents.web_agent import execute_step
                return execute_step(step_obj)
            elif agent == "llm":
                return _run_llm(action, language=language)
        except Exception as e:
            logger.warning("Step-specific execution failed, falling back to legacy: %s", e)

    # Fallback to legacy execution
    for attempt in range(2):
        try:
            if agent == "terminal":
                return _run_terminal(action)
            if agent == "gui":
                return _run_gui(action)
            if agent == "web":
                return _run_web(action)
            if agent == "llm":
                return _run_llm(action, language=language)
        except Exception as e:
            logger.warning("Step execution attempt %s failed: %s", attempt + 1, e)
            if attempt == 1:
                logger.exception("Step execution failed")
                return {"success": False, "result": str(e)[:500], "agent_used": agent}
    return {"success": False, "result": "Unknown agent.", "agent_used": "none"}


def _run_multi_step_task(task: str, language: Optional[str] = None) -> dict[str, Any]:
    """
    Execute a multi-step task using the task planner.
    """
    try:
        from core.task_planner import plan_task

        if is_stop_requested():
            return {"success": False, "result": "Stopped.", "agent_used": "orchestrator"}
        plan = plan_task(task, language=language)

        if not plan.is_multi_step or not plan.steps:
            return run_single_step_task(task, language=language)

        logger.info(f"Executing multi-step plan with {len(plan.steps)} steps")

        results = []
        overall_success = True
        agents_used = []

        for i, step in enumerate(plan.steps):
            step_num = i + 1
            logger.info(f"Step {step_num}/{len(plan.steps)}: {step.agent} - {step.action[:80]}")

            result = _execute_single_step(step.agent, step.action, step_obj=step, language=language)
            results.append(f"Step {step_num}: {result['result']}")
            agents_used.append(result.get('agent_used', step.agent))
            
            if not result.get('success', False):
                logger.warning(f"Step {step_num} failed: {result.get('result', 'Unknown error')}")
                overall_success = False
                # Continue with remaining steps even if one fails
        
        # Combine all results
        combined_result = "\n\n".join(results)
        agents_summary = ", ".join(set(agents_used))
        
        return {
            "success": overall_success,
            "result": combined_result,
            "agent_used": f"multi-step ({agents_summary})",
            "steps_completed": len(results)
        }
        
    except Exception as e:
        logger.exception("Multi-step execution failed")
        return {"success": False, "result": f"Multi-step planning error: {str(e)[:500]}", "agent_used": "planner"}


def run_single_step_task(task: str, language: Optional[str] = None) -> dict[str, Any]:
    """
    Route and execute a single-step task. Returns dict with success, result, agent_used.
    """
    agent = _route_task(task)
    return _execute_single_step(agent, task, language=language)


def run_task(task: str, language: Optional[str] = None) -> dict[str, Any]:
    """
    Route and execute a task (single or multi-step). Returns dict with success, result, agent_used.
    """
    clear_stop()
    try:
        from core.task_planner import _is_multi_step_task
        
        if _is_multi_step_task(task):
            logger.info("Detected multi-step task: %s", task[:80])
            return _run_multi_step_task(task, language=language)
        else:
            logger.info("Executing single-step task: %s", task[:80])
            return run_single_step_task(task, language=language)

    except ImportError:
        logger.warning("Task planner not available, using single-step execution")
        return run_single_step_task(task, language=language)
    except Exception as e:
        logger.exception("Task routing failed")
        return {"success": False, "result": f"Task routing error: {str(e)[:500]}", "agent_used": "orchestrator"}


def run_task_with_langgraph(task: str, language: Optional[str] = None) -> dict[str, Any]:
    """
    Run task through a LangGraph workflow with multi-step support.
    State flows: task -> plan -> execute -> result.
    """
    clear_stop()
    try:
        from typing import TypedDict
        from langgraph.graph import StateGraph, START, END
        from core.task_planner import _is_multi_step_task

        class State(TypedDict):
            task: str
            result: str
            agent_used: str
            success: bool
            is_multi_step: bool

        def plan_task_node(state: State) -> State:
            """Determine if task is multi-step and set planning flag."""
            is_multi_step = _is_multi_step_task(state["task"])
            return {"is_multi_step": is_multi_step}

        def execute_task_node(state: State) -> State:
            """Execute task using appropriate method (single or multi-step)."""
            if state.get("is_multi_step", False):
                out = _run_multi_step_task(state["task"], language=language)
            else:
                out = run_single_step_task(state["task"], language=language)
            
            return {
                "success": out["success"], 
                "result": out.get("result") or "", 
                "agent_used": out.get("agent_used") or "unknown"
            }

        graph = StateGraph(State)
        graph.add_node("plan", plan_task_node)
        graph.add_node("execute", execute_task_node)
        graph.add_edge(START, "plan")
        graph.add_edge("plan", "execute")
        graph.add_edge("execute", END)
        compiled = graph.compile()
        
        initial: State = {
            "task": task, 
            "result": "", 
            "agent_used": "", 
            "success": False,
            "is_multi_step": False
        }
        final = compiled.invoke(initial)
        
        return {
            "success": final["success"], 
            "result": final["result"], 
            "agent_used": final["agent_used"]
        }
    except ImportError:
        return run_task(task, language=language)
    except Exception as e:
        logger.exception("LangGraph run failed: %s", e)
        return run_task(task, language=language)
