"""Send a message from the main agent to an otdel's chat.

Waits for the head agent's response and returns it — enabling
multi-round dialogue between the main agent and a department.

Accepts either otdel_id or otdel_name — resolves automatically.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .base import ToolResult, make_success, make_error
from ._registry import register_tool

logger = logging.getLogger(__name__)


async def _resolve_otdel_id(otdel_id: str, otdel_name: str) -> tuple[str, str]:
    """Resolve otdel_id from name if needed. Returns (otdel_id, otdel_name).

    Only accepts IDs that exist in the otdels config — ghost IDs are rejected.
    """
    from ..agents.manager import get_otdel, load_otdels

    if otdel_id:
        otdel = get_otdel(otdel_id)
        if otdel:
            return otdel_id, otdel.get("name", otdel_id)
        return "", ""  # Reject unknown IDs — don't create ghost otdels

    if otdel_name:
        otdels = load_otdels()
        name_lower = otdel_name.lower()
        if isinstance(otdels, list):
            for o in otdels:
                if o.get("name", "").lower() == name_lower:
                    return o.get("otdelid", ""), o.get("name", "")
        elif isinstance(otdels, dict):
            for o in otdels.get("otdels", []):
                if o.get("name", "").lower() == name_lower:
                    return o.get("otdelid", ""), o.get("name", "")

    return "", ""


@register_tool(
    name='otdel_message',
    description='Отправить сообщение в чат отдела от имени главного агента и получить ответ главы. Ждёт обработки (делегирование, оценка, автопилот) и возвращает итоговый ответ. Принимает otdel_id ИЛИ otdel_name. Только для главного агента.',
    category='other',
    scope='primary',
    dangerous=False,
)
async def otdel_message(params: dict[str, Any]) -> ToolResult:
    """
    Отправить сообщение в чат отдела и получить ответ главы.

    Использует полный pipeline: глава может делегировать работникам,
    оценивать, итерировать через автопилот. Возвращает итоговый ответ.

    Параметры:
      otdel_id (str) — ID отдела (опционально, если указан otdel_name)
      otdel_name (str) — название отдела (опционально, если указан otdel_id)
      message (str) — текст сообщения (обязательно)
    """
    otdel_id = params.get("otdel_id", "")
    otdel_name = params.get("otdel_name", "")
    message = params.get("message", "")

    if not otdel_id and not otdel_name:
        return make_error("otdel_id or otdel_name required")
    if not message:
        return make_error("message required")

    # Resolve otdel_id from name if needed
    otdel_id, resolved_name = await _resolve_otdel_id(otdel_id, otdel_name)
    if not otdel_id:
        return make_error(f"Отдел «{otdel_name}» не найден. Используй otdel_manage(list) для списка отделов.")

    try:
        from ..chat.otdel_helpers import _load_history

        # Snapshot history length — we'll poll for new assistant messages
        history_before = _load_history(otdel_id)
        known_msg_ids = {m.get("id") for m in history_before}

        # Run the full pipeline (awaits completion, not fire-and-forget)
        from ..chat.ws_router import _handle_otdel_send

        synthetic_msg = {"otdel_id": otdel_id, "message": message}
        await _handle_otdel_send("tool:otdel_message", synthetic_msg)

        # Collect all new assistant messages from history
        history_after = _load_history(otdel_id)
        new_messages = [
            m for m in history_after
            if m.get("id") not in known_msg_ids and m.get("role") == "assistant"
        ]

        if not new_messages:
            return make_success({
                "status": "no_response",
                "otdel_id": otdel_id,
                "otdel_name": resolved_name,
                "info": f"Сообщение отправлено в отдел «{resolved_name}», но глава не ответила.",
            })

        # Build a readable summary of the head's response
        last_msg = new_messages[-1]
        head_name = last_msg.get("sender_name", last_msg.get("sender", "глава"))
        head_response = last_msg.get("content", "")

        # If there were multiple assistant messages (workers + head),
        # include the full chain
        if len(new_messages) > 1:
            parts = []
            for m in new_messages:
                name = m.get("sender_name", m.get("sender", "?"))
                content = m.get("content", "")
                parts.append(f"[{name}]: {content}")
            full_chain = "\n\n".join(parts)
            return make_success({
                "status": "completed",
                "otdel_id": otdel_id,
                "otdel_name": resolved_name,
                "head_name": head_name,
                "head_response": head_response,
                "full_chain": full_chain,
                "iterations": len(new_messages),
                "info": f"Отдел «{resolved_name}» обработал ({len(new_messages)} сообщений). Последний ответ от {head_name}.",
            })

        return make_success({
            "status": "completed",
            "otdel_id": otdel_id,
            "otdel_name": resolved_name,
            "head_name": head_name,
            "head_response": head_response,
            "info": f"Глава отдела «{resolved_name}» ({head_name}) ответил.",
        })

    except Exception as e:
        logger.error("otdel_message error for %s: %s", otdel_id, e)
        return make_error(f"otdel_message error: {e}")
