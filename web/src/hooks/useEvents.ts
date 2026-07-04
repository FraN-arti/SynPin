/**
 * useEvents — subscribe to the EventBus stream and manage local toast state.
 *
 * Sources of toasts:
 *  1. REST `/api/events?limit=20` on mount — surfaces events that fired
 *     before the WS handshake finished.
 *  2. WS `event:new` frames — live updates while the app is open.
 *  3. WS `event:read` frames — removes toasts dismissed in another tab.
 *
 * Auto-fade: NOT handled here. `Events.tsx` uses a CSS `animation`
 * with `animation-fill-mode: forwards` and removes the toast on
 * `animationend` — survives re-renders, doesn't depend on JS timers.
 *
 * Source-aware filtering (set via `isEventRelevant`): if the user is
 * currently in the chat of the agent that just replied, skip the toast
 * (the message is already on-screen in the active panel).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { API_BASE } from '../config'
import type { AppEvent, InAppSettings } from '../types/events'

const DEFAULT_SETTINGS: InAppSettings = {
  enabled: true,
  auto_fade_seconds: 8,
  max_visible: 4,
}

interface UseEventsOptions {
  wsOn?: (type: string, handler: (data: any) => void) => () => void
  /**
   * Called when the user clicks a toast (not the close button). Receives
   * the underlying AppEvent so the caller can navigate to its source.
   */
  onToastClick?: (ev: AppEvent) => void
}

export interface UseEventsResult {
  toasts: AppEvent[]
  unreadCount: number
  settings: InAppSettings
  updateSettings: (patch: Partial<InAppSettings>) => Promise<InAppSettings>
  dismiss: (id: string) => void
  markAllRead: () => Promise<void>
  clear: () => Promise<void>
}

export function useEvents({
  wsOn,
  onToastClick,
}: UseEventsOptions = {}): UseEventsResult {
  const [toasts, setToasts] = useState<AppEvent[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [settings, setSettings] = useState<InAppSettings>(DEFAULT_SETTINGS)

  // IDs we've already shown — protects against REST + WS showing the same event.
  const seenIds = useRef<Set<string>>(new Set())

  // Click handler ref — keeps handler closure fresh without re-subscribing WS.
  const clickRef = useRef(onToastClick)
  useEffect(() => { clickRef.current = onToastClick }, [onToastClick])

  // Settings ref — used by handler before settings state propagates.
  const settingsRef = useRef(settings)
  useEffect(() => { settingsRef.current = settings }, [settings])

  // ── Mount: load settings + surface unread ───────────────────────
  useEffect(() => {
    let alive = true
    fetch(`${API_BASE}/api/events/settings`)
      .then(r => r.json())
      .then((data: { in_app: InAppSettings }) => {
        if (alive && data?.in_app) setSettings(data.in_app)
      })
      .catch(() => {})

    fetch(`${API_BASE}/api/events?limit=20`)
      .then(r => r.json())
      .then((data: { unread_count: number; items: AppEvent[] }) => {
        if (!alive) return
        setUnreadCount(data.unread_count ?? 0)
        const unread = (data.items || []).filter((e: AppEvent) => !e.read_at)
        // Newest first from API; show the most recent max_visible.
        const visible = unread.slice(0, settingsRef.current.max_visible)
        for (const ev of visible.reverse()) {
          pushToast(ev)
        }
      })
      .catch(() => {})

    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── WS subscriptions ────────────────────────────────────────────
  useEffect(() => {
    if (!wsOn) return
    const offNew = wsOn('event:new', (ev: AppEvent) => {
      if (!ev || !ev.id) return
      pushToast(ev)
      setUnreadCount(c => c + 1)
    })

    const offRead = wsOn('event:read', (data: { id: string }) => {
      if (!data?.id) return
      setToasts(prev => prev.filter(t => t.id !== data.id))
      setUnreadCount(c => Math.max(0, c - 1))
    })

    return () => { offNew(); offRead() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsOn])

  function pushToast(ev: AppEvent) {
    if (seenIds.current.has(ev.id)) return
    seenIds.current.add(ev.id)
    setToasts(prev => {
      const next = [...prev, ev]
      return next.slice(-settingsRef.current.max_visible)
    })
  }

  // ── Mutations ───────────────────────────────────────────────────
  const dismiss = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
    fetch(`${API_BASE}/api/events/${id}/read`, { method: 'POST' }).catch(() => {})
  }, [])

  const markAllRead = useCallback(async () => {
    await fetch(`${API_BASE}/api/events/read-all`, { method: 'POST' }).catch(() => {})
    setUnreadCount(0)
  }, [])

  const clear = useCallback(async () => {
    await fetch(`${API_BASE}/api/events/clear`, { method: 'POST' }).catch(() => {})
    setToasts([])
    setUnreadCount(0)
  }, [])

  const updateSettings = useCallback(async (patch: Partial<InAppSettings>): Promise<InAppSettings> => {
    const res = await fetch(`${API_BASE}/api/events/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    })
    if (!res.ok) throw new Error(`settings update failed: ${res.status}`)
    const data = await res.json()
    const next = data?.in_app ?? settings
    setSettings(next)
    return next
  }, [settings])

  return {
    toasts,
    unreadCount,
    settings,
    updateSettings,
    dismiss,
    markAllRead,
    clear,
  }
}