"""WebSocket endpoint — single /ws for all chat types.

Multiplexed protocol:
  Client → Server: {"type": "chat:send", ...} or {"type": "otdel:send", ...}
  Server → Client: {"type": "chat:chunk", ...} or {"type": "otdel:message", ...}
"""

import asyncio
import re
import json
from .router import get_all_tool_names
import logging
import uuid
from dataclasses import dataclass, field
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .ws_manager import ws_manager
from ..time import now as _now

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ws"])

# Worker retry policy now lives in head_retry (protocol.yaml knob) —
# see head_protocol/protocol.config.py. The hidden MAX_WORKER_RETRY auto-loop
# was removed because it duplicated the knob and masked worker responses from
# the head (responded_workers never got populated, head_retry kept failing
# on phase gating).
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


def compute_phase(state: HeadState | None) -> dict:
    """Return the current delegation phase and a snapshot of who's waiting.

    Phases:
      - DELEGATED     : task dispatched, no answers yet (or expected is empty)
      - PARTIAL       : some workers answered, others still missing
      - ALL_RESPONDED : every expected worker has produced a response

    Computed from expected/responded SETS — never from worker_attempts
    (which tracks retry-budget, not delegation state).

    Returns dict with keys:
      phase, delegation_id, expected, missing, received, ready_to_decide,
      summary.
    """
    if state is None:
        return {
            "phase": "DELEGATED",
            "delegation_id": None,
            "expected": [],
            "missing": [],
            "received": [],
            "ready_to_decide": False,
            "summary": "no_state",
        }

    delegation_id = state.active_delegation_id
    if not delegation_id:
        return {
            "phase": "DELEGATED",
            "delegation_id": None,
            "expected": [],
            "missing": [],
            "received": [],
            "ready_to_decide": False,
            "summary": "no_active_delegation",
        }

    expected_set = set(state.expected_workers)
    responded_set = set(state.responded_workers.keys())
    missing = sorted(expected_set - responded_set)
    expected_sorted = sorted(expected_set)

    received_list = []
    for slug in expected_sorted:
        if slug in responded_set:
            resp = state.responded_workers[slug]
            if isinstance(resp, dict):
                content = resp.get("content", "") or ""
            else:
                content = str(resp)
            received_list.append(
                {
                    "slug": slug,
                    "has_content": bool(content.strip()),
                }
            )

    if not expected_set:
        phase = "DELEGATED"
    elif not missing:
        phase = "ALL_RESPONDED"
    elif not responded_set:
        phase = "DELEGATED"
    else:
        phase = "PARTIAL"

    ready_to_decide = phase == "ALL_RESPONDED"

    if phase == "DELEGATED":
        summary = f"отправлено задание, ждём первых ответов от {', '.join(expected_sorted) or '—'}"
    elif phase == "PARTIAL":
        summary = f"получены ответы от {len(received_list)}/{len(expected_sorted)}, ждём {', '.join(missing)}"
    else:
        summary = f"все {len(expected_sorted)} работников ответили, можно принимать решение"

    return {
        "phase": phase,
        "delegation_id": delegation_id,
        "expected": expected_sorted,
        "missing": missing,
        "received": received_list,
        "ready_to_decide": ready_to_decide,
        "summary": summary,
    }


