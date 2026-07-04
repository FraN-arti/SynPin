/**
 * Events — toast stack for in-app events.
 *
 * Lifecycle:
 *  - Mount: CSS animation `event-toast-in` plays (180ms slide+fade).
 *  - After `autoFadeSeconds`, the toast gets the `event-toast-fading`
 *    class which starts the opacity transition.
 *  - On `transitionend` (opacity), we call onDismiss which removes it
 *    from the stack and posts a read receipt.
 *
 * Why setTimeout-in-useEffect instead of onAnimationEnd:
 *  - The previous CSS-driven approach had a race: onAnimationEnd fires
 *    after the 180ms slide-in, but the classList change had to be
 *    scheduled via setTimeout, and onTransitionEnd could leak across
 *    remounts (the same `ev.id` re-mounting after a WS reconnect would
 *    catch a stale transitionend event from the previous DOM node).
 *  - The useEffect approach gives us a real cleanup function so the
 *    timer is cancelled if the toast is dismissed early (manual ×) or
 *    unmounts for any other reason.
 *
 * Manual × calls onDismiss immediately + marks read.
 */
import { useEffect } from 'react'
import type { AppEvent } from '../types/events'

interface EventsProps {
  toasts: AppEvent[]
  onDismiss: (id: string) => void
  autoFadeSeconds: number
}

function ToastCard({ ev, onDismiss, autoFadeMs, onClick }: {
  ev: AppEvent
  onDismiss: (id: string) => void
  autoFadeMs: number
  onClick?: (ev: AppEvent) => void
}) {
  // Schedule fade-out after autoFadeMs. If the component unmounts (manual
  // dismiss, parent re-render that drops this toast, or strict-mode double
  // mount), the cleanup cancels the timer and the classList add — no
  // leak, no stale DOM access.
  useEffect(() => {
    const node = document.querySelector(`[data-event-id="${ev.id}"]`)
    if (!node) return
    const t = window.setTimeout(() => {
      node.classList.add('event-toast-fading')
    }, autoFadeMs)
    return () => window.clearTimeout(t)
  }, [ev.id, autoFadeMs])

  return (
    <div
      data-event-id={ev.id}
      className="event-toast event-toast-in"
      style={{ animationDelay: '0ms', animationDuration: '180ms' }}
      role="status"
      aria-live="polite"
      onClick={() => onClick?.(ev)}
      onTransitionEnd={(e) => {
        // Only react to our own opacity transition. Bubbles from children
        // are filtered by currentTarget !== target.
        if (e.currentTarget !== e.target) return
        if (e.propertyName !== 'opacity') return
        onDismiss(ev.id)
      }}
    >
      <div className="event-toast-body">
        <div className="event-toast-title">{ev.title}</div>
        <div className="event-toast-text">{ev.body}</div>
      </div>
      <button
        type="button"
        className="event-toast-close"
        aria-label="Закрыть"
        onClick={(e) => { e.stopPropagation(); onDismiss(ev.id) }}
      >
        ×
      </button>
    </div>
  )
}

export function Events({ toasts, onDismiss, autoFadeSeconds, onToastClick }: EventsProps & { onToastClick?: (ev: AppEvent) => void }) {
  if (toasts.length === 0) return null
  const autoFadeMs = Math.max(1000, autoFadeSeconds * 1000)

  return (
    <div className="event-stack" aria-label="Уведомления">
      {toasts.map(ev => (
        <ToastCard key={ev.id} ev={ev} onDismiss={onDismiss} autoFadeMs={autoFadeMs} onClick={onToastClick} />
      ))}
    </div>
  )
}
