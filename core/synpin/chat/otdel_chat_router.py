"""Otdel Chat Router — independent chat for each department.

Flow:
1. User sends message → saved to otdel chat history
2. @mentions parsed → Head always sees everything, workers only when @mentioned
3. Each agent gets: otdel system prompt + own prompt + relevant history
4. LLM called for each responding agent → response saved to history
5. After workers respond, Head gets a follow-up turn to acknowledge/summarize
"""
import json
import asyncio
import re
import logging
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .providers import ProviderRegistry
from .providers.base import ChatMessage
from .task_manager import task_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/otdels", tags=["otdel-chat"])

# Global registry — set during app startup
registry: ProviderRegistry | None = None

# Import shared history + helpers from otdel_helpers (single source of truth)
from .ws_router import create_head_state, get_head_state
from .otdel_helpers import (
    _load_history,
    _save_history,
    _parse_mentions,
    _build_otdel_system_prompt,
    _build_head_context,
    _build_worker_context,
    _get_agent_name,
)


# ── API Endpoints ──────────────────────────────────────────────────────────

class OtdelChatSend(BaseModel):
    message: str
    sender: str = "user"  # "user" for Artur, agent slug for agents


@router.get("/{otdel_id}/chat/history")
async def get_otdel_chat_history(otdel_id: str):
    """Get chat history for an otdel."""
    messages = _load_history(otdel_id)
    return {"messages": messages}


async def _notify_compaction(chat_task, save_result: dict):
    """Send compaction notification via WebSocket."""
    try:
        event = json.dumps({
            "type": "otdel:compacting",
            "otdel_id": chat_task.otdel_id,
            "before": save_result.get("before", 0),
            "after": save_result.get("after", 0),
        }, ensure_ascii=False)
        await chat_task.queue.put(event)
    except Exception:
        pass


