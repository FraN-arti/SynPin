# 📅 Roadmap

> Актуально: 2026-06-10. Фаза 0-1 (ядро) — ~95% готово. Фаза 2 — в процессе.

---

## Фаза 0: Фундамент ✅

- [x] Имя: **SynPin**
- [x] Структура проекта: `core/` + `web/`
- [x] Python core: FastAPI, uvicorn, pydantic
- [x] React UI: React 19, Vite 6, TypeScript 5.7
- [x] Dev-супервизор: `core/dev_server.py`
- [x] CLI: `synpin start/stop/status/setup/logs/version/update`
- [x] Install script: `scripts/install.ps1`
- [x] Конфигурация: `~/.synpin/config/` (YAML, hot-reload)
- [x] Wiki: философия, архитектура, конфигурация

---

## Фаза 1: Ядро (MVP)

### Память ✅
- [x] MEMORY.md + USER.md per agent
- [x] Frozen Snapshot (стабильный system prompt)
- [x] Датированные факты: `facts/YYYY-MM-DD_topic.md`
- [x] Shared USER.md: глобальный для всех агентов
- [x] File Locking: безопасный конкурентный доступ
- [x] Threat Scanning: защита от injection
- [x] Сессии: персистентная история (JSON на диске)
- [x] state.json: bookmarks per channel
- [x] Компакция: truncate при превышении context_window
- [x] Авто-сброс сессий (daily/timer/time + архивация)
- [x] Авто-запись памяти: агент proactively сохраняет
- [x] FTS5 full-text search по памяти
- [x] Memory API: 14+ REST эндпоинтов

### Инструменты ✅ (13/20)
- [x] `terminal` — async shell exec (bash, 30s timeout)
- [x] `file_read` — чтение файлов (offset/limit, 1MB cap)
- [x] `file_write` — запись файлов (атомарная, mkdir)
- [x] `search_files` — ripgrep + Python fallback
- [x] `web_search` — DuckDuckGo (3 стратегии)
- [x] `code_exec` — sandboxed Python exec
- [x] `memory_read` — чтение MEMORY/USER/facts
- [x] `memory_write` — add/remove/replace entries
- [x] `head_delegate` — делегирование задач воркерам ✅ (Head Protocol)
- [x] `head_await` — ожидание ответов от воркеров ✅ (Head Protocol)
- [x] `head_evaluate` — quality gate ✅ (Head Protocol)
- [x] `head_retry` — ретрай упавшего воркера ✅ (Head Protocol)
- [x] `head_decide` — стратегическое решение ✅ (Head Protocol)
- [ ] `browser` — веб-браузер (Puppeteer/Playwright)
- [ ] `vision` — анализ изображений
- [ ] `message_send` — отправка сообщений в каналы
- [ ] `agent_call` — вызов другого агента
- [ ] `task_create` / `task_update` — управление задачами
- [ ] `skill_use` — использование навыков

### Чат ✅
- [x] SSE стриминг через fetch + ReadableStream
- [x] Native OpenAI function calling (tool_calls)
- [x] Text fallback parser (5 паттернов для моделей без native function calling)
- [x] Tool execution loop (до 5 итераций)
- [x] Chat history persistence (JSON per agent+channel)
- [x] Compaction (token-based, configurable)
- [x] Memory + session context injection
- [x] Background task system (asyncio.Task + Queue)
- [x] Polling recovery (после перезагрузки страницы)

### WebSocket ✅
- [x] Single `/ws` endpoint (мультиплексированный)
- [x] chat:send / chat:chunk протокол
- [x] otdel:send / otdel:chunk / otdel:thinking / otdel:done
- [x] ws_manager (connection manager)
- [x] useWebSocket React hook (reconnect, events)

### Провайдеры ✅
- [x] OpenAI-compatible (SSE streaming + tool_calls)
- [x] Anthropic Claude (SSE streaming)
- [x] Provider registry (YAML, hot-reload через ConfigWatcher)
- [x] 40+ каталог провайдеров
- [x] Model combos: `provider/model` формат (9router/hermes-agent и т.д.)

### Агенты ✅
- [x] CRUD: create, read, update, delete
- [x] Roles & Departments management
- [x] Per-agent config (agent.yaml)
- [x] External agents (Hermes Agent detection)
- [x] Tools assignment per agent

