"""Single source of truth for current time across SynPin.

Every module that needs "now" should call `synpin.time.now()` instead of
`datetime.now()`.  This returns the machine's local time — whatever the
server OS clock shows.  No timezone math, no config, no magic.
"""
from datetime import datetime


def now() -> datetime:
    """Return current machine time (naive, local)."""
    return datetime.now()


def now_iso() -> str:
    """Return current machine time as ISO string."""
    return now().isoformat()


def now_str() -> str:
    """Return current machine time as human-readable string."""
    return now().strftime("%Y-%m-%d %H:%M:%S")
