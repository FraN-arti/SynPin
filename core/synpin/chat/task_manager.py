"""Background task manager for SynPin chat.

Decouples LLM execution from HTTP response lifecycle:
- User message saved immediately to disk
- LLM execution runs in asyncio.Task (survives client disconnect)
- SSE streaming reads from asyncio.Queue (real-time)
- History saved by background task (independent of client)

This ensures agents continue working even when the user closes the browser.
"""
import asyncio
import logging
import json
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class ChatTask:
    """A single chat execution task.
    
    Wraps an async generator that produces SSE chunks.
    Runs independently of the HTTP response.
    """
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.queue: asyncio.Queue[str | None] = asyncio.Queue()
        self.task: asyncio.Task | None = None
        self.done = False
        self.error: str | None = None
    
    async def run(self, generator: AsyncGenerator[str, None]):
        """Run the generator and push chunks to queue."""
        try:
            async for chunk in generator:
                await self.queue.put(chunk)
        except Exception as e:
            logger.error("Chat task %s failed: %s", self.task_id, e)
            self.error = str(e)
            # Push error chunk
            error_data = json.dumps({"type": "error", "message": str(e)})
            await self.queue.put(f"data: {error_data}\n\n")
        finally:
            self.done = True
            await self.queue.put(None)  # Signal completion
    
    async def stream(self) -> AsyncGenerator[str, None]:
        """Read chunks from queue (for SSE response)."""
        while True:
            chunk = await self.queue.get()
            if chunk is None:
                break
            yield chunk


class TaskManager:
    """Manages background chat tasks.
    
    Usage:
        manager = TaskManager()
        
        # Create task and start execution
        task = manager.create("task_123")
        task.task = asyncio.create_task(task.run(my_generator()))
        
        # Stream to client
        async for chunk in task.stream():
            yield chunk
    """
    
    def __init__(self):
        self._tasks: dict[str, ChatTask] = {}
    
    def create(self, task_id: str) -> ChatTask:
        """Create a new chat task."""
        task = ChatTask(task_id)
        self._tasks[task_id] = task
        return task
    
    def get(self, task_id: str) -> ChatTask | None:
        """Get an existing task."""
        return self._tasks.get(task_id)
    
    def cleanup(self, task_id: str):
        """Remove a completed task."""
        self._tasks.pop(task_id, None)
    
    def active_count(self) -> int:
        """Number of active (not completed) tasks."""
        return sum(1 for t in self._tasks.values() if not t.done)


# Global singleton
task_manager = TaskManager()
