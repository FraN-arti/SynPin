# 🏗️ Архитектура SynPin

## Общая схема (реализовано)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Web UI (React 19)                             │
│  Chat · Otdel Chat · Settings · Agent Selection · Themes        │
└─────────────────────────┬───────────────────────────────────────┘
                          │ WebSocket (/ws) + HTTP + SSE Stream
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│              WebSocket Layer (ws_router.py)                      │
│  /ws — multiplexed: chat:send, otdel:send                       │
│  useWebSocket.ts — React hook с reconnect                       │
└────────┬───────────────────────────────────┬────────────────────┘
         │                                   │
         ▼                                   ▼
┌─────────────────┐            ┌─────────────────────────────────┐
│  REST API       │            │  Otdel Chat Router               │
│  (FastAPI)      │            │  (otdel_chat_router.py)          │
│                 │            │  /api/otdels/{id}/chat/*          │
│  /api/agents    │            │  @mentions, Head/Worker flow      │
│  /api/chat/*    │            │  Chat history per otdel           │
│  /api/memory    │            └──────────────────────────────────┘
│  /api/providers │
│  /api/stats/*   │
│  /api/themes/*  │
│  /api/config/*  │
│  /api/health    │
└────────┬────────┘
         │
    ┌────┴────────────────────┐
    ▼                         ▼
┌──────────────────┐   ┌──────────────────────────┐
│  Task Manager    │   │     Tools Layer           │
│  (Queue + async) │   │  8 базовых инструментов   │
│  ChatTask wraps  │   │  + 5 Head Protocol tools  │
│  asyncio.Task    │   │  (13 инструментов)        │
│  + asyncio.Queue │   │                           │
│  for WS chunks   │   │  Security Sandbox:        │
└────────┬─────────┘   │  security.yaml            │
         │             │  allowed_directories       │
         ▼             └─────────────┬─────────────┘
┌─────────────────────────┐          │
│    Chat Router          │          │
│  (router.py)            │          │
│  SSE streaming          │          │
│  Tool execution loop    │          │
│  Text fallback parser   │          │
│  (5 patterns: JSON,     │          │
│   tool_call, XML, etc)  │          │
└─────────┬───────────────┘          │
          │                          │
          ▼                          │
┌───────────────────────────────────┤
│  Background Task System           │
│  asyncio.Task (survives disconnect)│
│  Queue-based WS/SSE streaming    │
│  History saved by background task │
└─────────┬─────────────────────────┘
          │
          ▼
┌─────────────────────────┐
│    Providers Layer      │
│  9router (hermes, sum)  │
│  Mistral (fallback)     │
│  Model combos:          │
│  provider/model format  │
│  (YAML registry + hot)  │
└─────────────┬───────────┘
              │
              ▼
┌───────────────────────────────────────────────┐
│              Memory System                    │
│  MemoryStore (MEMORY.md + USER.md)            │
│  MemorySearch (FTS5 full-text)                │
│  FrozenSnapshot (system prompt stability)     │
│  AgentState (bookmarks per channel)           │
│  Facts (dated entries)                        │
│  Compaction (token-based, auto)               │
│  Session auto-reset (daily/timer/time)        │
│  Memory + session context injection           │
└───────────────────────────────────────────────┘
```

## Слои

### 1. Web UI (`web/`)
React SPA — чат, otdel-чат и настройки:
- **Chat UI** — стриминг, tool timeline, markdown, emoji
- **Otdel Chat** — otdel-чат с @mentions, streaming chunks, thinking indicators
- **Settings** — провайдеры, агенты, роли/департаменты, каналы
- **Agent Selection** — выбор агента (SynPin + внешние)
- **Widget System** — drag-and-drop панели (departments tab)
- **Themes** — импорт/экспорт тем через tweakcn API
- **Stats** — overview, usage, tool stats, sessions
- **WebSocket** — useWebSocket hook с reconnect
- **Технологии:** React 19, Vite 6, TypeScript 5.7, @dnd-kit
- **Нет:** Zustand, TanStack Query (удалены)

### 2. WebSocket Layer (`core/synpin/chat/ws_router.py`)
Single `/ws` endpoint с мультиплексированным протоколом:
- **Client → Server:** `{"type": "chat:send"}` или `{"type": "otdel:send"}`
- **Server → Client:** `{"type": "chat:chunk"}`, `{"type": "otdel:chunk"}`, `{"type": "otdel:thinking"}` и т.д.
- **HeadState** — per-otdel состояние для Head Protocol (delegation state, worker tracking)
- **Auto-reconnect** — клиент переподключается с exponential backoff

### 3. REST API (`core/synpin/api/`)
FastAPI сервер — единая точка входа:
- `POST /api/chat/stream` — SSE стриминг чата
- `POST /api/chat/hermes/stream` — прокси для Hermes
- `GET/POST /api/agents` — CRUD агентов
- `GET/POST /api/memory` — управление памятью
- `GET /api/providers` — список провайдеров
- `GET /api/stats/overview` — обзор системы
- `GET /api/stats/usage` — статистика использования
- `GET /api/stats/tools` — статистика инструментов
- `GET /api/stats/sessions` — список сессий
- `GET/POST /api/themes/*` — импорт/управление темами (tweakcn)
- `GET/POST /api/config/*` — настройки компакции, сессий
- `GET /api/health` — health check

### 4. Otdel Chat Router (`core/synpin/chat/otdel_chat_router.py`)
Изолированный чат для каждого отдела:
- **@mention routing** — Глава видит всё, работники — только при @mention
- **Head/Worker flow** — Глава делегирует → работники отвечают → Head follow-up
- **History per otdel** — `chat.json` в `data/otdels/{otdel_id}/`
- **Compaction** — автоматическое сжатие при превышении `compaction_limit`

### 5. Task Manager (`core/synpin/chat/task_manager.py`)
Фоновый менеджер задач чата:
- **ChatTask** — оборачивает asyncio.Task + asyncio.Queue
- **WS streaming** — клиент читает из Queue через WebSocket
- **Survives disconnect** — LLM работает даже после закрытия браузера
- **Polling recovery** — клиент переподключается и читает из Queue
- **History persistence** — история сохраняется фоновой задачей

### 6. Chat Router (`core/synpin/chat/router.py`)
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

### 7. Providers (`core/synpin/chat/providers/`)
LLM-провайдеры с combo-системой:
- **Model combos** — формат `provider/model` (например `9router/general-agent`)
- **9router** — hermes-agent, summarise-agent (локальный прокси)
- **Mistral** — fallback через Mistral API
- **Provider registry** — YAML конфигурация, hot-reload через ConfigWatcher
- **Mistral** — поддержка через `supports_stream_options: false`

### 8. Agents (`core/synpin/agents/`)
Управление агентами:
- **CRUD** — create, read, update, delete
- **Roles & Departments** — roles.yaml, departments.yaml
- **Otdels** — otdels.yaml (head + workers)
- **Per-agent config** — agent.yaml (личность, настройки)
- **External agents** — Hermes Agent detection
- **Model resolution** — `9router/general-agent` → provider=`9router`, model=`general-agent`

### 9. Tools (`core/synpin/tools/`)
Инструменты агентов (13 инструментов):
- **terminal** — async shell exec (bash, 30s timeout)
- **file_read** — чтение файлов (offset/limit, 1MB cap)
- **file_write** — запись файлов (атомарная, mkdir)
- **search_files** — ripgrep + Python fallback
- **web_search** — DuckDuckGo поиск
- **code_exec** — sandboxed Python exec
- **memory_read** — чтение MEMORY/USER/facts
- **memory_write** — add/remove/replace entries
- **head_delegate** — делегирование задач воркерам (builtin, otdel-only)
- **head_await** — ожидание ответов от воркеров (builtin, otdel-only)
- **head_evaluate** — quality gate (builtin, otdel-only)
- **head_retry** — ретрай упавшего воркера (builtin, otdel-only)
- **head_decide** — стратегическое решение (builtin, otdel-only)
- **Security sandbox** — `security.yaml` с configurable `allowed_directories`

### 10. Memory (`core/synpin/memory/`)
Система памяти:
- **MemoryStore** — bounded curated memory (MEMORY.md + USER.md)
- **MemorySearch** — FTS5 full-text search
- **FrozenSnapshot** — system prompt stability
- **AgentState** — bookmarks per channel
- **Compaction** — token-based, auto-сжатие при превышении context_window
- **Session auto-reset** — daily/timer/time с архивацией
- **File Locking** — безопасный конкурентный доступ

### 11. Stats API (`core/synpin/api/stats_router.py`)
Системная статистика:
- `/api/stats/overview` — summary cards (агенты, сообщения, uptime)
- `/api/stats/usage` — статистика по моделям и агентам
- `/api/stats/tools` — использование инструментов
- `/api/stats/sessions` — список сессий

### 12. Themes API (`core/synpin/api/themes_router.py`)
Управление темами через tweakcn:
- Импорт тем из tweakcn формата
- Конвертация CSS → JSON переменные
- Хранение в `~/.synpin/themes/custom.json`

---

## Структура проекта

```
synpin/
├── core/                      ← Python ядро
│   ├── synpin/
│   │   ├── agents/            ← роли агентов, manager.py
│   │   ├── memory/            ← FTS5 + Markdown + frozen snapshot
│   │   ├── tools/             ← 13 инструментов + security sandbox
│   │   │   ├── head_delegate.py  ← Head Protocol (builtin)
│   │   │   ├── head_await.py     ← Head Protocol (builtin)
│   │   │   ├── head_evaluate.py  ← Head Protocol (builtin)
│   │   │   ├── head_retry.py     ← Head Protocol (builtin)
│   │   │   └── head_decide.py    ← Head Protocol (builtin)
│   │   ├── chat/              ← чат-роутеры + провайдеры
│   │   │   ├── router.py      ← основной цикл чата (SSE)
│   │   │   ├── ws_router.py   ← WebSocket endpoint (multiplexed)
│   │   │   ├── ws_manager.py  ← WS connection manager
│   │   │   ├── otdel_chat_router.py ← otdel-чат (HTTP fallback)
│   │   │   ├── otdel_helpers.py     ← otdel логика (history, prompts)
│   │   │   ├── task_manager.py      ← фоновый менеджер задач
│   │   │   └── providers/     ← LLM провайдеры (OpenAI, Anthropic)
│   │   ├── config/            ← менеджер конфигурации + YAML
│   │   │   ├── settings.yaml  ← общие настройки (server, ui, feed, kanban)
│   │   │   ├── departments.yaml ← департаменты
│   │   │   ├── otdels.yaml    ← отделы (head, workers, compaction)
│   │   │   ├── roles.yaml     ← роли агентов
│   │   │   ├── channels.yaml  ← каналы связи (Feishu и т.д.)
│   │   │   ├── memory.yaml    ← настройки памяти и компакции
│   │   │   ├── security.yaml  ← allowed_directories
│   │   │   ├── tools.yaml     ← реестр инструментов
│   │   │   └── watcher.py     ← ConfigWatcher (hot-reload)
│   │   ├── api/               ← FastAPI + WebSocket
│   │   │   ├── server.py      ← FastAPI app, includes all routers
│   │   │   ├── agents_router.py      ← CRUD агентов
│   │   │   ├── providers_router.py   ← CRUD провайдеров
│   │   │   ├── memory_router.py      ← CRUD памяти
│   │   │   ├── config_router.py      ← настройки компакции/сессий
│   │   │   ├── stats_router.py       ← статистика системы
│   │   │   ├── themes_router.py      ← tweakcn темы
│   │   │   ├── hermes_chat_router.py ← Hermes прокси
│   │   │   └── external_agents_router.py ← внешние агенты
│   │   └── __main__.py        ← CLI точка входа
│   ├── dev_server.py          ← Dev supervisor (hot-reload)
│   └── pyproject.toml
├── web/                       ← React UI
│   └── src/
│       ├── App.tsx            ← основной компонент (DndContext)
│       ├── config.ts          ← API_BASE, WS_URL
│       ├── components/
│       │   ├── SettingsPage.tsx       ← настройки (все вкладки)
│       │   ├── OtdelChatView.tsx      ← чат отдела (WebSocket)
│       │   ├── OtdelSettingsPanel.tsx  ← настройки отдела
│       │   ├── WidgetDropZone.tsx     ← drag-and-drop виджеты
│       │   ├── MemorySection.tsx      ← секция памяти
│       │   ├── MarkdownRenderer.tsx   ← рендерер markdown
│       │   └── EmojiPicker.tsx        ← пикер эмодзи
│       ├── hooks/
│       │   └── useWebSocket.ts       ← WS hook (reconnect, events)
│       ├── lib/
│       │   ├── emoji.ts              ← утилиты эмодзи
│       │   ├── providers.ts          ← утилиты провайдеров
│       │   └── markdown.ts           ← утилиты markdown
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
| Otdel Chat (WebSocket, @mentions, streaming) | ✅ Реализовано |
| Settings (провайдеры, агенты, отделы) | ✅ Реализовано |
| Agent CRUD | ✅ Реализовано |
| Otdels (head, workers, compaction) | ✅ Реализовано |
| Memory (MEMORY.md, USER.md, FTS5) | ✅ Реализовано |
| Tools (8 базовых + 5 Head Protocol = 13) | ✅ Реализовано |
| Chat Router (SSE, tool execution) | ✅ Реализовано |
| Text fallback parser (5 паттернов) | ✅ Реализовано |
| WebSocket (single /ws, multiplexed) | ✅ Реализовано |
| Providers (9router, Mistral) | ✅ Реализовано |
| External agents (Hermes) | ✅ Реализовано |
| Task Manager (background tasks, polling recovery) | ✅ Реализовано |
| Security sandbox (security.yaml) | ✅ Реализовано |
| Compaction + session auto-reset | ✅ Реализовано |
| Widget System (drag-and-drop) | ✅ Реализовано |
| Stats API (overview, usage, tools, sessions) | ✅ Реализовано |
| Themes (tweakcn import/export) | ✅ Реализовано |
| Head Protocol (delegate, await, evaluate, retry, decide) | ✅ Реализовано |
| **Router (делегат/команда)** | 🔮 Планируется в Фазе 3 |
| **Engine (ReAct-луп)** | 🔮 Планируется в Фазе 3 |
| **MCP** | ❌ Не реализовано |
| **Dashboard** | ❌ Не реализовано |
| **Kanban** | ❌ Не реализовано |
| **Forum** | ❌ Не реализовано |
| **Group Chat** | ❌ Не реализовано |

---

*Архитектура модульная — каждый слой можно заменить или расширить без трогания остальных.*
