import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { EmojiPicker } from './EmojiPicker'
import { MarkdownRenderer } from './MarkdownRenderer'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:2088'

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

    const unsubDone = wsOn('otdel:done', (msg) => {
      if (msg.otdel_id !== otdel.otdelid) return
      setSending(false)
    })

    return () => {
      unsubMessage()
      unsubDone()
    }
  }, [wsOn, otdel.otdelid])

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || sending) return
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
                    {isStreaming && (
                      <div className="otdel-msg-streaming-dots">
                        <span></span><span></span><span></span>
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
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
            placeholder={sending ? 'Агенты работают...' : 'Спроси что-нибудь...'}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={sending}
          />
          <button className="send-btn" onClick={handleSend} disabled={!input.trim() || sending}>
            {sending ? '...' : '→'}
          </button>
        </div>
      </div>
    </div>
  )
}
