# 🛠 Инструменты агентов

Инструменты — **что агент может делать** с системой. Реализовано 8 из 16 запланированных.

---

## Архитектура

```
core/synpin/tools/
├── base.py              # базовые типы (ToolHandler, ToolResult, make_error)
├── registry.py          # реестр — загружает tools.yaml, резолвит handlers
├── terminal.py          # async shell exec
├── file_read.py         # чтение файлов с номерами строк
├── file_write.py        # атомарная запись файлов
├── search_files.py      # ripgrep + Python fallback
├── web_search.py        # DuckDuckGo поиск
├── code_exec.py         # sandboxed Python exec
├── memory_read.py       # чтение MEMORY/USER/facts
└── memory_write.py      # add/remove/replace entries
```

Каждый инструмент — async функция с описанием, параметрами и результатом.

---

## Реализованные инструменты (8/16)

### Базовые (все агенты)

| Инструмент | Что делает | Параметры |
|---|---|---|
| `file_read` | Читает файл с номерами строк | `path`, `offset=1`, `limit=500` |
| `search_files` | Ищет по имени или содержимому | `pattern`, `target="content"`, `path="."` |

### Для разработчиков

| Инструмент | Что делает | Параметры |
|---|---|---|
| `file_write` | Создаёт/перезаписывает файл | `path`, `content` |
| `terminal` | Выполняет shell-команду | `command`, `timeout=180`, `workdir` |
| `code_exec` | Выполняет Python-код | `code`, `timeout=30` |

### Для исследователей

| Инструмент | Что делает | Параметры |
|---|---|---|
| `web_search` | Поиск в интернете (DuckDuckGo) | `query`, `limit=5` |

### Память

| Инструмент | Что делает | Параметры |
|---|---|---|
| `memory_read` | Читает MEMORY/USER/facts | `target`, `filename` (опционально) |
| `memory_write` | Записывает в память | `action` (add/replace/remove), `target`, `content` |

---

## Реестр инструментов

Инструменты загружаются из `~/.synpin/config/tools.yaml`. Реестр динамически импортирует handlers:

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

### Список инструментов агента

```yaml
# ~/.synpin/config/tools.yaml
tools:
  terminal:
    description: "Execute a shell command"
    parameters:
      command: "Shell command to execute"
      timeout: "Max seconds (default: 180)"
      workdir: "Working directory"
  
  file_read:
    description: "Read a text file with line numbers"
    parameters:
      path: "Path to the file"
      offset: "Start line (default: 1)"
      limit: "Max lines (default: 500)"
```

---

## Безопасность

### Песочница

Инструменты работают в **песочнице**:

| Защита | Что делает |
|---|---|
| **command_timeout** | Команды не зависают навсегда (30s для shell) |
| **file_read limits** | Не читает файлы больше 1MB |
| **code_exec sandbox** | Python exec в изолированном контексте |

### Реализованные ограничения

```yaml
# tools.yaml — пример
tools:
  terminal:
    timeout: 30
  file_read:
    max_size: 1048576  # 1MB
  code_exec:
    timeout: 30
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
- Только директории: ~/.synpin/data/, ~/.synpin/config/
- Максимум файл: 1MB
- Запрещено: rm, sudo, curl|bash

Используй инструменты когда нужно. Не используй когда можешь ответить напрямую.
```

### Пример использования

```
User: "Найди все файлы где упоминается CORS"

Agent: search_files("CORS", target="content", path="D:\\synpin\\")
Result: 
  wiki/channels-hierarchy.md:108| Не забыл про CORS middleware
  core/main.py:45| app.add_middleware(CORSMiddleware, ...)

Agent: Нашёл 2 файла:
  - wiki/channels-hierarchy.md (упоминание в документации)
  - core/main.py (реализация middleware)
```

---

## Нереализованные инструменты (планируются)

| Инструмент | Что делает | Статус |
|---|---|---|
| `browser` | Веб-браузер (Puppeteer/Playwright) | Фаза 3 |
| `vision` | Анализ изображений | Фаза 3 |
| `message_send` | Отправка сообщений в каналы | Фаза 3 |
| `agent_call` | Вызов другого агента | Фаза 3 |
| `task_create` | Управление задачами | Фаза 6 |
| `task_update` | Обновление задач | Фаза 6 |
| `skill_use` | Использование навыков | Фаза 3 |

---

## Связь с другими документами

- [Агенты](agents.md) — личность, роли, директивы
- [Конфигурация](configuration.md) — общие настройки системы
- [Память](memory-sessions.md) — как агент хранит знания

---

*Инструменты — это руки агента. Дай правильные — сделает всё. Дай лишние — сломает.*
