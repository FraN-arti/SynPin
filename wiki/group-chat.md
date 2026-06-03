# 💬 Group Chat Engine

## Концепция

Агенты обсуждают задачу **перед** действием — но только в режиме "команда" или "группа".

```
Пользователь: "Создай API для L2 сервера"
        ↓
    Router → режим: команда (3 агента)
        ↓
┌─────────────────────────────────────────┐
│  Архитектор: "Предлагаю FastAPI + JWT"  │
│  Программист: "Хорошо. Ещё rate limit"  │
│  Ревьюер: "В прошлый раз забыли логи"   │
│  Архитектор: "Согласен. Итоговый план:" │
└─────────────────────────────────────────┘
        ↓
   Консенсус достигнут → Действие
        ↓
  Программист пишет код → Ревьюер проверяет
```

---

## Режимы Router

| Режим | Обсуждение | Когда |
|-------|-----------|-------|
| **Делегат** | ❌ Нет | Простая задача: "напиши тесты", "прочитай файл" |
| **Команда** | ✅ Да, короткое | Средняя задача: "создай API endpoint" |
| **Группа** | ✅ Да, полное | Сложная задача: "спроектируй микросервис" |

Конфигурация задаётся в настройках, не хардкод.

---

## Каналы

Каждый канал — **отдельный каталог** с файлами.

```
teams/
├── engineering/
│   ├── MEMORY.md               # память канала
│   └── sessions/
│       ├── 2026-06-03_api.md   # командная сессия
│       └── 2026-06-02_deploy.md
├── design/
│   ├── MEMORY.md
│   └── sessions/
│       └── 2026-06-03_ui.md
└── devops/
    ├── MEMORY.md
    └── sessions/
        └── 2026-06-03_ci.md
```

### Идентификаторы каналов

Каналы используют ID-based имена (как агенты):
- `engineering` — инженерный канал
- `design` — дизайн-канал
- `devops` — девопс-канал

---

## Иерархия контекста

### Координатор vs Исполнители

| Роль | Что видит | Зачем |
|------|-----------|-------|
| **Координатор канала** | Полный диалог + shared memory | Принимает стратегические решения |
| **Агент-исполнитель** | Свою задачу + релевантные решения | Не перегружается контекстом |

### Пример

```
Канал: engineering
Координатор: architect (видит ВСЁ)

Участники:
├── developer (видит свою часть: "напиши auth endpoint")
├── reviewer (видит свою часть: "проверь код")
└── tester (видит свою часть: "напиши тесты")
```

### Как работает

1. Координатор получает полный диалог
2. Разбивает на подзадачи
3. Каждому исполнителю — только его часть
4. Исполнители работают параллельно
5. Координатор собирает результаты

---

## Механизм обсуждений

### 1. Message Queue
- Асинхронная очередь сообщений
- Приоритеты по ролям (архитектор говорит первым при проектировании)
- Таймауты на ответ (агент не отвечает → пропуск или retry)

### 2. Turn Management
- Кто говорит сейчас — определяется Router'ом
- Следующий — зависит от контекста сообщения
- Пример: архитектор предложил → программист комментирует → ревьюер проверяет

### 3. Consensus Building
- Все согласны → действие
- Есть разногласия → дополнительный раунд
- Таймаут → решение большинства или эскалация

### 4. Conflict Resolution
- Арбитр (назначенный агент или пользователь)
- Голосование
- Эскалация к пользователю при deadlock

---

## Интеграция с памятью

### Перед обсуждением

Каждый агент загружает контекст из памяти:

```python
# Архитектор начинает обсуждение
context = memory.search(
    query="API architecture best practices",
    n_results=3,
    source="shared"
)
# → "Используй JWT + refresh tokens", "Добавляй rate limiting"

architect.propose(f"На основе опыта: {context}")
```

### После обсуждения

Результат записывается в память:

```python
memory.store(
    type="decision",
    content="FastAPI + JWT + rate limiting + structured logging",
    agents=["architect", "programmer", "reviewer"],
    task_id="task_042"
)
```

### Память канала

```markdown
# Shared Team Memory — engineering

## Collective Lessons
- Все агенты: при работе с API всегда проверять auth middleware
- developer: FastAPI middleware должен быть перед роутами

## Project Standards
- YAML для конфигов
- Pydantic v2 для валидации
- TypeScript strict mode в React
```

---

## WebSocket стриминг

Каждое сообщение в обсуждении стримится в UI:

```json
{
  "type": "group_message",
  "channel": "engineering",
  "task_id": "task_042",
  "agent": "architect",
  "message": "Предлагаю FastAPI + JWT auth",
  "timestamp": "2026-05-31T18:30:00Z"
}
```

UI показывает:
- Кто говорит
- Что предлагает
- Статус обсуждения (discussion / consensus / conflict)

---

## Командные сессии

Командные сессии хранятся в `teams/*/sessions/`.

### Формат файла

```markdown
# Session: API Redesign

**Channel:** engineering
**Started:** 2026-06-03 14:30
**Participants:** architect, developer, reviewer
**Task:** Спроектируй API для авторизации

---

**Architect:** Предлагаю JWT-based auth с refresh tokens.

**Developer:** Хорошо. Ещё rate limiting на login.

**Reviewer:** В прошлый раз забыли логи. Добавим structured logging.

**Architect:** Согласен. Итоговый план: JWT + rate limiting + logging.

---

**Outcome:** success
**Summary:** JWT auth + refresh tokens + rate limiting + structured logging
**Key Decisions:**
- JWT с expiry 15min для access token
- Refresh token в httpOnly cookie
- Rate limiting через SlowAPI
```

### Формат имени файла

```
YYYY-MM-DD_short-description.md
```

---

## Автоматическое извлечение фактов

Из командных сессий извлекаются:

| Тип | Куда записывается |
|-----|-------------------|
| **Решения** | `teams/*/MEMORY.md` + `shared/MEMORY.md` |
| **Ошибки** | `agents/*/MEMORY.md` (Anti-patterns) + `shared/MEMORY.md` |
| **Факты** | `agents/*/facts/YYYY-MM-DD_topic.md` |
| **Паттерны** | `agents/*/MEMORY.md` (Patterns) |

---

*Обсуждение — это не баг. Это фича.*
