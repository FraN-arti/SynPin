# 📚 SynPin Wiki

Документация проекта SynPin — Agent-Driven Organization Platform.

---

## 🚀 Быстрый старт

| Документ | Описание |
|---|---|
| [Quick Start](quickstart.md) | Установка, запуск, первые шаги |
| [Configuration](configuration.md) | YAML-конфиги: провайдеры, агенты, отделы, каналы, память |

---

## 🤖 Агенты

| Документ | Описание |
|---|---|
| [**Агенты**](agents.md) | Личность, модель combos (provider/model), роли, hot-reload |
| [**Отделы**](otdels.md) | Департаменты → Отделы, Head Protocol, @mentions |
| [Память и сессии](memory-sessions.md) | MEMORY.md, типы сессий, авто-очистка, компакция |
| [Инструменты](tools.md) | 13 инструментов (8 базовых + 5 Head Protocol) |
| [**Интеграции**](integrations.md) | Hermes ACP, внешние агенты |
| [**Каналы и иерархия**](channels-hierarchy.md) | Department-based коммуникация, @mention, visibility rules |
| [**Виджеты**](widgets.md) | Drag-and-drop панели, layout persistence, расширяемость |

---

## 📖 Структура

| Документ | Описание |
|---|---|
| [Архитектура](architecture.md) | Архитектура системы (WebSocket, Head Protocol, Stats, Themes) |
| [Философия](philosophy.md) | Философия проекта |
| [Roadmap](roadmap.md) | Дорожная карта (Фаза 1 ~95% готово) |

---

## 📁 Структура документов

```
wiki/
├── README.md               # Wiki-оглавление (этот файл)
├── index.md                # Навигация
├── quickstart.md           # Быстрый старт
├── configuration.md        # Конфигурация системы (11 YAML файлов)
├── agents.md               # Агенты: личность, model combos, роли
├── otdels.md               # Отделы: департаменты, Head Protocol
├── tools.md                # Инструменты агентов (13 штук + Head Protocol)
├── integrations.md         # Hermes, внешние агенты
├── memory-sessions.md      # Память и сессии (компакция, авто-сброс)
├── memory-system.md        # Система памяти
├── channels-hierarchy.md   # Каналы и коммуникация (мессенджеры)
├── widgets.md              # Drag-and-drop виджеты
├── dashboard.md            # Web UI (чат + otdel-чат + настройки)
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
Otdels (департаменты → отделы, Head Protocol)
    ↓
Channels (где работают агенты, внешние мессенджеры)
    ↓
Tools (что делают агенты, security sandbox, head tools)
    ↓
Memory (что запоминают, компакция)
```

Каждый документ ссылается на связанные. Начни с Configuration → Agents → Otdels → Tools.

---

*SynPin — это не фреймворк. Это компания, которая работает на тебя.*
