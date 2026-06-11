<div align="center">

<img src="synpin.png" alt="SynPin" width="120" />

**ИИ-команда, которая работает вместе с вами.**

[Как это работает](#как-это-работает) · [Быстрый старт](#быстрый-старт) · [Архитектура](#архитектура) · [Лицензия](#лицензия)

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## Как это работает

SynPin — это платформа, где ИИ-агенты живут в организации как настоящие сотрудники. У каждого агента есть имя, роль и место в команде. Они общаются друг с другом, делятся задачами и помнят прошлые разговоры.

В отличие от обычных чат-ботов, здесь агенты **действительно работают вместе**: один пишет код, другой проверяет, третий помогает с архитектурой. И всё это — в одном интерфейсе.

---

## Быстрый старт

### Разработка (рекомендуется)

```bash
# Backend
cd core
SYNPIN_DEV=1 PYTHONPATH=. python -m uvicorn synpin.api.server:app --host 0.0.0.0 --port 2088

# Frontend (отдельная консоль)
cd web
npm install
npm run dev
```

Откройте `http://localhost:2099` — Vite проксирует API на порт 2088.

### Production

```bash
git clone https://github.com/FraN-arti/SynPin.git
cd SynPin
pip install -e ./core
cd web && npm install && npm run build && cd ..
synpin start
```

Откройте `http://localhost:2088`.

---

## Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                Web UI (React 19 + TypeScript)            │
│   Chat · Otdel Chat · Settings · Widgets · Themes       │
└─────────────────────┬───────────────────────────────────┘
                      │ WebSocket (/ws) + HTTP
                      ▼
┌─────────────────────────────────────────────────────────┐
│              Backend (Python FastAPI + uvicorn)          │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Chat Router  │  │  REST API    │  │  WS Router   │  │
│  │  (LLM call)   │  │  (14 endpoints) │ (streaming)  │  │
│  └──────┬───────┘  └──────────────┘  └──────┬───────┘  │
│         │                                    │          │
│  ┌──────┴────────────────────────────────────┴───────┐  │
│  │              Tools Layer (13 инструментов)         │  │
│  │  terminal · file_read · web_search · code_exec    │  │
│  │  memory_read · memory_write · search_files        │  │
│  │  head_delegate · head_evaluate · head_retry       │  │
│  │  head_decide · file_write                         │  │
│  └──────────────────────┬────────────────────────────┘  │
│                         │                               │
│  ┌──────────────────────┴────────────────────────────┐  │
│  │           Memory System (FTS5 + JSON)             │  │
│  │  MEMORY.md · USER.md · Frozen Snapshot            │  │
│  │  Facts · Sessions · Auto-compaction               │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
         │                              │
    ┌────┴────┐                    ┌────┴────┐
    │  9router │                    │ Mistral │
    │ (hermes) │                    │  (API)  │
    └─────────┘                    └─────────┘
```

---

## Стек

| Компонент | Технология |
|-----------|------------|
| Backend | Python 3.11, FastAPI, uvicorn, Pydantic |
| Frontend | React 19, TypeScript 5.7, Vite 6 |
| Стили | Tailwind CSS, CSS переменные |
| Стриминг | WebSocket (мультиплексированный /ws) |
| Память | JSON на диске, FTS5 full-text search |
| Провайдеры | OpenAI-compatible API (9router, Mistral) |
| DnD | @dnd-kit/core + sortable |

---

## Структура проекта

```
SynPin/
├── core/                    # Python backend
│   └── synpin/
│       ├── agents/          # Управление агентами
│       ├── api/             # REST API (FastAPI)
│       ├── chat/            # Chat + Otdel + WebSocket
│       ├── config/          # YAML конфигурация
│       ├── memory/          # Память агентов (FTS5)
│       └── tools/           # 13 инструментов
├── web/                     # React frontend
│   └── src/
│       ├── components/      # UI компоненты
│       ├── hooks/           # useWebSocket
│       └── lib/             # Утилиты
├── wiki/                    # Документация
└── scripts/                 # Утилиты установки
```

---

## Лицензия

MIT License. Автор: [FraN-arti](https://github.com/FraN-arti).
