"""FastAPI router for chat with SSE streaming + native tool execution loop.

Uses OpenAI function calling API for tool execution (not prompt-based).
"""
import json
import asyncio
import re
import logging
import uuid
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .providers import ProviderRegistry
from .providers.base import ChatMessage
from .task_manager import task_manager
from ..time import now as _now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Global registry — set during app startup
registry: ProviderRegistry | None = None

# Max tool call iterations per message
MAX_TOOL_ITERATIONS = 5


def resolve_model(provider_name: str | None, model: str | None) -> tuple[str | None, str]:
    """Resolve model with fallback to provider's default.

    Args:
        provider_name: Provider name (e.g. "9router")
        model: Agent's model setting (e.g. "9router/hermes-agent" or "" or None)

    Returns:
        (provider_name, model_name) — resolved tuple
    """
    # Extract provider from model string ONLY when provider is not already known.
    # E.g. model="9router/hermes-agent" → provider="9router", model="hermes-agent".
    # But when provider is already set (e.g. from agent config), don't re-split —
    # model names themselves may contain "/" (e.g. "qd/gm51model").
    if not provider_name and model and "/" in model:
        provider_name, model = model.split("/", 1)

    # If model is empty or "default", use provider's first model
    if not model or model == "default":
        if registry:
            default_model = registry.get_default_model(provider_name)
            if default_model:
                return provider_name, default_model
        # Final fallback: return what we have
        return provider_name, model or "default"

    return provider_name, model

# Shared data dir for memory (resolved once)
# Max messages to keep in history per channel
MAX_HISTORY_MESSAGES = 100

