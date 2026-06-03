"""Frozen Snapshot — system prompt stability for prefix cache.

Concept from Hermes: the system prompt is frozen at session start and never
changes mid-session. Mid-session writes update files on disk immediately
(durable) but do NOT change the system prompt — this preserves the prefix
cache for the entire session.

Usage:
    snapshot = FrozenSnapshot(agent_id, memory_store)
    snapshot.freeze()  # call at session start
    
    # In system prompt:
    system_prompt += snapshot.get_memory_block()
    system_prompt += snapshot.get_user_block()
    
    # During session — writes go to disk, not to snapshot
    memory_store.add("memory", "new entry")
    # snapshot.get_memory_block() still returns the frozen version
    
    # At session end:
    snapshot.unfreeze()  # optional, for cleanup
"""

import logging
from typing import Dict, Optional

from .store import MemoryStore

logger = logging.getLogger(__name__)


class FrozenSnapshot:
    """Manages frozen system prompt content for an agent.
    
    The snapshot is captured once at freeze() time and remains stable
    throughout the session. This ensures:
    1. System prompt is identical across all turns → prefix cache hits
    2. Mid-session memory writes don't invalidate the cache
    3. Tool responses show live state (not frozen)
    """
    
    def __init__(self, agent_id: str, memory_store: MemoryStore):
        self.agent_id = agent_id
        self._store = memory_store
        self._frozen: bool = False
        self._snapshot: Dict[str, str] = {"memory": "", "user": ""}
        self._facts_snapshot: str = ""
    
    def freeze(self):
        """Capture frozen snapshot from current memory state.
        
        Call this once at session start, AFTER load_from_disk().
        """
        # Capture MEMORY.md and USER.md snapshots
        self._snapshot["memory"] = self._store.format_for_system_prompt("memory") or ""
        self._snapshot["user"] = self._store.format_for_system_prompt("user") or ""
        
        # Capture recent facts
        self._facts_snapshot = self._build_facts_block()
        
        self._frozen = True
        logger.info(
            "Frozen snapshot captured for %s: %d + %d chars",
            self.agent_id,
            len(self._snapshot["memory"]),
            len(self._snapshot["user"]),
        )
    
    def unfreeze(self):
        """Clear the frozen snapshot. Optional, for cleanup."""
        self._frozen = False
        self._snapshot = {"memory": "", "user": ""}
        self._facts_snapshot = ""
        logger.info("Frozen snapshot cleared for %s", self.agent_id)
    
    @property
    def is_frozen(self) -> bool:
        return self._frozen
    
    def get_memory_block(self) -> Optional[str]:
        """Return frozen MEMORY.md block for system prompt injection.
        
        Returns None if empty. This is the FROZEN version — mid-session
        writes do not affect it.
        """
        if not self._frozen:
            logger.warning("get_memory_block() called before freeze()")
            return None
        block = self._snapshot["memory"]
        return block if block else None
    
    def get_user_block(self) -> Optional[str]:
        """Return frozen USER.md block for system prompt injection."""
        if not self._frozen:
            logger.warning("get_user_block() called before freeze()")
            return None
        block = self._snapshot["user"]
        return block if block else None
    
    def get_facts_block(self) -> Optional[str]:
        """Return recent facts block for system prompt injection."""
        if not self._frozen:
            return None
        return self._facts_snapshot if self._facts_snapshot else None
    
    def get_full_context(self) -> str:
        """Return complete frozen context for system prompt."""
        parts = []
        
        memory_block = self.get_memory_block()
        if memory_block:
            parts.append(memory_block)
        
        user_block = self.get_user_block()
        if user_block:
            parts.append(user_block)
        
        facts_block = self.get_facts_block()
        if facts_block:
            parts.append(facts_block)
        
        return "\n\n".join(parts)
    
    def _build_facts_block(self) -> str:
        """Build a block of recent facts for system prompt."""
        result = self._store.list_facts(limit=10)
        if not result.get("success") or not result.get("facts"):
            return ""
        
        lines = ["RECENT FACTS (dated decisions):"]
        for fact in result["facts"][:5]:  # Top 5 most recent
            filename = fact["filename"]
            # Extract date and topic from filename
            parts = filename.replace(".md", "").split("_", 1)
            if len(parts) == 2:
                date, topic = parts
                lines.append(f"- {date}: {topic.replace('_', ' ')}")
        
        return "\n".join(lines)
