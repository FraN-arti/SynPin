# ⚙️ Конфигурация

Все пользовательские настройки хранятся в `~/.synpin/config/`.

---

## Структура каталогов

```
~/.synpin/
├── config/
│   ├── settings.yaml         # Общие настройки системы
│   ├── providers.yaml        # LLM провайдеры
│   ├── agents.yaml           # Операционные настройки агентов
│   ├── roles.yaml            # Роли агентов
│   ├── departments.yaml      # Департаменты
│   ├── otdels.yaml           # Отделы (head + workers + compaction)
│   ├── channels.yaml         # Каналы связи (Feishu и т.д.)
│   ├── external_agents.yaml  # Внешние агенты (Hermes)
│   ├── tools.yaml            # Реестр инструментов
│   ├── memory.yaml           # Настройки памяти и компакции
│   ├── security.yaml         # Allowed directories для sandbox
│   └── templates/            # Шаблоны для нового конфига
│       ├── agents.yaml
│       ├── channels.yaml
│       ├── departments.yaml
│       ├── external_agents.yaml
│       ├── memory.yaml
│       ├── otdels.yaml
│       ├── roles.yaml
│       ├── security.yaml
│       ├── settings.yaml
│       └── tools.yaml
├── agents/
│   ├── 85n1yo4x/             # agentid = имя директории
│   │   ├── agent.yaml        # Личность и настройки
│   │   └── avatar.png        # Аватар (опционально)
│   ├── 1f39sqld/
│   │   └── agent.yaml
│   └── ix13aox3/
│       └── agent.yaml
├── themes/
│   └── custom.json           # Пользовательские темы (tweakcn)
├── logs/
└── data/
    ├── agents/               # Память агентов (MEMORY.md, facts/)
    ├── otdels/               # Чат-история отделов (chat.json per otdel)
    ├── shared/               # Глобальный USER.md
    └── search.db             # SQLite FTS5 индекс
```

---

## settings.yaml

Общие настройки сервера, UI, фида, канбана и форума.

```yaml
primary_agent_slug: 8e5tv711

server:
  host: 0.0.0.0
  port: 2088
  dev_port: 2099
  cors_origins:
    - http://localhost:2099
    - http://localhost:2088
  rate_limit:
    enabled: false
    requests_per_minute: 60
  gateway_auth: none

ui:
  theme: dark
  language: ru
  sidebar:
    default_open: true
    show_icons: true
  chat:
    show_metadata: true
    metadata_delay_ms: 500
    max_message_length: 4000
    auto_scroll: true
    streaming_border: true

feed:
  enabled: true
  max_items: 50
  time_range: 24h
  filters:
    new_ideas: true
    task_updates: true
    memory_updates: false
    board_updates: true
    delegations: true
  sort: newest
  group_by: department

kanban:
  default_stages:
    - slug: backlog
      name: Бэклог
      color: '#6b7280'
    - slug: in-progress
      name: В работе
      color: '#f59e0b'
    - slug: review
      name: Ревью
      color: '#3b82f6'
    - slug: testing
      name: Тестирование
      color: '#8b5cf6'
    - slug: done
      name: Готово
      color: '#10b981'
  require_signoff: true
  auto_archive_days: 30

forum:
  sections:
    - slug: ideas
      name: Идеи
      icon: 💡
      description: Предложения и голосования
    - slug: qa
      name: Q&A
      icon: ❓
      description: Вопросы и ответы
    - slug: discussions
      name: Обсуждения
      icon: 🗣
      description: Архитектурные дискуссии
    - slug: knowledge
      name: База знаний
      icon: 📚
      description: Паттерны, находки, лучшие практики
  auto_promote_to_kanban: true

templates:
  task:
    title_format: '[{department}] {summary}'
    default_description: "## Описание\n...\n\n## Критерии приёмки\n- [ ]\n"
    auto_assign: false
  session:
    system_includes:
      - personality
      - memory
      - skills
      - channel_context
      - recent_sessions
```

### Ключевые параметры

| Параметр | По умолчанию | Описание |
|---|---|---|
| `server.port` | `2088` | Порт API + Web UI |
| `server.dev_port` | `2099` | Порт Vite dev server |
| `ui.language` | `ru` | Язык интерфейса |
| `ui.theme` | `dark` | Тема UI |
| `primary_agent_slug` | — | Основной агент |
| `feed.enabled` | `true` | Лента активности |

---

## providers.yaml

Конфигурация LLM-провайдеров. Поддерживаются любые OpenAI-совместимые API.

