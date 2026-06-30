"""Head Protocol: Retry a failed worker via mentor."""
from __future__ import annotations

from typing import Any

from ..chat.ws_router import get_head_state
from ._registry import register_tool
from .base import ToolResult, make_success, make_error



@register_tool(
    name='head_retry',
    description='Повторно отправить задачу работнику если он не ответил или ответил с ошибкой.',
    category='head_protocol',
    scope='head',
    dangerous=False,
)
async def head_retry(params: dict[str, Any]) -> ToolResult:
    """
    Retry a worker that failed or timed out.
    
    Params:
        otdel_id: str (injected)
        delegation_id: str (optional, uses active)
        worker_slug: str - the worker to retry
        error_context: str - what went wrong
        attempt: int - retry attempt number (default: increments from state)
    
    Returns:
        {retry_message: str, guidance: str, attempt: int}
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
    
    worker_slug = params.get("worker_slug")
    if not worker_slug:
        return make_error("worker_slug required")
    
    if worker_slug not in state.worker_slugs:
        return make_error(f"Worker {worker_slug} not in this otdel")
    
    error_context = params.get("error_context", "Previous attempt failed or timed out")
    attempt = params.get("attempt")
    
    if attempt is None:
        attempt = state.worker_attempts.get(worker_slug, 0) + 1
    
    state.worker_attempts[worker_slug] = attempt
    
    # Clear previous response for this worker so we can wait for new one
    state.responded_workers.pop(worker_slug, None)
    
    # Get original task for this worker
    original_task = ""
    if state.current_delegation:
        for w in state.current_delegation.get("workers", []):
            if w.get("slug") == worker_slug:
                original_task = w.get("task", "")
                break
    
    retry_message = (
        f"🔄 Retry #{attempt} for @{worker_slug}.\n"
        f"Original task: {original_task}\n"
        f"Previous error: {error_context}\n"
        f"Please try again, considering the error above."
    )
    
    guidance = (
        f"Send this message to @{worker_slug} via head_delegate or directly. "
        f"Attempt {attempt}/3. After 3 failed attempts, consider head_decide takeover."
    )
    
    return {
        "success": True,
        "output": retry_message,
        "retry_message": retry_message,
        "guidance": guidance,
        "attempt": attempt,
        "worker_slug": worker_slug,
    }


__all__ = ["head_retry"]