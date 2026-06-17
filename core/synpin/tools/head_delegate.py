"""Head Protocol: Delegate tasks to workers."""
from __future__ import annotations

import uuid
from typing import Any

from ..chat.ws_router import get_head_state
from .base import ToolResult, make_success, make_error


async def head_delegate(params: dict[str, Any]) -> ToolResult:
    """
    Structure a delegation to workers.
    
    Params:
        otdel_id: str (injected by execute_tool)
        workers: list[dict] - each with {slug: str, task: str}
        strategy: "parallel" | "sequential" | "pipeline" (default: "parallel")
        context: str - additional context for workers
        timeout_ms: int (default: 120000)
    
    Returns:
        {delegation_id, expected_workers, timeout_ms, guidance}
    """
    otdel_id = params.get("otdel_id")
    if not otdel_id:
        return make_error("otdel_id required (should be injected by system)")
    
    state = get_head_state(otdel_id)
    if not state:
        return make_error(f"No HeadState for otdel {otdel_id}")
    
    workers = params.get("workers", [])
    if not workers:
        return make_error("At least one worker required")
    
    strategy = params.get("strategy", "parallel")
    context = params.get("context", "")
    timeout_ms = params.get("timeout_ms", 120000)
    
    # Validate workers exist in this otdel
    valid_slugs = set(state.worker_slugs)
    invalid = [w["slug"] for w in workers if w.get("slug") not in valid_slugs]
    if invalid:
        return make_error(f"Workers not in this otdel: {invalid}")
    
    delegation_id = f"del-{uuid.uuid4().hex[:8]}"
    
    # Update state
    state.active_delegation_id = delegation_id
    state.expected_workers = {w["slug"] for w in workers}
    state.current_delegation = {
        "delegation_id": delegation_id,
        "workers": workers,
        "strategy": strategy,
        "context": context,
        "timeout_ms": timeout_ms,
    }
    state.delegation_history.append(state.current_delegation)
    
    # Initialize attempt counters
    for w in workers:
        slug = w["slug"]
        if slug not in state.worker_attempts:
            state.worker_attempts[slug] = 0
    
    worker_names = ", ".join(f"@{w['slug']}" for w in workers)
    guidance = (
        f"Delegation {delegation_id} created. "
        f"Workers: {worker_names}. "
        f"Strategy: {strategy}. Timeout: {timeout_ms//1000}s. "
        f"Workers will respond automatically — do NOT write 'waiting for response'."
    )
    
    return make_success(guidance)


# For direct import
__all__ = ["head_delegate"]