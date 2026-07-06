import { useCallback, type FormEvent, type Dispatch, type SetStateAction } from 'react'
import type { Message } from '../components/chatTypes'
import type { ToolCall } from '../components/ToolTimeline'
import type { AgentConfig } from '../components/Sidebar'
import type { ImageAttachment } from '../components/ImageAttachment'
import { HIDDEN_TOOLS } from '../components/ToolTimeline'

type WsSend = (type: string, payload: Record<string, any>) => boolean
type WsOn = (type: string, handler: (data: any) => void) => () => void

export interface UseChatSubmitParams {
  input: string
  attachments: { dataUrl: string }[]
  isTyping: boolean
  activeAgent: AgentConfig | null
  textareaRef: React.RefObject<HTMLTextAreaElement | null>
  isStreamingRef: React.RefObject<boolean>
  setInput: (v: string) => void
  setAttachments: Dispatch<SetStateAction<ImageAttachment[]>>
  setMessages: Dispatch<SetStateAction<Message[] | null>>
  setIsTyping: (v: boolean) => void
  setCompactionNotice: (n: string | null) => void
  wsSend: WsSend
  wsOn: WsOn
}

export interface UseChatSubmitReturn {
  handleSubmit: (e: FormEvent) => Promise<void>
  handleKeyDown: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void
}

/**
 * Parse <think>...</think> tags out of streaming text chunks.
 */
function processChunk(text: string, inThinkingRef: { value: boolean }): { thinking: string; content: string } {
  let thinking = ''
  let content = ''
  let remaining = text
  while (remaining.length > 0) {
    if (inThinkingRef.value) {
      const closeIdx = remaining.indexOf('</think>')
      if (closeIdx === -1) {
        thinking += remaining
        remaining = ''
      } else {
        thinking += remaining.slice(0, closeIdx)
        remaining = remaining.slice(closeIdx + 12)
        inThinkingRef.value = false
      }
    } else {
      const openIdx = remaining.indexOf('<think>')
      if (openIdx === -1) {
        content += remaining
        remaining = ''
      } else {
        content += remaining.slice(0, openIdx)
        remaining = remaining.slice(openIdx + 7)
        inThinkingRef.value = true
      }
    }
  }
  return { thinking, content }
}

export function useChatSubmit(params: UseChatSubmitParams): UseChatSubmitReturn {
  const {
    input, attachments, isTyping, activeAgent,
    textareaRef, isStreamingRef,
    setInput, setAttachments, setMessages, setIsTyping, setCompactionNotice,
    wsSend, wsOn,
  } = params

  const handleSubmit = useCallback(async (e: FormEvent) => {
    e.preventDefault()
    if (!input.trim() && attachments.length === 0) return

    void isTyping

    const userImages = attachments.map(a => a.dataUrl)
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim() || (attachments.length > 0 ? `[Image${attachments.length > 1 ? ` (${attachments.length})` : ''}]` : ''),
      timestamp: new Date(),
      images: userImages.length > 0 ? userImages : undefined,
    }

    const userInput = input
    setInput('')
    setAttachments([])
    if (textareaRef.current) textareaRef.current.style.height = 'auto'

    setIsTyping(true)
    isStreamingRef.current = true

    const assistantId = (Date.now() + 1).toString()
    setMessages(prev => [...(prev ?? []), userMsg, {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      tools: [],
    }])

    const activeTools: ToolCall[] = []
    let toolIndex = 0
    let fullContent = ''
    let fullThinking = ''
    let gotChunk = false
    // Track last appended chunk text — if the same payload arrives twice
    // in a row (WS re-broadcast, transport retry), skip the duplicate.
    // Backend streams incremental deltas so identical adjacent chunks are
    // never legitimate new content.
    let lastChunkText = ''
    const inThinkingRef = { value: false }

    const cleanupFns: (() => void)[] = []

    const onChunk = wsOn('chat:chunk', (msg: any) => {
      if (msg.agent_slug !== activeAgent?.slug) return
      const text = String(msg.content ?? '')
      if (text === lastChunkText) return  // dedup identical re-broadcast
      lastChunkText = text
      gotChunk = true
      const { thinking: t, content: c } = processChunk(text, inThinkingRef)
      if (t) fullThinking += t
      if (c) fullContent += c
      setMessages(prev => (prev ?? []).map(m => m.id === assistantId ? { ...m, content: fullContent, thinking: fullThinking || undefined } : m))
    })

    const onToolStart = wsOn('chat:tool_start', (msg: any) => {
      if (msg.agent_slug !== activeAgent?.slug) return
      const toolName = String(msg.tool || '')
      if (HIDDEN_TOOLS.has(toolName)) { toolIndex++; return }
      const tc: ToolCall = { id: `${assistantId}-tool-${toolIndex++}`, name: toolName, params: (msg.params as Record<string, unknown>) || {}, status: 'running' }
      activeTools.push(tc)
      setMessages(prev => (prev ?? []).map(m => m.id === assistantId ? { ...m, tools: [...activeTools] } : m))
    })

    const onToolEnd = wsOn('chat:tool_end', (msg: any) => {
      if (msg.agent_slug !== activeAgent?.slug) return
      const toolName = String(msg.tool || '')
      if (HIDDEN_TOOLS.has(toolName)) return
      const idx = activeTools.findIndex(t => t.name === toolName && t.status === 'running')
      if (idx !== -1 && activeTools[idx]) {
        activeTools[idx].status = msg.success ? 'completed' : 'error'
        activeTools[idx].result = String(msg.result || '')
        activeTools[idx].error = msg.error ? String(msg.error) : undefined
      }
      setMessages(prev => (prev ?? []).map(m => m.id === assistantId ? { ...m, tools: [...activeTools] } : m))
    })

    const onDone = wsOn('chat:done', (msg: any) => {
      if (msg.agent_slug !== activeAgent?.slug) return
      isStreamingRef.current = false
      setMessages(prev => {
        const updated = prev ?? []
        if (!gotChunk) return updated.filter(m => m.id !== assistantId)
        return updated.map(m => {
          if (m.id !== assistantId) return m
          const content = m.content || ''
          if (content.includes('[Компакция') || content.includes('[Суммаризация')) {
            const match = content.match(/\[(Компакция[^\]]*|Суммаризация[^\]]*)\]/)
            if (match) {
              setCompactionNotice(match[0])
              setTimeout(() => setCompactionNotice(null), 5000)
            }
          }
          return { ...m, model: msg.model || 'assistant', agent_name: msg.agent_name, prompt_tokens: msg.usage?.prompt_tokens, completion_tokens: msg.usage?.completion_tokens }
        })
      })
      cleanup()
    })

    const onError = wsOn('chat:error', (msg: any) => {
      isStreamingRef.current = false
      cleanup()
      setMessages(prev => (prev ?? []).map(m => m.id === assistantId ? { ...m, content: m.content || `⚠️ Error: ${msg.message || 'Stream error'}` } : m))
    })

    const cleanup = () => {
      cleanupFns.forEach(fn => fn())
      setIsTyping(false)
    }

    cleanupFns.push(onChunk, onToolStart, onToolEnd, onDone, onError)

    wsSend('chat:send', {
      agent_slug: activeAgent?.slug || '',
      message: userInput,
      channel_id: 'web',
      images: userImages.length > 0 ? userImages : undefined,
    })
  }, [input, attachments, isTyping, activeAgent, wsSend, wsOn])

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }, [handleSubmit])

  return { handleSubmit, handleKeyDown }
}