### Отделы (Otdels) ✅
- [x] departments.yaml — Вахтан, Сузумебачи, Волокита, Разработка
- [x] otdels.yaml — Грахатули, Обсуждение аниме
- [x] Head (управляющий) / Worker (работник) roles
- [x] @mention routing — Глава видит всё, работники при упоминании
- [x] Otdel Chat Router (HTTP + WebSocket)
- [x] Compaction per otdel (compaction_limit, keep_recent)
- [x] OtdelChatView + OtdelSettingsPanel (React)

### Безопасность ✅
- [x] Security sandbox: configurable `allowed_directories` через `security.yaml`
- [x] command_timeout для shell команд
- [x] file_read limits (1MB cap)

### Stats API ✅
- [x] `/api/stats/overview` — summary cards (агенты, сообщения, uptime)
- [x] `/api/stats/usage` — статистика по моделям и агентам
- [x] `/api/stats/tools` — использование инструментов
- [x] `/api/stats/sessions` — список сессий

### Themes ✅
- [x] `/api/themes/*` — tweakcn интеграция
- [x] Импорт тем из tweakcn JSON формата
- [x] Конвертация CSS → JSON переменные

### Веб-интерфейс ✅
- [x] Chat UI (стриминг, тэги, markdown, emoji)
- [x] Agent selection (SynPin + external)
- [x] Memory UI (USER.md просмотр, компакция, сессии)
- [x] Settings: Providers (каталог, CRUD)
- [x] Settings: Agents (каталог, CRUD)
- [x] Settings: Departments (отделы, drag-and-drop в виджет-зону)
- [x] Settings: Channels (Feishu подключён)
- [x] Otdel Chat UI (WebSocket streaming, thinking, compaction)
- [x] WidgetDropZone (drag-and-drop departments)
- [ ] **Settings: General** — UI только, нет сохранения
- [ ] **Settings: Skills** — placeholder

---

## Фаза 2: Стабилизация (ближайшее)

### Исправления
- [x] **Settings bug**: одинарные кавычки в fetch() → backtick interpolation ✅ dd36eed
- [x] **Duplicate messages fix** — исправлены дублирующиеся сообщения ✅
- [x] **Background tasks** — asyncio.Task + Queue для фоновых LLM-задач ✅
- [x] **Polling recovery** — переподключение после перезагрузки страницы ✅
- [x] **Security sandbox configurable** — allowed_directories через security.yaml ✅
- [x] **WebSocket** — single /ws endpoint, multiplexed protocol ✅
- [x] **Otdels** — departments + otdels + Head/Worker flow ✅
- [x] **Head Protocol** — 5 инструментов для Главы ✅
- [x] **Stats API** — overview, usage, tools, sessions ✅
- [x] **Themes** — tweakcn import/export ✅
- [ ] **Settings: Channels** — подключить к бэкенду
- [ ] **Settings: General** — подключить сохранение
- [x] **Мёртвый код**: axios, zustand, react-router-dom, react-query → удалён ✅ dd36eed
- [ ] **memory_write tool**: memory_read инжект в промпт (агент не знает когда вызывать)
- [ ] **Search shared**: FTS5 индексация shared/USER.md

### CLI и дизайн
- [ ] **CLI `synpin`**: дизайн в консоли (цвета, форматирование, брендинг)
- [ ] **CLI проверки и фолбеки**: что если сервер запущен/порт занят/Python не установлен
- [ ] **Автообновление**: `synpin update` — надёжный rollback, проверка версий, бэкап

### Onboarding (первый запуск)
- [ ] **Стартовое окно**: приветственная страница при первом запуске (нет конфигов)
- [ ] **Мастер настройки**: пошаговый setup wizard (провайдер, модель, имя пользователя)
- [ ] **Пропуск**: опция "я уже знаю что делаю" → переход к базовым настройкам

### Визуальная тема
- [ ] **Тема**: dark/light переключение
- [ ] **Custom Theme Studio**: hue slider → 60+ CSS переменных через OKLCH
- [ ] **6 пресетов**: Ocean, Spring, Sunset, Forest, Purple, Mocha
- [ ] **Advanced panel**: 5 групп цветов (Background, Text, Accent, Border, Semantic)
- [ ] **Per-variable overrides** с reset
- [ ] Хранение в localStorage, real-time preview
- [ ] Оранжевый (hue=25) как дефолтная стартовая позиция

