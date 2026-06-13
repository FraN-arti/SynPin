import { useState, useEffect, useRef, useLayoutEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'

/**
 * MultiSelectMenu — a portal-based multi-select dropdown.
 *
 * Differs from DropdownMenu in two ways:
 *   1. The value is always a string[] (empty list = nothing selected).
 *   2. Picking an item toggles it in/out of the selection; the menu
 *      stays open so the user can keep adding/removing. Closing
 *      requires clicking outside or pressing Escape — same
 *      outside-click + Escape behaviour as DropdownMenu.
 *
 * Reuses the same `.custom-dropdown*` CSS classes so the visual
 * styling matches the single-select variant — the trigger
 * looks identical, only the items' interaction model differs
 * (checkboxes instead of a single checkmark).
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
  /** Trigger width, e.g. "180px" or "100%". */
  width?: string
  disabled?: boolean
  /** Placeholder shown when the selection is empty. */
  placeholder?: string
  /** Tooltip / title attribute on the trigger. */
  title?: string
}

const MENU_GAP = 4
const VIEWPORT_PADDING = 8

export function MultiSelectMenu({
  value,
  options,
  onChange,
  width,
  disabled,
  placeholder = '—',
  title,
}: MultiSelectMenuProps) {
  const [open, setOpen] = useState(false)
  const [position, setPosition] = useState<
    { top: number; left: number; width: number; placement: 'bottom' | 'top' } | null
  >(null)

  const triggerRef = useRef<HTMLDivElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  const updatePosition = useCallback(() => {
    const trigger = triggerRef.current
    if (!trigger) return
    const rect = trigger.getBoundingClientRect()
    const vh = window.innerHeight
    const vw = window.innerWidth
    const estimatedMenuHeight = Math.min(240, options.length * 36 + 8)
    const spaceBelow = vh - rect.bottom - VIEWPORT_PADDING
    const spaceAbove = rect.top - VIEWPORT_PADDING
    const placement: 'bottom' | 'top' =
      spaceBelow >= estimatedMenuHeight || spaceBelow >= spaceAbove ? 'bottom' : 'top'
    const left = Math.max(
      VIEWPORT_PADDING,
      Math.min(rect.left, vw - rect.width - VIEWPORT_PADDING),
    )
    const top =
      placement === 'bottom'
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
    window.addEventListener('scroll', onScrollOrResize, true)
    return () => {
      window.removeEventListener('resize', onScrollOrResize)
      window.removeEventListener('scroll', onScrollOrResize, true)
    }
  }, [open, updatePosition])

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

  const toggle = (option: MultiSelectOption) => {
    if (option.disabled) return
    const isSelected = value.includes(option.value)
    const next = isSelected
      ? value.filter(v => v !== option.value)
      : [...value, option.value]
    onChange(next)
  }

  // Trigger label: count if 1+ selected, otherwise placeholder.
  const label =
    value.length === 0
      ? placeholder
      : value.length === 1
        ? (options.find(o => o.value === value[0])?.label ?? placeholder)
        : `${value.length} выбрано`

  const menuNode =
    open && position ? (
      <div
        ref={menuRef}
        className="custom-dropdown-menu open portal"
        role="listbox"
        aria-multiselectable="true"
        style={{
          position: 'fixed',
          top: position.top,
          left: position.left,
          width: position.width,
          zIndex: 9999,
        }}
        data-placement={position.placement}
      >
        {options.map(option => {
          const isSelected = value.includes(option.value)
          return (
            <button
              key={option.value}
              type="button"
              className={`custom-dropdown-item ${isSelected ? 'selected' : ''} ${option.disabled ? 'disabled' : ''}`}
              onClick={() => toggle(option)}
              disabled={option.disabled}
              role="option"
              aria-selected={isSelected}
            >
              <span
                className="custom-dropdown-item-check"
                aria-hidden="true"
                style={{
                  width: '14px',
                  height: '14px',
                  flexShrink: 0,
                  border: '1.5px solid currentColor',
                  borderRadius: '3px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: isSelected ? 'currentColor' : 'transparent',
                  marginRight: '2px',
                }}
              >
                {isSelected && (
                  <svg
                    width="9"
                    height="9"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="var(--bg, #0d0d1a)"
                    strokeWidth="4"
                  >
                    <path d="M5 12l5 5L20 7" />
                  </svg>
                )}
              </span>
              <span className="custom-dropdown-item-label">{option.label}</span>
            </button>
          )
        })}
      </div>
    ) : null

  return (
    <div
      className={`custom-dropdown ${disabled ? 'disabled' : ''}`}
      ref={triggerRef}
      style={{ width }}
      title={title}
    >
      <button
        className={`custom-dropdown-trigger ${open ? 'open' : ''}`}
        onClick={() => !disabled && setOpen(o => !o)}
        type="button"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="dropdown-selected">{label}</span>
        <svg
          className="dropdown-arrow"
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {createPortal(menuNode, document.body)}
    </div>
  )
}
