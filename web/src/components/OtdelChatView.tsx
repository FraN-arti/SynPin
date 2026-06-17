import { useState, useEffect, useCallback, useMemo } from 'react'
import { EmojiPicker } from './EmojiPicker'
import { MarkdownRenderer } from './MarkdownRenderer'
import { useChatScroll } from '../hooks/useChatScroll'

import { API_BASE } from '../config'

interface OtdelData {
  otdelid: string
  name: string
  description: string
  color: string
  mentor_role: string
  escalation: string
  agent_count: number
  head: string
  workers: string[]
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  sender: string
  sender_name?: string
  content: string
  is_head?: boolean
  timestamp: string
  streaming?: boolean
  tools?: ToolCall[]
  compaction?: boolean
  model?: string
  provider?: string
  prompt_tokens?: number
  completion_tokens?: number
}

interface ToolCall {
  id: string
  name: string
  params: Record<string, unknown>
  status: 'running' | 'completed' | 'error'
  result?: string
  error?: string
}

interface Agent {
  slug: string
  name: string
  department?: string
}

interface Department {
  departmentsid: string
  name: string
  color: string
}

type WsSend = (type: string, payload?: Record<string, any>) => boolean
type WsOn = (type: string, handler: (data: any) => void) => () => void

interface OtdelChatViewProps {
  otdel: OtdelData
  onOpenSettings: () => void
  wsSend: WsSend
  wsOn: WsOn
  wsConnected: boolean
}

