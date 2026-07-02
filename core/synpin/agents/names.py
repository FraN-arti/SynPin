"""Runtime name resolution for departments and agents.

Single source of truth for reading human-readable names from YAML files.
Used by both projects/router.py (project enrichment) and agents/manager.py
(otdel enrichment) so the parsing logic doesn't drift.

Functions:
    read_otdel(otdelid) -> dict | None
        Read data/otdels/{id}/otdel.yaml as a flat dict.
        Handles simple scalars plus a YAML inline/block list under `workers`.

    read_otdel_name(otdelid) -> str | None
        Read just the department name from otdel.yaml.

    read_agent_name(agentid) -> str | None
        Read just the agent name from agent.yaml.

All functions are defensive: any I/O or parse error returns None instead
of raising. This is a runtime-only enrichment — failure to resolve a name
must never break the request that triggered the enrichment.
"""
from __future__ import annotations

from ..paths import get_otdels_dir, get_agents_dir


def read_otdel(otdelid: str) -> dict | None:
    """Read data/otdels/{id}/otdel.yaml into a flat dict.

    Handles simple scalars plus a YAML inline list under `workers` (the
    only nested field needed for project payloads). Cheap one-shot parse.
    """
    try:
        path = get_otdels_dir() / otdelid / "otdel.yaml"
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8")
        out: dict = {}
        workers: list[str] = []
        in_workers = False
        for raw in text.splitlines():
            line = raw.rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if not in_workers and ":" in stripped:
                key, _, value = stripped.partition(":")
                key = key.strip()
                value = value.strip()
                if key == "workers":
                    in_workers = True
                    # Flow-style list on the same line: workers: [a, b]
                    if value.startswith("[") and value.endswith("]"):
                        workers = [
                            w.strip().strip("'\"")
                            for w in value[1:-1].split(",")
                            if w.strip()
                        ]
                        out["workers"] = workers
                        in_workers = False
                    continue
                if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
                    value = value[1:-1]
                out[key] = value
            elif in_workers and stripped.startswith("-"):
                item = stripped.lstrip("-").strip()
                if item.startswith(("'", '"')) and item.endswith(("'", '"')) and len(item) >= 2:
                    item = item[1:-1]
                if item:
                    workers.append(item)
        if workers or "workers" not in out:
            out["workers"] = workers
        # Strip the sentinel if no items accumulated
        if isinstance(out.get("workers"), str):
            out["workers"] = []
        return out
    except Exception:
        return None


def read_otdel_name(otdelid: str) -> str | None:
    """Read department (otdel) name from data/otdels/{id}/otdel.yaml."""
    try:
        otdel_file = get_otdels_dir() / otdelid / "otdel.yaml"
        if not otdel_file.exists():
            return None
        for line in otdel_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("name:"):
                value = stripped[len("name:"):].strip()
                if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
                    value = value[1:-1]
                return value or None
        return None
    except Exception:
        return None


def read_agent_name(agentid: str) -> str | None:
    """Read agent name from data/agents/{id}/agent.yaml."""
    try:
        agent_file = get_agents_dir() / agentid / "agent.yaml"
        if not agent_file.exists():
            return None
        for line in agent_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("name:"):
                value = stripped[len("name:"):].strip()
                if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
                    value = value[1:-1]
                return value or None
        return None
    except Exception:
        return None