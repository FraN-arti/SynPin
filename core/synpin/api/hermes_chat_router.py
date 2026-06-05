"""REST API for Hermes Agent chat proxy.

Hermes maintains its own context, memory, and session management.
SynPin only needs to persist conversation history for agent-switch continuity.
"""
import httpx
import json
import os
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["hermes-chat"])

HERMES_API_URL = "http://127.0.0.1:8642"
HERMES_API_KEY = ""  # Will be loaded from config

# History storage
_DATA_DIR = None
MAX_HISTORY_MESSAGES = 100


def _get_data_dir():
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


class HermesChatRequest(BaseModel):
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

    # Compact history if too long (same logic as internal agents)
    if agent_slug and history:
        try:
            from ..chat.router import compact_messages
            history, compaction_notice = compact_messages(
                history,
                system_prompt=req.system_prompt or "",
                agent_slug=agent_slug,
            )
            if compaction_notice:
                logger.info("Hermes compaction for %s: %s", agent_slug, compaction_notice)
        except Exception as e:
            logger.warning("Compaction failed for Hermes %s: %s", agent_slug, e)

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

    async def wrapped_stream():
        """Stream response and save history after completion."""
        async for chunk in stream_hermes_response(messages, req.temperature, req.max_tokens):
            yield chunk

        # Save history after streaming completes
        if agent_slug:
            updated_history = list(history)
            updated_history.append({"role": "user", "content": req.message})
            _save_chat_history(agent_slug, channel_id, updated_history)

    return StreamingResponse(
        wrapped_stream(),
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
