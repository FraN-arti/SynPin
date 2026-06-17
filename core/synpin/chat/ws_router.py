"""WebSocket endpoint — single /ws for all chat types.

Multiplexed protocol:
  Client → Server: {"type": "chat:send", ...} or {"type": "otdel:send", ...}
  Server → Client: {"type": "chat:chunk", ...} or {"type": "otdel:message", ...}
"""

import asyncio
import re
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .ws_manager import ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ws"])

# Worker retry settings
MAX_WORKER_RETRY = 2  # original + 1 retry
WORKER_TIMEOUT_S = 60  # seconds to wait for worker response


# ─── Head Protocol State ───────────────────────────────────────────────

@dataclass
class HeadState:
    """Per-otdel state for Head protocol tools."""
    otdel_id: str
    head_slug: str
    worker_slugs: list[str]
    
    # Delegation state
    active_delegation_id: str | None = None
    expected_workers: set[str] = field(default_factory=set)
    responded_workers: dict[str, dict] = field(default_factory=dict)  # slug -> response
    worker_attempts: dict[str, int] = field(default_factory=dict)  # slug -> attempt count
    delegation_history: list[dict] = field(default_factory=list)
    
    # Current delegation params
    current_delegation: dict | None = None
    
    def reset_delegation(self):
        self.active_delegation_id = None
        self.expected_workers.clear()
        self.responded_workers.clear()
        # Keep worker_attempts for retry tracking
        self.current_delegation = None


# Global HeadState store per otdel
_head_states: dict[str, HeadState] = {}


def get_head_state(otdel_id: str) -> HeadState | None:
    return _head_states.get(otdel_id)


def create_head_state(otdel_id: str, head_slug: str, worker_slugs: list[str]) -> HeadState:
    state = HeadState(otdel_id=otdel_id, head_slug=head_slug, worker_slugs=worker_slugs)
    _head_states[otdel_id] = state
    return state


def clear_head_state(otdel_id: str):
    _head_states.pop(otdel_id, None)


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

    # Compaction: trim old messages if context exceeds limit (internal agents only)
    from .router import compact_messages
    compacted_history, compaction_notice = compact_messages(
        history,
        system_prompt=full_system_prompt,
        agent_slug=agent_slug,
    )
    if compaction_notice:
        logger.info("WS chat compaction for %s: %s", agent_slug, compaction_notice)

    messages = [ChatMessage(role=m["role"], content=m["content"]) for m in compacted_history]

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
        assistant_entry = {"role": "assistant", "content": full_response, "timestamp": datetime.now().isoformat()}
        if model:
            assistant_entry["model"] = model
        if provider_name:
            assistant_entry["provider"] = provider_name
        if agent_data and agent_data.get("name"):
            assistant_entry["agent_name"] = agent_data["name"]
        history.append(assistant_entry)
        _save_chat_history(agent_slug, channel_id, history)

    # Signal done
    await ws_manager.send(user_id, {
        "type": "chat:done",
        "agent_slug": agent_slug,
        "content": full_response,
    })


