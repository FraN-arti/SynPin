"""Send a message from the main agent to an otdel's chat.

Directly saves to history + broadcasts via WebSocket.
Head agent processes in background.

Accepts either otdel_id or otdel_name — resolves automatically.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Any

from .base import ToolResult, make_success, make_error
from ._registry import register_tool
from ..time import now as _now


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
    description='Отправить сообщение в чат отдела от имени главного агента. Глава отдела получит уведомление и может ответить. Принимает otdel_id ИЛИ otdel_name. Только для главного агента.',
    category='other',
    scope='primary',
    dangerous=False,
)
async def otdel_message(params: dict[str, Any]) -> ToolResult:
    """
    Отправить сообщение в чат отдела от имени главного агента.

    Сообщение сохраняется в историю и отправляется через WebSocket.
    Глава отдела получает уведомление и обрабатывает в фоне.

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
        from ..chat.otdel_helpers import _load_history, _save_history
        from ..chat.ws_manager import ws_manager

        # Save message to history
        history = _load_history(otdel_id)
        user_msg = {
            "id": f"u-{uuid.uuid4().hex[:8]}",
            "role": "user",
            "sender": "main_agent",
            "content": message,
            "timestamp": _now().isoformat(),
        }
        history.append(user_msg)
        _save_history(otdel_id, history)

        # Broadcast to all connected WS clients
        await ws_manager.broadcast({
            "type": "otdel:message",
            "otdel_id": otdel_id,
            "message": user_msg,
        })

        # Trigger head agent processing in background
        asyncio.create_task(_process_head(otdel_id, message))

        return make_success({
            "status": "sent",
            "otdel_id": otdel_id,
            "otdel_name": resolved_name,
            "message": message,
            "info": f"Сообщение отправлено в отдел «{resolved_name}». Глава отдела получит уведомление.",
        })

    except Exception as e:
        return make_error(f"otdel_message error: {e}")


async def _process_head(otdel_id: str, message: str):
    """Process head agent response in background."""
    try:
        from ..chat.otdel_helpers import (
            _load_history, _save_history,
            _build_otdel_system_prompt, _build_head_context,
        )
        from ..chat.providers.base import ChatMessage
        from ..chat.ws_manager import ws_manager
        from ..agents.manager import get_otdel, get_agent
        from ..chat.router import resolve_model, stream_response

        otdel = get_otdel(otdel_id)
        if not otdel:
            return

        head_slug = otdel.get("head", "")
        head_agent = get_agent(head_slug)
        if not head_agent:
            return

        # Build context
        history = _load_history(otdel_id)
        system_prompt = _build_otdel_system_prompt(otdel, head_agent, True)
        context_messages = _build_head_context(history, head_slug)
        messages = [ChatMessage(role=m["role"], content=m["content"]) for m in context_messages]
        messages.append(ChatMessage(role="user", content=message))

        model = head_agent.get("model", "")
        provider_name = head_agent.get("provider")
        provider_name, model = resolve_model(provider_name, model)

        head_protocol_tools = ["head_delegate", "head_evaluate", "head_retry", "head_decide", "head_block", "kanban_task"]
        tool_names = list(head_agent.get("tools", [])) + head_protocol_tools

        # Stream response
        full_response = ""
        async for chunk in stream_response(
            provider_name=provider_name,
            messages=messages,
            model=model,
            temperature=head_agent.get("temperature", 0.7),
            max_tokens=head_agent.get("max_tokens", 4096),
            system_prompt=system_prompt,
            agent_name=head_agent.get("name", head_slug),
            agent_slug=head_slug,
            tool_names=tool_names,
            otdel_id=otdel_id,
        ):
            if '"type": "chunk"' in chunk:
                try:
                    payload = json.loads(chunk.split("data: ", 1)[1].split("\n")[0])
                    if payload.get("type") == "chunk":
                        full_response += payload.get("content", "")
                except Exception:
                    pass

        if full_response:
            # Save response
            agent_msg = {
                "id": f"a-{uuid.uuid4().hex[:8]}",
                "role": "assistant",
                "sender": head_slug,
                "sender_name": head_agent.get("name", head_slug),
                "content": full_response,
                "is_head": True,
                "timestamp": _now().isoformat(),
                "model": model,
                "provider": provider_name,
            }
            history = _load_history(otdel_id)
            history.append(agent_msg)
            _save_history(otdel_id, history)

            # Broadcast response
            await ws_manager.broadcast({
                "type": "otdel:message",
                "otdel_id": otdel_id,
                "message": agent_msg,
            })

    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Head processing failed for otdel %s: %s", otdel_id, e)
