/**
 * useChatSubmit — owns the submit/streaming loop for the main chat.
 *
 * Two streaming paths:
 * - Hermes external agents: POST to /api/chat/hermes/stream, read SSE.
 * - SynPin agents: send 'chat:send' over WebSocket, listen for
 *   'chat:chunk' / 'chat:tool_start' / 'chat:tool_end' / 'chat:done' / 'chat:error'.
 *
 * State mutated via setters passed in by the caller (App.tsx). This
 * keeps React's "single source of truth" model intact while letting
 * the streaming logic live outside the App.tsx composition root.
 */

import { useCallback, type FormEvent, type Dispatch, type SetStateAction } from 'react'
import type { Message } from '../components/chatTypes'
import type { ToolCall } from '../components/ToolTimeline'
import type { AgentConfig } from '../components/Sidebar'
import type { ImageAttachment } from '../components/ImageAttachment'
import { HIDDEN_TOOLS } from '../components/ToolTimeline'
import { API_BASE } from '../config'

type WsSend = (type: string, payload: Record<string, any>) => boolean
type WsOn = (type: string, handler: (data: any) => void) => () => void

export interface UseChatSubmitParams {
  input: string
  attachments: { dataUrl: string }[]
  isTyping: boolean
  activeAgent: AgentConfig | null
  textareaRef: React.RefObject<HTMLTextAreaElement | null>
  messagesRef: React.RefObject<Message[] | null>
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
 * Parse <think>...</think> tags out of streaming text chunks. Universal
 * for all models that emit raw reasoning tokens inline with content.
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

function buildSystemPrompt(activeAgent: AgentConfig | null, isHermes: boolean): Promise<string | undefined> {
  if (!activeAgent) return Promise.resolve(undefined)

  if (isHermes) {
    const ctx: string[] = [
      'Ты работаешь внутри платформы SynPin — системы управления агентами (agent-driven organization).',
      'Ты подключён как внешний агент (external agent) в организации SynPin.',
    ]
    if (activeAgent.name) ctx.push(`Твоё имя в SynPin: ${activeAgent.name}`)
    if (activeAgent.role_name) ctx.push(`Твоя роль: ${activeAgent.role_name}`)
    if (activeAgent.department_name) ctx.push(`Твой отдел: ${activeAgent.department_name}`)
    if (activeAgent.system_prompt) ctx.push(activeAgent.system_prompt)
    ctx.push('Если тебя спрашивают где ты или что ты — ты внутри SynPin и можешь помогать с задачами организации.')
    let systemPrompt = ctx.join('\n')

    if (activeAgent.is_primary) {
      return fetch(`${API_BASE}/api/config/main-agent-prompt`)
        .then(r => r.ok ? r.json() : null)
        .then(data => (data?.prompt ? `${systemPrompt}\n\n${data.prompt}` : systemPrompt))
        .catch(() => systemPrompt)
    }
    return Promise.resolve(systemPrompt)
  }

  const parts: string[] = []
  if (activeAgent.name) parts.push(`Имя: ${activeAgent.name}`)
  if (activeAgent.description) parts.push(activeAgent.description)
  if (activeAgent.role_name) parts.push(`Роль: ${activeAgent.role_name}`)
  if (activeAgent.department_name) parts.push(`Департамент: ${activeAgent.department_name}`)
  if (activeAgent.system_prompt) parts.push(activeAgent.system_prompt)
  if (activeAgent.tone) parts.push(`Тон общения: ${activeAgent.tone}`)
  if (activeAgent.style) parts.push(`Стиль ответов: ${activeAgent.style}`)
  if (activeAgent.traits && activeAgent.traits.length > 0) parts.push(`Характеристики: ${activeAgent.traits.join(', ')}`)
  return Promise.resolve(parts.length > 0 ? parts.join('\n\n') : undefined)
}

export function useChatSubmit(params: UseChatSubmitParams): UseChatSubmitReturn {
  const {
    input, attachments, isTyping, activeAgent,
    textareaRef, messagesRef, isStreamingRef,
    setInput, setAttachments, setMessages, setIsTyping, setCompactionNotice,
    wsSend, wsOn,
  } = params

  const handleSubmit = useCallback(async (e: FormEvent) => {
    e.preventDefault()
    if (!input.trim() && attachments.length === 0) return

    // If stuck after server restart, clear stale state before re-sending.
    // The caller owns clearStuckState — we just expose a hook for it via
    // a small ref. Here we just check isTyping defensively.
    void isTyping

    const userImages = attachments.map(a => a.dataUrl)
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim() || (attachments.length > 0 ? `[Изображение${attachments.length > 1 ? ` (${attachments.length})` : ''}]` : ''),
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
    const inThinkingRef = { value: false }

    const isHermesAgent = !!(activeAgent?.is_external && activeAgent?.type === 'hermes')
    const systemPrompt = await buildSystemPrompt(activeAgent ?? null, isHermesAgent)
    const agentName = activeAgent?.name

    // ── Hermes agents: keep SSE (separate endpoint) ──────────────
    if (isHermesAgent) {
      try {
        const history = (messagesRef.current ?? []).map(m => ({ role: m.role, content: m.content }))
        const response = await fetch(`${API_BASE}/api/chat/hermes/stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: userInput,
            model: activeAgent?.model || 'general-agent',
            provider: activeAgent?.provider,
            history,
            system_prompt: systemPrompt,
            agent_name: agentName,
            agent_slug: activeAgent?.slug,
            channel_id: 'web',
            temperature: activeAgent?.temperature || 0.7,
            max_tokens: activeAgent?.max_tokens,
          }),
        })
        if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        const reader = response.body?.getReader()
        if (!reader) throw new Error('No response body')
        const decoder = new TextDecoder()
        let buffer = ''
        // eslint-disable-next-line no-constant-condition
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''
          let streamDone = false
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            let parsed: Record<string, unknown>
            try { parsed = JSON.parse(line.slice(6)) } catch { continue }
            if (parsed.type === 'chunk' && typeof parsed.content === 'string') {
              const { thinking: t, content: c } = processChunk(parsed.content, inThinkingRef)
              if (t) fullThinking += t
              if (c) fullContent += c
              setMessages(prev => (prev ?? []).map(m => m.id === assistantId ? { ...m, content: fullContent, thinking: fullThinking || undefined } : m))
            } else if (parsed.type === 'tool_start') {
              const toolName = String(parsed.tool || '')
              if (HIDDEN_TOOLS.has(toolName)) { toolIndex++; continue }
              const tc: ToolCall = { id: `${assistantId}-tool-${toolIndex++}`, name: toolName, params: (parsed.params as Record<string, unknown>) || {}, status: 'running' }
              activeTools.push(tc)
              setMessages(prev => (prev ?? []).map(m => m.id === assistantId ? { ...m, tools: [...(m.tools || []), tc] } : m))
            } else if (parsed.type === 'tool_end') {
              const toolName = String(parsed.tool || '')
              if (HIDDEN_TOOLS.has(toolName)) continue
              const idx = activeTools.findIndex(t => t.name === toolName && t.status === 'running')
              if (idx !== -1 && activeTools[idx]) {
                activeTools[idx].status = parsed.success ? 'completed' : 'error'
                activeTools[idx].result = String(parsed.result || '')
              }
              setMessages(prev => (prev ?? []).map(m => m.id === assistantId ? { ...m, tools: [...activeTools] } : m))
            } else if (parsed.type === 'done') {
              const usage = parsed.usage as Record<string, number> | undefined
              setMessages(prev => (prev ?? []).map(m => m.id === assistantId ? { ...m, model: parsed.model as string, agent_name: parsed.agent_name as string, prompt_tokens: usage?.prompt_tokens, completion_tokens: usage?.completion_tokens } : m))
              streamDone = true; break
            } else if (parsed.type === 'error') { throw new Error(String(parsed.message || 'Stream error')) }
          }
          if (streamDone) break
        }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Unknown error'
        setMessages(prev => (prev ?? []).map(m => m.id === assistantId ? { ...m, content: m.content || `⚠️ Ошибка: ${errorMsg}` } : m))
      } finally {
        setIsTyping(false)
      }
      return
    }

    // ── SynPin agents: WebSocket ─────────────────────────────────
    const cleanupFns: (() => void)[] = []
    let gotChunk = false

    const onChunk = wsOn('chat:chunk', (msg: any) => {
      if (msg.agent_slug !== activeAgent?.slug) return
      gotChunk = true
      const { thinking: t, content: c } = processChunk(msg.content, inThinkingRef)
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
      setMessages(prev => (prev ?? []).map(m => m.id === assistantId ? { ...m, tools: [...(m.tools || []), tc] } : m))
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
      setMessages(prev => (prev ?? []).map(m => m.id === assistantId ? { ...m, content: m.content || `⚠️ Ошибка: ${msg.message || 'Stream error'}` } : m))
    })

    const cleanup = () => {
      cleanupFns.forEach(fn => fn())
      setIsTyping(false)
    }

    cleanupFns.push(onChunk, onToolStart, onToolEnd, onDone, onError)

    wsSend('chat:send', {
      agent_slug: activeAgent?.slug || '',
      message: userInput,
      system_prompt: systemPrompt,
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