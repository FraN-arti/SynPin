"""OpenAI-compatible provider (OpenAI, LM Studio, any OpenAI-compatible API).

Supports native function calling via the `tools` parameter.
"""
import json
import httpx
from typing import AsyncIterator

from .base import BaseProvider, ChatMessage


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI-compatible APIs."""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _build_body(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int | None,
        stream: bool,
        tools: list[dict] | None = None,
    ) -> dict:
        """Build the request body for OpenAI-compatible API."""
        api_messages = []
        for m in messages:
            msg: dict = {"role": m.role, "content": m.content}

            # For tool results, add tool_call_id
            if m.role == "tool" and m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id

            # For assistant messages with tool_calls
            if m.role == "assistant" and m.tool_calls:
                msg["tool_calls"] = m.tool_calls
                # When tool_calls present, content can be null
                if not m.content:
                    msg["content"] = None

            api_messages.append(msg)

        body: dict = {
            "model": model,
            "messages": api_messages,
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        if stream:
            body["stream_options"] = {"include_usage": True}
        if tools:
            body["tools"] = tools

        return body

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = True,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body = self._build_body(messages, model, temperature, max_tokens, stream, tools)

        async with httpx.AsyncClient(timeout=300.0) as client:
            if not stream:
                # ── Non-streaming ──
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()

                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                finish_reason = choice.get("finish_reason", "")

                # Text content
                content = message.get("content") or ""
                if content:
                    yield content

                # Tool calls (native)
                tool_calls = message.get("tool_calls")
                if tool_calls and finish_reason == "tool_calls":
                    yield f"__TOOL_CALLS__:{json.dumps(tool_calls)}"

                # Usage
                usage = data.get("usage")
                if usage:
                    yield f"__USAGE__:{json.dumps(usage)}"
                return

            # ── Streaming: SSE ──
            # Accumulate tool call deltas
            accumulated_tool_calls: dict[int, dict] = {}  # index → {id, name, arguments}
            finish_reason = None

            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=body,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    # Process choices
                    for choice in chunk.get("choices", []):
                        delta = choice.get("delta", {})
                        fr = choice.get("finish_reason")

                        # Text content
                        content = delta.get("content")
                        if content:
                            yield content

                        # Tool call deltas
                        tool_call_deltas = delta.get("tool_calls")
                        if tool_call_deltas:
                            for tc_delta in tool_call_deltas:
                                idx = tc_delta.get("index", 0)
                                if idx not in accumulated_tool_calls:
                                    accumulated_tool_calls[idx] = {
                                        "id": tc_delta.get("id", ""),
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    }
                                tc = accumulated_tool_calls[idx]
                                fn = tc_delta.get("function", {})
                                if fn.get("name"):
                                    tc["function"]["name"] = fn["name"]
                                if fn.get("arguments"):
                                    tc["function"]["arguments"] += fn["arguments"]
                                if tc_delta.get("id"):
                                    tc["id"] = tc_delta["id"]

                        if fr:
                            finish_reason = fr

                    # Usage
                    if chunk.get("usage"):
                        yield f"__USAGE__:{json.dumps(chunk['usage'])}"

            # After stream ends: emit accumulated tool calls
            if finish_reason == "tool_calls" and accumulated_tool_calls:
                all_calls = [accumulated_tool_calls[i] for i in sorted(accumulated_tool_calls)]
                yield f"__TOOL_CALLS__:{json.dumps(all_calls)}"

    def supports_streaming(self) -> bool:
        return True
