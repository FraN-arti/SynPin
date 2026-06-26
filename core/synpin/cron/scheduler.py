"""Cron scheduler — background worker that checks for due jobs.

Tick every 60 seconds. When a job fires:
- send_message → saves to otdel history + triggers head agent
- run_prompt → one-shot LLM call → saves response to chat history + broadcasts WS
"""
from __future__ import annotations

import asyncio
import logging
import json
from datetime import datetime
from typing import Any
from types import SimpleNamespace

from .jobs import get_due_jobs, advance_next_run
from ..time import now as _now
from ..services.daemon_manager import DaemonManager

logger = logging.getLogger(__name__)

_tick_task: asyncio.Task | None = None
_TICK_INTERVAL = 60  # seconds


async def _execute_job(job: Any) -> None:
    """Execute a fired cron job.

    Records execution outcome (last_result, last_result_message,
    last_duration_ms, last_run_at) on the job BEFORE advancing the
    schedule. Honors job.delivery — silent jobs skip chat messages.
    """
    from .models import LastResult
    from .jobs import _save_job, get_job
    from ..time import now as _now
    import time

    started = time.time()
    started_iso = _now().isoformat()
    try:
        if job.action_type.value == "send_message":
            await _execute_send_message(job)

        elif job.action_type.value == "run_prompt":
            await _execute_run_prompt(job)

        # Advance next run
        advance_next_run(job)
        # Mark success
        job.last_run_at = started_iso
        job.last_result = LastResult.SUCCESS
        job.last_result_message = ""
        job.last_duration_ms = int((time.time() - started) * 1000)
        _save_job(job)
        logger.info("Cron job %s executed: %s", job.id, job.name)

    except Exception as e:
        # Record error, but still advance one-shot jobs to avoid infinite
        # retry loops. For repeating jobs (cron/interval) we keep the
        # schedule so the next attempt still runs.
        logger.error("Cron job %s failed: %s", job.id, e)
        import traceback
        traceback.print_exc()
        try:
            advance_next_run(job)
        except Exception:
            pass
        try:
            job.last_run_at = started_iso
            job.last_result = LastResult.ERROR
            job.last_result_message = str(e)[:200]
            job.last_duration_ms = int((time.time() - started) * 1000)
            _save_job(job)
        except Exception as save_err:
            logger.error("Failed to record cron error for %s: %s", job.id, save_err)


# ── run_prompt: one-shot LLM call ────────────────────────────────────────


