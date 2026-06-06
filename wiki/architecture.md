# 🏗️ Архитектура SynPin

## Общая схема (реализовано)

```
┌─────────────────────────────────────────────────────┐
│                  Web UI (React 19)                  │
│  Chat · Settings · Agent Selection                  │
└───────────────────────┬─────────────────────────────┘
                        │ HTTP / SSE Stream (polling recovery)
                        ▼
┌─────────────────────────────────────────────────────┐
│              REST API (FastAPI)                     │
│  /api/agents  /api/chat/stream  /api/memory        │
│  Polling recovery: client reconnects → resume SSE   │
└───────────────────────┬─────────────────────────────┘
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
┌───────────────────┐       ┌───────────────────────┐
│  Task Manager     │       │     Tools Layer       │
│  (Queue + async)  │       │  terminal · file ·    │
│  ChatTask wraps   │       │  web · code · memory  │
│  asyncio.Task     │       │  (8 инструментов)     │
│  + asyncio.Queue  │       │                       │
│  for SSE chunks   │       │  Security Sandbox:    │
└─────────┬─────────┘       │  security.yaml        │
          │                 │  allowed_directories   │
          ▼                 └───────────┬───────────┘
┌─────────────────────────┐             │
│    Chat Router          │             │
│  (openai.py)            │             │
│  SSE streaming          │             │
│  Tool execution loop    │             │
│  Text fallback parser   │             │
│  (5 patterns: JSON,     │             │
│   tool_call, XML, etc)  │             │
└─────────┬───────────────┘             │
          │                             │
          ▼                             │
┌───────────────────────────────────────┤
│  Background Task System               │
│  asyncio.Task (survives disconnect)   │
│  Queue-based SSE streaming            │
│  History saved by background task     │
└─────────┬─────────────────────────────┘
          │
          ▼
┌─────────────────────────┐             │
│    Providers Layer      │             │
│  9router (hermes, sum)  │             │
│  Mistral (fallback)     │             │
│  Model combos:          │             │
│  provider/model format  │             │
│  (YAML registry + hot)  │             │
└─────────────┬───────────┘             │
              │                         │
              ▼                         │
┌───────────────────────────────────────┴─────────────┐
│              Memory System                          │
│  MemoryStore (MEMORY.md + USER.md)                  │
│  MemorySearch (FTS5 full-text)                      │
│  FrozenSnapshot (system prompt stability)           │
│  AgentState (bookmarks per channel)                 │
│  Facts (dated entries)                              │
│  Compaction (token-based, auto)                     │
│  Session auto-reset (daily/timer/time)              │
│  Memory + session context injection in prompt       │
└─────────────────────────────────────────────────────┘
```

## Слои

### 1. Web UI (`web/`)
React SPA — чат и настройки:
- **Chat UI** — стриминг, tool timeline, markdown, emoji
- **Settings** — провайдеры, агенты, роли/департаменты
- **Agent Selection** — выбор агента (SynPin + внешние)
- **Технологии:** React 19, Vite 6, TypeScript 5.7, Tailwind 4
- **Нет:** Zustand, TanStack Query (удалены)

### 2. REST API (`core/synpin/api/`)
FastAPI сервер — единая точка входа:
- `POST /api/chat/stream` — SSE стриминг чата
- `POST /api/chat/hermes/stream` — прокси для Hermes
- `GET/POST /api/agents` — CRUD агентов
- `GET/POST /api/memory` — управление памятью
- `GET /api/providers` — список провайдеров
- `GET /api/health` — health check

### 3. Task Manager (`core/synpin/chat/task_manager.py`)
Фоновый менеджер задач чата:
- **ChatTask** — оборачивает asyncio.Task + asyncio.Queue
- **SSE streaming** — клиент читает из Queue
- **Survives disconnect** — LLM работает даже после закрытия браузера
- **Polling recovery** — клиент переподключается и читает из Queue
- **History persistence** — история сохраняется фоновой задачей

### 4. Chat Router (`core/synpin/chat/`)
Основной цикл чата:
- **SSE streaming** через fetch + ReadableStream
- **Tool execution loop** (до 5 итераций)
- **Text fallback tool call parser** — 5 паттернов для моделей без native function calling:
  1. ```` ```tool_call ``` ```` блоки (старый формат)
  2. RAW JSON с `"name"` и `"params"` (nemotron-style)
  3. Nested JSON params (гибкий парсинг)
  4. `<function=name><parameter=path>...` (Llama.cpp / GGUF XML)
  5. `<arg_key=name>` формат (некоторые GGUF модели)
- **History persistence** (JSON per agent+channel)
- **Compaction** (token-based, configurable)
- **Memory + session context injection** в system prompt
- **Session auto-reset** (daily/timer/time + архивация)

