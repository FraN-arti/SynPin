/**
 * MouseTooltip — portal-based tooltip that follows the mouse cursor.
 * Use for stats, charts, and other hover-interactive elements.
 *
 * Usage:
 *   <MouseTooltip content={<div>Custom content</div>}>
 *     <div className="stat-card">...</div>
 *   </MouseTooltip>
 *
 *   <MouseTooltip content="Simple text" offset={12}>
 *     <span>Hover me</span>
 *   </MouseTooltip>
 */
import { useState, useRef, useCallback, useEffect, type ReactNode, type ReactElement } from 'react'
import { createPortal } from 'react-dom'

interface MouseTooltipProps {
  content: ReactNode
  children: ReactElement
  offset?: { x: number; y: number }
  className?: string
}

export function MouseTooltip({
  content,
  children,
  offset = { x: 12, y: 12 },
  className,
}: MouseTooltipProps) {
  const tooltipRef = useRef<HTMLDivElement>(null)
  // 'idle' → waiting, 'visible' → shown with animation
  const [phase, setPhase] = useState<'idle' | 'visible'>('idle')
  const [pos, setPos] = useState({ x: 0, y: 0 })
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearTimers = useCallback(() => {
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null }
    if (hideTimerRef.current) { clearTimeout(hideTimerRef.current); hideTimerRef.current = null }
  }, [])

  const onMouseEnter = useCallback((e: React.MouseEvent) => {
    clearTimers()
    // Immediately set position from mouse event — tooltip will track from here
    setPos({ x: e.clientX + offset.x, y: e.clientY + offset.y })
    timerRef.current = setTimeout(() => {
      setPhase('visible')
    }, 300)
  }, [clearTimers, offset])

  const onMouseLeave = useCallback(() => {
    clearTimers()
    hideTimerRef.current = setTimeout(() => {
      setPhase('idle')
    }, 50)
  }, [clearTimers])

  useEffect(() => clearTimers, [clearTimers])

  // Track mouse position ALWAYS — updates position even during idle (hidden) phase
  useEffect(() => {
    const handleMove = (e: MouseEvent) => {
      const x = e.clientX + offset.x
      const y = e.clientY + offset.y
      const tooltipEl = tooltipRef.current
      let finalX = x
      let finalY = y
      if (tooltipEl) {
        const tw = tooltipEl.offsetWidth
        const th = tooltipEl.offsetHeight
        if (x + tw > window.innerWidth - 8) finalX = e.clientX - tw - offset.x
        if (y + th > window.innerHeight - 8) finalY = e.clientY - th - offset.y
      }
      setPos({ x: finalX, y: finalY })
    }
    window.addEventListener('mousemove', handleMove, { passive: true })
    return () => window.removeEventListener('mousemove', handleMove)
  }, [offset])

  const trigger = (
    <span
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      style={{ display: 'contents' }}
    >
      {children}
    </span>
  )

  // Always render the tooltip (so mousemove can update position).
  // visibility + opacity control the appearance animation.
  const isVisible = phase === 'visible'
  const tooltip = createPortal(
    <div
      ref={tooltipRef}
      className={`custom-tooltip mouse-tooltip ${className || ''}`}
      style={{
        position: 'fixed',
        top: pos.y,
        left: pos.x,
        pointerEvents: 'none',
        opacity: isVisible ? 1 : 0,
        visibility: isVisible ? 'visible' : 'hidden',
        transition: 'opacity 0.15s ease',
      }}
      role="tooltip"
    >
      <div className="custom-tooltip-content">{content}</div>
    </div>,
    document.body,
  )

  return (
    <>
      {trigger}
      {tooltip}
    </>
  )
}
