import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * useUndoWithProgress — generic "delete with 5-second undo toast" hook.
 *
 * Encapsulates the debounce/undo/progress-bar timer quartet that was
 * previously copy-pasted across three SettingsPage sections. The
 * component consuming this hook stays responsible for:
 *   - what to do when undo expires (call the real delete API)
 *   - what to do when the user clicks undo (restore the deleted item)
 *   - how to render the toast (this hook just gives you the data)
 *
 * The hook owns: pendingDelete state, undoProgress (0..100), and the
 * countdown timers. Calling start() arms a new undo window; calling
 * undo() within the window restores and stops the timers.
 *
 * Timer choice: 5000ms undo window, 30ms progress update tick
 * (matches the inline `transition: 'width 30ms linear'` in CSS).
 */
export interface UndoItem<T> {
  /** Unique id of the deleted entity (for restore). */
  id: string
  /** Display label for the toast ("«X» удалена"). */
  label: string
  /** Original index, so caller can splice the item back into a list. */
  index: number
  /** Anything else the caller needs to restore (e.g. color, text_color, description). */
  extras?: T
}

export interface UseUndoWithProgressOptions<T> {
  /** ms before undo expires and the deletion is finalised. */
  durationMs?: number
  /** Called when the timer expires — perform the real delete. */
  onExpire: (item: UndoItem<T>) => void
  /**
   * Called when the user clicks "Отменить" inside the toast — perform
   * the restore. The hook stops the timer; the caller does the splice.
   */
  onUndo: (item: UndoItem<T>) => void
}

export interface UseUndoWithProgressReturn<T> {
  pendingDelete: UndoItem<T> | null
  undoProgress: number
  /** Arm a new undo window. Replaces any in-flight undo. */
  start: (item: UndoItem<T>) => void
  /** Cancel current undo and call onUndo. No-op if no pending delete. */
  undo: () => void
  /** Dismiss toast without calling onExpire/onUndo (e.g. user navigated away). */
  cancel: () => void
}

export function useUndoWithProgress<T = unknown>(
  options: UseUndoWithProgressOptions<T>,
): UseUndoWithProgressReturn<T> {
  const { durationMs = 5000, onExpire, onUndo } = options

  const [pendingDelete, setPendingDelete] = useState<UndoItem<T> | null>(null)
  const [undoProgress, setUndoProgress] = useState(100)

  const undoTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const progressTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  // Hold the current item in a ref so the timers can call onExpire/onUndo
  // with the right value even if state has been replaced by a newer start().
  const currentItemRef = useRef<UndoItem<T> | null>(null)

  const clearTimers = useCallback(() => {
    if (undoTimerRef.current) {
      clearTimeout(undoTimerRef.current)
      undoTimerRef.current = null
    }
    if (progressTimerRef.current) {
      clearInterval(progressTimerRef.current)
      progressTimerRef.current = null
    }
  }, [])

  // On unmount: stop timers, but DO NOT fire the expire callback.
  // Firing expire on unmount was a bug: it meant that navigating
  // away from Settings during the 5-second undo window would
  // silently commit the deletion — the user pressed "Отменить"
  // (or just navigated elsewhere) but the delete went through
  // anyway. The safer default is: if the user navigates away,
  // the deletion is paused (timers stop), and the item is dropped
  // from the toast. If we wanted the "auto-commit on unmount"
  // behaviour we'd have a separate `commit()` method.
  useEffect(() => {
    return () => {
      clearTimers()
    }
  }, [clearTimers])

  const start = useCallback(
    (item: UndoItem<T>) => {
      clearTimers()
      currentItemRef.current = item
      setPendingDelete(item)
      setUndoProgress(100)

      // Progress bar: 100 → 0 over durationMs, ticked every 30ms.
      // (CSS uses transition: width 30ms linear so we update synchronously.)
      const startTime = Date.now()
      progressTimerRef.current = setInterval(() => {
        const elapsed = Date.now() - startTime
        const remaining = Math.max(0, 100 - (elapsed / durationMs) * 100)
        setUndoProgress(remaining)
        if (remaining <= 0) {
          if (progressTimerRef.current) clearInterval(progressTimerRef.current)
          progressTimerRef.current = null
        }
      }, 30)

      undoTimerRef.current = setTimeout(() => {
        clearTimers()
        const final = currentItemRef.current
        currentItemRef.current = null
        setPendingDelete(null)
        if (final) onExpire(final)
      }, durationMs)
    },
    [clearTimers, durationMs, onExpire],
  )

  const undo = useCallback(() => {
    const item = currentItemRef.current
    clearTimers()
    currentItemRef.current = null
    setPendingDelete(null)
    setUndoProgress(100)
    if (item) onUndo(item)
  }, [clearTimers, onUndo])

  const cancel = useCallback(() => {
    clearTimers()
    currentItemRef.current = null
    setPendingDelete(null)
    setUndoProgress(100)
  }, [clearTimers])

  return { pendingDelete, undoProgress, start, undo, cancel }
}