async def _handle_otdel_send(user_id: str, msg: dict):
    """Handle otdel chat message — process agents and push responses via WS."""
    from .otdel_helpers import (
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
    save_stats = _save_history(otdel_id, history)
    if save_stats.get("was_compacted"):
        await ws_manager.send(user_id, {
            "type": "otdel:compacting",
            "otdel_id": otdel_id,
            "before": save_stats["before"],
            "after": save_stats["after"],
        })

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
        agent_slug_lower = slug.lower()
        if agent_name_lower in user_mentions or agent_slug_lower in user_mentions:
            agent_queue.append((agent, False, message))

    if not agent_queue:
        return

    # Create HeadState for this otdel session
    head_state = create_head_state(otdel_id, head_slug, worker_slugs)

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

        # Determine tools for this agent
        if is_head:
            # Head gets their configured tools + head protocol tools (builtin, otdel-only)
            agent_tools = list(agent.get("tools", []))
            head_protocol_tools = ["head_delegate", "head_evaluate", "head_retry", "head_decide", "head_block", "kanban_task"]
            tool_names = agent_tools + head_protocol_tools
        else:
            tool_names = agent.get("tools", [])

        # Stream LLM response via WebSocket chunks
        agent_msg_id = f"a-{uuid.uuid4().hex[:8]}"
        full_response = ""
        # Track tool calls made during streaming
        tools_called = []  # Track tool calls made during streaming

        # Notify client that this agent is thinking
        await ws_manager.send(user_id, {
            "type": "otdel:thinking",
            "otdel_id": otdel_id,
            "agent_slug": agent_slug_val,
            "agent_name": agent_name_val,
            "is_head": is_head,
        })

        # Debug: log available tools for head
        if is_head:
            logger.info("Otdel %s HEAD tools available: %s", otdel_id, tool_names)

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
                tool_names=tool_names,
                otdel_id=otdel_id,  # Pass otdel context for head protocol tools
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
                                "model": model,
                                "provider": provider_name,
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
                        # Track tool calls for placeholder generation
                        if msg_type == "tool_start":
                            tools_called.append({
                                "name": payload.get("tool", ""),
                                "params": payload.get("params", {}),
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
        # Strip leaked text-based tool calls from response (e.g. <tool_call>...</tool_call>)
        full_response = re.sub(
            r'<tool_call>.*?</tool_call>', '', full_response, flags=re.DOTALL
        ).strip()
        # Also strip ```tool_call...``` blocks
        full_response = re.sub(
            r'```tool_call.*?```', '', full_response, flags=re.DOTALL
        ).strip()
        # If empty response but tools were called, generate a placeholder
        if not full_response and tools_called:
            # Debug: log what tools were called
            tool_names_called = [tc["name"] for tc in tools_called]
            logger.info("Otdel %s HEAD called tools: %s (head_delegate present: %s)", 
                       otdel_id, tool_names_called, "head_delegate" in tool_names_called)
            
            # Build placeholder from tool calls
            delegate_targets = []
            for tc in tools_called:
                if tc["name"] == "head_delegate":
                    target = tc["params"].get("worker", tc["params"].get("target", ""))
                    task = tc["params"].get("task", tc["params"].get("instruction", ""))
                    if target:
                        target_agent = get_agent(target) if target else None
                        target_name = target_agent.get("name", target) if target_agent else target
                        delegate_targets.append(target_name)
                    if task:
                        delegate_targets.append(f"«{task[:80]}»")
            if delegate_targets:
                full_response = f"📋 Делегирую: {', '.join(delegate_targets)}"
            else:
                full_response = "📋 Обрабатываю задачу..."
            # Send placeholder as chunk so frontend can display it
            await ws_manager.send(user_id, {
                "type": "otdel:chunk",
                "otdel_id": otdel_id,
                "message_id": agent_msg_id,
                "content": full_response,
                "sender": agent_slug_val,
                "sender_name": agent_name_val,
                "is_head": is_head,
                "model": model,
                "provider": provider_name,
            })

        if full_response:
            agent_msg = {
                "id": agent_msg_id,
                "role": "assistant",
                "sender": agent_slug_val,
                "sender_name": agent_name_val,
                "content": full_response,
                "is_head": is_head,
                "timestamp": datetime.now().isoformat(),
                "model": model,
                "provider": provider_name,
            }
            history.append(agent_msg)
            save_stats = _save_history(otdel_id, history)
            if save_stats.get("was_compacted"):
                await ws_manager.send(user_id, {
                    "type": "otdel:compacting",
                    "otdel_id": otdel_id,
                    "before": save_stats["before"],
                    "after": save_stats["after"],
                })

            # Send done event
            await ws_manager.send(user_id, {
                "type": "otdel:done",
                "otdel_id": otdel_id,
                "message_id": agent_msg_id,
                "message": agent_msg,
            })

            if is_head:
                # Workers are triggered ONLY via head_delegate tool (HeadState),
                # NOT via @mentions in text. This prevents accidental triggering
                # when the head mentions worker names in passing.
                # Example: "Архитектор — хороший специалист" should NOT trigger Архитектор.

                # Check HeadState for workers from head_delegate tool
                hs = get_head_state(otdel_id)
                if hs and hs.expected_workers:
                    for slug in hs.expected_workers:
                        if slug not in processed_slugs and slug not in expected_workers:
                            agent = get_agent(slug)
                            if agent:
                                expected_workers.add(slug)
                                # Use delegation task from HeadState as trigger
                                delegation = hs.current_delegation or {}
                                workers_list = delegation.get("workers", [])
                                task_text = ""
                                for w in workers_list:
                                    if w.get("slug") == slug:
                                        task_text = w.get("task", "")
                                        break
                                trigger = task_text or full_response.strip()
                                agent_queue.append((agent, False, trigger))
                                logger.info("Otdel %s head_delegate: queueing %s (task=%s)", otdel_id, agent.get("name"), task_text[:60])
                    if expected_workers:
                        head_delegating = True
            # Note: agent response already sent via otdel:chunk + otdel:done above
            # No need for otdel:message here

            processed_slugs.add(agent_slug_val)
            if not is_head:
                # Check if worker response indicates failure
                is_error = full_response.startswith("⚠️ Ошибка:") or not full_response.strip()
                worker_attempts = head_state.worker_attempts if head_state else {}
                current_attempt = worker_attempts.get(agent_slug_val, 0)
                
                if is_error and current_attempt < MAX_WORKER_RETRY:
                    # Retry: increment attempt and re-queue worker
                    worker_attempts[agent_slug_val] = current_attempt + 1
                    retry_task = f"[RETRY #{current_attempt + 1}] {trigger_message}"
                    agent_queue.append((agent, False, retry_task))
                    logger.warning("Otdel %s worker %s failed, retrying (attempt %d/%d)", 
                                 otdel_id, agent_slug_val, current_attempt + 1, MAX_WORKER_RETRY)
                    # Don't add to responded_workers yet - will be added on final response
                else:
                    # Success or max retries exceeded
                    if is_error and current_attempt >= MAX_WORKER_RETRY:
                        logger.error("Otdel %s worker %s failed after %d retries, escalating to head", 
                                   otdel_id, agent_slug_val, MAX_WORKER_RETRY)
                        # Head will be notified in follow-up
                    responded_workers.add(agent_slug_val)
                    workers_responded += 1

        processed_count += 1

    # ── Head follow-up (gather pattern) ──────────────────────────────
    # ONE follow-up: workers respond → head summarizes → DONE
    should_followup = False
    if head_delegating and expected_workers:
        missing = expected_workers - responded_workers
        if not missing:
            should_followup = True
        else:
            # Some workers haven't responded — still follow up so head can
            # either wait, delegate to others, or finalize
            logger.info("Otdel %s follow-up: %d workers still pending, asking head", otdel_id, len(missing))
            should_followup = True
    elif head_processed and workers_responded > 0 and not head_delegating:
        should_followup = True

    if should_followup and processed_count < max_iterations:
        history = _load_history(otdel_id)
        context_messages = _build_head_context(history, head_slug, exclude_last=False)

        if head_delegating:
            missing = expected_workers - responded_workers
            if missing:
                missing_names = []
                for s in missing:
                    a = get_agent(s)
                    missing_names.append(a.get("name", s) if a else s)
                acknowledge_trigger = (
                    f"Некоторые работники ещё не ответили: {', '.join(missing_names)}. "
                    "Жди их ответов в чате. "
                    "Если нужно — отправь задачу повторно через head_delegate. "
                    "НЕ ПИШИ что все ответили — это неправда."
                )
            else:
                acknowledge_trigger = (
                    "Все работники отдела ответили. "
                    "Проанализируй их ответы.\n"
                    "Если задача требует дополнительных действий (делегировать другому агенту, "
                    "отправить на доработку, передать результат следующему этапу) — ПРОДОЛЖАЙ, "
                    "вызывай head_delegate или другие инструменты.\n"
                    "Если задача полностью выполнена — сформируй итог для пользователя."
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

        # Head gets head protocol tools in follow-up too
        head_agent_tools = list(head_agent.get("tools", []))
        head_protocol_tools = ["head_delegate", "head_evaluate", "head_retry", "head_decide", "head_block", "kanban_task"]
        tool_names = head_agent_tools + head_protocol_tools

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
                tool_names=tool_names,
                otdel_id=otdel_id,  # Pass otdel context for head protocol tools
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

        # Strip leaked text-based tool calls from follow-up response too
        full_response = re.sub(
            r'<tool_call>.*?</tool_call>', '', full_response, flags=re.DOTALL
        ).strip()
        full_response = re.sub(
            r'```tool_call.*?```', '', full_response, flags=re.DOTALL
        ).strip()

        if full_response:
            agent_msg = {
                "id": followup_msg_id,
                "role": "assistant",
                "sender": head_slug,
                "sender_name": head_name,
                "content": full_response,
                "is_head": True,
                "timestamp": datetime.now().isoformat(),
                "model": model,
                "provider": provider_name,
            }
            history.append(agent_msg)
            save_stats = _save_history(otdel_id, history)
            if save_stats.get("was_compacted"):
                await ws_manager.send(user_id, {
                    "type": "otdel:compacting",
                    "otdel_id": otdel_id,
                    "before": save_stats["before"],
                    "after": save_stats["after"],
                })

            await ws_manager.send(user_id, {
                "type": "otdel:done",
                "otdel_id": otdel_id,
                "message_id": followup_msg_id,
                "message": agent_msg,
            })

            # Check if head_delegate was called again in follow-up
            # If so, need to process the new workers
            hs = get_head_state(otdel_id)
            if hs and hs.expected_workers:
                new_workers = hs.expected_workers - responded_workers
                if new_workers:
                    for slug in new_workers:
                        agent = get_agent(slug)
                        if agent:
                            agent_queue.append((agent, False, ""))
                            logger.info("Otdel %s follow-up delegation: queueing %s", otdel_id, agent.get("name"))


    # ── Second pass: process workers queued by follow-up delegations ──
    while agent_queue and processed_count < max_iterations:
        agent, is_head, trigger_message = agent_queue.pop(0)
        agent_slug_val = agent.get("slug", "")
        agent_name_val = agent.get("name", "")

        system_prompt = _build_otdel_system_prompt(otdel, agent, is_head)
        history = _load_history(otdel_id)

        if is_head:
            context_messages = _build_head_context(history, agent_slug_val)
        else:
            context_messages = _build_worker_context(history, agent_slug_val, head_slug, head_name)

        messages = [ChatMessage(role=m["role"], content=m["content"]) for m in context_messages]
        messages.append(ChatMessage(role="user", content=trigger_message))

        model = agent.get("model", "default")
        provider_name = agent.get("provider")
        if provider_name and model.startswith(f"{provider_name}/"):
            model = model[len(provider_name) + 1:]

        if is_head:
            tool_names = list(agent.get("tools", [])) + ["head_delegate", "head_evaluate", "head_retry", "head_decide", "kanban_task"]
        else:
            tool_names = agent.get("tools", [])

        agent_msg_id = f"a-{uuid.uuid4().hex[:8]}"
        full_response = ""

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
                tool_names=tool_names,
                otdel_id=otdel_id,
            ):
                try:
                    payload = json.loads(chunk.split("data: ", 1)[1].split("\n")[0])
                    msg_type = payload.get("type", "")
                    if msg_type == "chunk":
                        content = payload.get("content", "")
                        if content:
                            full_response += content
                            await ws_manager.send(user_id, {
                                "type": "otdel:chunk", "otdel_id": otdel_id,
                                "message_id": agent_msg_id, "content": content,
                                "sender": agent_slug_val, "sender_name": agent_name_val, "is_head": is_head,
                            })
                    elif msg_type in ("tool_start", "tool_end"):
                        await ws_manager.send(user_id, {
                            "type": f"otdel:{msg_type}", "otdel_id": otdel_id,
                            "message_id": agent_msg_id, "tool": payload.get("tool"),
                            "params": payload.get("params"), "result": payload.get("result"),
                            "success": payload.get("success"), "error": payload.get("error"),
                            "index": payload.get("index"),
                        })
                    elif msg_type == "error":
                        full_response = f"⚠️ Ошибка: {payload.get('message', 'Unknown error')}"
                except Exception:
                    pass
        except Exception as e:
            full_response = f"⚠️ Ошибка: {e}"

        full_response = re.sub(r'<tool_call>.*?</tool_call>', '', full_response, flags=re.DOTALL).strip()

        if full_response:
            agent_msg = {
                "id": agent_msg_id, "role": "assistant",
                "sender": agent_slug_val, "sender_name": agent_name_val,
                "content": full_response, "is_head": is_head,
                "timestamp": datetime.now().isoformat(),
                "model": model, "provider": provider_name,
            }
            history = _load_history(otdel_id)
            history.append(agent_msg)
            _save_history(otdel_id, history)
            await ws_manager.send(user_id, {
                "type": "otdel:done", "otdel_id": otdel_id,
                "message_id": agent_msg_id, "message": agent_msg,
            })

        processed_slugs.add(agent_slug_val)
        if not is_head:
            responded_workers.add(agent_slug_val)
            workers_responded += 1
        processed_count += 1

    # Signal done
    await ws_manager.send(user_id, {
        "type": "otdel:done",
        "otdel_id": otdel_id,
    })
