import { useEffect, useLayoutEffect, useRef, useState, useCallback, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

/**
 * PickerMenu — portal-based search-and-select menu.
 *
 * Same escape problem as DropdownMenu: any `position: absolute` element
 * nested inside a `position: relative` ancestor that has `backdrop-filter`,
 * `transform`, `filter`, or `overflow-y: auto` becomes trapped in that
 * ancestor's stacking context. In NewTaskModal (.kanban-modal with
 * `overflow-y: auto` + `backdrop-filter` on overlay), the inline-positioned
 * `.kanban-dept-dropdown` and `.tag-picker-popup` were getting clipped.
 *
 * Pattern: trigger is inline, menu is rendered via React Portal in
 * document.body, position computed from trigger's getBoundingClientRect().
 * Same global fix as DropdownMenu.
 *
 * Supports two modes:
 *   - Single (default): `value: string | null`, `onSelect`, closes after pick.
 *   - Multi: `multi`, `value: string[]`, `onChange`, stays open, checkmarks.
 *
 * The two modes are distinguished by the `multi` prop — TypeScript narrows
 * the `value`/`onSelect`|`onChange` shapes accordingly.
 */

export interface PickerOption {
  id: string
  label: string
  /** Optional badge shown next to the label (e.g. "скоро" for disabled). */
  badge?: ReactNode
  /** Optional search-string to match against query (defaults to label). */
  searchText?: string
  /** When true, option is shown but not selectable. */
  disabled?: boolean
}

type SingleProps = {
  multi?: false
  /** Currently selected option id, or null. */
  value: string | null
  onSelect: (id: string) => void
}

type MultiProps = {
  multi: true
  /** Currently selected option ids. */
  value: string[]
  onChange: (ids: string[]) => void
}

type CommonProps = {
  options: PickerOption[]
  /** Width of the trigger (e.g. "100%"). */
  triggerWidth?: string
  /** Placeholder when no option selected. */
  placeholder?: string
  /** Optional search input inside the menu. */
  searchable?: boolean
  searchPlaceholder?: string
  /** Empty state message. */
  emptyMessage?: string
  /** Extra CSS class for the trigger button. */
  triggerClassName?: string
  /** Class to apply to the currently-selected option. */
  selectedOptionClassName?: string
  /**
   * Format the trigger label from the currently-selected options. Defaults
   * to comma-joined labels. Only used in multi mode.
   */
  formatTriggerLabel?: (selected: PickerOption[]) => string
}

export type PickerMenuProps = (SingleProps | MultiProps) & CommonProps

const MENU_GAP = 4
const VIEWPORT_PADDING = 8

export function PickerMenu(props: PickerMenuProps) {
  const {
    options,
    triggerWidth,
    placeholder = '',
    searchable = false,
    searchPlaceholder = 'Поиск...',
    emptyMessage = 'Ничего не найдено',
    triggerClassName = 'picker-trigger',
    selectedOptionClassName = 'active',
  } = props

  const isMulti = props.multi === true

  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [position, setPosition] = useState<{ top: number; left: number; width: number; placement: 'bottom' | 'top' } | null>(null)

  const triggerRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)

  // Selected set — for fast lookup. In single mode the set has 0 or 1 entry.
  const selectedIds = new Set<string>(
    isMulti
      ? (props.value as string[])
      : (props.value as string | null) ? [props.value as string] : []
  )

  const selectedOptions = options.filter(o => selectedIds.has(o.id))

  const updatePosition = useCallback(() => {
    const trigger = triggerRef.current
    if (!trigger) return
    const rect = trigger.getBoundingClientRect()
    const vh = window.innerHeight
    const estimatedMenuHeight = searchable ? 240 : Math.min(240, options.length * 36 + 8)
    const spaceBelow = vh - rect.bottom - VIEWPORT_PADDING
    const spaceAbove = rect.top - VIEWPORT_PADDING
    const placement: 'bottom' | 'top' = spaceBelow >= estimatedMenuHeight || spaceBelow >= spaceAbove
      ? 'bottom'
      : 'top'
    const left = Math.max(VIEWPORT_PADDING, Math.min(rect.left, window.innerWidth - rect.width - VIEWPORT_PADDING))
    const top = placement === 'bottom'
      ? rect.bottom + MENU_GAP
      : Math.max(VIEWPORT_PADDING, rect.top - estimatedMenuHeight - MENU_GAP)
    setPosition({ top, left, width: rect.width, placement })
  }, [options.length, searchable])

  useLayoutEffect(() => {
    if (!open) {
      setPosition(null)
      setQuery('')
      return
    }
    updatePosition()
    const onScrollOrResize = () => updatePosition()
    window.addEventListener('resize', onScrollOrResize)
    // capture: true so we catch scroll on any ancestor (.kanban-modal
    // has its own overflow-y: auto).
    window.addEventListener('scroll', onScrollOrResize, true)
    return () => {
      window.removeEventListener('resize', onScrollOrResize)
      window.removeEventListener('scroll', onScrollOrResize, true)
    }
  }, [open, updatePosition])

  // Focus the search input when the menu opens.
  useEffect(() => {
    if (open && searchable) {
      const t = setTimeout(() => searchInputRef.current?.focus(), 0)
      return () => clearTimeout(t)
    }
  }, [open, searchable])

  useEffect(() => {
    if (!open) return
    const handleMouseDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (triggerRef.current?.contains(t)) return
      if (menuRef.current?.contains(t)) return
      setOpen(false)
    }
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }
    document.addEventListener('mousedown', handleMouseDown)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleMouseDown)
      document.removeEventListener('keydown', handleKey)
    }
  }, [open])

  const handleSelect = (opt: PickerOption) => {
    if (opt.disabled) return
    if (isMulti) {
      const onChange = (props as MultiProps).onChange
      const current = (props as MultiProps).value
      const next = current.includes(opt.id)
        ? current.filter(id => id !== opt.id)
        : [...current, opt.id]
      onChange(next)
      // Multi: stay open so user can keep picking. Don't reset query —
      // user may want to find another similar option.
    } else {
      ;(props as SingleProps).onSelect(opt.id)
      setOpen(false)
      setQuery('')
    }
  }

  const filteredOptions = searchable && query.trim()
    ? options.filter(o => {
        const haystack = (o.searchText ?? o.label).toLowerCase()
        return haystack.includes(query.trim().toLowerCase())
      })
    : options

  // Build trigger label. In single mode, the selected option's label.
  // In multi, comma-joined labels (or custom formatter if provided).
  let triggerLabel: string
  if (isMulti) {
    if (selectedOptions.length === 0) {
      triggerLabel = placeholder
    } else if (props.formatTriggerLabel) {
      triggerLabel = props.formatTriggerLabel(selectedOptions)
    } else {
      triggerLabel = selectedOptions.map(o => o.label).join(', ')
    }
  } else {
    triggerLabel = selectedOptions[0]?.label ?? placeholder
  }

  const menuNode = open && position ? (
    <div
      ref={menuRef}
      className="picker-menu open"
      role="listbox"
      aria-multiselectable={isMulti || undefined}
      style={{
        position: 'fixed',
        top: position.top,
        left: position.left,
        width: position.width,
        zIndex: 9999,
      }}
      data-placement={position.placement}
    >
      {searchable && (
        <div className="picker-search-wrap">
          <input
            ref={searchInputRef}
            className="picker-search"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder={searchPlaceholder}
            type="text"
            autoComplete="off"
          />
        </div>
      )}
      <div className="picker-options">
        {filteredOptions.length === 0 ? (
          <div className="picker-empty">{emptyMessage}</div>
        ) : (
          filteredOptions.map(opt => {
            const isSelected = selectedIds.has(opt.id)
            return (
              <button
                key={opt.id}
                type="button"
                role="option"
                aria-selected={isSelected}
                className={`picker-option ${isSelected ? selectedOptionClassName : ''} ${opt.disabled ? 'disabled' : ''}`}
                onClick={() => handleSelect(opt)}
                disabled={opt.disabled}
              >
                {isMulti && (
                  <span className={`picker-check ${isSelected ? 'checked' : ''}`} aria-hidden="true">
                    {isSelected ? '✓' : ''}
                  </span>
                )}
                <span className="picker-option-label">{opt.label}</span>
                {opt.badge != null && <span className="picker-option-badge">{opt.badge}</span>}
              </button>
            )
          })
        )}
      </div>
    </div>
  ) : null

  return (
    <div className="picker-menu-root" style={{ width: triggerWidth }}>
      <button
        type="button"
        className={`${triggerClassName} ${open ? 'open' : ''} ${selectedOptions.length > 0 ? 'has-value' : ''}`}
        onClick={() => setOpen(o => !o)}
        ref={triggerRef}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="picker-trigger-text">{triggerLabel}</span>
        <span className="picker-arrow">{open ? '▴' : '▾'}</span>
      </button>
      {createPortal(menuNode, document.body)}
    </div>
  )
}
