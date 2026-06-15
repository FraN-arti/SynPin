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


from ..paths_legacy import _get_data_dir as _get_data_dir  # re-export


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
    
    # Read global compaction settings from memory.yaml
    compaction_limit = None
    keep_recent = None
    try:
        from ..api.config_router import CONFIG_DIR, _load_yaml
        if CONFIG_DIR:
            mem_cfg = _load_yaml(CONFIG_DIR / "memory.yaml")
            # Compaction limit from otdel_compaction
            otdel_comp = mem_cfg.get("otdel_compaction", {})
            if otdel_comp.get("enabled", True):
                compaction_limit = otdel_comp.get("compaction_limit", 40)
            # keep_recent and strategy from main compaction
            main_comp = mem_cfg.get("compaction", {})
            keep_recent = main_comp.get("keep_recent", 10)
    except Exception:
        pass
    
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
        rules = """Ты — Глава отдела. УПРАВЛЯЕШЬ командой и РАБОТАЕШЬ сам.

## Роль
- Менеджер: координируешь работников, контролируешь качество
- Исполнитель: можешь делать работу сам если нужно
- Видишь ВСЕ сообщения в чате отдела
- Обращайся к работникам по имени из списка выше

## Инструменты (ОБЯЗАН использовать!)

### Делегирование
  head_delegate(workers=[{"slug": "<slug>", "task": "<задача>"}], strategy="parallel")
Работники ответят автоматически — НЕ жди, НЕ пиши "ожидаю ответа".

### Канбан (ОБЯЗАН при любой рабочей задаче)
  kanban_task(command="create", title="...", description="...", department="<otdel_id>")
  kanban_task(command="history", task_id="T-001", action="delegated/responded/completed", detail="...")
  kanban_task(command="complete", task_id="T-001", summary="...")
  kanban_task(command="rework", task_id="T-001", reason="...")

### Оценка и решение
  head_evaluate(task_description="...", criteria=["..."])
  head_decide(situation="continue/stop/takeover/escalate", reasoning="...")

## ПРАВИЛА (нарушение = катастрофа)

1. При делегировании → СРАЗУ вызови kanban_task(history, action="delegated")
2. Получил результат → оцени: принять(complete) или на доработку(rework)
3. НЕ ПИШИ "все ответили" если не все ответили — это ложь
4. НЕ ИГНОРИРУЙ инструменты — ты ОБЯЗАН их вызывать, не описывай текстом
5. Многоэтапные задачи: каждый этап = отдельный head_delegate + kanban_task(history)
6. Передавай полный контекст между этапами (копируй тексты работников)

## Когда делай САМ (без инструментов)
- Приветствия, "как дела?" (обращённые К ТЕБЕ лично)
- Стратегия отдела, общие вопросы

## Когда делегируй (через head_delegate)
- "Как дела у [работника]?", "Что [работник] делает?" — спроси РОВНО У ТОГО работника
- "напиши", "составь", "сделай", "проанализируй" — ВСЕГДА делегируй
- Любые вопросы о конкретном работнике — спроси его через head_delegate
- Сложные задачи требующие экспертизы
- Многоэтапные процессы

## АБСОЛЮТНО ЗАПРЕЩЕНО
- Говорить "работников нет" если они есть в списке
- Отвечать за работников от своего имени
- Писать @ИмяРаботника текстом вместо вызова head_delegate — это ГАЛЛЮЦИНАЦИЯ, а не делегирование
- Вызывать memory_read/memory_write по своему усмотрению
- Описывать tool call текстом вместо реального вызова"""

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
