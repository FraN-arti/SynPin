"""Head Protocol: Quality gate - evaluate worker results."""
from __future__ import annotations

from typing import Any

from ..chat.ws_router import get_head_state
from ._registry import register_tool
from .base import ToolResult, make_success, make_error



@register_tool(
    name='head_evaluate',
    description='Оценить результаты работников по критериям. Проверяет удовлетворяют ли ответы поставленной задаче.',
    category='head_protocol',
    scope='head',
    dangerous=False,
)
async def head_evaluate(params: dict[str, Any]) -> ToolResult:
    """
    Evaluate if worker results satisfy the task.
    
    Params:
        otdel_id: str (injected)
        delegation_id: str (optional, uses active)
        task_description: str - original task description
        results: list[dict] - worker results to evaluate (optional, uses state if not provided)
        criteria: list[str] - evaluation criteria (optional)
    
    Returns:
        {satisfied: bool, issues: [], suggestions: []}
    """
    otdel_id = params.get("otdel_id")
    if not otdel_id:
        return make_error("otdel_id required")
    
    state = get_head_state(otdel_id)
    if not state:
        return make_error(f"No HeadState for otdel {otdel_id}")
    
    delegation_id = params.get("delegation_id") or state.active_delegation_id
    if not delegation_id or delegation_id != state.active_delegation_id:
        return make_error(f"No active delegation matching {delegation_id}")
    
    task_description = params.get("task_description", "")
    criteria = params.get("criteria", [])
    
    # Use provided results or get from state
    results = params.get("results")
    if not results:
        results = [
            {"slug": slug, "response": state.responded_workers[slug]}
            for slug in state.expected_workers
            if slug in state.responded_workers
        ]
    
    if not results:
        return {
            "success": False,
            "output": "",
            "error": "No results to evaluate",
            "satisfied": False,
            "issues": ["No worker responses available"],
            "suggestions": ["Wait for responses first with head_await"],
        }
    
    # Simple evaluation logic
    issues = []
    suggestions = []
    
    for r in results:
        slug = r.get("slug", "unknown")
        response = r.get("response", {})
        content = response.get("content", "") if isinstance(response, dict) else str(response)
        
        if not content or content.strip() == "":
            issues.append(f"{slug}: empty response")
            suggestions.append(f"Retry {slug} with head_retry")
        
        # Check for error indicators
        if "⚠️" in content or "Ошибка" in content or "Error" in content:
            issues.append(f"{slug}: response contains error")
            suggestions.append(f"Review {slug}'s output and consider retry")
    
    satisfied = len(issues) == 0
    
    # Add custom criteria checks if provided
    for criterion in criteria:
        # This could be extended with LLM-based evaluation
        pass
    
    output = "Results satisfy task" if satisfied else f"Found {len(issues)} issue(s)"
    
    return {
        "success": True,
        "output": output,
        "satisfied": satisfied,
        "issues": issues,
        "suggestions": suggestions,
    }


__all__ = ["head_evaluate"]