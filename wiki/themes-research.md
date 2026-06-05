# 🎨 Визуальные темы — Исследование OpenClaw

> **📋 Статус: Планируется (Фаза 2)** — это design spec, не реализовано.

> Источник: OpenClaw Issue #28300, PR #44382, ClawHub
> Дата: 2026-06-04

## Концепция

OpenClaw использует **OKLCH color space** для генерации тем. Пользователь крутит один hue slider → алгоритм генерирует 60+ CSS переменных для всего UI.

## Почему OKLCH

- **Равномерные градиенты** — в отличие от RGB/HSV, OKLCH даёт визуально равномерные переходы
- **Один параметр** — hue (0-360°) определяет весь цветовой палитр
- **ISO-luminance** — яркость сохраняется при смене hue, текст остаётся читаемым

## Архитектура темы

### CSS Variables (60+)

Все цвета — чистые CSS переменные на `:root`:

```
:root {
  /* Backgrounds */
  --bg-primary: #1a1a2e;
  --bg-secondary: #16213e;
  --bg-tertiary: #0f3460;
  
  /* Text */
  --text-primary: #e8e3d5;
  --text-secondary: #7b7f87;
  --text-accent: #f6c453;
  
  /* Accent */
  --accent: #f97316;
  --accent-soft: #fb923c;
  --accent-gradient: linear-gradient(...);
  
  /* Border */
  --border: #3c414b;
  --border-light: #5b6472;
  
  /* Semantic */
  --error: #f97066;
  --success: #7dd3a5;
  --warning: #f6c453;
  --info: #8cc8ff;
}
```

### Hue Slider → Algorithm

```
Input: hue = 25 (оранжевый)
Output:
  accent = oklch(65% 0.15 25)      // основной акцент
  accent-soft = oklch(70% 0.12 25)  // приглушённый
  bg-primary = oklch(15% 0.02 25)   // фон с тёплым оттенком
  bg-secondary = oklch(18% 0.03 25) // второй фон
  text-accent = oklch(75% 0.10 25)  // акцентный текст
  ... (60+ переменных)
```

### 5 Color Groups (Advanced Panel)

| Группа | Переменные | Описание |
|---|---|---|
| Background | 4-5 | Фоны (primary, secondary, tertiary, elevated) |
| Text | 3-4 | Текст (primary, secondary, muted, accent) |
| Accent | 3-4 | Акценты (main, soft, gradient, hover) |
| Border | 2-3 | Границы (default, light, focus) |
| Semantic | 4-5 | Статусы (error, success, warning, info) |

### 6 Preset Themes

| Пресет | Hue | Вайб |
|---|---|---|
| Ocean | ~210 | Синий, морской, прохладный |
| Spring | ~120 | Зелёный, свежий, живой |
| Sunset | ~30 | Оранжевый, тёплый, энергичный |
| Forest | ~150 | Тёмно-зелёный, природный |
| Purple | ~270 | Фиолетовый, креативный |
| Mocha | ~30 | Коричневый, кофейный, уютный |

## UI паттерн

### Theme Toggle
```
[☀️ System] [🌙 Dark] [☀️ Light] [⋯ More]
                                    ↓
                              ┌─────────────┐
                              │ Ocean       │
                              │ Spring      │
                              │ Sunset      │
                              │ Forest      │
                              │ Purple      │
                              │ Mocha       │
                              │ ─────────── │
                              │ 🎨 Custom   │
                              └─────────────┘
```

### Custom Theme Studio
```
┌─────────────────────────────┐
│ 🎨 Custom Theme        [✕]  │
│─────────────────────────────│
│ Hue: [██████████░░░░] 25°   │
│                             │
│ [🌙 Dark] [☀️ Light]        │
│ [Gradient ≋] [Solid ─]      │
│                             │
│ ┌─ Background ────────────┐ │
│ │ ● ● ● ●                │ │
│ └─────────────────────────┘ │
│ ┌─ Text ──────────────────┐ │
│ │ ● ● ● ●                │ │
│ └─────────────────────────┘ │
│ ┌─ Accent ────────────────┐ │
│ │ ● ● ● ●                │ │
│ └─────────────────────────┘ │
│ ...                         │
│                             │
│ [Reset to defaults]         │
└─────────────────────────────┘
```

## Реализация для SynPin

### Файлы
- `web/src/lib/theme-generator.ts` — OKLCH algorithm (~200 строк)
- `web/src/lib/themes.ts` — preset definitions
- `web/src/components/ThemeStudio.tsx` — floating panel
- `web/src/components/ThemeToggle.tsx` — 4-button toggle
- `web/src/index.css` — CSS variables на :root

### Дефолтная тема
- Hue: 25 (оранжевый — фирменный цвет SynPin)
- Mode: dark
- Accent: oklch(65% 0.15 25)

### Хранение
```typescript
// localStorage
{
  "synpin-theme": {
    "hue": 25,
    "mode": "dark",
    "preset": null,  // or "ocean", "spring", etc.
    "overrides": {}  // per-variable overrides
  }
}
```

### Приоритет
1. `overrides` (per-variable)
2. `preset` (если выбран)
3. `hue` slider (generates from OKLCH)
4. Дефолт (orange, dark)

## Ключевые файлы OpenClaw для вдохновения

- `ui/src/ui/theme-generator.ts` — OKLCH algorithm
- `ui/src/ui/theme.ts` — theme resolution
- `ui/src/styles/base.css` — CSS variable blocks
- `src/tui/theme/palettes.ts` — TUI palettes (5 themes)

---

*Исследование conducted 2026-06-04. Источник: OpenClaw GitHub.*
