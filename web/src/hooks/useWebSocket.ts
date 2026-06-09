/**
 * useWebSocket — single WS connection with multiplexed message routing.
 *
 * Usage:
 *   const { send, on } = useWebSocket()
 *   on('chat:chunk', (msg) => { ... })
 *   send('chat:send', { agent_slug, message })
 */
import { useEffect, useRef, useCallback, useState } from 'react'

import { WS_URL } from '../config'
const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000]

type MessageHandler = (data: any) => void

interface WebSocketState {
  connected: boolean
  reconnecting: boolean
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null)
  const handlersRef = useRef<Map<string, Set<MessageHandler>>>(new Map())
  const reconnectAttempt = useRef(0)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [state, setState] = useState<WebSocketState>({ connected: false, reconnecting: false })
  const mountedRef = useRef(true)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    try {
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        reconnectAttempt.current = 0
        if (mountedRef.current) setState({ connected: true, reconnecting: false })
        console.log('[ws] connected')
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          const type = msg.type as string
          const handlers = handlersRef.current.get(type)
          if (handlers) {
            handlers.forEach(h => h(msg))
          }
          // Also fire '*' wildcard handlers
          const wildcard = handlersRef.current.get('*')
          if (wildcard) {
            wildcard.forEach(h => h(msg))
          }
        } catch (e) {
          console.warn('[ws] parse error:', e)
        }
      }

      ws.onclose = () => {
        wsRef.current = null
        if (!mountedRef.current) return
        setState({ connected: false, reconnecting: true })
        scheduleReconnect()
      }

      ws.onerror = () => {
        // onclose will fire after this
      }
    } catch (e) {
      console.error('[ws] connect error:', e)
      scheduleReconnect()
    }
  }, [])

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return
    const delay = RECONNECT_DELAYS[Math.min(reconnectAttempt.current, RECONNECT_DELAYS.length - 1)]
    reconnectAttempt.current++
    console.log(`[ws] reconnecting in ${delay}ms (attempt ${reconnectAttempt.current})`)
    reconnectTimer.current = setTimeout(connect, delay)
  }, [connect])

  const disconnect = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }
    wsRef.current?.close()
    wsRef.current = null
    setState({ connected: false, reconnecting: false })
  }, [])

  const send = useCallback((type: string, payload: Record<string, any> = {}) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn('[ws] not connected, cannot send:', type)
      return false
    }
    ws.send(JSON.stringify({ type, ...payload }))
    return true
  }, [])

  const on = useCallback((type: string, handler: MessageHandler) => {
    if (!handlersRef.current.has(type)) {
      handlersRef.current.set(type, new Set())
    }
    handlersRef.current.get(type)!.add(handler)

    // Return unsubscribe function
    return () => {
      handlersRef.current.get(type)?.delete(handler)
    }
  }, [])

  useEffect(() => {
    mountedRef.current = true
    connect()
    return () => {
      mountedRef.current = false
      disconnect()
    }
  }, [connect, disconnect])

  return { send, on, ...state }
}
