/**
 * useChatHistory — loads chat history when active agent changes or
 * the user returns to the chat view.
 *
 * Behaviour:
 *  - On mount/agent-switch, fetch /api/chat/history.
 *  - If the last message is a user message with no assistant reply
 *    (a background task is in flight), insert a placeholder assistant
 *    bubble and set isTyping. After 5s, refetch once to catch any
 *    response that arrived during the gap (one-shot, no polling).
 *  - Cancellation flag is set on unmount so stale fetches don't
 *    overwrite newer state.
 */

import { useEffect } from 'react'
import type { Message } from '../components/chatTypes'
import type { ToolCall } from '../components/ToolTimeline'
import type { AgentConfig } from '../components/Sidebar'
import { API_BASE } from '../config'

export interface UseChatHistoryParams {
  activeAgent: AgentConfig | null
  viewType: string
  setMessages: (m: Message[] | null | ((prev: Message[] | null) => Message[] | null)) => void
  setIsTyping: (v: boolean) => void
}

interface RawMessage {
  role: string
  content: string
  timestamp?: string
  model?: string
  agent_name?: string
  prompt_tokens?: number
  completion_tokens?: number
  tools?: ToolCall[]
}

function restoreMessages(rawMsgs: RawMessage[]): Message[] {
  return rawMsgs.map((m, i) => ({
    id: `restored-${i}`,
    role: m.role as 'user' | 'assistant',
    content: m.content,
    timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
    model: m.model,
    agent_name: m.agent_name,
    prompt_tokens: m.prompt_tokens,
    completion_tokens: m.completion_tokens,
    tools: m.tools,
  }))
}

export function useChatHistory({
  activeAgent, viewType, setMessages, setIsTyping,
}: UseChatHistoryParams): void {
  useEffect(() => {
    if (!activeAgent || viewType !== 'chat') return

    setMessages(null)
    let cancelled = false

    const fetchHistory = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/chat/history?agent_slug=${activeAgent.slug}&channel_id=web&limit=20`)
        if (cancelled) return
        if (!res.ok) { setMessages([]); return }
        const data = await res.json()
        const msgs: RawMessage[] = data.messages || []

        if (msgs.length === 0) { setMessages([]); return }

        const lastMsg = msgs[msgs.length - 1]
        const hasPendingTask = lastMsg?.role === 'user'
        const restored = restoreMessages(msgs)
        const lastRestored = restored[restored.length - 1]
        const alreadyHasPlaceholder = lastRestored?.role === 'assistant' && !lastRestored.content

        if (hasPendingTask && !alreadyHasPlaceholder) {
          restored.push({
            id: `placeholder-${Date.now()}`,
            role: 'assistant',
            content: '',
            timestamp: new Date(),
            tools: [],
          })
          setIsTyping(true)

          // Safety refetch: catch responses that arrived between history load and WS connect.
          // One-shot, 5s delay, no polling loop.
          setTimeout(async () => {
            if (cancelled) return
            try {
              const retryRes = await fetch(`${API_BASE}/api/chat/history?agent_slug=${activeAgent.slug}&channel_id=web&limit=20`)
              if (!retryRes.ok) return
              const retryData = await retryRes.json()
              const retryMsgs: RawMessage[] = retryData.messages || []
              const lastRetryMsg = retryMsgs[retryMsgs.length - 1]
              if (lastRetryMsg?.role === 'assistant') {
                setMessages(prev => {
                  const list = prev ?? []
                  const placeholderId = list.map(m => m.id).reverse().find(id => {
                    const msg = list.find(m => m.id === id)
                    return msg?.role === 'assistant' && !msg.content
                  })
                  if (!placeholderId) return list
                  setIsTyping(false)
                  return list.map(m => m.id === placeholderId
                    ? { ...m, content: lastRetryMsg.content, model: lastRetryMsg.model, agent_name: lastRetryMsg.agent_name, prompt_tokens: lastRetryMsg.prompt_tokens, completion_tokens: lastRetryMsg.completion_tokens, tools: lastRetryMsg.tools }
                    : m
                  )
                })
              }
            } catch { /* silent */ }
          }, 5000)
        }

        setMessages(restored)
      } catch (e) {
        if (cancelled) return
        console.error('[history] load error:', e)
        setMessages([])
      }
    }
    fetchHistory()

    return () => { cancelled = true }
  }, [activeAgent, viewType, setMessages, setIsTyping])
}