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
# agents/85n1yo4x/agent.yaml
agentid: 85n1yo4x
name: Архитектор
description: 'Проектирует системы, принимает архитектурные решения'
role: t0wy3h5qcd9m          # rolesid из roles.yaml
department: 4lv3b3opepr8     # departmentsid из departments.yaml

personality:
  tone: профессиональный
  style: развернутый, с примерами
  traits:
    - аналитичный
    - внимателен к деталям
    - прагматичный

behavior:
  max_iterations: 10
  temperature: 0.7
  max_tokens: 40096

system_prompt: 'Ты — Архитектор...'
memory: {}
```

---

## 📋 Роли (roles.yaml)

Роли определяют **уровень ответственности** агента.

```yaml
# ~/.synpin/config/roles.yaml
roles:
  - rolesid: t0wy3h5qcd9m      # 12-символьный ID
    name: Техлид
    description: 'Руководит техническими решениями'
    color: '#f59e0b'

  - rolesid: 0xzkvsn954lt
    name: Разработчик
    description: 'Пишет код, делает рефакторинг'
    color: '#3b82f6'
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
  - departmentsid: 4lv3b3opepr8
    name: Разработка
    description: 'Backend, frontend, инфраструктура'
    color: '#22c55e'

  - departmentsid: ytue80l14hnk
    name: QA
    description: 'Тестирование, контроль качества'
    color: '#ef4444'
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
  "role": "t0wy3h5qcd9m",
  "department": "4lv3b3opepr8",
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
- Модель (из подключённых провайдеров)
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