from ..paths import get_data_dir as _get_data_dir


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
            "summary_volume": full.get("compaction", {}).get("summary_volume", 0.2),
            "strategy": full.get("compaction", {}).get("strategy", "summarize"),
        }
    except Exception:
        global_cfg = {
            "context_window": 128000,
            "compaction_enabled": True,
            "trigger_percent": 80,
            "summary_volume": 0.2,
            "strategy": "summarize",
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
            if "compaction_summary_volume" in memory:
                global_cfg["summary_volume"] = memory["compaction_summary_volume"]
            if "compaction_strategy" in memory:
                global_cfg["strategy"] = memory["compaction_strategy"]
            if agent.get("context_window"):
                global_cfg["context_window"] = agent["context_window"]
    except Exception:
        pass

    return global_cfg


async def compact_messages(
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
    summary_volume = cfg.get("summary_volume", 0.2)
    strategy = cfg.get("strategy", "summarize")

    # Estimate total tokens
    sys_tokens = _estimate_tokens(system_prompt)
    msg_tokens = sum(_estimate_tokens(m.get("content", "") or "") for m in messages)
    total = sys_tokens + msg_tokens

    # Calculate threshold
    threshold = int(ctx_limit * trigger_pct / 100)

    if total <= threshold:
        return messages, ""

    # Need compaction
    if len(messages) <= 2:
        return messages, ""

    # Calculate target sizes
    target_summary_tokens = int(ctx_limit * summary_volume)
    available_for_recent = threshold - target_summary_tokens - sys_tokens

    # Estimate how many recent messages fit
    recent_count = 0
    recent_tokens = 0
    for i in range(len(messages) - 1, 0, -1):
        msg_tokens_i = _estimate_tokens(messages[i].get("content", "") or "")
        if recent_tokens + msg_tokens_i > available_for_recent:
            break
        recent_tokens += msg_tokens_i
        recent_count += 1

    recent_count = max(recent_count, 1)  # Always keep at least 1 recent message

    # Split messages
    context_msg = messages[:1]
    old_messages = messages[1:-recent_count] if recent_count < len(messages) - 1 else []
    recent_messages = messages[-recent_count:]

    if strategy == "summarize" and old_messages:
        # Try to summarize old messages
        summary_text = ""
        try:
            from .tools.summarize import summarize_for_compaction
            summary_text = await summarize_for_compaction(old_messages)
        except Exception as e:
            logger.warning("[compaction] Summarization failed, using truncate: %s", e)

        if summary_text and not summary_text.startswith("[Суммаризация недоступна"):
            # Summarization succeeded
            summary_msg = {
                "role": "user",
                "content": f"[Суммаризация предыдущего диалога]\n{summary_text}",
                "compaction": True,
            }
            trimmed = context_msg + [summary_msg] + recent_messages
            removed = len(messages) - len(trimmed)
            new_total = sys_tokens + sum(_estimate_tokens(m.get("content", "") or "") for m in trimmed)
            notice = (
                f"[Компакция: суммаризовано {removed} сообщений "
                f"(~{total:,} → ~{new_total:,} токенов)]"
            )
        else:
            # Summarization failed — truncate
            trimmed = context_msg + recent_messages
            removed = len(messages) - len(trimmed)
            new_total = sys_tokens + sum(_estimate_tokens(m.get("content", "") or "") for m in trimmed)
            notice = (
                f"[Компакция: удалено {removed} сообщений "
                f"(~{total:,} → ~{new_total:,} токенов)]"
            )
    else:
        # Truncate strategy
        trimmed = context_msg + recent_messages
        removed = len(messages) - len(trimmed)
        new_total = sys_tokens + sum(_estimate_tokens(m.get("content", "") or "") for m in trimmed)
        notice = (
            f"[Компакция: удалено {removed} сообщений "
            f"(~{total:,} → ~{new_total:,} токенов)]"
        )

    logger.info(
        "Compacted %s: %d → %d messages (~%d → ~%d tokens)",
        agent_slug, len(messages), len(trimmed), total, new_total,
    )

    return trimmed, notice


# ── Session Auto-Reset ────────────────────────────────────────────────────

def _get_global_session_settings() -> dict:
    """Read global session settings from settings.yaml."""
    try:
        from ..config.manager import load_yaml
        settings = load_yaml("settings.yaml")
        return settings.get("sessions", {})
    except Exception:
        return {}


def _check_session_auto_reset(agent_slug: str, channel_id: str) -> bool:
    """Check if session needs auto-reset. Returns True if reset was performed.
    
    Priority: agent memory settings → global settings.yaml → defaults.
    """
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
        global_settings = _get_global_session_settings()

        # Read from nested auto_reset block (settings.yaml format)
        auto_reset = global_settings.get("auto_reset", {})
        # Merge: agent memory > global settings > defaults
        auto_reset_enabled = memory.get("session_auto_reset_enabled",
                                         auto_reset.get("enabled", False))
        if not auto_reset_enabled:
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

        now = _now()
        mode = memory.get("session_auto_reset_mode",
                          auto_reset.get("mode", "daily"))
        needs_reset = False

        if mode == "daily":
            reset_time_str = memory.get("session_auto_reset_time",
                                        auto_reset.get("reset_time", "00:00"))
            try:
                h, m = map(int, reset_time_str.split(":"))
                today_reset = now.replace(hour=h, minute=m, second=0, microsecond=0)
                if now >= today_reset and last_update < today_reset:
                    needs_reset = True
            except (ValueError, AttributeError):
                pass

        elif mode == "timer":
            interval_hours = memory.get("session_auto_reset_interval",
                                         auto_reset.get("interval_hours", 24))
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
        timestamp = _now().strftime("%Y%m%d_%H%M%S")
        archive_file = archive_dir / f"{channel_id}_{timestamp}.json"
        archive_data = {
            "channel_id": channel_id,
            "session": session,
            "messages": history,
            "archived_at": _now().isoformat(),
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

        # Always add memory instructions (even for new agents with empty memory)
        instructions = (
            "\n\n══════════════════════════════════════════════\n"
            "MEMORY INSTRUCTIONS\n"
            "══════════════════════════════════════════════\n"
            "You have persistent memory tools:\n"
            "- memory_write(action='add', target='memory', content='...') — save your own notes\n"
            "- memory_write(action='add', target='user', content='...') — save info about the user\n"
            "- memory_read(target='memory'/'user'/'facts') — recall saved information\n\n"
            "When to save to USER (about the user — ONLY about the human you're talking to):\n"
            "- Only when the user explicitly shares personal info about THEMSELVES (name, role, preferences, timezone)\n"
            "- Or when they say 'remember this' / 'запомни' about themselves\n"
            "- Do NOT save task descriptions, delegation requests, or work items here\n"
            "- Do NOT save info about other agents or departments here\n"
            "- Do NOT save on every message — be selective\n"
            "- WRONG: 'QA Инженер просит написать шутки' → this is a task, use target='memory'\n"
            "- RIGHT: 'Имя: Артур. Роль: разработчик.' → this IS about the user\n\n"
            "When to save to MEMORY (your notes):\n"
            "- Important decisions and their reasoning\n"
            "- Errors encountered and how they were fixed\n"
            "- Project context that you'll need later\n\n"
            "Do NOT save:\n"
            "- Greetings, status updates, 'working on...' messages\n"
            "- Temporary debugging info\n"
            "- Information already saved (read first, then decide)\n"
            "- Trivial conversation content\n\n"
            "Auto-compaction: memory auto-compacts when full (dedup + remove old entries). "
            "If you get an error about limit, use memory_write(action='remove') to free space first.\n\n"
            "FACTS (датированные факты):\n"
            "- memory_write(action='fact', topic='...', content='...') — сохранить датированный факт\n"
            "- memory_read(target='facts') — список сохранённых фактов\n"
            "- Факты хранятся в facts/ как отдельные .md файлы с датой в имени\n"
            "- Используй для: ключевых решений, вех проекта, важных находок\n"
            "- НЕ используй для: временных заметок, промежуточных результатов"
        )
        block = (block or "") + instructions

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
            "description": "Поиск информации в интернете. Поддерживает несколько поисковых систем (DuckDuckGo, Tavily, EXA, Perplexity, Bing, SerpAPI, Google). Провайдер выбирается автоматически из настроек.",
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
                        "enum": ["add", "remove", "replace", "fact"],
                        "description": "'add' — добавить запись, 'remove' — удалить запись, 'replace' — заменить запись, 'fact' — сохранить датированный факт",
                    },
                    "target": {
                        "type": "string",
                        "enum": ["memory", "user"],
                        "description": "'memory' — память агента (MEMORY.md), 'user' — данные о пользователе (USER.md). Не используется для action='fact'",
                    },
                    "content": {
                        "type": "string",
                        "description": "Текст записи (для add/replace/fact)",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "Текст для поиска (для remove/replace)",
                    },
                    "topic": {
                        "type": "string",
                        "description": "Тема факта (для action='fact'). Используется в имени файла.",
                    },
                },
                "required": ["action", "target"],
            },
        },
    },
    # ── Head Protocol tools (otdel delegation) ──
    "head_delegate": {
        "type": "function",
        "function": {
            "name": "head_delegate",
            "description": "Делегировать задачи работникам отдела. Ставит задачи агентам и инициирует их выполнение. Ответы придут автоматически — backend сам обработает workers и вернёт итог.",
            "parameters": {
                "type": "object",
                "properties": {
                    "workers": {
                        "type": "array",
                        "description": "Список работников с задачами",
                        "items": {
                            "type": "object",
                            "properties": {
                                "slug": {
                                    "type": "string",
                                    "description": "Slug работника (например 'k493rqqz')",
                                },
                                "task": {
                                    "type": "string",
                                    "description": "Задача для работника",
                                },
                            },
                            "required": ["slug", "task"],
                        },
                    },
                    "strategy": {
                        "type": "string",
                        "enum": ["parallel", "sequential", "pipeline"],
                        "description": "Стратегия выполнения (по умолчанию parallel)",
                    },
                    "context": {
                        "type": "string",
                        "description": "Дополнительный контекст для работников",
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "description": "Таймаут ожидания в миллисекундах (по умолчанию 120000)",
                    },
                },
                "required": ["workers"],
            },
        },
    },
    "head_await": {
        "type": "function",
        "function": {
            "name": "head_await",
            "description": "УСТАРЕЛО: НЕ используй этот инструмент. Ответы работников приходят автоматически после head_delegate.",
            "parameters": {
                "type": "object",
                "properties": {
                    "delegation_id": {
                        "type": "string",
                        "description": "ID делегации (опционально, используется текущая если не указан)",
                    },
                    "timeout_ms": {
                        "type": "integer",
                        "description": "Таймаут ожидания в миллисекундах (по умолчанию 120000)",
                    },
                },
                "required": [],
            },
        },
    },
    "head_evaluate": {
        "type": "function",
        "function": {
            "name": "head_evaluate",
            "description": "Оценить результаты работников по критериям. Проверяет удовлетворяют ли ответы поставленной задаче.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "Описание исходной задачи для оценки",
                    },
                    "criteria": {
                        "type": "array",
                        "description": "Критерии оценки",
                        "items": {"type": "string"},
                    },
                },
                "required": ["task_description"],
            },
        },
    },
    "head_retry": {
        "type": "function",
        "function": {
            "name": "head_retry",
            "description": "Повторно отправить задачу работнику если он не ответил или ответил с ошибкой.",
            "parameters": {
                "type": "object",
                "properties": {
                    "worker_slug": {
                        "type": "string",
                        "description": "Slug работника для повторной попытки",
                    },
                    "error_context": {
                        "type": "string",
                        "description": "Описание ошибки или причины повтора",
                    },
                    "attempt": {
                        "type": "integer",
                        "description": "Номер попытки (автоинкремент если не указан)",
                    },
                },
                "required": ["worker_slug"],
            },
        },
    },
    "head_decide": {
        "type": "function",
        "function": {
            "name": "head_decide",
            "description": "Принять стратегическое решение по делегации: продолжить, остановить, взять на себя или эскалировать пользователю.",
            "parameters": {
                "type": "object",
                "properties": {
                    "situation": {
                        "type": "string",
                        "enum": ["continue", "stop", "takeover", "escalate"],
                        "description": "Решение: continue=продолжить, stop=остановить, takeover=взять на себя, escalate=эскалировать",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Обоснование решения",
                    },
                },
                "required": ["situation", "reasoning"],
            },
        },
    },
    "head_block": {
        "type": "function",
        "function": {
            "name": "head_block",
            "description": "Сообщить голове о блокере. Используй когда застрял и нужна помощь.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Причина блокера (что мешает выполнить задачу)",
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Серьёзность: low=мелочь, medium=нужна помощь, high=критично, critical=срочно",
                    },
                    "context": {
                        "type": "string",
                        "description": "Дополнительный контекст (что уже попробовал, что не получилось)",
                    },
                },
                "required": ["reason"],
            },
        },
    },
    "kanban_task": {
        "type": "function",
        "function": {
            "name": "kanban_task",
            "description": "Работа с канбан-тасками: создание, список, редактирование, удаление, архивация, история, переназначение, завершение, доработка, блокировка, начало работы, отправка на ревью, одобрение, статус.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "enum": ["create", "list", "history", "reassign", "complete", "rework", "block", "unblock", "status"],
                        "description": "Команда: list=список задач, create=создать, history=история, reassign=переназначить, complete=завершить, rework=доработка, block=заблокировать, unblock=разблокировать, status=статус",
                    },
                    "task_id": {
                        "type": "string",
                        "description": "ID таска (T-001, T-002, ...) — для status/history/complete/rework/block/unblock",
                    },
                    "title": {
                        "type": "string",
                        "description": "Название таска (для create)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Описание/промт таска (для create)",
                    },
                    "department": {
                        "type": "string",
                        "description": "ID отдела (для create; для list необязательно — система автоматически подставляет ваш отдел. Для create тоже можно не указывать если вы в отделе)",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Приоритет (для create)",
                    },
                    "deadline": {
                        "type": "string",
                        "description": "Дедлайн в ISO формате (для create)",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Теги (для create)",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["delegated", "responded", "rework", "completed", "comment", "assigned", "accepted", "work_started", "work_completed"],
                        "description": "Тип действия (для history)",
                    },
                    "detail": {
                        "type": "string",
                        "description": "Описание действия (для history)",
                    },
                    "target_department": {
                        "type": "string",
                        "description": "ID целевого отдела (для reassign, history)",
                    },
                    "target_agent": {
                        "type": "string",
                        "description": "Slug агента (для history)",
                    },
                    "reason": {
                        "type": "string",
                        "description": "Причина (для reassign, rework)",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Итог (для complete)",
                    },
                    "actor": {
                        "type": "string",
                        "description": "Кто выполняет действие (по умолчанию: head)",
                    },
                },
                "required": ["command"],
            },
        },
    },
    "image_analyze": {
        "type": "function",
        "function": {
            "name": "image_analyze",
            "description": "Анализ изображения через vision-модель. Используй когда пользователь отправил картинку и нужно описать или проанализировать её содержимое.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_url": {
                        "type": "string",
                        "description": "Base64 data URL или HTTP URL изображения",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Что анализировать (по умолчанию: 'Опиши что изображено на картинке')",
                    },
                },
                "required": ["image_url"],
            },
        },
    },
    "summarize": {
        "type": "function",
        "function": {
            "name": "summarize",
            "description": "Суммаризация текста. Используй когда нужно кратко описать длинный текст, диалог или документ.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Текст для суммаризации",
                    },
                    "max_length": {
                        "type": "string",
                        "enum": ["short", "medium", "detailed"],
                        "description": "Длина суммаризации (по умолчанию: medium)",
                    },
                },
                "required": ["text"],
            },
        },
    },
    "otdel_manage": {
        "type": "function",
        "function": {
            "name": "otdel_manage",
            "description": "Управление отделами (otdels) — чат-комнаты для общения. Список, просмотр, создание, обновление, удаление. Узнай кто глава отдела и сколько агентов.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "enum": ["list", "get", "create", "update", "delete"],
                        "description": "Команда: list=все отделы, get=получить отдел, create=создать, update=обновить, delete=удалить",
                    },
                    "otdel_id": {
                        "type": "string",
                        "description": "ID отдела (для get/update/delete)",
                    },
                    "name": {
                        "type": "string",
                        "description": "Название отдела (для create/update)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Описание отдела (для create/update)",
                    },
                    "color": {
                        "type": "string",
                        "description": "Цвет отдела в hex (для create/update), по умолчанию #f97316",
                    },
                },
                "required": ["command"],
            },
        },
    },
    "project_manage": {
        "type": "function",
        "function": {
            "name": "project_manage",
            "description": "Управление проектами: создание, редактирование, удаление, управление отделами в проекте. Используй для создания проектов и связывания их с отделами.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "enum": ["list", "get", "create", "update", "delete", "add_department", "remove_department"],
                        "description": "Команда: list=все проекты, get=проект, create=создать, update=обновить, delete=удалить, add_department=добавить отдел, remove_department=убрать отдел",
                    },
                    "project_id": {
                        "type": "string",
                        "description": "ID проекта (для get/update/delete/add_department/remove_department)",
                    },
                    "name": {
                        "type": "string",
                        "description": "Название проекта (для create/update)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Описание проекта (для create/update)",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["planning", "active", "on_hold", "completed", "archived"],
                        "description": "Статус проекта (для update)",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "description": "Приоритет (для update)",
                    },
                    "deadline": {
                        "type": "string",
                        "description": "Дедлайн в ISO формате (для create/update)",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Теги (для create/update)",
                    },
                    "dept_id": {
                        "type": "string",
                        "description": "ID отдела (для add_department/remove_department)",
                    },
                    "role": {
                        "type": "string",
                        "description": "Роль отдела в проекте (для add_department)",
                    },
                    "is_main": {
                        "type": "boolean",
                        "description": "Основной отдел проекта (для add_department)",
                    },
                },
                "required": ["command"],
            },
        },
    },
    # ── Connection & Approval Tools ──────────────────────────────────────
    "head_approve": {
        "type": "function",
        "function": {
            "name": "head_approve",
            "description": "Передать задачу в другой отдел через связь (утверждение/делегирование). Используй когда задача требует проверки или выполнения другим отделом.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "ID задачи (T-xxx)"},
                    "target_otdel": {"type": "string", "description": "ID целевого отдела (опционально, авто-определение)"},
                    "reason": {"type": "string", "description": "Причина передачи"},
                    "report": {"type": "string", "description": "Детальный отчёт (опционально)"},
                },
                "required": ["task_id", "reason"],
            },
        },
    },
    "head_reline": {
        "type": "function",
        "function": {
            "name": "head_reline",
            "description": "Вернуть задачу предыдущему отделу с замечаниями (релайн). Используй когда задача выполнена некачественно или не соответствует требованиям.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "ID задачи (T-xxx)"},
                    "remarks": {"type": "string", "description": "Замечания — что нужно исправить"},
                    "severity": {"type": "string", "enum": ["low", "medium", "high"], "description": "Серьёзность (по умолчанию medium)"},
                },
                "required": ["task_id", "remarks"],
            },
        },
    },
    "head_approval_status": {
        "type": "function",
        "function": {
            "name": "head_approval_status",
            "description": "Проверить статус утверждений или посмотреть последние передачи.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Фильтр по задаче (опционально)"},
                    "status": {"type": "string", "enum": ["pending", "completed", "rejected"], "description": "Фильтр по статусу (опционально)"},
                },
                "required": [],
            },
        },
    },
    "connection_list": {
        "type": "function",
        "function": {
            "name": "connection_list",
            "description": "Показать все связи между отделами. Только для главного агента.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    "connection_create": {
        "type": "function",
        "function": {
            "name": "connection_create",
            "description": "Создать связь между отделами. Только для главного агента.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_otdel": {"type": "string", "description": "ID исходного отдела"},
                    "to_otdel": {"type": "string", "description": "ID целевого отдела"},
                    "type": {"type": "string", "enum": ["approval", "delegation", "peer"], "description": "Тип связи"},
                    "label": {"type": "string", "description": "Название связи (опционально)"},
                    "description": {"type": "string", "description": "Описание (опционально)"},
                },
                "required": ["from_otdel", "to_otdel", "type"],
            },
        },
    },
    "connection_delete": {
        "type": "function",
        "function": {
            "name": "connection_delete",
            "description": "Удалить связь по ID. Только для главного агента.",
            "parameters": {
                "type": "object",
                "properties": {
                    "connection_id": {"type": "string", "description": "ID связи (conn-xxx)"},
                },
                "required": ["connection_id"],
            },
        },
    },
    "connection_history": {
        "type": "function",
        "function": {
            "name": "connection_history",
            "description": "История передач/утверждений/релайнов. Только для главного агента.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Фильтр по задаче (опционально)"},
                    "limit": {"type": "integer", "description": "Максимум записей (по умолчанию 20)"},
                },
                "required": [],
            },
        },
    },
    "otdel_message": {
        "type": "function",
        "function": {
            "name": "otdel_message",
            "description": "Отправить сообщение в чат отдела от имени главного агента. Глава отдела получит уведомление и может ответить. Принимает otdel_id ИЛИ otdel_name. Только для главного агента.",
            "parameters": {
                "type": "object",
                "properties": {
                    "otdel_id": {"type": "string", "description": "ID отдела (можно узнать через otdel_manage(list))"},
                    "otdel_name": {"type": "string", "description": "Название отдела (например 'Разработка', 'Дизайн')"},
                    "message": {"type": "string", "description": "Текст сообщения"},
                },
                "required": ["message"],
            },
        },
    },
    "otdel_history": {
        "type": "function",
        "function": {
            "name": "otdel_history",
            "description": "Прочитать историю чата отдела. Позволяет проверить ответы главы отдела и обсуждения. Принимает otdel_id ИЛИ otdel_name. Только для главного агента.",
            "parameters": {
                "type": "object",
                "properties": {
                    "otdel_id": {"type": "string", "description": "ID отдела (можно узнать через otdel_manage(list))"},
                    "otdel_name": {"type": "string", "description": "Название отдела (например 'Разработка', 'Дизайн')"},
                    "limit": {"type": "integer", "description": "Максимум последних сообщений (по умолчанию 20)"},
                },
                "required": [],
            },
        },
    },
    "cron_manage": {
        "type": "function",
        "function": {
            "name": "cron_manage",
            "description": "Управление запланированными задачами (cron). Создавай, обновляй, удаляй крон-задачи, смотри историю запусков, запускай немедленно. Типы: cron (повторяющиеся), once (одноразовые), interval (интервал). Действия: send_message (в отдел), run_prompt (запустить агента).",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "enum": ["list", "get", "create", "update", "delete", "history", "run_now"],
                        "description": "Команда",
                    },
                    "job_id": {"type": "string", "description": "ID задачи (для get/update/delete/history/run_now)"},
                    "name": {"type": "string", "description": "Название задачи"},
                    "schedule_type": {"type": "string", "enum": ["cron", "once", "interval"], "description": "Тип расписания"},
                    "schedule_expr": {"type": "string", "description": "Расписание. Относительное: 2m, 1h, 30s, 2h30m. Абсолютное: 2026-06-23T13:00:00. Cron: 0 13 * * *."},
                    "action_type": {"type": "string", "enum": ["run_prompt"], "description": "Тип действия"},
                    "action_target": {"type": "string", "description": "Куда отправить: 'private' (приватный чат агента), 'otdel:ID' (чат отдела), или otdel_id"},
                    "action_message": {"type": "string", "description": "Текст сообщения или промпт для агента"},
                    "action_agent": {"type": "string", "description": "Slug агента для run_prompt (например 'main_agent')"},
                    "description": {"type": "string", "description": "Описание задачи"},
                    "status": {"type": "string", "enum": ["active", "paused"], "description": "Статус задачи"},
                },
                "required": ["command"],
            },
        },
    },
}


