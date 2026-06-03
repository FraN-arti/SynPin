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
        
        # Initialize components
        self._store = MemoryStore(agent_id, data_dir)
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
    
    def add(self, target: str, content: str) -> Dict[str, Any]:
        """Add entry to memory (memory or user)."""
        result = self._store.add(target, content)
        if result.get("success"):
            # Re-index for search
            self._search.index_agent(self.agent_id)
        return result
    
    def replace(self, target: str, old_text: str, new_content: str) -> Dict[str, Any]:
        """Replace entry in memory."""
        result = self._store.replace(target, old_text, new_content)
        if result.get("success"):
            self._search.index_agent(self.agent_id)
        return result
    
    def remove(self, target: str, old_text: str) -> Dict[str, Any]:
        """Remove entry from memory."""
        result = self._store.remove(target, old_text)
        if result.get("success"):
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
