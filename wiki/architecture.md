# 🏗️ Архитектура SynPin

## Общая схема (реализовано)

```
┌─────────────────────────────────────────────────────┐
│                  Web UI (React 19)                  │
│  Chat · Settings · Agent Selection                  │
└───────────────────────┬─────────────────────────────┘
                        │ HTTP / SSE Stream
                        ▼
┌─────────────────────────────────────────────────────┐
│              REST API (FastAPI)                     │
│  /api/agents  /api/chat/stream  /api/memory        │
└───────────────────────┬─────────────────────────────┘
                        │
          ┌─────────────┴─────────────┐
          ▼                           ▼
┌───────────────────┐       ┌───────────────────────┐
│  Chat Router      │       │     Tools Layer       │
│  (openai.py)      │       │  terminal · file ·    │
│  SSE streaming    │       │  web · code · memory  │
│  Tool execution   │       │  (8 инструментов)     │
└─────────┬─────────┘       └───────────┬───────────┘
          │                             │
          ▼                             │
┌─────────────────────────┐             │
│    Providers Layer      │             │
│  OpenAI-compatible      │             │
│  Anthropic Claude       │             │
│  (YAML registry)        │             │
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

### 3. Chat Router (`core/synpin/chat/`)
Основной цикл чата:
- **SSE streaming** через fetch + ReadableStream
- **Tool execution loop** (до 5 итераций)
- **History persistence** (JSON per agent+channel)
- **Compaction** (token-based, configurable)
- **Memory + session context injection**

### 4. Providers (`core/synpin/chat/providers/`)
LLM-провайдеры:
- **OpenAI-compatible** — SSE streaming + native function calling
- **Anthropic Claude** — SSE streaming
- **Provider registry** — YAML конфигурация, hot-reload
- **Mistral** — поддержка через `supports_stream_options: false`

### 5. Agents (`core/synpin/agents/`)
Управление агентами:
- **CRUD** — create, read, update, delete
- **Roles & Departments** — roles.yaml, departments.yaml
- **Per-agent config** — agent.yaml (личность, настройки)
- **External agents** — Hermes Agent detection

### 6. Tools (`core/synpin/tools/`)
Инструменты агентов:
- **Terminal** — async shell exec (bash, 30s timeout)
- **File read/write** — чтение/запись файлов
- **Search** — ripgrep + Python fallback
- **Web search** — DuckDuckGo
- **Code exec** — sandboxed Python
- **Memory read/write** — управление памятью

### 7. Memory (`core/synpin/memory/`)
Система памяти:
- **MemoryStore** — bounded curated memory (MEMORY.md + USER.md)
- **MemorySearch** — FTS5 full-text search
- **FrozenSnapshot** — system prompt stability
- **AgentState** — bookmarks per channel
- **File Locking** — безопасный конкурентный доступ

---

## Структура проекта

```
synpin/
├── core/                      ← Python ядро
│   ├── synpin/
│   │   ├── agents/            ← роли агентов
│   │   ├── memory/            ← FTS5 + Markdown + frozen snapshot
│   │   ├── tools/             ← инструменты (8 штук)
│   │   ├── chat/              ← чат-роутер + провайдеры
│   │   ├── router/            ← заглушка (планируется)
│   │   ├── engine/            ← заглушка (планируется)
│   │   ├── config/            ← менеджер конфигурации
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
| Providers (OpenAI, Anthropic, Mistral) | ✅ Реализовано |
| External agents (Hermes) | ✅ Реализовано |
| **Router (делегат/команда)** | ❌ Заглушка |
| **Engine (ReAct-луп)** | ❌ Заглушка |
| **MCP** | ❌ Не реализовано |
| **Dashboard** | ❌ Не реализовано |
| **Kanban** | ❌ Не реализовано |
| **Forum** | ❌ Не реализовано |
| **Group Chat** | ❌ Не реализовано |

---

*Архитектура модульная — каждый слой можно заменить или расширить без трогания остальных.*
