/**
 * Events — toast stack for in-app events.
 *
 * Renders bottom-right, newest at bottom, each card level-tinted.
 * Auto-fade after settings.auto_fade_seconds (default 8s). Manual × dismisses.
 *
 * Reads state from useEvents() — no own state here, this is a pure renderer.
 */
import { useEffect, useRef } from 'react'
import type { AppEvent } from '../types/events'

interface EventsProps {
  toasts: AppEvent[]
  onDismiss: (id: string) => void
  /** Seconds before a toast auto-fades. */
  autoFadeSeconds: number
}

function levelClass(level: AppEvent['level']): string {
  return `event-toast event-toast-${level}`
}

function ToastCard({ ev, onDismiss, autoFadeMs }: { ev: AppEvent; onDismiss: (id: string) => void; autoFadeMs: number }) {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    timer.current = setTimeout(() => onDismiss(ev.id), autoFadeMs)
    return () => {
      if (timer.current) clearTimeout(timer.current)
    }
  }, [ev.id, autoFadeMs, onDismiss])

  return (
    <div className={levelClass(ev.level)} role="status" aria-live="polite">
      <div className="event-toast-body">
        <div className="event-toast-title">{ev.title}</div>
        <div className="event-toast-text">{ev.body}</div>
      </div>
      <button
        type="button"
        className="event-toast-close"
        aria-label="Закрыть"
        onClick={() => onDismiss(ev.id)}
      >
        ×
      </button>
    </div>
  )
}

export function Events({ toasts, onDismiss, autoFadeSeconds }: EventsProps) {
  if (toasts.length === 0) return null
  const autoFadeMs = Math.max(1000, autoFadeSeconds * 1000)

  return (
    <div className="event-stack" aria-label="Уведомления">
      {toasts.map(ev => (
        <ToastCard key={ev.id} ev={ev} onDismiss={onDismiss} autoFadeMs={autoFadeMs} />
      ))}
    </div>
  )
}