# 📊 Web UI

## Текущая реализация
Веб-интерфейс SynPin — **React SPA** с чатом, otdel-чатом и настройками.

### Стек

| Компонент | Технология |
|-----------|------------|
| Фреймворк | React 19 + Vite 6 |
| Язык | TypeScript 5.7 (strict) |
| Стили | Tailwind CSS 4 |
| Real-time | WebSocket (single /ws, multiplexed) |
| HTTP | fetch API |
| Drag & Drop | @dnd-kit/core |
| Markdown | Модульный рендерер |

---

## Страницы

### 1. Chat (основная)
- Стриминг ответов в реальном времени (WebSocket)
- Tool Timeline — коллапсируемый список действий
- Markdown рендеринг
- Выбор агента (SynPin + внешние)
- История сообщений (персистентная)
- Эмодзи-пикер

### 2. Otdel Chat (чат отдела)
- Изолированный чат для каждого отдела
- @mentions — обращения через @Имя
- Streaming chunks через WebSocket (otdel:chunk)
- Thinking indicators — показывает кто думает
- Compaction indicators — уведомления о компакции
- Tool calls — отображение вызовов инструментов агентов
- Цвета агентов — по цвету департамента
- Head/Worker визуальное разделение

### 3. Settings
- **Основное** — общие настройки (только просмотр)
- **Агенты** — каталог агентов, CRUD, выбор модели (provider/model)
- **Провайдеры** — каталог LLM-провайдеров, CRUD
- **Память** — MemorySection (USER.md просмотр, компакция, сессии)
- **Каналы** — настройки каналов связи (Feishu подключён)
- **Отделы** — departments tab, draggable в виджет-зону
- **Скиллы** — placeholder

### 4. Widget Zone
- WidgetDropZone — зона для drag-and-drop виджетов
- Только departments tab доступен для перетаскивания

---

## Компоненты

```
web/src/
├── App.tsx                    ← основной компонент (chat + settings + DndContext)
├── config.ts                  ← API_BASE, WS_URL
├── main.tsx                   ← точка входа
├── index.css                  ← стили
├── components/
│   ├── SettingsPage.tsx       ← страница настроек (7 вкладок)
│   ├── OtdelChatView.tsx      ← чат отдела (WebSocket streaming)
│   ├── OtdelSettingsPanel.tsx  ← настройки отдела (Head, Workers, Compaction)
│   ├── WidgetDropZone.tsx     ← drag-and-drop виджеты (departments)
│   ├── MemorySection.tsx      ← секция памяти (USER.md, компакция)
│   ├── MarkdownRenderer.tsx   ← рендерер markdown
│   └── EmojiPicker.tsx        ← пикер эмодзи
├── hooks/
│   └── useWebSocket.ts       ← WebSocket hook (connect, reconnect, events)
├── lib/
│   ├── emoji.ts               ← утилиты эмодзи
│   ├── providers.ts           ← утилиты провайдеров (PROVIDER_CATALOG)
│   └── markdown.ts            ← утилиты markdown
└── images/
    └── synpin.png             ← логотип
```

---

## WebSocket

### useWebSocket hook

```typescript
const { send, on, connected, reconnecting } = useWebSocket()

// Подписка на события
on('chat:chunk', (msg) => { /* стриминг текста */ })
on('otdel:message', (msg) => { /* новое сообщение в отделе */ })
on('otdel:thinking', (msg) => { /* агент думает */ })
on('otdel:chunk', (msg) => { /* стриминг otdel ответа */ })
on('otdel:done', (msg) => { /* ответ готов */ })

// Отправка
send('chat:send', { agent_slug, message })
send('otdel:send', { otdel_id, message })
```

### Протокол

| Тип | Направление | Описание |
|---|---|---|
| `ping` | Client → Server | Heartbeat |
| `pong` | Server → Client | Heartbeat ответ |
| `chat:send` | Client → Server | Отправить сообщение |
| `chat:chunk` | Server → Client | Стриминг текста |
| `chat:tool_start` | Server → Client | Инструмент начат |
| `chat:tool_end` | Server → Client | Инструмент завершён |
| `chat:done` | Server → Client | Ответ готов |
| `otdel:send` | Client → Server | Сообщение в отдел |
| `otdel:message` | Server → Client | Новое сообщение отдела |
| `otdel:thinking` | Server → Client | Агент думает |
| `otdel:chunk` | Server → Client | Стриминг otdel |
| `otdel:done` | Server → Client | Ответ отдела готов |
| `otdel:compacting` | Server → Client | Компакция истории |
| `otdel:tool_start` | Server → Client | Инструмент в отделе |
| `otdel:tool_end` | Server → Client | Инструмент завершён |

### Reconnect

- Exponential backoff: 1s, 2s, 4s, 8s, 16s
- Автоматическое переподключение при обрыве
- Wildcard handlers (`*`) для глобальных обработчиков

---

## Виджеты статусов

| Статус | Цвет | Значение |
|--------|------|----------|
| 🟢 Active | Green | Агент работает |
| 🟡 Thinking | Yellow | Думает / ждёт LLM |
| 🔴 Error | Red | Ошибка |
| ⚪ Idle | Gray | Ожидает задачу |
| 💬 Discussing | Blue | Участвует в обсуждении |

---

## Themes (tweakcn)

Система тем через интеграцию с tweakcn:
- Импорт тем из tweakcn JSON формата
- Конвертация CSS переменных → JSON
- Хранение в `~/.synpin/themes/custom.json`
- Real-time preview

---

## Планируется

- **Dashboard** — обзор — агенты, статусы, последняя активность
- **Kanban-доска** — задачи с дедлайнами и этапами
- **Forum** — обсуждения агентов (идеи, решения)
- **Activity log** — история действий всех агентов
- **Responsive / Mobile** — media queries, hamburger menu
- **Keyboard shortcuts** — горячие клавиши

---

*Dashboard — это не роскошь. Это необходимость.*
