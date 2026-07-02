"""Cron job models for SynPin."""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from ..time import now as _now


class ScheduleType(str, Enum):
    ONCE = "once"         # one-shot: run at specific time
    CRON = "cron"         # repeating: cron expression
    INTERVAL = "interval" # repeating: every N seconds


class ActionType(str, Enum):
    SEND_MESSAGE = "send_message"   # send message to otdel chat
    RUN_PROMPT = "run_prompt"       # run agent with a prompt (LLM call)


class JobStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"  # for one-shot jobs after execution
    MISSED = "missed"        # one-shot job whose fire time passed while server was offline


class DeliveryMode(str, Enum):
    """Where the result of a cron-triggered agent run is delivered.

    Critical for avoiding "chat spam" — most cron jobs are silent
    (check a status, log to memory, send to otdel) and only a few
    should ping the user's private chat.
    """
    PRIVATE = "private"   # agent output → user's private chat (default)
    OTDEL = "otdel"      # agent output → otdel chat (action_target)
    SILENT = "silent"     # no chat message; only memory/log


class LastResult(str, Enum):
    """Outcome of the most recent execution."""
    SUCCESS = "success"   # job ran, agent finished
    ERROR = "error"       # job ran, agent raised or timed out
    SKIPPED = "skipped"   # job didn't run (e.g. server offline, agent busy)


class CronJob(BaseModel):
    id: str
    name: str
    created_by: str = "user"           # "user", "main_agent", agent slug
    description: str = ""

    # Schedule
    schedule_type: ScheduleType = ScheduleType.CRON
    schedule_expr: str = ""            # cron: "0 13 * * *", interval: "30m", once: ISO timestamp
    timezone: str = "Europe/Moscow"

    # Action
    action_type: ActionType = ActionType.SEND_MESSAGE
    action_target: str = ""            # otdel_id for send_message, agent_slug for run_prompt
    action_message: str = ""           # message text or prompt
    action_agent: str = ""             # agent to run (for run_prompt)

    # Delivery — where the result goes. Default "private" to keep
    # backward compatibility with existing jobs.
    delivery: DeliveryMode = DeliveryMode.PRIVATE

    # State
    status: JobStatus = JobStatus.ACTIVE
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    run_count: int = 0
    # Last execution record (set by the scheduler after each run)
    last_result: LastResult = LastResult.SUCCESS
    last_result_message: str = ""      # short reason on error/skipped, tooltip in UI
    last_duration_ms: Optional[int] = None
    created_at: str = Field(default_factory=lambda: _now().isoformat())
    updated_at: str = Field(default_factory=lambda: _now().isoformat())
