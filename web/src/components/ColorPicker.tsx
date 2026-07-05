import { useState, useRef, useEffect, useLayoutEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'

/**
 * ColorPicker — глобальный color picker в стиле SynPin.
 *
 * Заменяет нативный `<input type="color">` (маленький квадратик, OS-тул).
 * SynPin-style: квадратик 28x28 в glass-обёртке, при клике — popover с:
 *   - 12 предустановленных swatches (SynPin palette)
 *   - свободный hex-input
 *   - кнопка «Custom…» → открывает нативный picker для произвольного цвета
 *
 * Использование:
 *   <ColorPicker value={color} onChange={setColor} />
 *   <ColorPicker value={color} onChange={setColor} size="sm" />
 */

export interface ColorPickerProps {
  value: string
  onChange: (color: string) => void
  /** Trigger size: 'sm' = 20x20 (для тесных row), 'md' = 28x28 (default) */
  size?: 'sm' | 'md'
}

// SynPin curated palette — статусы канбана + UI-акценты
const PALETTE = [
  '#9ca3af', // backlog (серый)
  '#60a5fa', // todo (синий)
  '#c084fc', // ready (фиолетовый)
  '#fb923c', // in_progress (оранжевый)
  '#fbbf24', // review (жёлтый)
  '#f472b6', // revision (розовый)
  '#f87171', // blocked (красный)
  '#4ade80', // done (зелёный)
  '#6b7280', // archive (тёмно-серый)
  '#f97316', // accent (оранжевый SynPin)
  '#22d3ee', // cyan
  '#a78bfa', // lavender
]

const VIEWPORT_PADDING = 8

function isValidHex(v: string) {
  return /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(v)
}

export function ColorPicker({ value, onChange, size = 'md' }: ColorPickerProps) {
  const [open, setOpen] = useState(false)
  const [hexInput, setHexInput] = useState(value)
  const [position, setPosition] = useState<{ top: number; left: number; placement: 'bottom' | 'top' } | null>(null)

  const triggerRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const nativeInputRef = useRef<HTMLInputElement>(null)

  // Sync hexInput when external value changes (e.g. from API refresh)
  useEffect(() => { setHexInput(value) }, [value])

  const updatePosition = useCallback(() => {
    const trigger = triggerRef.current
    if (!trigger) return
    const rect = trigger.getBoundingClientRect()
    const popoverHeight = 220 // approx
    const spaceBelow = window.innerHeight - rect.bottom - VIEWPORT_PADDING
    const placement: 'bottom' | 'top' = spaceBelow >= popoverHeight ? 'bottom' : 'top'
    const top = placement === 'bottom'
      ? rect.bottom + 4
      : Math.max(VIEWPORT_PADDING, rect.top - popoverHeight - 4)
    const left = Math.max(
      VIEWPORT_PADDING,
      Math.min(rect.left, window.innerWidth - rect.width - VIEWPORT_PADDING),
    )
    setPosition({ top, left, placement })
  }, [])

  useLayoutEffect(() => {
    if (!open) { setPosition(null); return }
    updatePosition()
    const onScrollOrResize = () => updatePosition()
    window.addEventListener('resize', onScrollOrResize)
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
      if (popoverRef.current?.contains(t)) return
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

  const applyHex = (raw: string) => {
    const trimmed = raw.trim()
    if (isValidHex(trimmed)) onChange(trimmed.toLowerCase())
  }

  const popover = open && position ? (
    <div
      ref={popoverRef}
      className="color-picker-popover"
      role="dialog"
      aria-label="Выбор цвета"
      style={{ position: 'fixed', top: position.top, left: position.left, zIndex: 9999 }}
      data-placement={position.placement}
    >
      <div className="color-picker-swatches">
        {PALETTE.map(c => (
          <button
            key={c}
            type="button"
            className={`color-swatch ${c === value ? 'active' : ''}`}
            style={{ background: c }}
            onClick={() => { onChange(c); setOpen(false) }}
            aria-label={`Цвет ${c}`}
            title={c}
          />
        ))}
      </div>
      <div className="color-picker-row">
        <input
          type="text"
          className="color-picker-hex"
          value={hexInput}
          onChange={e => setHexInput(e.target.value)}
          onBlur={() => applyHex(hexInput)}
          onKeyDown={e => { if (e.key === 'Enter') applyHex(hexInput) }}
          placeholder="#rrggbb"
          maxLength={7}
          spellCheck={false}
        />
        <button
          type="button"
          className="color-picker-native-btn"
          onClick={() => nativeInputRef.current?.click()}
          title="Открыть палитру системы"
        >
          ⋯
        </button>
        <input
          ref={nativeInputRef}
          type="color"
          value={isValidHex(value) ? value : '#000000'}
          onChange={e => onChange(e.target.value)}
          className="color-picker-native-input"
          tabIndex={-1}
          aria-hidden="true"
        />
      </div>
    </div>
  ) : null

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className={`color-picker-trigger size-${size} ${open ? 'open' : ''}`}
        onClick={() => setOpen(o => !o)}
        style={{ background: value }}
        aria-label={`Текущий цвет: ${value}. Изменить.`}
        title={value}
      />
      {createPortal(popover, document.body)}
    </>
  )
}