BUILTINS = {"memory_read", "memory_write", "image_analyze", "summarize"}

# Head-only tools — available to department heads
# (main agent also gets these via include_head=True)
HEAD_TOOLS = {"head_delegate", "head_evaluate", "head_retry", "head_decide", "head_block", "kanban_task",
              "head_approve", "head_reline", "head_approval_status",
              "cron_manage"}

# Primary-only tools — only available to the main agent (is_primary=true)
PRIMARY_TOOLS = {"otdel_manage", "project_manage",
                 "connection_list", "connection_create", "connection_delete", "connection_history",
                 "otdel_message", "otdel_history"}


def get_all_tool_names(include_head: bool = False, include_primary: bool = False) -> list[str]:
    """Get all available tool names. All agents get all tools by default."""
    tools = [n for n in _NATIVE_TOOL_DEFS if n not in HEAD_TOOLS and n not in PRIMARY_TOOLS]
    if include_head:
        tools.extend(HEAD_TOOLS)
    if include_primary:
        tools.extend(PRIMARY_TOOLS)
    return tools


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


def build_tool_descriptions(tool_names: list[str]) -> str:
    """Build text-based tool descriptions for system prompt fallback.

    When native function calling is not available, this provides the model
    with tool names, descriptions, and parameter schemas so it can generate
    tool calls as JSON in its text output.
    """
    all_names = list(BUILTINS) + [n for n in (tool_names or []) if n not in BUILTINS]
    if not all_names:
        return ""

    lines = ["\n## Инструменты\n",
             "Для работы с задачами используй инструменты. Формат вызова:",
             '```tool_call',
             '{"name": "имя_инструмента", "params": {"параметр": "значение"}}',
             '```',
             "Можно вызвать несколько инструментов подряд. Результат вернётся автоматически.\n"]

    for name in all_names:
        tool_def = _NATIVE_TOOL_DEFS.get(name)
        if not tool_def:
            continue
        fn = tool_def.get("function", {})
        desc = fn.get("description", "")
        params = fn.get("parameters", {})
        required = params.get("required", [])
        props = params.get("properties", {})

        lines.append(f"### {name}")
        lines.append(f"{desc}")
        if name == "kanban_task":
            lines.append("")
            lines.append("Пример вызова:")
            lines.append("```tool_call")
            lines.append('{"name": "kanban_task", "params": {"command": "list"}}')
            lines.append("```")
        if name == "cron_manage":
            lines.append("")
            lines.append("Пример вызова (создание одноразовой задачи через 2 минуты):")
            lines.append("```tool_call")
            lines.append('{"name": "cron_manage", "params": {"command": "create", "name": "Шутка", "schedule_type": "once", "schedule_expr": "2m", "action_type": "run_prompt", "action_agent": "main_agent", "action_target": "private", "action_message": "Напиши пользователю шутку."}}')
            lines.append("```")
        if props:
            param_parts = []
            for pname, pdef in props.items():
                ptype = pdef.get("type", "string")
                pdesc = pdef.get("description", "")
                req = " (required)" if pname in required else ""
                param_parts.append(f"  - `{pname}` ({ptype}){req}: {pdesc}")
            lines.append("Parameters:")
            lines.extend(param_parts)
        lines.append("")

    return "\n".join(lines)