async def _execute_run_prompt(job: Any) -> None:
    """Run a one-shot LLM call for a cron job WITH tool support.

    Calls the agent's LLM with action_message as the prompt,
    executes any tool calls the model requests (up to MAX_TOOL_ITERATIONS),
    saves the final response to chat history, and broadcasts via WS.

    Resolution:
      - action_agent: agent slug to call (e.g. main agent, Лютик)
      - action_target: where to send the response
        - "private" or empty → agent's private chat (channel_id="cron")
        - otdel_id → that otdel's chat
    """
    from ..agents.manager import get_agent
    from ..chat.router import (
        registry, _build_system_prompt_with_memory, _load_chat_history, _save_chat_history,
        execute_tool, build_openai_tools, get_all_tool_names, BUILTINS, build_tool_descriptions,
    )
    from ..chat.providers.base import ChatMessage

    agent_slug = job.action_agent or ""
    if not agent_slug:
        logger.warning("Cron job %s has no action_agent", job.id)
        return

    # Resolve "main_agent" to actual primary agent slug
    if agent_slug == "main_agent":
        try:
            from ..agents.manager import load_agents
            for a in load_agents().get("agents", []):
                if a.get("is_primary"):
                    agent_slug = a.get("slug", "")
                    break
        except Exception:
            pass

    agent_data = get_agent(agent_slug)
    if not agent_data:
        logger.warning("Cron job %s: agent %s not found", job.id, agent_slug)
        return

    prompt = job.action_message or f"Выполни запланированную задачу: {job.name}"

    # Determine channel: "cron" for private chat, otdel_id for otdel chat
    action_target = job.action_target or ""
    if action_target and action_target.startswith("otdel:"):
        channel_id = action_target[len("otdel:"):]
        is_otdel = True
    elif action_target and action_target != "private":
        channel_id = action_target
        is_otdel = True
    else:
        # Private chat — use "web" so messages persist in the same history as UI
        channel_id = "web"
        is_otdel = False

    logger.info("Cron run_prompt: agent=%s, channel=%s, is_otdel=%s, prompt=%s",
                agent_slug, channel_id, is_otdel, prompt[:80])

    # Build system prompt with memory
    req = SimpleNamespace(agent_slug=agent_slug, system_prompt="", channel_id=channel_id)
    full_system_prompt = _build_system_prompt_with_memory(req)

    # Inject cron task as system instruction (NOT as user message in history)
    full_system_prompt += "\n\n## Задача от планировщика (cron)\n" + prompt

    # Load history — last N messages for context, no cron trigger
    history = _load_chat_history(agent_slug, channel_id)

    # Get provider/model
    provider_name = agent_data.get("provider") or None
    model = agent_data.get("model", "")
    temperature = agent_data.get("temperature", 0.7)
    max_tokens = agent_data.get("max_tokens", 4096)
    is_primary = agent_data.get("is_primary", False)

    if registry is None:
        logger.error("Cron run_prompt: chat provider registry not configured")
        return

    provider = registry.get(provider_name) if provider_name else None
    if not provider:
        logger.error("Cron run_prompt: provider %s not found for agent %s", provider_name, agent_slug)
        return

    # Build messages
    messages = [ChatMessage(role=m["role"], content=m["content"]) for m in history]
    if full_system_prompt:
        messages = [ChatMessage(role="system", content=full_system_prompt)] + messages

    # Build tools — primary agent gets head tools too
    tool_names = get_all_tool_names(include_head=is_primary, include_primary=is_primary)
    native_tools = build_openai_tools(tool_names)
    tool_desc = build_tool_descriptions(tool_names)
    if tool_desc and messages and messages[0].role == "system":
        messages[0] = ChatMessage(role="system", content=messages[0].content + tool_desc)

    MAX_TOOL_ITERATIONS = 10
    full_response = ""
    usage = None

    # Tool loop — allow agent to use tools (web_search, terminal, etc.)
    for iteration in range(MAX_TOOL_ITERATIONS):
        iter_text = ""
        iter_tool_calls = []

        try:
            async for chunk in provider.chat(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                tools=native_tools,
            ):
                if chunk.startswith("__USAGE__:"):
                    try:
                        usage = json.loads(chunk[10:])
                    except json.JSONDecodeError:
                        pass
                elif chunk.startswith("__TOOL_CALLS__:"):
                    try:
                        iter_tool_calls = json.loads(chunk[15:])
                    except json.JSONDecodeError:
                        pass
                elif chunk:
                    iter_text += chunk
        except Exception as e:
            logger.error("Cron run_prompt LLM call failed for %s: %s", agent_slug, e)
            full_response = f"[Ошибка LLM: {e}]"
            break

        if not iter_tool_calls:
            # No tool calls — final response
            full_response = iter_text
            break

        # Execute tool calls
        messages.append(ChatMessage(role="assistant", content=iter_text or None, tool_calls=iter_tool_calls))
        for tc in iter_tool_calls:
            fn = tc.get("function", {})
            tc_id = tc.get("id", f"call_{iteration}")
            t_name = fn.get("name", "")
            try:
                t_params = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                t_params = {}

            if t_name not in tool_names and t_name not in BUILTINS:
                result_text = f"Tool '{t_name}' not enabled"
            else:
                result = await execute_tool(t_name, t_params, agent_slug, otdel_id=channel_id if is_otdel else None)
                output = result.get("output", "")
                result_text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)

            messages.append(ChatMessage(role="tool", content=result_text, tool_call_id=tc_id))
        # Continue loop for next LLM call with tool results

    if not full_response:
        logger.warning("Cron run_prompt: empty response from %s", agent_slug)
        return

    # Save assistant response to history
    assistant_entry = {
        "role": "assistant",
        "content": full_response,
        "timestamp": _now().isoformat(),
        "cron_job_id": job.id,
    }
    if model:
        assistant_entry["model"] = model
    if provider_name:
        assistant_entry["provider"] = provider_name
    if agent_data.get("name"):
        assistant_entry["agent_name"] = agent_data["name"]
    if usage:
        assistant_entry["prompt_tokens"] = usage.get("prompt_tokens", 0)
        assistant_entry["completion_tokens"] = usage.get("completion_tokens", 0)

    # Save to correct destination: otdel chat, agent private session, or
    # skip entirely (silent). The is_otdel branch is decided ABOVE based on
    # job.action_target format. The job.delivery field is an orthogonal
    # axis: even if is_otdel=True, a delivery='silent' job skips chat writes.
    from .models import DeliveryMode
    delivery = getattr(job, "delivery", DeliveryMode.PRIVATE)

    if delivery == DeliveryMode.SILENT:
        # Silent: log to memory but don't bloat the chat.
        logger.info("Cron run_prompt: SILENT delivery — skipping chat save/broadcast for %s", job.id)
    elif is_otdel:
        from ..chat.otdel_helpers import _load_history as _load_otdel_history, _save_history as _save_otdel_history
        otdel_history = _load_otdel_history(channel_id)
        otdel_history.append({
            "id": f"cron-{job.id[-8:]}",
            "role": "assistant",
            "sender": agent_slug,
            "sender_name": agent_data.get("name", agent_slug),
            "content": full_response,
            "timestamp": _now().isoformat(),
            "cron_job_id": job.id,
            "model": model,
            "provider": provider_name,
        })
        _save_otdel_history(channel_id, otdel_history)
    else:
        history.append(assistant_entry)
        _save_chat_history(agent_slug, channel_id, history)

    # Broadcast via WS — silent jobs do NOT broadcast chat messages.
    # 'cron:fired' event still goes out so the UI can update its stats card.
    from ..chat.ws_manager import ws_manager

    if delivery != DeliveryMode.SILENT:
        assistant_msg = {
            "id": f"cron-{job.id[-8:]}",
            "role": "assistant",
            "sender": agent_slug,
            "sender_name": agent_data.get("name", agent_slug),
            "content": full_response,
            "timestamp": _now().isoformat(),
            "cron_job_id": job.id,
            "is_head": agent_data.get("is_head", False),
            "model": model,
            "provider": provider_name,
        }

        if is_otdel:
            await ws_manager.broadcast({
                "type": "otdel:message",
                "otdel_id": channel_id,
                "message": assistant_msg,
            })
        else:
            await ws_manager.broadcast({
                "type": "chat:cron",
                "agent_slug": agent_slug,
                "message": assistant_msg,
            })

    # Always broadcast cron:fired so the UI stats card updates.
    await ws_manager.broadcast({
        "type": "cron:fired",
        "job_id": job.id,
        "job_name": job.name,
        "agent_slug": agent_slug,
        "channel": channel_id,
        "delivery": delivery.value,
    })

    logger.info("Cron run_prompt: response saved for %s (%d chars, delivery=%s)",
                agent_slug, len(full_response), delivery.value)


