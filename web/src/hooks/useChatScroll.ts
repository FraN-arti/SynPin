/**
 * useChatScroll — unified auto-scroll hook for chat views.
 *
 * Pattern: sentinel-based scroll. A <div ref={callbackRef} /> is placed at
 * the bottom of the message list. Two triggers:
 *
 * 1. Callback ref: fires when the sentinel mounts into the DOM (covers F5 /
 *    initial history load where useLayoutEffect can race with async state).
 * 2. useLayoutEffect on [messages]: covers new messages arriving while the
 *    chat is already open.
 *
 * Both use scrollIntoView({ block: 'end' }) which finds the nearest
 * scrollable ancestor automatically.
 *
 * Usage:
 *   const { sentinelRef, scrollToBottom } = useChatScroll(messages)
 *   // In JSX: <div ref={sentinelRef} />
 *   // scrollToBottom() for manual triggers (e.g. after sending)
 */

import { useRef, useLayoutEffect, useCallback } from 'react'

export function useChatScroll<T>(messages: T[] | null) {
  const endRef = useRef<HTMLDivElement>(null)

  // Callback ref — fires when the sentinel mounts into the DOM.
  // This covers the F5 / initial-load case where useLayoutEffect may race
  // with async history restoration.
  const callbackRef = useCallback((node: HTMLDivElement | null) => {
    if (!node) return
    // Use rAF to ensure layout is settled before scrolling
    requestAnimationFrame(() => {
      node.scrollIntoView({ behavior: 'smooth', block: 'end' })
    })
  }, [])

  // Merge: attach both the stored ref (for manual access) and the callback ref
  const sentinelRef = useCallback(
    (node: HTMLDivElement | null) => {
      endRef.current = node
      callbackRef(node)
    },
    [callbackRef],
  )

  // Auto-scroll on every messages change (covers streaming, new messages, etc.)
  useLayoutEffect(() => {
    if (!messages || messages.length === 0) return
    // If the ref is already attached, scroll immediately
    if (endRef.current) {
      endRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' })
    }
  }, [messages])

  // Manual scroll-to-bottom (e.g. after sending a message)
  const scrollToBottom = useCallback(() => {
    const target = endRef.current
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'end' })
    }
  }, [])

  return { sentinelRef, scrollToBottom }
}