def _task_done_callback(task, user_id: str, msg_type: str):
    """Log errors from fire-and-forget tasks (asyncio.create_task swallows them)."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error(
            "[ws_task] %s for %s FAILED: %s: %s", msg_type, user_id, type(exc).__name__, exc
        )
    else:
        logger.debug("[ws_task] %s for %s completed OK", msg_type, user_id)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Single WebSocket endpoint for all real-time communication."""
    user_id = "default"  # No auth for now
    await ws_manager.connect(ws, user_id)

    # Run session reset check on first connect (primary trigger)
    try:
        from .session_reset import check_and_reset_on_connect

        check_and_reset_on_connect()
    except Exception as e:
        logger.debug("Session reset on connect failed (non-critical): %s", e)

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws_manager.send(
                    user_id,
                    {
                        "type": "error",
                        "message": "Invalid JSON",
                    },
                )
                continue

            msg_type = msg.get("type", "")

            if msg_type == "ping":
                await ws_manager.send(user_id, {"type": "pong"})
                continue

            # Route to appropriate handler
            if msg_type == "chat:send":
                task = asyncio.create_task(_handle_chat_send(user_id, msg))
                task.add_done_callback(
                    lambda t, _uid=user_id: _task_done_callback(t, _uid, "chat:send")
                )
            elif msg_type == "otdel:send":
                task = asyncio.create_task(_handle_otdel_send(user_id, msg))
                task.add_done_callback(
                    lambda t, _uid=user_id: _task_done_callback(t, _uid, "otdel:send")
                )
            else:
                await ws_manager.send(
                    user_id,
                    {
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                    },
                )

    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)
    except Exception as e:
        logger.error("WS error for %s: %s", user_id, e)
        ws_manager.disconnect(user_id)


async def _auto_analyze_images(images: list[str]) -> str:
    """Analyze images via image_analyze tool and return text for system prompt."""
    try:
        from ..tools.image_analyze import image_analyze
    except ImportError:
        return ""

    async def _analyze_one(idx: int, img_url: str) -> str:
        try:
            result = await image_analyze(
                {
                    "image_url": img_url,
                    "prompt": "Подробно опиши что изображено на картинке. Цвета, объекты, текст, стиль.",
                }
            )
            if result.get("success"):
                return f"[Изображение {idx + 1}]: {result['output']}"
            else:
                return f"[Изображение {idx + 1}]: не удалось — {result.get('error', 'unknown')}"
        except Exception as e:
            logger.warning("[auto_analyze] Failed to analyze image %d: %s", idx, e)
            return f"[Изображение {idx + 1}]: ошибка — {e}"

    try:
        results = await asyncio.gather(
            *[_analyze_one(i, url) for i, url in enumerate((images or [])[:3])]
        )
    except Exception as e:
        logger.warning("[auto_analyze] Error: %s", e)
        return ""

    if not results:
        return ""

    return (
        "\n\n[АНАЛИЗ ИЗОБРАЖЕНИЙ — выполнено автоматически]\n"
        + "\n\n".join(results)
        + "\n\n[Конец анализа изображений. Используй эти описания для ответа пользователю.]"
    )


