# 🤖 Агенты

Агент в SynPin — это не просто LLM. Это **личность с памятью, навыками и ролью** в организации.

---

## Архитектура агента

```
┌─────────────────────────────────────────────────┐
│                    АГЕНТ                         │
├─────────────────────────────────────────────────┤
│  👤 Личность    → кто он, как общается, ценности │
│  🧠 Память      → MEMORY.md, USER.md, сессии     │
│  🛠 Скиллы       → навыки, умения, шаблоны       │
│  📋 Роль        → worker / head / director       │
│  📡 Контекст    → канал, отдел, текущие задачи   │
└─────────────────────────────────────────────────┘
```

Каждый компонент загружается при старте сессии.

---

## 👤 Личность (Personality)

У каждого агента есть **личность** — набор характеристик, определяющих его поведение, стиль общения и подход к задачам.

### personality.yaml

```yaml
# ~/.synpin/data/agents/architect/personality.yaml

name: "Архитектор"
codename: "architect"

# Стиль общения
communication:
  style: "краткий_и_технический"     # краткий / подробный / технический / дружелюбный
  language: "ru"                      # ru / en / auto
  tone: "профессиональный"            # профессиональный / дружелюбный / строгий / наставнический
  use_emojis: true                    # использовать эмодзи
  use_markdown: true                  # форматировать ответы
  max_response_length: 500            # максимум символов (0 = без ограничений)

# Характер
character:
  type: "аналитик"                    # аналитик / экспериментатор / консерватор / прагматик
  risk_tolerance: "low"               # low / medium / high
  decision_speed: "deliberate"        # fast / balanced / deliberate (обдуманный)
  prefers: ["схемы", "диаграммы", "код"]  # предпочтительные форматы

# Ценности
values:
  - "Точность важнее скорости"
  - "Документируй решения"
  - "Предупреждай о рисках заранее"

# Специфика отдела
department_focus: "Web Development"
expertise: ["FastAPI", "React", "системный дизайн", "архитектура"]

# Запреты (что агент НЕ делает)
restrictions:
  - "Не принимает финальные решения без одобрения главы"
  - "Не изменяет продакшен-конфиги без review"
```

### Почему это важно

| Без личности | С личностью |
|---|---|
| Все агенты отвечают одинаково | Каждый агент уникален |
| Нет понимания «кто есть кто» | Агенты дополняют друг друга |
| Хаос в стиле общения | Предсказуемый формат |
| Сложно делегировать | Понятно к кому обращаться |

### Примеры личностей

**Аналитик (architect):**
- Думает долго, отвечает чётко
- Предпочитает схемы и код
- Предупреждает о рисках

**Экспериментатор (developer):**
- Быстро пробует разные подходы
- Предлагает 2-3 варианта решения
- Не боится ошибок

**Прагматик (qa):**
- Фокус на результат
- Ищет крайние случаи
- Жёсткий в стандартах

---

## 🛠 Скиллы (Skills)

Скиллы — это **навыки и умения** агента. Главы отделов могут создавать скиллы для своих агентов или подключать существующие из библиотеки.

### Структура скиллов

```
~/.synpin/skills/
├── shared/                    # общие скиллы (доступны всем)
│   ├── code-review/
│   │   ├── SKILL.md
│   │   └── checklist.yaml
│   ├── git-workflow/
│   │   └── SKILL.md
│   └── api-design/
│       └── SKILL.md
├── web-dev/                   # скиллы отдела web-dev
│   ├── react-component/
│   │   ├── SKILL.md
│   │   └── template.tsx
│   └── tailwind-styling/
│       └── SKILL.md
└── api-design/                # скиллы отдела api-design
    ├── fastapi-crud/
    │   └── SKILL.md
    └── auth-flow/
        └── SKILL.md
```

### SKILL.md

```markdown
# Skill: React Component

## Description
Создание React-компонентов с TypeScript, Zod валидацией и тестами.

## When to use
- Нужно создать новый UI-компонент
- Нужно рефакторить существующий
- Нужна форма с валидацией

## Steps
1. Определить props интерфейс
2. Создать Zod схему валидации
3. Написать компонент с TypeScript strict
4. Добавить тесты (минимум 1)
5. Экспортировать через barrel file

## Template
```tsx
// component.tsx
import { z } from 'zod'

export const PropsSchema = z.object({
  // ...
})

export type Props = z.infer<typeof PropsSchema>

export const Component = ({ ... }: Props) => {
  // ...
}
```

## Checklist
- [ ] Props типизированы
- [ ] Zod валидация
- [ ] Тесты написаны
- [ ] Экспорт через index.ts
```

### skills.yaml у агента

```yaml
# ~/.synpin/data/agents/frontend/skills.yaml

skills:
  # Подключённые из shared
  - name: "code-review"
    source: "shared"
    enabled: true

  - name: "git-workflow"
    source: "shared"
    enabled: true

  # Скиллы отдела (созданы главой web-dev)
  - name: "react-component"
    source: "web-dev"
    enabled: true

  - name: "tailwind-styling"
    source: "web-dev"
    enabled: true

  # Отключённые
  - name: "api-design"
    source: "shared"
    enabled: false  # не нужно frontend-агенту
```

