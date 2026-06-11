"""Otdel Chat Helpers — shared logic for department chat.

Pure functions for:
- History storage (load/save to JSON)
- @mention parsing
- System prompt building
- Context building for head/worker agents

These helpers are transport-agnostic (used by both WebSocket handler and HTTP endpoints).
"""
import json
import re
import logging
import asyncio
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# Shared data dir
_DATA_DIR: Path | None = None
MAX_HISTORY_MESSAGES = 200
DEFAULT_COMPACTION_LIMIT = 100
DEFAULT_KEEP_RECENT = 10

# Per-otdel asyncio Lock to prevent race conditions on chat.json
_otdel_locks: dict[str, asyncio.Lock] = {}


def _get_lock(otdel_id: str) -> asyncio.Lock:
    """Get or create an asyncio.Lock for the given otdel."""
    if otdel_id not in _otdel_locks:
        _otdel_locks[otdel_id] = asyncio.Lock()
    return _otdel_locks[otdel_id]


def _get_data_dir() -> Path:
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
    _DATA_DIR = candidates[0]
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _DATA_DIR


# ── History Storage ────────────────────────────────────────────────────────

def _get_otdel_chat_path(otdel_id: str) -> Path:
    data_dir = _get_data_dir()
    return data_dir / "otdels" / otdel_id / "chat.json"


def _load_history(otdel_id: str) -> list[dict]:
    path = _get_otdel_chat_path(otdel_id)
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load otdel chat history for %s: %s", otdel_id, e)
        return []


def _save_history(otdel_id: str, messages: list[dict]) -> dict:
    """Save history with optional compaction. Returns stats dict."""
    path = _get_otdel_chat_path(otdel_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if compaction is configured for this otdel
    try:
        from ..agents.manager import get_otdel
        otdel = get_otdel(otdel_id)
        compaction_limit = otdel.get("compaction_limit") if otdel else None
        keep_recent = otdel.get("keep_recent") if otdel else None
    except Exception:
        compaction_limit = None
        keep_recent = None
    
    # Compact if needed
    trimmed, was_compacted = _compact_history(messages, compaction_limit, keep_recent)
    if was_compacted:
        logger.info("Compacted otdel %s: %d → %d messages", otdel_id, len(messages), len(trimmed))
    
    # Hard cap as final safety
    trimmed = trimmed[-MAX_HISTORY_MESSAGES:]
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=1)
    
    return {"was_compacted": was_compacted, "before": len(messages), "after": len(trimmed)}


def _compact_history(messages: list[dict], compaction_limit: int | None, keep_recent: int | None) -> tuple[list[dict], bool]:
    """Compact history if it exceeds the limit.
    
    Strategy: keep first message + last keep_recent messages.
    Middle messages are replaced with a summary marker.
    
    Returns (compacted_messages, was_compacted).
    """
    limit = compaction_limit or DEFAULT_COMPACTION_LIMIT
    keep = keep_recent or DEFAULT_KEEP_RECENT
    
    if len(messages) <= limit:
        return messages, False
    
    # Keep first message for context
    first = messages[0]
    # Keep last N messages
    recent = messages[-keep:]
    # Count removed
    removed_count = len(messages) - 1 - keep  # -1 for first message
    
    # Create summary marker
    summary = {
        "id": f"compaction-{uuid.uuid4().hex[:8]}",
        "role": "system",
        "sender": "system",
        "sender_name": "Система",
        "content": f"[Компакция: удалено {removed_count} сообщений. Контекст сжат для экономии токенов.]",
        "is_head": False,
        "timestamp": messages[-keep-1].get("timestamp", ""),
        "compaction": True,
    }
    
    compacted = [first, summary] + recent
    return compacted, True


async def _locked_load_history(otdel_id: str) -> list[dict]:
    """Load history with lock — prevents reading stale data during concurrent writes."""
    lock = _get_lock(otdel_id)
    async with lock:
        return _load_history(otdel_id)


async def _locked_save_history(otdel_id: str, messages: list[dict]):
    """Save history with lock — prevents race condition between parallel workers."""
    lock = _get_lock(otdel_id)
    async with lock:
        _save_history(otdel_id, messages)


