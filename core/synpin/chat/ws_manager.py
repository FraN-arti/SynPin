"""WebSocket Connection Manager — single WS per client, multiplexed messaging.

One user may have several open WS connections (e.g. multiple browser tabs,
strict-mode dev hot-reload). We keep a set of sockets per user_id, and
disconnect removes only the socket that closed, never the whole user.
"""
import asyncio
import json
import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections.

    One user can hold multiple concurrent WS connections (multi-tab,
    dev HMR, etc). Messages are multiplexed by 'type' field.
    """

    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, user_id: str = "default") -> None:
        """Accept a new WebSocket connection."""
        await ws.accept()
        async with self._lock:
            bucket = self._connections.setdefault(user_id, set())
            bucket.add(ws)
            total = sum(len(b) for b in self._connections.values())
        logger.info(
            "WS connected: %s (user sockets=%d, total=%d)",
            user_id, len(self._connections[user_id]), total,
        )

        # Check if session reset was missed while offline
        try:
            from .session_reset import _should_reset, _get_sessions_config, _reset_sessions
            cfg = _get_sessions_config()
            if cfg and _should_reset(cfg):
                logger.info("[ws] Session reset was missed — triggering on connect")
                _reset_sessions()
        except Exception as e:
            logger.debug("[ws] Session reset check skipped: %s", e)

    def disconnect(self, ws: WebSocket, user_id: str = "default") -> None:
        """Remove a specific WS connection (the one that just closed)."""
        bucket = self._connections.get(user_id)
        if not bucket:
            return
        bucket.discard(ws)
        if not bucket:
            del self._connections[user_id]
        total = sum(len(b) for b in self._connections.values())
        logger.info(
            "WS disconnected: %s (user sockets=%d, total=%d)",
            user_id, len(self._connections.get(user_id, set())), total,
        )

    async def send(self, user_id: str, message: dict):
        """Send a JSON message to all sockets of a given user."""
        payload = json.dumps(message, ensure_ascii=False)
        for ws in list(self._connections.get(user_id, set())):
            if ws.client_state.name != "CONNECTED":
                # FastAPI/Starlette already closed the socket (client
                # disconnected). The next send_text would raise
                # 'Unexpected ASGI message websocket.send, after sending
                # websocket.close'. Drop silently — disconnect() will
                # be called by the receive loop in the router.
                self.disconnect(ws, user_id)
                continue
            try:
                await ws.send_text(payload)
            except Exception as e:
                logger.warning("WS send failed for %s: %s", user_id, e)
                self.disconnect(ws, user_id)

    async def broadcast(self, message: dict):
        """Send a JSON message to ALL connected clients, on every open socket."""
        dead: list[tuple[str, WebSocket]] = []
        for user_id, bucket in list(self._connections.items()):
            for ws in list(bucket):
                try:
                    await ws.send_text(json.dumps(message, ensure_ascii=False))
                except Exception:
                    dead.append((user_id, ws))
        for user_id, ws in dead:
            self.disconnect(ws, user_id)

    @property
    def active_count(self) -> int:
        return sum(len(b) for b in self._connections.values())


# Singleton
ws_manager = ConnectionManager()
