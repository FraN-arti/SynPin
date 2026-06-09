# 🛠 Инструменты агентов

Инструменты — **что агент может делать** с системой. Реализовано 13 инструментов из запланированных.

---

## Архитектура

```
core/synpin/tools/
├── base.py              # базовые типы (ToolHandler, ToolResult, make_error)
├── registry.py          # реестр — загружает tools.yaml, резолвит handlers
├── security.py          # security sandbox (allowed_directories из security.yaml)
│
├── # Базовые инструменты (8 штук)
├── terminal.py          # async shell exec
├── file_read.py         # чтение файлов с номерами строк
├── file_write.py        # атомарная запись файлов
├── search_files.py      # ripgrep + Python fallback
├── web_search.py        # DuckDuckGo поиск
├── code_exec.py         # sandboxed Python exec
├── memory_read.py       # чтение MEMORY/USER/facts
├── memory_write.py      # add/remove/replace entries
│
└── # Head Protocol — инструменты управляющего отдела (5 штук)
    head_delegate.py     # делегирование задач воркерам
    head_await.py        # ожидание ответов от воркеров
    head_evaluate.py     # quality gate — оценка результатов
    head_retry.py        # ретрай упавшего воркера
    head_decide.py       # стратегическое решение
```

Каждый инструмент — async функция с описанием, параметрами и результатом.

---

## Базовые инструменты (8)

### Файловые операции

| Инструмент | Что делает | Параметры |
|---|---|---|
| `file_read` | Читает файл с номерами строк | `path`, `offset=1`, `limit=500` |
| `file_write` | Создаёт/перезаписывает файл | `path`, `content` |
| `search_files` | Ищет по имени или содержимому | `pattern`, `target="content"`, `path="."` |

### Код и терминал

| Инструмент | Что делает | Параметры |
|---|---|---|
| `terminal` | Выполняет shell-команду | `command`, `timeout=180`, `workdir` |
| `code_exec` | Выполняет Python-код в sandbox | `code`, `timeout=30` |

### Веб

| Инструмент | Что делает | Параметры |
|---|---|---|
| `web_search` | Поиск в интернете (DuckDuckGo) | `query`, `limit=5` |

### Память

| Инструмент | Что делает | Параметры |
|---|---|---|
| `memory_read` | Читает MEMORY/USER/facts | `target`, `filename` (опционально) |
| `memory_write` | Записывает в память | `action` (add/replace/remove), `target`, `content` |

---

## Head Protocol — инструменты управляющего (5)

**Head Protocol** — набор инструментов для Главы отдела, автоматически добавляемых в otdel-чате.

> ⚡ Все 5 инструментов **builtin** (встроены), используются только в контексте otdel-чата и **автоматически добавляются** к списку инструментов Главы.

### head_delegate

Структурированное делегирование задач воркерам.

```
Параметры:
  workers:    [{slug: str, task: str}]  — кто и что делает
  strategy:   "parallel" | "sequential" | "pipeline" (по умолчанию "parallel")
  context:    str — дополнительный контекст для воркеров
  timeout_ms: int (по умолчанию 120000)

Возвращает: {delegation_id, expected_workers, timeout_ms, guidance}
```

### head_await

Ожидание ответов от делегированных воркеров с таймаутом и фолбэком.

```
Параметры:
  delegation_id: str (опционально, берёт активный)
  timeout_ms:    int (по умолчанию 120000)

Возвращает: {status: "all_responded"|"timeout"|"partial", results: [...], missing: [...]}
```

### head_evaluate

Quality gate — проверяет, удовлетворяют ли результаты задаче.

```
Параметры:
  task_description: str — описание задачи
  criteria:         list[str] — критерии оценки (опционально)

Возвращает: {satisfied: bool, issues: [], suggestions: []}
```

### head_retry

Фолбэк при падении воркера — повторная отправка с контекстом ошибки.

```
Параметры:
  worker_slug:  str — какой воркер повторить
  error_context: str — что пошло не так
  attempt:      int (автоинкремент)

Возвращает: {retry_message: str, guidance: str, attempt: int}
```

### head_decide

Стратегическое решение: продолжить, остановить, взять самому, эскалировать.

```
Параметры:
  situation: "continue" | "stop" | "takeover" | "escalate"
  reasoning: str — почему принято это решение
  context:   dict — дополнительный контекст

Возвращает: {action: str, reasoning: str, next_prompt: str}
```

### Как работает Head Protocol

```
1. Глава получает запрос от пользователя
2. Глава вызывает head_delegate(workers=[...], task="...")
3. Глава вызывает head_await() — ждёт ответов воркеров
4. Если воркер упал → head_retry(worker_slug, error_context)
5. После ответов → head_evaluate() — проверяет качество
6. head_decide("continue"|"stop"|"takeover"|"escalate")
7. Глава формирует итог для пользователя
```

---

## Реестр инструментов

Инструменты загружаются из `~/.synpin/config/tools.yaml`. Реестр динамически импортирует handlers базовых инструментов:

