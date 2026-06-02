"""Base provider interface for LLM chat."""
from abc import ABC, abstractmethod
from typing import AsyncIterator
from dataclasses import dataclass


@dataclass
class ChatMessage:
    role: str  # "user", "assistant", "system"
    content: str


@dataclass
class ChatResponse:
    content: str
    model: str
    finish_reason: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0


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
    ) -> AsyncIterator[str]:
        """Yield text chunks as they arrive. Last chunk is empty to signal end."""
        ...

    @abstractmethod
    def supports_streaming(self) -> bool:
        """Whether this provider/model combination supports streaming."""
        return True
