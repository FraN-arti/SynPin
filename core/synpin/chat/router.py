"""FastAPI router for chat with SSE streaming + native tool execution loop.

Uses OpenAI function calling API for tool execution (not prompt-based).
"""
import json
import asyncio
import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .providers import ProviderRegistry
from .providers.base import ChatMessage

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Global registry — set during app startup
registry: ProviderRegistry | None = None

# Max tool call iterations per message
MAX_TOOL_ITERATIONS = 5


class ChatRequest(BaseModel):
    message: str
    model: str | None = None
    provider: str | None = None
    agent_name: str | None = None  # Display name for UI (e.g. "Архитектор")
    system_prompt: str | None = None  # Merged system prompt with tone, style, traits
    temperature: float = 0.7
    max_tokens: int | None = None
    history: list[dict[str, str]] = []  # [{role, content}, ...]
    tools: list[str] = []  # Enabled tool names for this agent


# ─── Native function calling tool definitions ────────────────────────
# OpenAI function calling format — sent in the `tools` parameter

_NATIVE_TOOL_DEFS: dict[str, dict] = {
    "terminal": {
        "type": "function",
        "function": {
            "name": "terminal",
            "description": "Выполнение shell-команд (bash). Используй для запуска git, npm, python, ls, cat и любых других команд.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell-команда для выполнения",
                    },
                },
                "required": ["command"],
            },
        },
    },
    "file_read": {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "Чтение содержимого файла. Возвращает содержимое с номерами строк.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Путь к файлу (абсолютный или относительный)",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Номер строки начала (1-based, опционально)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Максимум строк для чтения (опционально)",
                    },
                },
                "required": ["path"],
            },
        },
    },
    "file_write": {
        "type": "function",
        "function": {
            "name": "file_write",
            "description": "Запись/перезапись содержимого файла. Создаёт файл или перезаписывает существующий.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Путь к файлу",
                    },
                    "content": {
                        "type": "string",
                        "description": "Содержимое файла для записи",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    "search_files": {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Поиск по содержимому или имени файла (grep/find).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Шаблон поиска (regex для content, glob для files)",
                    },
                    "path": {
                        "type": "string",
                        "description": "Директория для поиска (опционально, по умолчанию текущая)",
                    },
                    "target": {
                        "type": "string",
                        "enum": ["content", "files"],
                        "description": "'content' — поиск по содержимому, 'files' — поиск по именам файлов",
                    },
                    "file_glob": {
                        "type": "string",
                        "description": "Фильтр по расширению файлов (опционально, например '*.py')",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    "web_search": {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Поиск информации в интернете через DuckDuckGo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Максимальное количество результатов (по умолчанию 10)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    "code_exec": {
        "type": "function",
        "function": {
            "name": "code_exec",
            "description": "Выполнение Python-кода. Используй для вычислений, анализа данных, генерации контента.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python-код для выполнения",
                    },
                },
                "required": ["code"],
            },
        },
    },
}


def build_openai_tools(tool_names: list[str]) -> list[dict] | None:
    """Build OpenAI function calling tools list for enabled tools."""
    if not tool_names:
        return None

    tools = []
    for name in tool_names:
        tool_def = _NATIVE_TOOL_DEFS.get(name)
        if tool_def:
            tools.append(tool_def)

    return tools if tools else None


async def execute_tool(tool_name: str, params: dict) -> dict:
    """Execute a tool via the tool registry. Returns result dict."""
    try:
        from ..tools import get_tool_registry

        handlers = get_tool_registry()
        handler = handlers.get(tool_name)
        if not handler:
            return {"success": False, "output": "", "error": f"Tool '{tool_name}' not found in registry"}

        result = await handler(params)
        return result
    except Exception as e:
        return {"success": False, "output": "", "error": f"Tool execution error: {e}"}


# ─── SSE streaming ──────────────────────────────────────────────────