export function OtdelChatView({ otdel, onOpenSettings, wsSend, wsOn }: OtdelChatViewProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [agents, setAgents] = useState<Agent[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [sending, setSending] = useState(false)
  const [thinkingAgents, setThinkingAgents] = useState<Map<string, string>>(new Map()) // slug → name
  const [compacting, setCompacting] = useState<{ before: number; after: number } | null>(null)
  const [workerStatuses, setWorkerStatuses] = useState<Map<string, 'idle' | 'thinking' | 'done'>>(new Map())
  const [delegations, setDelegations] = useState<Array<{id: string; worker: string; workerName: string; task: string; status: 'pending' | 'done'}>>([])
  const { sentinelRef: messagesEndRef } = useChatScroll(messages)

  // Load agents and departments for color mapping
  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/api/agents`).then(r => r.json()),
      fetch(`${API_BASE}/api/departments`).then(r => r.json()),
    ]).then(([agentsData, deptsData]) => {
      setAgents((agentsData.agents || []).filter((a: Agent & { enabled: boolean }) => a.enabled))
      setDepartments(deptsData.departments || [])
    }).catch(() => {})
  }, [])

  // Map: agent slug → department color
  const agentColorMap = useMemo(() => {
    const map = new Map<string, string>()
    const deptMap = new Map<string, string>()
    for (const d of departments) {
      deptMap.set(d.departmentsid, d.color)
    }
    for (const a of agents) {
      if (a.department && deptMap.has(a.department)) {
        map.set(a.slug, deptMap.get(a.department)!)
      }
    }
    return map
  }, [agents, departments])

  // Load chat history
  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/otdels/${otdel.otdelid}/chat/history`)
      if (res.ok) {
        const data = await res.json()
        const msgs = data.messages || []
        setMessages(msgs)
        // Rebuild worker statuses from chat history (survives F5 refresh)
        const respondedSlugs = new Set<string>()
        for (const m of msgs) {
          if (m.role === 'assistant' && m.sender && m.sender !== 'user') {
            respondedSlugs.add(m.sender)
          }
        }
        const restoredStatuses = new Map<string, 'idle' | 'thinking' | 'done'>()
        for (const slug of respondedSlugs) {
          restoredStatuses.set(slug, 'done')
        }
        setWorkerStatuses(restoredStatuses)
      }
    } catch {}
  }, [otdel.otdelid])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  // Periodic history refresh — catch missed WS messages
  useEffect(() => {
    const interval = setInterval(() => {
      if (!sending) return // Only refresh when idle
      loadHistory()
    }, 5000) // Check every 5 seconds when sending
    return () => clearInterval(interval)
  }, [loadHistory, sending])

  // WebSocket message handlers for this otdel
  useEffect(() => {
    const unsubMessage = wsOn('otdel:message', (msg) => {
      if (msg.otdel_id !== otdel.otdelid) return
      const chatMsg = msg.message as ChatMessage
      setMessages(prev => {
        if (prev.some(m => m.id === chatMsg.id)) return prev
        return [...prev, chatMsg]
      })
    })

    // Thinking indicator — agent started processing
    const unsubThinking = wsOn('otdel:thinking', (msg) => {
      if (msg.otdel_id !== otdel.otdelid) return
      setThinkingAgents(prev => {
        const next = new Map(prev)
        next.set(msg.agent_slug, msg.agent_name)
        return next
      })
      // Update worker status panel
      setWorkerStatuses(prev => {
        const next = new Map(prev)
        next.set(msg.agent_slug, 'thinking')
        return next
      })
    })

    // Compaction indicator — history was compacted
    const unsubCompacting = wsOn('otdel:compacting', (msg) => {
      if (msg.otdel_id !== otdel.otdelid) return
      setCompacting({ before: msg.before, after: msg.after })
      // Auto-clear after 3 seconds
      setTimeout(() => setCompacting(null), 3000)
    })

    // Streaming chunks — accumulate into a single message
    const unsubChunk = wsOn('otdel:chunk', (msg) => {
      if (msg.otdel_id !== otdel.otdelid) return
      const { message_id, content, sender, sender_name, is_head } = msg
      if (!message_id || !content) return
      // Clear thinking for this agent when first chunk arrives
      setThinkingAgents(prev => {
        if (!prev.has(sender)) return prev
        const next = new Map(prev)
        next.delete(sender)
        return next
      })
      setMessages(prev => {
        const idx = prev.findIndex(m => m.id === message_id)
        if (idx >= 0) {
          // Update existing streaming message
          const updated = [...prev]
          const oldMsg = updated[idx]!
          updated[idx] = {
            id: oldMsg.id,
            role: oldMsg.role,
            sender: oldMsg.sender,
            sender_name: oldMsg.sender_name,
            content: oldMsg.content + content,
            is_head: oldMsg.is_head,
            timestamp: oldMsg.timestamp,
            streaming: true,
          }
          return updated
        } else {
          // Create new streaming message
          const newMsg: ChatMessage = {
            id: message_id,
            role: 'assistant',
            sender: sender || 'unknown',
            sender_name,
            content,
            is_head,
            streaming: true,
            timestamp: new Date().toISOString(),
          }
          return [...prev, newMsg]
        }
      })
    })

    // Tool events — update message with tool calls
    const unsubToolStart = wsOn('otdel:tool_start', (msg) => {
      if (msg.otdel_id !== otdel.otdelid) return
      const { message_id, tool, params, index } = msg
      if (!message_id || !tool) return

      // Track delegation cards
      if (tool === 'head_delegate') {
        // Reset statuses when a NEW delegation round starts
        setWorkerStatuses(new Map())
        setDelegations([])
        // head_delegate sends workers as an ARRAY of {slug, task} objects
        const workersParam = params?.workers || []
        const taskForAll = params?.task || params?.instruction || ''
        const workersList = Array.isArray(workersParam) && workersParam.length > 0
          ? workersParam
          : [{ slug: params?.worker || params?.target || '', task: taskForAll }]
        for (const w of workersList) {
          if (!w?.slug) continue
          setDelegations(prev => [...prev, {
            id: `${message_id}-del-${w.slug}-${index ?? Date.now()}`,
            worker: w.slug,
            workerName: '', // resolved at render time
            task: typeof w.task === 'string' ? w.task : taskForAll,
            status: 'pending',
          }])
        }
      }

      setMessages(prev => {
        const idx = prev.findIndex(m => m.id === message_id)
        if (idx >= 0) {
          const updated = [...prev]
          const oldMsg = updated[idx]!
          const tc: ToolCall = {
            id: `${message_id}-tool-${index ?? Date.now()}`,
            name: tool,
            params: (params as Record<string, unknown>) || {},
            status: 'running',
          }
          updated[idx] = {
            ...oldMsg,
            tools: [...(oldMsg.tools || []), tc],
          }
          return updated
        }
        return prev
      })
    })

    const unsubToolEnd = wsOn('otdel:tool_end', (msg) => {
      if (msg.otdel_id !== otdel.otdelid) return
      const { message_id, tool, result, success, error } = msg
      if (!message_id || !tool) return
      setMessages(prev => {
        const idx = prev.findIndex(m => m.id === message_id)
        if (idx >= 0) {
          const updated = [...prev]
          const oldMsg = updated[idx]!
          const toolCalls = oldMsg.tools || []
          const toolIdx = toolCalls.findIndex(t => t.name === tool && t.status === 'running')
          if (toolIdx >= 0) {
            const newTools = [...toolCalls]
            const oldTool = newTools[toolIdx]!
            newTools[toolIdx] = {
              id: oldTool.id,
              name: oldTool.name,
              params: oldTool.params,
              status: success ? 'completed' : 'error',
              result: result ? String(result) : '',
              error: error ? String(error) : undefined,
            }
            updated[idx] = {
              ...oldMsg,
              tools: newTools,
            }
          }
          return updated
        }
        return prev
      })
    })

    // Done — finalize streaming message
    const unsubDone = wsOn('otdel:done', (msg) => {
      if (msg.otdel_id !== otdel.otdelid) return
      const { message_id, message: finalMsg } = msg
      // Clear all thinking for this otdel when done
      setThinkingAgents(new Map())
      if (message_id && finalMsg) {
        // Mark this agent as done in worker status panel
        setWorkerStatuses(prev => {
          const next = new Map(prev)
          next.set(finalMsg.sender, 'done')
          return next
        })
        // Mark delegation as done if this worker was delegated to
        if (finalMsg.is_head) {
          // Head is summarizing — mark ALL remaining pending delegations as done
          setDelegations(prev => prev.map(d => ({...d, status: 'done' as const})))
        } else {
          setDelegations(prev => prev.map(d =>
            d.worker === finalMsg.sender ? { ...d, status: 'done' as const } : d
          ))
        }
        setMessages(prev => {
          const idx = prev.findIndex(m => m.id === message_id)
          if (idx >= 0) {
            // Update existing streaming message
            const updated = [...prev]
            const oldMsg = updated[idx]!
            updated[idx] = {
              id: oldMsg.id,
              role: oldMsg.role,
              sender: oldMsg.sender,
              sender_name: oldMsg.sender_name,
              content: finalMsg.content,
              is_head: oldMsg.is_head,
              timestamp: finalMsg.timestamp,
              streaming: false,
              model: (finalMsg as any).model || oldMsg.model,
              provider: (finalMsg as any).provider || oldMsg.provider,
              prompt_tokens: (finalMsg as any).prompt_tokens || oldMsg.prompt_tokens,
              completion_tokens: (finalMsg as any).completion_tokens || oldMsg.completion_tokens,
            }
            return updated
          }
          // Message not found (no chunks received) — add it as new
          return [...prev, {
            id: message_id,
            role: 'assistant',
            sender: finalMsg.sender,
            sender_name: finalMsg.sender_name,
            content: finalMsg.content,
            is_head: finalMsg.is_head,
            timestamp: finalMsg.timestamp,
            streaming: false,
            model: (finalMsg as any).model,
            provider: (finalMsg as any).provider,
            prompt_tokens: (finalMsg as any).prompt_tokens,
            completion_tokens: (finalMsg as any).completion_tokens,
          }]
        })
      }
      setSending(false)
    })

    const unsubError = wsOn('otdel:error', (msg) => {
      if (msg.otdel_id !== otdel.otdelid) return
      setSending(false)
      // Could show error toast
    })

    return () => {
      unsubMessage()
      unsubThinking()
      unsubCompacting()
      unsubChunk()
      unsubToolStart()
      unsubToolEnd()
      unsubDone()
      unsubError()
    }
  }, [wsOn, otdel.otdelid])


  const handleSend = async () => {
    if (!input.trim()) return
    const text = input.trim()
    setInput('')
    setSending(true)
    // Reset worker statuses for new round
    setWorkerStatuses(new Map())
    setDelegations([])

    const textarea = document.querySelector('.otdel-bottom-input .chat-textarea') as HTMLTextAreaElement
    if (textarea) textarea.style.height = 'auto'

    // Send via WebSocket — backend will push the message back with its own id
    wsSend('otdel:send', {
      otdel_id: otdel.otdelid,
      message: text,
    })
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 150) + 'px'
  }

  const handleEmojiSelect = (emoji: string) => {
    setInput(prev => prev + emoji)
  }


  const isLeftSide = (msg: ChatMessage) => {
    return msg.role === 'user' || msg.sender === 'user' || msg.is_head === true
  }

  return (
    <div className="otdel-chat-view">
      {/* Header */}
      <div className="otdel-chat-header">
        <div className="otdel-header-info">
          <span className="otdel-header-dot" style={{ background: otdel.color }} />
          <div>
            <span className="otdel-header-name">{otdel.name}</span>
            {otdel.description && <span className="otdel-header-desc">{otdel.description}</span>}
          </div>
        </div>
        <button className="otdel-settings-btn" onClick={onOpenSettings} title="Настроить отдел">
          <span className="otdel-settings-icon">≡</span>
          <span>Настроить</span>
        </button>
      </div>

      {/* Worker Status Panel */}
      {(() => {
        const headSlug = otdel.head
        const workerSlugs = otdel.workers.filter(w => w !== headSlug)
        const allSlugs = [headSlug, ...workerSlugs]
        if (allSlugs.length === 0) return null

        const getWorkerInfo = (slug: string) => {
          const agent = agents.find(a => a.slug === slug)
          return { name: agent?.name || slug, slug }
        }
        return (
          <div className="otdel-worker-status-bar">
            {allSlugs.map(slug => {
              const { name } = getWorkerInfo(slug)
              const status = workerStatuses.get(slug) || 'idle'
              const isHead = slug === headSlug
              return (
                <div key={slug} className={`otdel-worker-chip ${status} ${isHead ? 'head-chip' : ''}`}>
                  <span className={`otdel-worker-dot ${status} ${isHead ? 'head-dot' : ''}`} />
                  <span className="otdel-worker-name">{isHead ? '👑 ' : ''}{name}</span>
                  {status === 'thinking' && <span className="otdel-worker-status-text">думает...</span>}
                  {status === 'done' && <span className="otdel-worker-status-text">✓</span>}
                </div>
              )
            })}
          </div>
        )
      })()}

      {/* Delegation Cards — compact one-line blocks */}
      {delegations.length > 0 && (
        <div className="otdel-delegations">
          {delegations.map(d => {
            const agent = agents.find(a => a.slug === d.worker)
            return (
              <div key={d.id} className={`otdel-delegation-chip ${d.status}`}>
                <span className={`otdel-delegation-dot ${d.status}`} />
                <span className="otdel-delegation-name">{agent?.name || d.worker}</span>
              </div>
            )
          })}
        </div>
      )}

      {/* Messages */}
      <div className="otdel-messages-area">
        {messages.length === 0 ? (
          <div className="otdel-empty-chat">
            <div className="otdel-empty-icon">🏢</div>
            <p>Чат отдела «{otdel.name}»</p>
            <p className="otdel-empty-hint">
              {otdel.description || 'Начните общение, написав сообщение'}
            </p>
          </div>
        ) : (
          <div className="otdel-messages-container">
            {messages.map(msg => {
              // Compaction marker — render as system message
              if (msg.compaction) {
                return (
                  <div key={msg.id} className="otdel-compaction-marker">
                    <span>🗜️ {msg.content}</span>
                  </div>
                )
              }
              // Skip empty messages (no content and no tools)
              const hasTools = msg.tools && msg.tools.length > 0
              const hasContent = msg.content && msg.content.trim()
              const hasValidSender = msg.sender_name && msg.sender_name !== '?'
              if (!hasContent && !hasTools) return null
              if (!hasValidSender && !hasContent) return null
              const left = isLeftSide(msg)
              const isHead = msg.is_head === true
              const isStreaming = msg.streaming === true

              const workerColor = !left && !isHead ? agentColorMap.get(msg.sender) : undefined

              return (
                <div key={msg.id} className={`otdel-msg-row ${left ? 'left' : 'right'} ${isStreaming ? 'streaming' : ''}`}>
                  <div
                    className={`otdel-msg-avatar ${left ? 'left' : 'right'}`}
                    style={workerColor ? { background: workerColor + '20' } : undefined}
                  >
                    {left ? '👤' : '🏢'}
                  </div>
                  <div className="otdel-msg-body">
                    <div
                      className={`otdel-msg-bubble ${left ? 'left' : 'right'} ${isHead ? 'head' : ''}`}
                      style={workerColor ? {
                        borderColor: workerColor,
                        background: workerColor + '12',
                      } : undefined}
                    >
                      <MarkdownRenderer content={msg.content} isStreaming={isStreaming} />
                      </div>
                      {/* Message meta info — time · agent · model */}
                      {msg.role === 'assistant' && (msg.model || msg.sender_name) && !isStreaming && (
                        <div className="otdel-msg-meta">
                          <span className="msg-meta-time">{new Date(msg.timestamp).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}</span>
                          {msg.sender_name && (
                            <>
                              <span className="meta-sep"> — </span>
                              <span className="meta-badge gold">{msg.sender_name}</span>
                            </>
                          )}
                          {msg.model && (
                            <>
                              <span className="meta-dot"> · </span>
                              <span className="meta-badge">{msg.model}</span>
                            </>
                          )}
                          {msg.prompt_tokens && (
                            <>
                              <span className="meta-dot"> · </span>
                              <span className="meta-badge dim">{msg.prompt_tokens} tok</span>
                            </>
                          )}
                        </div>
                      )}
                      {msg.tools && msg.tools.length > 0 && (
                      <div className="otdel-msg-tools">
                        {msg.tools.map(tc => (
                          <div key={tc.id} className={`otdel-tool-call ${tc.status}`}>
                            <div className="otdel-tool-header">
                              <span className="otdel-tool-icon">
                                {tc.status === 'running' ? '⏳' : tc.status === 'completed' ? '✅' : '❌'}
                              </span>
                              <span className="otdel-tool-name">{tc.name}</span>
                            </div>
                            {tc.status === 'running' && (
                              <div className="otdel-tool-params">Выполняется...</div>
                            )}
                            {tc.status === 'completed' && tc.result && (
                              <div className="otdel-tool-result">
                                <pre>{tc.result}</pre>
                              </div>
                            )}
                            {tc.status === 'error' && tc.error && (
                              <div className="otdel-tool-error">
                                <pre>{tc.error}</pre>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    {isStreaming && (
                      <div className="otdel-msg-streaming-dots">
                        <span></span><span></span><span></span>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
            {/* Typing indicator — agents thinking before first chunk */}
            {thinkingAgents.size > 0 && Array.from(thinkingAgents.entries()).map(([slug, name]) => {
              const isHeadAgent = slug === otdel.head
              const side = isHeadAgent ? 'left' : 'right'
              return (
                <div key={`typing-${slug}`} className={`otdel-msg-row ${side}`}>
                  <div className={`otdel-msg-avatar ${side}`}>{isHeadAgent ? '🏢' : '👤'}</div>
                  <div className="otdel-msg-body">
                    <div className={`otdel-msg-name ${side}`}>{name}</div>
                      <div className="otdel-typing-dots">
                        <span></span><span></span><span></span>
                      </div>
                  </div>
                </div>
              )
            })}
            {/* Compaction indicator */}
            {compacting && (
              <div className="otdel-compaction-banner">
                <span className="compaction-icon">🗜️</span>
                <span className="compaction-text">
                  Компакция: {compacting.before} → {compacting.after} сообщений
                </span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="otdel-bottom-input">
        <div className="input-bar">
          <EmojiPicker onSelect={handleEmojiSelect} />
          <textarea
            className="chat-textarea"
            placeholder={compacting ? 'Компакция истории...' : sending ? 'Агенты работают... (Enter — отправить ещё)' : 'Спроси что-нибудь...'}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <button className="send-btn" onClick={handleSend} disabled={!input.trim() || !!compacting}>
            →
          </button>
        </div>
      </div>
    </div>
  )
}