async def _handle_chat_send(user_id: str, msg: dict):
    """Handle private chat message — stream LLM response via WS."""
    from .router import (
        registry,
        _build_system_prompt_with_memory,
        _load_chat_history,
        _save_chat_history,
    )
    from .providers.base import ChatMessage

    if registry is None:
        await ws_manager.send(user_id, {"type": "error", "message": "Chat provider not configured"})
        return

    agent_slug = msg.get("agent_slug", "")
    message = msg.get("message", "")
    channel_id = msg.get("channel_id", "web")
    system_prompt = msg.get("system_prompt", "")
    images = msg.get("images")  # list[str] of base64 data URLs

    if not agent_slug or not message:
        await ws_manager.send(
            user_id, {"type": "error", "message": "Missing agent_slug or message"}
        )
        return

    # Build system prompt with memory + session context
    from types import SimpleNamespace

    req = SimpleNamespace(agent_slug=agent_slug, system_prompt=system_prompt, channel_id=channel_id)
    full_system_prompt = _build_system_prompt_with_memory(req)

    # Load history + add user message (with images)
    history = _load_chat_history(agent_slug, channel_id)
    user_entry = {"role": "user", "content": message, "timestamp": _now().isoformat()}
    if images:
        user_entry["images"] = images
    history.append(user_entry)
    _save_chat_history(agent_slug, channel_id, history)

    # Auto-analyze images BEFORE sending to agent
    if images:
        full_system_prompt += await _auto_analyze_images(images)

    # Compaction: trim old messages if context exceeds limit (internal agents only)
    from .router import compact_messages

    compacted_history, compaction_notice = await compact_messages(
        history,
        system_prompt=full_system_prompt,
        agent_slug=agent_slug,
    )
    if compaction_notice:
        logger.info("WS chat compaction for %s: %s", agent_slug, compaction_notice)
        # Notify client about compaction
        await ws_manager.send(
            user_id,
            {
                "type": "chat:compacting",
                "agent_slug": agent_slug,
                "notice": compaction_notice,
                "before": len(history),
                "after": len(compacted_history),
            },
        )

    # Build messages — only pass images from the LAST user message
    # (old images are already analyzed by auto_analyze, no need to send raw base64)
    last_user_idx = None
    for i in range(len(compacted_history) - 1, -1, -1):
        if compacted_history[i].get("role") == "user":
            last_user_idx = i
            break

    messages = []
    for i, m in enumerate(compacted_history):
        msg_images = m.get("images") if i == last_user_idx else None
        messages.append(ChatMessage(role=m["role"], content=m["content"], images=msg_images))

    # Get provider/model
    from ..agents.manager import get_agent

    agent_data = get_agent(agent_slug)
    provider_name = agent_data.get("provider") if agent_data else None
    model = agent_data.get("model", "") if agent_data else ""
    temperature = agent_data.get("temperature", 0.7) if agent_data else 0.7
    max_tokens = agent_data.get("max_tokens", 4096) if agent_data else 4096
    is_primary = agent_data.get("is_primary", False) if agent_data else False
    tool_names = get_all_tool_names(include_head=is_primary, include_primary=is_primary)

    # Resolve model with fallback to provider's default
    from .router import resolve_model

    provider_name, model = resolve_model(provider_name, model)

    # Stream response via WS
    full_response = ""
    tool_calls = []  # Track tool calls for history
    usage = None  # Token usage from done message
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
                    await ws_manager.send(
                        user_id,
                        {
                            "type": "chat:chunk",
                            "agent_slug": agent_slug,
                            "content": content,
                        },
                    )
                elif msg_type == "tool_start":
                    # Track tool call
                    tool_calls.append(
                        {
                            "name": payload.get("tool", ""),
                            "params": payload.get("params", {}),
                            "status": "running",
                        }
                    )
                    # Forward
                    ws_type = f"chat:{msg_type}"
                    ws_msg = {"type": ws_type, "agent_slug": agent_slug}
                    ws_msg.update({k: v for k, v in payload.items() if k != "type"})
                    await ws_manager.send(user_id, ws_msg)
                elif msg_type == "tool_end":
                    # Update tool call status
                    tool_name = payload.get("tool", "")
                    for tc in tool_calls:
                        if tc["name"] == tool_name and tc["status"] == "running":
                            tc["status"] = "completed" if payload.get("success") else "error"
                            tc["result"] = payload.get("result", "")
                            break
                    # Forward
                    ws_type = f"chat:{msg_type}"
                    ws_msg = {"type": ws_type, "agent_slug": agent_slug}
                    ws_msg.update({k: v for k, v in payload.items() if k != "type"})
                    await ws_manager.send(user_id, ws_msg)
                elif msg_type in ("done", "error"):
                    # Extract usage for history
                    if msg_type == "done" and "usage" in payload:
                        usage = payload["usage"]
                    # Forward
                    ws_type = f"chat:{msg_type}"
                    ws_msg = {"type": ws_type, "agent_slug": agent_slug}
                    ws_msg.update({k: v for k, v in payload.items() if k != "type"})
                    await ws_manager.send(user_id, ws_msg)
            except Exception as parse_err:
                logger.debug("Chunk parse error for %s: %s", agent_slug, parse_err)
    except Exception as e:
        logger.error("Chat stream error for %s: %s", agent_slug, e)
        await ws_manager.send(user_id, {"type": "error", "message": str(e)})
        return

    # If streaming completed but no response was captured, notify client
    if not full_response:
        await ws_manager.send(
            user_id,
            {
                "type": "chat:error",
                "agent_slug": agent_slug,
                "message": "Agent did not produce a response. Check server logs.",
            },
        )

    # Save assistant response to history
    if full_response:
        assistant_entry = {
            "role": "assistant",
            "content": full_response,
            "timestamp": _now().isoformat(),
        }
        if model:
            assistant_entry["model"] = model
        if provider_name:
            assistant_entry["provider"] = provider_name
        if agent_data and agent_data.get("name"):
            assistant_entry["agent_name"] = agent_data["name"]
        # Save token usage if available
        if usage:
            assistant_entry["prompt_tokens"] = usage.get("prompt_tokens", 0)
            assistant_entry["completion_tokens"] = usage.get("completion_tokens", 0)
        # Save tool calls for badge display after reload
        if tool_calls:
            assistant_entry["tools"] = tool_calls
        history.append(assistant_entry)
        _save_chat_history(agent_slug, channel_id, history)

    # Signal done (include usage for footer display)
    done_msg = {
        "type": "chat:done",
        "agent_slug": agent_slug,
        "content": full_response,
    }
    if usage:
        done_msg["usage"] = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }
    await ws_manager.send(user_id, done_msg)


