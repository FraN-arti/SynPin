# 🧠 Память и сессии

Система памяти SynPin построена по принципу Hermes — простые Markdown-файлы, прозрачная структура, лёгкий бэкап.

---

## Структура

```
~/.synpin/data/
├── agents/
│   ├── architect/
│   │   ├── MEMORY.md        # долговременная память
│   │   ├── personality.yaml # ВСЁ: агент + пользователь
│   │   ├── skills.yaml      # подключённые скиллы
│   │   └── sessions/        # история сессий
│   ├── developer/
│   │   ├── MEMORY.md
│   │   ├── personality.yaml
│   │   ├── skills.yaml
│   │   └── sessions/
│   └── researcher/
│       ├── MEMORY.md
│       ├── personality.yaml
│       ├── skills.yaml
│       └── sessions/
└── shared/
    └── MEMORY.md            # общие знания команды
```

### Принцип

- **Каждый агент — изолирован.** Своя память, свои сессии, свой контекст.
- **MEMORY.md — долговременная память.** Факты, уроки, решения.
- **USER.md — предпочтения пользователя** для этого конкретного агента.
- **Сессии — история взаимодействий.** Markdown-файлы, читаемые человеком.
- **Shared MEMORY.md — коллективное обучение.** Ошибка одного = знание всех.

---

## MEMORY.md

Долговременная память агента. Заполняется автоматически + вручную.

```markdown
# Agent Memory — architect

## Facts
- Проект на FastAPI + React
- Порт 2088 для API, 2099 для Vite dev
- Пользователь предпочитает YAML конфиги
- LM Studio запущен на localhost:1234

## Lessons Learned
- При проектировании API всегда учитывать auth middleware первым
- FastAPI dependencies — лучший способ для cross-cutting concerns
- Пользователь не любит verbose логи

## Active Decisions
- Используем Pydantic v2 для валидации
- ChromaDB для векторной памяти (когда подключим)
- JWT для авторизации с refresh tokens

## Past Errors
- 2025-06-01: Забыл про CORS middleware → добавлен в базовый шаблон
- 2025-06-02: Не учёл rate limiting → добавлен как обязательный пункт
```

### Секции

| Секция | Описание | Кто заполняет |
|---|---|---|
| `Facts` | Факты о проекте, окружении, предпочтениях | Агент + пользователь |
| `Lessons Learned` | Уроки из ошибок и успехов | Агент (автоматически) |
| `Active Decisions` | Текущие архитектурные решения | Агент |
| `Past Errors` | Прошлые ошибки и как были исправлены | Агент (автоматически) |

---

## USER.md

Предпочтения пользователя для конкретного агента.

```markdown
# User Profile — architect

## Communication
- Язык: русский
- Стиль: кратко, по делу
- Предпочитает схемы и диаграммы

## Preferences
- Любит YAML вместо JSON для конфигов
- Не любит verbose логи
- Хочет видеть процесс обсуждения, не только результат

## Project Context
- Работает над SynPin — агентский фреймворк
- Стек: Python/FastAPI + React/Vite
- Локальный-first, данные не уходят наружу
```

---

## Сессии

Каждое взаимодействие агента с пользователем — отдельная сессия в Markdown.

```markdown
# Session: Архитектура API для авторизации

**Agent:** architect
**Started:** 2025-06-01 14:30
**Ended:** 2025-06-01 14:45
**Task:** Спроектируй API для авторизации

---

**User:** Спроектируй API для авторизации

**Architect:** Предлагаю JWT-based auth с refresh tokens.
Вот схема:

1. POST /auth/login → access_token + refresh_token
2. POST /auth/refresh → новый access_token
3. POST /auth/logout → инвалидация refresh_token

**User:** А что насчёт rate limiting?

**Architect:** Добавим middleware на уровне FastAPI:
- 10 запросов/мин на login
- 3 запроса/мин на refresh

---

**Outcome:** success
**Summary:** JWT auth + refresh tokens + rate limiting middleware
**Key Decisions:**
- JWT с expiry 15min для access token
- Refresh token в httpOnly cookie
- Rate limiting через SlowAPI
```

### Формат имени файла

```
YYYY-MM-DD_short-description.md
```

Примеры:
- `2025-06-01_architecture-api.md`
- `2025-06-02_auth-tests.md`
- `2025-06-03_bugfix-404.md`

---

## Shared MEMORY.md

Общая память команды. Ошибка одного агента автоматически записывается сюда — другие агенты видят и не повторяют.

```markdown
# Shared Team Memory

## Collective Lessons
- Все агенты: при работе с API всегда проверять auth middleware
- developer: FastAPI middleware должен быть перед роутами
- architect: При проектировании учитывать rate limiting с самого начала

## Project Standards
- YAML для конфигов
- Pydantic v2 для валидации
- TypeScript strict mode в React
- Тесты обязательны для API endpoints

## Known Issues
- CORS middleware забыт в базовом шаблоне (исправлено 2025-06-01)
- Rate limiting не был в initial design (добавлено 2025-06-01)
```

---

## Типы сессий

Не все сессии одинаковы. Тип определяет как сессия влияет на память.

### 1. Обычная сессия (default)

Стандартный диалог пользователя с агентом.

```yaml
type: "session"
```

**Что происходит:**
- Агент ведёт диалог
- В конце ключевые факты/решения/ошибки автоматически сохраняются в MEMORY.md

### 2. Checkpoint — подведение итогов

Запускается когда этап завершён или по запросу пользователя.

```yaml
type: "checkpoint"
```

