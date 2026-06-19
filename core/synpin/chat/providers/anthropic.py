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
        tools: list[dict] | None = None,
    ) -> AsyncIterator[str]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        # Extract system message and filter tool messages
        system = None
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system = m.content
            elif m.role == "tool":
                # Anthropic API doesn't support tool role messages; skip them
                continue
            elif m.images and m.role == "user":
                # Multimodal content for Anthropic
                content_parts = []
                if m.content:
                    content_parts.append({"type": "text", "text": m.content})
                for img_data in m.images:
                    # Parse data URL: "data:image/png;base64,..."
                    media_type = "image/jpeg"
                    raw_data = img_data
                    if img_data.startswith("data:"):
                        # "data:image/png;base64,iVBOR..."
                        parts = img_data.split(",", 1)
                        if len(parts) == 2:
                            header = parts[0]  # "data:image/png;base64"
                            raw_data = parts[1]
                            if ";base64" in header:
                                media_type = header.split(":")[1].split(";")[0]
                    content_parts.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": raw_data},
                    })
                chat_messages.append({"role": m.role, "content": content_parts})
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

        # Send tools if provided
        if tools:
            body["tools"] = tools

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
