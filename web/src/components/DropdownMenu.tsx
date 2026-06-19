import { useState, useEffect, useRef, useLayoutEffect, useCallback, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

/**
 * DropdownMenu — единый portal-based dropdown.
 *
 * Рендерит триггер inline (как раньше), а само меню — в document.body через
 * React Portal. Координаты меню берутся из getBoundingClientRect() триггера.
 *
 * Зачем portal:
 *  - `overflow: hidden/auto/scroll` на любом предке (включая .settings-page,
 *    .agent-expanded-content) больше НЕ обрезает меню.
 *  - `backdrop-filter`, `transform`, `filter`, `isolation` на любом предке
 *    больше НЕ создают новый stacking context, ломающий z-index.
 *  - z-index: 9999 в теле документа — абсолютно над всем в приложении.
 *
 * Сохраняет 100% визуала прежнего .custom-dropdown-* (те же CSS-классы).
 */

export interface DropdownOption {
  value: string
  label: ReactNode
  disabled?: boolean
  badge?: ReactNode
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

const MENU_GAP = 4 // px between trigger and menu
const VIEWPORT_PADDING = 8 // keep menu inside viewport

export function DropdownMenu({ value, options, onChange, width, disabled, menuMinWidth, searchable }: DropdownMenuProps) {
  const [open, setOpen] = useState(false)
  const [highlighted, setHighlighted] = useState(-1)
  const [position, setPosition] = useState<{ top: number; left: number; width: number; placement: 'bottom' | 'top' } | null>(null)
  const [searchQuery, setSearchQuery] = useState('')

  const triggerRef = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)
  const searchInputRef = useRef<HTMLInputElement>(null)

  const selected = options.find(o => o.value === value)

  // Compute & update menu position relative to viewport.
  // Re-runs on open, on window resize, and on scroll (capture: true catches
  // scroll inside any ancestor — the trigger may be inside .settings-page
  // which scrolls independently).
  const updatePosition = useCallback(() => {
    const trigger = triggerRef.current
    if (!trigger) return
    const rect = trigger.getBoundingClientRect()
    const vh = window.innerHeight
    const vw = window.innerWidth
    // Provisional height for placement decision; actual height is set after mount
    const estimatedMenuHeight = Math.min(240, options.length * 36 + 8)
    const spaceBelow = vh - rect.bottom - VIEWPORT_PADDING
    const spaceAbove = rect.top - VIEWPORT_PADDING
    const placement: 'bottom' | 'top' = spaceBelow >= estimatedMenuHeight || spaceBelow >= spaceAbove
      ? 'bottom'
      : 'top'
    const left = Math.max(VIEWPORT_PADDING, Math.min(rect.left, vw - rect.width - VIEWPORT_PADDING))
    const top = placement === 'bottom'
      ? rect.bottom + MENU_GAP
      : Math.max(VIEWPORT_PADDING, rect.top - estimatedMenuHeight - MENU_GAP)
    setPosition({ top, left, width: rect.width, placement })
  }, [options.length])

  useLayoutEffect(() => {
    if (!open) {
      setPosition(null)
      return
    }
    updatePosition()
    const onScrollOrResize = () => updatePosition()
    window.addEventListener('resize', onScrollOrResize)
    // capture: true — fire even for scroll on any ancestor (the trigger is
    // deep inside .settings-page which has its own overflow-y: auto)
    window.addEventListener('scroll', onScrollOrResize, true)
    return () => {
      window.removeEventListener('resize', onScrollOrResize)
      window.removeEventListener('scroll', onScrollOrResize, true)
    }
  }, [open, updatePosition])

  // Close on outside click / Escape
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

  const handleSelect = (option: DropdownOption) => {
    if (option.disabled) return
    onChange(option.value)
    setOpen(false)
    setHighlighted(-1)
    setSearchQuery('')
  }

  // Filter options by search query (case-insensitive, matches against string labels)
  const filteredOptions = searchable && searchQuery.trim()
    ? options.filter(o => {
        const label = typeof o.label === 'string' ? o.label : String(o.value)
        return label.toLowerCase().includes(searchQuery.toLowerCase())
      })
    : options

  // Auto-focus search input when opened
  useEffect(() => {
    if (open && searchable && searchInputRef.current) {
      // Small delay so the portal DOM is mounted
      const t = setTimeout(() => searchInputRef.current?.focus(), 0)
      return () => clearTimeout(t)
    }
  }, [open, searchable])

  // Reset search on close
  useEffect(() => {
    if (!open) setSearchQuery('')
  }, [open])

  // Render menu into document.body via portal. This is the global fix:
  // it escapes any clipping/stacking-context ancestor, regardless of where
  // the trigger lives in the tree.
  const menuNode = open && position ? (
    <div
      ref={menuRef}
      className={`custom-dropdown-menu open portal ${searchable ? 'has-search' : ''}`}
      role="listbox"
      style={{
        position: 'fixed',
        top: position.top,
        left: position.left,
        width: position.width,
        minWidth: menuMinWidth,
        zIndex: 9999,
      }}
      data-placement={position.placement}
    >
      {searchable && (
        <div className="custom-dropdown-search-wrap">
          <svg className="custom-dropdown-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" r="8" /><path d="m21 21-4.3-4.3" />
          </svg>
          <input
            ref={searchInputRef}
            type="text"
            className="custom-dropdown-search"
            placeholder="Поиск..."
            value={searchQuery}
            onChange={e => { setSearchQuery(e.target.value); setHighlighted(-1) }}
            onKeyDown={e => {
              if (e.key === 'ArrowDown') { e.preventDefault(); setHighlighted(h => Math.min(h + 1, filteredOptions.length - 1)) }
              else if (e.key === 'ArrowUp') { e.preventDefault(); setHighlighted(h => Math.max(h - 1, 0)) }
              else if (e.key === 'Enter' && highlighted >= 0 && highlighted < filteredOptions.length) { e.preventDefault(); handleSelect(filteredOptions[highlighted]) }
            }}
            onMouseDown={e => e.stopPropagation()}
          />
        </div>
      )}
      {filteredOptions.length === 0 && (
        <div className="custom-dropdown-empty">Ничего не найдено</div>
      )}
      {filteredOptions.map((option, i) => (
        <button
          key={option.value}
          type="button"
          className={`custom-dropdown-item ${option.value === value ? 'selected' : ''} ${option.disabled ? 'disabled' : ''} ${i === highlighted ? 'highlighted' : ''}`}
          onClick={() => handleSelect(option)}
          onMouseEnter={() => setHighlighted(i)}
          disabled={option.disabled}
          role="option"
          aria-selected={option.value === value}
        >
          <span className="custom-dropdown-item-label">
            {option.label}
            {option.badge != null && <span className="custom-dropdown-item-badge">{option.badge}</span>}
          </span>
          {option.value === value && (
            <svg className="dropdown-check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
              <path d="M5 12l5 5L20 7" />
            </svg>
          )}
        </button>
      ))}
    </div>
  ) : null

  return (
    <div className={`custom-dropdown ${disabled ? 'disabled' : ''}`} ref={triggerRef} style={{ width }}>
      <button
        className={`custom-dropdown-trigger ${open ? 'open' : ''}`}
        onClick={() => !disabled && setOpen(o => !o)}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="dropdown-selected">{selected?.label || value}</span>
        <svg className="dropdown-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {createPortal(menuNode, document.body)}
    </div>
  )
}
