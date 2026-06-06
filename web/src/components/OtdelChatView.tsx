import { useState, useRef, useEffect } from 'react'
import { EmojiPicker } from './EmojiPicker'

interface OtdelData {
  otdelid: string
  name: string
  description: string
  color: string
  mentor_role: string
  escalation: string
  agent_count: number
}

interface OtdelChatViewProps {
  otdel: OtdelData
  onBack: () => void
  onOpenSettings: () => void
}

export function OtdelChatView({ otdel, onBack, onOpenSettings }: OtdelChatViewProps) {
  const [messages, setMessages] = useState<{ role: 'user' | 'assistant'; content: string; id: string }[]>([])
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim()) return
    const userMsg = { role: 'user' as const, content: input.trim(), id: `u-${Date.now()}` }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    // Reset textarea height
    const textarea = document.querySelector('.otdel-bottom-input .chat-textarea') as HTMLTextAreaElement
    if (textarea) textarea.style.height = 'auto'

    // TODO: connect to department's agent
    // For now, echo back
    setTimeout(() => {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `[${otdel.name}] Чат отдела в разработке. Скоро здесь будет ментор и работники.`,
        id: `a-${Date.now()}`,
      }])
    }, 500)
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
              {otdel.mentor_role ? `Ментор: ${otdel.mentor_role}` : 'Ментор не назначен'}
              {otdel.agent_count > 0 ? ` · ${otdel.agent_count} агентов` : ''}
            </p>
          </div>
        ) : (
          <div className="otdel-messages-container">
            {messages.map(msg => (
              <div key={msg.id} className={`message-row ${msg.role}`}>
                <div className={`message-avatar ${msg.role}`}>
                  {msg.role === 'assistant' ? '🏢' : 'U'}
                </div>
                <div className="message-wrapper">
                  <div className="message-bubble">
                    <span>{msg.content}</span>
                  </div>
                </div>
              </div>
            ))}
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
            placeholder="Спроси что-нибудь..."
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
