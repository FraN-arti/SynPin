"""FastAPI router for chat with SSE streaming."""
import json
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .providers import ProviderRegistry
from .providers.base import ChatMessage

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Global registry — set during app startup
registry: ProviderRegistry | None = None


class ChatRequest(BaseModel):
    message: str
    model: str | None = None
    provider: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    history: list[dict[str, str]] = []  # [{role, content}, ...]


async def stream_response(
    provider_name: str,
    messages: list[ChatMessage],
    model: str,
    temperature: float,
    max_tokens: int | None,
):
    """SSE stream generator."""
    provider = registry.get(provider_name)
    if not provider:
        yield f"data: {json.dumps({'error': f'Provider not found: {provider_name}'})}\n\n"
        return

    usage = None
    try:
        async for chunk in provider.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        ):
            if chunk:  # text content
                # Check if this is a usage signal (prefixed with __USAGE__)
                if chunk.startswith("__USAGE__:"):
                    try:
                        usage = json.loads(chunk[10:])
                    except json.JSONDecodeError:
                        pass
                else:
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            else:  # end signal
                break
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    # Final done event with model and usage
    done_data = {"type": "done", "model": model}
    if usage:
        done_data["usage"] = usage
    yield f"data: {json.dumps(done_data)}\n\n"


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """Stream chat response via SSE."""
    if registry is None:
        raise HTTPException(500, "Chat provider not configured")

    # Build messages from history + current message
    messages = [ChatMessage(role=m["role"], content=m["content"]) for m in req.history]
    messages.append(ChatMessage(role="user", content=req.message))

    model = req.model or "default"
    provider_name = req.provider

    return StreamingResponse(
        stream_response(provider_name, messages, model, req.temperature, req.max_tokens),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/complete")
async def chat_complete(req: ChatRequest):
    """Non-streaming chat response (returns full text at once)."""
    if registry is None:
        raise HTTPException(500, "Chat provider not configured")

    messages = [ChatMessage(role=m["role"], content=m["content"]) for m in req.history]
    messages.append(ChatMessage(role="user", content=req.message))

    provider_name = req.provider
    provider = registry.get(provider_name)
    if not provider:
        raise HTTPException(400, f"Provider not found: {provider_name}")

    content = ""
    model = req.model or "default"

    async for chunk in provider.chat(
        messages=messages,
        model=model,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        stream=False,
    ):
        content += chunk

    return {"content": content, "model": model}


@router.get("/providers")
async def list_providers():
    """List available providers."""
    if registry is None:
        return {"providers": []}
    return {"providers": registry.list_names(), "default": registry._default}
