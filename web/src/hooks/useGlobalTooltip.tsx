/**
 * useGlobalTooltip — intercepts all native `title` attributes
 * and shows a custom mouse-following tooltip instead.
 *
 * Usage: call once in App root — all title attributes become mouse-following.
 */
import { useEffect, useRef, useCallback, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

export function useGlobalTooltip(): ReactNode {
  const tooltipRef = useRef<HTMLDivElement>(null)
  const titleRef = useRef<string>('')
  const targetRef = useRef<Element | null>(null)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const mousePosRef = useRef({ x: 0, y: 0 })

  const showTooltip = useCallback((text: string) => {
    const el = tooltipRef.current
    if (!el) return
    el.textContent = text
    const { x: mx, y: my } = mousePosRef.current
    const tw = el.offsetWidth || 200
    const th = el.offsetHeight || 40
    let x = mx + 12
    let y = my + 12
    if (x + tw > window.innerWidth - 8) x = mx - tw - 12
    if (y + th > window.innerHeight - 8) y = my - th - 12
    el.style.left = `${x}px`
    el.style.top = `${y}px`
    el.style.visibility = 'visible'
    el.style.opacity = '1'
  }, [])

  const hideTooltip = useCallback(() => {
    const el = tooltipRef.current
    if (!el) return
    el.style.visibility = 'hidden'
    el.style.opacity = '0'
  }, [])

  useEffect(() => {
    const onMouseOver = (e: MouseEvent) => {
      const target = e.target as Element
      const el = target.closest('[title]')
      if (!el || !el.getAttribute('title')) return

      const text = el.getAttribute('title')!
      if (!text) return

      titleRef.current = text
      targetRef.current = el
      el.setAttribute('title', '')

      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => {
        showTooltip(text)
      }, 300)
    }

    const onMouseOut = (e: MouseEvent) => {
      const target = e.target as Element
      const el = target.closest('[title]') || targetRef.current
      if (!el) return

      if (titleRef.current) {
        el.setAttribute('title', titleRef.current)
        titleRef.current = ''
        targetRef.current = null
      }

      if (timerRef.current) {
        clearTimeout(timerRef.current)
        timerRef.current = null
      }
      hideTooltip()
    }

    const onMouseMove = (e: MouseEvent) => {
      mousePosRef.current = { x: e.clientX, y: e.clientY }
      const el = tooltipRef.current
      if (!el || el.style.visibility === 'hidden') return
      const tw = el.offsetWidth
      const th = el.offsetHeight
      let x = e.clientX + 12
      let y = e.clientY + 12
      if (x + tw > window.innerWidth - 8) x = e.clientX - tw - 12
      if (y + th > window.innerHeight - 8) y = e.clientY - th - 12
      el.style.left = `${x}px`
      el.style.top = `${y}px`
    }

    document.addEventListener('mouseover', onMouseOver, true)
    document.addEventListener('mouseout', onMouseOut, true)
    document.addEventListener('mousemove', onMouseMove, { passive: true })

    return () => {
      document.removeEventListener('mouseover', onMouseOver, true)
      document.removeEventListener('mouseout', onMouseOut, true)
      document.removeEventListener('mousemove', onMouseMove, true)
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [showTooltip, hideTooltip])

  return createPortal(
    <div
      ref={tooltipRef}
      className="global-mouse-tooltip"
      style={{
        position: 'fixed',
        zIndex: 99999,
        visibility: 'hidden',
        opacity: 0,
        pointerEvents: 'none',
        transition: 'opacity 0.15s ease',
      }}
    />,
    document.body,
  )
}
