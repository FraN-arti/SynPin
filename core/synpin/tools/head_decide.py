"""Head Protocol: Strategic decision - continue/stop/takeover/escalate."""
from __future__ import annotations

from typing import Any

from ..chat.ws_router import get_head_state
from .base import ToolResult, make_success, make_error


async def head_decide(params: dict[str, Any]) -> ToolResult:
    """
    Make a strategic decision about the delegation.
    
    Params:
        otdel_id: str (injected)
        delegation_id: str (optional, uses active)
        situation: "continue" | "stop" | "takeover" | "escalate"
        reasoning: str - why this decision
        context: dict - additional context
    
    Returns:
        {action: str, reasoning: str, next_prompt: str}
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
    
    situation = params.get("situation")
    valid_situations = ("continue", "stop", "takeover", "escalate")
    if situation not in valid_situations:
        return make_error(f"Invalid situation. Must be one of: {', '.join(valid_situations)}")
    
    reasoning = params.get("reasoning", "")
    context = params.get("context", {})
    
    # Build next prompt based on decision
    if situation == "continue":
        action = "continue_delegation"
        next_prompt = "Delegation continues. Monitor worker progress."
    elif situation == "stop":
        action = "stop_delegation"
        next_prompt = "Delegation stopped. Summarize what was accomplished and report to user."
        state.reset_delegation()
    elif situation == "takeover":
        action = "head_takeover"
        next_prompt = "Head takes over the task personally. Complete the work and report."
        state.reset_delegation()
    elif situation == "escalate":
        action = "escalate_to_user"
        next_prompt = "Escalate to user. Report the situation and ask for guidance."
    
    # Record decision in history
    state.delegation_history.append({
        "delegation_id": delegation_id,
        "decision": situation,
        "reasoning": reasoning,
        "context": context,
    })
    
    return {
        "success": True,
        "output": f"Decision: {situation} — {reasoning}",
        "action": action,
        "reasoning": reasoning,
        "next_prompt": next_prompt,
    }


__all__ = ["head_decide"]