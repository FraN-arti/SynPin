/**
 * Events — toast stack for in-app events.
 *
 * Lifecycle:
 *  - Mount: CSS animation `event-toast-in` plays (180ms slide+fade).
 *  - After `autoFadeMs`, the `event-toast-fading` class is added which
 *    starts the 0.25s opacity transition (defined in events.css).
 *  - 300ms later (just past the CSS transition) we call onDismiss to
 *    remove the toast from state and post a read receipt.
 *
 * Why setTimeout-in-useEffect instead of onTransitionEnd:
 *  - onTransitionEnd was unreliable: when React re-mounts a toast card
 *    with the same id (e.g. after WS reconnect), the previous DOM node's
 *    transitionend could fire and dismiss a brand new toast.
 *  - Two setTimeouts give us predictable cleanup: if the component
 *    unmounts (manual ×, parent re-render, StrictMode double-mount),
 *    both timers cancel cleanly.
 */
import { useEffect, useRef } from 'react'
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
  const toastRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const node = toastRef.current
    if (!node) return
    let dismissTimer: number | undefined
    const showTimer = window.setTimeout(() => {
      node.classList.add('event-toast-fading')
      dismissTimer = window.setTimeout(() => onDismiss(ev.id), 300)
    }, autoFadeMs)
    return () => {
      window.clearTimeout(showTimer)
      if (dismissTimer !== undefined) window.clearTimeout(dismissTimer)
    }
  }, [ev.id, autoFadeMs, onDismiss])

  return (
    <div
      ref={toastRef}
      data-event-id={ev.id}
      className="event-toast event-toast-in"
      style={{ animationDelay: '0ms', animationDuration: '180ms' }}
      role="status"
      aria-live="polite"
      onClick={() => onClick?.(ev)}
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