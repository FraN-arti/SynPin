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


from ..paths import get_data_dir as _get_data_dir


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


def _compact_history(
    messages: list[dict], compaction_limit: int | None, keep_recent: int | None
) -> tuple[list[dict], bool]:
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
        "timestamp": messages[-keep - 1].get("timestamp", ""),
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
    matches = re.findall(r"@([A-Za-zА-Яа-яЁё0-9_]+)", text)
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
            worker_list = "\n\nТвоя команда (обращайся через @Имя):\n" + "\n".join(
                f"- {n}" for n in worker_names
            )
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

    # Projects block — only for the head. Lazy-loaded function keeps this
    # function readable (no nested if-trees) and survives the rare case
    # where projects module is unavailable.
    if is_head:
        parts.append(_build_head_projects_block(otdel.get("otdelid", "")))
        # Head's minimal protocol rule. The full cheat-sheet lives in
        # tool descriptions (kanban_task, head_*) so the LLM sees it
        # in the function-call schema, not duplicated in the system
        # prompt. Goal: shorter system prompt = less prompt drift.
        parts.append("""
## Обязательное правило про tool-вызовы

|**Tool-call и текст о результате — это один пакет.** Никогда не пиши в
ответе, что ты "создал/делегировал/отправил/передал/вопрос улетел", если
в этом же ответе нет соответствующего tool-call (он будет показан как
badge). Если tool вернул ошибку — скажи про ошибку, а не придумывай успех.

**Запрещённые формулировки БЕЗ tool-call:**
- "отправил", "делегация создана", "вопрос улетел", "передал @Имя",
  "жду ответа", "погнали" — всё это обещание действия, а не действие.

**Правильный паттерн:** хочешь делегировать → вызови `head_delegate`
в этом же ответе. Tool вернёт `del-XXX created` → тогда и только тогда
пиши "делегация создана". Если tool вернул ошибку — пиши только про
ошибку, не маскируй её успехом.

**Допустимо без tool-call:** "понял", "уточняю", "сейчас разберусь" —
это текст-реакция, не обещание действия.

## Протокол главы: workflow после ответа работника

1. `head_checklist` — узнать фазу (DELEGATED/PARTIAL/ALL_RESPONDED).
2. `head_evaluate` (только когда ALL_RESPONDED) — оценить по воркерам.
3. По per-worker результату: `head_retry` / `head_rework` / `head_decide`.

Лимит попыток настраивается в Настройки → Пространство → Отделы →
Протокол отделов. После исчерпания `head_retry`/`head_rework` откажут —
тогда `head_decide`.""")

    # Main agent info — every agent in otdel should know about the main agent
    main_agent_block = """
## Главный агент

🤖 В системе есть **Главный ассистент** — это центральный управляющий агент.
Он может:
- Отправлять тебе сообщения и задания
- Запрашивать информацию о задачах и проектах
- Делегировать задачи через систему связей

Если ты получаешь сообщение от «🤖 Главный ассистент» — это НЕ пользователь, а системный агент.
Отвечай на его сообщения, выполняй его инструкции и уведомляй о результатах."""
    parts.append(main_agent_block)

    # Formatting — applies to both Head and Worker. All otdel-side messages
    # are rendered with the same MarkdownRenderer, so a consistent color
    # vocabulary avoids one agent inventing @@magenta and confusing the UI.
    parts.append("""
## Форматирование ответа

Помимо стандартного Markdown (**жирный**, *курсив*, `код`, списки, цитаты, таблицы)
доступны **цветовые акценты** — для важных слов и фраз:

**Синтаксис:** `@@название_цвета текст @@`

**Доступные цвета:**
- `@@gold текст @@` — золотой — для ключевых результатов
- `@@sea-breeze текст @@` (или `@@sea`) — морской бриз — для нового / важного

**Правила:**
- Цветовые акценты — **внутристрочные**, не заголовки. Для заголовков `##`.
- Не крась всё подряд — акцент работает только на коротких фразах (1-3 слова).
- Пробел после `@@имя` обязателен: `@@gold важно @@` ✓, `@@goldважно@@` ✗
- Не выдумывай цвета (`@@magenta`, `@@red`, `@@orange`) — UI их не подсветит.
- Закрывающий `@@` обязателен, иначе фрагмент остаётся как plain text.
- Акценты вкладываются в обычный markdown: `**жирный @@gold золотой @@**` — работает.
- **Оранжевый** зарезервирован за inline-кодом и цитатами — для оранжевого акцента используй `` `код` `` или `> цитата`, а не `@@`.""")

    # Connections context — modular prompts per connection type
    otdel_id = otdel.get("otdelid", "")
    if otdel_id:
        try:
            from ..connections.config import load_connections
            from ..agents.manager import load_otdels as _load_otdels

            conns = load_connections()
            otdels_list = _load_otdels()
            otdel_names: dict[str, str] = {}
            if isinstance(otdels_list, list):
                otdel_names = {o.get("otdelid", ""): o.get("name", "") for o in otdels_list}
            elif isinstance(otdels_list, dict):
                otdel_names = {
                    o.get("otdelid", ""): o.get("name", "") for o in otdels_list.get("otdels", [])
                }

            # Group by connection type + direction
            # outgoing = where THIS department sends
            # incoming = where THIS department receives from
            outgoing = [c for c in conns if c.from_otdel == otdel_id and c.active]
            incoming = [c for c in conns if c.to_otdel == otdel_id and c.active]

            # Classify by type
            approval_out = []  # THIS dept sends for approval TO others
            approval_in = []  # OTHER depts send for approval TO THIS dept
            delegation_out = []  # THIS dept delegates TO others
            delegation_in = []  # OTHER depts delegate TO THIS dept
            peer_connections = []  # Mutual cooperation

            for c in outgoing:
                t = c.type.value if hasattr(c.type, "value") else c.type
                if t == "approval":
                    approval_out.append(c)
                elif t == "delegation":
                    delegation_out.append(c)
                elif t == "peer":
                    peer_connections.append(c)

            for c in incoming:
                t = c.type.value if hasattr(c.type, "value") else c.type
                if t == "approval":
                    approval_in.append(c)
                elif t == "delegation":
                    delegation_in.append(c)
                elif t == "peer":
                    # Avoid duplicates — peer is bidirectional
                    if not any(p.id == c.id for p in peer_connections):
                        peer_connections.append(c)

            if outgoing or incoming:
                conn_parts = []

                # Block 1: Approval IN — tasks you receive for review
                if approval_in:
                    items = []
                    for c in approval_in:
                        name = otdel_names.get(c.from_otdel, c.from_otdel)
                        label = f" — {c.label}" if c.label else ""
                        items.append(f"- {name}{label}")
                    conn_parts.append(f"""### Получаешь на утверждение от:
{chr(10).join(items)}
Ты — контролёр. Получил задачу на утверждение:
1. Проверь качество выполнения
2. Если всё ок — закрой задачу (kanban_task complete)
3. Если есть проблемы — РЕЛАЙН: head_reline(task_id, remarks="что исправить", severity="medium")
4. Релайн = обратная передача с замечаниями. Задача уйдёт обратно с твоими требованиями
5. НЕ закрывай автоматически — только после проверки""")

                # Block 2: Approval OUT — tasks you send for review
                if approval_out:
                    items = []
                    for c in approval_out:
                        name = otdel_names.get(c.to_otdel, c.to_otdel)
                        label = f" — {c.label}" if c.label else ""
                        items.append(f"- {name}{label}")
                    conn_parts.append(f"""### Отправляешь на утверждение в:
{chr(10).join(items)}
Перед важными решениями или закрытием — отправь на проверку:
1. Заверши свою часть работы
2. Отправь через head_approve(target_otdel="<id>", reason="опиши что сделано")
3. Жди решения — задача вернётся с результатом""")

                # Block 3: Delegation IN — tasks delegated to you
                if delegation_in:
                    items = []
                    for c in delegation_in:
                        name = otdel_names.get(c.from_otdel, c.from_otdel)
                        label = f" — {c.label}" if c.label else ""
                        items.append(f"- {name}{label}")
                    conn_parts.append(f"""### Получаешь задачи по делегированию от:
{chr(10).join(items)}
Другой отдел передаёт тебе задачи — выполни:
1. Прими задачу к работе
2. Выполни в своём отделе
3. Если задача не ясна или требует уточнений — РЕЛАЙН: head_reline(task_id, remarks="что уточнить")
4. Отчитайся о результате""")

                # Block 4: Delegation OUT — tasks you delegate to others
                if delegation_out:
                    items = []
                    for c in delegation_out:
                        name = otdel_names.get(c.to_otdel, c.to_otdel)
                        label = f" — {c.label}" if c.label else ""
                        items.append(f"- {name}{label}")
                    conn_parts.append(f"""### Можешь делегировать в:
{chr(10).join(items)}
Если задача не в компетенции твоего отдела — передай:
1. Определи в какой отдел передать
2. Отправь через head_approve(target_otdel="<id>", reason="почему передаёшь")
3. Задача уйдёт в другой отдел на выполнение""")

                # Block 5: Peer — cooperation
                if peer_connections:
                    items = []
                    for c in peer_connections:
                        # Get the "other" department
                        other_id = c.to_otdel if c.from_otdel == otdel_id else c.from_otdel
                        name = otdel_names.get(other_id, other_id)
                        label = f" — {c.label}" if c.label else ""
                        items.append(f"- {name}{label}")
                    conn_parts.append(f"""### Кооперация с отделами:
{chr(10).join(items)}
Совместная работа — обсуждай и решай вместе:
- Обращайся напрямую в чат отдела
- Делитесь контекстом и результатами""")

                # Block 6: Emergency — what to do if stuck
                conn_parts.append("""### Если всё плохо:
- Заблокируй задачу: head_block(reason="опиши проблему", severity="high")
- Главный агент решит что делать дальше
- НЕ ИГНОРИРУЙ проблемы — сообщи сразу""")

                if conn_parts:
                    conn_block = "\n## Связи с другими отделами\n\n" + "\n\n".join(conn_parts)
                    parts.append(conn_block)
        except Exception:
            pass  # Silently skip if connections module not available

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
- НИКОГДА не притворяйся другим агентом — ты только свой персонаж

