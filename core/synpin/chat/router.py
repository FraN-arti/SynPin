"""FastAPI router for chat with SSE streaming + native tool execution loop.

Uses OpenAI function calling API for tool execution (not prompt-based).
"""
import json
import asyncio
import re
import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .providers import ProviderRegistry
from .providers.base import ChatMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Global registry — set during app startup
registry: ProviderRegistry | None = None

# Max tool call iterations per message
MAX_TOOL_ITERATIONS = 5

# Shared data dir for memory (resolved once)
_DATA_DIR: Path | None = None

# Max messages to keep in history per channel
MAX_HISTORY_MESSAGES = 100


def _get_data_dir() -> Path | None:
    """Resolve data directory (same logic as memory_router)."""
    global _DATA_DIR
    if _DATA_DIR is not None:
        return _DATA_DIR
    candidates = [
        Path.home() / ".synpin" / "data",
        Path(__file__).resolve().parent.parent.parent / "data",
    ]
    for candidate in candidates:
        if candidate.exists():
            _DATA_DIR = candidate
            return _DATA_DIR
    # Create first candidate
    _DATA_DIR = candidates[0]
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _DATA_DIR


def _get_history_path(agent_slug: str, channel_id: str) -> Path | None:
    """Get file path for chat history of agent+channel."""
    data_dir = _get_data_dir()
    if not data_dir:
        return None
    return data_dir / "agents" / agent_slug / "sessions" / f"{channel_id}.json"


def _save_chat_history(
    agent_slug: str,
    channel_id: str,
    messages: list[dict],
):
    """Save chat history to disk. Keeps last MAX_HISTORY_MESSAGES."""
    path = _get_history_path(agent_slug, channel_id)
    if not path:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Trim to max size
        trimmed = messages[-MAX_HISTORY_MESSAGES:]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(trimmed, f, ensure_ascii=False, indent=1)
    except Exception as e:
        logger.warning("Failed to save chat history for %s/%s: %s", agent_slug, channel_id, e)


def _load_chat_history(agent_slug: str, channel_id: str) -> list[dict]:
    """Load chat history from disk."""
    path = _get_history_path(agent_slug, channel_id)
    if not path or not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load chat history for %s/%s: %s", agent_slug, channel_id, e)
        return []


def _clear_chat_history(agent_slug: str, channel_id: str):
    """Delete chat history file."""
    path = _get_history_path(agent_slug, channel_id)
    if path and path.exists():
        try:
            path.unlink()
        except Exception as e:
            logger.warning("Failed to clear chat history for %s/%s: %s", agent_slug, channel_id, e)


# ── Compaction ────────────────────────────────────────────────────────────

