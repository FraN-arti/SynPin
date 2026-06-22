"""Read otdel chat history — for the main agent to check responses.

Accepts either otdel_id or otdel_name — resolves automatically.
"""
from __future__ import annotations

import os
from typing import Any

from .base import ToolResult, make_success, make_error

_API_BASE = os.environ.get("SYNPIN_API_BASE", "http://127.0.0.1:2088")


async def _resolve_otdel_id(otdel_id: str, otdel_name: str) -> tuple[str, str]:
    """Resolve otdel_id from name if needed. Returns (otdel_id, otdel_name)."""
    if otdel_id:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(f"{_API_BASE}/api/otdels/{otdel_id}")
                if res.status_code == 200:
                    data = res.json()
                    return otdel_id, data.get("name", otdel_id)
        except Exception:
            pass
        return otdel_id, otdel_id

    if otdel_name:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(f"{_API_BASE}/api/otdels")
                if res.status_code == 200:
                    data = res.json()
                    for o in data.get("departments", data.get("otdels", [])):
                        if o.get("name", "").lower() == otdel_name.lower():
                            return o.get("id", o.get("otdelid", "")), o.get("name", "")
        except Exception:
            pass

    return "", ""


async def otdel_history(params: dict[str, Any]) -> ToolResult:
    """
    Прочитать историю чата отдела.

    Позволяет главному агенту проверить:
      - Ответил ли глава отдела
      - Что обсуждают в отделе
      - Статус задач

    Параметры:
      otdel_id (str) — ID отдела (опционально, если указан otdel_name)
      otdel_name (str) — название отдела (опционально, если указан otdel_id)
      limit (int) — максимум последних сообщений (по умолчанию 20)
    """
    otdel_id = params.get("otdel_id", "")
    otdel_name = params.get("otdel_name", "")
    limit = params.get("limit", 20)

    if not otdel_id and not otdel_name:
        return make_error("otdel_id or otdel_name required")

    # Resolve
    otdel_id, resolved_name = await _resolve_otdel_id(otdel_id, otdel_name)
    if not otdel_id:
        return make_error(f"Отдел «{otdel_name}» не найден. Используй otdel_manage(list) для списка отделов.")

    try:
        import httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(
                f"{_API_BASE}/api/otdels/{otdel_id}/chat/history",
                params={"limit": limit},
            )
            if res.status_code != 200:
                return make_error(f"Failed to get history: {res.text}")

            data = res.json()
            messages = data.get("messages", [])
            total = data.get("total", 0)

            # Format for readability
            formatted = []
            for msg in messages:
                sender = msg.get("sender", msg.get("role", "unknown"))
                content = msg.get("content", "")
                timestamp = msg.get("timestamp", "")

                if sender == "main_agent":
                    prefix = "🤖 Главный агент"
                elif sender == "user":
                    prefix = "👤 Пользователь"
                elif sender == "head":
                    prefix = "👔 Глава отдела"
                else:
                    # Try to resolve agent name
                    try:
                        from ..agents.manager import get_agent
                        agent = get_agent(sender)
                        name = agent.get("name", sender) if agent else sender
                        prefix = f"🧑 {name}"
                    except Exception:
                        prefix = f"🧑 {sender}"

                formatted.append(f"[{timestamp}] {prefix}: {content}")

            return make_success({
                "otdel_id": otdel_id,
                "otdel_name": resolved_name,
                "messages_count": len(messages),
                "total": total,
                "history": formatted,
            })

    except httpx.ConnectError:
        return make_error("Cannot connect to SynPin server")
    except Exception as e:
        return make_error(f"otdel_history error: {e}")
