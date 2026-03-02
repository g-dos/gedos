"""
GEDOS Task Planner — breaks complex natural language tasks into sequential steps.
Uses LLM to analyze tasks and create structured execution plans.
"""

import logging
import json
from typing import List, Dict, Any, Literal, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

AgentType = Literal["terminal", "gui", "web", "llm"]

@dataclass
class TaskStep:
    """A single step in a multi-step task plan."""
    agent: AgentType
    action: str
    expected_result: Optional[str] = None
    depends_on: Optional[int] = None  # Index of step this depends on


@dataclass
class TaskPlan:
    """Complete execution plan for a multi-step task."""
    original_task: str
    steps: List[TaskStep]
    is_multi_step: bool = True


def _is_multi_step_task(task: str) -> bool:
    """
    Heuristic to detect if a task requires multiple steps.
    Returns True if task likely needs multiple agent interactions.
    """
    low = task.lower().strip()
    
    # Explicit multi-step indicators
    multi_indicators = [
        "then", "and then", "after that", "next", "followed by",
        "create and", "open and", "write and", "run and",
        "first", "second", "finally", "lastly",
        ",", ";", "step", "steps"
    ]
    
    if any(indicator in low for indicator in multi_indicators):
        return True
    
    # Check for multiple action words
    action_words = [
        "create", "write", "open", "run", "execute", "navigate", "click", 
        "install", "build", "compile", "test", "deploy", "upload", "download"
    ]
    
    action_count = sum(1 for word in action_words if word in low)
    if action_count >= 2:
        return True
    
    # Long tasks are often multi-step
    if len(task.split()) > 8:
        return True
    
    return False


def _create_planning_prompt(task: str) -> str:
    """Create LLM prompt for task planning."""
    return f"""Break down this task into sequential steps for execution by different agents:

Task: {task}

Available agents:
- terminal: Execute shell commands, run scripts, file operations
- gui: Control macOS GUI, click buttons, open apps
- web: Browse websites, navigate URLs, web automation  
- llm: Answer questions, provide explanations, analyze text

Return a JSON array of steps. Each step must have:
- agent: one of "terminal", "gui", "web", "llm" 
- action: specific command or instruction for that agent
- expected_result: what should happen (optional)

Example format:
[
  {{"agent": "gui", "action": "open -a 'Visual Studio Code'", "expected_result": "VS Code opens"}},
  {{"agent": "terminal", "action": "touch hello.py", "expected_result": "Create empty hello.py file"}},
  {{"agent": "terminal", "action": "echo 'print(\\"Hello World\\")' > hello.py", "expected_result": "Write code to file"}},
  {{"agent": "terminal", "action": "python hello.py", "expected_result": "Run script and print Hello World"}}
]

Important rules:
- Keep steps atomic and specific
- Use actual commands that agents can execute
- Order steps logically 
- Prefer terminal commands over GUI when possible
- For file operations, use shell commands
- For app opening, use 'open -a AppName' format

Break down: {task}"""


def plan_task(task: str, language: Optional[str] = None) -> TaskPlan:
    """
    Analyze a task and create an execution plan.
    Returns TaskPlan with steps if multi-step, or single step if simple.
    """
    try:
        # Check if task needs multi-step planning
        if not _is_multi_step_task(task):
            # Single-step task - return as-is for normal routing
            return TaskPlan(
                original_task=task,
                steps=[],
                is_multi_step=False
            )
        
        # Use LLM to plan multi-step task
        from core.llm import complete as llm_complete

        prompt = _create_planning_prompt(task)
        response = llm_complete(prompt, max_tokens=1000, language=language)
        
        # Try to extract JSON from response
        steps_data = _extract_json_from_response(response)
        
        if not steps_data:
            logger.warning("Failed to parse LLM planning response, falling back to single-step")
            return TaskPlan(
                original_task=task,
                steps=[],
                is_multi_step=False
            )
        
        # Convert to TaskStep objects
        steps = []
        for i, step_data in enumerate(steps_data):
            if not isinstance(step_data, dict):
                continue
                
            agent = step_data.get("agent")
            action = step_data.get("action")
            
            if not agent or not action:
                continue
                
            if agent not in ["terminal", "gui", "web", "llm"]:
                logger.warning(f"Invalid agent '{agent}' in step {i}, skipping")
                continue
            
            step = TaskStep(
                agent=agent,
                action=action,
                expected_result=step_data.get("expected_result"),
                depends_on=step_data.get("depends_on")
            )
            steps.append(step)
        
        if not steps:
            logger.warning("No valid steps extracted from plan, falling back to single-step")
            return TaskPlan(
                original_task=task,
                steps=[],
                is_multi_step=False
            )
        
        logger.info(f"Created {len(steps)}-step plan for task: {task[:50]}...")
        return TaskPlan(
            original_task=task,
            steps=steps,
            is_multi_step=True
        )
        
    except Exception as e:
        logger.exception(f"Task planning failed: {e}")
        return TaskPlan(
            original_task=task,
            steps=[],
            is_multi_step=False
        )


def _extract_json_from_response(response: str) -> Optional[List[Dict[str, Any]]]:
    """
    Extract JSON array from LLM response, handling various formats.
    """
    try:
        # Try to parse response directly
        data = json.loads(response.strip())
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    
    # Look for JSON array in response (between [ and ])
    import re
    json_match = re.search(r'\[(.*?)\]', response, re.DOTALL)
    if json_match:
        try:
            json_str = '[' + json_match.group(1) + ']'
            data = json.loads(json_str)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
    
    # Look for individual JSON objects and combine them
    json_objects = re.findall(r'\{[^}]*\}', response)
    if json_objects:
        try:
            steps = []
            for obj_str in json_objects:
                obj = json.loads(obj_str)
                steps.append(obj)
            return steps
        except json.JSONDecodeError:
            pass
    
    return None