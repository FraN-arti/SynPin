"""Persistent memory system for agents.

Components:
- MemoryStore: bounded curated memory with file persistence
- FrozenSnapshot: system prompt stability for prefix cache
- AgentState: bookmarks per agent per channel
- MemorySearch: FTS5 full-text search
- MemoryManager: orchestrates all components

Usage:
    from synpin.memory import MemoryManager
    
    manager = MemoryManager(agent_id="architect", data_dir=Path("~/.synpin/data"))
    manager.initialize()
    
    # System prompt
    system_prompt += manager.get_system_prompt_block()
    
    # CRUD
    manager.add("memory", "new pattern")
    manager.add_fact("port-2099", "Use port 2099 for dev")
    
    # Search
    results = manager.search("auth middleware")
    
    # State
    manager.set_active_session("engineering", "session_123")
"""

from .store import MemoryStore, FileLock
from .frozen_snapshot import FrozenSnapshot
from .state import AgentState
from .search import MemorySearch
from .manager import MemoryManager

__all__ = [
    "MemoryStore",
    "FileLock",
    "FrozenSnapshot",
    "AgentState",
    "MemorySearch",
    "MemoryManager",
]
