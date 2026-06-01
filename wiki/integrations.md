# 🔌 Интеграция внешних агентов

SynPin может подключать **внешние агентские системы** как полноценных агентов в организации.

---

## Концепция

Внешний агент — не просто LLM-провайдер. Это **полноценный агент** со своей:
- Памятью
- Навыками
- Инструментами
- Личностью

SynPin даёт ему **роль** в организации. Агент сохраняет свою идентичность.

```
┌─────────────────────────────────────────────┐
│           SynPin Organization                │
│                                              │
│  Board of Directors:                         │
│    ├── architect (director)                  │
│    └── hermes (director) ← внешний агент    │
│                                              │
│  Hermes получает:                            │
│    ├── Роль от SynPin: director              │
│    ├── Свою память из Hermes                 │
│    ├── Свои инструменты (terminal, file...)  │
│    └── Доступ к чатам, канбану, форуму       │
└─────────────────────────────────────────────┘
```

---

## Поддерживаемые интеграции

### 1. Hermes Agent (через ACP)

**Протокол:** Agent Client Protocol (ACP) — JSON-RPC через stdio.

```yaml
# ~/.synpin/config/providers.yaml
providers:
  hermes:
    type: "acp-agent"
    command: "hermes acp --stdio"
    agent_id: "hermes-main"
    role: "director"
```

**Что получает:**
- Память: `~/.hermes/data/MEMORY.md`, `USER.md`
- Скиллы: `~/.hermes/skills/`
- Инструменты: terminal, file, web, memory...
- Личность: из personality.yaml в Hermes

**Как работает:**
```
SynPin → запускает "hermes acp --stdio" → JSON-RPC → ответы с контекстом Hermes
```

**Статус:** 🟡 Требует разработки коннектора

---

### 2. OpenClaw

**Протокол:** TBD (исследовать)

```yaml
providers:
  openclaw:
    type: "external-agent"
    command: "openclaw agent --stdio"
    role: "developer"
```

**Что получает:**
- Свои навыки и память из OpenClaw
- Роль developer в SynPin
- Доступ к канбану и чатам отдела

**Статус:** 🔴 Планируется

---

### 3. Windsurf / Cursor / Copilot

**Протокол:** TBD (исследовать)

```yaml
providers:
  windsurf:
    type: "external-agent"
    command: "windsurf agent --stdio"
    role: "developer"
```

**Статус:** 🔴 Планируется

---

## Архитектура интеграции

### Внешний агент vs Внутренний агент

| | Внутренний агент | Внешний агент |
|---|---|---|
| **Память** | `~/.synpin/data/agents/` | Своя система (Hermes, OpenClaw...) |
| **Скиллы** | `~/.synpin/skills/` | Свои скиллы + SynPin |
| **Инструменты** | SynPin tools | Свои tools + SynPin tools |
| **Личность** | personality.yaml в SynPin | Своя личность + роль от SynPin |
| **Контекст** | Channel context | Channel context + свой контекст |

### Коннектор

```python
# core/integrations/acp_connector.py

class ACPConnector:
    """Подключается к внешнему агенту через ACP."""
    
    def __init__(self, config: dict):
        self.command = config["command"]
        self.agent_id = config["agent_id"]
        self.role = config["role"]
        self.process = None
    
    async def connect(self):
        """Запускает внешний агент как subprocess."""
        self.process = await asyncio.create_subprocess_exec(
            *shlex.split(self.command),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=sys.stderr
        )
    
    async def send_message(self, message: str, context: dict) -> str:
        """Отправляет сообщение внешнему агенту."""
        # JSON-RPC запрос
        request = {
            "jsonrpc": "2.0",
            "method": "prompt",
            "params": {
                "message": message,
                "context": context,  # роль, канал, задачи
            },
            "id": 1
        }
        # Отправка и получение ответа
        ...
    
    async def disconnect(self):
        """Завершает подключение."""
        if self.process:
            self.process.terminate()
```

### Регистрация внешнего агента

```yaml
# ~/.synpin/data/agents/hermes/personality.yaml

name: "Гермес"
codename: "hermes"
source: "external"          #标记为 внешний агент
integration: "acp"

# Роль от SynPin
role: "director"

# Своя личность (дополнение к Hermes)
character:
  type: "прагматик"

# Инструменты (двойные)
tools:
  hermes:                   # свои инструменты
    - terminal
    - file
    - web
    - memory
  synpin:                   # инструменты SynPin
    - read_file
    - search_files
    - synpin_chat
    - synpin_kanban
```

---

## Поток интеграции

```
1. SynPin запускает внешний агент через коннектор
   ↓
2. Внешний агент загружает свою память и навыки
   ↓
3. SynPin передаёт роль, канал, контекст
   ↓
4. Агент работает как полноценный участник:
   - Получает задачи
   - Общается в канале
   - Делегирует
   - Пишет в свою память
   ↓
5. Результаты видны в SynPin (канбан, лента, форум)
```

---

## Преимущества

| Преимущество | Описание |
|---|---|
| **Не изобретать велосипед** | Используем готовые агентские системы |
| **Сохранение идентичности** | Агент не теряет свою память и навыки |
| **Гибкость** | Разные агенты для разных ролей |
| **Масштабируемость** | Подключаем сколько угодно внешних агентов |

---

## Ограничения

| Ограничение | Описание |
|---|---|
| **Зависимость** | Если внешний агент упал — агент в SynPin не работает |
| **Синхронизация памяти** | Два хранилища (Hermes + SynPin) нужно синхронизировать |
| **Конфликт инструментов** | Одинаковые инструменты в обеих системах |
| **Безопасность** | Внешний агент имеет доступ к файловой системе |

---

## Roadmap

| Этап | Что | Статус |
|---|---|---|
| 1. Исследование ACP протокола | Изучить документацию Hermes | ✅ Готово |
| 2. Коннектор к ACP | Написать ACPConnector | 🔴 TODO |
| 3. Регистрация внешнего агента | personality.yaml + role | 🔴 TODO |
| 4. Двойные инструменты | Hermes + SynPin tools | 🔴 TODO |
| 5. Синхронизация памяти | Memory bridge | 🔴 TODO |
| 6. Интеграция OpenClaw | Исследовать протокол | 🔴 Планируется |
| 7. Интеграция Windsurf | Исследовать протокол | 🔴 Планируется |

---

## Связь с другими документами

- [Агенты](agents.md) — личность, роли, директивы
- [Инструменты](tools.md) — что умеют агенты
- [Конфигурация](configuration.md) — провайдеры

---

*Внешний агент — не инструмент. Это коллега из другой компании, который пришёл работать в твою организацию.*
