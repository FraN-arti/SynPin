"""WebSocket Connection Manager — single WS per client, multiplexed messaging."""

import json
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections.
    
    One connection per user_id. Messages are multiplexed by 'type' field.
    """

    def __init__(self):
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, ws: WebSocket, user_id: str = "default") -> None:
        """Accept a new WebSocket connection."""
        await ws.accept()
        self._connections[user_id] = ws
        self._connection_order.append(user_id)
        logger.info(f"[ws] Client connected: {user_id} (total: {len(self._connections)})")

        # Check if session reset was missed while offline
        try:
            from .session_reset import _should_reset, _get_sessions_config, _reset_sessions
            cfg = _get_sessions_config()
            if _should_reset(cfg):
                logger.info("[ws] Session reset was missed — triggering on connect")
                _reset_sessions()
        except Exception:
            pass
            try:
                await old.close(code=4001, reason="replaced by new connection")
            except Exception:
                pass
        self._connections[user_id] = ws
        logger.info("WS connected: %s (total: %d)", user_id, len(self._connections))

    def disconnect(self, user_id: str):
        """Remove a WebSocket connection."""
        self._connections.pop(user_id, None)
        logger.info("WS disconnected: %s (total: %d)", user_id, len(self._connections))

    async def send(self, user_id: str, message: dict):
        """Send a JSON message to a connected client."""
        ws = self._connections.get(user_id)
        if not ws:
            return
        try:
            await ws.send_text(json.dumps(message, ensure_ascii=False))
        except Exception as e:
            logger.warning("WS send failed for %s: %s", user_id, e)
            self.disconnect(user_id)

    async def broadcast(self, message: dict):
        """Send a JSON message to ALL connected clients."""
        disconnected = []
        for user_id, ws in self._connections.items():
            try:
                await ws.send_text(json.dumps(message, ensure_ascii=False))
            except Exception:
                disconnected.append(user_id)
        for uid in disconnected:
            self.disconnect(uid)

    @property
    def active_count(self) -> int:
        return len(self._connections)


# Singleton
ws_manager = ConnectionManager()
