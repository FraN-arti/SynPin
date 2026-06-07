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

    async def connect(self, ws: WebSocket, user_id: str = "default"):
        """Accept and register a WebSocket connection."""
        await ws.accept()
        # Close existing connection if any (one per user)
        old = self._connections.pop(user_id, None)
        if old:
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
