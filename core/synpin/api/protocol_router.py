"""Protocol settings API (global, not per-otdel).

Currently exposes the retry-limit knob used by head_retry / head_delegate.
"""

from __future__ import annotations

from fastapi import APIRouter

from ._base import BaseRequest
from ..protocol.config import load_settings, save_settings


router = APIRouter(prefix="/api/protocol", tags=["protocol"])


class ProtocolSettingsUpdate(BaseRequest):
    """Partial update — both fields optional. extra='forbid' catches
    typos in field names (see api/_base.py for rationale).
    """

    retry_limit_enabled: bool | None = None
    max_retries: int | None = None


@router.get("/settings")
def get_protocol_settings() -> dict:
    return load_settings().model_dump()


@router.put("/settings")
def update_protocol_settings(req: ProtocolSettingsUpdate) -> dict:
    settings = load_settings()
    if req.retry_limit_enabled is not None:
        settings.retry_limit_enabled = req.retry_limit_enabled
    if req.max_retries is not None:
        # Pydantic Field(ge=1, le=10) enforces the range. Let it raise —
        # FastAPI returns 422 with a readable error.
        settings.max_retries = req.max_retries
    save_settings(settings)
    return settings.model_dump()


__all__ = ["router"]
