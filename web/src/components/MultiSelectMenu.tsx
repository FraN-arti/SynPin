import { PickerMenu, type PickerOption } from './PickerMenu'

/**
 * MultiSelectMenu — тонкая обёртка над PickerMenu (multi mode) для
 * обратной совместимости.
 *
 * С 2026-07-05 PickerMenu — единый компонент для всех dropdown'ов.
 * MultiSelectMenu сохранён как алиас для существующего вызывающего
 * (KanbanSection — селектор статусов задач). Конвертирует старый API:
 *   value: string[], options: { value, label }[], onChange(value[])
 * в новый:
 *   value: string[], options: { id, label }[], onChange(ids[])
 *
 * Что упрощено по сравнению со старым MultiSelectMenu:
 *   - trigger label: было "{value.length} выбрано", стало
 *     comma-joined labels (через formatTriggerLabel). Если хочется
 *     старое поведение — используй PickerMenu напрямую и задай
 *     свой formatTriggerLabel.
 *   - галочка у selected items: было inline-styled span, стало
 *     стандартный .picker-check (одинаковый с NewTaskModal).
 */

export interface MultiSelectOption {
  value: string
  label: string
  disabled?: boolean
}

export interface MultiSelectMenuProps {
  value: string[]
  options: MultiSelectOption[]
  onChange: (value: string[]) => void
  /** Trigger width, e.g. "180px" или "100%". */
  width?: string
  disabled?: boolean
  /** Placeholder when selection is empty. */
  placeholder?: string
  /** Tooltip / title attribute on the trigger. */
  title?: string
}

export function MultiSelectMenu({
  value,
  options,
  onChange,
  width,
  disabled,
  placeholder = '—',
  title,
}: MultiSelectMenuProps) {
  const pickerOptions: PickerOption[] = options.map(o => ({
    id: o.value,
    label: o.label,
    disabled: o.disabled,
  }))

  return (
    <div
      className={disabled ? 'custom-dropdown disabled' : 'custom-dropdown'}
      title={title}
    >
      <PickerMenu
        multi
        value={value}
        options={pickerOptions}
        onChange={onChange}
        triggerWidth={width}
        placeholder={placeholder}
        triggerClassName="custom-dropdown-trigger"
        formatTriggerLabel={(selected) =>
          selected.length === 0
            ? placeholder
            : selected.length === 1
              ? selected[0]!.label
              : `${selected.length} выбрано`
        }
      />
    </div>
  )
}