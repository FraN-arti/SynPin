"""REST API for Hermes Agent chat proxy.

Hermes maintains its own context, memory, and session management.
SynPin only needs to persist conversation history for agent-switch continuity.

Architecture: background task execution decoupled from HTTP response.
- User message saved immediately to disk
- LLM execution runs in asyncio.Task (survives client disconnect)
- SSE streaming reads from asyncio.Queue (real-time)
- History saved by background task (independent of client)
"""
import httpx
import json
import os
import logging
import uuid
import asyncio
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from ._base import BaseRequest

from ..chat.task_manager import task_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["hermes-chat"])

HERMES_API_URL = "http://127.0.0.1:8642"
HERMES_API_KEY = ""  # Will be loaded from config

# History storage — Hermes keeps long history for context continuity
MAX_HISTORY_MESSAGES = 1000  # Large limit — Hermes manages its own context

from ..paths_legacy import _get_data_dir as _get_data_dir  # re-export


def _get_history_path(agent_slug: str, channel_id: str):
    data_dir = _get_data_dir()
    if not data_dir:
        return None
    return data_dir / "agents" / agent_slug / "sessions" / f"{channel_id}.json"


def _load_chat_history(agent_slug: str, channel_id: str) -> list[dict]:
    path = _get_history_path(agent_slug, channel_id)
    if not path or not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load history for %s/%s: %s", agent_slug, channel_id, e)
        return []


def _save_chat_history(agent_slug: str, channel_id: str, messages: list[dict]):
    path = _get_history_path(agent_slug, channel_id)
    if not path:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        trimmed = messages[-MAX_HISTORY_MESSAGES:]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(trimmed, f, ensure_ascii=False, indent=1)
    except Exception as e:
        logger.warning("Failed to save history for %s/%s: %s", agent_slug, channel_id, e)


class HermesChatRequest(BaseRequest):
    message: str
    history: list[dict[str, str]] = []
    system_prompt: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    agent_name: str | None = None
    agent_slug: str | None = None  # For history persistence
    channel_id: str | None = None  # For history persistence


def _get_hermes_key() -> str:
    """Load Hermes API key from .env file."""
    global HERMES_API_KEY
    if HERMES_API_KEY:
        return HERMES_API_KEY

    home = Path.home()
    candidates = [
        Path(os.environ.get("HERMES_HOME", "")) / ".env" if os.environ.get("HERMES_HOME") else None,
        home / "AppData" / "Local" / "hermes" / ".env",
        home / ".hermes" / ".env",
    ]

    for env_path in candidates:
        if env_path and env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("API_SERVER_KEY="):
                    HERMES_API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return HERMES_API_KEY
    return ""


async def stream_hermes_response(
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int | None,
):
    """SSE stream proxy to Hermes API server."""
    api_key = _get_hermes_key()

    payload = {
        "model": "hermes-agent",
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    full_content = ""
    usage = None
    model = "hermes-agent"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{HERMES_API_URL}/v1/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Hermes API error {response.status_code}: {error_body.decode()}'})}\n\n"
                    return

                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    lines = buffer.split("\n")
                    buffer = lines.pop() or ""

                    for line in lines:
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue

                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        choices = data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full_content += content
                                yield f"data: {json.dumps({'type': 'chunk', 'content': content})}\n\n"

                        if "usage" in data:
                            usage = data["usage"]
                        if "model" in data:
                            model = data["model"]

    except httpx.ConnectError:
        yield f"data: {json.dumps({'type': 'error', 'message': 'Hermes API server not available. Make sure gateway is running.'})}\n\n"
        return
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        return

    done_data = {"type": "done", "model": model, "agent_name": "Hermes Agent"}
    if usage:
        done_data["usage"] = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
    yield f"data: {json.dumps(done_data)}\n\n"


@router.post("/hermes/stream")
async def hermes_chat_stream(req: HermesChatRequest):
    """Stream chat response from Hermes Agent via SSE.

    History persistence: SynPin saves conversation history to disk so that
    when the user switches agents and comes back, the context is restored.
    Hermes handles its own memory/session — we only persist the conversation.
    """
    channel_id = req.channel_id or "web"
    agent_slug = req.agent_slug

    # Load persisted history if available
    history = list(req.history)
    if agent_slug:
        persisted = _load_chat_history(agent_slug, channel_id)
        # Use frontend history if longer (has current session), else persisted
        if len(persisted) > len(history):
            history = persisted

    # NOTE: No compaction for Hermes — it manages its own context/memory.
    # History is persisted to disk with a large limit (MAX_HISTORY_MESSAGES=1000)
    # so context survives browser/system restarts.

    # Build messages for Hermes
    messages = []

    # System prompt (from frontend — contains SynPin identity context)
    if req.system_prompt:
        messages.append({"role": "system", "content": req.system_prompt})

    # History
    for msg in history:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

    # Current message
    messages.append({"role": "user", "content": req.message})

    # ── Background execution: decoupled from HTTP response ──
    # 1. Save user message IMMEDIATELY
    if agent_slug:
        updated_history = list(history)
        updated_history.append({"role": "user", "content": req.message})
        _save_chat_history(agent_slug, channel_id, updated_history)

    # 2. Create background task for Hermes LLM execution
    task_id = f"hermes_{channel_id}_{uuid.uuid4().hex[:8]}"

    async def _background_execution():
        """Run Hermes LLM in background — survives client disconnect."""
        try:
            full_response = ""
            async for chunk in stream_hermes_response(messages, req.temperature, req.max_tokens):
                await hermes_task.queue.put(chunk)
                # Capture assistant response for history
                if '"type": "chunk"' in chunk:
                    try:
                        payload = json.loads(chunk.split("data: ", 1)[1].split("\n")[0])
                        if payload.get("type") == "chunk":
                            full_response += payload.get("content", "")
                    except Exception:
                        pass

            # Save assistant response after streaming completes
            if agent_slug and full_response:
                updated_history = list(history)
                updated_history.append({"role": "user", "content": req.message})
                updated_history.append({"role": "assistant", "content": full_response})
                _save_chat_history(agent_slug, channel_id, updated_history)

        except Exception as e:
            # Save error message to history so polling won't loop forever
            logger.error("Hermes background task failed for %s: %s", agent_slug, e)
            if agent_slug:
                error_msg = f"\u26a0\ufe0f \u041e\u0448\u0438\u0431\u043a\u0430: Hermes \u043d\u0435 \u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d ({e})"
                updated_history = list(history)
                updated_history.append({"role": "user", "content": req.message})
                updated_history.append({"role": "assistant", "content": error_msg})
                _save_chat_history(agent_slug, channel_id, updated_history)

        # Signal completion (always, even on error)
        await hermes_task.queue.put(None)

    hermes_task = task_manager.create(task_id)
    hermes_task.task = asyncio.create_task(_background_execution())

    # 3. SSE generator reads from queue (real-time streaming)
    async def _sse_from_queue():
        """Read chunks from background task queue."""
        while True:
            chunk = await hermes_task.queue.get()
            if chunk is None:
                break
            yield chunk
        # Cleanup
        task_manager.cleanup(task_id)

    return StreamingResponse(
        _sse_from_queue(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/hermes/health")
async def hermes_health():
    """Check if Hermes API server is available."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{HERMES_API_URL}/health")
            if resp.status_code == 200:
                return {"status": "ok", "available": True}
    except Exception:
        pass
    return {"status": "unavailable", "available": False}
