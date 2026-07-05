import { PickerMenu, type PickerOption } from './PickerMenu'

/**
 * DropdownMenu — тонкая обёртка над PickerMenu для обратной совместимости.
 *
 * С 2026-07-05 PickerMenu — единый компонент для всех dropdown'ов в SynPin
 * (одинаковый стиль: blur, focus-shadow, orange glow). DropdownMenu
 * сохранён как алиас для существующих вызывающих (MemorySection,
 * OtdelSettingsPanel, AgentsSection, etc.) — он конвертирует старый API
 * (`value: string`, `option.value/label: ReactNode`) в новый
 * (`value: string | null`, `option.id/label: string`) внутри.
 *
 * Новый код должен использовать PickerMenu напрямую.
 *
 * Что не перенесено из старого DropdownMenu:
 *   - Keyboard nav (ArrowUp/Down/Enter, highlighted option) — PickerMenu
 *     пока без него. Это OK для текущих use-cases (короткие enum-списки).
 */

export interface DropdownOption {
  value: string
  label: React.ReactNode
  disabled?: boolean
  badge?: React.ReactNode
}

export interface DropdownMenuProps {
  value: string
  options: DropdownOption[]
  onChange: (value: string) => void
  /** Inline-стиль ширины триггера (например, "100%" или "220px") */
  width?: string
  disabled?: boolean
  /** Алиас для контроля ширины меню. По умолчанию совпадает с шириной триггера. */
  menuMinWidth?: number
  /** Показать поле поиска внутри меню (фильтрация по label). */
  searchable?: boolean
}

export function DropdownMenu({
  value,
  options,
  onChange,
  width,
  disabled,
  searchable,
}: DropdownMenuProps) {
  // Конвертируем DropdownOption[] → PickerOption[]. Label в PickerMenu
  // принимает только string — рендерим ReactNode в строку через String().
  const pickerOptions: PickerOption[] = options.map(o => ({
    id: o.value,
    label: typeof o.label === 'string' ? o.label : String(o.value),
    disabled: o.disabled,
    badge: o.badge,
  }))

  return (
    <div className={disabled ? 'custom-dropdown disabled' : 'custom-dropdown'}>
      <PickerMenu
        value={value}
        options={pickerOptions}
        onSelect={onChange}
        triggerWidth={width}
        searchable={searchable}
        // Trigger стилизуется через классы .custom-dropdown-trigger —
        // PickerMenu рендерит <button> с классом по умолчанию `picker-trigger`,
        // поэтому пробрасываем наш CSS-класс через triggerClassName.
        triggerClassName="custom-dropdown-trigger"
      />
    </div>
  )
}