**Что происходит:**
- Агент анализирует все сессии с последнего checkpoint
- Агрессивная суммаризация → MEMORY.md
- Обновляет Active Decisions, Facts, Lessons Learned
- Записывает итоги этапа

**Когда использовать:**
- Завершена фаза разработки
- Пользователь просит: «подведи итоги»
- Автоматически после N выполненных задач

### 3. Retrospective — анализ ошибок

Специальная сессия для анализа того, что пошло не так.

```yaml
type: "retrospective"
```

**Что происходит:**
- Агент просматривает ошибки за период
- Формулирует Lessons Learned
- Записывает в **shared MEMORY.md** — чтобы другие агенты тоже знали
- Создаёт правила «не делать X в контексте Y»

**Когда использовать:**
- После критической ошибки
- Пользователь просит: «разбери что пошло не так»
- Автоматически при повторении одной ошибки 2+ раз

---

## Автоматическое извлечение фактов

Ключевая фишка — агент не просто ведёт диалог, а **извлекает знания** из него.

### Процесс

```
Диалог с пользователем
  ↓
Агент маркирует важное в процессе:
  📌 "Это важное решение" → decision
  ⚠️ "Это ошибка, не повторять" → lesson
  💡 "Это факт о проекте" → fact
  ✅ "Этап завершён" → checkpoint trigger
  ↓
В конце сессии → автосохранение:
  ┌─────────────────────────────────────┐
  │ MEMORY.md (агент)                   │
  │ ├── Facts: +новые факты             │
  │ ├── Lessons Learned: +уроки         │
  │ ├── Active Decisions: обновлены     │
  │ └── Past Errors: +ошибки            │
  ├─────────────────────────────────────┤
  │ shared/MEMORY.md (команда)          │
  │ └── Collective Lessons: +общие      │
  └─────────────────────────────────────┘
```

### Как агент «не наступает на грабли»

| Механизм | Что даёт |
|---|---|
| **MEMORY.md** при старте | Прошлые ошибки видны сразу |
| **Shared MEMORY.md** | Ошибки других агентов тоже видны |
| **Последние 5 сессий** | Контекст недавних решений |
| **Checkpoint** | Структурированные итоги → MEMORY.md |
| **Retrospective** | Анализ ошибок → правила для всех |

### Пример

```
Агент developer: "Забыл про auth middleware" → Ошибка → Past Errors
       ↓
shared/MEMORY.md: "Все агенты: auth middleware — первый пункт"
       ↓
Агент architect (новая сессия):
  Загружает shared MEMORY.md → видит правило → не повторяет
```

### Авто-чистка

```yaml
# settings.yaml
sessions:
  max_age: 30d           # авто-удаление старше 30 дней
  max_per_agent: 100     # максимум 100 сессий на агента
  auto_summarize: true   # суммаризировать ключевые факты перед удалением
```

### Команды (будут добавлены)

```bash
synpin sessions list              # список сессий агента
synpin sessions show <id>         # показать сессию
synpin sessions clean --older 7d  # удалить старые
synpin sessions summarize         # суммаризировать все сессии в MEMORY.md

# Типы сессий
synpin session start --type checkpoint     # начать checkpoint
synpin session start --type retrospective  # начать retrospective
```

---

## Контекст агента

При старте сессии агент загружает:

1. **personality.yaml** — кто он, как общается (см. [Агенты](agents.md))
2. **MEMORY.md** — свои долговременные знания
3. **USER.md** — предпочтения пользователя
4. **skills.yaml + SKILL.md** — активные скиллы (см. [Агенты](agents.md))
5. **Shared MEMORY.md** — коллективные знания команды
6. **Последние 5 сессий** — недавний контекст

Это даёт агенту полную картину без потери нити разговора.

---

## Поиск по памяти (FTS5 — по умолчанию)

Поиск по сессиям, MEMORY.md, задачам и форуму реализован на **SQLite FTS5** — полнотекстовый поиск без LLM.

### Почему FTS5

| Параметр | Значение |
|---|---|
| Скорость | Мгновенно (4500× быстрее LLM-поиска) |
| Зависимости | Нулевые — SQLite встроен в Python |
| Формат | Один файл `.db` — portable |
| Стоимость | Бесплатно, локально |

### Что индексируется

- Сессии агентов (`sessions/*.md`)
- MEMORY.md всех агентов
- Shared MEMORY.md
- Канбан-задачи (`data/tasks/*.yaml`)
- Форум-посты

### Операторы поиска

```
python AND fastapi          # оба термина
"exact phrase"              # точная фраза
auth OR login               # любой термин
deploy*                     # wildcard (deploy, deployment, deployed)
python NOT java             # исключение
```

### Пример API

```python
from core.search import SearchIndex

idx = SearchIndex(db_path="~/.synpin/data/search.db")

# Индексация
idx.index_session("architect", "2025-06-01_api-design.md", content)
idx.index_memory("architect", memory_md_content)
idx.index_task("TASK-001", "Реализовать auth", tags=["backend", "security"])

# Поиск
results = idx.search("auth middleware", limit=10)
# → [{file, agent, score, snippet, type}, ...]
```

### Расширенная память (опционально)

Поверх FTS5 можно подключить векторный поиск:

| Тип | Описание |
|---|---|
| **ChromaDB** | Векторный поиск по памяти |
| **Embedding** | Семантический поиск (`all-MiniLM-L6-v2` и др.) |
| **Semantic search** | «Найди похожие ошибки» по смыслу, не по ключевым словам |

Базовый поиск (FTS5) работает всегда. Векторный — опция.

---

*Память — не опция. Это фундамент.*
