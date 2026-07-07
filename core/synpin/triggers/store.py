"""
Triggers — atomic YAML storage for per-otdel instances.

Pattern follows kanban columns.yaml / labels.yaml:
  - data/triggers/{otdel_id}.yaml — user config
  - Atomic write: write to .tmp, fsync, rename
  - Cache in memory; reload on demand
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

import yaml


TRIGGERS_DIR = Path("data/triggers")


def ensure_dir() -> Path:
    TRIGGERS_DIR.mkdir(parents=True, exist_ok=True)
    return TRIGGERS_DIR


def _path_for(otdel_id: str) -> Path:
    # Sanitize — otdel ids are user-controlled
    safe = "".join(c for c in otdel_id if c.isalnum() or c in "-_:")
    if not safe:
        raise ValueError(f"invalid otdel_id: {otdel_id!r}")
    return TRIGGERS_DIR / f"{safe}.yaml"


def load(otdel_id: str) -> dict[str, Any]:
    """Load triggers for an otdel. Returns empty structure if missing."""
    path = _path_for(otdel_id)
    if not path.exists():
        return {"otdel_id": otdel_id, "triggers": []}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "triggers" not in data:
        data["triggers"] = []
    return data


def save(otdel_id: str, data: dict[str, Any]) -> None:
    """Atomic save. Writes to .tmp then renames."""
    ensure_dir()
    data = dict(data)
    data["otdel_id"] = otdel_id
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    path = _path_for(otdel_id)
    # Write to temp file in same dir (rename is atomic on same fs)
    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def list_otdels() -> list[str]:
    """Return all otdel ids that have a triggers file."""
    ensure_dir()
    return [p.stem for p in TRIGGERS_DIR.glob("*.yaml")]


def all_instances() -> list[dict[str, Any]]:
    """Load every instance across all otdels. Used by engine on boot."""
    out: list[dict[str, Any]] = []
    for oid in list_otdels():
        data = load(oid)
        for t in data.get("triggers", []):
            t["_otdel_id"] = oid
            out.append(t)
    return out
