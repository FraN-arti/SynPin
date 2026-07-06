"""
Connection ref resolution — turn a stored ref into a real entity.

For `otdel:<id>`, resolution is trivial (the id is the otdel slug).
For `agent:primary`, the slug is dynamic — the user can change the
primary agent in `agents.yaml` at any time, and connections that
reference the primary slot should always point to whichever agent
currently has `is_primary: True`.
"""
from __future__ import annotations

import logging
from .refs import RefKind, parse_ref

logger = logging.getLogger("synpin.connections.resolve")


class ResolvedRef:
    """A ref that has been resolved to a concrete entity.

    `kind` and `id` are always the concrete (post-resolution) form.
    For primary-agent refs, `id` is the current primary agent's slug.
    """

    def __init__(self, kind: RefKind, ref_id: str, display_name: str = "") -> None:
        self.kind = kind
        self.id = ref_id
        self.display_name = display_name or ref_id

    def __repr__(self) -> str:
        return f"ResolvedRef(kind={self.kind!r}, id={self.id!r})"


def _current_primary_agent() -> str | None:
    """Look up the slug of whichever agent is currently primary."""
    try:
        from synpin.agents.manager import load_agents
        data = load_agents() or {}
        agents = data.get("agents", []) if isinstance(data, dict) else data
    except Exception as e:  # noqa: BLE001
        logger.debug("resolve: could not load agents: %s", e)
        return None
    for a in agents:
        if isinstance(a, dict) and a.get("is_primary"):
            return a.get("slug") or a.get("agentid") or None
    return None


def _otdel_name(otdel_id: str) -> str:
    try:
        from synpin.agents.manager import load_otdels
        raw = load_otdels() or []
        otdels = raw.get("otdels", []) if isinstance(raw, dict) else raw
        for o in otdels:
            if isinstance(o, dict) and o.get("otdelid") == otdel_id:
                return o.get("name", otdel_id)
    except Exception as e:  # noqa: BLE001
        logger.debug("resolve: could not load otdels: %s", e)
    return otdel_id


def resolve_ref(ref: str) -> ResolvedRef:
    """Resolve a stored ref to a concrete entity.

    For `agent:primary` returns the current primary agent's slug.
    For `otdel:<id>` returns the otdel id (no transformation).
    """
    kind, ref_id = parse_ref(ref)
    if kind == "agent" and ref_id == "primary":
        slug = _current_primary_agent()
        if slug:
            return ResolvedRef("agent", slug, display_name="Главный агент")
        # No primary configured — return the ref unchanged so callers
        # can show a useful error rather than a crash.
        return ResolvedRef("agent", "primary", display_name="Главный агент (не назначен)")
    if kind == "otdel":
        return ResolvedRef("otdel", ref_id, display_name=_otdel_name(ref_id))
    # Unknown kind — return as-is.
    return ResolvedRef(kind, ref_id)
