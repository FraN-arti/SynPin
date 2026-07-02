"""Head Protocol: Checklist — current phase of the active delegation.

The head's decision loop used to be racy: it could call head_retry /
head_rework / head_decide before the worker actually produced an answer,
because the head's own text stream and the worker's response both flow
through the same WebSocket. This tool reports the *objective* phase of
the delegation so the head can ground its decisions in fact, not
memory of what it last thought.

Phase semantics:
  DELEGATED    — task was dispatched, nothing back yet. expected ∩ responded = ∅.
  PARTIAL      — at least one worker is in, but the set isn't complete.
                 expected − responded = non-empty. The head must wait
                 (no new tool calls) before retrying / reworking / deciding.
  ALL_RESPONDED — every expected worker has been seen. The head may now
                  evaluate them (head_evaluate) and decide.

This is a READ-ONLY snapshot. It does NOT enforce anything — that is
intentional for the first iteration (lets us confirm the legibility
of the picture before turning it into a hard gate).

Output shape:
  {
    "phase": "DELEGATED" | "PARTIAL" | "ALL_RESPONDED",
    "delegation_id": str | None,
    "expected":     [...],          # slugs still owed a response
    "received":     [{slug, has_content}, ...],
    "missing":      [...],          # alias for expected, for clarity
    "ready_to_decide": bool,
    "summary":      str,            # one-liner for the head
  }
"""

from __future__ import annotations

from typing import Any

from ..chat.ws_router import compute_phase, get_head_state
from ._registry import register_tool
from .base import ToolResult, make_error


@register_tool(
    name="head_checklist",
    description="Рапорт: текущая фаза активной делегации (DELEGATED/PARTIAL/ALL_RESPONDED) и список ожидающих/полученных ответов работников. Используй перед head_retry / head_rework / head_decide, чтобы не принимать решение до того, как ответы реально пришли.",
    category="head_protocol",
    scope="head",
    dangerous=False,
)
async def head_checklist(params: dict[str, Any]) -> ToolResult:
    """Snapshot of where the active delegation stands."""
    otdel_id = params.get("otdel_id")
    if not otdel_id:
        return make_error("otdel_id required")

    state = get_head_state(otdel_id)
    if not state:
        return make_error(f"No HeadState for otdel {otdel_id}")

    delegation_id = state.active_delegation_id
    if not delegation_id:
        # No delegation ever started — return a benign empty picture so the
        # head can still call this defensively without a prior head_delegate.
        empty = compute_phase(state)
        return {
            "success": True,
            "output": "No active delegation. Nothing in flight.",
            **{k: v for k, v in empty.items() if k != "summary"},
            "summary": "no_active_delegation",
        }

    phase_info = compute_phase(state)

    # Augment with content_chars (UI-facing — checklist tool exposes richer
    # detail than the gating version, to help the head plan next step).
    received_with_chars = []
    for entry in phase_info["received"]:
        slug = entry["slug"]
        resp = state.responded_workers[slug]
        if isinstance(resp, dict):
            content = resp.get("content", "") or ""
        else:
            content = str(resp)
        received_with_chars.append(
            {
                "slug": slug,
                "has_content": entry["has_content"],
                "content_chars": len(content),
            }
        )

    return {
        "success": True,
        "output": phase_info["summary"],
        "phase": phase_info["phase"],
        "delegation_id": phase_info["delegation_id"],
        "expected": phase_info["expected"],
        "received": received_with_chars,
        "missing": phase_info["missing"],
        "ready_to_decide": phase_info["ready_to_decide"],
        "summary": phase_info["summary"],
    }


__all__ = ["head_checklist"]
