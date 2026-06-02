"""OpenAI-compatible provider (OpenAI, LM Studio, any OpenAI-compatible API)."""
import httpx
from typing import AsyncIterator

from .base import BaseProvider, ChatMessage


class OpenAIProvider(BaseProvider):
    """Provider for OpenAI-compatible APIs."""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = True,
    ) -> AsyncIterator[str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:  # only send auth header if key is present
            headers["Authorization"] = f"Bearer {self.api_key}"

        body: dict = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "stream": stream,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        if stream:
            body["stream_options"] = {"include_usage": True}

        async with httpx.AsyncClient(timeout=300.0) as client:
            if not stream:
                # Non-streaming: single JSON response
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=body,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                yield content
                return

            # Streaming: SSE
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

                    data = line[6:]  # strip "data: "
                    if data == "[DONE]":
                        break

                    import json
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    # Extract text from chunk
                    choices = chunk.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content")
                        if content:
                            yield content

                    # Check for usage in any chunk (often appears in the last chunk with content)
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                        yield f"__USAGE__:{json.dumps(usage)}"

    def supports_streaming(self) -> bool:
        return True
