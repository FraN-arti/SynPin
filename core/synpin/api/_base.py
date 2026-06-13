"""Shared base for Pydantic request models.

extra="forbid" globally catches the "PATCH 200 OK but the field was silently
dropped because the schema didn't include it" class of bug. Without it,
Pydantic v2's default behaviour is to ignore unknown fields — meaning a
typo or missing field in the request schema passes validation, the handler
returns success, and the user thinks it worked when the data didn't change.

Inheriting from BaseRequest instead of BaseModel directly is the
single config change that prevents this entire class of bug.
"""
from pydantic import BaseModel, ConfigDict


class BaseRequest(BaseModel):
    """All API request models should inherit from this, not BaseModel."""

    model_config = ConfigDict(extra="forbid")