```python
# core/synpin/tools/registry.py
_MODULE_MAP = {
    "terminal": ".terminal",
    "file_read": ".file_read",
    "file_write": ".file_write",
    "search_files": ".search_files",
    "web_search": ".web_search",
    "code_exec": ".code_exec",
    "memory_read": ".memory_read",
    "memory_write": ".memory_write",
}
```

> **Примечание:** Head Protocol инструменты (head_delegate, head_await и т.д.) **не в MODULE_MAP** — они импортируются напрямую в ws_router.py и otdel_chat_router.py при обработке otdel-чата.

### tools.yaml — реестр всех инструментов

```yaml
# ~/.synpin/config/tools.yaml
tools:
  # ─── Файловые операции ──────────────────────────
  file_read:
    display: "Чтение файлов"
    category: files
    implemented: true
  file_write:
    display: "Запись файлов"
    category: files
    implemented: true
  search_files:
    display: "Поиск по файлам"
    category: files
    implemented: true

  # ─── Код и терминал ─────────────────────────────
  terminal:
    display: "Терминал"
    category: code
    implemented: true
  code_exec:
    display: "Запуск кода"
    category: code
    implemented: true

  # ─── Веб ────────────────────────────────────────
  web_search:
    display: "Поиск в интернете"
    category: web
    implemented: true

  # ─── Память ─────────────────────────────────────
  memory_read:
    display: "Чтение памяти"
    category: memory
    implemented: true
    builtin: true
  memory_write:
    display: "Запись в память"
    category: memory
    implemented: true
    builtin: true

  # ─── Head Protocol (builtin, otdel-only) ────────
  head_delegate:
    display: "Делегирование Главы"
    category: head_protocol
    implemented: true
    builtin: true
  head_await:
    display: "Ожидание ответов"
    category: head_protocol
    implemented: true
    builtin: true
  head_evaluate:
    display: "Оценка результатов"
    category: head_protocol
    implemented: true
    builtin: true
  head_retry:
    display: "Ретрай воркера"
    category: head_protocol
    implemented: true
    builtin: true
  head_decide:
    display: "Стратегическое решение"
    category: head_protocol
    implemented: true
    builtin: true
```

### Группировка для UI

```yaml
categories:
  files: "Файлы"
  code: "Код и терминал"
  web: "Веб"
  memory: "Память"
  communication: "Коммуникация"
  tasks: "Задачи"
  skills: "Скиллы"
  head_protocol: "Протокол Главы"
```

---

## Безопасность

### Песочница (Security Sandbox)

Инструменты работают в **песочнице**, настраиваемой через `security.yaml`:

| Защита | Что делает | Конфигурация |
|---|---|---|
| **allowed_directories** | Файловые операции только в разрешённых папках | `security.yaml → security.allowed_directories` |
| **command_timeout** | Команды не зависают навсегда (30s для shell) | `tools.yaml → tools.terminal.timeout` |
| **file_read limits** | Не читает файлы больше 1MB | `tools.yaml → tools.file_read.max_size` |
| **code_exec sandbox** | Python exec в изолированном контексте | `tools.yaml → tools.code_exec.timeout` |

### security.yaml

```yaml
# core/synpin/config/security.yaml
# Все файловые инструменты (read, write, search, terminal cwd) ограничены этими директориями
security:
  allowed_directories:
    - "D:\\synpin"
    # - "C:\\Projects"
    # - "C:\\Games\\l2client"
```

---

## Как агент использует инструменты

### Промпт с инструментами

```
Доступные инструменты:

1. file_read(path, offset=1, limit=500)
   → Читает файл с номерами строк

2. search_files(pattern, target="content", path=".")
   → Ищет по содержимому или имени

3. file_write(path, content)
   → Создаёт/перезаписывает файл

4. terminal(command, timeout=180)
   → Выполняет shell-команду

Ограничения:
- Только директории из security.yaml (allowed_directories)
- Максимум файл: 1MB
- Запрещено: rm, sudo, curl|bash

Используй инструменты когда нужно. Не используй когда можешь ответить напрямую.
```

---

## Нереализованные инструменты (планируются)

| Инструмент | Что делает | Статус |
|---|---|---|
| `web_extract` | Извлечение контента с веб-страниц (парсинг HTML) | Фаза 2 |
| `browser` | Веб-браузер (Puppeteer/Playwright) | Фаза 3 |
| `vision` | Анализ изображений | Фаза 3 |
| `message_send` | Отправка сообщений в каналы | Фаза 3 |
| `agent_call` | Вызов другого агента | Фаза 3 |
| `task_create` | Создание задачи на канбан-доске | Фаза 6 |
| `task_update` | Обновление задач | Фаза 6 |
| `skill_use` | Использование навыков | Фаза 3 |

---

## Связь с другими документами

- [Агенты](agents.md) — личность, роли, директивы
- [Отделы](otdels.md) — структура департаментов и отделов, Head Protocol
- [Конфигурация](configuration.md) — общие настройки системы
- [Память](memory-sessions.md) — как агент хранит знания

---

*Инструменты — это руки агента. Дай правильные — сделает всё. Дай лишние — сломает.*
