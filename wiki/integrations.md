# 🔌 Интеграция внешних агентов

SynPin подключает **внешние агентские системы** как полноценных агентов в организации.

---

## Концепция

```
┌─────────────────────────────────────────────┐
│           SynPin Organization                │
│                                              │
│  Все агенты (в UI одним списком):            │
│    ├── 85n1yo4x (Архитектор) — SynPin       │
│    ├── 1f39sqld (Разработчик) — SynPin      │
│    ├── ix13aox3 (QA Инженер) — SynPin       │
│    └── hermes (Hermes) — внешний ←──────┐   │
│                                          │   │
│  Hermes Gateway (localhost:8642) ────────┘   │
│    ├── Своя память и навыки                  │
│    ├── Свои инструменты (terminal, file...)  │
│    └── Доступ к чатам SynPin                 │
└─────────────────────────────────────────────┘
```

Внешний агент — не просто LLM-провайдер. Это **полноценный агент** со своей:
- Памятью (MEMORY.md, сессии)
- Навыками (skills)
- Инструментами (terminal, file, browser...)
- Личностью

SynPin даёт ему **роль** в организации. Агент сохраняет свою идентичность.

---

## Поддерживаемые интеграции

### Hermes Agent (через HTTP API)

**Протокол:** HTTP API server (порт 8642).

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
    description: 'AI ассистент с полным доступом к инструментам'
    chat_url: "http://localhost:8642"
    models:
      - hermes-agent
```

### Как это работает

1. **Автодетект:** SynPin проверяет доступность `localhost:8642/health`
2. **Регистрация:** Если Hermes доступен, он добавляется в список агентов
3. **Чат:** Сообщения проксируются через `POST /api/chat/hermes/stream`
4. **Метаданные:** В ответе — модель, токены, имя агента

### API Endpoints

| Метод | URL | Описание |
|---|---|---|
| `GET` | `/api/external-agents` | Список внешних агентов |
| `GET` | `/api/external-agents/detect` | Автодетект Hermes |
| `PUT` | `/api/external-agents/{slug}` | Обновить (включить/выключить, роль, департамент) |

### Чат с Hermes

```bash
# Через SynPin proxy
POST /api/chat/hermes/stream
Content-Type: application/json

{
  "message": "Привет! Кто ты?",
  "model": "hermes-agent",
  "history": [],
  "temperature": 0.7
}
```

**Ответ:** SSE stream с чанками:

```
data: {"type": "chunk", "content": "Привет! "}
data: {"type": "chunk", "content": "Я Hermes..."}
data: {"type": "done", "model": "hermes-agent", "usage": {...}}
```

---

## Настройка Hermes

### 1. Установка Hermes Agent

```bash
# Установка
npm install -g @nousresearch/hermes-agent

# Первичная настройка
hermes setup
```

### 2. Конфигурация gateway

```bash
# Путь к .env
C:\Users\<user>\AppData\Local\hermes\.env

# Ключ API (нужен для работы)
HERMES_API_KEY=sk-...
```

### 3. Запуск gateway

```bash
hermes gateway
# Сервер стартует на :8642
```

### 4. Проверка доступности

```bash
curl http://localhost:8642/health
# {"status": "ok", "version": "..."}

curl http://localhost:8642/v1/models
# {"data": [{"id": "hermes-agent", ...}]}
```

---

## Управление внешними агентами

### Через UI

1. **Настройки → AI Агенты**
2. Секция "External Agents" (появится если Hermes доступен)
3. Карточка агента с:
   - Статусом (доступен/недоступен)
   - Типом (hermes)
   - Описанием
4. При наведении — expanded overlay:
   - Agent ID
   - Выбор роли (из roles.yaml)
   - Выбор департамента (из departments.yaml)
   - Модели
   - Вкл/выкл

### Через API

```bash
# Включить агента
curl -X PUT http://localhost:2088/api/external-agents/hermes \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'

# Сменить роль
curl -X PUT http://localhost:2088/api/external-agents/hermes \
  -H "Content-Type: application/json" \
  -d '{"role": "t0wy3h5qcd9m"}'
```

---

## Архитектура интеграции

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Frontend   │────▶│  SynPin API  │────▶│    Hermes    │
│  (React/Vite)│     │  (FastAPI)   │     │  Gateway     │
│              │     │              │     │  (:8642)     │
│  Chat Page   │     │  /api/chat/  │     │  /v1/chat/   │
│  Agent Select│     │  hermes/     │     │  completions │
│              │     │  stream      │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
```

### Поток сообщения

1. Пользователь пишет сообщение в чат
2. Frontend определяет активного агента
3. Если агент внешний → `POST /api/chat/hermes/stream`
4. SynPin API проксирует запрос в Hermes Gateway
5. Hermes обрабатывает и стримит ответ
6. Frontend отображает ответ в реальном времени

---

## Связь с другими документами

- [Агенты](agents.md) — структура агентов и API
- [Конфигурация](configuration.md) — YAML-конфиги
- [Каналы и иерархия](channels-hierarchy.md) — организация команды

---

*Внешние агенты — это не замена, а расширение. SynPin даёт роль, агент — экспертизу.*
