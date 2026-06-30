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
from fastapi import APIRouter, HTTPException, Request
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
    """Load agent memory data (USER, MEMORY, FACTS) for system prompt injection.

    Returns ONLY the memory data — no instructions.
    Instructions are added separately at the END of system prompt via _get_memory_instructions().

    Uses the shared MemoryManager cache (synpin.memory.get_manager) so the
    same instance is reused across tool calls, system-prompt assembly, and
    HTTP API calls within a single process.
    """
    if not agent_slug:
        return ""
    try:
        from ..memory import get_manager
        manager = get_manager(agent_slug)
        return manager.get_system_prompt_block() or ""
    except Exception as e:
        logger.warning("Failed to load memory for %s: %s", agent_slug, e)
        return ""


def _get_memory_instructions() -> str:
    """Memory usage instructions — injected at the END of system prompt.

    Being last means the model reads this right before generating a response,
    so it remembers to use memory/session tools when appropriate.
    """
    return (
        "\n\n══════════════════════════════════════════════\n"
        "ПАМЯТЬ И ИСТОРИЯ — КАК ИСПОЛЬЗАТЬ\n"
        "══════════════════════════════════════════════\n"
        "Твоя память (USER, MEMORY, FACTS) уже загружена в начале этого промпта.\n"
        "Ты видишь её — НЕ НУЖНО вызывать memory_read перед каждым ответом.\n\n"
        "КРИТИЧЕСКИ ВАЖНО — НЕ ВРИ ПРО ЗАПИСЬ:\n"
        "Ты НЕ ДОЛЖЕН говорить 'Записал', 'Запомнил', 'Добавил в память' если НЕ вызвал\n"
        "memory_write в этом же ответе. Если факт стоит запомнить — ВЫЗОВИ memory_write,\n"
        "дождись ответа 'success', и ТОЛЬКО ПОТОМ подтверждай запись пользователю.\n"
        "Если ты не вызвал memory_write — так и скажи: 'Это интересно, хочешь чтобы я запомнил?'\n"
        "Не подтверждай действие, которое не произошло. Это вводит пользователя в заблуждение.\n\n"
        "КОГДА ВЫЗЫВАТЬ memory_read:\n"
        "- Когда нужно вспомнить конкретный факт или деталь\n"
        "- 'А что мы решали?', 'как называлась задача?'\n"
        "- memory_read(target='facts') — датированные решения\n\n"
        "КОГДА ВЫЗЫВАТЬ session_history:\n"
        "- 'Что мы обсуждали', 'помнишь', 'а в прошлый раз', 'что было вчера'\n"
        "- session_history(action='list') — покажи список архивов\n"
        "- session_history(action='search', query='...') — ищи по ключевым словам\n\n"
        "ЗАПИСЫВАЙ В ПАМЯТЬ САМОСТОЯТЕЛЬНО — НЕ ЖДИ ПОКА ПОПРОСЯТ:\n"
        "Когда пользователь сообщает факт о себе, своей жизни или работе — запомни это\n"
        "автоматически через memory_write. Пользователь НЕ ДОЛЖЕН говорить 'запиши'.\n"
        "Это твоя работа — замечать важное и сохранять без напоминаний.\n"
        "Формат записи: memory_write(action='add', target='user', content='...').\n\n"
        "ТРИ ХРАНИЛИЩА, РАЗНАЯ СЕМАНТИКА. Перед записью определи КУДА идёт факт:\n\n"
        "**USER.md — личность пользователя (target='user'):**\n"
        "- Имя, возраст, профессия, навыки, опыт\n"
        "- Характер, манера общения, предпочтения в формате ответов\n"
        "- Семья, важные люди, регулярные маршруты\n"
        "- Хронические особенности здоровья, лекарства\n"
        "- НЕ пиши сюда события или планы — это для MEMORY\n\n"
        "**MEMORY.md — долгоживущая память (target='memory'):**\n"
        "- События жизни: был у врача, поездка, что-то важное\n"
        "- Планы: 'на выходные хочу заняться SynPin', 'через месяц отпуск'\n"
        "- Контекст, важный через недели/месяцы: что обсуждали, что обещали\n"
        "- Используй чтобы спустя время напомнить: 'а помнишь ты хотел...'\n"
        "- НЕ пиши сюда итоги решений — это для FACTS\n\n"
        "**FACTS (action='fact') — блокнот решений:**\n"
        "- Итог обсуждения задачи: 'решили использовать Sonnet 4 для бэкенда'\n"
        "- Финальный выбор после сравнения вариантов\n"
        "- ADR-style заметки о том, КАК что-то сделали\n"
        "- Записывается ТОЛЬКО когда был реальный ход обсуждения → появился итог\n"
        "- НЕ пиши сюда 'привет как дела' или мелкие операции\n\n"
        "НЕ ПИШИ В ПАМЯТЬ ВООБЩЕ:\n"
        "- Приветствия, статусы, 'работаю над...'\n"
        "- Повторы того что уже в памяти (сначала прочитай)\n"
        "- Мелкие технические операции (открыл файл, прочитал строку)\n"
        "- Информацию из архивных сессий, если она уже там сохранена"
    )


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

