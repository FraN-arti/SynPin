# SynPin — Multi-Agent Framework

🚀 Open-source агентский фреймворк с разделённой архитектурой:
Python-ядро (FastAPI) + React Web UI.

## Установка

```powershell
iex (irm https://raw.githubusercontent.com/FraN-arti/SynPin/main/scripts/install.ps1)
```

## Использование

```bash
synpin start      # Запустить сервер
synpin stop       # Остановить
synpin status     # Статус сервера
synpin config     # Показать конфигурацию
synpin setup      # Мастер настройки
synpin logs       # Логи сервера
synpin version    # Версия
```

## Разработка

```bash
git clone https://github.com/FraN-arti/SynPin.git
cd synpin
dev.bat           # Запуск dev-сервера (hot-reload)
dev.bat stop      # Остановка
```

## Структура

```
synpin/
├── core/              # Python-ядро (FastAPI)
│   ├── synpin/        # Пакет: agents, memory, tools, router, engine
│   ├── api/           # REST API endpoints
│   ├── dev_server.py  # Dev supervisor (hot-reload)
│   └── pyproject.toml
├── web/               # React 19 + Vite 6 + Tailwind 4
├── wiki/              # Документация проекта
├── dev.bat            # Эмуляция CLI для разработки
└── install.ps1        # Скрипт установки
```

## Стек

- **Core:** Python 3.11+, FastAPI, uvicorn, ChromaDB
- **Web:** TypeScript 5.7, React 19, Vite 6, Tailwind 4
- **Embeddings:** nomic-embed-text-v1.5 (LM Studio)
