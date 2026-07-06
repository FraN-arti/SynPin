"""
Connection refs — encode (kind, id) as a string.

Why refs:
- Connections can target an `otdel:<id>` or the `agent:primary` (main agent).
- We store them as a single string in the existing `from_otdel` /
  `to_otdel` fields for backward compatibility (no YAML migration needed).
- Format: `"<kind>:<id>"` for new entries; legacy bare IDs are treated
  as otdel refs by `parse_ref()`.

Examples:
    "otdel:otdel-1749"  → ("otdel", "otdel-1749")
    "agent:primary"    → ("agent", "primary")
    "otdel-1749"       → ("otdel", "otdel-1749")   # legacy, no prefix
"""
from __future__ import annotations

from typing import Literal


RefKind = Literal["otdel", "agent"]


def make_ref(kind: RefKind, ref_id: str) -> str:
    """Encode a connection endpoint as a single string."""
    return f"{kind}:{ref_id}"


def parse_ref(ref: str) -> tuple[RefKind, str]:
    """Decode a ref string into (kind, id). Legacy bare IDs default to otdel.

    Raises ValueError on empty or malformed input.
    """
    if not ref:
        raise ValueError("empty connection ref")
    if ":" in ref:
        kind, _, ref_id = ref.partition(":")
        if kind in ("otdel", "agent") and ref_id:
            return kind, ref_id  # type: ignore[return-value]
        raise ValueError(f"invalid connection ref: {ref!r}")
    # Legacy format — bare ID, treat as otdel.
    return "otdel", ref


def is_primary_agent_ref(ref: str) -> bool:
    """True if this ref points to the dynamic primary agent slot."""
    try:
        kind, ref_id = parse_ref(ref)
    except ValueError:
        return False
    return kind == "agent" and ref_id == "primary"


def normalize_ref(ref: str) -> str:
    """Re-encode a ref so legacy bare IDs become explicit `otdel:` refs."""
    kind, ref_id = parse_ref(ref)
    return make_ref(kind, ref_id)