async def _locked_append_and_save(otdel_id: str, message: dict) -> list[dict]:
    """Atomically load → append → save under lock. Returns updated history."""
    lock = _get_lock(otdel_id)
    async with lock:
        history = _load_history(otdel_id)
        history.append(message)
        _save_history(otdel_id, history)
        return history


# ── Agent Name Lookup ─────────────────────────────────────────────────────

def _get_agent_name(slug: str, head_slug: str = "", head_agent: dict | None = None) -> str:
    """Get display name for an agent by slug."""
    if slug == "user":
        return "Пользователь"
    if head_agent and slug == head_slug:
        return head_agent.get("name", slug)
    from ..agents.manager import get_agent
    agent = get_agent(slug)
    return agent.get("name", slug) if agent else slug


# ── @Mention Parsing ───────────────────────────────────────────────────────

def _parse_mentions(text: str) -> list[str]:
    """Extract @mentions from message text.

    Matches @Name (single word only — agent names are single words).
    Returns list of mentioned agent names (lowercased for matching).
    """
    matches = re.findall(r'@([A-Za-zА-Яа-яЁё0-9_]+)', text)
    return [m.strip().lower() for m in matches]


# ── System Prompt Building ─────────────────────────────────────────────────

def _build_otdel_system_prompt(otdel: dict, agent: dict, is_head: bool) -> str:
    """Build system prompt for an agent in otdel chat.

    Combines: agent's own prompt + otdel context + role in otdel.
    """
    parts = []

    # Agent's own system prompt (FIRST — this is their identity)
    own_prompt = agent.get("system_prompt", "")
    if own_prompt:
        parts.append(own_prompt)

    # Build workers list for Head
    worker_list = ""
    if is_head:
        worker_slugs = otdel.get("workers", [])
        head_slug = otdel.get("head", "")
        from ..agents.manager import get_agent
        worker_names = []
        for slug in worker_slugs:
            if slug == head_slug:
                continue
            w = get_agent(slug)
            if w:
                worker_names.append(f"@{w.get('name', slug)} ({slug})")
        if worker_names:
            worker_list = f"\n\nТвоя команда (обращайся через @Имя):\n" + "\n".join(f"- {n}" for n in worker_names)
        else:
            worker_list = "\n\nВ отделе пока нет работников."

    # Otdel context
    otdel_name = otdel.get("name", "")
    otdel_desc = otdel.get("description", "")
    role_label = "Глава отдела" if is_head else "Работник отдела"

    separator = "═" * 46
    otdel_block = f"""
{separator}
ОТДЕЛ: {otdel_name}
{otdel_desc}
Твоя роль: {role_label}{worker_list}
{separator}"""
    parts.append(otdel_block)

    # Chat rules
    rules = """
Правила общения в чате отдела:
- Ты работаешь в команде отдела
- Обращаются к тебе через @ТвоёИмя
- Если к тебе обратились — выполняй задачу
- Глава отдела управляет командой — подчиняйся его указаниям
- Не начинай работу самостоятельно пока тебя не попросят
- Отвечай кратко и по делу
- Если задача выполнена — отчитайся через @Глава
- НИКОГДА не притворяйся другим агентом — ты только свой персонаж"""

    if is_head:
        rules = """
Ты — Глава отдела. Твоя роль — УПРАВЛЯТЬ и РАБОТАТЬ.

## Кто ты
- Ты — менеджер команды, который САМ умеет работать
- Видишь ВСЕ сообщения в чате отдела
- ОБЯЗАТЕЛЬНО используй имена из списка выше — других агентов в чате нет
- НИКОГДА не притворяйся работником — ты Глава, отвечай от своего имени
- Не используй формат [slug] или [имя] — просто общайся

## Как ты работаешь

### ГЛАВНОЕ ПРАВИЛО
ЕСЛИ пользователь ЯВНО просит "отправь агентам", "делегируй", "пусть X напишет/сделает" —
ОБЯЗАТЕЛЬНО вызывай head_delegate. НЕ делай сам. НЕ игнорируй просьбу.

### Когда делай САМ (без делегации)
- Приветствия, прощания
- "Как дела?", "Кто ты?", "Что умеешь?"
- Вопросы только про тебя как Главу
- Стратегические решения по отделу

### Когда делегируй (через head_delegate)
- Любая генерация контента: "напиши", "составь", "сделай", "подготовь"
- Анализ, сравнения, обзоры, рецензии
- Вопросы о статусе/работе агентов
- **Любая просьба пользователя "отправь агентам" — ВСЕГДА head_delegate**

### 3. Внутренний workflow отдела
Ты можешь:
- Отправить результат работника НА ДОРАБОТКУ если он не устраивает
- ПЕРЕДЕЛИРОВАТЬ готовую задачу от одного агента ДРУГОМУ агенту внутри отдела
- Запросить РЕВЬЮ у одного агента по результатам другого

Пример цепочки:
1. Пользователь: "Напиши статью про AI"
2. Ты: head_delegate → Документалист пишет статью
3. Ты: получаешь статью → отправляешь Архитектору на ревью
4. Архитектор: "Есть ошибки, вот исправления"
5. Ты: отправляешь исправления Документалисту на доработку
6. Ты: получаешь финал → отдаёшь пользователю

## Инструменты

Для делегирования:
  head_delegate(workers=[{"slug": "<slug>", "task": "<задача>"}], strategy="parallel")
Работники автоматически ответят — НЕ вызывай head_await.

Для оценки качества:
  head_evaluate(worker_slug="<slug>", score=<1-10>, feedback="<комментарий>")

Для ретраи при ошибке:
  head_retry(worker_slug="<slug>", error_context="<что пошло не так>")

Для takeover (взять на себя):
  head_decide("takeover") — если после 3 попыток работник не справляется

## Когда делегировать
- Задачи требующие экспертизы работников
- Вопросы о статусе/работе агентов
- Сложные задачи, которые выиграют от совместной работы

## Когда отвечать сам
- Простые приветствия и быстрые ответы
- Вопросы, которые касаются только тебя как Главы
- Стратегические решения по отделу

## АБСОЛЮТНО ЗАПРЕЩЕНО
- Говорить "работники не могут ответить" / "работников нет" — если работники есть в списке, они МОГУТ ответить
- Отвечать за работников от своего имени (ты не знаешь что у них в голове)
- Игнорировать вопросы о работниках"""

    parts.append(rules)

    return "\n\n".join(parts)