# ─── Native function calling tool definitions ────────────────────────
# OpenAI function calling format — sent in the `tools` parameter.
#
# Built dynamically from tools/_registry. To add a new tool, write a
# handler in tools/<name>.py wrapped in @register_tool(...). That's it.
# Parameter schemas are omitted (handlers still take params: dict).
# Recover full JSON schemas later via pydantic models per handler.
#
# Lazy build: the dict is filled on first use, not at module-import
# time. Reason: chat/ws_router.py imports from this module, and
# some tools/*.py modules import chat/ws_router — so eagerly building
# here would cause circular imports on first boot.
_NATIVE_TOOL_DEFS: dict[str, dict] = {}
_BUILD_ATTEMPTED: bool = False


def _rebuild_native_tool_defs() -> dict:
    """Build OpenAI-style function definitions from the @register_tool registry.

    Imports synpin.tools (fires every @register_tool decorator) and
    walks the registry. Idempotent — safe to call from anywhere.
    """
    from .. import tools  # noqa: F401  -- triggers every @register_tool
    from ..tools._registry import all_tools
    return {
        name: {
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        }
        for name, spec in all_tools().items()
    }


def _ensure_defs_built() -> None:
    """Populate _NATIVE_TOOL_DEFS on first use. Idempotent.

    Note: this function may be reached via `from X import Y`, in which
    case Python stores it under the importing module's namespace; the
    enclosing function's `globals()` is NOT this module's dict. Resolve
    the right dict via sys.modules + the function's __module__.
    """
    import sys
    global _BUILD_ATTEMPTED
    if _BUILD_ATTEMPTED:
        return
    _BUILD_ATTEMPTED = True
    target = sys.modules[_ensure_defs_built.__module__]
    target.__dict__["_NATIVE_TOOL_DEFS"] = _rebuild_native_tool_defs()


def get_native_tool_defs() -> dict:
    """Public accessor returning the live _NATIVE_TOOL_DEFS dict.

    Triggers lazy build on first call. Always returns the current
    dict from the chat.router module — callers must NOT hold onto
    the returned reference across rebinds, or they can simply
    re-call this function.
    """
    import sys
    mod = sys.modules["synpin.chat.router"]
    if not mod.__dict__["_NATIVE_TOOL_DEFS"]:
        mod.__dict__["_ensure_defs_built"]()
    return mod.__dict__["_NATIVE_TOOL_DEFS"]


def _ensure_defs_built_first() -> dict:
    """One-shot helper: ensures built and returns the live dict.

    Preferred entry point for callers that don't already import the
    symbol directly. Combining build + lookup into one function makes
    sure both happen against the live module dict.
    """
    _ensure_defs_built()
    return get_native_tool_defs()





BUILTINS = {"memory_read", "memory_write", "image_analyze", "summarize", "session_history"}

# Head-only tools — available to department heads
# (main agent also gets these via include_head=True)
#
# NOTE: cron_manage was REMOVED on 2026-06-30 — scheduling intent is
# now parsed directly from user_text via cron/intent_parser.py in
# chat/router.py's auto-schedule hook. Letting agents call cron_manage
# caused infinite recursion (agent re-scheduled itself on every cron
# fire, producing "5 напомни про чайник" spam). The HTTP API
# (/api/cron/jobs) and UI Settings → Крон remain available for manual
# management — only the in-agent tool was removed.
HEAD_TOOLS = {"head_delegate", "head_evaluate", "head_retry", "head_decide", "head_block", "kanban_task",
              "head_approve", "head_reline", "head_approval_status",
              "skill_manage"}

# Primary-only tools — only available to the main agent (is_primary=true)
PRIMARY_TOOLS = {"otdel_manage", "project_manage",
                 "connection_list", "connection_create", "connection_delete", "connection_history",
                 "otdel_message", "otdel_history"}

# Tools flagged as "dangerous" — UI shows warning icon and tooltip.
# These tools can modify the system (filesystem, shell, code execution).
# Kept as a constant (not a settings.yaml field) because it's a code-level
# safety policy, not a user preference.
DANGEROUS_TOOLS = {"terminal", "code_exec", "file_write"}


def get_all_tool_names(include_head: bool = False, include_primary: bool = False) -> list[str]:
    """Get all available tool names for the agent context.

    All agents get all tools by default, MINUS those globally disabled in
    settings.yaml:tools.disabled. The disabled list is re-read on every
    call so UI toggles take effect immediately.
    """
    # Use accessor that reads through to chat.router's live dict.
    native_defs = get_native_tool_defs()
    from ..config.manager import get_disabled_tools
    disabled = set(get_disabled_tools())

    tools = [
        n for n in native_defs
        if n not in HEAD_TOOLS and n not in PRIMARY_TOOLS and n not in disabled
    ]
    if include_head:
        tools.extend(t for t in HEAD_TOOLS if t not in disabled)
    if include_primary:
        tools.extend(t for t in PRIMARY_TOOLS if t not in disabled)
    return tools


def is_tool_dangerous(name: str) -> bool:
    """Return True if this tool can modify the system (terminal, code, files)."""
    return name in DANGEROUS_TOOLS


