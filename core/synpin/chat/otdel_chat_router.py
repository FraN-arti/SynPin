"""Otdel Chat Router — independent chat for each department.

Flow:
1. User sends message → saved to otdel chat history
2. @mentions parsed → Head always sees everything, workers only when @mentioned
3. Each agent gets: otdel system prompt + own prompt + relevant history
4. LLM called for each responding agent → response saved to history
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

# Shared data dir
_DATA_DIR: Path | None = None

MAX_HISTORY_MESSAGES = 200


def _get_data_dir() -> Path:
    global _DATA_DIR
    if _DATA_DIR is not None:
        return _DATA_DIR
    candidates = [
        Path.home() / ".synpin" / "data",
        Path(__file__).resolve().parent.parent.parent / "data",
    ]
    for candidate in candidates:
        if candidate.exists():
            _DATA_DIR = candidate
            return _DATA_DIR
    _DATA_DIR = candidates[0]
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _DATA_DIR


# ── History Storage ────────────────────────────────────────────────────────

def _get_otdel_chat_path(otdel_id: str) -> Path:
    data_dir = _get_data_dir()
    return data_dir / "otdels" / otdel_id / "chat.json"


def _load_history(otdel_id: str) -> list[dict]:
    path = _get_otdel_chat_path(otdel_id)
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load otdel chat history for %s: %s", otdel_id, e)
        return []


def _save_history(otdel_id: str, messages: list[dict]):
    path = _get_otdel_chat_path(otdel_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    trimmed = messages[-MAX_HISTORY_MESSAGES:]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=1)


# ── @Mention Parsing ───────────────────────────────────────────────────────

def _parse_mentions(text: str) -> list[str]:
    """Extract @mentions from message text.
    
    Supports: @AgentName, @Agent Name (with space)
    Returns list of mentioned agent names (lowercased for matching).
    """
    # Match @name or @name surname (up to next @ or end of line)
    matches = re.findall(r'@([A-Za-zА-Яа-яЁё0-9_]+(?:\s+[A-Za-zА-Яа-яЁё0-9_]+)*)', text)
    return [m.strip().lower() for m in matches]


# ── System Prompt Building ─────────────────────────────────────────────────

def _build_otdel_system_prompt(otdel: dict, agent: dict, is_head: bool) -> str:
    """Build system prompt for an agent in otdel chat.
    
    Combines: agent's own prompt + otdel context + role in otdel.
    """
    parts = []
    
    # Agent's own system prompt (FIRST - this is their identity)
    own_prompt = agent.get("system_prompt", "")
    if own_prompt:
        parts.append(own_prompt)
    
    # Build workers list for Head
    worker_list = ""
    if is_head:
        worker_slugs = otdel.get("workers", [])
        head_slug = otdel.get("head", "")
        from ..agents.manager import get_agent
        worker_names = []
        for slug in worker_slugs:
            if slug == head_slug:
                continue
            w = get_agent(slug)
            if w:
                worker_names.append(f"@{w.get('name', slug)} ({slug})")
        if worker_names:
            worker_list = f"\n\nТвоя команда (обращайся через @Имя):\n" + "\n".join(f"- {n}" for n in worker_names)
        else:
            worker_list = "\n\nВ отделе пока нет работников."
    
    # Otdel context
    otdel_name = otdel.get("name", "")
    otdel_desc = otdel.get("description", "")
    role_label = "Глава отдела" if is_head else "Работник отдела"
    
    separator = "═" * 46
    otdel_block = f"""
{separator}
ОТДЕЛ: {otdel_name}
{otdel_desc}
Твоя роль: {role_label}{worker_list}
{separator}"""
    parts.append(otdel_block)
    
    # Chat rules
    rules = """
Правила общения в чате отдела:
- Ты работаешь в команде отдела
- Обращаются к тебе через @ТвоёИмя
- Если к тебе обратились — выполняй задачу
- Глава отдела управляет командой — подчиняйся его указаниям
- Не начинай работу самостоятельно пока тебя не попросят
- Отвечай кратко и по делу
- Если задача выполнена — отчитайся через @Глава"""
    
    if is_head:
        rules = """
