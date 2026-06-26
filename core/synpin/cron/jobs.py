"""Cron job CRUD — one YAML file per job in data/cron/jobs/."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from ..time import now as _now
from pathlib import Path
from typing import Any, Optional

import yaml

from ..paths import get_data_dir
from .models import CronJob, ScheduleType, ActionType, JobStatus

logger = logging.getLogger(__name__)


# ── Global agent limit (per created_by) ──────────────────────────────────
#
# A single global cap prevents any one agent from flooding the system
# with cron jobs. Read from settings.yaml (cron.agent_limit_per_creator)
# with a sane default of 3. Live reloads on settings change because the
# value is read on every create_job() call — no cache.

DEFAULT_AGENT_LIMIT = 3


def get_agent_limit() -> int:
    """Read global per-creator cron limit from settings.yaml.

    Returns DEFAULT_AGENT_LIMIT if config is missing or invalid.
    """
    try:
        from ..config.manager import load_yaml
        data = load_yaml("settings.yaml")
        cron_cfg = (data or {}).get("cron", {}) or {}
        val = cron_cfg.get("agent_limit_per_creator", DEFAULT_AGENT_LIMIT)
        return max(1, int(val))
    except Exception:
        return DEFAULT_AGENT_LIMIT


def count_active_for_creator(created_by: str) -> int:
    """Count active cron jobs owned by `created_by`.

    Used to enforce the global per-creator cap.
    """
    count = 0
    for job in list_jobs(include_disabled=True):
        if job.created_by == created_by and job.status == JobStatus.ACTIVE:
            count += 1
    return count


def _cron_dir() -> Path:
    d = get_data_dir() / "cron" / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _job_path(job_id: str) -> Path:
    return _cron_dir() / f"{job_id}.yaml"


def _save_job(job: CronJob) -> None:
    path = _job_path(job.id)
    data = job.model_dump()
    # Convert enums to strings for YAML compatibility
    for key, val in data.items():
        if hasattr(val, 'value'):
            data[key] = val.value
    path.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False), encoding="utf-8")


def _load_job(path: Path) -> Optional[CronJob]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if data:
            return CronJob(**data)
    except Exception as e:
        logger.warning("Failed to load cron job %s: %s", path.name, e)
    return None


class CronLimitExceeded(Exception):
    """Raised when a creator tries to exceed their per-creator cron cap.

    Caller (API layer) translates this into HTTP 409 with a clear message.
    """
    def __init__(self, creator: str, current: int, limit: int):
        self.creator = creator
        self.current = current
        self.limit = limit
        super().__init__(
            f"Creator '{creator}' already has {current} active cron jobs "
            f"(limit {limit}). Pause or delete existing jobs first."
        )

# ── Cron expression → next run ──────────────────────────────────────────────

def _parse_cron_expr(expr: str, after: Optional[datetime] = None) -> Optional[datetime]:
    """Parse simple cron expression and return next fire time.
    Supports: "MIN HOUR DOM MON DOW"
    """
    try:
        from croniter import croniter
        base = after or _now()
        cron = croniter(expr, base)
        return cron.get_next(datetime)
    except ImportError:
        logger.warning("croniter not installed — cron scheduling disabled")
        return None
    except Exception as e:
        logger.warning("Invalid cron expression '%s': %s", expr, e)
        return None


def _parse_interval_expr(expr: str) -> Optional[timedelta]:
    """Parse interval expression like '30m', '1h', '2h30m'."""
    total = 0
    current = ""
    for ch in expr.lower():
        if ch.isdigit() or ch == '.':
            current += ch
        elif ch == 's':
            total += int(float(current) or 1) * 1
            current = ""
        elif ch == 'm':
            total += int(float(current) or 1) * 60
            current = ""
        elif ch == 'h':
            total += int(float(current) or 1) * 3600
            current = ""
        elif ch == 'd':
            total += int(float(current) or 1) * 86400
            current = ""
    if current:
        total += int(float(current) or 0)
    return timedelta(seconds=total) if total > 0 else None


def _parse_once_expr(expr: str) -> Optional[datetime]:
    """Parse ISO timestamp for one-shot jobs."""
    try:
        return datetime.fromisoformat(expr)
    except Exception:
        return None


def compute_next_run(job: CronJob) -> Optional[str]:
    """Compute the next run time for a job."""
    now = _now()

    if job.schedule_type == ScheduleType.ONCE:
        # Try absolute ISO timestamp first
        dt = _parse_once_expr(job.schedule_expr)
        if dt and dt > now:
            return dt.isoformat()
        # Then try relative time: "2m", "1h", "30s", "2h30m"
        td = _parse_interval_expr(job.schedule_expr)
        if td:
            return (now + td).isoformat()
        return None

    elif job.schedule_type == ScheduleType.CRON:
        dt = _parse_cron_expr(job.schedule_expr, now)
        return dt.isoformat() if dt else None

    elif job.schedule_type == ScheduleType.INTERVAL:
        td = _parse_interval_expr(job.schedule_expr)
        if td:
            # If we have a last_run, schedule from that; otherwise from now
            if job.last_run_at:
                last = datetime.fromisoformat(job.last_run_at)
                return (last + td).isoformat()
            return (now + td).isoformat()
        return None

    return None

# ── CRUD ─────────────────────────────────────────────────────────────────────

def create_job(
    name: str,
    schedule_type: str,
    schedule_expr: str,
    action_type: str,
    action_target: str = "",
    action_message: str = "",
    action_agent: str = "",
    created_by: str = "user",
    description: str = "",
    timezone: str = "Europe/Moscow",
    delivery: str = "private",
) -> CronJob:
    """Create a new cron job.

    Raises CronLimitExceeded if `created_by` already has the maximum
    number of active jobs (see get_agent_limit).
    """
    # Enforce per-creator limit BEFORE writing anything to disk.
    limit = get_agent_limit()
    current = count_active_for_creator(created_by)
    if current >= limit:
        raise CronLimitExceeded(created_by, current, limit)

    # Lazy import to avoid circular deps (DeliveryMode is in models.py)
    from .models import DeliveryMode

    job_id = f"cron-{uuid.uuid4().hex[:8]}"
    job = CronJob(
        id=job_id,
        name=name,
        created_by=created_by,
        description=description,
        schedule_type=ScheduleType(schedule_type),
        schedule_expr=schedule_expr,
        timezone=timezone,
        action_type=ActionType(action_type),
        action_target=action_target,
        action_message=action_message,
        action_agent=action_agent,
        delivery=DeliveryMode(delivery),
    )
    job.next_run_at = compute_next_run(job)

    # Hard rule: one-shot job whose fire time already passed → mark missed
    if job.schedule_type == ScheduleType.ONCE and not job.next_run_at:
        job.status = JobStatus.MISSED
        logger.warning("Cron one-shot job %s created with past time — marked as missed", job_id)

    _save_job(job)
    logger.info("Created cron job %s: %s (next: %s, status: %s)", job_id, name, job.next_run_at, job.status.value)
    return job


def get_job(job_id: str) -> Optional[CronJob]:
    """Get a job by ID."""
    path = _job_path(job_id)
    if path.exists():
        return _load_job(path)
    return None

def list_jobs(include_disabled: bool = False) -> list[CronJob]:
    """List all cron jobs."""
    jobs = []
    for path in sorted(_cron_dir().glob("*.yaml")):
        job = _load_job(path)
        if job:
            if include_disabled or job.status == JobStatus.ACTIVE:
                jobs.append(job)
    return jobs


def update_job(job_id: str, **kwargs: Any) -> Optional[CronJob]:
    """Update a job's fields."""
    job = get_job(job_id)
    if not job:
        return None

    for key, value in kwargs.items():
        if hasattr(job, key) and value is not None:
            if key == "schedule_type":
                value = ScheduleType(value)
            elif key == "action_type":
                value = ActionType(value)
            elif key == "status":
                value = JobStatus(value)
            setattr(job, key, value)

    job.updated_at = _now().isoformat()

    # Recompute next_run if schedule changed
    if "schedule_type" in kwargs or "schedule_expr" in kwargs or "status" in kwargs:
        if job.status == JobStatus.ACTIVE:
            job.next_run_at = compute_next_run(job)
        else:
            job.next_run_at = None

    _save_job(job)
    logger.info("Updated cron job %s: %s", job_id, kwargs)
    return job


