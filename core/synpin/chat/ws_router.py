"""WebSocket endpoint — single /ws for all chat types.

Multiplexed protocol:
  Client → Server: {"type": "chat:send", ...} or {"type": "otdel:send", ...}
  Server → Client: {"type": "chat:chunk", ...} or {"type": "otdel:message", ...}
"""

import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ws"])


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Single WebSocket endpoint for all real-time communication."""
    user_id = "default"  # No auth for now
    await ws_manager.connect(ws, user_id)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws_manager.send(user_id, {
                    "type": "error",
                    "message": "Invalid JSON",
                })
                continue

            msg_type = msg.get("type", "")

            if msg_type == "ping":
                await ws_manager.send(user_id, {"type": "pong"})
                continue

            # Route to appropriate handler
            if msg_type == "chat:send":
                asyncio.create_task(_handle_chat_send(user_id, msg))
            elif msg_type == "otdel:send":
                asyncio.create_task(_handle_otdel_send(user_id, msg))
            else:
                await ws_manager.send(user_id, {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)
    except Exception as e:
        logger.error("WS error for %s: %s", user_id, e)
        ws_manager.disconnect(user_id)


async def _handle_chat_send(user_id: str, msg: dict):
    """Handle private chat message — stream LLM response via WS."""
    from .router import registry, _build_system_prompt_with_memory, _load_chat_history, _save_chat_history
    from .providers.base import ChatMessage
    import uuid
    from datetime import datetime

    if registry is None:
        await ws_manager.send(user_id, {"type": "error", "message": "Chat provider not configured"})
        return

    agent_slug = msg.get("agent_slug", "")
    message = msg.get("message", "")
    channel_id = msg.get("channel_id", "web")
    system_prompt = msg.get("system_prompt", "")

    if not agent_slug or not message:
        await ws_manager.send(user_id, {"type": "error", "message": "Missing agent_slug or message"})
        return

    # Build system prompt with memory + session context
    from types import SimpleNamespace
    req = SimpleNamespace(agent_slug=agent_slug, system_prompt=system_prompt, channel_id=channel_id)
    full_system_prompt = _build_system_prompt_with_memory(req)

    # Load history + add user message
    history = _load_chat_history(agent_slug, channel_id)
    history.append({"role": "user", "content": message, "timestamp": datetime.now().isoformat()})
    _save_chat_history(agent_slug, channel_id, history)

    messages = [ChatMessage(role=m["role"], content=m["content"]) for m in history]

    # Get provider/model
    from ..agents.manager import get_agent
    agent_data = get_agent(agent_slug)
    provider_name = agent_data.get("provider") if agent_data else None
    model = agent_data.get("model", "default") if agent_data else "default"
    temperature = agent_data.get("temperature", 0.7) if agent_data else 0.7
    max_tokens = agent_data.get("max_tokens", 4096) if agent_data else 4096
    tool_names = agent_data.get("tools", []) if agent_data else []

    if provider_name and model.startswith(f"{provider_name}/"):
        model = model[len(provider_name) + 1:]

    # Stream response via WS
    full_response = ""
    try:
        from .router import stream_response
        async for chunk in stream_response(
            provider_name=provider_name,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=full_system_prompt,
            agent_name=agent_data.get("name", agent_slug) if agent_data else agent_slug,
            agent_slug=agent_slug,
            tool_names=tool_names,
        ):
            # Parse SSE chunk and forward via WS
            try:
                payload = json.loads(chunk.split("data: ", 1)[1].split("\n")[0])
                msg_type = payload.get("type", "")

                if msg_type == "chunk":
                    content = payload.get("content", "")
                    full_response += content
                    await ws_manager.send(user_id, {
                        "type": "chat:chunk",
                        "agent_slug": agent_slug,
                        "content": content,
                    })
                elif msg_type in ("tool_start", "tool_end", "done", "error"):
                    # Forward tool events and done/error as-is
                    ws_type = f"chat:{msg_type}"
                    ws_msg = {"type": ws_type, "agent_slug": agent_slug}
                    ws_msg.update({k: v for k, v in payload.items() if k != "type"})
                    await ws_manager.send(user_id, ws_msg)
            except Exception:
                pass
    except Exception as e:
        logger.error("Chat stream error for %s: %s", agent_slug, e)
        await ws_manager.send(user_id, {"type": "error", "message": str(e)})
        return

    # Save assistant response to history
    if full_response:
        history.append({"role": "assistant", "content": full_response, "timestamp": datetime.now().isoformat()})
        _save_chat_history(agent_slug, channel_id, history)

    # Signal done
    await ws_manager.send(user_id, {
        "type": "chat:done",
        "agent_slug": agent_slug,
        "content": full_response,
    })


async def _handle_otdel_send(user_id: str, msg: dict):
    """Handle otdel chat message — process agents and push responses via WS."""
    from .otdel_chat_router import (
        _load_history, _save_history, _parse_mentions,
        _build_otdel_system_prompt, _build_head_context, _build_worker_context,
    )
    from .providers.base import ChatMessage
    from ..agents.manager import get_otdel, get_agent
    import uuid
    from datetime import datetime

    otdel_id = msg.get("otdel_id", "")
    message = msg.get("message", "")

    if not otdel_id or not message:
        await ws_manager.send(user_id, {"type": "error", "message": "Missing otdel_id or message"})
        return

    otdel = get_otdel(otdel_id)
    if not otdel:
        await ws_manager.send(user_id, {"type": "error", "message": f"Otdel not found: {otdel_id}"})
        return

    log = logging.getLogger("synpin.otdel")

    # Save user message
    history = _load_history(otdel_id)
    user_msg = {
        "id": f"u-{uuid.uuid4().hex[:8]}",
        "role": "user",
        "sender": "user",
        "content": message,
        "timestamp": datetime.now().isoformat(),
    }
    history.append(user_msg)
    _save_history(otdel_id, history)

    # Push user message to client
    await ws_manager.send(user_id, {
        "type": "otdel:message",
        "otdel_id": otdel_id,
        "message": user_msg,
    })

    # Parse @mentions
    user_mentions = _parse_mentions(message)

    # Find head agent
    head_slug = otdel.get("head", "")
    head_agent = get_agent(head_slug) if head_slug else None
    head_name = head_agent.get("name", head_slug) if head_agent else head_slug

    # Find worker agents
    worker_slugs = otdel.get("workers", [])

    # Build initial queue
    agent_queue = [(head_agent, True, message)] if head_agent else []
    for slug in worker_slugs:
        if slug == head_slug:
            continue
        agent = get_agent(slug)
        if not agent:
            continue
        agent_name_lower = agent.get("name", "").lower()
        if agent_name_lower in user_mentions:
            agent_queue.append((agent, False, message))

    if not agent_queue:
        return

    # Process agents
    processed_count = 0
    head_processed = False
    workers_responded = 0
    max_iterations = 10
    expected_workers = set()
    responded_workers = set()
    head_delegating = False
    processed_slugs = set()

    while agent_queue and processed_count < max_iterations:
        agent, is_head, trigger_message = agent_queue.pop(0)
        agent_slug_val = agent.get("slug", "")
        agent_name_val = agent.get("name", "")

        system_prompt = _build_otdel_system_prompt(otdel, agent, is_head)
        history = _load_history(otdel_id)

        if is_head:
            context_messages = _build_head_context(history, agent_slug_val)
            head_processed = True
        else:
            context_messages = _build_worker_context(history, agent_slug_val, head_slug, head_name)

        messages = [ChatMessage(role=m["role"], content=m["content"]) for m in context_messages]
        messages.append(ChatMessage(role="user", content=trigger_message))

        model = agent.get("model", "default")
        provider_name = agent.get("provider")
        if provider_name and model.startswith(f"{provider_name}/"):
            model = model[len(provider_name) + 1:]

        # Stream LLM response via WebSocket chunks
        agent_msg_id = f"a-{uuid.uuid4().hex[:8]}"
        full_response = ""
        streaming = True

        try:
            from .router import stream_response as base_stream
            async for chunk in base_stream(
                provider_name=provider_name,
                messages=messages,
                model=model,
                temperature=agent.get("temperature", 0.7),
                max_tokens=agent.get("max_tokens", 4096),
                system_prompt=system_prompt,
                agent_name=agent_name_val,
                agent_slug=agent_slug_val,
                tool_names=agent.get("tools", []),  # Agents in otdel get their tools
            ):
                try:
                    payload = json.loads(chunk.split("data: ", 1)[1].split("\n")[0])
                    msg_type = payload.get("type", "")

                    if msg_type == "chunk":
                        content = payload.get("content", "")
                        if content:
                            full_response += content
                            # Push chunk via WS
                            await ws_manager.send(user_id, {
                                "type": "otdel:chunk",
                                "otdel_id": otdel_id,
                                "message_id": agent_msg_id,
                                "content": content,
                                "sender": agent_slug_val,
                                "sender_name": agent_name_val,
                                "is_head": is_head,
                            })
                    elif msg_type in ("tool_start", "tool_end"):
                        # Forward tool events via WS
                        await ws_manager.send(user_id, {
                            "type": f"otdel:{msg_type}",
                            "otdel_id": otdel_id,
                            "message_id": agent_msg_id,
                            "tool": payload.get("tool"),
                            "params": payload.get("params"),
                            "result": payload.get("result"),
                            "success": payload.get("success"),
                            "error": payload.get("error"),
                            "index": payload.get("index"),
                        })
                    elif msg_type == "done":
                        streaming = False
                    elif msg_type == "error":
                        streaming = False
                        full_response = f"⚠️ Ошибка: {payload.get('message', 'Unknown error')}"
                except Exception:
                    pass
        except Exception as e:
            logger.error("LLM call failed for agent %s in otdel %s: %s", agent_slug_val, otdel_id, e)
            full_response = f"⚠️ Ошибка: {e}"
            streaming = False

        # Save final message to history
        if full_response:
            agent_msg = {
                "id": agent_msg_id,
                "role": "assistant",
                "sender": agent_slug_val,
                "sender_name": agent_name_val,
                "content": full_response,
                "is_head": is_head,
                "timestamp": datetime.now().isoformat(),
            }
            history.append(agent_msg)
            _save_history(otdel_id, history)

            # Send done event
            await ws_manager.send(user_id, {
                "type": "otdel:done",
                "otdel_id": otdel_id,
                "message_id": agent_msg_id,
                "message": agent_msg,
            })

            if is_head:
                new_mentions = _parse_mentions(full_response)
                for slug in worker_slugs:
                    if slug == head_slug or slug == agent_slug_val:
                        continue
                    mentioned_agent = get_agent(slug)
                    if not mentioned_agent:
                        continue
                    mentioned_name_lower = mentioned_agent.get("name", "").lower()
                    if mentioned_name_lower in new_mentions:
                        expected_workers.add(slug)
                        if slug not in processed_slugs:
                            agent_queue.append((mentioned_agent, False, full_response))

                if expected_workers:
                    head_delegating = True
            # Note: agent response already sent via otdel:chunk + otdel:done above
            # No need for otdel:message here

            processed_slugs.add(agent_slug_val)

        processed_count += 1

    # ── Head follow-up (gather pattern) ──────────────────────────────
    should_followup = False
    if head_delegating and expected_workers:
        missing = expected_workers - responded_workers
        if not missing:
            should_followup = True
        else:
            log.warning("Otdel %s missing responses from %s", otdel_id, missing)
    elif head_processed and workers_responded > 0 and not head_delegating:
        should_followup = True

    if should_followup and processed_count < max_iterations:
        history = _load_history(otdel_id)
        context_messages = _build_head_context(history, head_slug, exclude_last=False)

        if head_delegating:
            acknowledge_trigger = (
                "Все работники отдела ответили. "
                "Проанализируй их ответы и сформируй итог для пользователя. "
                "Кратко — что сделано, есть ли проблемы."
            )
        else:
            acknowledge_trigger = "Работники отдела ответили. Посмотри их ответы и прокомментируй, если нужно."

        messages = [ChatMessage(role=m["role"], content=m["content"]) for m in context_messages]
        messages.append(ChatMessage(role="user", content=acknowledge_trigger))

        system_prompt = _build_otdel_system_prompt(otdel, head_agent, True)
        model = head_agent.get("model", "default")
        provider_name = head_agent.get("provider")
        if provider_name and model.startswith(f"{provider_name}/"):
            model = model[len(provider_name) + 1:]

        # Stream follow-up response
        followup_msg_id = f"a-{uuid.uuid4().hex[:8]}"
        full_response = ""

        try:
            from .router import stream_response as base_stream
            async for chunk in base_stream(
                provider_name=provider_name,
                messages=messages,
                model=model,
                temperature=head_agent.get("temperature", 0.7),
                max_tokens=head_agent.get("max_tokens", 4096),
                system_prompt=system_prompt,
                agent_name=head_name,
                agent_slug=head_slug,
                tool_names=head_agent.get("tools", []),  # Head gets tools in follow-up too
            ):
                try:
                    payload = json.loads(chunk.split("data: ", 1)[1].split("\n")[0])
                    msg_type = payload.get("type", "")

                    if msg_type == "chunk":
                        content = payload.get("content", "")
                        if content:
                            full_response += content
                            await ws_manager.send(user_id, {
                                "type": "otdel:chunk",
                                "otdel_id": otdel_id,
                                "message_id": followup_msg_id,
                                "content": content,
                                "sender": head_slug,
                                "sender_name": head_name,
                                "is_head": True,
                            })
                    elif msg_type in ("tool_start", "tool_end"):
                        # Forward tool events via WS
                        await ws_manager.send(user_id, {
                            "type": f"otdel:{msg_type}",
                            "otdel_id": otdel_id,
                            "message_id": followup_msg_id,
                            "tool": payload.get("tool"),
                            "params": payload.get("params"),
                            "result": payload.get("result"),
                            "success": payload.get("success"),
                            "error": payload.get("error"),
                            "index": payload.get("index"),
                        })
                    elif msg_type == "error":
                        full_response = f"⚠️ Ошибка: {payload.get('message', 'Unknown error')}"
                except Exception:
                    pass
        except Exception as e:
            logger.error("Head follow-up failed in otdel %s: %s", otdel_id, e)
            full_response = f"⚠️ Ошибка: {e}"

        if full_response:
            agent_msg = {
                "id": followup_msg_id,
                "role": "assistant",
                "sender": head_slug,
                "sender_name": head_name,
                "content": full_response,
                "is_head": True,
                "timestamp": datetime.now().isoformat(),
            }
            history.append(agent_msg)
            _save_history(otdel_id, history)

            await ws_manager.send(user_id, {
                "type": "otdel:done",
                "otdel_id": otdel_id,
                "message_id": followup_msg_id,
                "message": agent_msg,
            })

    # Signal done
    await ws_manager.send(user_id, {
        "type": "otdel:done",
        "otdel_id": otdel_id,
    })
