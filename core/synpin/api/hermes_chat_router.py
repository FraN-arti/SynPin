"""REST API for Hermes Agent chat proxy."""
import httpx
import json
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/chat", tags=["hermes-chat"])

HERMES_API_URL = "http://127.0.0.1:8642"
HERMES_API_KEY = ""  # Will be loaded from config


class HermesChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = []
    system_prompt: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    agent_name: str | None = None


def _get_hermes_key() -> str:
    """Load Hermes API key from .env file."""
    global HERMES_API_KEY
    if HERMES_API_KEY:
        return HERMES_API_KEY

    # Check multiple possible .env locations
    home = Path.home()
    candidates = [
        Path(os.environ.get("HERMES_HOME", "")) / ".env" if os.environ.get("HERMES_HOME") else None,
        home / "AppData" / "Local" / "hermes" / ".env",  # Windows
        home / ".hermes" / ".env",  # Linux/macOS
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

                        # Extract content from OpenAI format
                        choices = data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                full_content += content
                                yield f"data: {json.dumps({'type': 'chunk', 'content': content})}\n\n"

                        # Extract usage from final chunk
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

    # Send done event
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
    """Stream chat response from Hermes Agent via SSE."""
    # Build messages in OpenAI format
    messages = []

    # Add system prompt if provided
    if req.system_prompt:
        messages.append({"role": "system", "content": req.system_prompt})

    # Add history
    for msg in req.history:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

    # Add current message
    messages.append({"role": "user", "content": req.message})

    return StreamingResponse(
        stream_hermes_response(messages, req.temperature, req.max_tokens),
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
