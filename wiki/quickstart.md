# 🚀 Быстрый старт

## Установка (Production)

```powershell
git clone https://github.com/FraN-arti/SynPin.git
cd SynPin
.\scripts\install.ps1
```

Скрипт автоматически:
- Проверит Python 3.11+, uv, Node.js, npm
- Создаст `~/.synpin/`
- Установит Python зависимости
- Установит npm зависимости и соберёт Web UI
- Добавит команду `synpin` в PATH

После установки:

```bash
synpin setup    # Мастер настройки
synpin start    # Запустить сервер
synpin doctor   # Проверить здоровье системы
```

## Разработка

```bash
git clone https://github.com/FraN-arti/SynPin.git
cd SynPin

# Зависимости (автоматически при первом запуске)
cd core && uv sync && cd ..

# Запуск dev-сервера (hot-reload, автоустановка npm)
dev.bat

# Остановка
dev.bat stop
```

Откроется одна консоль с обоими процессами:
```
  🚀 SynPin v0.2.2 — Development Mode

  Core:  http://0.0.0.0:2088/api
  Web:   http://localhost:2099
  Docs:  http://0.0.0.0:2088/docs
```

## CLI команды

| Команда | Описание |
|---------|----------|
| `synpin start` | Запустить сервер |
| `synpin stop` | Остановить сервер |
| `synpin status` | Статус сервера |
| `synpin config` | Показать конфигурацию |
| `synpin setup` | Мастер настройки |
| `synpin doctor` | Проверка здоровья (Python, Node, npm, порты, конфиги) |
| `synpin update` | Обновление с GitHub |
| `synpin logs` | Логи сервера |
| `synpin version` | Версия |

## Конфигурация

При установке создаются:
```
~/.synpin/
├── config/
│   ├── agents.yaml      # Агенты (НЕ в git)
│   ├── otdels.yaml      # Отделы (НЕ в git)
│   ├── providers.yaml   # API ключи (НЕ в git)
│   └── settings.yaml    # Настройки
├── data/                 # Данные агентов
├── logs/                 # Логи
└── repo/                 # Клон репозитория
```

Шаблоны конфигов: `core/synpin/config/templates/`

## API

```bash
# Health check
curl http://127.0.0.1:2088/api/health
# → {"status": "ok", "version": "0.2.2"}

# Swagger docs
# → http://127.0.0.1:2088/docs
```

---

*Начни с малого. Расти постепенно.*