@router.post("/{otdel_id}/chat/send")
async def send_otdel_chat_message(otdel_id: str, req: OtdelChatSend):
    """Send a message to otdel chat and trigger agent responses.
    
    Flow:
    1. Save user message
    2. Parse @mentions
    3. Head always processes (sees everything)
    4. Mentioned workers process their mentions
    5. After workers respond, Head gets a follow-up turn
    """
    if registry is None:
        raise HTTPException(500, "Chat provider not configured")
    
    # Load otdel data
    from ..agents.manager import get_otdel, get_agent, load_otdels
    otdel = get_otdel(otdel_id)
    if not otdel:
        raise HTTPException(404, f"Otdel not found: {otdel_id}")
    
    # Save user message
    history = _load_history(otdel_id)
    user_msg = {
        "id": f"u-{uuid.uuid4().hex[:8]}",
        "role": "user",
        "sender": req.sender,
        "content": req.message,
        "timestamp": datetime.now().isoformat(),
    }
    history.append(user_msg)
    save_result = _save_history(otdel_id, history)
    if save_result.get("was_compacted"):
        await _notify_compaction(chat_task, save_result)
    
    # Parse @mentions from user message
    user_mentions = _parse_mentions(req.message)
    
    # Find head agent
    head_slug = otdel.get("head", "")
    head_agent = get_agent(head_slug) if head_slug else None
    head_name = head_agent.get("name", head_slug) if head_agent else head_slug
    
    # Find worker agents
    worker_slugs = otdel.get("workers", [])
    agents_to_process = []
    
    # Head always processes (sees everything)
    if head_agent:
        agents_to_process.append((head_agent, True))
    
    # Workers process if @mentioned in user message
    for slug in worker_slugs:
        if slug == head_slug:
            continue
        agent = get_agent(slug)
        if not agent:
            continue
        agent_name_lower = agent.get("name", "").lower()
        agent_slug_lower = slug.lower()
        if agent_name_lower in user_mentions or agent_slug_lower in user_mentions:
            agents_to_process.append((agent, False))
    
    # If no agents to process, just return
    if not agents_to_process:
        return {
            "ok": True,
            "message_id": user_msg["id"],
            "responses": [],
        }
    
    # Process agents iteratively: user message -> Head -> @mentions -> Workers -> Head follow-up
    task_id = f"otdel_{otdel_id}_{uuid.uuid4().hex[:8]}"
    chat_task = task_manager.create(task_id)
    
    async def _process_agents():
        """Process agents iteratively until no new @mentions."""
        log = logging.getLogger("synpin.otdel")
        responses = []

        # Queue of agents to process: (agent, is_head, trigger_message)
        agent_queue = [(agent, True, req.message) for agent in [head_agent] if agent]
        
        # Add workers mentioned in user message
        for slug in worker_slugs:
            if slug == head_slug:
                continue
            agent = get_agent(slug)
            if not agent:
                logger.warning("Worker agent %s NOT FOUND in otdel %s", slug, otdel_id)
                continue
            agent_name_lower = agent.get("name", "").lower()
            agent_slug_lower = slug.lower()
            if agent_name_lower in user_mentions or agent_slug_lower in user_mentions:
                agent_queue.append((agent, False, req.message))
        
        logger.info("Otdel %s agent_queue: %s", otdel_id, [(a.get("name"), h) for a, h, _ in agent_queue])
        
        processed_count = 0
        
        # Create HeadState for this otdel session (needed for head_delegate tool)
        try:
            create_head_state(otdel_id, head_slug, worker_slugs)
            logger.info("Created HeadState for otdel %s", otdel_id)
        except Exception as e:
            logger.warning("Failed to create HeadState for otdel %s: %s", otdel_id, e)
        head_processed = False
        workers_responded = 0
        max_iterations = 10  # Prevent infinite loops
        expected_workers = set()   # Slugs of workers Head @mentioned (gather targets)
        responded_workers = set()  # Slugs of workers who actually responded
        head_delegating = False    # True when Head delegated (suppress first response)
        processed_slugs = set()    # Deduplication — don't process same agent twice
        followup_done = False      # Only allow ONE follow-up per request
        
        while agent_queue and processed_count < max_iterations:
            agent, is_head, trigger_message = agent_queue.pop(0)
            agent_slug_val = agent.get("slug", "")
            agent_name_val = agent.get("name", "")
            
            # Build system prompt
            system_prompt = _build_otdel_system_prompt(otdel, agent, is_head)
            
            # Reload history to get all messages so far
            history = _load_history(otdel_id)
            
            # Build context based on role
            if is_head:
                context_messages = _build_head_context(history, agent_slug_val)
                head_processed = True
            else:
                context_messages = _build_worker_context(history, agent_slug_val, head_slug, head_name)
            
            # Build messages for LLM
            messages = [ChatMessage(role=m["role"], content=m["content"]) for m in context_messages]
            messages.append(ChatMessage(role="user", content=trigger_message))
            
            # Get provider/model info
            model = agent.get("model", "default")
            provider_name = agent.get("provider")
            
            # Strip provider prefix
            if provider_name and model.startswith(f"{provider_name}/"):
                model = model[len(provider_name) + 1:]
            
            # Determine tools for this agent
            if is_head:
                head_protocol_tools = ["head_delegate", "head_evaluate", "head_retry", "head_decide", "kanban_task"]
                tool_names = list(agent.get("tools", [])) + head_protocol_tools
            else:
                tool_names = agent.get("tools", [])

            # Call LLM
            full_response = ""
            logger.info("Otdel %s calling LLM for %s (model=%s, provider=%s)", otdel_id, agent_name_val, model, provider_name)
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
                    # Capture content from SSE chunks
                    if '"type": "chunk"' in chunk:
                        try:
                            payload = json.loads(chunk.split("data: ", 1)[1].split("\n")[0])
                            if payload.get("type") == "chunk":
                                full_response += payload.get("content", "")
                        except Exception:
                            pass
            except Exception as e:
                logger.error("LLM call failed for agent %s in otdel %s: %s", agent_slug_val, otdel_id, e)
                full_response = f"⚠️ Ошибка: {e}"
            
            logger.info("Otdel %s %s responded: %d chars", otdel_id, agent_name_val, len(full_response))
            
            # Save agent response
            if full_response:
                agent_msg = {
                    "id": f"a-{uuid.uuid4().hex[:8]}",
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
                _save_history(otdel_id, history)
                responses.append(agent_msg)
                
                if is_head:
                    # Check HeadState first — head_delegate tool sets expected_workers there
                    hs = get_head_state(otdel_id)
                    if hs and hs.expected_workers:
                        for slug in hs.expected_workers:
                            if slug in worker_slugs and slug != head_slug and slug != agent_slug_val:
                                if slug not in processed_slugs:
                                    agent = get_agent(slug)
                                    if agent:
                                        expected_workers.add(slug)
                                        delegation = hs.current_delegation or {}
                                        workers_list = delegation.get("workers", [])
                                        task_text = ""
                                        for w in workers_list:
                                            if w.get("slug") == slug:
                                                task_text = w.get("task", full_response.strip())
                                                break
                                        agent_queue.append((agent, False, task_text or full_response.strip()))
                                        logger.info("Otdel %s head_delegate: queueing %s (task=%s)", otdel_id, agent.get("name"), task_text[:60] if task_text else "")
                    else:
                        # Fallback: check @mentions in text (for models that don't use tools)
                        new_mentions = _parse_mentions(full_response)
                        logger.info("Otdel %s Head response mentions=%s (fallback)", otdel_id, new_mentions)
                        
                        for slug in worker_slugs:
                            if slug == head_slug or slug == agent_slug_val:
                                continue
                            mentioned_agent = get_agent(slug)
                            if not mentioned_agent:
                                continue
                            mentioned_name_lower = mentioned_agent.get("name", "").lower()
                            mentioned_slug_lower = slug.lower()
                            if mentioned_name_lower in new_mentions or mentioned_slug_lower in new_mentions:
                                expected_workers.add(slug)
                                if slug not in processed_slugs:
                                    trigger = re.sub(r'^\[.*?\]:\s*', '', full_response.strip())
                                    agent_queue.append((mentioned_agent, False, trigger))
                                    logger.info("Otdel %s gather: expecting %s", otdel_id, mentioned_agent.get("name"))
                    
                    if expected_workers:
                        head_delegating = True
                        logger.info("Otdel %s Head delegating to %d workers: %s", otdel_id, len(expected_workers), expected_workers)
                    else:
                        # Head responded directly (no delegation) — show immediately
                        event_data = json.dumps(agent_msg, ensure_ascii=False)
                        await chat_task.queue.put(event_data)
                else:
                    # Worker response — always show to user
                    responded_workers.add(agent_slug_val)
                    workers_responded += 1
                    event_data = json.dumps(agent_msg, ensure_ascii=False)
                    await chat_task.queue.put(event_data)
                
                processed_slugs.add(agent_slug_val)
            
            processed_count += 1
        
        # ── Head follow-up (gather pattern) ──────────────────────────────
        # If Head delegated: wait for ALL expected workers, then follow-up
        # If Head didn't delegate but workers responded: follow-up anyway
        should_followup = False
        if head_delegating and expected_workers:
            missing = expected_workers - responded_workers
            if not missing:
                should_followup = True
                logger.info("Otdel %s all %d workers responded — running Head follow-up", otdel_id, len(expected_workers))
            else:
                logger.warning("Otdel %s missing responses from %s", otdel_id, missing)
        elif head_processed and workers_responded > 0 and not head_delegating:
            # Workers were @mentioned by user directly (not by Head)
            should_followup = True
        
        if should_followup and processed_count < max_iterations and not followup_done:
            followup_done = True
            history = _load_history(otdel_id)
            context_messages = _build_head_context(history, head_slug, exclude_last=False)
            
            if head_delegating:
                # Find original user message for context
                original_task = ""
                for m in history:
                    if m.get("sender") == "user":
                        original_task = m.get("content", "")
                acknowledge_trigger = (
                    "Работники отдела ответили. Проанализируй их ответы.\n"
                    f"Исходная задача пользователя: «{original_task}»\n"
                    "Если задача многоэтапная и есть ещё невыполненные этапы — "
                    "продолжай, вызывай head_delegate для следующего этапа.\n"
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
                    tool_names=["head_delegate", "head_evaluate", "head_retry", "head_decide", "kanban_task"],
                    otdel_id=otdel_id,
                ):
                    if '"type": "chunk"' in chunk:
                        try:
                            payload = json.loads(chunk.split("data: ", 1)[1].split("\n")[0])
                            if payload.get("type") == "chunk":
                                full_response += payload.get("content", "")
                        except Exception:
                            pass
            except Exception as e:
                logger.error("Head follow-up failed in otdel %s: %s", otdel_id, e)
                full_response = ""
            
            if full_response:
                agent_msg = {
                    "id": f"a-{uuid.uuid4().hex[:8]}",
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
                _save_history(otdel_id, history)
                responses.append(agent_msg)
                
                event_data = json.dumps(agent_msg, ensure_ascii=False)
                await chat_task.queue.put(event_data)
        
        # Signal completion and cleanup
        await chat_task.queue.put(None)
        task_manager.cleanup(task_id)
    
    # Start background task
    chat_task.task = asyncio.create_task(_process_agents())

    # Return immediately — frontend polls for responses
    return {
        "ok": True,
        "message_id": user_msg["id"],
        "task_id": task_id,
    }


@router.get("/{otdel_id}/chat/task/{task_id}")
async def get_otdel_chat_task(otdel_id: str, task_id: str):
    """Poll task status for streaming responses.
    
    DEPRECATED: Use WebSocket /ws with type='otdel:send' instead.
    This endpoint is kept for backward compatibility.
    """
    task = task_manager.get(task_id)
    if not task:
        return {"status": "completed", "done": True}
    
    # Check if done
    try:
        chunk = await asyncio.wait_for(task.queue.get(), timeout=0.1)
        if chunk is None:
            task_manager.cleanup(task_id)
            return {"status": "completed", "done": True}
        # Try to parse as agent response JSON
        try:
            message = json.loads(chunk)
            return {"status": "running", "done": False, "message": message}
        except (json.JSONDecodeError, TypeError):
            return {"status": "running", "done": False}
    except asyncio.TimeoutError:
        return {"status": "running", "done": False}