def delete_job(job_id: str) -> bool:
    """Delete a cron job."""
    path = _job_path(job_id)
    if path.exists():
        path.unlink()
        logger.info("Deleted cron job %s", job_id)
        return True
    return False


def get_due_jobs() -> list[CronJob]:
    """Get all active jobs whose next_run_at is in the past."""
    now = _now()
    due = []
    for job in list_jobs():
        if job.status != JobStatus.ACTIVE or not job.next_run_at:
            continue
        try:
            next_dt = datetime.fromisoformat(job.next_run_at)
            if next_dt <= now:
                due.append(job)
        except Exception:
            continue
    return due


def sweep_missed_jobs() -> list[str]:
    """Mark active once-jobs with null next_run_at as missed.

    Called once at scheduler startup. Returns list of job IDs that
    were marked missed — prevents them from sitting active forever
    when the server was offline at their scheduled time.
    """
    now = _now()
    missed = []
    for path in sorted(_cron_dir().glob("*.yaml")):
        job = _load_job(path)
        if not job:
            continue
        if job.status != JobStatus.ACTIVE:
            continue
        if job.schedule_type != ScheduleType.ONCE:
            continue
        if job.next_run_at is not None:
            continue
        # Active once-job with no next_run_at — fire time already passed
        job.status = JobStatus.MISSED
        job.updated_at = _now().isoformat()
        _save_job(job)
        missed.append(job.id)
        logger.warning("Sweep: marked missed one-shot job %s (%s)", job.id, job.name)
    return missed


def advance_next_run(job: CronJob) -> None:
    """Advance the job's next_run_at after execution."""
    if job.schedule_type == ScheduleType.ONCE:
        job.status = JobStatus.COMPLETED
        job.next_run_at = None
    else:
        job.next_run_at = compute_next_run(job)

    job.last_run_at = _now().isoformat()
    job.run_count += 1
    _save_job(job)


def mark_job_run(job_id: str) -> None:
    """Mark a job as having been run (advance next_run)."""
    job = get_job(job_id)
    if job:
        advance_next_run(job)
