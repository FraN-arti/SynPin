/**
 * useEvents — subscribe to the EventBus stream and manage local toast state.
 *
 * Responsibilities:
 *  - WS subscribe: append `event:new` payloads to the toast stack, trim to
 *    `settings.max_visible`. Apply `event:read` removals.
 *  - REST: load current in-app settings, send dismiss / mark-all / clear.
 *  - Sync across tabs: a dismiss in tab A removes the toast in tab B via
 *    the broadcasted `event:read` event.
 *
 * Mounted once in App.tsx; the rendered `<Events />` consumes the same
 * hook instance via a small context to avoid duplicate subscriptions.
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
  /** WS subscribe helper from useWebSocket(): (type, handler) => unsubscribe */
  wsOn?: (type: string, handler: (data: any) => void) => () => void
}

export interface UseEventsResult {
  toasts: AppEvent[]
  unreadCount: number
  settings: InAppSettings
  /** Persist new settings (partial: pass any subset). Returns the new effective settings. */
  updateSettings: (patch: Partial<InAppSettings>) => Promise<InAppSettings>
  /** Dismiss a single toast → marks it read on the backend. */
  dismiss: (id: string) => void
  /** Mark all unread events as read. */
  markAllRead: () => Promise<void>
  /** Wipe all events on the backend (settings action). */
  clear: () => Promise<void>
}

export function useEvents({ wsOn }: UseEventsOptions = {}): UseEventsResult {
  const [toasts, setToasts] = useState<AppEvent[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [settings, setSettings] = useState<InAppSettings>(DEFAULT_SETTINGS)

  // Track which IDs we've already pushed into the toast stack to avoid
  // double-add on React StrictMode double-invocation of effects.
  const seenIds = useRef<Set<string>>(new Set())

  // ── Load settings + initial unread count on mount ───────────────
  useEffect(() => {
    let alive = true
    fetch(`${API_BASE}/api/events/settings`)
      .then(r => r.json())
      .then((data: { in_app: InAppSettings }) => {
        if (alive && data?.in_app) setSettings(data.in_app)
      })
      .catch(() => { /* keep defaults */ })

    fetch(`${API_BASE}/api/events?limit=20`)
      .then(r => r.json())
      .then((data: { unread_count: number; items: AppEvent[] }) => {
        if (!alive) return
        setUnreadCount(data.unread_count ?? 0)
        // No toasts pre-populated on mount — toasts are for things that
        // happen *while* the user is in the app. Reconnect scenarios
        // can be revisited later.
      })
      .catch(() => { /* ignore */ })

    return () => { alive = false }
  }, [])

  // ── WS subscriptions ────────────────────────────────────────────
  useEffect(() => {
    if (!wsOn) return
    const offNew = wsOn('event:new', (ev: AppEvent) => {
      if (!ev || !ev.id) return
      if (seenIds.current.has(ev.id)) return
      seenIds.current.add(ev.id)

      setToasts(prev => {
        // Trim to max_visible — drop oldest
        const next = [...prev, ev]
        return next.slice(-settingsRef.current.max_visible)
      })
      setUnreadCount(c => c + 1)
    })

    const offRead = wsOn('event:read', (data: { id: string }) => {
      if (!data?.id) return
      setToasts(prev => prev.filter(t => t.id !== data.id))
      setUnreadCount(c => Math.max(0, c - 1))
    })

    return () => { offNew(); offRead() }
  }, [wsOn])

  // Keep settings accessible from the WS handler closure (avoids stale closure
  // when settings change after the subscription is set up).
  const settingsRef = useRef(settings)
  useEffect(() => { settingsRef.current = settings }, [settings])

  // ── Mutations ───────────────────────────────────────────────────
  const dismiss = useCallback((id: string) => {
    // Optimistically remove from local toast stack
    setToasts(prev => prev.filter(t => t.id !== id))
    // Tell the backend (and other tabs)
    fetch(`${API_BASE}/api/events/${id}/read`, { method: 'POST' }).catch(() => {})
  }, [])

  const markAllRead = useCallback(async () => {
    await fetch(`${API_BASE}/api/events/read-all`, { method: 'POST' }).catch(() => {})
    // The server broadcasts event:read for each, so our WS subscription
    // will clear the toast stack. Just zero the count locally too.
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