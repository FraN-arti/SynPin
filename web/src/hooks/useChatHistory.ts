import { useEffect } from 'react'
import { API_BASE } from '../config'
import type { Message } from '../components/chatTypes'
import type { AgentConfig } from '../components/Sidebar'

export interface UseChatHistoryParams {
  activeAgent: AgentConfig | null
  viewType: string
  setMessages: (m: Message[] | null | ((prev: Message[] | null) => Message[] | null)) => void
  isStreamingRef: React.MutableRefObject<boolean>
}

interface RawMessage {
  role: string
  content: string
  timestamp?: string
  model?: string
  agent_name?: string
  prompt_tokens?: number
  completion_tokens?: number
  tools?: any[]
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
  activeAgent, viewType, setMessages, isStreamingRef,
}: UseChatHistoryParams): void {
  useEffect(() => {
    if (!activeAgent || viewType !== 'chat') return
    // Don't reload history while SSE is actively streaming
    if (isStreamingRef.current) return

    let cancelled = false

    const fetchHistory = async () => {
      try {
        const res = await fetch(
          `${API_BASE}/api/chat/history?agent_slug=${activeAgent.slug}&channel_id=web&limit=20`
        )
        if (cancelled) return
        if (!res.ok) { setMessages([]); return }
        const data = await res.json()
        const msgs: RawMessage[] = data.messages || []
        if (msgs.length === 0) { setMessages([]); return }
        setMessages(restoreMessages(msgs))
      } catch (e) {
        if (cancelled) return
        console.error('[history] load error:', e)
        setMessages([])
      }
    }
    fetchHistory()
    return () => { cancelled = true }
    // KEY: compare by slug, not by object reference — agent:list_changed
    // creates a new object with the same slug, but that shouldn't reload history
  }, [activeAgent?.slug, viewType, setMessages, isStreamingRef])
}
