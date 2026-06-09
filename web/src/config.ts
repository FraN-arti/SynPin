/**
 * API & WebSocket configuration — single source of truth.
 *
 * Uses RELATIVE URLs so the frontend works regardless of how it's accessed:
 *   - Dev mode:   Vite proxy forwards /api/* and /ws/* → localhost:2088
 *   - Production: backend serves frontend on same port (2088)
 *   - Tailscale:  browser → tailscale-ip:2099 → Vite proxy → localhost:2088
 *
 * When IP/port changes — update only settings.yaml, restart backend. Done.
 */

/** Base URL for REST API calls (empty string = relative) */
export const API_BASE = ''

/** WebSocket URL, derived from current page origin */
function buildWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws`
}

/** WebSocket endpoint */
export const WS_URL = buildWsUrl()