# ── send_message: save to otdel + trigger head ────────────────────────────


async def _execute_send_message(job: Any) -> None:
    """Save message to otdel history, trigger head agent, broadcast WS.

    Honors job.delivery:
      "private" — N/A here (send_message is always to an otdel).
      "otdel"   — write message + trigger head + broadcast (default here).
      "silent"  — skip chat write AND skip head agent trigger. Useful
                  for jobs that just write to memory/log without
                  disrupting the team chat.
    """
    from ..chat.otdel_helpers import _load_history, _save_history
    from ..chat.ws_manager import ws_manager
    from .models import DeliveryMode
    import uuid

    otdel_id = job.action_target
    if not otdel_id:
        logger.warning("Cron job %s has no action_target", job.id)
        return

    delivery = getattr(job, "delivery", DeliveryMode.OTDEL)

    # Build the message regardless of delivery — we always want it for logs
    msg = {
        "id": f"cron-{uuid.uuid4().hex[:8]}",
        "role": "user",
        "sender": "cron",
        "content": job.action_message or f"⏰ Запланированная задача: {job.name}",
        "timestamp": _now().isoformat(),
        "cron_job_id": job.id,
    }

    if delivery == DeliveryMode.SILENT:
        # Silent: log only, no chat write, no head trigger, no WS broadcast.
        logger.info("Cron send_message: SILENT delivery — skipping chat/head for %s (%s)", job.id, job.name)
        return

    # Save user message
    history = _load_history(otdel_id)
    history.append(msg)
    _save_history(otdel_id, history)

    # Broadcast user message to WS clients
    await ws_manager.broadcast({
        "type": "otdel:message",
        "otdel_id": otdel_id,
        "message": msg,
    })

    # Trigger head agent to process the message
    await _trigger_head_agent(otdel_id, job)

    logger.info("Cron send_message: saved to otdel %s, head triggered (delivery=%s)",
                otdel_id, delivery.value)


