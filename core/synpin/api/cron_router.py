"""Cron API — manage scheduled tasks."""
from __future__ import annotations

from typing import Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..cron.jobs import (
    create_job, get_job, list_jobs, update_job, delete_job,
)

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


@router.get("/jobs")
def api_list_jobs() -> dict[str, Any]:
    """List all cron jobs."""
    jobs = list_jobs(include_disabled=True)
    return {"jobs": [j.model_dump() for j in jobs], "count": len(jobs)}


@router.post("/jobs")
def api_create_job(req: CronJobCreate) -> dict[str, Any]:
    """Create a cron job."""
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
    return {"status": "triggered", "job_id": job_id}

    return {"status": "triggered", "job_id": job_id, "name": job.name}


@router.delete("/jobs/{job_id}")
def api_delete_job(job_id: str) -> dict[str, Any]:
    """Delete a cron job."""
    if not delete_job(job_id):
        raise HTTPException(404, f"Job not found: {job_id}")
    return {"status": "deleted", "job_id": job_id}