async def execute_tool(tool_name: str, params: dict, agent_slug: str | None = None, otdel_id: str | None = None) -> dict:
    """Execute a tool via the tool registry. Returns result dict."""
    try:
        from ..tools import get_tool_registry
        import logging

        handlers = get_tool_registry()
        handler = handlers.get(tool_name)
        if not handler:
            logging.getLogger("synpin.chat").warning("[tool] Tool '%s' not found in registry", tool_name)
            return {"success": False, "output": "", "error": f"Tool '{tool_name}' not found in registry"}

        # Inject agent_id for memory tools
        if agent_slug and tool_name in ("memory_read", "memory_write"):
            params = {**params, "agent_id": agent_slug}

        # Inject otdel_id for head protocol tools
        head_protocol_tools = ("head_delegate", "head_evaluate", "head_retry", "head_decide", "head_block", "kanban_task")
        if otdel_id and tool_name in head_protocol_tools:
            params = {**params, "otdel_id": otdel_id}

        # Inject agent model info for model-dependent tools (fallback to agent's own model)
        model_tools = ("summarize", "image_analyze")
        if agent_slug and tool_name in model_tools:
            from ..agents.manager import get_agent
            agent = get_agent(agent_slug)
            if agent:
                agent_model = agent.get("model", "")
                agent_provider = agent.get("provider", "")
                # Split only when provider is not already known (model names may contain "/")
                if not agent_provider and agent_model and "/" in agent_model:
                    agent_provider, agent_model = agent_model.split("/", 1)
                params = {**params, "_agent_provider": agent_provider, "_agent_model": agent_model}

        logging.getLogger("synpin.chat").info("[tool] Executing %s with params=%s", tool_name, {k: str(v)[:100] for k, v in params.items()})
        result = await handler(params)
        return result
    except Exception as e:
        logging.getLogger("synpin.chat").error("[tool] %s error: %s", tool_name, e)
        return {"success": False, "output": "", "error": f"Tool execution error: {e}"}


