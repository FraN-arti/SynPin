"""AgentState — bookmarks per agent per channel.


state.json tracks where the agent left off
enabling quick recovery after restart.

Structure:
{
  "active_sessions": {
    "engineering": {
      "session_id": "2026-06-03_api-redesign",
      "last_position": 42,
      "last_action": "Решили использовать REST",
      "waiting_for": "ответ от developer"
    },
    "direct": {
      "session_id": "2026-06-03_chat-with-artur",
      "last_position": 8,
      "last_action": "Обсуждали архитектуру памяти",
      "waiting_for": null
    }
  },
  "last_compaction": "2026-06-03T12:00:00"
}

Flow:
1. Agent reads state.json at startup
2. Knows exactly where it left off in each channel
3. Updates state.json after each action
4. On restart, reads state.json and continues
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional
from ..time import now as _now

logger = logging.getLogger(__name__)


class AgentState:
    """Manages agent bookmarks (state.json) for restart recovery."""
    
    def __init__(self, agent_id: str, data_dir: Path):
        self.agent_id = agent_id
        self.state_dir = Path(data_dir) / "agents" / agent_id
        self.state_path = self.state_dir / "state.json"
        
        # In-memory state
        self._state: Dict[str, Any] = {
            "active_sessions": {},
            "last_compaction": None,
        }
        
        # Ensure directory exists
        self.state_dir.mkdir(parents=True, exist_ok=True)
    
    def load(self):
        """Load state from disk."""
        if not self.state_path.exists():
            logger.info("No state.json for %s, starting fresh", self.agent_id)
            return
        
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                self._state = json.load(f)
            logger.info(
                "State loaded for %s: %d active sessions",
                self.agent_id,
                len(self._state.get("active_sessions", {})),
            )
        except Exception as e:
            logger.error("Failed to load state for %s: %s", self.agent_id, e)
            self._state = {"active_sessions": {}, "last_compaction": None}
    
    def save(self):
        """Save state to disk atomically."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.state_dir), suffix=".tmp", prefix=".state_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, str(self.state_path))
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    
    # ── Session Management ───────────────────────────────────────────────
    
    def get_active_session(self, channel: str) -> Optional[Dict[str, Any]]:
        """Get the active session for a channel."""
        return self._state.get("active_sessions", {}).get(channel)
    
    def set_active_session(
        self,
        channel: str,
        session_id: str,
        last_position: int = 0,
        last_action: str = "",
        waiting_for: Optional[str] = None,
    ):
        """Set or update the active session for a channel."""
        if "active_sessions" not in self._state:
            self._state["active_sessions"] = {}
        
        self._state["active_sessions"][channel] = {
            "session_id": session_id,
            "last_position": last_position,
            "last_action": last_action,
            "waiting_for": waiting_for,
            "updated_at": _now().isoformat(),
        }
        self.save()
    
    def update_position(self, channel: str, last_position: int, last_action: str = ""):
        """Update the position for an active session."""
        session = self.get_active_session(channel)
        if session:
            session["last_position"] = last_position
            if last_action:
                session["last_action"] = last_action
            session["updated_at"] = _now().isoformat()
            self.save()
    
    def clear_channel(self, channel: str):
        """Clear the active session for a channel."""
        if "active_sessions" in self._state:
            self._state["active_sessions"].pop(channel, None)
            self.save()
    
    def get_all_active(self) -> Dict[str, Dict[str, Any]]:
        """Get all active sessions."""
        return self._state.get("active_sessions", {})
    
    # ── Compaction ───────────────────────────────────────────────────────
    
    def set_last_compaction(self, timestamp: Optional[str] = None):
        """Record when the last compaction happened."""
        self._state["last_compaction"] = timestamp or _now().isoformat()
        self.save()
    
    def get_last_compaction(self) -> Optional[str]:
        """Get the last compaction timestamp."""
        return self._state.get("last_compaction")
    
    # ── Serialization ────────────────────────────────────────────────────
    
    def to_dict(self) -> Dict[str, Any]:
        """Export state as dict."""
        return self._state.copy()
    
    def from_dict(self, data: Dict[str, Any]):
        """Import state from dict."""
        self._state = data
        self.save()
