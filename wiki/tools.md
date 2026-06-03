# 🛠 Инструменты агентов

Инструменты — **что агент может делать** с системой. Не все агенты имеют все инструменты.

---

## Архитектура

```
core/tools/
├── base.py          # базовые инструменты (все агенты)
├── filesystem.py    # чтение/запись/поиск файлов
├── terminal.py      # выполнение команд
├── web.py           # поиск + парсинг (опционально)
└── registry.py      # реестр доступных инструментов
```

Каждый инструмент — функция с описанием, параметрами и результатом.

---

## Доступные инструменты

### Базовые (все агенты)

| Инструмент | Что делает | Пример |
|---|---|---|
| `read_file` | Читает файл с номерами строк | `read_file("wiki/agents.md")` |
| `search_files` | Ищет по имени или содержимому | `search_files("auth", target="content")` |
| `list_dir` | Список файлов в директории | `list_dir("wiki/")` |

### Для разработчиков

| Инструмент | Что делает | Пример |
|---|---|---|
| `write_file` | Создаёт/перезаписывает файл | `write_file("new.py", "print('hi')")` |
| `patch_file` | Правит часть файла (find & replace) | `patch_file("app.py", "old", "new")` |
| `run_command` | Выполняет shell-команду | `run_command("git status")` |

### Для исследователей

| Инструмент | Что делает | Пример |
|---|---|---|
| `web_search` | Поиск в интернете | `web_search("FastAPI auth best practices")` |
| `web_extract` | Парсит страницу в markdown | `web_extract(["https://example.com"])` |

### Для всех (опционально)

| Инструмент | Что делает | Пример |
|---|---|---|
| `read_image` | Загружает изображение для анализа | `read_image("screenshot.png")` |
| `run_python` | Выполняет Python-код | `run_python("import json; ...")` |

---

## Конфигурация инструментов

### tools.yaml (глобальный)

```yaml
# ~/.synpin/config/tools.yaml

# Определения всех доступных инструментов
definitions:
  read_file:
    description: "Read a text file with line numbers"
    parameters:
      path: "Path to the file"
      offset: "Start line (default: 1)"
      limit: "Max lines (default: 500)"

  search_files:
    description: "Search file contents or find files by name"
    parameters:
      pattern: "Regex or glob pattern"
      target: "content or files"
      path: "Directory to search (default: .)"

  write_file:
    description: "Write content to a file (overwrites)"
    parameters:
      path: "File path"
      content: "Complete file content"

  patch_file:
    description: "Targeted find-and-replace in a file"
    parameters:
      path: "File path"
      old_string: "Text to find"
      new_string: "Replacement text"

  run_command:
    description: "Execute a shell command"
    parameters:
      command: "Shell command"
      timeout: "Max seconds (default: 180)"
      workdir: "Working directory"

  web_search:
    description: "Search the web"
    parameters:
      query: "Search query"
      limit: "Max results (default: 5)"

  web_extract:
    description: "Extract content from URLs"
    parameters:
      urls: "List of URLs (max 5)"
```

### Инструменты в agent.yaml

```yaml
# agents/architect/agent.yaml

name: "Архитектор"

tools:
  enabled:
    - read_file
    - search_files
    - list_dir
    - write_file        # для документации
    - patch_file        # для правок конфигов
  disabled:
    - run_command       # не нужно архитектору
    - web_search        # не нужно
    - web_extract

  limits:
    max_file_size: "100KB"     # не читать огромные файлы
    max_search_results: 50     # лимит результатов поиска
    command_timeout: 60        # таймаут команд (если разрешены)
    allowed_dirs:              # доступ только к этим директориям
      - "~/.synpin/data/"
      - "~/.synpin/config/"
      - "~/.synpin/wiki/"
```

### Инструменты по ролям (дефолты)

```yaml
# ~/.synpin/config/tools.yaml

role_defaults:
  worker:
    enabled:
      - read_file
      - search_files
      - list_dir
    disabled:
      - run_command
      - web_search

  developer:
    enabled:
      - read_file
      - search_files
      - list_dir
      - write_file
      - patch_file
      - run_command
    disabled:
      - web_search

  researcher:
    enabled:
      - read_file
      - search_files
      - list_dir
      - web_search
      - web_extract
    disabled:
      - run_command
      - write_file

  head:
    enabled:
      - read_file
      - search_files
      - list_dir
      - write_file
      - patch_file
    disabled:
      - run_command
```

---

## Безопасность

### Песочница

Инструменты работают в **песочнице**:

| Защита | Что делает |
|---|---|
| **allowed_dirs** | Агент видит только разрешённые директории |
| **max_file_size** | Не читает файлы больше лимита |
| **command_timeout** | Команды не зависают навсегда |
| **blocked_commands** | Запрещённые команды (rm -rf, sudo, и т.д.) |
| **read-only mode** | Агент может только читать, не писать |

### Запрещённые команды

```yaml
blocked_commands:
  - "rm -rf"
  - "sudo"
  - "curl | bash"
  - "wget | sh"
  - "chmod 777"
  - "dd if="
  - "mkfs"
  - "format"
```

---

## Как агент использует инструменты

### Промпт с инструментами

```
Доступные инструменты:

1. read_file(path, offset=1, limit=500)
   → Читает файл с номерами строк

2. search_files(pattern, target="content", path=".")
   → Ищет по содержимому или имени

3. write_file(path, content)
   → Создаёт/перезаписывает файл

4. patch_file(path, old_string, new_string)
   → Правит часть файла

Ограничения:
- Только директории: ~/.synpin/data/, ~/.synpin/config/
- Максимум файл: 100KB
- Запрещено: rm, sudo, curl|bash

Используй инструменты когда нужно. Не используй когда можешь ответить напрямую.
```

### Пример использования

```
User: "Найди все файлы где упоминается CORS"

Agent: search_files("CORS", target="content", path="~/.synpin/")

Result: 
  wiki/channels-hierarchy.md:108| Не забыл про CORS middleware
  core/main.py:45| app.add_middleware(CORSMiddleware, ...)

Agent: Нашёл 2 файла:
  - wiki/channels-hierarchy.md (упоминание в документации)
  - core/main.py (реализация middleware)
```

---

## Связь с скиллами

Скиллы могут **требовать определённые инструменты**:

```yaml
# SKILL.md: react-component

required_tools:
  - read_file
  - write_file
  - patch_file

# Если у агента нет этих инструментов — скилл не работает
```

---

## Связь с другими документами

- [Агенты](agents.md) — личность, роли, директивы
- [Конфигурация](configuration.md) — общие настройки системы
- [Память](memory-sessions.md) — как агент хранит знания

---

*Инструменты — это руки агента. Дай правильные — сделает всё. Дай лишние — сломает.*