async def stream_response(
    provider_name: str,
    messages: list[ChatMessage],
    model: str,
    temperature: float,
    max_tokens: int | None,
    system_prompt: str | None = None,
    agent_name: str | None = None,
    tool_names: list[str] | None = None,
):
    """SSE stream generator with native tool execution loop.

    Flow:
    1. Build OpenAI-format tools from enabled tool names
    2. Call LLM (non-streaming) with tools parameter
    3. If model returns tool_calls → execute tools → loop
    4. Stream final LLM response as chunks
    5. Yield done with usage
    """
    provider = registry.get(provider_name)
    if not provider:
        yield f"data: {json.dumps({'type': 'error', 'message': f'Provider not found: {provider_name}'})}\n\n"
        return

    # Build initial message list
    chat_messages = list(messages)

    # Prepend system prompt if provided
    if system_prompt:
        chat_messages = [ChatMessage(role="system", content=system_prompt)] + chat_messages

    # Build native OpenAI tools
    tool_names = tool_names or []
    native_tools = build_openai_tools(tool_names)

    usage = None
    model_name = model
    tool_count = 0

    # ── Phase 1: Tool loop (native function calling) ──
    if native_tools:
        for iteration in range(MAX_TOOL_ITERATIONS):
            # Call LLM non-streaming with tools
            full_text = ""
            model_tool_calls = []

            try:
                async for chunk in provider.chat(
                    messages=chat_messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False,
                    tools=native_tools,
                ):
                    if chunk.startswith("__TOOL_CALLS__:"):
                        try:
                            model_tool_calls = json.loads(chunk[15:])
                        except json.JSONDecodeError:
                            pass
                    elif chunk.startswith("__USAGE__:"):
                        try:
                            usage = json.loads(chunk[10:])
                        except json.JSONDecodeError:
                            pass
                    elif chunk:
                        full_text += chunk
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                return

            # No tool calls → done with tool loop
            if not model_tool_calls:
                # Append the text response (if any) to conversation
                if full_text:
                    chat_messages.append(ChatMessage(role="assistant", content=full_text))
                break

            # Process tool calls
            # First, append the assistant message with tool_calls to conversation
            assistant_msg = ChatMessage(
                role="assistant",
                content=full_text or None,
                tool_calls=model_tool_calls,
            )
            chat_messages.append(assistant_msg)

            for tc in model_tool_calls:
                fn = tc.get("function", {})
                tc_id = tc.get("id", f"call_{tool_count}")
                t_name = fn.get("name", "")

                # Parse arguments
                try:
                    t_params = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    t_params = {}

                # Check if tool is enabled
                if t_name not in tool_names:
                    tool_result = {"success": False, "output": "", "error": f"Tool '{t_name}' not enabled"}
                else:
                    # yield tool_start
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': t_name, 'params': t_params, 'index': tool_count})}\n\n"

                    # Execute
                    tool_result = await execute_tool(t_name, t_params)

                    # yield tool_end
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool': t_name, 'result': tool_result.get('output', ''), 'success': tool_result.get('success', False), 'error': tool_result.get('error'), 'index': tool_count})}\n\n"

                # Build tool result message
                if tool_result.get("success"):
                    result_text = tool_result.get("output", "Выполнено.")
                else:
                    result_text = f"Ошибка: {tool_result.get('error', 'Неизвестная ошибка')}"

                chat_messages.append(ChatMessage(
                    role="tool",
                    content=result_text,
                    tool_call_id=tc_id,
                ))
                tool_count += 1

    # ── Phase 2: Stream final response ──
    # No tools in Phase 2 — tool loop already exhausted; stream text + usage only
    try:
        async for chunk in provider.chat(
            messages=chat_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            tools=None,
        ):
            if chunk.startswith("__USAGE__:"):
                try:
                    usage = json.loads(chunk[10:])
                except json.JSONDecodeError:
                    pass
            elif chunk.startswith("__TOOL_CALLS__:"):
                # Shouldn't happen in Phase 2 (no tools), but ignore gracefully
                pass
            elif chunk:
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
            # Note: don't break on empty/unknown signals — keep reading for __USAGE__
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        return

    # Done event
    done_data = {"type": "done", "model": model_name}
    if agent_name:
        done_data["agent_name"] = agent_name
    if usage:
        done_data["usage"] = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
    yield f"data: {json.dumps(done_data)}\n\n"


# ─── REST endpoints ─────────────────────────────────────────────────


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """Stream chat response via SSE with native tool execution."""
    if registry is None:
        raise HTTPException(500, "Chat provider not configured")

    # Build messages from history + current message
    messages = [ChatMessage(role=m["role"], content=m["content"]) for m in req.history]
    messages.append(ChatMessage(role="user", content=req.message))

    model = req.model or "default"
    provider_name = req.provider

    return StreamingResponse(
        stream_response(
            provider_name=provider_name,
            messages=messages,
            model=model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            system_prompt=req.system_prompt,
            agent_name=req.agent_name,
            tool_names=req.tools or [],
        ),
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

    # Build system prompt
    sys_prompt_parts = []
    if req.system_prompt:
        sys_prompt_parts.append(req.system_prompt)

    if sys_prompt_parts:
        combined_prompt = "\n\n".join(sys_prompt_parts)
        messages = [ChatMessage(role="system", content=combined_prompt)] + messages

    # Build native tools
    native_tools = build_openai_tools(req.tools or [])

    content = ""
    model = req.model or "default"

    async for chunk in provider.chat(
        messages=messages,
        model=model,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        stream=False,
        tools=native_tools,
    ):
        if chunk.startswith("__TOOL_CALLS__:") or chunk.startswith("__USAGE__:"):
            continue
        content += chunk

    return {"content": content, "model": model}


@router.get("/providers")
async def list_providers():
    """List available providers."""
    if registry is None:
        return {"providers": []}
    return {"providers": registry.list_names(), "default": registry._default}
