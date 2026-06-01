# 🧠 Память и сессии

Система памяти SynPin построена по принципу Hermes — простые Markdown-файлы, прозрачная структура, лёгкий бэкап.

---

## Структура

```
~/.synpin/data/
├── agents/
│   ├── architect/
│   │   ├── MEMORY.md        # долговременная память
│   │   ├── USER.md          # предпочтения пользователя
│   │   └── sessions/        # история сессий
│   │       ├── 2025-06-01_architecture-api.md
│   │       └── 2025-06-02_microservice-design.md
│   ├── developer/
│   │   ├── MEMORY.md
│   │   ├── USER.md
│   │   └── sessions/
│   │       └── 2025-06-01_auth-tests.md
│   └── researcher/
│       ├── MEMORY.md
│       ├── USER.md
│       └── sessions/
│           └── ...
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

## Управление сессиями

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
```

---

## Контекст агента

При старте сессии агент загружает:

1. **MEMORY.md** — свои долговременные знания
2. **USER.md** — предпочтения пользователя
3. **Shared MEMORY.md** — коллективные знания команды
4. **Последние 5 сессий** — недавний контекст

Это даёт агенту полную картину без потери нити разговора.

---

## Расширенная память (опционально)

Когда администратор подключит — добавится поверх базовой:

| Тип | Описание |
|---|---|
| **ChromaDB** | Векторный поиск по памяти |
| **Embedding** | Семантический поиск (`all-MiniLM-L6-v2` и др.) |
| **Semantic search** | «Найди похожие ошибки» |

Базовая память (Markdown) работает всегда. Расширенная — опция.

---

*Память — не опция. Это фундамент.*
