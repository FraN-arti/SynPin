"""Base provider interface for LLM chat."""
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator
from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    role: str  # "user", "assistant", "system", "tool"
    content: str
    tool_call_id: str | None = None  # For role="tool" messages
    tool_calls: list[dict] | None = None  # For assistant messages with tool calls
    images: list[str] | None = None  # Base64 data URLs for multimodal content


@dataclass
class ChatResponse:
    content: str
    model: str
    finish_reason: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tool_calls: list[dict] = field(default_factory=list)


class BaseProvider(ABC):
    """Abstract LLM provider with streaming support."""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = True,
        tools: list[dict] | None = None,
    ) -> AsyncIterator[str]:
        """Yield text chunks as they arrive. Last chunk is empty to signal end.

        Special signals:
          __TOOL_CALLS__:<json>  — structured tool calls from the model
          __USAGE__:<json>       — token usage data
        """
        ...

    @abstractmethod
    def supports_streaming(self) -> bool:
        """Whether this provider/model combination supports streaming."""
        return True
