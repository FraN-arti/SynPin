"""MemoryManager — orchestrates memory components for an agent.

Single integration point for the agent engine. Manages:
- MemoryStore (MEMORY.md, USER.md, facts/)
- FrozenSnapshot (system prompt stability)
- AgentState (state.json bookmarks)
- MemorySearch (FTS5 full-text search)

Usage:
    manager = MemoryManager(agent_id="architect", data_dir=Path("~/.synpin/data"))
    manager.initialize()  # loads from disk, creates snapshot
    
    # In system prompt:
    system_prompt += manager.get_system_prompt_block()
    
    # During session:
    manager.add("memory", "new pattern")
    results = manager.search("auth middleware")
    
    # State management:
    manager.set_active_session("engineering", "session_123", last_position=42)
    session = manager.get_active_session("engineering")
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .store import MemoryStore
from .frozen_snapshot import FrozenSnapshot
from .state import AgentState
from .search import MemorySearch

logger = logging.getLogger(__name__)


class MemoryManager:
    """Orchestrates all memory components for an agent."""

    def __init__(
        self,
        agent_id: str,
        data_dir: Path,
        search_db_path: Optional[Path] = None,
    ):
        self.agent_id = agent_id
        self.data_dir = Path(data_dir)

        # Read limits from config (memory.yaml). Falls back to module
        # constants if config is missing or malformed.
        try:
            from ..config.manager import get_memory_limits
            limits = get_memory_limits()
            memory_char_limit = int(limits["memory_max_chars"])
            user_char_limit = int(limits["user_max_chars"])
            self._auto_refactor = bool(limits.get("auto_refactor", False))
            self._memory_enabled = bool(limits.get("memory_enabled", True))
        except Exception:
            from .store import MEMORY_CHAR_LIMIT, USER_CHAR_LIMIT
            memory_char_limit = MEMORY_CHAR_LIMIT
            user_char_limit = USER_CHAR_LIMIT
            self._auto_refactor = False
            self._memory_enabled = True

        # Initialize components
        self._store = MemoryStore(
            agent_id, data_dir,
            memory_char_limit=memory_char_limit,
            user_char_limit=user_char_limit,
        )
        self._snapshot = FrozenSnapshot(agent_id, self._store)
        self._state = AgentState(agent_id, data_dir)
        self._search = MemorySearch(data_dir, search_db_path)

        self._initialized = False
    
    def initialize(self):
        """Load from disk and create frozen snapshot.
        
        Call this once at agent startup.
        """
        # Load memory from disk
        self._store.load_from_disk()
        
        # Create frozen snapshot
        self._snapshot.freeze()
        
        # Load state
        self._state.load()
        
        # Index for search
        self._search.index_agent(self.agent_id)
        
        self._initialized = True
        logger.info("MemoryManager initialized for %s", self.agent_id)
    
    # ── System Prompt ────────────────────────────────────────────────────
    
    def get_system_prompt_block(self) -> str:
        """Return frozen memory context for system prompt injection."""
        if not self._initialized:
            return ""

        parts = []

        # USER block first — agents see user profile before their own notes
        user_block = self._snapshot.get_user_block()
        if user_block:
            parts.append(user_block)

        memory_block = self._snapshot.get_memory_block()
        if memory_block:
            parts.append(memory_block)

        facts_block = self._snapshot.get_facts_block()
        if facts_block:
            parts.append(facts_block)

        return "\n\n".join(parts)
    
    # ── Memory CRUD ──────────────────────────────────────────────────────

    def _refresh_snapshot(self) -> None:
        """Re-capture the system-prompt snapshot from current memory state.

        Called after every write so the next system-prompt assembly sees
        fresh data. The "frozen snapshot" trade-off — that mid-session
        writes do not invalidate the prefix cache — does not apply here:
        SynPin reuses one MemoryManager across multiple sessions (5-minute
        cache TTL), so a snapshot captured once at startup would block
        data the agent just wrote from being visible in the next request.
        For models in actual use (9router/hermes-agent, deepseek-v4-flash,
        etc.) the cost of an occasional cache invalidation is negligible
        compared to the bug of agents never seeing their own writes.
        """
        self._snapshot.freeze()

    def add(self, target: str, content: str) -> Dict[str, Any]:
        """Add entry to memory (memory or user).

        If the write would exceed the char limit AND auto_refactor is
        enabled, try compacting existing entries first (remove duplicates,
        drop oldest), then retry once. Falls back to the original
        "limit exceeded" error if compaction can't free enough room.
        """
        result = self._store.add(target, content)

        if not result.get("success") and self._auto_refactor:
            # Compaction strategy: shrink existing entries to leave room
            # for the incoming content.
            limit = (
                self._store.memory_char_limit
                if target == "memory"
                else self._store.user_char_limit
            )
            compacted = self._store._auto_compact(target, limit, incoming_chars=len(content))
            if compacted.get("compacted"):
                # Retry the add now that entries may be shorter
                result = self._store.add(target, content)
                if result.get("success"):
                    result["refactored"] = True

        if result.get("success"):
            self._refresh_snapshot()
            self._search.index_agent(self.agent_id)
        return result

    def replace(self, target: str, old_text: str, new_content: str) -> Dict[str, Any]:
        """Replace entry in memory."""
        result = self._store.replace(target, old_text, new_content)
        if result.get("success"):
            self._refresh_snapshot()
            self._search.index_agent(self.agent_id)
        return result

    def remove(self, target: str, old_text: str) -> Dict[str, Any]:
        """Remove entry from memory."""
        result = self._store.remove(target, old_text)
        if result.get("success"):
            self._refresh_snapshot()
            self._search.index_agent(self.agent_id)
        return result
    
    def read(self, target: str) -> Dict[str, Any]:
        """Read all entries for a target."""
        return self._store.read(target)
    
    # ── Facts ────────────────────────────────────────────────────────────
    
    def add_fact(self, topic: str, content: str, date: Optional[str] = None) -> Dict[str, Any]:
        """Add a dated fact."""
        result = self._store.add_fact(topic, content, date)
        if result.get("success"):
            self._refresh_snapshot()
            self._search.index_agent(self.agent_id)
        return result
    
    def list_facts(self, limit: int = 50) -> Dict[str, Any]:
        """List fact files."""
        return self._store.list_facts(limit)
    
    def read_fact(self, filename: str) -> Dict[str, Any]:
        """Read a specific fact."""
        return self._store.read_fact(filename)
    
    def remove_fact(self, filename: str) -> Dict[str, Any]:
        """Remove a fact."""
        result = self._store.remove_fact(filename)
        if result.get("success"):
            self._search.index_agent(self.agent_id)
        return result
    
    # ── Search ───────────────────────────────────────────────────────────
    
    def search(
        self,
        query: str,
        file_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search across agent's memory."""
        return self._search.search(
            query=query,
            agent_id=self.agent_id,
            file_type=file_type,
            limit=limit,
        )
    
    def search_all(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search across all agents and shared memory."""
        return self._search.search(query=query, limit=limit)
    
    # ── State Management ─────────────────────────────────────────────────
    
    def get_active_session(self, channel: str) -> Optional[Dict[str, Any]]:
        """Get the active session for a channel."""
        return self._state.get_active_session(channel)
    
    def set_active_session(
        self,
        channel: str,
        session_id: str,
        last_position: int = 0,
        last_action: str = "",
        waiting_for: Optional[str] = None,
    ):
        """Set or update the active session for a channel."""
        self._state.set_active_session(
            channel, session_id, last_position, last_action, waiting_for
        )
    
    def update_position(self, channel: str, last_position: int, last_action: str = ""):
        """Update the position for an active session."""
        self._state.update_position(channel, last_position, last_action)
    
    def clear_channel(self, channel: str):
        """Clear the active session for a channel."""
        self._state.clear_channel(channel)
    
    def get_all_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get all active sessions."""
        return self._state.get_all_active()
    
    # ── Compaction ───────────────────────────────────────────────────────
    
    def set_last_compaction(self, timestamp: Optional[str] = None):
        """Record when the last compaction happened."""
        self._state.set_last_compaction(timestamp)
    
    def get_last_compaction(self) -> Optional[str]:
        """Get the last compaction timestamp."""
        return self._state.get_last_compaction()
    
    # ── Maintenance ──────────────────────────────────────────────────────
    
    def reindex(self):
        """Re-index all memory files for search."""
        self._search.index_agent(self.agent_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "agent_id": self.agent_id,
            "memory_entries": len(self._store.memory_entries),
            "user_entries": len(self._store.user_entries),
            "memory_usage": f"{self._store._char_count('memory')}/{self._store.memory_char_limit}",
            "user_usage": f"{self._store._char_count('user')}/{self._store.user_char_limit}",
            "active_sessions": len(self._state.get_all_active()),
            "search_stats": self._search.get_stats(),
        }
    
    def close(self):
        """Cleanup resources."""
        self._search.close()


# ── Manager Cache ──────────────────────────────────────────────────────────
#
# Process-wide cache of MemoryManager instances, keyed by agent_id.
# TTL is 5 minutes — long enough to amortize disk reads across multiple
# tool calls in one chat turn, short enough that the next session sees
# fresh data without restart.
#
# Used by:
#   - api/memory_router.py   (HTTP API)
#   - tools/memory_*.py      (agent tool calls)
#   - chat/router.py:_load_memory_block (system prompt assembly)
#
# All three share the same cache so a write via API is immediately
# visible to the next tool call without waiting for TTL.

import threading
import time as _time

_MANAGER_TTL = 300  # 5 minutes
_managers: dict[str, "MemoryManager"] = {}
_manager_timestamps: dict[str, float] = {}
_manager_lock = threading.Lock()


def get_manager(agent_id: str, data_dir=None) -> "MemoryManager":
    """Get or create a cached MemoryManager for an agent.

    Cache expires after _MANAGER_TTL seconds; the next call after expiry
    rebuilds from disk.

    Args:
        agent_id: Agent slug (e.g. "7xr5o34o").
        data_dir: Optional explicit data dir. Defaults to synpin.paths.get_data_dir().

    Returns:
        Initialized MemoryManager instance.
    """
    now = _time.time()

    # Fast path: check cache without lock first
    if agent_id in _managers:
        created = _manager_timestamps.get(agent_id, 0)
        if now - created <= _MANAGER_TTL:
            return _managers[agent_id]

    # Slow path: rebuild under lock
    with _manager_lock:
        # Re-check after acquiring lock (double-checked locking)
        if agent_id in _managers:
            created = _manager_timestamps.get(agent_id, 0)
            if now - created > _MANAGER_TTL:
                # Expired — close old, replace
                try:
                    _managers[agent_id].close()
                except Exception:
                    pass
                del _managers[agent_id]
                _manager_timestamps.pop(agent_id, None)

        if agent_id not in _managers:
            if data_dir is None:
                from ..paths import get_data_dir
                data_dir = get_data_dir()
            manager = MemoryManager(agent_id, data_dir)
            manager.initialize()
            _managers[agent_id] = manager
            _manager_timestamps[agent_id] = now

    return _managers[agent_id]


def invalidate_manager(agent_id: str) -> None:
    """Drop a cached manager (force next call to re-read from disk).

    Called after filesystem mutations that bypass MemoryManager (e.g.
    test fixtures, manual file edits, migration scripts).
    """
    with _manager_lock:
        if agent_id in _managers:
            try:
                _managers[agent_id].close()
            except Exception:
                pass
            del _managers[agent_id]
            _manager_timestamps.pop(agent_id, None)


def clear_cache() -> None:
    """Drop all cached managers. Used by tests."""
    with _manager_lock:
        for m in _managers.values():
            try:
                m.close()
            except Exception:
                pass
        _managers.clear()
        _manager_timestamps.clear()


def get_cache_stats() -> dict:
    """Inspect the manager cache (for diagnostics/tests)."""
    with _manager_lock:
        now = _time.time()
        return {
            "size": len(_managers),
            "ttl_seconds": _MANAGER_TTL,
            "agents": list(_managers.keys()),
            "ages_seconds": {
                aid: round(now - ts, 1) for aid, ts in _manager_timestamps.items()
            },
        }
