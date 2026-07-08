/**
 * HoldToDeleteButton — confirm via 1.5s hold instead of a modal.
 *
 * Why: modals for destructive actions add friction (extra click + reading)
 * but instant-delete is too dangerous. Hold-to-confirm is the middle
 * ground — progressive SVG ring gives visual feedback, release cancels.
 *
 * Same shape as the cron hold button (cron-hold-btn) but generic:
 * works for departments, agents, projects, anything destructive.
 *
 * Usage:
 *   <HoldToDeleteButton onConfirm={() => deleteOtdel(id)} label="Удалить" />
 */
import { useRef, useState, type CSSProperties } from 'react'

const HOLD_MS = 1500

interface HoldToDeleteButtonProps {
  /** Called once the user holds for the full duration. */
  onConfirm: () => void | Promise<void>
  /** Button label, e.g. "Удалить". */
  label?: string
  /** Tooltip — explains the hold interaction. */
  title?: string
  /** Disable the button (e.g. during a save). */
  disabled?: boolean
}

export function HoldToDeleteButton({
  onConfirm,
  label = 'Удалить',
  title = 'Удерживай 1.5с чтобы удалить',
  disabled = false,
}: HoldToDeleteButtonProps) {
  const [progress, setProgress] = useState(0)
  const startRef = useRef<number>(0)
  const frameRef = useRef<number | null>(null)
  const safetyRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const firedRef = useRef(false)

  const cancel = () => {
    if (frameRef.current !== null) {
      cancelAnimationFrame(frameRef.current)
      frameRef.current = null
    }
    if (safetyRef.current !== null) {
      clearTimeout(safetyRef.current)
      safetyRef.current = null
    }
    startRef.current = 0
    firedRef.current = false
    setProgress(0)
  }

  const start = () => {
    if (disabled || startRef.current !== 0) return
    startRef.current = performance.now()
    firedRef.current = false

    const tick = () => {
      const elapsed = performance.now() - startRef.current
      const p = Math.min(1, elapsed / HOLD_MS)
      setProgress(p)
      if (p < 1) {
        frameRef.current = requestAnimationFrame(tick)
      } else if (!firedRef.current) {
        firedRef.current = true
        // Fire-and-forget; errors are the caller's responsibility.
        void onConfirm()
      }
    }
    frameRef.current = requestAnimationFrame(tick)
    // Safety net: rAF stops firing when the tab is backgrounded on
    // some browsers. Clear it once we're past the hold window.
    safetyRef.current = setTimeout(() => {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current)
        frameRef.current = null
      }
    }, HOLD_MS + 200)
  }

  const isHolding = progress > 0
  const r = 10
  const circumference = 2 * Math.PI * r

  return (
    <button
      onMouseDown={start}
      onMouseUp={cancel}
      onMouseLeave={cancel}
      onTouchStart={start}
      onTouchEnd={cancel}
      className={`hold-to-delete-btn ${isHolding ? 'holding' : ''}`}
      disabled={disabled}
      title={title}
      style={{ '--hold-progress': progress } as CSSProperties}
    >
      <svg className="hold-to-delete-ring" viewBox="0 0 24 24">
        <circle className="hold-to-delete-ring-bg" cx="12" cy="12" r={r} />
        <circle
          className="hold-to-delete-ring-progress"
          cx="12" cy="12" r={r}
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - progress)}
        />
      </svg>
      <span className="hold-to-delete-label">
        {progress > 0 ? 'Удерживай...' : label}
      </span>
    </button>
  )
}