async def _handle_otdel_send(user_id: str, msg: dict):
    """Handle otdel chat message — process agents and push responses via WS."""
    from .otdel_helpers import (
        _load_history,
        _save_history,
        _parse_mentions,
        _build_otdel_system_prompt,
        _build_head_context,
        _build_worker_context,
    )
    from .providers.base import ChatMessage
    from ..agents.manager import get_otdel, get_agent

    otdel_id = msg.get("otdel_id", "")
    message = msg.get("message", "")
    images = msg.get("images")  # list[str] of base64 data URLs

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
        "timestamp": _now().isoformat(),
    }
    if images:
        user_msg["images"] = images
    history.append(user_msg)
    save_stats = _save_history(otdel_id, history)
    if save_stats.get("was_compacted"):
        await ws_manager.send(
            user_id,
            {
                "type": "otdel:compacting",
                "otdel_id": otdel_id,
                "before": save_stats["before"],
                "after": save_stats["after"],
            },
        )

    # Push user message to client
    await ws_manager.send(
        user_id,
        {
            "type": "otdel:message",
            "otdel_id": otdel_id,
            "message": user_msg,
        },
    )

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
    # Continuation trigger: when a multi-step task is in flight (user message
    # contains раунд/этап/итерац/потом/сначала), and a worker just responded
    # to a head_delegate call, and the head did NOT itself queue another
    # delegation in the same turn — schedule one more head turn with a
    # reminder so the multi-step chain doesn't stall waiting for the user.
    # Gated to multi-step tasks only (not single delegation responses), and
    # to head_delegating=True (user asked head to manage the flow).
    multi_step = bool(
        re.search(r"\b(раунд|этап|итерац|потом|сначала|затем)\b", message, re.IGNORECASE)
    )
    needs_head_continuation = False
    last_delegation_id_at_worker_response = None

    while agent_queue and processed_count < max_iterations:
        agent, is_head, trigger_message = agent_queue.pop(0)
        agent_slug_val = agent.get("slug", "")
        agent_name_val = agent.get("name", "")

        system_prompt = _build_otdel_system_prompt(otdel, agent, is_head)
        history = _load_history(otdel_id)

        # Auto-analyze images from the current user message
        if images:
            system_prompt += await _auto_analyze_images(images)

        if is_head:
            context_messages = _build_head_context(history, agent_slug_val)
        else:
            context_messages = _build_worker_context(history, agent_slug_val, head_slug, head_name)

        messages = [
            ChatMessage(role=m["role"], content=m["content"], images=m.get("images"))
            for m in context_messages
        ]
        # Worker trigger: distinguish "Head delegated a task" from "user wrote
        # directly". Without this prefix the worker's LLM treats the trigger
        # as a generic user message (role=user, no sender label) and answers
        # as if Artur talked to it directly — losing the head→worker
        # delegation context. Mirrors the same fix in
        # otdel_chat_router.py so both code paths (HTTP + WS) agree.
        # Head trigger: keep the bare user-role — head context already labels
        # previous worker responses with their sender name, so the head
        # already knows who it is talking to.
        if is_head:
            trigger_content = trigger_message
        else:
            trigger_content = f"[📋 Задание от {head_name}]: {trigger_message}"
        messages.append(ChatMessage(role="user", content=trigger_content))

        model = agent.get("model", "")
        provider_name = agent.get("provider")

        # Resolve model with fallback to provider's default
        from .router import resolve_model

        provider_name, model = resolve_model(provider_name, model)

        # Determine tools for this agent
        if is_head:
            # Head gets all tools including head protocol tools
            tool_names = get_all_tool_names(include_head=True)
        else:
            tool_names = get_all_tool_names()

        # Stream LLM response via WebSocket chunks
        agent_msg_id = f"a-{uuid.uuid4().hex[:8]}"
        full_response = ""
        usage = None  # Track token usage
        # Track tool calls made during streaming
        tools_called = []  # Track tool calls made during streaming

        # Notify client that this agent is thinking
        await ws_manager.send(
            user_id,
            {
                "type": "otdel:thinking",
                "otdel_id": otdel_id,
                "agent_slug": agent_slug_val,
                "agent_name": agent_name_val,
                "is_head": is_head,
            },
        )

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
                            await ws_manager.send(
                                user_id,
                                {
                                    "type": "otdel:chunk",
                                    "otdel_id": otdel_id,
                                    "message_id": agent_msg_id,
                                    "content": content,
                                    "sender": agent_slug_val,
                                    "sender_name": agent_name_val,
                                    "is_head": is_head,
                                    "model": model,
                                    "provider": provider_name,
                                },
                            )
                    elif msg_type == "tool_start":
                        # Forward tool event via WS
                        await ws_manager.send(
                            user_id,
                            {
                                "type": f"otdel:{msg_type}",
                                "otdel_id": otdel_id,
                                "message_id": agent_msg_id,
                                "tool": payload.get("tool"),
                                "params": payload.get("params"),
                                "result": payload.get("result"),
                                "success": payload.get("success"),
                                "error": payload.get("error"),
                                "index": payload.get("index"),
                            },
                        )
                        # Track tool calls for placeholder generation
                        tools_called.append(
                            {
                                "name": payload.get("tool", ""),
                                "params": payload.get("params", {}),
                                "status": "running",
                            }
                        )
                    elif msg_type == "tool_end":
                        # Update tool call status
                        tool_name = payload.get("tool", "")
                        for tc in tools_called:
                            if tc["name"] == tool_name and tc.get("status") == "running":
                                tc["status"] = "completed" if payload.get("success") else "error"
                                tc["result"] = payload.get("result", "")
                                break
                        # Forward tool event via WS
                        await ws_manager.send(
                            user_id,
                            {
                                "type": f"otdel:{msg_type}",
                                "otdel_id": otdel_id,
                                "message_id": agent_msg_id,
                                "tool": payload.get("tool"),
                                "params": payload.get("params"),
                                "result": payload.get("result"),
                                "success": payload.get("success"),
                                "error": payload.get("error"),
                                "index": payload.get("index"),
                            },
                        )
                    elif msg_type == "done":
                        usage = payload.get("usage")
                        streaming = False
                    elif msg_type == "error":
                        streaming = False
                        full_response = f"⚠️ Ошибка: {payload.get('message', 'Unknown error')}"
                except Exception:
                    pass
        except Exception as e:
            logger.error(
                "LLM call failed for agent %s in otdel %s: %s", agent_slug_val, otdel_id, e
            )
            full_response = f"⚠️ Ошибка: {e}"
            streaming = False

        # Save final message to history
        # Strip leaked text-based tool calls from response (e.g. <tool_call>...</tool_call>)
        full_response = re.sub(
            r"<tool_call>.*?</tool_call>", "", full_response, flags=re.DOTALL
        ).strip()
        # Also strip ```tool_call...``` blocks
        full_response = re.sub(r"```tool_call.*?```", "", full_response, flags=re.DOTALL).strip()
        # If empty response but tools were called, generate a placeholder
        if not full_response and tools_called:
            # Debug: log what tools were called
            tool_names_called = [tc["name"] for tc in tools_called]
            logger.info(
                "Otdel %s HEAD called tools: %s (head_delegate present: %s)",
                otdel_id,
                tool_names_called,
                "head_delegate" in tool_names_called,
            )

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
            await ws_manager.send(
                user_id,
                {
                    "type": "otdel:chunk",
                    "otdel_id": otdel_id,
                    "message_id": agent_msg_id,
                    "content": full_response,
                    "sender": agent_slug_val,
                    "sender_name": agent_name_val,
                    "is_head": is_head,
                    "model": model,
                    "provider": provider_name,
                },
            )

        if full_response:
            agent_msg = {
                "id": agent_msg_id,
                "role": "assistant",
                "sender": agent_slug_val,
                "sender_name": agent_name_val,
                "content": full_response,
                "is_head": is_head,
                "timestamp": _now().isoformat(),
                "model": model,
                "provider": provider_name,
            }
            # Save tool calls for badge display after reload
            if tools_called:
                agent_msg["tools"] = tools_called
            # Save token usage if available
            if usage:
                agent_msg["prompt_tokens"] = usage.get("prompt_tokens", 0)
                agent_msg["completion_tokens"] = usage.get("completion_tokens", 0)
            history.append(agent_msg)
            save_stats = _save_history(otdel_id, history)
            if save_stats.get("was_compacted"):
                await ws_manager.send(
                    user_id,
                    {
                        "type": "otdel:compacting",
                        "otdel_id": otdel_id,
                        "before": save_stats["before"],
                        "after": save_stats["after"],
                    },
                )

            # Send done event (include usage for footer display)
            done_msg = {
                "type": "otdel:done",
                "otdel_id": otdel_id,
                "message_id": agent_msg_id,
                "message": agent_msg,
            }
            if usage:
                done_msg["usage"] = {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                }
            await ws_manager.send(user_id, done_msg)

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
                                logger.info(
                                    "Otdel %s head_delegate: queueing %s (task=%s)",
                                    otdel_id,
                                    agent.get("name"),
                                    task_text[:60],
                                )
                    if expected_workers:
                        head_delegating = True
            # Note: agent response already sent via otdel:chunk + otdel:done above
            # No need for otdel:message here

            processed_slugs.add(agent_slug_val)
            if not is_head:
                # Worker finished its turn. Track the response so the head
                # can see it via head_checklist / head_retry / head_evaluate.
                # Retry is owned by the head protocol (head_retry) — used to
                # be a hidden auto-retry here, but it duplicated the protocol
                # knob and masked state from the head (responded_workers
                # never got populated, so head_retry kept failing on phase
                # gating). The head now sees the failure and decides.
                is_error = full_response.startswith("⚠️ Ошибка:") or not full_response.strip()
                head_state.responded_workers[agent_slug_val] = {
                    "content": full_response,
                    "model": model,
                    "provider": provider_name,
                    "tools": tools_called,
                    "is_error": is_error,
                }

                # Multi-step continuation: if the original user message
                # contained a multi-step marker (раунд/этап/итерац/...) and
                # the head had delegated this task (head_delegating=True),
                # AND the head did NOT itself queue another delegation in
                # this same turn — mark that the follow-up should remind
                # the head to call head_delegate for the next step. Without
                # this the head often answers in prose ('Раунд 1: ...
                # Стартуем') and stalls waiting for the user to nudge it.
                if multi_step and head_delegating:
                    # Snapshot which delegation ID was active when this
                    # worker responded. The head's own follow-up will check
                    # whether the ID advanced (= head re-delegated itself
                    # in the same turn) to decide if a reminder is needed.
                    last_delegation_id_at_worker_response = (
                        head_state.active_delegation_id
                    )

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
            logger.info(
                "Otdel %s follow-up: %d workers still pending, asking head", otdel_id, len(missing)
            )
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
                # Multi-step nudge: if the user's task was explicitly
                # multi-step (раунд/этап/итерац/...) and the head did
                # NOT re-delegate in this turn, append an explicit
                # reminder to call head_delegate for the next step.
                # The check uses active_delegation_id — if the head
                # itself called head_delegate, this ID advances; if
                # it stayed put, the head answered in prose and we
                # need to push it to act.
                nudge = ""
                if (
                    multi_step
                    and last_delegation_id_at_worker_response
                    and head_state.active_delegation_id
                    == last_delegation_id_at_worker_response
                ):
                    nudge = (
                        "\n\nПодсказка: исходная задача была многоэтапной, "
                        "и в этом turn'е ты ещё не вызвал head_delegate "
                        "для следующего этапа. Сейчас самое время — "
                        "вызови head_delegate с конкретным task для "
                        "следующего этапа. Не пиши план прозой."
                    )
                acknowledge_trigger = (
                    "Все работники отдела ответили. "
                    "Проанализируй их ответы.\n"
                    "Если задача требует дополнительных действий (делегировать другому агенту, "
                    "отправить на доработку, передать результат следующему этапу) — ПРОДОЛЖАЙ, "
                    "вызывай head_delegate или другие инструменты.\n"
                    "Если задача полностью выполнена — сформируй итог для пользователя."
                    + nudge
                )
        else:
            acknowledge_trigger = (
                "Работники отдела ответили. Посмотри их ответы и прокомментируй, если нужно."
            )

        messages = [
            ChatMessage(role=m["role"], content=m["content"], images=m.get("images"))
            for m in context_messages
        ]
        messages.append(ChatMessage(role="user", content=acknowledge_trigger))

        system_prompt = _build_otdel_system_prompt(otdel, head_agent, True)
        model = head_agent.get("model", "")
        provider_name = head_agent.get("provider")

        # Resolve model with fallback to provider's default
        from .router import resolve_model

        provider_name, model = resolve_model(provider_name, model)

        # Head gets all tools including head protocol
        tool_names = get_all_tool_names(include_head=True)

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
                            await ws_manager.send(
                                user_id,
                                {
                                    "type": "otdel:chunk",
                                    "otdel_id": otdel_id,
                                    "message_id": followup_msg_id,
                                    "content": content,
                                    "sender": head_slug,
                                    "sender_name": head_name,
                                    "is_head": True,
                                },
                            )
                    elif msg_type in ("tool_start", "tool_end"):
                        # Forward tool events via WS
                        await ws_manager.send(
                            user_id,
                            {
                                "type": f"otdel:{msg_type}",
                                "otdel_id": otdel_id,
                                "message_id": followup_msg_id,
                                "tool": payload.get("tool"),
                                "params": payload.get("params"),
                                "result": payload.get("result"),
                                "success": payload.get("success"),
                                "error": payload.get("error"),
                                "index": payload.get("index"),
                            },
                        )
                    elif msg_type == "error":
                        full_response = f"⚠️ Ошибка: {payload.get('message', 'Unknown error')}"
                except Exception:
                    pass
        except Exception as e:
            logger.error("Head follow-up failed in otdel %s: %s", otdel_id, e)
            full_response = f"⚠️ Ошибка: {e}"

        # Strip leaked text-based tool calls from follow-up response too
        full_response = re.sub(
            r"<tool_call>.*?</tool_call>", "", full_response, flags=re.DOTALL
        ).strip()
        full_response = re.sub(r"```tool_call.*?```", "", full_response, flags=re.DOTALL).strip()

        if full_response:
            agent_msg = {
                "id": followup_msg_id,
                "role": "assistant",
                "sender": head_slug,
                "sender_name": head_name,
                "content": full_response,
                "is_head": True,
                "timestamp": _now().isoformat(),
                "model": model,
                "provider": provider_name,
            }
            history.append(agent_msg)
            save_stats = _save_history(otdel_id, history)
            if save_stats.get("was_compacted"):
                await ws_manager.send(
                    user_id,
                    {
                        "type": "otdel:compacting",
                        "otdel_id": otdel_id,
                        "before": save_stats["before"],
                        "after": save_stats["after"],
                    },
                )

            await ws_manager.send(
                user_id,
                {
                    "type": "otdel:done",
                    "otdel_id": otdel_id,
                    "message_id": followup_msg_id,
                    "message": agent_msg,
                },
            )

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
                            logger.info(
                                "Otdel %s follow-up delegation: queueing %s",
                                otdel_id,
                                agent.get("name"),
                            )

    # ── Second pass: process workers queued by follow-up delegations ──
    while agent_queue and processed_count < max_iterations:
        agent, is_head, trigger_message = agent_queue.pop(0)
        agent_slug_val = agent.get("slug", "")
        agent_name_val = agent.get("name", "")

        system_prompt = _build_otdel_system_prompt(otdel, agent, is_head)
        history = _load_history(otdel_id)

        # Auto-analyze images from the current user message
        if images:
            system_prompt += await _auto_analyze_images(images)

        if is_head:
            context_messages = _build_head_context(history, agent_slug_val)
        else:
            context_messages = _build_worker_context(history, agent_slug_val, head_slug, head_name)

        messages = [
            ChatMessage(role=m["role"], content=m["content"], images=m.get("images"))
            for m in context_messages
        ]
        # Same trigger-wrap as the main loop above. Empty trigger (follow-up
        # delegation with no task text) skips the wrap so we don't emit a
        # span with an empty body — workers use the head's own recent text
        # from history in that case.
        if is_head:
            trigger_content = trigger_message
        elif trigger_message:
            trigger_content = f"[📋 Задание от {head_name}]: {trigger_message}"
        else:
            trigger_content = trigger_message
        messages.append(ChatMessage(role="user", content=trigger_content))

        model = agent.get("model", "")
        provider_name = agent.get("provider")

        # Resolve model with fallback to provider's default
        from .router import resolve_model

        provider_name, model = resolve_model(provider_name, model)

        if is_head:
            tool_names = get_all_tool_names(include_head=True)
        else:
            tool_names = get_all_tool_names()

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
                            await ws_manager.send(
                                user_id,
                                {
                                    "type": "otdel:chunk",
                                    "otdel_id": otdel_id,
                                    "message_id": agent_msg_id,
                                    "content": content,
                                    "sender": agent_slug_val,
                                    "sender_name": agent_name_val,
                                    "is_head": is_head,
                                },
                            )
                    elif msg_type in ("tool_start", "tool_end"):
                        await ws_manager.send(
                            user_id,
                            {
                                "type": f"otdel:{msg_type}",
                                "otdel_id": otdel_id,
                                "message_id": agent_msg_id,
                                "tool": payload.get("tool"),
                                "params": payload.get("params"),
                                "result": payload.get("result"),
                                "success": payload.get("success"),
                                "error": payload.get("error"),
                                "index": payload.get("index"),
                            },
                        )
                    elif msg_type == "error":
                        full_response = f"⚠️ Ошибка: {payload.get('message', 'Unknown error')}"
                except Exception:
                    pass
        except Exception as e:
            full_response = f"⚠️ Ошибка: {e}"

        full_response = re.sub(
            r"<tool_call>.*?</tool_call>", "", full_response, flags=re.DOTALL
        ).strip()

        if full_response:
            agent_msg = {
                "id": agent_msg_id,
                "role": "assistant",
                "sender": agent_slug_val,
                "sender_name": agent_name_val,
                "content": full_response,
                "is_head": is_head,
                "timestamp": _now().isoformat(),
                "model": model,
                "provider": provider_name,
            }
            history = _load_history(otdel_id)
            history.append(agent_msg)
            _save_history(otdel_id, history)
            await ws_manager.send(
                user_id,
                {
                    "type": "otdel:done",
                    "otdel_id": otdel_id,
                    "message_id": agent_msg_id,
                    "message": agent_msg,
                },
            )

        processed_slugs.add(agent_slug_val)
        if not is_head:
            responded_workers.add(agent_slug_val)
            workers_responded += 1
        processed_count += 1

    # Signal done
    await ws_manager.send(
        user_id,
        {
            "type": "otdel:done",
            "otdel_id": otdel_id,
        },
    )
