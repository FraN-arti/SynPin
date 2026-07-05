/**
 * useEvents — subscribe to the EventBus stream and manage local toast state.
 *
 * Sources of toasts:
 *  1. REST `/api/events?limit=20` on mount — surfaces events that fired
 *     before the WS handshake finished.
 *  2. WS `event:new` frames — live updates while the app is open.
 *  3. WS `event:read` frames — removes toasts dismissed in another tab.
 *
 * Auto-fade: NOT handled here. `Events.tsx` uses a CSS transition
 * triggered by an animation-end listener — survives re-renders and
 * StrictMode, doesn't depend on JS timers.
 *
 * No client-side dedup: every event has a unique uuid from the
 * server, and the server's `publish_event` is the only producer. A
 * seenIds cache would actually break reconnect scenarios where the
 * WS is briefly offline while an event is broadcast — that event
 * would then be marked "seen" via REST but never shown as a toast.
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

  // Click handler ref — keeps handler closure fresh without re-subscribing WS.
  const clickRef = useRef(onToastClick)
  useEffect(() => { clickRef.current = onToastClick }, [onToastClick])

  // Settings ref — used by handler before settings state propagates.
  const settingsRef = useRef(settings)
  useEffect(() => { settingsRef.current = settings }, [settings])

  // Track if the WS subscription is currently active — used by pushToast.
  const subscribedRef = useRef(false)
  // Track event IDs that have already been added to the toast stack
  // in the current session (prevents React StrictMode double-add).
  const localIds = useRef<Set<string>>(new Set())

  // ── Mount: load settings + surface unread ───────────────────────
  useEffect(() => {
    let alive = true
    fetch(`${API_BASE}/api/events/settings`)
      .then(r => r.json())
      .then((data: { in_app: InAppSettings }) => {
        if (alive && data?.in_app) setSettings(data.in_app)
      })
      .catch((e) => console.error('[useevents] load events failed:', e))

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
      .catch((e) => console.error('[useevents] load events failed:', e))

    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── WS subscriptions ────────────────────────────────────────────
  useEffect(() => {
    if (!wsOn) return
    subscribedRef.current = true
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

    return () => {
      subscribedRef.current = false
      offNew()
      offRead()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsOn])

  function pushToast(ev: AppEvent) {
    // Cheap dedup against double-pushing the same event in one session
    // (e.g. REST load + WS re-broadcast in the same render cycle).
    if (localIds.current.has(ev.id)) return
    localIds.current.add(ev.id)
    setToasts(prev => {
      const next = [...prev, ev]
      return next.slice(-settingsRef.current.max_visible)
    })
  }

  // ── Mutations ───────────────────────────────────────────────────
  const dismiss = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
    // Drop the id from the local-seen set so a re-broadcast of the same
    // event (e.g. after WS reconnect) can still surface as a toast.
    // Without this, localIds grows unbounded and silently suppresses
    // legitimate retries — which is exactly why F5 used to "fix" things:
    // F5 remounts the hook, the Set is reset, and the missed event
    // finally shows.
    localIds.current.delete(id)
    fetch(`${API_BASE}/api/events/${id}/read`, { method: 'POST' }).catch((e) => console.warn('[useevents] mark read failed:', e))
  }, [])

  const markAllRead = useCallback(async () => {
    await fetch(`${API_BASE}/api/events/read-all`, { method: 'POST' }).catch((e) => console.warn('[useevents] mark read failed:', e))
    setUnreadCount(0)
  }, [])

  const clear = useCallback(async () => {
    await fetch(`${API_BASE}/api/events/clear`, { method: 'POST' }).catch((e) => console.warn('[useevents] mark read failed:', e))
    setToasts([])
    setUnreadCount(0)
    localIds.current.clear()
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