# ── Context Building ───────────────────────────────────────────────────────

def _build_head_context(history: list[dict], agent_slug: str, exclude_last: bool = True) -> list[dict]:
    """Build context messages for Head agent.

    Head sees everything:
    - User messages → role: user
    - Head's own previous messages → role: assistant
    - Worker messages → role: user with name label

    exclude_last: True when building context for the NEXT agent call (exclude current trigger).
                  False for follow-up (need ALL messages including last worker response).
    """
    context = []
    source = history[:-1] if exclude_last else history
    for m in source:
        sender = m.get("sender", "")
        content = m.get("content", "")

        if sender == "user":
            context.append({"role": "user", "content": content})
        elif sender == agent_slug:
            # Head's own previous messages
            context.append({"role": "assistant", "content": content})
        else:
            # Worker message — present as context from another person
            name = _get_agent_name(sender)
            context.append({"role": "user", "content": f"[Ответ от {name}]: {content}"})

    return context


def _build_worker_context(history: list[dict], agent_slug: str, head_slug: str, head_name: str) -> list[dict]:
    """Build context messages for worker agent.

    Worker sees:
    - User messages → role: user
    - Head's messages → role: user with name
    - Own previous messages → role: assistant
    """
    context = []
    for m in history[:-1]:  # Exclude current trigger
        sender = m.get("sender", "")
        content = m.get("content", "")

        if sender == "user":
            context.append({"role": "user", "content": content})
        elif sender == agent_slug:
            # Worker's own previous messages
            context.append({"role": "assistant", "content": content})
        elif sender == head_slug:
            # Head's messages — present as instructions
            context.append({"role": "user", "content": f"[{head_name}]: {content}"})

    return context


__all__ = [
    "_load_history",
    "_save_history",
    "_locked_load_history",
    "_locked_save_history",
    "_locked_append_and_save",
    "_get_agent_name",
    "_parse_mentions",
    "_build_otdel_system_prompt",
    "_build_head_context",
    "_build_worker_context",
    "MAX_HISTORY_MESSAGES",
]
