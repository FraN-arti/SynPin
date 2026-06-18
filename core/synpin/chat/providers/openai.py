"""OpenAI-compatible provider (OpenAI, LM Studio, any OpenAI-compatible API).

Supports native function calling via the `tools` parameter.
"""
import json
import httpx
from typing import AsyncIterator

from .base import BaseProvider, ChatMessage


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI-compatible APIs."""

    # Override in subclasses for providers that don't support all OpenAI params
    supports_stream_options = True

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
            # Some providers reject null or empty content
            content = m.content or ""
            if not content and m.role == "assistant" and m.tool_calls:
                content = " "  # Space as minimal non-empty content for tool_call messages
            msg: dict = {"role": m.role, "content": content}

            # For tool results, add tool_call_id
            if m.role == "tool" and m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id

            # For assistant messages with tool_calls
            if m.role == "assistant" and m.tool_calls:
                msg["tool_calls"] = m.tool_calls

            api_messages.append(msg)

        body: dict = {
            "model": model,
            "messages": api_messages,
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        if stream and self.supports_stream_options:
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
                # ── Non-streaming with retry on transient errors ──
                data = None
                for attempt in range(3):
                    try:
                        resp = await client.post(
                            f"{self.base_url}/chat/completions",
                            headers=headers,
                            json=body,
                        )
                        if resp.status_code in (502, 503, 529) and attempt < 2:
                            import asyncio
                            await asyncio.sleep(1.0 * (attempt + 1))
                            continue
                        # 400 with tools → retry without tools (provider may not support function calling)
                        if resp.status_code == 400 and body.get("tools") and attempt == 0:
                            import logging
                            error_body = resp.text[:500]
                            logging.getLogger("synpin.chat").warning("[provider] 400 with tools, retrying without tools. model=%s, response=%s", model, error_body)
                            body.pop("tools", None)
                            # Clean up tool-related messages for the retry
                            clean_msgs = []
                            for msg in body.get("messages", []):
                                if msg.get("role") == "tool":
                                    continue  # Remove tool result messages
                                if msg.get("tool_calls"):
                                    msg = {k: v for k, v in msg.items() if k != "tool_calls"}
                                clean_msgs.append(msg)
                            body["messages"] = clean_msgs
                            continue
                        if resp.status_code == 400:
                            import logging
                            _log = logging.getLogger("synpin.chat")
                            _log.error("[provider] 400 Bad Request. model=%s", model)
                            # Dump the problematic message
                            try:
                                error_msg = resp.json()
                                err_text = error_msg.get("error", {}).get("message", "")
                                # Extract message index from "messages.N.content"
                                import re
                                idx_match = re.search(r'messages\.(\d+)\.content', err_text)
                                if idx_match:
                                    bad_idx = int(idx_match.group(1))
                                    if bad_idx < len(body.get("messages", [])):
                                        bad_msg = body["messages"][bad_idx]
                                        _log.error("[provider] BAD message[%d]: role=%s, content=%s, keys=%s",
                                                   bad_idx, bad_msg.get("role"), repr(bad_msg.get("content"))[:200],
                                                   list(bad_msg.keys()))
                            except Exception as e:
                                _log.error("[provider] Could not parse error: %s", e)
                            _log.error("[provider] 400 response: %s", resp.text[:1000])
                            # Also write to file for debugging
                            try:
                                import os
                                debug_path = os.path.join(os.environ.get("APPDATA", "."), "synpin", "debug_400.log")
                                os.makedirs(os.path.dirname(debug_path), exist_ok=True)
                                with open(debug_path, "a", encoding="utf-8") as f:
                                    f.write(f"\n{'='*60}\n")
                                    f.write(f"400 Bad Request at {__import__('datetime').datetime.now().isoformat()}\n")
                                    f.write(f"Model: {model}\n")
                                    # Try to extract bad message index
                                    try:
                                        err_data = resp.json()
                                        err_inner = json.loads(err_data.get("error", {}).get("message", "{}"))
                                        err_text = err_inner.get("error", {}).get("message", "")
                                        f.write(f"Error: {err_text}\n")
                                        import re
                                        idx_match = re.search(r'messages\.(\d+)\.content', err_text)
                                        if idx_match:
                                            bad_idx = int(idx_match.group(1))
                                            msgs = body.get("messages", [])
                                            if bad_idx < len(msgs):
                                                bad = msgs[bad_idx]
                                                f.write(f"BAD message[{bad_idx}]: role={bad.get('role')}, content={repr(bad.get('content'))[:300]}, keys={list(bad.keys())}\n")
                                    except Exception:
                                        f.write(f"Response: {resp.text[:2000]}\n")
                                    f.write(f"Total messages: {len(body.get('messages', []))}\n")
                            except Exception:
                                pass
                        resp.raise_for_status()
                        data = resp.json()
                        break
                    except (httpx.ConnectError, httpx.ReadTimeout) as e:
                        if attempt < 2:
                            import asyncio
                            await asyncio.sleep(1.0 * (attempt + 1))
                            continue
                        raise
                if data is None:
                    raise httpx.HTTPStatusError("All retry attempts failed", request=resp.request, response=resp)

                choice = data.get("choices", [{}])[0]
                message = choice.get("message", {})
                finish_reason = choice.get("finish_reason", "")

                # Text content
                content = message.get("content") or ""
                if content:
                    yield content

                # Tool calls (native) — emit if present, regardless of finish_reason
                # (Mistral may return "stop" instead of "tool_calls")
                tool_calls = message.get("tool_calls")
                if tool_calls:
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
                # 400 with tools → retry without tools
                if response.status_code == 400 and body.get("tools"):
                    body.pop("tools", None)
                    async with client.stream("POST", f"{self.base_url}/chat/completions", headers=headers, json=body) as resp2:
                        resp2.raise_for_status()
                        async for line in resp2.aiter_lines():
                            if not line.startswith("data: "): continue
                            data_str = line[6:]
                            if data_str == "[DONE]": break
                            try: chunk = json.loads(data_str)
                            except json.JSONDecodeError: continue
                            for choice in chunk.get("choices", []):
                                delta = choice.get("delta", {})
                                content = delta.get("content")
                                if content: yield content
                                fr = choice.get("finish_reason")
                                if fr: finish_reason = fr
                            if chunk.get("usage"): yield f"__USAGE__:{json.dumps(chunk['usage'])}"
                    return

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

            # After stream ends: emit accumulated tool calls if present
            # (Mistral may return "stop" instead of "tool_calls" in finish_reason)
            if accumulated_tool_calls:
                all_calls = [accumulated_tool_calls[i] for i in sorted(accumulated_tool_calls)]
                yield f"__TOOL_CALLS__:{json.dumps(all_calls)}"

    def supports_streaming(self) -> bool:
        return True