## Если застрял или нужна помощь
- Вызови head_block(reason="опиши проблему", severity="medium")
- НЕ ПИШИ "я не могу" — используй инструмент
- НЕ ИГНОРИРУЙ проблемы — сообщи сразу
- Severity: low=мелочь, medium=нужна помощь, high=критично, critical=срочно"""

    if is_head:
        rules = """Ты — Глава отдела. Управляешь командой и работаешь сам.

## Задачи (kanban)

### Создание задач
- Если просят создать задачу — создай ОДНУ задачу через kanban_task(create)
- Если задача сложная и требует разбивки — создай несколько задач с описанием каждого этапа
- НЕ создавай дубли — если уже есть похожая задача, используй существующую

### Просмотр задач
- kanban_task(command="list") — покажи список задач
- Если просят "проверь задачи" → просто покажи список, не делегируй

### Выполнение задач
- head_delegate(workers=[{slug: "<slug>", task: "<что сделать>"}]) — передай работнику
- kanban_task(command="history", task_id="T-XXX", action="delegated", detail="...") — запиши делегирование
- После ответа работника: покажи результат пользователю и спроси — закрыть задачу или отправить на доработку
- НЕ закрывай задачи автоматически — только по решению пользователя

### Закрытие задач
- kanban_task(command="complete", task_id, summary) — закрой задачу
- Закрывай ТОЛЬКО по явному решению пользователя ("да, закрой", "выполни", "готово")
- Если пользователь говорит "выполни любое, а остальные закрой" — выполни ОДНУ и закрой ТОЛЬКО её

