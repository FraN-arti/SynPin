"""Cron API — manage scheduled tasks."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..cron.jobs import (
    create_job, get_job, list_jobs, update_job, delete_job,
    CronLimitExceeded, get_agent_limit, count_active_for_creator,
    DEFAULT_AGENT_LIMIT,
)
from ..cron.models import JobStatus

router = APIRouter(prefix="/api/cron", tags=["cron"])


class CronJobCreate(BaseModel):
    name: str
    schedule_type: str = "cron"     # "cron", "once", "interval"
    schedule_expr: str = ""         # "0 13 * * *", "2026-06-23T13:00:00", "30m"
    action_type: str = "send_message"  # "send_message", "run_prompt"
    action_target: str = ""         # otdel_id or agent_slug
    action_message: str = ""
    action_agent: str = ""
    description: str = ""
    created_by: str = "user"
    timezone: str = "Europe/Moscow"
    delivery: str = "private"       # "private" | "otdel" | "silent"


class CronJobUpdate(BaseModel):
    name: Optional[str] = None
    schedule_type: Optional[str] = None
    schedule_expr: Optional[str] = None
    action_type: Optional[str] = None
    action_target: Optional[str] = None
    action_message: Optional[str] = None
    action_agent: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None     # "active", "paused"
    timezone: Optional[str] = None
    delivery: Optional[str] = None


@router.get("/jobs")
def api_list_jobs() -> dict[str, Any]:
    """List all cron jobs."""
    jobs = list_jobs(include_disabled=True)
    return {"jobs": [j.model_dump() for j in jobs], "count": len(jobs)}


@router.post("/jobs")
def api_create_job(req: CronJobCreate) -> dict[str, Any]:
    """Create a cron job. Returns 409 if the creator hit the agent_limit cap."""
    try:
        job = create_job(
            name=req.name,
            schedule_type=req.schedule_type,
            schedule_expr=req.schedule_expr,
            action_type=req.action_type,
            action_target=req.action_target,
            action_message=req.action_message,
            action_agent=req.action_agent,
            created_by=req.created_by,
            description=req.description,
            timezone=req.timezone,
            delivery=req.delivery,
        )
    except CronLimitExceeded as e:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "cron_limit_exceeded",
                "creator": e.creator,
                "current": e.current,
                "limit": e.limit,
                "message": str(e),
            },
        )
    return job.model_dump()


@router.get("/jobs/{job_id}")
def api_get_job(job_id: str) -> dict[str, Any]:
    """Get a cron job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    return job.model_dump()


@router.put("/jobs/{job_id}")
def api_update_job(job_id: str, req: CronJobUpdate) -> dict[str, Any]:
    """Update a cron job."""
    updates = req.model_dump(exclude_none=True)
    job = update_job(job_id, **updates)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")
    return job.model_dump()


@router.post("/jobs/{job_id}/run")
async def api_run_job_now(job_id: str) -> dict[str, Any]:
    """Trigger a cron job immediately (run now)."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job not found: {job_id}")

    from ..cron.scheduler import _execute_job
    import asyncio

    # Fire-and-forget: schedule the job execution
    asyncio.create_task(_execute_job(job))
    return {"status": "triggered", "job_id": job_id, "name": job.name}


@router.delete("/jobs/{job_id}")
def api_delete_job(job_id: str) -> dict[str, Any]:
    """Delete a cron job."""
    if not delete_job(job_id):
        raise HTTPException(404, f"Job not found: {job_id}")
    return {"status": "deleted", "job_id": job_id}


# ── Stats & limit endpoints ───────────────────────────────────────────────


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


@router.get("/stats")
def api_cron_stats() -> dict[str, Any]:
    """Aggregate stats for the Cron UI card.

    Returns:
        total, by_status counts, nearest upcoming run, most recent run,
        global agent_limit, count of active jobs per creator.
    """
    now = datetime.now()
    all_jobs = list_jobs(include_disabled=True)

    # Counts by status
    by_status: dict[str, int] = {"active": 0, "paused": 0, "completed": 0, "missed": 0}
    for j in all_jobs:
        by_status[j.status.value] = by_status.get(j.status.value, 0) + 1

    # Nearest upcoming run (active, future next_run_at)
    upcoming: Optional[dict] = None
    for j in all_jobs:
        if j.status != JobStatus.ACTIVE:
            continue
        dt = _parse_iso(j.next_run_at)
        if not dt or dt <= now:
            continue
        rec = {
            "id": j.id,
            "name": j.name,
            "at": j.next_run_at,
            "in_seconds": int((dt - now).total_seconds()),
        }
        if upcoming is None or rec["in_seconds"] < upcoming["in_seconds"]:
            upcoming = rec

    # Most recent run (any status, has last_run_at)
    last_run: Optional[dict] = None
    for j in all_jobs:
        dt = _parse_iso(j.last_run_at)
        if not dt:
            continue
        rec = {
            "id": j.id,
            "name": j.name,
            "at": j.last_run_at,
            "ago_seconds": int((now - dt).total_seconds()),
            "result": j.last_result.value,
            "result_message": j.last_result_message,
            "duration_ms": j.last_duration_ms,
        }
        if last_run is None or rec["ago_seconds"] < last_run["ago_seconds"]:
            last_run = rec

    # Active count per creator
    creator_counts: dict[str, int] = {}
    for j in all_jobs:
        if j.status == JobStatus.ACTIVE:
            creator_counts[j.created_by] = creator_counts.get(j.created_by, 0) + 1

    return {
        "total": len(all_jobs),
        "by_status": by_status,
        "next_run": upcoming,
        "last_run": last_run,
        "agent_limit": get_agent_limit(),
        "agent_limit_default": DEFAULT_AGENT_LIMIT,
        "agent_limit_count": creator_counts,
    }


class AgentLimitUpdate(BaseModel):
    agent_limit_per_creator: int


@router.get("/agent-limit")
def api_get_agent_limit() -> dict[str, Any]:
    """Read the current global per-creator cap."""
    return {
        "agent_limit_per_creator": get_agent_limit(),
        "default": DEFAULT_AGENT_LIMIT,
    }


@router.put("/agent-limit")
def api_set_agent_limit(req: AgentLimitUpdate) -> dict[str, Any]:
    """Update the global per-creator cap in settings.yaml.

    Existing jobs are NOT auto-deleted — if you lower the cap below the
    current count, new jobs will be rejected until creators delete or
    pause their old ones.
    """
    val = max(1, int(req.agent_limit_per_creator))
    from ..config.manager import load_yaml, save_yaml
    data = load_yaml("settings.yaml") or {}
    cron_cfg = data.setdefault("cron", {})
    cron_cfg["agent_limit_per_creator"] = val
    save_yaml("settings.yaml", data)
    return {"agent_limit_per_creator": val}

