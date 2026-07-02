"""Head Protocol: Rework — transfer failed work to another worker.

Companion to head_retry. Where head_retry sends the same task to the
same worker again, head_rework moves it sideways: whatever the failed
worker produced (or the unfinished portion of it) becomes a new task
assigned to a different worker in the same otdel.

Lifecycle:
  1. Head calls head_delegate(w1, task=t)        — w1 starts
  2. w1 reports back, head is not satisfied
  3. Head calls head_rework(worker_slug=w1,
                            target_worker_slug=w2,
                            context="...", portion="whole|partial")
  4. Backend: bumps attempts[w2], clears responded_workers[w2],
     extends expected_workers with w2 (w1 stays in the delegation
     but stops hearing from this task — the soft variant).
  5. Head sends the rework_message to @w2 in the chat — w2 picks up.
  6. If w2 also fails / fails N times → head_rework refuses past the
     cap. Head must call head_decide.

The cap is shared with head_retry / head_delegate via protocol.config.

Note on "soft" removal: w1 stays in state.worker_slugs and in
current_delegation["workers"] but is no longer expected to respond —
if head_rework was a *partial* handover and head wants w1 back later,
they can call head_delegate on w1 with a fresh task. This was the
explicit choice — bare-toggling w1 off would let a misfiring head
silently drop workers from the loop.
"""

from __future__ import annotations

from typing import Any

from ..chat.ws_router import compute_phase, get_head_state
from ..protocol.config import get_max_retries, is_retry_limit_enabled
from ._registry import register_tool
from .base import ToolResult, make_error


@register_tool(
    name="head_rework",
    description="Передать задачу от одного работника другому работнику отдела (внутриотдельский rework). Используй когда первый работник не справился или нужно, чтобы работу доделал / переделал другой. Каждый работник ограничен общим бюджетом попыток.",
    category="head_protocol",
    scope="head",
    dangerous=False,
)
async def head_rework(params: dict[str, Any]) -> ToolResult:
    """
    Move a failed/incomplete task to another worker in the same otdel.

    Params:
        otdel_id: str (injected)
        delegation_id: str (optional, uses active)
        worker_slug: str — the worker who failed or produced unsatisfactory output
        target_worker_slug: str — who takes the work over
        context: str — what went wrong / what needs fixing, in the head's words
        portion: str — "whole" (default) or "partial" (w2 takes only part of w1's work)

    Returns:
        {rework_message: str, guidance: str, attempt: int}
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
        return make_error("worker_slug required — who failed/is being taken off the task")

    target_worker_slug = params.get("target_worker_slug")
    if not target_worker_slug:
        return make_error("target_worker_slug required — who takes over")

    # Validate both belong to this otdel
    valid_slugs = set(state.worker_slugs)
    if worker_slug not in valid_slugs:
        return make_error(f"Worker {worker_slug} not in this otdel")
    if target_worker_slug not in valid_slugs:
        return make_error(f"Worker {target_worker_slug} not in this otdel")

    if worker_slug == target_worker_slug:
        return make_error(
            "worker_slug and target_worker_slug must differ. "
            "To send the same task to the same worker again, use head_retry."
        )

    # Gating: head_rework must not fire before the source worker has
    # actually produced a response — otherwise we're handing off a
    # work-in-progress that doesn't exist yet. Phase ALL_RESPONDED
    # guarantees every expected worker has answered; we additionally
    # require that the *source* (worker_slug) is among them.
    phase_info = compute_phase(state)
    source_responded = any(r["slug"] == worker_slug for r in phase_info["received"])
    if phase_info["phase"] != "ALL_RESPONDED" or not source_responded:
        return make_error(
            f"Cannot rework from @{worker_slug}: phase={phase_info['phase']}, "
            f"missing={', '.join(phase_info['missing']) or '—'}. "
            f"Source worker must answer first; use head_checklist to inspect."
        )

    context = params.get("context", "Previous work needs rework")
    portion = (params.get("portion") or "whole").lower()
    if portion not in ("whole", "partial"):
        return make_error("portion must be 'whole' or 'partial'")

    # Read knob once (also used for error text)
    max_retries = get_max_retries()

    # Cap: refuse to push the target into another attempt past the budget.
    # Same cashier-says-stop metaphor as head_retry.
    if is_retry_limit_enabled():
        target_attempts = state.worker_attempts.get(target_worker_slug, 0) + 1
        if target_attempts > max_retries:
            return make_error(
                f"Rework cap reached for @{target_worker_slug} "
                f"(attempt {target_attempts}/{max_retries}). "
                f"Stop reworking and decide: call head_decide to accept, "
                f"close the task, or escalate to a human."
            )
        # Bump target's attempts even on partial handover: it's still
        # the target's first go at the work.
        state.worker_attempts[target_worker_slug] = target_attempts
    else:
        # Knob off: still log an attempt number for visibility, but no cap.
        state.worker_attempts.setdefault(target_worker_slug, 0)
        state.worker_attempts[target_worker_slug] += 1

    # Make target expected to respond. If they were already expected
    # in the same delegation (head decided to rework multiple times
    # across the same worker), keep them — this is just refreshing.
    state.expected_workers.add(target_worker_slug)

    # If we already had a previous response from the target on this task
    # (e.g., partial handover earlier), drop it so we wait for the new
    # attempt.
    state.responded_workers.pop(target_worker_slug, None)

    # Build the message the head will paste into the chat to @w2.
    # Carries: original task for w1, w1's last response (if any),
    # the head's reason for moving it sideways, and whether w2 should
    # treat this as "from scratch" (whole) or "extend what w1 did" (partial).
    original_task = ""
    if state.current_delegation:
        for w in state.current_delegation.get("workers", []):
            if w.get("slug") == worker_slug:
                original_task = w.get("task", "")
                break

    previous_response = state.responded_workers.get(worker_slug)
    # ws_router stores responses as dicts (slug -> {content, model, ...});
    # pull out the human text, fall back to a placeholder if absent.
    if isinstance(previous_response, dict):
        previous_text = previous_response.get("content", "") or ""
    elif previous_response:
        previous_text = str(previous_response)
    else:
        previous_text = ""
    previous_block = previous_text if previous_text.strip() else "(worker hadn't responded yet)"

    attempt = state.worker_attempts[target_worker_slug]
    portion_phrase = (
        "Переделай задачу целиком с нуля, предыдущий результат не нужен."
        if portion == "whole"
        else "Доделай / исправь результат предыдущего работника, не начинай с нуля."
    )

    rework_message = (
        f"🔁 Rework for @{target_worker_slug} "
        f"(passed from @{worker_slug}, attempt {attempt}/{max_retries}).\n"
        f"Original task: {original_task}\n"
        f"What @{worker_slug} produced: {previous_block}\n"
        f"What needs fixing: {context}\n"
        f"Approach: {portion_phrase}"
    )

    guidance = (
        f"Send this message to @{target_worker_slug} via the otdel chat. "
        f"@{worker_slug} stays in the otdel but stops expecting replies "
        f"for this task — re-engage them via a fresh head_delegate only "
        f"if you decide you want their input back. "
        f"Budget for @{target_worker_slug}: {attempt}/{max_retries}. "
        f"After reaching the cap, head_rework will refuse; call head_decide instead."
    )

    return {
        "success": True,
        "output": rework_message,
        "rework_message": rework_message,
        "guidance": guidance,
        "attempt": attempt,
        "worker_slug": worker_slug,
        "target_worker_slug": target_worker_slug,
        "portion": portion,
    }


__all__ = ["head_rework"]