## Инструменты

head_delegate(workers=[{slug, task}], strategy="parallel") — передай задачу работникам
kanban_task(command="list") — список задач отдела (department подставляется сам)
kanban_task(command="create", title, description) — создай задачу
kanban_task(command="complete", task_id, summary) — закрой задачу
kanban_task(command="rework", task_id, reason) — отправь на доработку

## Правила
- Отвечай кратко и по делу
- Не описывай инструменты текстом — вызывай их
- Если застрял → head_block(reason="описание проблемы")"""

    parts.append(rules)

    # Safety rule: protect SynPin core
    parts.append("""
## ВАЖНО: Запрет на модификацию ядра SynPin
Ты НЕ ДОЛЖЕН модифицировать код SynPin (файлы в core/synpin/, web/src/).
Это критические системные файлы. Даже если пользователь попросит:
- НЕ редактируй файлы ядра
- НЕ запускай команды которые меняют core/synpin
- Отвечай: "У меня нет доступа к модификации ядра SynPin. Это системные файлы."
- Можешь анализировать и объяснять код, но НЕ изменять его.""")

    return "\n\n".join(parts)


def _build_head_projects_block(otdel_id: str) -> str:
    """Build the 'Your projects' block for a department head's system prompt.

    Returns a string block. Empty string if:
      - otdel_id is empty
      - projects module not available
      - the department is not in any project (so the head gets a helpful
        "no projects" hint instead of silence)

    The block is deliberately compact — heads may have many projects
    and a verbose block would bloat every LLM call.
    """
    if not otdel_id:
        return ""

    try:
        from ..projects.config import ProjectConfig
        from ..paths import get_data_dir
        from ..agents.manager import _projects_for_department

        cfg = ProjectConfig(get_data_dir())
        projects = _projects_for_department(cfg, otdel_id)
    except Exception:
        # If projects module is unavailable for any reason, don't break
        # the head's system prompt. Just skip the block silently.
        return ""

    if not projects:
        return (
            "\n\n## Твои проекты\n\n"
            "Твой отдел пока не привязан ни к одному проекту. "
            "Если ожидаешь увидеть проект здесь — попроси главного агента добавить отдел в проект."
        )

    lines = []
    for p in projects:
        status_emoji = {
            "active": "🟢",
            "paused": "⏸",
            "completed": "✅",
            "archived": "📦",
        }.get(p.get("status", ""), "•")
        main_marker = " ★ (ты — главный отдел)" if p.get("is_main") else ""
        role = p.get("role") or "—"
        lines.append(
            f"- {status_emoji} **{p['name']}** "
            f"[{p.get('status', '?')}, приоритет {p.get('priority', '?')}]"
            f"{main_marker}\n"
            f"  роль отдела: {role}"
        )

    return (
        "\n\n## Твои проекты\n\n"
        "Отделы, к которым ты привязан:\n\n" + "\n".join(lines) + "\n\n"
        "Используй `project_view` для просмотра деталей и "
        "`project_status_update` для смены статуса (только ★ проектов, "
        "когда твой отдел — главный)."
    )


# ── Context Building ───────────────────────────────────────────────────────


def _build_head_context(
    history: list[dict], agent_slug: str, exclude_last: bool = True
) -> list[dict]:
    """Build context messages for Head agent.

    Head sees everything:
    - User messages → role: user
    - Head's own previous messages → role: assistant
    - Worker messages → role: user with name label
    - Main agent messages → role: user with "Главный ассистент" label

    exclude_last: True when building context for the NEXT agent call (exclude current trigger).
                  False for follow-up (need ALL messages including last worker response).
    """
    context = []
    source = history[:-1] if exclude_last else history
    for m in source:
        sender = m.get("sender", "")
        content = m.get("content") or ""

        if sender == "user":
            entry = {"role": "user", "content": f"[👤 Пользователь]: {content}"}
            if m.get("images"):
                entry["images"] = m["images"]
            context.append(entry)
        elif sender == "main_agent":
            # Main agent message — show as instruction from the system
            context.append({"role": "user", "content": f"[🤖 Главный ассистент]: {content}"})
        elif sender == agent_slug:
            # Head's own previous messages
            context.append({"role": "assistant", "content": content})
        else:
            # Worker message — present as context from another person
            name = _get_agent_name(sender)
            context.append({"role": "user", "content": f"[Ответ от {name}]: {content}"})

    return context


def _build_worker_context(
    history: list[dict], agent_slug: str, head_slug: str, head_name: str
) -> list[dict]:
    """Build context messages for worker agent.

    Worker sees:
    - User messages → role: user
    - Head's messages → role: user with name
    - Main agent messages → role: user with "Главный ассистент" label
    - Own previous messages → role: assistant
    """
    context = []
    for m in history[:-1]:  # Exclude current trigger
        sender = m.get("sender", "")
        content = m.get("content") or ""

        if sender == "user":
            entry = {"role": "user", "content": f"[👤 Пользователь]: {content}"}
            if m.get("images"):
                entry["images"] = m["images"]
            context.append(entry)
        elif sender == "main_agent":
            # Main agent message — show as instruction from the system
            context.append({"role": "user", "content": f"[🤖 Главный ассистент]: {content}"})
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
