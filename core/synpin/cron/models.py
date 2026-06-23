"""Cron job models for SynPin."""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
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

    # State
    status: JobStatus = JobStatus.ACTIVE
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    run_count: int = 0
    created_at: str = Field(default_factory=lambda: _now().isoformat())
    updated_at: str = Field(default_factory=lambda: _now().isoformat())
