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
| [**Агенты**](agents.md) | Личность, модель combos (provider/model), роли, hot-reload |
| [Память и сессии](memory-sessions.md) | MEMORY.md, типы сессий, авто-очистка, компакция |
| [Инструменты](tools.md) | 8 инструментов, security sandbox, web_extract (планируется) |
| [**Интеграции**](integrations.md) | Hermes ACP, внешние агенты |
| [**Каналы и иерархия**](channels-hierarchy.md) | Department-based коммуникация, @mentor, visibility rules |

---

## 📖 Структура

| Документ | Описание |
|---|---|
| [Архитектура](architecture.md) | Архитектура системы (background tasks, task manager, polling recovery) |
| [Философия](philosophy.md) | Философия проекта |
| [Roadmap](roadmap.md) | Дорожная карта (Фаза 1 ~90% готово) |

---

## 📁 Структура документов

```
wiki/
├── README.md               # Wiki-оглавление (этот файл)
├── index.md                # Навигация
├── quickstart.md           # Быстрый старт
├── configuration.md        # Конфигурация системы
├── agents.md               # Агенты: личность, model combos, роли
├── tools.md                # Инструменты агентов (8 штук + security sandbox)
├── integrations.md         # Hermes, внешние агенты
├── memory-sessions.md      # Память и сессии (компакция, авто-сброс)
├── memory-system.md        # Система памяти
├── channels-hierarchy.md   # Каналы и коммуникация (мессенджеры)
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
Agents (личность + model combos + роли)
    ↓
Channels (где работают агенты) ← channels-hierarchy.md
    ↓
Tools (что делают агенты, security sandbox)
    ↓
Memory (что запоминают, компакция)
```

Каждый документ ссылается на связанные. Начни с Configuration → Agents → Tools.

---

*SynPin — это не фреймворк. Это компания, которая работает на тебя.*
