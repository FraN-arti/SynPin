# 🚀 Быстрый старт

## Установка (Production)

```powershell
iex (irm https://raw.githubusercontent.com/<user>/synpin/main/scripts/install.ps1)
```

Скрипт автоматически:
- Проверит Python 3.11+, uv, Node.js
- Создаст `~/.synpin/`
- Установит зависимости
- Соберёт Web UI
- Добавит команду `synpin` в PATH

После установки:

```bash
synpin setup    # Мастер настройки
synpin start    # Запустить сервер
```

## Разработка

```bash
git clone <repo-url>
cd synpin

# Зависимости
cd core && uv sync
cd ../web && npm install
cd ..

# Запуск dev-сервера (hot-reload)
dev.bat

# Остановка
dev.bat stop
```

Откроется одна консоль с обоими процессами:
```
  🚀 SynPin v0.1.0 — Development Mode

  Core:  http://0.0.0.0:8000/api
  Web:   http://localhost:5173
  Docs:  http://0.0.0.0:8000/docs
```

## CLI команды

| Команда | Описание |
|---------|----------|
| `synpin start` | Запустить сервер |
| `synpin stop` | Остановить сервер |
| `synpin status` | Статус сервера |
| `synpin config` | Показать конфигурацию |
| `synpin setup` | Мастер настройки |
| `synpin logs` | Логи сервера |
| `synpin version` | Версия |

## API

```bash
# Health check
curl http://127.0.0.1:8000/api/health
# → {"status": "ok", "version": "0.1.0"}

# Swagger docs
# → http://127.0.0.1:8000/docs
```

---

*Начни с малого. Расти постепенно.*
