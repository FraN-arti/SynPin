"""Head protocol behaviour configuration (global, not per-otdel).

Currently only the retry-limit knob lives here. As the protocol grows
(LLM-judge, intra-otdel rework, escalation timers) all of those knobs
will land in the same file.

Storage: <config_dir>/protocol.yaml
"""

from .config import (
    ProtocolSettings,
    load_settings,
    save_settings,
    get_max_retries,
    is_retry_limit_enabled,
    DEFAULT_MAX_RETRIES,
    RETRY_LIMIT_ENABLED_DEFAULT,
)

__all__ = [
    "ProtocolSettings",
    "load_settings",
    "save_settings",
    "get_max_retries",
    "is_retry_limit_enabled",
    "DEFAULT_MAX_RETRIES",
    "RETRY_LIMIT_ENABLED_DEFAULT",
]