### Тесты
- [ ] pytest конфигурация
- [ ] Unit-тесты: memory/store.py (CRUD, file locking, char limits)
- [ ] Unit-тесты: tools (terminal, file_read, file_write, memory_read/write)
- [ ] Unit-тесты: chat/router.py (compaction, session management)
- [ ] Integration test: полный цикл chat → tool → response
- [ ] Vitest конфигурация
- [ ] React component tests

---

## Фаза 3: Мультиагентность

### Командные каналы (Отделы)
> 📌 **Отделы реализованы** (otdels.yaml, otdel_chat_router.py, Head Protocol).
> Осталось:

- [x] departments.yaml — RGB цвета, slug ID
- [x] otdels.yaml — head, workers, compaction
- [x] @mention routing — Head видит всё, Workers при упоминании
- [x] Head Protocol — delegate, await, evaluate, retry, decide
- [x] Otdel Chat UI — WebSocket streaming
- [ ] Context injection per department (специфичный контекст для каждого департамента)
- [ ] Cross-department delegation (совет отделов)

**Настройки: Каналы связи** — глобальные настройки каналов:
- [x] channels.yaml — Feishu подключён (WebSocket)
- [ ] Каждый тип канала: required_fields (bot_token, webhook, и т.д.)
- [ ] Modes: polling / webhook для Telegram, Discord и т.д.

### Router / Delegation
- [ ] Базовый Router: задача → агент → результат
- [ ] Делегат: простой delegation (one agent → one agent)
- [ ] Командный режим: обсуждение → консенсус → действие
- [ ] Каналы отделов с главами (@mention)
- [ ] Совет отделов (cross-channel делегирование)
- [ ] Совет директоров (стратегия)

### Engine
- [ ] Вынести agent loop из chat/router.py в engine/
- [ ] ReAct-луп (think → act → observe) — опциональный
- [ ] Tool execution middleware (rate limits, audit log)

---

## Фаза 4: Интеграции

### MCP
- [ ] MCP-клиент в core
- [ ] MCP-server для SynPin (REST → MCP bridge)
- [ ] Система плагинов для инструментов

### Уведомления
- [ ] Notification API (CRUD)
- [ ] WebSocket push (или SSE polling)
- [ ] Email/webhook интеграция
- [ ] UI: колокольчик + dropdown

### Контекст
- [ ] Текущее время/дата в системном промпте
- [ ] Статус других агентов ("коллега X уже ответил")
- [ ] Глобальные заметки/задачи

---

## Фаза 5: Multi-account

### Авторизация
- [ ] Login/Registration UI
- [ ] JWT токены
- [ ] Per-user USER.md (персональный профиль)
- [ ] Per-user agent configs
- [ ] Role-based access (admin/user)

---

## Фаза 6: Web UI расширение

### Страницы
- [ ] **Dashboard**: обзор — агенты, статусы, последняя активность
- [ ] **Kanban-доска**: задачи с дедлайнами и этапами
- [ ] **Forum**: обсуждения агентов (идеи, решения)
- [ ] **Activity log**: история действий всех агентов

### UX
- [ ] Responsive / Mobile (media queries, hamburger menu)
- [ ] Dark/Light theme (сейчас только dark)
- [ ] Keyboard shortcuts
- [ ] Drag & drop (kanban, agent reorder)

---

## Фаза 7: Production

- [ ] Docker / деплой
- [ ] Cron-задачи и расписания
- [ ] Экспорт/импорт памяти
- [ ] Rate limiting / abuse protection
- [ ] Linting + CI/CD
- [ ] Release v0.1 → v1.0

---

## Технический долг

- [x] ~~Удалить неиспользуемые зависимости (axios, zustand, react-router-dom, react-query)~~ ✅
- [x] ~~Удалить мёртвый код (emoji.ts: convertTextEmojis, sidebar навигация)~~ ✅
- [x] ~~Вынести hardcoded `D:\synpin` пути в конфиг~~ ✅ (security.yaml)
- [ ] Добавить Error Boundaries в React
- [ ] Исправить logger f-strings → %-форматирование
- [ ] Очистить wiki от устаревших ссылок

---

*План меняется. Философия — нет.*