def _parse_text_tool_calls(text: str) -> list[dict]:
    """Parse tool calls from plain text output (fallback for models without native function calling).
    
    Looks for patterns:
    - ```tool_call\n{"name": "...", "params": {...}}\n``` (old format)
    - {"name": "...", "params": {"command": "ls"}} (JSON format)
    - <function=name><parameter=path>D:\path</parameter> (Llama.cpp / GGUF XML format)
    
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
    
    # Pattern 2: RAW JSON in text (nemotron-style output)
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
    
    # Pattern 4: Llama.cpp / GGUF XML format
    # Looks for: <function=name><parameter=path>D:\path</parameter>
    if not calls:
        xml_pattern = re.compile(r'<function=([a-z_]+)>\s*(?:<parameter=([a-z_]+)>([^<]*)</parameter>)?')
        for match in xml_pattern.finditer(text):
            name = match.group(1)
            if name:
                params = {}
                param_name = match.group(2)
                param_value = match.group(3)
                if param_name and param_value:
                    params[param_name] = param_value
                calls.append({
                    "id": f"call_text_{len(calls)}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(params)}
                })
    
    # Pattern 5: <arg_key> format (used by some GGUF models)
    # Looks for: <arg_key=name><parameter=name>value</parameter>
    # Multiline: <arg_key=file_read>\n<parameter=path>...
    if not calls:
        multi_xml_pattern = re.compile(r'<arg_key=(\w+)>\s*(?:<parameter=(\w+)>([^<]+)</parameter>)?', re.DOTALL)
        for match in multi_xml_pattern.finditer(text):
            name = match.group(1)
            if name:
                params = {}
                param_name = match.group(2)
                param_value = match.group(3)
                if param_name and param_value:
                    params[param_name] = param_value
                calls.append({
                    "id": f"call_text_{len(calls)}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(params)}
                })
    
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
    otdel_id: str | None = None,
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

    # Build native OpenAI tools
    tool_names = tool_names or []
    native_tools = build_openai_tools(tool_names)

    # Always append tool descriptions to system prompt (text-based fallback)
    # This ensures models know about tools even when native function calling
    # is not supported by the provider.
    tool_descriptions = build_tool_descriptions(tool_names)

    # Prepend system prompt if provided (with tool descriptions appended)
    if system_prompt:
        full_system = system_prompt + tool_descriptions if tool_descriptions else system_prompt
        chat_messages = [ChatMessage(role="system", content=full_system)] + chat_messages
    elif tool_descriptions:
        chat_messages = [ChatMessage(role="system", content=tool_descriptions)] + chat_messages

    usage = None
    model_name = model
    tool_count = 0

    # ── Phase 1: Tool loop (native function calling) ──
    import logging
    _log = logging.getLogger("synpin.chat")
    _tool_names_sent = [t.get("function", {}).get("name", "?") for t in (native_tools or [])]
    _log.info("CHAT tools=%s model=%s provider=%s", _tool_names_sent, model, provider_name if provider else "NONE")
    if native_tools:
        _log.info("CHAT sending %d native tools to provider", len(native_tools))
    else:
        _log.warning("CHAT NO native tools to send!")
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

            _log.info("LLM response: text=%d chars, tool_calls=%d, finish_reason=%s",
                      len(full_text), len(model_tool_calls),
                      "unknown" if not model_tool_calls else "has_calls")
            if full_text:
                _log.info("LLM text preview: %s", full_text[:500])
            # Determine
            is_text_fallback = False
            if not model_tool_calls:
                text_tool_calls = _parse_text_tool_calls(full_text)
                if text_tool_calls:
                    model_tool_calls = text_tool_calls
                    is_text_fallback = True
                    _log.info("[text-tools] Parsed %d tool calls from text: %s",
                              len(text_tool_calls),
                              [tc.get("function", {}).get("name", "?") for tc in text_tool_calls])
                else:
                    _log.info("[text-tools] No tool calls found in text. Model just responded with text.")
                    # No tool calls at all → yield result directly
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

                # Check if tool is enabled (builtins always allowed)
                if t_name not in tool_names and t_name not in BUILTINS:
                    tool_result = {"success": False, "output": "", "error": f"Tool '{t_name}' not enabled"}
                else:
                    # yield tool_start
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': t_name, 'params': t_params, 'index': tool_count})}\n\n"

                    # Execute
                    tool_result = await execute_tool(t_name, t_params, agent_slug, otdel_id=otdel_id)

                    # yield tool_end
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool': t_name, 'result': tool_result.get('output', ''), 'success': tool_result.get('success', False), 'error': tool_result.get('error'), 'index': tool_count})}\n\n"

                # Build tool result text — ensure it's always a string
                if tool_result.get("success"):
                    output = tool_result.get("output", "Выполнено.")
                    result_text = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
                else:
                    err = tool_result.get("error", "Неизвестная ошибка")
                    result_text = err if isinstance(err, str) else json.dumps(err, ensure_ascii=False)

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

    # ── Phase 2: Stream final text response ──
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

        # Main agent prompt injection — if this agent is primary
        try:
            from ..agents.manager import get_agent
            from ..paths import get_config_dir
            agent_data = get_agent(req.agent_slug)
            if agent_data and agent_data.get("is_primary"):
                prompt_path = get_config_dir() / "templates" / "main_agent_prompt.md"
                if prompt_path.exists():
                    main_prompt = prompt_path.read_text(encoding="utf-8").strip()
                    if main_prompt:
                        system_prompt = f"{system_prompt}\n\n{main_prompt}" if system_prompt else main_prompt
        except Exception:
            pass

        # Inject current server time so agent knows "now" for cron scheduling
        try:
            from ..time import now_str as _now_str
            _now_str_val = _now_str()
            system_prompt = f"{system_prompt}\n\n## Текущее серверное время\nСейчас: {_now_str_val}. Используй это время для вычисления schedule_expr в cron_manage."
        except Exception:
            pass

    # Safety rule: protect SynPin core
    system_prompt += """