async def _trigger_head_agent(otdel_id: str, job: Any) -> None:
    """After send_message, trigger the head agent to respond in otdel chat."""
    from ..agents.manager import get_otdel, get_agent
    from ..chat.router import (
        registry, _build_system_prompt_with_memory, _load_chat_history,
        _save_chat_history, execute_tool, build_openai_tools,
        get_all_tool_names, BUILTINS, build_tool_descriptions,
    )
    from ..chat.otdel_helpers import (
        _build_otdel_system_prompt, _build_head_context,
        _build_worker_context, _load_history, _save_history,
    )
    from ..chat.providers.base import ChatMessage

    otdel = get_otdel(otdel_id)
    if not otdel:
        logger.warning("Cron send_message: otdel %s not found", otdel_id)
        return

    head_slug = otdel.get("head", "")
    if not head_slug:
        logger.warning("Cron send_message: otdel %s has no head", otdel_id)
        return

    head_agent = get_agent(head_slug)
    if not head_agent:
        logger.warning("Cron send_message: head agent %s not found", head_slug)
        return

    provider_name = head_agent.get("provider") or None
    model = head_agent.get("model", "")
    temperature = head_agent.get("temperature", 0.7)
    max_tokens = head_agent.get("max_tokens", 4096)
    is_primary = head_agent.get("is_primary", False)

    provider = registry.get(provider_name) if provider_name else None
    if not provider:
        logger.error("Cron send_message: provider %s not found for head %s", provider_name, head_slug)
        return

    # Build system prompt for head
    system_prompt = _build_otdel_system_prompt(otdel, head_agent, is_head=True)

    # Load otdel history
    otdel_history = _load_history(otdel_id)

    # Build messages for LLM
    messages = [ChatMessage(role=m["role"], content=m["content"]) for m in otdel_history]
    if system_prompt:
        messages = [ChatMessage(role="system", content=system_prompt)] + messages

    # Get tools for head agent
    tool_names = get_all_tool_names(include_head=is_primary, include_primary=is_primary)
    native_tools = build_openai_tools(tool_names)
    tool_desc = build_tool_descriptions(tool_names)
    if tool_desc and system_prompt:
        messages[0] = ChatMessage(role="system", content=system_prompt + tool_desc)

    # Tool loop (same pattern as stream_response but without SSE)
    import uuid as _uuid

    for iteration in range(10):  # Max 10 tool iterations
        full_text = ""
        tool_calls = []

        try:
            async for chunk in provider.chat(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                tools=native_tools,
            ):
                if chunk.startswith("__TOOL_CALLS__:"):
                    try:
                        tool_calls = json.loads(chunk[15:])
                    except json.JSONDecodeError:
                        pass
                elif chunk.startswith("__USAGE__:"):
                    pass
                elif chunk:
                    full_text += chunk
        except Exception as e:
            logger.error("Cron head agent LLM call failed: %s", e)
            return

        if not tool_calls:
            # No tool calls — final response
            if full_text:
                assistant_msg = {
                    "id": f"cron-{_uuid.uuid4().hex[:8]}",
                    "role": "assistant",
                    "sender": head_slug,
                    "sender_name": head_agent.get("name", head_slug),
                    "content": full_text,
                    "timestamp": _now().isoformat(),
                    "cron_job_id": job.id,
                    "is_head": True,
                    "model": model,
                    "provider": provider_name,
                }
                otdel_history.append(assistant_msg)
                _save_history(otdel_id, otdel_history)

                from ..chat.ws_manager import ws_manager
                await ws_manager.broadcast({
                    "type": "otdel:message",
                    "otdel_id": otdel_id,
                    "message": assistant_msg,
                })
            break

        # Execute tool calls and append results
        messages.append(ChatMessage(role="assistant", content=full_text or None, tool_calls=tool_calls))
        for tc in tool_calls:
            fn = tc.get("function", {})
            tc_id = tc.get("id", f"call_{iteration}")
            t_name = fn.get("name", "")
            try:
                t_params = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                t_params = {}

            if t_name not in tool_names and t_name not in BUILTINS:
                result_text = f"Tool '{t_name}' not enabled"
            else:
                result = await execute_tool(t_name, t_params, head_slug, otdel_id=otdel_id)
                output = result.get("output", "")
                result_text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)

            messages.append(ChatMessage(role="tool", content=result_text, tool_call_id=tc_id))

    logger.info("Cron head agent triggered in otdel %s", otdel_id)


