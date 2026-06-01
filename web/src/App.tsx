import { useState, useRef, useEffect } from 'react'
import './index.css'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isTyping) return

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMsg])
    setInput('')
    setIsTyping(true)

    setTimeout(() => {
      const assistantMsg: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Это шаблон ответа. Здесь будет ответ от SynPin агента.',
        timestamp: new Date(),
      }
      setMessages(prev => [...prev, assistantMsg])
      setIsTyping(false)
    }, 1500)
  }

  const InputField = ({ bottom = false }: { bottom?: boolean }) => (
    <form onSubmit={handleSubmit} className={`input-container ${bottom ? '' : ''}`}>
      <div className="input-form">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Спроси что-нибудь..."
          className="input-field"
        />
        <button
          type="submit"
          disabled={!input.trim() || isTyping}
          className="input-submit"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </form>
  )

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? '' : 'collapsed'}`}>
        <div className="sidebar-header">
          <div className="logo">S</div>
          <span className="sidebar-title">SynPin</span>
        </div>

        <button className="new-chat-btn">
          <span className="new-chat-icon">+</span>
          Новый чат
        </button>

        <nav className="sidebar-nav">
          <div className="nav-section-title">Сегодня</div>
          <button className="nav-item">Архитектура API</button>
          <button className="nav-item">Тесты для auth</button>
        </nav>

        <div className="sidebar-footer">
          <button className="settings-btn">
            <span>⚙️</span> Настройки
          </button>
        </div>
      </aside>

      {/* Main Area */}
      <main className="main-area">
        {/* Sidebar Toggle */}
        <button className="sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 12h18M3 6h18M3 18h18" />
          </svg>
        </button>

        {messages.length === 0 ? (
          // Empty State
          <div className="empty-state">
            <div className="empty-logo">S</div>
            <h1 className="empty-title">Чем могу помочь?</h1>
            <p className="empty-version">v0.1.1 — update test</p>
            <InputField />
          </div>
        ) : (
          // Messages
          <>
            <div className="messages-area">
              <div className="messages-container">
                {messages.map((msg) => (
                  <div key={msg.id} className={`message ${msg.role}`}>
                    <div className="message-avatar">
                      {msg.role === 'assistant' ? 'S' : 'U'}
                    </div>
                    <div className="message-content">
                      <p>{msg.content}</p>
                    </div>
                  </div>
                ))}
                {isTyping && (
                  <div className="typing-indicator">
                    <div className="message-avatar" style={{ background: 'var(--orange)', color: 'white' }}>S</div>
                    <div className="typing-dots">
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Bottom Input */}
            <div className="bottom-input">
              <InputField bottom />
              <p className="disclaimer">
                SynPin может ошибаться. Проверяй важную информацию.
              </p>
            </div>
          </>
        )}
      </main>
    </div>
  )
}

export default App