```yaml
providers:
  openai:
    type: "openai"
    base_url: "https://api.openai.com/v1"
    api_key: "sk-..."
    models:
      - gpt-4o
      - gpt-4o-mini
    default: true

  anthropic:
    type: "anthropic"
    base_url: "https://api.anthropic.com"
    api_key: "sk-ant-..."
    models:
      - claude-sonnet-4-20250514
      - claude-3-5-haiku-20241022

  mistral:
    type: "openai"
    base_url: "https://api.mistral.ai/v1"
    api_key: "..."
    supports_stream_options: false
    models:
      - mistral-large-latest
      - codestral-latest
```

### Типы провайдеров

| Тип | Описание |
|---|---|
| `openai` | OpenAI API |
| `anthropic` | Anthropic API |
| `openai-compatible` | Любое OpenAI-совместимое API |

---

## agents.yaml

Операционные настройки агентов (модель, провайдер, включён/выключено).

```yaml
agents:
  ix13aox3:
    name: QA Инженер
    role: управляющий
    department: советчик
    model: 9router/summarise-agent
    personality:
      tone: professional
      style: analytical
      traits:
        - thinks before answering
    system_prompt: ''
    enabled: true
    is_primary: false

  8e5tv711:
    name: Архитектор
    role: сотрудник
    department: советчик
    model: 9router/hermes-agent
    enabled: true
    is_primary: false

  nukf4tc0:
    model: 9router/thinking-agent
    enabled: true
```

> **Важно:** Личность агента (имя, роль, описание, system_prompt) может храниться как в `agents.yaml`, так и в `agents/{agentid}/agent.yaml`.

---

## roles.yaml

Роли агентов с уникальными slug-идентификаторами.

```yaml
# ~/.synpin/config/roles.yaml
roles:
  - rolesid: управляющий
    name: Управляющий
    description: управляющий отделом
    color: '#f59e0b'

  - rolesid: совет-директоров
    name: Совет Директоров
    description: это почти верхушка айзберга
    color: '#b60af5'

  - rolesid: работник-отдела
    name: Работник отдела
    description: Стандартный агент
    color: '#595245'
```

### Поля

| Поле | Описание |
|---|---|
| `rolesid` | Уникальный slug роли (кириллица, латиница) |
| `name` | Отображаемое имя роли |
| `description` | Описание роли |
| `color` | Цвет для UI (hex) |

---

## departments.yaml

Департаменты — высший уровень организационной структуры.

```yaml
departments:
  - departmentsid: how5jhamq02m
    name: Вахтан
    color: '#f97316'

  - departmentsid: cmpfmu9lsoz0
    name: Сузумебачи
    color: '#7cf915'

  - departmentsid: h0d8udk4wxio
    name: Волокита
    description: департамент отвечающий за обдумывание решений
    color: '#27166a'

  - departmentsid: t8rbmlmz7mps
    name: Разработка
    description: Отдел разработки
    color: '#bbf73b'
```

---

## otdels.yaml

Отделы — второй уровень, находятся внутри департаментов.

```yaml
otdels:
  - otdelid: pw6flsdgw48m
    name: Обсуждение аниме
    description: группа обсуждает аниме
    color: '#15f9a2'
    mentor_role: управляющий
    head: ix13aox3
    workers:
      - k493rqqz
      - 8e5tv711

  - otdelid: h1urnetgjr5q
    name: Грахатули
    description: Самый радостный отдел в мире для общения
    color: '#f915db'
    mentor_role: управляющий
    head: ix13aox3
    workers:
      - k493rqqz
      - 8e5tv711
      - nukf4tc0
      - ezu8oolt
      - 75ecwopd
    compaction_limit: 100
    keep_recent: 10
```

### Поля

| Поле | Описание |
|---|---|
| `otdelid` | Уникальный 12-символьный ID |
| `name` | Отображаемое имя отдела |
| `head` | slug агента-Главы |
| `workers` | Список slug'ов работников |
| `mentor_role` | Роль для фильтрации кандидатов в Главу |
| `compaction_limit` | Лимит сообщений (по умолчанию 100) |
| `keep_recent` | Сохранять последние N (по умолчанию 10) |

> Подробнее: [Отделы](otdels.md)

---

## channels.yaml

Каналы связи — внешние мессенджеры.

```yaml
channels:
  feishu-main:
    name: "Feishu — Основной"
    type: feishu
    status: connected
    app_id: "cli_a5..."
    app_secret: "***"
    mode: websocket
    binding:
      target: "main"
      agent_id: null
      department: null
    features:
      notifications: true
      file_upload: true
      commands: true
    rate_limit:
      messages_per_minute: 30

# Доступные типы каналов (для мастера добавления):
channel_types:
  feishu: { required_fields: [app_id, app_secret, verification_token], modes: [websocket, webhook] }
  whatsapp: { required_fields: [phone_number_id, access_token, verify_token], modes: [webhook] }
  telegram: { required_fields: [bot_token], modes: [polling, webhook] }
  slack: { required_fields: [bot_token, signing_secret], modes: [websocket] }
  discord: { required_fields: [bot_token], modes: [websocket] }
  email: { required_fields: [imap_host, imap_port, smtp_host, smtp_port, username, password], modes: [polling] }

# Цели привязки:
binding_targets:
  - slug: "main"       # Главный агент
  - slug: "department" # Все агенты департамента
  - slug: "agent"      # Конкретный агент
```