def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for Latin, ~1.5 for CJK."""
    if not text:
        return 0
    # Simple heuristic: 1 token ≈ 4 bytes (works for mixed content)
    return len(text) // 4


def _get_agent_compaction_config(agent_slug: str) -> dict:
    """Load compaction + context_window settings for an agent.
    
    Priority: global memory.yaml → per-agent config → hardcoded defaults.
    """
    # 1. Load global config from memory.yaml
    global_cfg = {}
    try:
        from ..config.manager import load_yaml
        full = load_yaml("memory.yaml")
        global_cfg = {
            "context_window": full.get("context_window", {}).get("default", 128000),
            "compaction_enabled": full.get("compaction", {}).get("enabled", True),
            "trigger_percent": full.get("compaction", {}).get("trigger_percent", 80),
            "keep_recent": full.get("compaction", {}).get("keep_recent", 10),
            "strategy": full.get("compaction", {}).get("strategy", "truncate"),
        }
    except Exception:
        global_cfg = {
            "context_window": 128000,
            "compaction_enabled": True,
            "trigger_percent": 80,
            "keep_recent": 10,
            "strategy": "truncate",
        }

    # 2. Override with per-agent settings if present
    try:
        from ..agents.manager import get_agent
        agent = get_agent(agent_slug)
        if agent:
            memory = agent.get("memory", {})
            if "compaction_enabled" in memory:
                global_cfg["compaction_enabled"] = memory["compaction_enabled"]
            if "compaction_trigger_percent" in memory:
                global_cfg["trigger_percent"] = memory["compaction_trigger_percent"]
            if "compaction_keep_recent" in memory:
                global_cfg["keep_recent"] = memory["compaction_keep_recent"]
            if "compaction_strategy" in memory:
                global_cfg["strategy"] = memory["compaction_strategy"]
            if agent.get("context_window"):
                global_cfg["context_window"] = agent["context_window"]
    except Exception:
        pass

    return global_cfg


def compact_messages(
    messages: list,
    system_prompt: str = "",
    agent_slug: str = "",
) -> tuple[list, str]:
    """Compact messages if they exceed context window.

    Returns (compacted_messages, compaction_notice).
    If no compaction needed, returns original messages and empty notice.
    """
    if not agent_slug:
        return messages, ""

    cfg = _get_agent_compaction_config(agent_slug)
    if not cfg.get("compaction_enabled", True):
        return messages, ""

    ctx_limit = cfg.get("context_window", 128000)
    trigger_pct = cfg.get("trigger_percent", 80)
    keep_recent = cfg.get("keep_recent", 10)

    # Estimate total tokens
    sys_tokens = _estimate_tokens(system_prompt)
    msg_tokens = sum(_estimate_tokens(m.get("content", "") or "") for m in messages)
    total = sys_tokens + msg_tokens

    # Calculate threshold
    threshold = int(ctx_limit * trigger_pct / 100)

    if total <= threshold:
        return messages, ""

    # Need compaction — trim old messages, keep last N
    if len(messages) <= keep_recent:
        return messages, ""

    # Split: keep system + first message (context) + last N messages
    trimmed = messages[:1] + messages[-keep_recent:]
    new_total = sys_tokens + sum(_estimate_tokens(m.get("content", "") or "") for m in trimmed)
    removed = len(messages) - len(trimmed)

    notice = (
        f"[Компакция: удалено {removed} старых сообщений "
        f"(~{total:,} → ~{new_total:,} токенов, лимит {ctx_limit:,})]"
    )

    logger.info(
        "Compacted %s: %d → %d messages (~%d → ~%d tokens)",
        agent_slug, len(messages), len(trimmed), total, new_total,
    )

    return trimmed, notice


# ── Session Auto-Reset ────────────────────────────────────────────────────

def _check_session_auto_reset(agent_slug: str, channel_id: str) -> bool:
    """Check if session needs auto-reset. Returns True if reset was performed."""
    if not agent_slug or not channel_id:
        return False

    try:
        from ..agents.manager import get_agent
        from ..memory.state import AgentState
        from datetime import datetime, timedelta

        agent = get_agent(agent_slug)
        if not agent:
            return False

        memory = agent.get("memory", {})
        if not memory.get("session_auto_reset_enabled", False):
            return False

        data_dir = _get_data_dir()
        if not data_dir:
            return False

        state = AgentState(agent_slug, data_dir)
        state.load()
        session = state.get_active_session(channel_id)
        if not session:
            return False  # No session to reset

        updated_at = session.get("updated_at", "")
        if not updated_at:
            return False

        try:
            last_update = datetime.fromisoformat(updated_at)
        except ValueError:
            return False

        now = datetime.now()
        mode = memory.get("session_auto_reset_mode", "daily")
        needs_reset = False

        if mode == "daily":
            reset_time_str = memory.get("session_auto_reset_time", "00:00")
            try:
                h, m = map(int, reset_time_str.split(":"))
                today_reset = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if now >= today_reset and last_update < today_reset:
                    needs_reset = True
            except (ValueError, AttributeError):
                pass

        elif mode == "timer":
            interval_hours = memory.get("session_auto_reset_interval", 24)
            if (now - last_update) > timedelta(hours=interval_hours):
                needs_reset = True

        elif mode == "time":
            reset_time_str = memory.get("session_auto_reset_time", "00:00")
            try:
                h, m = map(int, reset_time_str.split(":"))
                today_reset = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if now >= today_reset and last_update < today_reset:
                    needs_reset = True
            except (ValueError, AttributeError):
                pass

        if not needs_reset:
            return False

        # Archive old session
        if memory.get("session_archive_on_reset", True):
            _archive_session(agent_slug, channel_id, session)

        # Clear session
        state.clear_channel(channel_id)
        _clear_chat_history(agent_slug, channel_id)

        logger.info("Auto-reset session for %s/%s (mode=%s)", agent_slug, channel_id, mode)
        return True

    except Exception as e:
        logger.warning("Session auto-reset check failed for %s/%s: %s", agent_slug, channel_id, e)
        return False


def _archive_session(agent_slug: str, channel_id: str, session: dict):
    """Archive a session before clearing it."""
    try:
        data_dir = _get_data_dir()
        if not data_dir:
            return
        archive_dir = data_dir / "agents" / agent_slug / "sessions" / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        # Load history to archive
        history = _load_chat_history(agent_slug, channel_id)
        if not history and not session:
            return

        # Create archive entry
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_file = archive_dir / f"{channel_id}_{timestamp}.json"
        archive_data = {
            "channel_id": channel_id,
            "session": session,
            "messages": history,
            "archived_at": datetime.now().isoformat(),
        }
        with open(archive_file, "w", encoding="utf-8") as f:
            json.dump(archive_data, f, ensure_ascii=False, indent=1)

        logger.info("Archived session: %s", archive_file.name)
    except Exception as e:
        logger.warning("Failed to archive session: %s", e)


def _load_memory_block(agent_slug: str) -> str:
    """Load agent memory and return block for system prompt injection."""
    if not agent_slug:
        return ""
    try:
        from ..memory import MemoryManager
        data_dir = _get_data_dir()
        if not data_dir:
            return ""
        manager = MemoryManager(agent_slug, data_dir)
        manager.initialize()
        block = manager.get_system_prompt_block()
        manager.close()

        # Add memory instructions if block exists
        if block:
            instructions = (
                "\n\n══════════════════════════════════════════════\n"
                "MEMORY INSTRUCTIONS\n"
                "══════════════════════════════════════════════\n"
                "You have persistent memory tools:\n"
                "- memory_write(action='add', target='memory', content='...') — save important facts, decisions, patterns\n"
                "- memory_write(action='add', target='user', content='...') — save info about the user\n"
                "- memory_read(target='memory'/'user'/'facts') — recall saved information\n\n"
                "PROACTIVELY save:\n"
                "- User preferences, habits, communication style\n"
                "- Important decisions and their reasoning\n"
                "- Errors encountered and lessons learned\n"
                "- Project context and current tasks\n"
                "- Any information the user explicitly asks to remember\n\n"
                "Do NOT save: trivial conversation content, temporary debugging, repeated information."
            )
            block += instructions

        return block or ""
    except Exception as e:
        logger.warning("Failed to load memory for %s: %s", agent_slug, e)
        return ""


def _load_session_context(agent_slug: str, channel_id: str) -> str:
    """Load session context for the given agent+channel and return block for system prompt."""
    if not agent_slug or not channel_id:
        return ""
    try:
        from ..memory.state import AgentState
        data_dir = _get_data_dir()
        if not data_dir:
            return ""
        state = AgentState(agent_slug, data_dir)
        state.load()
        session = state.get_active_session(channel_id)

        if session:
            last_action = session.get("last_action", "")
            waiting_for = session.get("waiting_for", "")
            updated_at = session.get("updated_at", "")
            pos = session.get("last_position", 0)

            lines = [f"Previous session in channel '{channel_id}':"]
            if last_action:
                lines.append(f"- Last discussed: {last_action}")
            if waiting_for:
                lines.append(f"- Waiting for: {waiting_for}")
            if updated_at:
                lines.append(f"- Updated: {updated_at}")
            lines.append(f"- Messages in session: {pos}")

            separator = "═" * 46
            return f"{separator}\nSESSION CONTEXT\n{separator}\n" + "\n".join(lines)
        else:
            separator = "═" * 46
            return (
                f"{separator}\nSESSION CONTEXT\n{separator}\n"
                f"New session — no previous conversation found for channel '{channel_id}'."
            )
    except Exception as e:
        logger.warning("Failed to load session context for %s/%s: %s", agent_slug, channel_id, e)
        return ""


def _update_session_state(
    agent_slug: str,
    channel_id: str,
    user_message: str,
    message_count: int,
):
    """Update state.json after a chat turn."""
    if not agent_slug or not channel_id:
        return
    try:
        from ..memory.state import AgentState
        data_dir = _get_data_dir()
        if not data_dir:
            return
        state = AgentState(agent_slug, data_dir)
        state.load()
        # Use first 100 chars of user message as last_action
        last_action = user_message[:100] + ("..." if len(user_message) > 100 else "")
        state.set_active_session(
            channel=channel_id,
            session_id=f"session_{channel_id}",
            last_position=message_count,
            last_action=last_action,
        )
    except Exception as e:
        logger.warning("Failed to update session state for %s/%s: %s", agent_slug, channel_id, e)


class ChatRequest(BaseModel):
    message: str
    model: str | None = None
    provider: str | None = None
    agent_name: str | None = None  # Display name for UI (e.g. "Архитектор")
    agent_slug: str | None = None  # Agent ID for memory context loading
    channel_id: str | None = None  # Channel identifier for session tracking (e.g. "web", "feishu:<chat_id>")
    new_session: bool = False  # If true, clear active session for this channel (fresh start)
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
    "memory_read": {
        "type": "function",
        "function": {
            "name": "memory_read",
            "description": "Чтение памяти агента. Используй чтобы вспомнить предыдущие разговоры, факты, информацию о пользователе.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "enum": ["memory", "user", "facts"],
                        "description": "'memory' — память агента (MEMORY.md), 'user' — данные о пользователе (USER.md), 'facts' — список датированных фактов",
                    },
                    "filename": {
                        "type": "string",
                        "description": "Для facts: имя файла для чтения (опционально)",
                    },
                },
                "required": ["target"],
            },
        },
    },
    "memory_write": {
        "type": "function",
        "function": {
            "name": "memory_write",
            "description": "Запись в память агента. Используй чтобы запомнить важную информацию, факты, решения, данные о пользователе.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["add", "remove", "replace"],
                        "description": "'add' — добавить запись, 'remove' — удалить запись, 'replace' — заменить запись",
                    },
                    "target": {
                        "type": "string",
                        "enum": ["memory", "user"],
                        "description": "'memory' — память агента (MEMORY.md), 'user' — данные о пользователе (USER.md)",
                    },
                    "content": {
                        "type": "string",
                        "description": "Текст записи (для add/replace)",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "Текст для поиска (для remove/replace)",
                    },
                },
                "required": ["action", "target"],
            },
        },
    },
}


BUILTINS = {"memory_read", "memory_write"}


def build_openai_tools(tool_names: list[str]) -> list[dict] | None:
    """Build OpenAI function calling tools list for enabled tools."""
    tools = []

    # Always include built-in tools
    for name in BUILTINS:
        tool_def = _NATIVE_TOOL_DEFS.get(name)
        if tool_def:
            tools.append(tool_def)

    # Add agent-specific tools
    for name in tool_names:
        if name not in BUILTINS:
            tool_def = _NATIVE_TOOL_DEFS.get(name)
            if tool_def:
                tools.append(tool_def)

    return tools if tools else None


async def execute_tool(tool_name: str, params: dict, agent_slug: str | None = None) -> dict:
    """Execute a tool via the tool registry. Returns result dict."""
    try:
        from ..tools import get_tool_registry

        handlers = get_tool_registry()
        handler = handlers.get(tool_name)
        if not handler:
            return {"success": False, "output": "", "error": f"Tool '{tool_name}' not found in registry"}

        # Inject agent_id for memory tools
        if agent_slug and tool_name in ("memory_read", "memory_write"):
            params = {**params, "agent_id": agent_slug}

        result = await handler(params)
        return result
    except Exception as e:
        return {"success": False, "output": "", "error": f"Tool execution error: {e}"}


def _parse_text_tool_calls(text: str) -> list[dict]:
    """Parse tool calls from plain text output (fallback for models without native function calling).
    
    Looks for JSON patterns like:
    - {"name": "terminal", "params": {"command": "ls"}}
    - {"tool": "file_read", "params": {"path": "..."}}
    - ```tool_call\n{"name": "...", "params": {...}}\n```
    
    Returns list of OpenAI-format tool_call dicts.
    """
    if not text:
        return []
    
    calls = []
    
    # Pattern 1: ```tool_call blocks (old format)
    block_pattern = re.compile(r'```tool_call\s*\n?(.*?)\n?\s*```', re.DOTALL)
    for match in block_pattern.finditer(text):
        try:
            obj = json.loads(match.group(1).strip())
            name = obj.get("name") or obj.get("tool", "")
            params = obj.get("params") or obj.get("parameters") or {}
            if name:
                calls.append({
                    "id": f"call_text_{len(calls)}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(params)}
                })
        except json.JSONDecodeError:
            continue
    
    if calls:
        return calls
    
    # Pattern 2: Raw JSON in text (nemotron-style output)
    # Match standalone JSON objects that look like tool calls
    json_pattern = re.compile(r'\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"params"\s*:\s*\{[^{}]*\}[^{}]*\}')
    for match in json_pattern.finditer(text):
        try:
            obj = json.loads(match.group(0))
            name = obj.get("name", "")
            params = obj.get("params") or {}
            if name:
                calls.append({
                    "id": f"call_text_{len(calls)}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(params)}
                })
        except json.JSONDecodeError:
            continue
    
    # Pattern 3: Handle nested JSON params (more flexible)
    if not calls:
        # Try to find any JSON object with "name" and "params" keys
        depth_pattern = re.compile(r'\{(?:[^{}]|\{[^{}]*\})*\}', re.DOTALL)
        for match in depth_pattern.finditer(text):
            try:
                obj = json.loads(match.group(0))
                if isinstance(obj, dict):
                    name = obj.get("name", "")
                    params = obj.get("params") or obj.get("parameters") or {}
                    if name and isinstance(params, dict):
                        calls.append({
                            "id": f"call_text_{len(calls)}",
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(params)}
                        })
            except json.JSONDecodeError:
                continue
    
    return calls


# ─── SSE streaming ──────────────────────────────────────────────────

async def stream_response(
    provider_name: str,
    messages: list[ChatMessage],
    model: str,
    temperature: float,
    max_tokens: int | None,
    system_prompt: str | None = None,
    agent_name: str | None = None,
    agent_slug: str | None = None,
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

            # Determine if tool calls came from native API or text fallback
            is_text_fallback = False
            if not model_tool_calls:
                text_tool_calls = _parse_text_tool_calls(full_text)
                if text_tool_calls:
                    model_tool_calls = text_tool_calls
                    is_text_fallback = True
                else:
                    # No tool calls at all → yield Phase 1 result directly, skip Phase 2
                    # (Mistral requires last message to be user/tool, not assistant)
                    if full_text:
                        yield f"data: {json.dumps({'type': 'chunk', 'content': full_text})}\n\n"
                    if usage:
                        yield f"__USAGE__:{json.dumps(usage)}"
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
                    return

            # Execute all tool calls and collect results
            tool_results_for_msg = []  # For text fallback: [(name, result_text)]

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
                    tool_result = await execute_tool(t_name, t_params, agent_slug)

                    # yield tool_end
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool': t_name, 'result': tool_result.get('output', ''), 'success': tool_result.get('success', False), 'error': tool_result.get('error'), 'index': tool_count})}\n\n"

                # Build tool result text
                if tool_result.get("success"):
                    result_text = tool_result.get("output", "Выполнено.")
                else:
                    result_text = f"Ошибка: {tool_result.get('error', 'Неизвестная ошибка')}"

                if is_text_fallback:
                    # Text fallback: collect results for user message
                    tool_results_for_msg.append((t_name, result_text))
                else:
                    # Native function calling: use proper tool messages
                    chat_messages.append(ChatMessage(
                        role="tool",
                        content=result_text,
                        tool_call_id=tc_id,
                    ))
                tool_count += 1

            if is_text_fallback:
                # Text fallback: models like nemotron don't understand role="tool" format.
                # Send assistant text + tool results as user messages so the model
                # can see its own output and the results, then continue chaining.
                chat_messages.append(ChatMessage(role="assistant", content=full_text))
                for t_name, result_text in tool_results_for_msg:
                    chat_messages.append(ChatMessage(
                        role="user",
                        content=f"[Результат инструмента {t_name}]\n{result_text}\n\nПродолжай работать. Если задача выполнена — подведи итог.",
                    ))
            else:
                # Native: append assistant msg with tool_calls FIRST, then tool results
                # (Mistral requires assistant before tool, not after)
                assistant_msg = ChatMessage(
                    role="assistant",
                    content=full_text or None,
                    tool_calls=model_tool_calls,
                )
                chat_messages.append(assistant_msg)
                # Tool results were already appended in the loop above — need to reorder
                # Move tool messages after assistant by rebuilding the list
                # Find and reposition tool messages
                tool_msgs = [m for m in chat_messages if m.role == "tool"]
                non_tool_msgs = [m for m in chat_messages if m.role != "tool"]
                chat_messages = non_tool_msgs + tool_msgs

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


def _build_system_prompt_with_memory(req: ChatRequest) -> str:
    """Build system prompt with agent memory + session context injected."""
    system_prompt = req.system_prompt or ""
    if req.agent_slug:
        memory_block = _load_memory_block(req.agent_slug)
        if memory_block:
            system_prompt = f"{system_prompt}\n\n{memory_block}" if system_prompt else memory_block

        # Session context
        channel = req.channel_id or "web"
        session_block = _load_session_context(req.agent_slug, channel)
        if session_block:
            system_prompt = f"{system_prompt}\n\n{session_block}" if system_prompt else session_block
    return system_prompt


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

    # Strip provider prefix from model name (e.g. "mistral/codestral-latest" → "codestral-latest")
    # Agents store models as "provider/model" for SynPin routing, but APIs expect bare model names
    if provider_name and model.startswith(f"{provider_name}/"):
        model = model[len(provider_name) + 1:]

    # If new_session requested, clear the active session for this channel FIRST
    if req.new_session and req.agent_slug and req.channel_id:
        try:
            from ..memory.state import AgentState
            data_dir = _get_data_dir()
            if data_dir:
                state = AgentState(req.agent_slug, data_dir)
                state.load()
                state.clear_channel(req.channel_id)
            # Also clear persisted history
            _clear_chat_history(req.agent_slug, req.channel_id)
        except Exception as e:
            logger.warning("Failed to clear session for new_session: %s", e)

    # Check session auto-reset (daily/timer/time)
    if req.agent_slug and req.channel_id:
        _check_session_auto_reset(req.agent_slug, req.channel_id)

    # Build system prompt with memory + session context
    system_prompt = _build_system_prompt_with_memory(req)

    # Compaction: trim old messages if context exceeds limit
    if req.agent_slug:
        msg_dicts = [{"role": m.role, "content": m.content or ""} for m in messages]
        compacted, notice = compact_messages(msg_dicts, system_prompt, req.agent_slug)
        if notice:
            messages = [ChatMessage(role=m["role"], content=m["content"]) for m in compacted]
            system_prompt = f"{system_prompt}\n\n{notice}" if system_prompt else notice

    # Update session state after this request
    message_count = len(req.history) + 1  # history + current message
    if req.agent_slug and req.channel_id:
        _update_session_state(req.agent_slug, req.channel_id, req.message, message_count)

    # Wrap generator to capture response text and save history
    agent_slug = req.agent_slug
    channel_id = req.channel_id
    history_before = list(req.history)
    user_message = req.message

    async def _stream_with_save():
        full_response = ""
        async for chunk in stream_response(
            provider_name=provider_name,
            messages=messages,
            model=model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            system_prompt=system_prompt,
            agent_name=req.agent_name,
            agent_slug=req.agent_slug,
            tool_names=req.tools or [],
        ):
            # Capture chunk content for history
            if '"type": "chunk"' in chunk:
                try:
                    payload = json.loads(chunk.split("data: ", 1)[1].split("\n")[0])
                    if payload.get("type") == "chunk":
                        full_response += payload.get("content", "")
                except Exception:
                    pass
            yield chunk

        # Save full history after streaming completes
        if agent_slug and channel_id and full_response:
            new_messages = history_before + [
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": full_response},
            ]
            _save_chat_history(agent_slug, channel_id, new_messages)

    return StreamingResponse(
        _stream_with_save(),
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

    # If new_session requested, clear the active session for this channel FIRST
    if req.new_session and req.agent_slug and req.channel_id:
        try:
            from ..memory.state import AgentState
            data_dir = _get_data_dir()
            if data_dir:
                state = AgentState(req.agent_slug, data_dir)
                state.load()
                state.clear_channel(req.channel_id)
        except Exception as e:
            logger.warning("Failed to clear session for new_session: %s", e)

    # Check session auto-reset (daily/timer/time)
    if req.agent_slug and req.channel_id:
        _check_session_auto_reset(req.agent_slug, req.channel_id)

    # Build system prompt with memory + session context
    system_prompt = _build_system_prompt_with_memory(req)

    # Compaction: trim old messages if context exceeds limit
    if req.agent_slug:
        msg_dicts = [{"role": m.role, "content": m.content or ""} for m in messages]
        compacted, notice = compact_messages(msg_dicts, system_prompt, req.agent_slug)
        if notice:
            messages = [ChatMessage(role=m["role"], content=m["content"]) for m in compacted]
            system_prompt = f"{system_prompt}\n\n{notice}" if system_prompt else notice

    if system_prompt:
        messages = [ChatMessage(role="system", content=system_prompt)] + messages

    content = ""
    model = req.model or "default"
    usage = None

    try:
        async for chunk in provider.chat(
            messages=messages,
            model=model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            stream=False,
            tools=None,
        ):
            if chunk.startswith("__USAGE__:"):
                try:
                    usage = json.loads(chunk[10:])
                except json.JSONDecodeError:
                    pass
            elif chunk:
                content += chunk
    except Exception as e:
        raise HTTPException(500, f"Chat error: {e}")

    # Update session state
    message_count = len(req.history) + 1
    if req.agent_slug and req.channel_id:
        _update_session_state(req.agent_slug, req.channel_id, req.message, message_count)

    result = {"content": content, "model": model}
    if req.agent_name:
        result["agent_name"] = req.agent_name
    if usage:
        result["usage"] = usage

    # Save history for chat_complete (streaming saves via wrapper)
    if req.agent_slug and req.channel_id:
        new_messages = req.history + [
            {"role": "user", "content": req.message},
            {"role": "assistant", "content": content},
        ]
        _save_chat_history(req.agent_slug, req.channel_id, new_messages)

    return result


@router.get("/history")
async def get_chat_history(agent_slug: str, channel_id: str = "web"):
    """Load persisted chat history for an agent+channel."""
    messages = _load_chat_history(agent_slug, channel_id)
    return {"messages": messages, "count": len(messages)}


@router.delete("/history")
async def clear_chat_history(agent_slug: str, channel_id: str = "web"):
    """Clear persisted chat history for an agent+channel."""
    _clear_chat_history(agent_slug, channel_id)
    return {"success": True}