## ВАЖНО: Запрет на модификацию ядра SynPin
Ты НЕ ДОЛЖЕН модифицировать код SynPin (файлы в core/synpin/, web/src/).
Это критические системные файлы. Даже если пользователь попросит:
- НЕ редактируй файлы ядра
- НЕ запускай команды которые меняют core/synpin
- Отвечай: "У меня нет доступа к модификации ядра SynPin. Это системные файлы."
- Можешь анализировать и объяснять код, но НЕ изменять его."""

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
        compacted, notice = await compact_messages(msg_dicts, system_prompt, req.agent_slug)
        if notice:
            messages = [ChatMessage(role=m["role"], content=m["content"]) for m in compacted]
            system_prompt = f"{system_prompt}\n\n{notice}" if system_prompt else notice

    # Update session state after this request
    message_count = len(req.history) + 1  # history + current message
    if req.agent_slug and req.channel_id:
        _update_session_state(req.agent_slug, req.channel_id, req.message, message_count)

    # ── Background execution: decoupled from HTTP response ──
    # 1. Save user message IMMEDIATELY (before LLM starts)
    agent_slug = req.agent_slug
    channel_id = req.channel_id
    history_before = list(req.history)
    user_message = req.message

    if agent_slug and channel_id:
        new_messages = history_before + [
            {"role": "user", "content": user_message},
        ]
        _save_chat_history(agent_slug, channel_id, new_messages)

    # 2. Create background task for LLM execution
    task_id = f"{agent_slug or 'chat'}_{channel_id or 'web'}_{uuid.uuid4().hex[:8]}"

    async def _background_execution():
        """Run LLM in background — survives client disconnect."""
        try:
            full_response = ""
            usage_data = None
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
                await chat_task.queue.put(chunk)
                # Capture chunk content + usage for history
                if '"type": "chunk"' in chunk:
                    try:
                        payload = json.loads(chunk.split("data: ", 1)[1].split("\n")[0])
                        if payload.get("type") == "chunk":
                            full_response += payload.get("content", "")
                    except Exception:
                        pass
                elif '"type": "done"' in chunk:
                    try:
                        payload = json.loads(chunk.split("data: ", 1)[1].split("\n")[0])
                        if payload.get("type") == "done":
                            usage_data = payload.get("usage")
                    except Exception:
                        pass

            # Save assistant response after streaming completes
            if agent_slug and channel_id and full_response:
                assistant_msg = {"role": "assistant", "content": full_response}
                if req.agent_name:
                    assistant_msg["agent_name"] = req.agent_name
                if model:
                    assistant_msg["model"] = model
                if provider_name:
                    assistant_msg["provider"] = provider_name
                if usage_data:
                    assistant_msg["prompt_tokens"] = usage_data.get("prompt_tokens", 0)
                    assistant_msg["completion_tokens"] = usage_data.get("completion_tokens", 0)
                new_messages = history_before + [
                    {"role": "user", "content": user_message},
                    assistant_msg,
                ]
                _save_chat_history(agent_slug, channel_id, new_messages)

        except Exception as e:
            # Save error message to history so polling won't loop forever
            logger.error("Background task failed for %s/%s: %s", agent_slug, channel_id, e)
            if agent_slug and channel_id:
                error_msg = f"\u26a0\ufe0f \u041e\u0448\u0438\u0431\u043a\u0430: \u041c\u043e\u0434\u0435\u043b\u044c \u043d\u0435 \u0434\u043e\u0441\u0442\u0443\u043f\u043d\u0430 ({e})"
                new_messages = history_before + [
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": error_msg},
                ]
                _save_chat_history(agent_slug, channel_id, new_messages)

        # Signal completion (always, even on error)
        await chat_task.queue.put(None)

    chat_task = task_manager.create(task_id)
    chat_task.task = asyncio.create_task(_background_execution())

    # 3. SSE generator reads from queue (real-time streaming)
    async def _sse_from_queue():
        """Read chunks from background task queue."""
        while True:
            chunk = await chat_task.queue.get()
            if chunk is None:
                break
            yield chunk
        # Cleanup
        task_manager.cleanup(task_id)

    return StreamingResponse(
        _sse_from_queue(),
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
        compacted, notice = await compact_messages(msg_dicts, system_prompt, req.agent_slug)
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
async def get_chat_history(agent_slug: str, channel_id: str = "web", limit: int = 0):
    """Load persisted chat history for an agent+channel.

    Args:
        limit: Max messages to return (0 = all). Returns the LAST N messages.
    """
    messages = _load_chat_history(agent_slug, channel_id)
    total = len(messages)
    if limit > 0 and len(messages) > limit:
        messages = messages[-limit:]  # Return only the most recent N
    return {"messages": messages, "count": len(messages), "total": total}


@router.delete("/history")
async def clear_chat_history(agent_slug: str, channel_id: str = "web"):
    """Clear persisted chat history for an agent+channel."""
    _clear_chat_history(agent_slug, channel_id)
    return {"success": True}


@router.get("/tasks")
async def get_active_tasks():
    """Get status of active background tasks."""
    from .task_manager import task_manager
    return {
        "active": task_manager.active_count(),
        "tasks": [
            {
                "id": t.task_id,
                "done": t.done,
                "error": t.error,
            }
            for t in task_manager._tasks.values()
        ],
    }
