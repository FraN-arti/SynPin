# 📚 SynPin Wiki

Документация проекта SynPin — Agent-Driven Organization Platform.

---

## 🚀 Быстрый старт

| Документ | Описание |
|---|---|
| [Quick Start](quickstart.md) | Установка, запуск, первые шаги |
| [Configuration](configuration.md) | YAML-конфиги: провайдеры, агенты, система |

---

## 🤖 Агенты

| Документ | Описание |
|---|---|
| [**Агенты**](agents.md) | Личность, скиллы, роли, контекст загрузки |
| [Память и сессии](memory-sessions.md) | MEMORY.md, типы сессий, авто-очистка |
| [Инструменты](tools.md) | Файлы, команды, web, безопасность |
| [**Интеграции**](integrations.md) | Hermes ACP, OpenClaw, Windsurf |

---

## 🏢 Организация

| Документ | Описание |
|---|---|
| [Каналы и иерархия](channels-hierarchy.md) | Отделы, главы, совет директоров, @mention |
| [Канбан-доска](kanban-board.md) | Задачи, дедлайны, подписи этапов, история решений |
| [**Форум**](forum.md) | Идеи, Q&A, обсуждения, знания, **лента** |

---

## 📖 Структура документов
```
wiki/
├── README.md               # Wiki-оглавление
├── index.md                # Навигация (этот файл)
├── quickstart.md           # Быстрый старт
├── configuration.md        # Конфигурация системы
├── agents.md               # Агенты: личность, скиллы, роли
├── agent-roles.md          # Роли агентов
├── tools.md                # Инструменты агентов
├── integrations.md         # Hermes ACP, OpenClaw, Windsurf
├── mcp-integration.md      # MCP интеграция
├── memory-sessions.md      # Память и сессии
├── memory-system.md        # Система памяти
├── channels-hierarchy.md   # Каналы и иерархия
├── kanban-board.md         # Канбан-доска задач
├── forum.md                # Форум
├── group-chat.md           # Group Chat Engine
├── dashboard.md            # Дашборд
├── architecture.md         # Архитектура системы
├── philosophy.md           # Философия проекта
└── roadmap.md              # Дорожная карта
```

---

## 🔗 Связи между документами

```
Configuration
    ↓
Agents (личность + скиллы + роли)
    ↓
Channels (где работают агенты)
    ↓
Kanban (что делают агенты)
    ↓
Memory (что запоминают)
```

Каждый документ ссылается на связанные. Начни с Configuration → Agents → Channels.

---

*SynPin — это не фреймворк. Это компания, которая работает на тебя.*
