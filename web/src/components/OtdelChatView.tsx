import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { EmojiPicker } from './EmojiPicker'
import { MarkdownRenderer } from './MarkdownRenderer'

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
  onBack: () => void
  onOpenSettings: () => void
  wsSend: WsSend
  wsOn: WsOn
  wsConnected: boolean
}

export function OtdelChatView({ otdel, onBack, onOpenSettings, wsSend, wsOn }: OtdelChatViewProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [agents, setAgents] = useState<Agent[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [sending, setSending] = useState(false)
  const [thinkingAgents, setThinkingAgents] = useState<Map<string, string>>(new Map()) // slug → name
  const [compacting, setCompacting] = useState<{ before: number; after: number } | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

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
        setMessages(data.messages || [])
      }
    } catch {}
  }, [otdel.otdelid])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

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
        setMessages(prev => {
          const idx = prev.findIndex(m => m.id === message_id)
          if (idx >= 0) {
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
            }
            return updated
          }
          return prev
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

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim()) return
    const text = input.trim()
    setInput('')
    setSending(true)

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

  const getAgentName = (slug: string) => agents.find(a => a.slug === slug)?.name || slug

  const isLeftSide = (msg: ChatMessage) => {
    return msg.role === 'user' || msg.sender === 'user' || msg.is_head === true
  }

  return (
    <div className="otdel-chat-view">
      {/* Header */}
      <div className="otdel-chat-header">
        <button className="otdel-back-btn" onClick={onBack} title="Назад">
          ←
        </button>
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
              const left = isLeftSide(msg)
              const senderName = msg.sender === 'user' ? 'Вы' : (msg.sender_name || getAgentName(msg.sender))
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
                    <div className={`otdel-msg-name ${left ? 'left' : 'right'} ${isHead ? 'head' : ''}`}>
                      {senderName}
                    </div>
                    <div
                      className={`otdel-msg-bubble ${left ? 'left' : 'right'} ${isHead ? 'head' : ''}`}
                      style={workerColor ? {
                        borderColor: workerColor,
                        background: workerColor + '12',
                      } : undefined}
                    >
                      <MarkdownRenderer content={msg.content} isStreaming={isStreaming} />
                    </div>
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
            {thinkingAgents.size > 0 && Array.from(thinkingAgents.entries()).map(([slug, name]) => (
              <div key={`typing-${slug}`} className="otdel-msg-row left">
                <div className="otdel-msg-avatar left">🏢</div>
                <div className="otdel-msg-body">
                  <div className="otdel-msg-name left">{name}</div>
                  <div className="otdel-msg-bubble left typing-indicator">
                    <div className="typing-dots">
                      <span></span><span></span><span></span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
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
            placeholder={sending ? 'Агенты работают... (Enter — отправить ещё)' : 'Спроси что-нибудь...'}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <button className="send-btn" onClick={handleSend} disabled={!input.trim()}>
            →
          </button>
        </div>
      </div>
    </div>
  )
}