### 5. Providers (`core/synpin/chat/providers/`)
LLM-провайдеры с combo-системой:
- **Model combos** — формат `provider/model` (например `9router/general-agent`)
- **9router** — hermes-agent, summarise-agent (локальный прокси)
- **Mistral** — fallback через Mistral API
- **Provider registry** — YAML конфигурация, hot-reload через ConfigWatcher
- **Mistral** — поддержка через `supports_stream_options: false`

### 6. Agents (`core/synpin/agents/`)
Управление агентами:
- **CRUD** — create, read, update, delete
- **Roles & Departments** — roles.yaml, departments.yaml
- **Per-agent config** — agent.yaml (личность, настройки)
- **External agents** — Hermes Agent detection
- **Model resolution** — `9router/general-agent` → provider=`9router`, model=`general-agent`

### 7. Tools (`core/synpin/tools/`)
Инструменты агентов (8 инструментов):
- **terminal** — async shell exec (bash, 30s timeout)
- **file_read** — чтение файлов (offset/limit, 1MB cap)
- **file_write** — запись файлов (атомарная, mkdir)
- **search_files** — ripgrep + Python fallback
- **web_search** — DuckDuckGo поиск
- **code_exec** — sandboxed Python exec
- **memory_read** — чтение MEMORY/USER/facts
- **memory_write** — add/remove/replace entries
- **Security sandbox** — `security.yaml` с configurable `allowed_directories`

### 8. Memory (`core/synpin/memory/`)
Система памяти:
- **MemoryStore** — bounded curated memory (MEMORY.md + USER.md)
- **MemorySearch** — FTS5 full-text search
- **FrozenSnapshot** — system prompt stability
- **AgentState** — bookmarks per channel
- **Compaction** — token-based, auto-сжатие при превышении context_window
- **Session auto-reset** — daily/timer/time с архивацией
- **File Locking** — безопасный конкурентный доступ

---

## Структура проекта

```
synpin/
├── core/                      ← Python ядро
│   ├── synpin/
│   │   ├── agents/            ← роли агентов
│   │   ├── memory/            ← FTS5 + Markdown + frozen snapshot
│   │   ├── tools/             ← инструменты (8 штук) + security sandbox
│   │   ├── chat/              ← чат-роутер + провайдеры
│   │   │   ├── router.py      ← основной цикл чата
│   │   │   ├── task_manager.py← фоновый менеджер задач (Queue + asyncio.Task)
│   │   │   └── providers/     ← LLM провайдеры (OpenAI, Anthropic)
│   │   ├── router/            ← заглушка (планируется в Фазе 3)
│   │   ├── engine/            ← заглушка (планируется в Фазе 3)
│   │   ├── config/            ← менеджер конфигурации + security.yaml
│   │   │   ├── security.yaml  ← allowed_directories для sandbox
│   │   │   └── watcher.py     ← ConfigWatcher (hot-reload)
│   │   ├── api/               ← FastAPI + WebSocket
│   │   └── __main__.py        ← CLI точка входа
│   ├── dev_server.py          ← Dev supervisor (hot-reload)
│   └── pyproject.toml
├── web/                       ← React UI
│   └── src/
│       ├── App.tsx            ← основной компонент (chat + settings)
│       ├── components/
│       │   ├── SettingsPage.tsx
│       │   ├── MemorySection.tsx
│       │   ├── MarkdownRenderer.tsx
│       │   └── EmojiPicker.tsx
│       ├── lib/
│       │   ├── emoji.ts
│       │   ├── providers.ts
│       │   └── markdown.ts
│       └── index.css
├── wiki/                      ← Документация
├── scripts/
│   └── install.ps1            ← Скрипт установки
├── dev.bat                    ← Эмуляция CLI для разработки
└── README.md
```

---

## Что реализовано vs что планируется

| Компонент | Статус |
|---|---|
| Chat UI (стриминг, tool timeline) | ✅ Реализовано |
| Settings (провайдеры, агенты) | ✅ Реализовано |
| Agent CRUD | ✅ Реализовано |
| Memory (MEMORY.md, USER.md, FTS5) | ✅ Реализовано |
| Tools (8 инструментов) | ✅ Реализовано |
| Chat Router (SSE, tool execution) | ✅ Реализовано |
| Text fallback parser (5 паттернов) | ✅ Реализовано |
| Providers (9router, Mistral) | ✅ Реализовано |
| External agents (Hermes) | ✅ Реализовано |
| Task Manager (background tasks, polling recovery) | ✅ Реализовано |
| Security sandbox (security.yaml) | ✅ Реализовано |
| Compaction + session auto-reset | ✅ Реализовано |
| **Router (делегат/команда)** | 🔮 Планируется в Фазе 3 |
| **Engine (ReAct-луп)** | 🔮 Планируется в Фазе 3 |
| **MCP** | ❌ Не реализовано |
| **Dashboard** | ❌ Не реализовано |
| **Kanban** | ❌ Не реализовано |
| **Forum** | ❌ Не реализовано |
| **Group Chat** | ❌ Не реализовано |

---

*Архитектура модульная — каждый слой можно заменить или расширить без трогания остальных.*
