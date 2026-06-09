# SynPin Wiki

> *Это не инструмент. Это команда.*

## 📋 Оглавление

- [🎯 Философия](philosophy.md)
- [🏗️ Архитектура](architecture.md)
- [⚙️ Конфигурация](configuration.md)
- [🧠 Память и сессии](memory-sessions.md)
- [🛠 Инструменты](tools.md)
- [🤖 Агенты](agents.md)
- [🏢 Отделы](otdels.md)
- [🔌 Интеграции](integrations.md)
- [🚀 Быстрый старт](quickstart.md)
- [📅 Roadmap](roadmap.md)

---

## 🎯 Краткое описание

**SynPin** — платформа для создания агентных систем, где агенты:

- ✅ **Имеют память** — учатся на ошибках, накапливают опыт
- ✅ **Общаются друг с другом** — видишь процесс, не только результат
- ✅ **Специализированы** — каждый агент эксперт в своей области
- ✅ **Коллективно обучаются** — ошибки одного = знание всех
- ✅ **Мульти-модальны** — от простого делегата до полной инженерской группы
- ✅ **Организованы в отделы** — изолированные команды с Главами и работниками
- ✅ **Делегируют задачи** — Head Protocol: delegate → await → evaluate → decide

## 🏗️ Стек

| Слой | Технология |
|------|-----------|
| **Ядро** | Python 3.11+, FastAPI, uvicorn, pydantic |
| **Web UI** | React 19, Vite 6, TypeScript 5.7, Tailwind 4 |
| **Память** | SQLite FTS5 + Markdown |
| **WebSocket** | single `/ws`, multiplexed protocol |
| **Установка** | uv (Python) + npm (Web) |
| **Запуск** | `dev.bat` (dev) / `synpin start` (prod) |

## 📁 Структура

```
synpin/
├── core/              ← Python ядро (агенты, память, инструменты, API)
│   └── synpin/
│       ├── agents/    ← роли агентов
│       ├── memory/    ← FTS5 + Markdown + frozen snapshot
│       ├── tools/     ← инструменты (13 штук: 8 базовых + 5 Head Protocol)
│       ├── chat/      ← чат-роутер + провайдеры + WebSocket + otdel-чат
│       ├── config/    ← менеджер конфигурации (11 YAML файлов)
│       └── api/       ← FastAPI сервер + Stats + Themes
├── web/               ← React UI (чат + otdel-чат + настройки)
│   └── src/
│       ├── App.tsx    ← основной компонент
│       ├── components/← UI компоненты (8 штук)
│       ├── hooks/     ← useWebSocket hook
│       └── lib/       ← утилиты
└── wiki/              ← Эта документация
```

---

*Последнее обновление: 10 июня 2026*
