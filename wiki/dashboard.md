# 📊 Web UI

## Текущая реализация

Веб-интерфейс SynPin — **React SPA** с чатом и настройками.

### Стек

| Компонент | Технология |
|-----------|------------|
| Фреймворк | React 19 + Vite 6 |
| Язык | TypeScript 5.7 (strict) |
| Стили | Tailwind CSS 4 |
| Real-time | SSE Stream (fetch + ReadableStream) |
| HTTP | fetch API |

---

## Страницы

### 1. Chat (основная)
- Стриминг ответов в реальном времени
- Tool Timeline — коллапсируемый список действий
- Markdown рендеринг
- Выбор агента (SynPin + внешние)
- История сообщений (персистентная)
- Эмодзи-пикер

### 2. Settings
- **Providers** — каталог LLM-провайдеров, CRUD
- **Agents** — каталог агентов, CRUD
- **Roles & Departments** — roles.yaml, departments.yaml
- **General** — UI только, нет сохранения
- **Channels** — mock данные, нет бэкенда
- **Skills** — placeholder

---

## Компоненты

```
web/src/
├── App.tsx                    ← основной компонент (chat + settings)
├── main.tsx                   ← точка входа
├── index.css                  ← стили
├── components/
│   ├── SettingsPage.tsx       ← страница настроек
│   ├── MemorySection.tsx      ← секция памяти
│   ├── MarkdownRenderer.tsx   ← рендерер markdown
│   └── EmojiPicker.tsx        ← пикер эмодзи
├── lib/
│   ├── emoji.ts               ← утилиты эмодзи
│   ├── providers.ts           ← утилиты провайдеров
│   └── markdown.ts            ← утилиты markdown
└── images/
    └── synpin.png             ← логотип
```

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

## Real-time

SSE Stream через fetch + ReadableStream:
- `chunk` — кусок текста ответа
- `tool_start` — начало выполнения инструмента
- `tool_end` — завершение инструмента
- `done` — завершение ответа
- `error` — ошибка

---

## Планируется (Фаза 6)

- **Dashboard** — обзор — агенты, статусы, последняя активность
- **Kanban-доска** — задачи с дедлайнами и этапами
- **Forum** — обсуждения агентов (идеи, решения)
- **Activity log** — история действий всех агентов
- **Responsive / Mobile** — media queries, hamburger menu
- **Dark/Light theme** — переключение тем
- **Keyboard shortcuts** — горячие клавиши
- **Drag & drop** — kanban, agent reorder

---

*Dashboard — это не роскошь. Это необходимость.*