---

## memory.yaml

Настройки памяти, компакции и сессий.

```yaml
context_window:
  default: 128000

compaction:
  enabled: true
  trigger_percent: 80
  keep_recent: 10
  strategy: summarize
  summary_max_tokens: 500

sessions:
  auto_reset:
    enabled: true
    mode: daily
    reset_time: 00:00
    interval_hours: 24
  archive_on_reset: true
  max_history: 100

agent_memory:
  enabled: true
  path: agents/{dept}/{agent_id}/MEMORY.md
  auto_save:
    on_session_end: true
    on_error: true
    on_decision: true
    interval_minutes: 30
  categories:
    - { slug: lessons, name: Уроки }
    - { slug: decisions, name: Решения }
    - { slug: preferences, name: Предпочтения }
    - { slug: context, name: Контекст }

team_memory:
  enabled: true
  path: shared/MEMORY.md
  auto_share:
    new_patterns: true
    architecture_decisions: true
    best_practices: true
    bugs_found: true
  categories:
    - { slug: patterns, name: Паттерны }
    - { slug: adrs, name: ADR }
    - { slug: best-practices, name: Лучшие практики }
    - { slug: bugs, name: Баг-база }
    - { slug: onboarding, name: Онбординг }

system_memory:
  enabled: true
  fts5:
    enabled: true
    searchable_fields:
      - message_content
      - task_title
      - task_description
      - forum_title
      - forum_content
      - memory_entries

lifecycle:
  cleanup:
    enabled: true
    archive_sessions_after_days: 90
    delete_archived_after_days: 365
    compact_memory_threshold: 50
  retention:
    active_decisions: keep
    lessons: keep
    session_summaries: 90
    forum_posts: 365
```

---

## security.yaml

Ограничения безопасности для файловых инструментов.

```yaml
# Все файловые инструменты (read, write, search, terminal cwd) ограничены этими директориями
security:
  allowed_directories:
    - "D:\\synpin"
    # - "C:\\Projects"
```

---

## tools.yaml

Реестр инструментов с категориями и флагами implemented/builtin.

> Подробнее: [Инструменты](tools.md)

---

## external_agents.yaml

Внешние агенты (Hermes и другие).

```yaml
agents:
  hermes:
    name: Hermes
    type: hermes
    agentid: a1b2c3d4
    enabled: true
    role: director
    department: dev
    description: 'AI ассистент с полным доступом к инструментам'
    available: true
    models:
      - hermes-agent
    chat_url: "http://localhost:8642"
    icon_letter: H
    color: "#f97316"
```

---

## Агент: agent.yaml

Личность и настройки конкретного агента.

```yaml
# agents/ix13aox3/agent.yaml
agentid: ix13aox3
name: QA Инженер
description: ''
role: управляющий
department: советчик

personality:
  tone: professional
  style: analytical
  traits:
    - thinks before answering

behavior:
  max_iterations: 10
  temperature: 0.7
  max_tokens: 4096

system_prompt: ''

memory: {}
```

### Поля

| Поле | Описание |
|---|---|
| `agentid` | Уникальный 8-символьный ID |
| `name` | Отображаемое имя |
| `description` | Краткое описание роли |
| `role` | Ссылка на rolesid (slug) |
| `department` | Ссылка на departmentsid (slug) |
| `personality.tone` | Тон общения |
| `personality.style` | Стиль ответов |
| `personality.traits` | Характеристики |
| `behavior.temperature` | Температура LLM |
| `behavior.max_tokens` | Максимум токенов |
| `system_prompt` | Системный промпт |

---

## Порты

| Сервис | Порт | Описание |
|---|---|---|
| SynPin API | 2088 | Основной API + Web UI |
| Vite Dev | 2099 | Dev server для фронтенда |
| Hermes Gateway | 8642 | API server Hermes |
| WebSocket | 2088 | `/ws` endpoint (тот же порт) |

---

## Hot-Reload

Конфигурация автоматически перезагружается при изменении файлов:

```
ConfigWatcher (polling 5s)
    ↓
providers.yaml изменён → registry.reload()
agents.yaml изменён → перезагрузка агентов
tools.yaml изменён → перезагрузка инструментов
```

---

## Связь с другими документами

- [Агенты](agents.md) — подробности по структуре агентов
- [Отделы](otdels.md) — otdels.yaml и departments.yaml
- [Интеграции](integrations.md) — Hermes и внешние агенты
- [Инструменты](tools.md) — tools.yaml реестр
- [Быстрый старт](quickstart.md) — установка и запуск
