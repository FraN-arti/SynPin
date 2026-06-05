# 📅 Roadmap

> Актуально: 2026-06-04. Фаза 0-1 (ядро) — 60% готово.

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

### Инструменты ✅ (8/16)
- [x] `terminal` — async shell exec (bash, 30s timeout)
- [x] `file_read` — чтение файлов (offset/limit, 1MB cap)
- [x] `file_write` — запись файлов (атомарная, mkdir)
- [x] `search_files` — ripgrep + Python fallback
- [x] `web_search` — DuckDuckGo (3 стратегии)
- [x] `code_exec` — sandboxed Python exec
- [x] `memory_read` — чтение MEMORY/USER/facts
- [x] `memory_write` — add/remove/replace entries
- [ ] `browser` — веб-браузер (Puppeteer/Playwright)
- [ ] `vision` — анализ изображений
- [ ] `message_send` — отправка сообщений в каналы
- [ ] `agent_call` — вызов другого агента
- [ ] `task_create` / `task_update` — управление задачами
- [ ] `skill_use` — использование навыков

### Чат ✅
- [x] SSE стриминг через fetch + ReadableStream
- [x] Native OpenAI function calling (tool_calls)
- [x] Tool execution loop (до 5 итераций)
- [x] Chat history persistence (JSON per agent+channel)
- [x] Compaction (token-based, configurable)
- [x] Memory + session context injection

### Провайдеры ✅
- [x] OpenAI-compatible (SSE streaming + tool_calls)
- [x] Anthropic Claude (SSE streaming)
- [x] Provider registry (YAML, hot-reload)
- [x] 40+ каталог провайдеров

### Агенты ✅
- [x] CRUD: create, read, update, delete
- [x] Roles & Departments management
- [x] Per-agent config (agent.yaml)
- [x] External agents (Hermes Agent detection)
- [x] Tools assignment per agent

### Веб-интерфейс ⚠️
- [x] Chat UI (стриминг, тэги, markdown, emoji)
- [x] Agent selection (SynPin + external)
- [x] Memory UI (USER.md просмотр, компакция, сессии)
- [x] Settings: Providers (каталог, CRUD)
- [x] Settings: Agents (каталог, CRUD)
- [ ] **Settings: Channels** — mock данные, нет бэкенда
- [ ] **Settings: General** — UI только, нет сохранения
- [ ] **Settings: Skills** — placeholder
- [ ] **Settings: String interpolation bug** — ~15 fetch() с одинарными кавычками

---

## Фаза 2: Стабилизация (ближайшее)

### Исправления
- [x] **Settings bug**: одинарные кавычки в fetch() → backtick interpolation ✅ dd36eed
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
- [ ] **Пропуск**: опция "я уже знаю что делаю" → переход к 기본ным настройкам

### Визуальная тема (по аналогии с OpenClaw)
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

- [ ] Удалить неиспользуемые зависимости (axios, zustand, react-router-dom, react-query)
- [ ] Удалить мёртвый код (emoji.ts: convertTextEmojis, sidebar навигация)
- [ ] Вынести hardcoded `D:\synpin` пути в конфиг
- [ ] Добавить Error Boundaries в React
- [ ] Исправить logger f-strings → %-форматирование
- [ ] Очистить wiki от устаревших ссылок

---

*План меняется. Философия — нет.*
