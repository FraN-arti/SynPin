"""Send a message from the main agent to an otdel's chat.

Delegates to _handle_otdel_send for full pipeline processing
(head → workers → follow-up → autopilot iterations).
Accepts either otdel_id or otdel_name — resolves automatically.
"""
from __future__ import annotations

import asyncio
from typing import Any

from .base import ToolResult, make_success, make_error
from ._registry import register_tool


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
    description='Отправить сообщение в чат отдела от имени главного агента. Глава отдела получит уведомление и обработает с полным pipeline (делегирование, оценка, автопилот). Принимает otdel_id ИЛИ otdel_name. Только для главного агента.',
    category='other',
    scope='primary',
    dangerous=False,
)
async def otdel_message(params: dict[str, Any]) -> ToolResult:
    """
    Отправить сообщение в чат отдела от имени главного агента.

    Использует полный pipeline _handle_otdel_send — глава может
    делегировать работникам, оценивать, итерировать через автопилот.

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
        # Use the full pipeline — _handle_otdel_send handles:
        # - message saving, history, head processing
        # - worker delegation (head_delegate)
        # - follow-up and autopilot iterations
        # - otdel:done events
        from ..chat.ws_router import _handle_otdel_send

        synthetic_msg = {"otdel_id": otdel_id, "message": message}
        asyncio.create_task(_handle_otdel_send("tool:otdel_message", synthetic_msg))

        return make_success({
            "status": "sent",
            "otdel_id": otdel_id,
            "otdel_name": resolved_name,
            "message": message,
            "info": f"Сообщение отправлено в отдел «{resolved_name}». Глава отдела обработает с полным pipeline (делегирование, оценка, автопилот).",
        })

    except Exception as e:
        return make_error(f"otdel_message error: {e}")