def build_openai_tools(tool_names: list[str]) -> list[dict] | None:
    """Build OpenAI function calling tools list for enabled tools."""
    tools = []
    native_defs = get_native_tool_defs()  # lazy-build safe accessor

    # Always include built-in tools
    for name in BUILTINS:
        tool_def = native_defs.get(name)
        if tool_def:
            tools.append(tool_def)

    # Add agent-specific tools
    for name in tool_names:
        if name not in BUILTINS:
            tool_def = native_defs.get(name)
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

    native_defs = get_native_tool_defs()

    lines = ["\n## Инструменты\n",
             "Для работы с задачами используй инструменты. Формат вызова:",
             '```tool_call',
             '{"name": "имя_инструмента", "params": {"параметр": "значение"}}',
             '```',
             "Можно вызвать несколько инструментов подряд. Результат вернётся автоматически.\n"]

    for name in all_names:
        tool_def = native_defs.get(name)
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
        if agent_slug and tool_name in ("memory_read", "memory_write", "session_history"):
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

        # Inject available skills (name + description only — full text via skill_view)
        try:
            from ..skills.manager import list_skills
            from ..config.manager import get_disabled_skills
            skill_disabled = set(get_disabled_skills())
            skill_list = [s for s in list_skills() if s.name not in skill_disabled]
            if skill_list:
                lines = ["\n\n## Доступные скиллы\n"]
                lines.append(
                    "Это процедуры и подходы для решения задач. "
                    "Используй skill_view для получения полного текста скилла."
                )
                for s in skill_list:
                    lines.append(f"- **{s.name}** — {s.description}")
                system_prompt += "\n".join(lines)
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

    # Memory instructions at the very END — last thing the model reads before responding
    system_prompt += _get_memory_instructions()

    return system_prompt


@router.post("/stream")
async def chat_stream(req: ChatRequest, request: Request):
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
                # ── Auto-schedule hook ─────────────────────────────────
                # Parse user_text for schedule intent. If found, create
                # the cron job and append a 📌 marker to the response so
                # the user sees the reminder was set.
                #
                # This replaces the old "agent uses cron_manage tool"
                # loop which caused infinite recursion: agent re-scheduled
                # itself on every cron fire, producing "5 напомни про
                # чайник за 15 минут" spam. By moving parsing to a
                # deterministic regex on user_text only, there's no
                # tool, no LLM in the loop, no recursion possible.
                try:
                    from ..cron.intent_parser import (
                        parse_schedule_intent,
                        create_cron_from_intent,
                        build_intent_marker,
                    )
                    spec = parse_schedule_intent(user_message)
                    if spec is not None:
                        job_id = create_cron_from_intent(
                            spec, created_by="auto-intent-parser",
                        )
                        if job_id:
                            marker = build_intent_marker(spec, job_id=job_id)
                            # Append marker ONLY to the live SSE stream,
                            # not to history — history should reflect
                            # what the LLM said, not system-injected
                            # appendages.
                            await chat_task.queue.put(
                                f'data: {{"type": "chunk", "content": '
                                f'{json.dumps(marker, ensure_ascii=False)}}}\n\n'
                            )
                except Exception as parse_err:
                    logger.warning("auto-schedule hook failed: %s", parse_err)

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

    # 3. SSE generator reads from queue (real-time streaming).
    # Audit fix BUG 3.2: poll for client disconnect so we can abort
    # the background chat task if the user closes the window
    # mid-generation — otherwise we'd keep charging tokens on a
    # response nobody is reading.
    async def _sse_from_queue():
        """Read chunks from background task queue, abort if client disconnects."""
        while True:
            # Race the queue against a short sleep so we can detect
            # client disconnect promptly without blocking forever.
            queue_task = asyncio.create_task(chat_task.queue.get())
            disconnect_task = asyncio.create_task(asyncio.sleep(0.5))
            done, pending = await asyncio.wait(
                {queue_task, disconnect_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
            if disconnect_task in done and await request.is_disconnected():
                # Client gave up — cancel the background LLM call
                # so we stop charging tokens.
                chat_task.task.cancel()
                task_manager.cleanup(task_id)
                return
            if queue_task in done:
                chunk = queue_task.result()
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

    # ── Auto-schedule hook ─────────────────────────────────
    # Same intent parser as the streaming endpoint — parses user_text,
    # creates a cron if a schedule intent is detected, appends a 📌
    # marker to the response so the user sees the reminder was set.
    schedule_marker = ""
    if req.agent_slug and req.channel_id:
        try:
            from ..cron.intent_parser import (
                parse_schedule_intent,
                create_cron_from_intent,
                build_intent_marker,
            )
            spec = parse_schedule_intent(req.message)
            if spec is not None:
                job_id = create_cron_from_intent(
                    spec, created_by="auto-intent-parser",
                )
                if job_id:
                    schedule_marker = "\n\n" + build_intent_marker(spec, job_id=job_id)
        except Exception as parse_err:
            logger.warning("auto-schedule hook (complete) failed: %s", parse_err)

    result = {"content": content + schedule_marker, "model": model}
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
