"""Head Protocol: Quality gate - evaluate worker results.

Per-worker evaluation. Returns a `per_worker` list (one entry per
worker actually evaluated) so the head can pick which workers to
retry / rework / accept individually rather than guessing from a
global satisfied bool.

Backward-compatible: also returns the flat `satisfied / issues /
suggestions` derived from the per-worker results. Existing callers
that just look at the flat output keep working.

Future: the `pass` for `criterion in criteria` (line 90) is the
planned LLM-judge slot — when wired, each per-worker entry will
gain a `criterion_results: [{criterion, satisfied, evidence}]` block.
"""

from __future__ import annotations

from typing import Any

from ..chat.ws_router import get_head_state
from ._registry import register_tool
from .base import ToolResult, make_error


@register_tool(
    name="head_evaluate",
    description="Оценить результаты работников по критериям. Возвращает per-worker оценку (satisfied/issues/suggestions на каждого), плюс общую сводку. Принимает optional worker_slugs — если передан, оценивает только этих (точечная оценка).",
    category="head_protocol",
    scope="head",
    dangerous=False,
)
async def head_evaluate(params: dict[str, Any]) -> ToolResult:
    """
    Per-worker quality gate.

    Params:
        otdel_id: str (injected)
        delegation_id: str (optional, uses active)
        task_description: str - original task description
        worker_slugs: list[str] (optional) - which workers to evaluate.
                      If omitted, evaluates everyone in expected ∩ responded.
        criteria: list[str] - evaluation criteria (optional)

    Returns:
        {
          per_worker: [
            {slug, satisfied, issues: [str], suggestions: [str]}, ...
          ],
          satisfied: bool,                  # flat, all
          issues: [str],                    # flat, all
          suggestions: [str],               # flat, all
        }
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

    criteria = params.get("criteria", [])
    worker_slugs_opt = params.get("worker_slugs")

    # Decide which workers to evaluate. We only consider workers that
    # are in BOTH expected and responded — that's the "real" answer set.
    expected = set(state.expected_workers)
    responded = set(state.responded_workers.keys())
    candidates = expected & responded

    if worker_slugs_opt:
        # Caller asked for specific workers. Validate they exist and
        # have responded. Unknown slugs are reported back as a flat
        # per_worker entry with has_response=False, so the head isn't
        # left guessing why its list was incomplete.
        requested = set(worker_slugs_opt)
        unknown = sorted(requested - expected)
        targets = sorted(requested & candidates)
    else:
        unknown = []
        targets = sorted(candidates)

    if not targets and not unknown:
        return {
            "success": False,
            "output": "",
            "error": "No results to evaluate",
            "satisfied": False,
            "issues": ["No worker responses available"],
            "suggestions": ["Wait for worker responses before evaluating"],
            "per_worker": [],
        }

    per_worker: list[dict] = []

    # Report unknown slugs (called but not in this otdel) so the
    # head sees the discrepancy in one place instead of failing
    # silently.
    for slug in unknown:
        per_worker.append(
            {
                "slug": slug,
                "satisfied": False,
                "issues": [f"{slug}: not in this otdel"],
                "suggestions": ["Remove from worker_slugs or check otdel composition"],
            }
        )

    for slug in targets:
        resp = state.responded_workers[slug]
        if isinstance(resp, dict):
            content = resp.get("content", "") or ""
        else:
            content = str(resp)

        issues: list[str] = []
        suggestions: list[str] = []

        if not content or not content.strip():
            issues.append(f"{slug}: empty response")
            suggestions.append(f"Retry {slug} with head_retry")

        # Cheap error markers. LLM-judge goes here for deeper checks.
        if "⚠️" in content or "Ошибка" in content or "Error" in content:
            issues.append(f"{slug}: response contains error")
            suggestions.append(f"Review {slug}'s output and consider retry")

        # Reserved slot for future LLM-judge per criterion. For now,
        # `criteria` is just echoed back so the head sees the head
        # passed them — but no decision is made off them.
        for criterion in criteria:
            # TODO: replace with LLM-judge call when wired.
            pass

        per_worker.append(
            {
                "slug": slug,
                "satisfied": len(issues) == 0,
                "issues": issues,
                "suggestions": suggestions,
            }
        )

    # Flat backward-compat layer.
    flat_issues = sum((p["issues"] for p in per_worker), [])
    flat_suggestions = sum((p["suggestions"] for p in per_worker), [])
    flat_satisfied = all(p["satisfied"] for p in per_worker) if per_worker else False

    if per_worker:
        summary = (
            f"evaluated {len(targets)} worker(s); "
            f"{sum(1 for p in per_worker if p['satisfied'])}/{len(per_worker)} satisfied"
        )
    else:
        summary = "no workers evaluated"

    return {
        "success": True,
        "output": summary,
        "satisfied": flat_satisfied,
        "issues": flat_issues,
        "suggestions": flat_suggestions,
        "per_worker": per_worker,
    }


__all__ = ["head_evaluate"]
