/**
 * Tooltip — portal-based custom tooltip with rich content.
 * Appears anchored to the trigger element, does NOT follow mouse.
 *
 * Usage:
 *   <Tooltip content="Simple text">
 *     <button>Hover me</button>
 *   </Tooltip>
 *
 *   <Tooltip content={<div><b>Title</b><br/>Detail</div>}>
 *     <span>Rich</span>
 *   </Tooltip>
 */
import { useState, useRef, useCallback, useEffect, type ReactNode, type ReactElement } from 'react'
import { createPortal } from 'react-dom'

export type TooltipPlacement = 'top' | 'bottom' | 'left' | 'right'

interface TooltipProps {
  content: ReactNode
  children: ReactElement
  placement?: TooltipPlacement
  delay?: number
  className?: string
}

export function Tooltip({
  content,
  children,
  placement = 'top',
  delay = 400,
  className,
}: TooltipProps) {
  const triggerRef = useRef<HTMLSpanElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const [state, setState] = useState<'hidden' | 'positioning' | 'visible'>('hidden')
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const [actualPlacement, setActualPlacement] = useState(placement)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearTimers = useCallback(() => {
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null }
    if (hideTimerRef.current) { clearTimeout(hideTimerRef.current); hideTimerRef.current = null }
  }, [])

  const calculatePosition = useCallback(() => {
    const trigger = triggerRef.current
    const tooltipEl = tooltipRef.current
    if (!trigger) return

    const rect = trigger.getBoundingClientRect()
    const scrollY = window.scrollY
    const scrollX = window.scrollX
    const gap = 8

    let top = 0
    let left = 0
    let usedPlacement = placement

    // Try preferred placement first
    switch (placement) {
      case 'top':
        top = rect.top + scrollY - gap
        left = rect.left + scrollX + rect.width / 2
        break
      case 'bottom':
        top = rect.bottom + scrollY + gap
        left = rect.left + scrollX + rect.width / 2
        break
      case 'left':
        top = rect.top + scrollY + rect.height / 2
        left = rect.left + scrollX - gap
        break
      case 'right':
        top = rect.top + scrollY + rect.height / 2
        left = rect.right + scrollX + gap
        break
    }

    // Flip if would go off-screen
    if (tooltipEl) {
      const tw = tooltipEl.offsetWidth
      const th = tooltipEl.offsetHeight

      if (usedPlacement === 'top' && rect.top - th - gap < 0) {
        usedPlacement = 'bottom'
        top = rect.bottom + scrollY + gap
      } else if (usedPlacement === 'bottom' && rect.bottom + th + gap > window.innerHeight) {
        usedPlacement = 'top'
        top = rect.top + scrollY - gap
      } else if (usedPlacement === 'left' && rect.left - tw - gap < 0) {
        usedPlacement = 'right'
        left = rect.right + scrollX + gap
      } else if (usedPlacement === 'right' && rect.right + tw + gap > window.innerWidth) {
        usedPlacement = 'left'
        left = rect.left + scrollX - gap
      }
    }

    setPos({ top, left })
    setActualPlacement(usedPlacement)
  }, [placement])

  const show = useCallback(() => {
    clearTimers()
    timerRef.current = setTimeout(() => {
      // Step 1: render tooltip off-screen to get dimensions
      setState('positioning')
    }, delay)
  }, [delay, clearTimers])

  const hide = useCallback(() => {
    clearTimers()
    hideTimerRef.current = setTimeout(() => {
      setState('hidden')
    }, 100)
  }, [clearTimers])

  // After positioning render, calculate real position then reveal
  useEffect(() => {
    if (state === 'positioning') {
      // double-rAF ensures the browser has painted the tooltip at (0,0)
      // so offsetWidth/offsetHeight are available for flip calculations
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          calculatePosition()
          setState('visible')
        })
      })
    }
  }, [state, calculatePosition])

  useEffect(() => {
    if (state !== 'hidden') {
      window.addEventListener('scroll', calculatePosition, true)
      window.addEventListener('resize', calculatePosition)
      return () => {
        window.removeEventListener('scroll', calculatePosition, true)
        window.removeEventListener('resize', calculatePosition)
      }
    }
  }, [state, calculatePosition])

  useEffect(() => clearTimers, [clearTimers])

  const isVisible = state !== 'hidden'

  const trigger = (
    <span
      ref={triggerRef}
      onMouseEnter={show}
      onMouseLeave={hide}
      style={{ display: 'contents' }}
    >
      {children}
    </span>
  )

  const tooltip = isVisible ? createPortal(
    <div
      ref={tooltipRef}
      className={`custom-tooltip custom-tooltip-${actualPlacement} ${state === 'positioning' ? 'tt-hidden' : ''} ${className || ''}`}
      style={{ top: pos.top, left: pos.left }}
      onMouseEnter={show}
      onMouseLeave={hide}
      role="tooltip"
    >
      <div className="custom-tooltip-content">{content}</div>
      <div className="custom-tooltip-arrow" />
    </div>,
    document.body,
  ) : null

  return (
    <>
      {trigger}
      {tooltip}
    </>
  )
}