Ты — Глава отдела. Твоя роль:
- Управляй командой: ставь задачи, принимай результаты
- Видишь ВСЕ сообщения в чате отдела
- Распределяй задачи между работниками через @упоминания
- ОБЯЗАТЕЛЬНО используй имена из списка выше — других агентов в чате нет
- Оценивай результаты работы
- Если работник отчитался — прими работу или запроси исправление
- Не отвечай "ок, принял" без необходимости — это создаёт лишний шум
- Если нужно — передавай информацию наверх (пользователю)
- Не выполняй работу за работников — делегируй"""
    
    parts.append(rules)
    
    return "\n\n".join(parts)


# ── API Endpoints ──────────────────────────────────────────────────────────

class OtdelChatSend(BaseModel):
    message: str
    sender: str = "user"  # "user" for Artur, agent slug for agents


@router.get("/{otdel_id}/chat/history")
async def get_otdel_chat_history(otdel_id: str):
    """Get chat history for an otdel."""
    messages = _load_history(otdel_id)
    return {"messages": messages}


@router.post("/{otdel_id}/chat/send")
async def send_otdel_chat_message(otdel_id: str, req: OtdelChatSend):
    """Send a message to otdel chat and trigger agent responses.
    
    Flow:
    1. Save user message
    2. Parse @mentions
    3. Head always processes (sees everything)
    4. Mentioned workers process their mentions
    5. Each agent's response is saved to history
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
    _save_history(otdel_id, history)
    
    # Parse @mentions from user message
    user_mentions = _parse_mentions(req.message)
    
    # Find head agent
    head_slug = otdel.get("head", "")
    head_agent = get_agent(head_slug) if head_slug else None
    
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
        if agent_name_lower in user_mentions:
            agents_to_process.append((agent, False))
    
    # If no agents to process, just return
    if not agents_to_process:
        return {
            "ok": True,
            "message_id": user_msg["id"],
            "responses": [],
        }
    
    # Process agents iteratively: user message -> Head -> @mentions in Head response -> Workers -> etc.
    task_id = f"otdel_{otdel_id}_{uuid.uuid4().hex[:8]}"
    chat_task = task_manager.create(task_id)
    
    async def _process_agents():
        """Process agents iteratively until no new @mentions."""
        responses = []
        
        # Queue of agents to process: (agent, is_head, triggering_message)
        # triggering_message is the message content that caused this agent to be called
        agent_queue = [(agent, True, req.message) for agent in [head_agent] if agent]
        
        # Add workers mentioned in user message
        for slug in worker_slugs:
            if slug == head_slug:
                continue
            agent = get_agent(slug)
            if not agent:
                continue
            agent_name_lower = agent.get("name", "").lower()
            if agent_name_lower in user_mentions:
                agent_queue.append((agent, False, req.message))
        
        processed_count = 0
        max_iterations = 10  # Prevent infinite loops
        
        while agent_queue and processed_count < max_iterations:
            agent, is_head, trigger_message = agent_queue.pop(0)
            agent_slug = agent.get("slug", "")
            agent_name = agent.get("name", "")
            
            # Build system prompt
            system_prompt = _build_otdel_system_prompt(otdel, agent, is_head)
            
            # Reload history to get all messages so far
            history = _load_history(otdel_id)
            
            # Build context
            if is_head:
                # Head sees everything
                context_messages = [
                    {"role": m.get("role", "user"), "content": f"[{m.get('sender', '?')}] {m.get('content', '')}"}
                    for m in history[:-1]  # Exclude current trigger message
                ]
            else:
                # Worker sees: user messages, head messages mentioning them, own messages
                context_messages = []
                for m in history[:-1]:
                    sender = m.get("sender", "")
                    content = m.get("content", "")
                    if sender == "user" or sender == agent_slug:
                        context_messages.append({
                            "role": "user" if sender != agent_slug else "assistant",
                            "content": f"[{sender}] {content}" if sender != agent_slug else content,
                        })
                    elif sender == head_slug:
                        # Include head messages (they may contain @mentions to this worker)
                        context_messages.append({
                            "role": "user",
                            "content": f"[{agent_name}] {content}",
                        })
            
            # Build messages for LLM
            messages = [ChatMessage(role=m["role"], content=m["content"]) for m in context_messages]
            messages.append(ChatMessage(role="user", content=trigger_message))
            
            # Get provider/model info
            model = agent.get("model", "default")
            provider_name = agent.get("provider")
            
            # Strip provider prefix
            if provider_name and model.startswith(f"{provider_name}/"):
                model = model[len(provider_name) + 1:]
            
            # Call LLM
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
                    agent_name=agent_name,
                    agent_slug=agent_slug,
                    tool_names=agent.get("tools", []),
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
                logger.error("LLM call failed for agent %s in otdel %s: %s", agent_slug, otdel_id, e)
                full_response = f"⚠️ Ошибка: {e}"
            
            # Save agent response
            if full_response:
                agent_msg = {
                    "id": f"a-{uuid.uuid4().hex[:8]}",
                    "role": "assistant",
                    "sender": agent_slug,
                    "sender_name": agent_name,
                    "content": full_response,
                    "is_head": is_head,
                    "timestamp": datetime.now().isoformat(),
                }
                history.append(agent_msg)
                _save_history(otdel_id, history)
                responses.append(agent_msg)
                
                # Check for NEW @mentions in this response
                new_mentions = _parse_mentions(full_response)
                if new_mentions and not is_head:
                    # Head mentioned someone - add them to queue
                    for slug in worker_slugs:
                        if slug == head_slug or slug == agent_slug:
                            continue
                        mentioned_agent = get_agent(slug)
                        if not mentioned_agent:
                            continue
                        mentioned_name_lower = mentioned_agent.get("name", "").lower()
                        if mentioned_name_lower in new_mentions:
                            agent_queue.append((mentioned_agent, False, full_response))
            
            processed_count += 1
        
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
    """Poll task status for streaming responses."""
    task = task_manager.get(task_id)
    if not task:
        return {"status": "completed", "done": True}
    
    # Check if done
    try:
        chunk = await asyncio.wait_for(task.queue.get(), timeout=0.1)
        if chunk is None:
            task_manager.cleanup(task_id)
            return {"status": "completed", "done": True}
        return {"status": "running", "done": False, "chunk": chunk}
    except asyncio.TimeoutError:
        return {"status": "running", "done": False}
