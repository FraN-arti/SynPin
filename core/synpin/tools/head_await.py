"""Head Protocol: Wait for worker responses with timeout/fallback."""
from __future__ import annotations

import asyncio
from typing import Any

from ..chat.ws_router import get_head_state
from ._registry import register_tool
from .base import ToolResult, make_success, make_error



@register_tool(
    name='head_await',
    description='УСТАРЕЛО: НЕ используй этот инструмент. Ответы работников приходят автоматически после head_delegate.',
    category='head_protocol',
    scope='all',
    dangerous=False,
)
async def head_await(params: dict[str, Any]) -> ToolResult:
    """
    Wait for all expected workers to respond.
    
    Params:
        otdel_id: str (injected)
        delegation_id: str (optional, uses active if not specified)
        timeout_ms: int (default: 120000)
    
    Returns:
        {status: "all_responded" | "timeout" | "partial", results: [...], missing: [...]}
    """
    otdel_id = params.get("otdel_id")
    if not otdel_id:
        return make_error("otdel_id required")
    
    state = get_head_state(otdel_id)
    if not state:
        return make_error(f"No HeadState for otdel {otdel_id}")
    
    delegation_id = params.get("delegation_id") or state.active_delegation_id
    if not delegation_id:
        return make_error("No active delegation")
    
    # Verify this matches the active delegation
    if delegation_id != state.active_delegation_id:
        return make_error(f"Delegation {delegation_id} is not active (active: {state.active_delegation_id})")
    
    timeout_ms = params.get("timeout_ms", 120000)
    expected = state.expected_workers
    
    if not expected:
        return make_success("No workers expected")
    
    # Wait for responses
    start_time = asyncio.get_event_loop().time()
    timeout_seconds = timeout_ms / 1000
    
    while True:
        responded = set(state.responded_workers.keys())
        missing = expected - responded
        
        if not missing:
            # All responded
            results = [
                {"slug": slug, "response": state.responded_workers[slug]}
                for slug in expected
            ]
            return {
                "success": True,
                "output": f"All {len(expected)} workers responded",
                "status": "all_responded",
                "results": results,
                "missing": [],
            }
        
        elapsed = (asyncio.get_event_loop().time() - start_time) * 1000
        if elapsed >= timeout_ms:
            # Timeout
            results = [
                {"slug": slug, "response": state.responded_workers.get(slug, {})}
                for slug in expected
            ]
            return {
                "success": False,
                "output": "",
                "error": f"Timeout waiting for {len(missing)} worker(s): {', '.join(missing)}",
                "status": "timeout",
                "results": results,
                "missing": list(missing),
            }
        
        # Check every 500ms
        await asyncio.sleep(0.5)


# For direct import
__all__ = ["head_await"]