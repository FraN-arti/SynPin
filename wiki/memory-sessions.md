# 🧠 Память и сессии

Система памяти SynPin построена по принципу Hermes — простые Markdown-файлы, прозрачная структура, лёгкий бэкап. Дополнена иерархией контекста (координатор vs исполнители) и датированными фактами.

---

## Структура на диске

```
~/.synpin/data/
├── state.db                      # SQLite: индекс + FTS5
├── agents/
│   ├── architect/
│   │   ├── MEMORY.md             # компактная память (frozen snapshot)
│   │   ├── state.json            # bookmarks per channel
│   │   ├── facts/                # датированные решения
│   │   │   ├── 2026-06-03_port-2099.md
│   │   │   └── 2026-06-02_api-convention.md
│   │   └── sessions/             # Markdown архив
│   │       └── 2026-06-03_api.md
│   └── developer/
│       ├── MEMORY.md
│       ├── state.json
│       ├── facts/
│       └── sessions/
├── teams/
│   └── engineering/
│       ├── MEMORY.md             # память канала
│       └── sessions/
│           └── 2026-06-03_api.md
└── shared/
    └── MEMORY.md                 # глобальная память команды
```

### Принцип

- **SQLite** — индекс сессий + FTS5 поиск (быстрый доступ)
- **Markdown** — human-readable архив (удобный бэкап, версионирование)
- **state.json** — per-agent bookmark (восстановление после рестарта)
- **Frozen snapshot** — системный промпт фиксируется при старте
- **Датированные факты** — агент видит актуальность решений

---

## MEMORY.md — компактная память

Долговременная память агента. **Не раздувается.**

```markdown
# Memory — architect

## Patterns
- Text-fallback: инструменты шлём как role="user"
- Порты: 2088 prod, 2099 dev
- Гит: всегда советоваться перед push

## Conventions
- YAML для конфигов
- Pydantic v2 для валидации

## Anti-patterns
- Не забывать auth middleware
- Не делать verbose логи
```

**Лимит:** ~2200 символов. Если не влезает — компакция.

---

## USER.md — предпочтения пользователя

```markdown
# User Profile — architect

## Communication
- Язык: русский
- Стиль: кратко, по делу

## Preferences
- Любит YAML вместо JSON
- Не любит verbose логи
```

**Лимит:** ~1375 символов.

---

## facts/*.md — датированные решения

Конкретные ситуативные решения с привязкой ко времени.

```markdown
# 2026-06-03_port-2099

## Контекст
Нужен порт для dev-сервера SynPin

## Решение
Используем 2099 — остальные закрыты

## Статус
Актуально
```

**Почему датированные файлы:** агент при поиске видит актуальность. Факт от вчера > факт от 3 месяцев назад.

**Структура имени:** `YYYY-MM-DD_topic.md`

---

## state.json — bookmark после рестарта

Каждый агент хранит файл-закладку. Это не сессия, это **указатель**.

```json
{
  "active_sessions": {
    "engineering": {
      "session_id": "2026-06-03_api-redesign",
      "last_position": 42,
      "last_action": "Решили использовать REST",
      "waiting_for": "ответ от developer"
    },
    "direct": {
      "session_id": "2026-06-03_chat-with-artur",
      "last_position": 8,
      "last_action": "Обсуждали архитектуру памяти",
      "waiting_for": null
    }
  },
  "last_compaction": "2026-06-03T12:00:00"
}
```

### Поток при рестарте

```
Рестарт SynPin / компа / браузера
    │
    ▼
Загрузка агента
    │
    ▼
Чтение state.json
    │
    ├──→ engineering: "я был в сессии api-redesign, позиция 42"
    │    → читаю последние N сообщений из sessions/2026-06-03_api-redesign.md
    │    → контекст восстановлен
    │
    └──→ direct: "я был в chat-with-artur, позиция 8"
         → читаю последние N сообщений
    
    ▼
Агент готов работать во всех каналах
```

### Поток при новом сообщении

```
Пользователь пишет в engineering
    │
    ▼
Router: "это для architect"
    │
    ▼
Агент читает state.json → engineering → session_id
    │
    ▼
Читает sessions/2026-06-03_api-redesign.md с позиции 42
    │
    ▼
Имеет полный контекст → отвечает
    │
    ▼
Обновляет state.json: last_position = 43
```

---

## Frozen Snapshot (из Hermes)

Системный промпт фиксируется при старте сессии и не меняется.

