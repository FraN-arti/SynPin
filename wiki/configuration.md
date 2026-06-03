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
│   ├── external_agents.yaml  # Внешние агенты (Hermes)
│   └── memory.yaml           # Настройки памяти
├── agents/
│   ├── 85n1yo4x/             # agentid = имя директории
│   │   ├── agent.yaml        # Личность и настройки
│   │   └── avatar.png        # Аватар (опционально)
│   ├── 1f39sqld/
│   │   └── agent.yaml
│   └── ix13aox3/
│       └── agent.yaml
├── logs/
└── data/
```

---

## settings.yaml

Общие настройки сервера, UI и логирования.

```yaml
server:
  host: "0.0.0.0"
  port: 2088
  dev_port: 2099

ui:
  language: "ru"
  theme: "dark"

logging:
  level: "info"
  file: "~/.synpin/logs/synpin.log"
```

| Параметр | По умолчанию | Описание |
|---|---|---|
| `server.host` | `0.0.0.0` | Адрес прослушивания |
| `server.port` | `2088` | Порт API + Web UI |
| `server.dev_port` | `2099` | Порт Vite dev server |
| `ui.language` | `ru` | Язык интерфейса |
| `ui.theme` | `dark` | Тема UI |

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

  local:
    type: "openai-compatible"
    base_url: "http://localhost:1234/v1"
    api_key: ""
    models:
      - local-model
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
  ix13aox3:                    # agentid = ключ
    name: QA Инженер
    role: управляющий
    department: советчик
    model: "9router/general-agent"
    enabled: true

  8e5tv711:
    name: Архитектор
    role: сотрудник
    department: советчик
    model: "9router/general-agent"
    enabled: true

  yni1tbod:
    name: Тестер
    role: сотрудник
    department: поиск
    model: "9router/general-agent"
    enabled: true
```

> **Важно:** Личность агента (имя, роль, описание, system_prompt) хранится в `agents/{agentid}/agent.yaml`, а не здесь.

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

  - rolesid: сотрудник
    name: Сотрудник
    description: сотрудник отдела
    color: '#6a4b16'
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

Департаменты с уникальными slug-идентификаторами.

```yaml
departments:
  - departmentsid: кодер
    name: кодер
    description: занимается кодом
    color: '#3b82f6'

  - departmentsid: поиск
    name: поиск
    description: поиск информации
    color: '#929baa'

  - departmentsid: советчик
    name: советчик
    description: участвует в переговорах
    color: '#bb3bf7'
```

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

---

## Связь с другими документами

- [Агенты](agents.md) — подробности по структуре агентов
- [Интеграции](integrations.md) — Hermes и внешние агенты
- [Быстрый старт](quickstart.md) — установка и запуск
