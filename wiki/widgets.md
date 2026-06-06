# 🧩 Виджеты (Drag & Drop панели)

Drag-and-drop система виджетов для кастомизации интерфейса SynPin.

---

## Концепция

Две drop-зоны (левая и правая) на основной странице, куда можно перетаскивать модули из Settings. Виджеты показывают компактный контент прямо на главной — не заходя в настройки.

```
┌──────────┬──────────────┬──────────────────┬──────────────┐
│ Sidebar  │ Left Widget  │   Main Content   │ Right Widget │
│ (агенты) │   Zone       │  (чат/настр.)    │   Zone       │
│ fixed    │ fixed        │   padding        │ fixed        │
│ z:50     │ z:10         │   0 280px 0      │ z:10         │
└──────────┴──────────────┴──────────────────┴──────────────┘
```

---

## Архитектура

### Компоненты

| Компонент | Файл | Описание |
|---|---|---|
| `WidgetDropZone` | `WidgetDropZone.tsx` | Droppable зона + SortableContext для виджетов |
| `SortableWidget` | `WidgetDropZone.tsx` | Обёртка виджета с drag handle и кнопкой удаления |
| `DraggableTab` | `SettingsPage.tsx` | Tab-заголовки в Settings — draggable sources |
| `useWidgetLayout` | `WidgetDropZone.tsx` | Hook для управления layout state |
| `WIDGET_META` | `WidgetDropZone.tsx` | Реестр мета-данных виджетов (тип → иконка + имя) |

### DndContext

- Расположен на уровне `App.tsx`, оборачивает `<main-layout>`
- Библиотека: `@dnd-kit/core` + `@dnd-kit/sortable`
- Sensors: PointerSensor (distance: 8px) + KeyboardSensor

### Поток данных

```
Settings Tab (DraggableTab)
    ↓ useDraggable (id: "tab-departments")
    ↓ DragOverlay (показывает иконку + имя)
    ↓
WidgetDropZone (useDroppable)
    ↓ onDragEnd → handleDragEnd
    ↓ Определяет: новый виджет или reorder
    ↓
useWidgetLayout → syncLayout
    ↓ setLayout + saveWidgetLayout (localStorage)
    ↓ dispatchEvent('synpin-widgets-changed')
    ↓
WidgetDropZone re-renders с новым layout
```

---

## Типы виджетов

```typescript
type WidgetType = 'departments' | 'skills' | 'channels'
```

### Реестр мета-данных

```typescript
const WIDGET_META: Record<WidgetType, { label: string; icon: string }> = {
  departments: { label: 'Отделы', icon: '🏢' },
  skills:      { label: 'Скиллы', icon: '🧠' },
  channels:    { label: 'Каналы', icon: '📡' },
}
```

### Добавление нового виджета

1. Добавить тип в `WidgetType` (union type)
2. Добавить запись в `WIDGET_META`
3. Создать компонент-рендерер (как `DepartmentsWidgetContent`)
4. Добавить case в `SortableWidget` → `widget-card-body`

---

## Persist layout

### localStorage

- **Ключ:** `synpin_widget_layout`
- **Формат:**
  ```json
  {
    "left": ["departments"],
    "right": ["skills"]
  }
  ```

### Миграция

Старый формат (`{ widgets: [...] }`) автоматически мигрирует в `{ left: [...], right: [] }`.

### Синхронизация

Custom event `synpin-widgets-changed` — для обновления UI между компонентами без перезагрузки.

---

## CSS Layout

### Зоны (fixed position)

```css
.widget-drop-zone {
  position: fixed;
  top: 0;
  bottom: 0;
  width: 280px;
  padding: 70px 8px 12px;  /* отступ от логотипа */
  z-index: 10;              /* под sidebar (z:50) */
  pointer-events: none;     /* клики проходят сквозь */
}

.widget-drop-zone > * {
  pointer-events: auto;     /* но виджеты кликабельны */
}
```

### Основной контент

```css
.main-area {
  padding: 0 280px;  /* отступ под зоны виджетов */
}
```

### Draggable табы

```css
.settings-nav-tab.draggable {
  cursor: grab;
}
.settings-nav-tab.draggable::after {
  content: '⋮';  /* индикатор draggability */
}
```

---

## Workflow

1. **Settings → таб "Отделы"** — хватаешь за заголовок (видна `⋮`)
2. **Тащишь** — появляются обе зоны с `← Перетащите сюда` / `→ Перетащите сюда`
3. **Drop** — виджет появляется в выбранной зоне
4. **Reorder** — drag handle `⠿` внутри виджета
5. **Remove** — кнопка `×` (появляется при hover)
6. **F5** — layout сохраняется в localStorage

---

## Ограничения

- Максимум 3 типа виджетов (пока enum)
- Один виджет не может быть в обеих зонах одновременно
- Настройки контента виджетов хранятся в backend (YAML), не в localStorage
- localStorage — per-browser, не синхронизируется между устройствами