```
Старт сессии
    │
    ▼
Чтение MEMORY.md + USER.md + facts/*.md
    │
    ▼
Заморозка → frozen_snapshot (в system prompt)
    │
    ▼
Во время сессии:
    ├── Записи в MEMORY.md → обновляются на диске
    ├── НО НЕ меняют frozen_snapshot
    └── Tool-ответы показывают актуальное состояние
    │
    ▼
Конец сессии → следующая сессия читает заново
```

**Зачем:**
- Системный промпт стабилен → **prefix cache не ломается**
- Агент видит актуальное состояние через tool-ответы
- Нет race condition при конкурентных записях

---

## Иерархия контекста

### Координатор vs Исполнители

| Роль | Что видит |
|------|-----------|
| **Координатор** | Полная командная сессия + shared memory + персональная память |
| **Агент-исполнитель** | Своя задача + релевантные решения + shared memory |

Координатор ** должен** видеть всё — он принимает стратегические решения. Исполнитель видит только свою часть — чтобы не перегружать контекст.

### Командные сессии

Каждый канал — **свой каталог** с файлами.

```
teams/engineering/sessions/
├── 2026-06-03_api-redesign.md      # полный диалог всех участников
├── 2026-06-02_deploy-plan.md
└── ...
```

**Кто хранит полный контекст:** координатор канала.

**Исполнители** хранят только **свой** лог в персональных sessions/:
```
agents/developer/sessions/2026-06-03_api-redesign_my-part.md
```

Это не дублирование — это **проекция**. Координатор хранит оригинал, агент — свою релевантную часть.

---

## Компакция

### Аналогия с Git

```
Агенты работают параллельно (ветки)
    │
    ▼
Координатор компактирует (merge в main)
    ├── Суммаризует диалог
    ├── Извлекает факты → facts/*.md
    ├── Обновляет MEMORY.md
    │
    ▼
Следующая задача: агент читает обновлённый MEMORY.md (pull)
```

Агенты **не ждут** компакции. Они работают со своим контекстом. Когда начинают новую задачу — **обязательно** читают актуальный MEMORY.md.

### Шаблон компакции (из Hermes)

```markdown
[CONTEXT COMPACTION — REFERENCE ONLY]

## Active Task
Текущая задача

## Completed Actions
- Что сделано

## Active State
- Что происходит сейчас

## In Progress
- Что в работе

## Blocked
- Что заблокировано

## Key Decisions
- Какие решения приняты

## Resolved Questions
- Какие вопросы закрыты

## Pending User Asks
- Что ждёт ответа

## Relevant Files
- Какие файлы задействованы

## Remaining Work
- Что осталось
```

### Детерминированный fallback (из Hermes)

Если LLM недоступен для суммаризации — суммаризация по правилам:

```python
def deterministic_summary(messages):
    """Правила без LLM: берём первые/последние сообщения, извлекаем ключевое."""
    summary = []
    summary.append("## Active Task")
    summary.append(extract_last_task(messages))
    summary.append("## Key Decisions")
    summary.append(extract_decisions(messages))
    summary.append("## Relevant Files")
    summary.append(extract_files(messages))
    return "\n".join(summary)
```

---

## Типы сессий

### 1. Обычная сессия (default)

Стандартный диалог пользователя с агентом.

### 2. Checkpoint — подведение итогов

Запускается когда этап завершён или по запросу пользователя.

### 3. Retrospective — анализ ошибок

Специальная сессия для анализа того, что пошло не так.

---

## Авто-чистка

```yaml
# settings.yaml
sessions:
  max_age: 30d           # авто-удаление старше 30 дней
  max_per_agent: 100     # максимум 100 сессий на агента
  auto_summarize: true   # суммаризировать ключевые факты перед удалением
```

---

## Конкурентный доступ (из Hermes)

File locking для безопасной записи из нескольких сессий:

```python
with file_lock(MEMORY.md):
    # Перечитать с диска (другая сессия могла записать)
    fresh = read_file(MEMORY.md)
    # Модифицировать
    fresh.append(new_entry)
    # Записать
    write_file(MEMORY.md, fresh)
```

---

## Threat Scanning (из Hermes)

Защита от injection в память:

```python
# При записи в MEMORY.md:
scan_result = threat_scan(content)
if scan_result:
    return error("Blocked: potential injection pattern")
```

---

## Контекст агента при старте

```
1. personality.yaml — кто он, как общается
2. MEMORY.md — frozen snapshot (компактная память)
3. USER.md — frozen snapshot (предпочтения пользователя)
4. facts/*.md — датированные решения (актуальные)
5. skills.yaml + SKILL.md — активные скиллы
6. shared/MEMORY.md — коллективные знания
7. state.json — bookmarks per channel
```

---

*Память — не опция. Это фундамент.*
