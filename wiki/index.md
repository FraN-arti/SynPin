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
| [**Интеграции**](integrations.md) | Hermes ACP, внешние агенты |

---

## 📖 Структура

| Документ | Описание |
|---|---|
| [Архитектура](architecture.md) | Архитектура системы |
| [Философия](philosophy.md) | Философия проекта |
| [Roadmap](roadmap.md) | Дорожная карта |

---

## 📁 Структура документов

```
wiki/
├── README.md               # Wiki-оглавление (этот файл)
├── index.md                # Навигация
├── quickstart.md           # Быстрый старт
├── configuration.md        # Конфигурация системы
├── agents.md               # Агенты: личность, скиллы, роли
├── tools.md                # Инструменты агентов
├── integrations.md         # Hermes, внешние агенты
├── memory-sessions.md      # Память и сессии
├── memory-system.md        # Система памяти
├── channels-hierarchy.md   # Каналы (мессенджеры)
├── dashboard.md            # Web UI (чат + настройки)
├── architecture.md         # Архитектура системы
├── philosophy.md           # Философия проекта
├── roadmap.md              # Дорожная карта
│
├── 📋 Design Specs (планируется):
│   ├── kanban-board.md     # Kanban-доска задач
│   ├── forum.md            # Форум
│   ├── group-chat.md       # Group Chat Engine
│   ├── mcp-integration.md  # MCP интеграция
│   ├── agent-roles.md      # Роли агентов
│   ├── themes-research.md  # Исследование тем
│   └── onboarding.md       # Стартовое окно
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
Tools (что делают агенты)
    ↓
Memory (что запоминают)
```

Каждый документ ссылается на связанные. Начни с Configuration → Agents → Tools.

---

*SynPin — это не фреймворк. Это компания, которая работает на тебя.*
