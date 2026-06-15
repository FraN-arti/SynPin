"""Memory API Router — endpoints for agent memory management.

Endpoints:
- GET  /api/memory/{agent_id}           — read agent memory
- POST /api/memory/{agent_id}/add       — add entry
- POST /api/memory/{agent_id}/replace   — replace entry
- POST /api/memory/{agent_id}/remove    — remove entry
- GET  /api/memory/{agent_id}/facts     — list facts
- POST /api/memory/{agent_id}/facts     — add fact
- GET  /api/memory/{agent_id}/facts/{filename} — read fact
- DELETE /api/memory/{agent_id}/facts/{filename} — remove fact
- POST /api/memory/{agent_id}/search    — search memory
- GET  /api/memory/{agent_id}/state     — get state
- POST /api/memory/{agent_id}/state     — set active session
- GET  /api/memory/{agent_id}/stats     — get statistics
- POST /api/memory/{agent_id}/reindex   — re-index for search
- GET  /api/config/memory               — read global memory config
- PUT  /api/config/memory               — update global memory config
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from ._base import BaseRequest

from ..memory import MemoryManager
from ..memory.store import USER_CHAR_LIMIT
# ── Shared USER Path ──────────────────────────────────────────────────────────
_shared_user_path = None
def _get_shared_user_path() -> Path:
    """Get path to global shared USER.md."""
    global _shared_user_path
    if _shared_user_path is not None:
        return _shared_user_path
    shared_dir = DATA_DIR / "shared"
    shared_dir.mkdir(parents=True, exist_ok=True)
    _shared_user_path = shared_dir / "USER.md"
    return _shared_user_path


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory"])

# ── Data Directory ───────────────────────────────────────────────────────

# Use the same DATA_DIR as tools (paths_legacy)
from ..paths_legacy import _get_data_dir_tools as _get_data_dir

DATA_DIR: Path = _get_data_dir()

# ── Manager Cache ────────────────────────────────────────────────────────

import time

_MANAGER_TTL = 300  # 5 minutes in seconds
_managers: Dict[str, MemoryManager] = {}
_manager_timestamps: Dict[str, float] = {}


def get_manager(agent_id: str) -> MemoryManager:
    """Get or create MemoryManager for an agent. Cache expires after 5 min."""
    now = time.time()
    if agent_id in _managers:
        # Check if cache is still valid
        created = _manager_timestamps.get(agent_id, 0)
        if now - created > _MANAGER_TTL:
            # Cache expired, recreate
            try:
                _managers[agent_id].close()
            except Exception:
                pass
            del _managers[agent_id]
            del _manager_timestamps[agent_id]
    if agent_id not in _managers:
        manager = MemoryManager(agent_id, DATA_DIR)
        manager.initialize()
        _managers[agent_id] = manager
        _manager_timestamps[agent_id] = now
    return _managers[agent_id]


# ── Request/Response Models ──────────────────────────────────────────────

class AddRequest(BaseRequest):
    target: str = "memory"  # "memory" or "user"
    content: str


class ReplaceRequest(BaseRequest):
    target: str = "memory"
    old_text: str
    new_content: str


class RemoveRequest(BaseRequest):
    target: str = "memory"
    old_text: str


class AddFactRequest(BaseRequest):
    topic: str
    content: str
    date: Optional[str] = None


class SearchRequest(BaseRequest):
    query: str
    file_type: Optional[str] = None
    limit: int = 10


class SetSessionRequest(BaseRequest):
    channel: str
    session_id: str
    last_position: int = 0
    last_action: str = ""
    waiting_for: Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("/user")
async def read_global_user():
    """Read the global shared USER.md profile."""
    try:
        path = _get_shared_user_path()
        if not path.exists():
            return {"success": True, "target": "user", "entries": [], "usage": "0% — 0/1,375 chars", "entry_count": 0}
        content = path.read_text(encoding="utf-8")
        entries = [e.strip() for e in content.split("\n§\n") if e.strip()]
        current = len(content)
        limit = USER_CHAR_LIMIT
        pct = min(100, int((current / limit) * 100)) if limit > 0 else 0
        return {"success": True, "target": "user", "entries": entries, "usage": f"{pct}% — {current:,}/{limit:,} chars", "entry_count": len(entries)}
    except Exception as e:
        logger.error("Failed to read user profile: %s", e)
        raise HTTPException(500, "Failed to read user profile")

@router.post("/user/add")
async def add_user_entry(req: AddRequest):
    """Add entry to global shared USER.md."""
    try:
        path = _get_shared_user_path()
        if not path.exists():
            path.write_text(req.content.strip() + "\n", encoding="utf-8")
            return {"success": True, "message": "Entry added.", "entries": [req.content.strip()]}
        import re
        content = path.read_text(encoding="utf-8")
        entries = [e.strip() for e in content.split("\n§\n") if e.strip()]
        if req.content.strip() in entries:
            return {"success": True, "message": "Entry already exists.", "entries": entries}
        new_content = content.rstrip("\n") + "\n§\n" + req.content.strip() + "\n"
        path.write_text(new_content, encoding="utf-8")
        return {"success": True, "message": "Entry added.", "entries": entries + [req.content.strip()]}
    except Exception as e:
        logger.error("Failed to add user entry: %s", e)
        raise HTTPException(500, "Failed to add user entry")

@router.post("/user/remove")
async def remove_user_entry(req: RemoveRequest):
    """Remove entry from global shared USER.md."""
    try:
        path = _get_shared_user_path()
        if not path.exists():
            return {"success": False, "error": "USER.md does not exist."}
        content = path.read_text(encoding="utf-8")
        entries = [e.strip() for e in content.split("\n§\n") if e.strip()]
        matches = [e for e in entries if req.old_text in e]
        if not matches:
            return {"success": False, "error": f"No entry matched '{req.old_text}'."}
        if len(matches) > 1 and len({e: 1 for e in matches}) > 1:
            return {"success": False, "error": "Multiple entries matched. Be more specific.", "matches": [e[:80] for e in matches]}
        entries.remove(matches[0])
        path.write_text("\n§\n".join(entries) + "\n", encoding="utf-8")
        return {"success": True, "message": "Entry removed."}
    except Exception as e:
        logger.error("Failed to remove user entry: %s", e)
        raise HTTPException(500, "Failed to remove user entry")

@router.post("/user/replace")
async def replace_user_entry(req: ReplaceRequest):
    """Replace entry in global shared USER.md."""
    try:
        path = _get_shared_user_path()
        if not path.exists():
            return {"success": False, "error": "USER.md does not exist."}
        content = path.read_text(encoding="utf-8")
        entries = [e.strip() for e in content.split("\n§\n") if e.strip()]
        matches = [i for i, e in enumerate(entries) if req.old_text in e]
        if not matches:
            return {"success": False, "error": f"No entry matched '{req.old_text}'."}
        entries[matches[0]] = req.new_content.strip()
        path.write_text("\n§\n".join(entries) + "\n", encoding="utf-8")
        return {"success": True, "message": "Entry replaced."}
    except Exception as e:
        logger.error("Failed to replace user entry: %s", e)
        raise HTTPException(500, "Failed to replace user entry")


@router.get("/{agent_id}")
async def read_agent_memory(agent_id: str, target: str = "memory"):
    """Read agent memory (memory only). USER.md is global."""
    try:
        manager = get_manager(agent_id)
        return manager.read(target)
    except Exception as e:
        logger.error("Failed to read memory for %s: %s", agent_id, e)
        raise HTTPException(500, "Failed to read agent memory")


@router.post("/{agent_id}/add")
async def add_entry(agent_id: str, req: AddRequest):
    """Add entry to agent memory."""
    try:
        manager = get_manager(agent_id)
        return manager.add(req.target, req.content)
    except Exception as e:
        logger.error("Failed to add entry for %s: %s", agent_id, e)
        raise HTTPException(500, "Failed to add entry")


@router.post("/{agent_id}/replace")
async def replace_entry(agent_id: str, req: ReplaceRequest):
    """Replace entry in agent memory."""
    try:
        manager = get_manager(agent_id)
        return manager.replace(req.target, req.old_text, req.new_content)
    except Exception as e:
        logger.error("Failed to replace entry for %s: %s", agent_id, e)
        raise HTTPException(500, "Failed to replace entry")


@router.post("/{agent_id}/remove")
async def remove_entry(agent_id: str, req: RemoveRequest):
    """Remove entry from agent memory."""
    try:
        manager = get_manager(agent_id)
        return manager.remove(req.target, req.old_text)
    except Exception as e:
        logger.error("Failed to remove entry for %s: %s", agent_id, e)
        raise HTTPException(500, "Failed to remove entry")


@router.get("/{agent_id}/facts")
async def list_facts(agent_id: str, limit: int = 50):
    """List fact files for an agent."""
    try:
        manager = get_manager(agent_id)
        return manager.list_facts(limit)
    except Exception as e:
        logger.error("Failed to list facts for %s: %s", agent_id, e)
        raise HTTPException(500, "Failed to list facts")


@router.post("/{agent_id}/facts")
async def add_fact(agent_id: str, req: AddFactRequest):
    """Add a dated fact."""
    try:
        manager = get_manager(agent_id)
        return manager.add_fact(req.topic, req.content, req.date)
    except Exception as e:
        logger.error("Failed to add fact for %s: %s", agent_id, e)
        raise HTTPException(500, "Failed to add fact")


@router.get("/{agent_id}/facts/{filename}")
async def read_fact(agent_id: str, filename: str):
    """Read a specific fact."""
    try:
        manager = get_manager(agent_id)
        return manager.read_fact(filename)
    except Exception as e:
        logger.error("Failed to read fact for %s: %s", agent_id, e)
        raise HTTPException(500, "Failed to read fact")


@router.delete("/{agent_id}/facts/{filename}")
async def remove_fact(agent_id: str, filename: str):
    """Remove a fact."""
    try:
        manager = get_manager(agent_id)
        return manager.remove_fact(filename)
    except Exception as e:
        logger.error("Failed to remove fact for %s: %s", agent_id, e)
        raise HTTPException(500, "Failed to remove fact")


@router.post("/{agent_id}/search")
async def search_memory(agent_id: str, req: SearchRequest):
    """Search across agent memory."""
    try:
        manager = get_manager(agent_id)
        results = manager.search(req.query, req.file_type, req.limit)
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error("Failed to search memory for %s: %s", agent_id, e)
        raise HTTPException(500, "Failed to search memory")


@router.get("/{agent_id}/state")
async def get_state(agent_id: str):
    """Get agent state (active sessions)."""
    try:
        manager = get_manager(agent_id)
        return {
            "active_sessions": manager.get_all_active_sessions(),
            "last_compaction": manager.get_last_compaction(),
        }
    except Exception as e:
        logger.error("Failed to get state for %s: %s", agent_id, e)
        raise HTTPException(500, "Failed to get agent state")


@router.post("/{agent_id}/state")
async def set_session(agent_id: str, req: SetSessionRequest):
    """Set active session for a channel."""
    try:
        manager = get_manager(agent_id)
        manager.set_active_session(
            req.channel,
            req.session_id,
            req.last_position,
            req.last_action,
            req.waiting_for,
        )
        return {"success": True}
    except Exception as e:
        logger.error("Failed to set session for %s: %s", agent_id, e)
        raise HTTPException(500, "Failed to set session")


@router.get("/{agent_id}/stats")
async def get_stats(agent_id: str):
    """Get memory statistics."""
    try:
        manager = get_manager(agent_id)
        return manager.get_stats()
    except Exception as e:
        logger.error("Failed to get stats for %s: %s", agent_id, e)
        raise HTTPException(500, "Failed to get stats")


@router.post("/{agent_id}/reindex")
async def reindex(agent_id: str):
    """Re-index memory for search."""
    try:
        manager = get_manager(agent_id)
        manager.reindex()
        return {"success": True, "message": "Re-indexed"}
    except Exception as e:
        logger.error("Failed to reindex for %s: %s", agent_id, e)
        raise HTTPException(500, "Failed to reindex")
