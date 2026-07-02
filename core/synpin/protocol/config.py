"""Settings for head agent protocol behaviour.

Owns a single file: <config_dir>/protocol.yaml.

These are intentionally GLOBAL — every otdel in the system shares the
same retry policy. The user said: don't make me configure each otdel
separately.

The first (and for now only) knob is the worker-retry limit. When the
limit is reached, head_retry and head_delegate refuse to send a worker
home again — they return an error nudging the head to call head_decide.
Metaphor from Artur: a cashier who, asked for the total, doesn't keep
reciting promos — she gives the answer or says "I'll get the manager."

Add new knobs here. Don't introduce per-otdel protocol config in this
file — if the need appears, open a separate module.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from ..config.manager import load_yaml, save_yaml
from ..ws_broadcast import broadcast

logger = logging.getLogger(__name__)


# ── Defaults ──────────────────────────────────────────────────────

# 3 retries matches the spec'd behaviour in head_retry: after 3 failed
# attempts the head is nudged to head_decide. Raising the default would
# weaken the very behaviour we just made real — keep it explicit.
DEFAULT_MAX_RETRIES = 3
RETRY_LIMIT_ENABLED_DEFAULT = True


# ── Model ─────────────────────────────────────────────────────────


class ProtocolSettings(BaseModel):
    """Behaviour knobs for the head protocol.

    retry_limit_enabled: when False, head_retry / head_delegate behave
        as before — no cap, the loop can spin until the head LLM
        decides to stop. Equivalent to "I trust the LLM to know when
        to stop."
    max_retries: when retry_limit_enabled is True, the worker can be
        sent back to retry at most this many times per delegation.
        After the cap is reached both head_retry and head_delegate
        refuse another attempt and tell the head to call head_decide.
    """

    retry_limit_enabled: bool = RETRY_LIMIT_ENABLED_DEFAULT
    max_retries: int = Field(default=DEFAULT_MAX_RETRIES, ge=1, le=10)


# ── File location ─────────────────────────────────────────────────

_FILENAME = "protocol.yaml"


# ── Load / save ───────────────────────────────────────────────────


def load_settings() -> ProtocolSettings:
    """Read protocol.yaml, fall back to defaults. Persists defaults on
    first use so the user can find and edit the file directly.
    """
    data = load_yaml(_FILENAME) or {}
    try:
        settings = ProtocolSettings(**data)
    except Exception as e:
        # A corrupt or partial file should not break the server — fall
        # back to defaults and log. Next save will rewrite the file
        # cleanly.
        logger.warning(
            "[protocol] failed to parse protocol.yaml (%s); using defaults",
            e,
        )
        settings = ProtocolSettings()
        save_settings(settings)
        return settings

    # First-run convenience: persist defaults so the file is on disk
    # for the curious / for hand-editing. Cheap (idempotent overwrite).
    if not data:
        save_settings(settings)
    return settings


def save_settings(settings: ProtocolSettings) -> None:
    """Persist protocol.yaml and broadcast the change."""
    save_yaml(_FILENAME, settings.model_dump())
    broadcast(
        {
            "type": "protocol:settings_updated",
            "settings": settings.model_dump(),
        }
    )


# ── Convenience accessors used by tools (head_retry, head_delegate)


def get_max_retries() -> int:
    """Return the active cap. Always returns an int (defaults applied)."""
    return load_settings().max_retries


def is_retry_limit_enabled() -> bool:
    """True when the retry cap is enforced. False = trust the LLM."""
    return load_settings().retry_limit_enabled