# ── Scheduler tick loop ──────────────────────────────────────────────────


async def _tick_loop() -> None:
    """Background loop — check for due jobs every minute."""
    while True:
        try:
            due = get_due_jobs()
            for job in due:
                logger.info("Cron tick: firing job %s (%s)", job.id, job.name)
                await _execute_job(job)
        except Exception as e:
            logger.error("Cron tick error: %s", e)
        await asyncio.sleep(_TICK_INTERVAL)


def start_scheduler() -> None:
    """Start the cron scheduler background task."""
    global _tick_task
    if _tick_task and not _tick_task.done():
        return  # already running

    # Sweep missed one-shot jobs at startup
    from .jobs import sweep_missed_jobs
    missed = sweep_missed_jobs()
    if missed:
        logger.info("[cron] Sweep: marked %d missed one-shot job(s): %s", len(missed), missed)

    try:
        loop = asyncio.get_running_loop()
        _tick_task = loop.create_task(_tick_loop())
        logger.info("[cron] Scheduler started (tick every %ds)", _TICK_INTERVAL)
    except RuntimeError:
        logger.warning("[cron] No running event loop, cannot start scheduler")


def register_cron_scheduler(dm: DaemonManager) -> None:
    """Register cron tick with DaemonManager."""
    # Sweep missed jobs at registration time
    from .jobs import sweep_missed_jobs
    missed = sweep_missed_jobs()
    if missed:
        logger.info("[cron] Sweep: marked %d missed one-shot job(s): %s", len(missed), missed)

    # Start the tick loop via DaemonManager
    global _tick_task
    try:
        loop = asyncio.get_running_loop()
        _tick_task = loop.create_task(_tick_loop())
        dm._services["cron-scheduler"] = type("svc", (), {
            "name": "cron-scheduler",
            "_task": _tick_task,
            "is_async": True,
        })()
        logger.info("[cron] Scheduler registered with DaemonManager")
    except RuntimeError:
        logger.warning("[cron] No running event loop")
