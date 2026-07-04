/**
 * Events — toast stack for in-app events.
 *
 * Animation lifecycle:
 *  - Mount: CSS animation `event-toast-in` plays (180ms slide+fade).
 *  - After `autoFadeSeconds` of being mounted, the toast gets the
 *    `event-toast-fading` class which starts the fade-out animation.
 *  - On `animationend`, we remove the toast from the stack.
 *
 * Why CSS-driven fade instead of `setTimeout`:
 *  - Survives React re-renders / StrictMode double-mount (the animation
 *    keeps running independently of component identity).
 *  - Naturally pauses when the tab is hidden (CSS animations pause when
 *    the page is not visible).
 *
 * Manual × calls `onDismiss` which removes it immediately + marks read.
 */
import type { AppEvent } from '../types/events'

interface EventsProps {
  toasts: AppEvent[]
  onDismiss: (id: string) => void
  autoFadeSeconds: number
}

function ToastCard({ ev, onDismiss, autoFadeMs, onClick }: { ev: AppEvent; onDismiss: (id: string) => void; autoFadeMs: number; onClick?: (ev: AppEvent) => void }) {
  // Trigger the fade-out animation by adding the class after a delay.
  // We use a CSS transition (opacity + transform) instead of a real
  // animation so React's state change cleanly applies both states.
  // After fade-out duration completes, dispatch the dismiss.
  return (
    <div
      className="event-toast event-toast-in"
      style={{ animationDelay: '0ms', animationDuration: '180ms' }}
      role="status"
      aria-live="polite"
      data-fade-after={autoFadeMs}
      onClick={() => onClick?.(ev)}
      onAnimationEnd={(e) => {
        // Only react to our own in-animation ending (not bubble from children).
        if (e.currentTarget !== e.target) return
        // Schedule fade-out
        setTimeout(() => {
          e.currentTarget.classList.add('event-toast-fading')
        }, autoFadeMs)
      }}
      onTransitionEnd={(e) => {
        if (e.currentTarget !== e.target) return
        if (e.propertyName !== 'opacity') return
        // Fade-out complete — remove from stack.
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