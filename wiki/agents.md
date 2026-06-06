# 🤖 Агенты

Агент в SynPin — это не просто LLM. Это **личность с памятью, навыками и ролью** в организации.

---

## Архитектура агента

```
┌─────────────────────────────────────────────────┐
│                    АГЕНТ                         │
├─────────────────────────────────────────────────┤
│  🆔 Agent ID     → уникальный 8-символьный ID   │
│  👤 Имя          → отображаемое имя             │
│  📋 Роль         → rolesid (ссылка на роль)     │
│  🏢 Департамент  → departmentsid (ссылка на отд)│
│  🧠 Память       → system prompt, описание      │
│  🎭 Характер     → tone, style, traits          │
│  🔧 Поведение    → temperature, max_tokens      │
│  📡 Провайдер    → LLM провайдер и модель       │
│                      (model combo: provider/m)  │
└─────────────────────────────────────────────────┘
```

---

## 🆔 Agent ID (agentid)

Каждый агент имеет **уникальный 8-символьный ID** (a-z, 0-9), генерируемый при создании.

- Используется как **ключ** в `agents.yaml`
- Используется как **имя директории** агента
- Используется как **slug** в API URL (`/api/agents/{agentid}`)
- **Неизменяем** после создания (вплоть до удаления)

```
agents/
├── 85n1yo4x/          ← agentid = slug
│   ├── agent.yaml     ← личность и настройки
│   └── avatar.png     ← опционально
├── 1f39sqld/
│   └── agent.yaml
└── ix13aox3/
    └── agent.yaml
```

### Почему agentid, а не имя?

- Кириллица в путях/URL — проблемы с совместимостью
- Имена могут дублироваться, agentid — уникален
- Короткий, компактный, ASCII-safe

---

## Структура agent.yaml

```yaml
# agents/ix13aox3/agent.yaml
agentid: ix13aox3
name: QA Инженер
description: ''
role: управляющий              # slug из roles.yaml
department: советчик           # slug из departments.yaml
model: 9router/hermes-agent    # combo формат: provider/model

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

---

## 📡 Model Combos (provider/model)

Агенты используют **combo-формат** для указания модели:

```yaml
model: 9router/general-agent   # provider=9router, model=general-agent
model: mistral/mistral-large-latest
model: anthropic/claude-3.5-sonnet
```

**Как это работает:**
1. В `agent.yaml` указывается `model: provider/model`
2. Agent Manager парсит: `9router/general-agent` → provider=`9router`, model=`general-agent`
3. Provider резолвится из `providers.yaml`
4. Если провайдер не найден — fallback на дефолтный

**9router** — локальный прокси, предоставляющий доступ к моделям:
- `9router/hermes-agent` — Hermes (по умолчанию)
- `9router/summarise-agent` — для суммаризации

**Fallback цепочка:**
- Запрошенный провайдер → Mistral → дефолтный

---

## 🔄 Hot-Reload Config

Конфигурация агентов и провайдеров **автоматически перезагружается** при изменении файлов:

```
ConfigWatcher (polling 5s)
    ↓
providers.yaml изменён → registry.reload()
agents.yaml изменён → перезагрузка агентов
tools.yaml изменён → перезагрузка инструментов
```

**Ручная перезагрузка:**
```bash
POST /api/admin/reload
# → перечитывает providers.yaml
```

---

## 📋 Роли (roles.yaml)

Роли определяют **уровень ответственности** агента.

```yaml
# ~/.synpin/config/roles.yaml
roles:
  - rolesid: управляющий      # slug-идентификатор
    name: Управляющий
    description: управляющий отделом
    color: '#f59e0b'

  - rolesid: сотрудник
    name: Сотрудник
    description: сотрудник отдела
    color: '#6a4b16'
```

### Типы ролей

| Роль | Описание | Кто может делегировать |
|---|---|---|
| **Worker** | Исполнитель задач | Глава отдела |
| **Head** | Глава канала/отдела | Совет директоров |
| **Director** | Стратег, член совета | Пользователь |

---

## 🏢 Департаменты (departments.yaml)

Департаменты определяют **область специализации** агента.

```yaml
# ~/.synpin/config/departments.yaml
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

## REST API

### Агенты

| Метод | URL | Описание |
|---|---|---|
| `GET` | `/api/agents` | Список всех агентов |
| `GET` | `/api/agents/{agentid}` | Получить агента |
| `POST` | `/api/agents` | Создать нового агента |
| `PUT` | `/api/agents/{agentid}` | Обновить агента |
| `DELETE` | `/api/agents/{agentid}` | Удалить агента (+ папку) |

### Создание агента (POST /api/agents)

```json
{
  "name": "Маркетолог",
  "role": "сотрудник",
  "department": "кодер",
  "model": "9router/general-agent",
  "description": "Продвижение продукта",
  "system_prompt": "Ты — Маркетолог...",
  "tone": "дружелюбный",
  "style": "креативный",
  "temperature": 0.8
}
```

Ответ: полный объект агента с `agentid`, `slug` и т.д.

### Роли и департаменты

| Метод | URL | Описание |
|---|---|---|
| `GET` | `/api/roles` | Список ролей |
| `PUT` | `/api/roles` | Заменить все роли |
| `GET` | `/api/departments` | Список департаментов |
| `PUT` | `/api/departments` | Заменить все департаменты |

---

## Внешние агенты

Внешние агенты (например, Hermes) подключаются через HTTP API и отображаются в том же списке.

```yaml
# ~/.synpin/config/external_agents.yaml
agents:
  hermes:
    name: Hermes
    type: hermes
    agentid: a1b2c3d4
    enabled: true
    role: director
    department: dev
```

### API для внешних агентов

| Метод | URL | Описание |
|---|---|---|
| `GET` | `/api/external-agents` | Список внешних агентов |
| `GET` | `/api/external-agents/detect` | Автодетект Hermes |
| `PUT` | `/api/external-agents/{slug}` | Обновить (включить/выключить) |

### Интеграция с Hermes

Hermes подключается через HTTP API server (порт 8642):

```bash
# Проверка доступности
curl http://localhost:8642/health

# Список моделей
curl http://localhost:8642/v1/models

# Чат (через SynPin proxy)
POST /api/chat/hermes/stream
```

---

## Управление через UI

### Вкладка "AI Агенты" в Настройках

1. **Роли и департаменты** — верхняя секция с добавлением/удалением
2. **Кнопка "＋ Создать агента"** — откроет модалку создания
3. **Карточки агентов** — сгруппированы по ролям
4. **Expanded overlay** — при наведении на карточку: настройки агента, вкл/выкл, удаление

### Модалка создания

Обязательное поле: **Имя**. Остальное опционально:
- Роль (выпадающий список)
- Департамент (выпадающий список)
- Модель (из подключённых провайдеров, combo формат)
- Описание
- System Prompt

### Валидация

При попытке создания с пустым обязательным полем:
- Поле подсвечивается красной рамкой
- Текст "Обязательное поле" под полем
- Кнопка "Создать" краснеет с анимацией

---

## Связь с другими документами

- [Память и сессии](memory-sessions.md) — как агент хранит знания
- [Каналы и иерархия](channels-hierarchy.md) — где агент работает
- [Конфигурация](configuration.md) — YAML-конфиги системы
- [Интеграции](integrations.md) — Hermes, внешние агенты

---

*Агент без личности — инструмент. Агент с личностью — коллега.*