### Связь личности и скиллов

Личность агента влияет на **как** он применяет скиллы:

| Личность | Применение скиллов |
|---|---|
| **Аналитик** | Строго по инструкции, шаг за шагом |
| **Экспериментатор** | Пробует разные подходы, может отступить от шаблона |
| **Консерватор** | Только проверенные методы, не импровизирует |
| **Прагматик** | Фокус на результат, пропускает "красивости" |

Пример: скилл `react-component`

- **Аналитик**: создаёт по шаблону, проверяет каждый пункт чеклиста
- **Экспериментатор**: может предложить альтернативную архитектуру
- **Консерватор**: использует только подтверждённые паттерны
- **Прагматик**: делает минимум для working solution, потом дорабатывает

---

### Как главы создают скиллы

Скиллы создаются **вручную** — глава отдела создаёт папку и SKILL.md в соответствующей директории:

```
~/.synpin/skills/web-dev/
└── react-component/
    ├── SKILL.md          # описание, шаги, шаблоны
    └── template.tsx      # опционально: файлы-шаблоны
```

**Веб-интерфейс** показывает все скиллы:
- Список скиллов отдела
- Контент каждого SKILL.md
- Какие агенты какие скиллы используют
- Статус (enabled/disabled)

Это даёт **полный контроль** — всё видно, всё прозрачно.

### Преимущества скиллов

- **Гибкость** — каждый отдел со своими скиллами
- **Переиспользование** — shared скиллы для всех
- **Быстрое обучение** — новый агент получает скиллы отдела
- **Контроль** — глава решает какие скиллы включить
- **Шаблоны** — скилл содержит готовые шаблоны и чеклисты

---

## 📋 Роли

| Роль | Описание | Кто может делегировать |
|---|---|---|
| **Worker** | Исполнитель задач | Глава отдела |
| **Head** | Глава канала/отдела | Совет директоров |
| **Director** | Стратег, член совета директоров | Пользователь |

### Worker

```yaml
role: "worker"
permissions:
  - execute_tasks
  - propose_solutions
  - ask_for_help
  - access_channel_memory
  - use_assigned_skills
restrictions:
  - cannot_assign_tasks
  - cannot_modify_shared_memory_directly
  - cannot_change_other_agents_skills
```

### Head

```yaml
role: "head"
permissions:
  - execute_tasks
  - assign_tasks_to_workers
  - moderate_channel
  - create_department_skills
  - enable_disable_skills
  - access_all_channel_memory
  - cross_channel_communication
restrictions:
  - cannot_override_board_decisions
  - cannot_modify_other_departments
```

### Director

```yaml
role: "director"
permissions:
  - strategic_decisions
  - cross_department_delegation
  - approve_rejections
  - access_all_memory
  - resolve_conflicts
  - modify_shared_memory
restrictions:
  - cannot_directly_modify_worker_skills  # через head
```

---

## 📡 Контекст загрузки

При старте сессии агент загружает:

```
1. personality.yaml       → кто я, как общаюсь
2. MEMORY.md              → что я знаю
3. USER.md                → что хочет пользователь
4. skills.yaml            → что я умею
   └── Загрузка SKILL.md для каждого enabled скилла
5. Shared MEMORY.md       → что знает команда
6. Channel context.md     → что делает мой отдел
7. Последние 5 сессий     → что делал недавно
8. Активные задачи        → что делаю сейчас
```

### Промпт агента (пример)

```
Ты — {name}. Твоя роль: {role} в отделе {department}.

Характер: {character.type}
Стиль: {communication.style}, {communication.tone}

Твоя экспертиза: {expertise}
Твои ценности: {values}

Загруженные скиллы:
- {skill.name}: {skill.description}

Твоя память:
{MEMORY.md content}

Контекст отдела:
{context.md}

Последние сессии:
{recent sessions}

Активные задачи:
{active tasks}

---

Ты НЕ можешь: {restrictions}
Ты ОБЯЗАН: обращаться через @mention, записывать ошибки в память

Начни работу.
```

---

## Управление агентами

```bash
# Создать агента
synpin agent create --name developer --role worker --department web-dev

# Настроить личность
synpin agent personality --name developer --style technical --tone professional

# Назначить скиллы
synpin agent skills --name developer --add react-component,code-review

# Посмотреть профиль
synpin agent show --name developer

# Список агентов отдела
synpin agents list --department web-dev
```

---

## Связь с другими документами

- [Память и сессии](memory-sessions.md) — как агент хранит знания
- [Каналы и иерархия](channels-hierarchy.md) — где агент работает
- [Канбан-доска](kanban-board.md) — как агент получает задачи
- [Конфигурация](configuration.md) — как настроить провайдеров и систему

---

*Агент без личности — инструмент. Агент с личностью — коллега.*
