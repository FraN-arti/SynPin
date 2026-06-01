# ⚙️ Конфигурация

Все пользовательские настройки хранятся в `~/.synpin/config/`.

---

## Файлы

```
~/.synpin/config/
├── settings.yaml      # Общие настройки системы
├── providers.yaml     # LLM провайдеры
├── agents.yaml        # Агенты и роли
├── memory.yaml        # Настройки памяти
└── tools.yaml         # Инструменты и MCP
```

---

## settings.yaml

Общие настройки сервера, UI и логирования.

```yaml
server:
  host: "0.0.0.0"
  port: 2088

ui:
  language: "ru"       # ru / en
  theme: "dark"

logging:
  level: "info"        # debug / info / warning
  file: "~/.synpin/logs/synpin.log"
```

| Параметр | По умолчанию | Описание |
|---|---|---|
| `server.host` | `0.0.0.0` | Адрес прослушивания |
| `server.port` | `2088` | Порт API + Web UI |
| `ui.language` | `ru` | Язык интерфейса |
| `ui.theme` | `dark` | Тема UI |
| `logging.level` | `info` | Уровень логирования |
| `logging.file` | `~/.synpin/logs/synpin.log` | Путь к файлу логов |

---

## providers.yaml

Конфигурация LLM-провайдеров. Поддерживаются любые OpenAI-совместимые API.

```yaml
default: "lm-studio"

providers:
  lm-studio:
    type: "openai-compatible"
    base_url: "http://localhost:1234/v1"
    api_key: ""
    model: "default"
    max_tokens: 4096
    temperature: 0.7

  ollama:
    type: "openai-compatible"
    base_url: "http://localhost:11434/v1"
    model: "llama3"

  openai:
    type: "openai"
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-4o"
```

### Типы провайдеров

| Тип | Описание |
|---|---|
| `openai-compatible` | Любой OpenAI-совместимый API (LM Studio, Ollama, vLLM, localAI) |
| `openai` | OpenAI API (с auto-fallback) |
| `anthropic` | Anthropic Claude API |

### Переменные окружения

В конфигах можно использовать `${VAR_NAME}` — значение подставляется из окружения:

```yaml
providers:
  openai:
    api_key: "${OPENAI_API_KEY}"
```

---

## memory.yaml

Настройки системы памяти на базе ChromaDB.

```yaml
storage:
  type: "chromadb"
  path: "~/.synpin/data/chroma"

embedding:
  provider: "local"     # local / openai / ollama
  model: "all-MiniLM-L6-v2"
  dimension: 384

collections:
  per_agent: true       # отдельная коллекция на агента
  shared: true          # общая коллекция знаний
  max_items: 10000      # лимит на коллекцию

retention:
  errors: 90d           # хранить ошибки 90 дней
  decisions: 365d       # решения — год
  context: 30d          # контекст задач — месяц
```

### Хранилище

ChromaDB — встроенная векторная БД. Не требует отдельного сервера.

### Embedding-модели

| Провайдер | Модель | Размерность |
|---|---|---|
| `local` | `all-MiniLM-L6-v2` | 384 |
| `local` | `all-mpnet-base-v2` | 768 |
| `openai` | `text-embedding-3-small` | 1536 |
| `ollama` | `nomic-embed-text` | 768 |

### Коллекции

- **per-agent** — каждый агент хранит свои ошибки, решения, контекст
- **shared** — коллективная база знаний, доступная всем агентам

### Retention

Автоматическая очистка старых записей:
- `errors` — ошибки агентов
- `decisions` — принятые решения и их обоснования
- `context` — контекст выполненных задач

---

## agents.yaml

Конфигурация агентов, ролей и моделей.

```yaml
# Роли по умолчанию
roles:
  worker:
    model: "default"
    max_iterations: 10
    tools: ["search", "code", "files"]

  director:
    model: "default"
    max_iterations: 20
    tools: ["search", "code", "files", "delegate"]

# Агенты
agents:
  - name: "architect"
    role: "director"
    description: "Проектирует архитектуру и принимает стратегические решения"

  - name: "developer"
    role: "worker"
    description: "Пишет код и реализует задачи"

  - name: "reviewer"
    role: "worker"
    description: "Проверяет качество кода и даёт feedback"

  - name: "researcher"
    role: "worker"
    description: "Ищет информацию и анализирует данные"
```

---

## tools.yaml

Настройки инструментов и MCP-серверов.

```yaml
# Встроенные инструменты
builtins:
  search:
    enabled: true
    max_results: 5

  code:
    enabled: true
    sandbox: false       # true = изолированное выполнение
    timeout: 30          # секунд

  files:
    enabled: true
    allowed_dirs: ["~/projects"]

# MCP-серверы
mcp_servers:
  # filesystem:
  #   command: "npx"
  #   args: ["-y", "@modelcontextprotocol/server-filesystem", "~/projects"]

  # github:
  #   command: "npx"
  #   args: ["-y", "@modelcontextprotocol/server-github"]
  #   env:
  #     GITHUB_TOKEN: "${GITHUB_TOKEN}"
```

---

## Создание конфигов

При первом запуске `synpin setup` создаёт конфиги с дефолтными значениями:

```powershell
synpin setup
```

Или вручную — скопируй шаблон:

```powershell
mkdir ~/.synpin/config
# Создай файлы вручную или через synpin setup
```

---

*Конфиги перезагружаются автоматически при изменении файлов.*
