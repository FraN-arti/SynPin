"""Anthropic Claude provider."""
import httpx
from typing import AsyncIterator

from .base import BaseProvider, ChatMessage


class AnthropicProvider(BaseProvider):
    """Provider for Anthropic Claude API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com"

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = True,
    ) -> AsyncIterator[str]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        # Extract system message if present
        system = None
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system = m.content
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        body: dict = {
            "model": model,
            "messages": chat_messages,
            "temperature": temperature,
            "stream": stream,
        }
        if system:
            body["system"] = system
        if max_tokens:
            body["max_tokens"] = max_tokens
        else:
            body["max_tokens"] = 4096

        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/messages",
                headers=headers,
                json=body,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue

                    data = line[6:]
                    import json
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type", "")

                    # Text content delta
                    if event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield delta.get("text", "")

                    # End of stream
                    elif event_type == "message_stop":
                        yield ""  # signal end

    def supports_streaming(self) -> bool:
        return True
