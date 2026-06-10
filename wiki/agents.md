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
│  🏢 Департамент  → departmentsid                │
│  🏗️ Отдел       → otdels.yaml (head/workers)   │
│  🧠 Память       → system prompt, описание      │
│  🎭 Характер     → tone, style, traits          │
│  🔧 Поведение    → temperature, max_tokens      │
│  📡 Провайдер    → LLM провайдер и модель       │
│                      (model combo: provider/model)│
│  🔧 Инструменты  → tools: [terminal, file...]   │
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
├── dept-001/          ← agentid = slug
│   ├── agent.yaml     ← личность и настройки
│   └── avatar.png     ← опционально
├── dept-002/
│   └── agent.yaml
└── agent-001/
    └── agent.yaml
```

### Почему agentid, а не имя?

- Кириллица в путях/URL — проблемы с совместимостью
- Имена могут дублироваться, agentid — уникален
- Короткий, компактный, ASCII-safe

---

## Структура agent.yaml

```yaml
# agents/agent-001/agent.yaml
agentid: agent-001
name: Backend Lead
description: ''
role: управляющий              # slug из roles.yaml
department: backend            # slug из departments.yaml
model: 9router/summarise-agent # combo формат: provider/model

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
model: 9router/hermes-agent    # Hermes
model: 9router/summarise-agent # Для суммаризации
model: 9router/thinking-agent  # Thinking модель
model: 9router/code-agent      # Кодинг
model: mistral/mistral-large-latest
model: anthropic/claude-3.5-sonnet
```

**Как это работает:**
1. В `agents.yaml` или `agent.yaml` указывается `model: provider/model`
2. Agent Manager парсит: `9router/hermes-agent` → provider=`9router`, model=`hermes-agent`
3. Provider резолвится из `providers.yaml`
4. Если провайдер не найден — fallback на дефолтный

**9router** — локальный прокси, предоставляющий доступ к моделям:
- `9router/hermes-agent` — Hermes (по умолчанию)
- `9router/summarise-agent` — для суммаризации
- `9router/thinking-agent` — thinking модель
- `9router/code-agent` — модель для кода

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

### Типы ролей

| Роль | Описание | Кто может делегировать |
|---|---|---|
| **Работник отдела** | Исполнитель задач | Глава отдела |
| **Управляющий** | Глава канала/отдела | Совет директоров |
| **Совет Директоров** | Стратег, член совета | Пользователь |

---

## 🏢 Департаменты (departments.yaml)

Департаменты определяют **область специализации** агента.

```yaml
# ~/.synpin/config/departments.yaml
departments:
  - departmentsid: dept-001
    name: Backend
    color: '#f97316'

  - departmentsid: dept-002
    name: Frontend
    color: '#7cf915'

  - departmentsid: dept-003
    name: Analytics
    description: Департамент аналитики и отчётов
    color: '#27166a'

  - departmentsid: dept-004
    name: DevOps
    description: Инфраструктура и деплой
    color: '#bbf73b'
```

---

## 🏗️ Отделы (otdels.yaml)

Агенты принадлежат к **отделам** — изолированным командам с Главой и работниками.

```yaml
# ~/.synpin/config/otdels.yaml
otdels:
  - otdelid: otdel-001
    name: Web Team
    description: Веб-разработка и фронтенд
    color: '#f915db'
    mentor_role: управляющий
    head: agent-001          # slug агента-Главы
    workers:                 # slug'ы работников
      - agent-002
      - agent-003
      - agent-004
```

> Подробнее: [Отделы](otdels.md)

### Глава vs Работник

| | Глава (Head) | Работник (Worker) |
|---|---|---|
| **Видит** | Все сообщения отдела | Только свои + указания Главы |
| **Инструменты** | Базовые + Head Protocol | Только базовые |
| **Делегирует** | Да (через @mention) | Нет |
| **Отчитывается** | Пользователю | Главе |

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
  "role": "работник-отдела",
  "department": "dept-001",
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

### Отделы

| Метод | URL | Описание |
|---|---|---|
| `GET` | `/api/otdels` | Список всех отделов |
| `GET` | `/api/otdels/{otdelid}` | Получить отдел |
| `PUT` | `/api/otdels/{otdelid}` | Обновить отдел (head, workers, compaction) |

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

### Вкладка "Агенты" в Настройках

1. **Роли и департаменты** — верхняя секция с добавлением/удалением
2. **Кнопка "＋ Создать агента"** — откроет модалку создания
3. **Карточки агентов** — сгруппированы по ролям
4. **Expanded overlay** — при наведении на карточку: настройки агента, вкл/выкл, удаление

### Модалка создания

Обязательное поле: **Имя**. Остальное опционально:
- Роль (выпадающий список)
- Департамент (выпадающий список)
- Модель (из подключённых провайдеров, combo формат: provider/model)
- Описание
- System Prompt

### Валидация

При попытке создания с пустым обязательным полем:
- Поле подсвечивается красной рамкой
- Текст "Обязательное поле" под полем
- Кнопка "Создать" краснеет с анимацией

---

## Связь с другими документами

- [Отделы](otdels.md) — структура отделов, Head Protocol
- [Память и сессии](memory-sessions.md) — как агент хранит знания
- [Каналы и иерархия](channels-hierarchy.md) — где агент работает
- [Конфигурация](configuration.md) — YAML-конфиги системы
- [Интеграции](integrations.md) — Hermes, внешние агенты

---

*Агент без личности — инструмент. Агент с личностью — коллега.*
