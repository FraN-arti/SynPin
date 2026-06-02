import { useState, useRef, useEffect, useCallback } from 'react'
import './index.css'
import synpinLogo from './images/synpin.png'
import { MarkdownRenderer } from './components/MarkdownRenderer'
import { EmojiPicker } from './components/EmojiPicker'
import { SettingsPage } from './components/SettingsPage'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:2088'
const DEFAULT_MODEL = 'general-agent'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  model?: string
  usage?: { prompt_tokens: number; completion_tokens: number; total_tokens: number }
}

function App() {
  const [page, setPage] = useState<'chat' | 'settings'>('chat')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    const saved = localStorage.getItem('synpin-sidebar')
    return saved === 'open'
  })
  const [sidebarReady, setSidebarReady] = useState(false)
  const [logoVisible, setLogoVisible] = useState(false)
  const [revealedMeta, setRevealedMeta] = useState<Set<string>>(new Set())
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Save sidebar state
  useEffect(() => {
    localStorage.setItem('synpin-sidebar', sidebarOpen ? 'open' : 'closed')
  }, [sidebarOpen])

  // Reveal metadata 0.5s after streaming completes
  useEffect(() => {
    if (!isTyping && messages.length > 0) {
      const lastMsg = messages[messages.length - 1]
      if (lastMsg?.role === 'assistant') {
        const timer = setTimeout(() => {
          setRevealedMeta(prev => {
            const next = new Set(prev)
            next.add(lastMsg.id)
            return next
          })
        }, 500)
        return () => clearTimeout(timer)
      }
    }
  }, [isTyping, messages])

  // Initial load: logo always, sidebar animation if was open
  useEffect(() => {
    const logoTimer = setTimeout(() => setLogoVisible(true), 1000)
    if (sidebarOpen) {
      const sidebarTimer = setTimeout(() => setSidebarReady(true), 1400)
      return () => { clearTimeout(logoTimer); clearTimeout(sidebarTimer) }
    } else {
      // If closed, still show logo and mark ready
      setSidebarReady(true)
      return () => clearTimeout(logoTimer)
    }
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 150) + 'px'
  }

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isTyping) return

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    }

    setMessages(prev => [...prev, userMsg])
    const userInput = input
    setInput('')

    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }

    setIsTyping(true)

    // Create assistant message placeholder
    const assistantId = (Date.now() + 1).toString()
    setMessages(prev => [...prev, {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    }])

    try {
      // Build history including the new user message
      const history = [...messages.map(m => ({ role: m.role, content: m.content })), { role: 'user' as const, content: userInput }]

      const response = await fetch(`${API_BASE}/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userInput,
          model: 'general-agent',
          history,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let buffer = ''
      let fullContent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Parse SSE lines
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // keep incomplete line in buffer

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue

          const data = line.slice(6)
          let parsed: Record<string, unknown>
          try {
            parsed = JSON.parse(data)
          } catch {
            continue
          }

          if (parsed.type === 'chunk' && typeof parsed.content === 'string') {
            fullContent += parsed.content
            setMessages(prev =>
              prev.map(m => m.id === assistantId ? { ...m, content: fullContent } : m)
            )
          } else if (parsed.type === 'done') {
            const usage = parsed.usage as { prompt_tokens: number; completion_tokens: number; total_tokens: number } | undefined
            const model = parsed.model as string | undefined
            setMessages(prev =>
              prev.map(m => m.id === assistantId
                ? { ...m, model: model || DEFAULT_MODEL, usage: usage || undefined }
                : m
              )
            )
            break
          } else if (parsed.type === 'error') {
            throw new Error(String(parsed.message || 'Stream error'))
          }
        }
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Unknown error'
      setMessages(prev =>
        prev.map(m => m.id === assistantId
          ? { ...m, content: m.content || `⚠️ Ошибка: ${errorMsg}` }
          : m
        )
      )
    } finally {
      setIsTyping(false)
    }
  }, [input, isTyping, messages])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  }

  const renderMeta = (msg: Message) => {
    if (msg.role === 'user') {
      return <span className="message-time">{formatTime(msg.timestamp)}</span>
    }
    // Assistant: time — [tokens] · [model] · [in/out]
    return (
      <>
        <span className="message-time">{formatTime(msg.timestamp)}</span>
        <span className="meta-sep"> — </span>
        {msg.usage && (
          <>
            <span className="meta-badge gold">{msg.usage.total_tokens} tok</span>
            <span className="meta-dot"> · </span>
          </>
        )}
        {msg.model && (
          <>
            <span className="meta-badge">{msg.model}</span>
            <span className="meta-dot"> · </span>
          </>
        )}
        {msg.usage && (
          <span className="meta-badge gold">IN: {msg.usage.prompt_tokens} · OUT: {msg.usage.completion_tokens}</span>
        )}
      </>
    )
  }

  const handleEmojiSelect = (emoji: string) => {
    const el = textareaRef.current
    if (!el) return
    const start = el.selectionStart
    const end = el.selectionEnd
    const newValue = input.slice(0, start) + emoji + input.slice(end)
    setInput(newValue)
    // Restore cursor position after emoji
    requestAnimationFrame(() => {
      el.focus()
      el.selectionStart = el.selectionEnd = start + emoji.length
    })
  }

  const renderInput = () => (
    <form onSubmit={handleSubmit} className="input-container">
      <div className="input-form">
        <EmojiPicker onSelect={handleEmojiSelect} />
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Спроси что-нибудь..."
          className="input-field"
          rows={1}
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
      {/* Fixed Logo — always visible, never moves */}
      <div
        className={`app-logo ${logoVisible ? 'visible' : ''}`}
        onClick={() => setSidebarOpen(!sidebarOpen)}
      >
        <img src={synpinLogo} alt="SynPin" />
      </div>

      {/* Sidebar — slides in/out */}
      <aside className={`sidebar ${sidebarOpen && sidebarReady ? 'open' : ''}`}>
        <div className="sidebar-content">
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
            <button className="settings-btn" onClick={() => setPage('settings')}>
              <span>⚙️</span> Настройки
            </button>
          </div>
        </div>
      </aside>

      {/* Main Area */}
      <main className="main-area">
        {page === 'settings' ? (
          <SettingsPage onBack={() => setPage('chat')} />
        ) : messages.length === 0 ? (
          <div className="empty-state">
            <img src={synpinLogo} alt="SynPin" className="empty-logo-img" />
            <h1 className="empty-title">Чем могу помочь?</h1>
            {renderInput()}
          </div>
        ) : (
          <>
            <div className="messages-area">
              <div className="messages-container">
                {messages.map((msg) => {
                  const isLastAssistant = msg.role === 'assistant' && msg.id === messages[messages.length - 1]?.id && isTyping
                  return (
                    <div key={msg.id} className={`message-row ${msg.role}`}>
                      <div className={`message-avatar ${msg.role} ${isLastAssistant ? 'streaming' : ''}`}>
                        {msg.role === 'assistant' ? (
                          <img src={synpinLogo} alt="S" className="avatar-logo" />
                        ) : 'U'}
                      </div>
                      <div className={`message-wrapper ${isLastAssistant ? 'streaming' : ''}`}>
                        <div className="message-bubble">
                          <MarkdownRenderer content={msg.content} isStreaming={isLastAssistant} />
                        </div>
                      </div>
                      <div className={`message-footer ${msg.role} ${msg.role === 'user' || revealedMeta.has(msg.id) ? 'visible' : ''}`}>
                        {msg.role === 'user' || revealedMeta.has(msg.id) ? renderMeta(msg) : null}
                      </div>
                    </div>
                  )
                })}
                <div ref={messagesEndRef} />
              </div>
            </div>

            <div className="bottom-input">
              {renderInput()}
            </div>
          </>
        )}
      </main>
    </div>
  )
}

export default App
