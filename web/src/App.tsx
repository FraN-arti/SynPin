import { useState, useRef, useEffect, useCallback } from 'react'
import './index.css'
import synpinLogo from './images/synpin.png'
import { MarkdownRenderer } from './components/MarkdownRenderer'
import { EmojiPicker } from './components/EmojiPicker'
import { SettingsPage } from './components/SettingsPage'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:2088'

interface AgentConfig {
  slug: string
  agentid: string
  name: string
  role: string
  role_name: string
  department: string
  department_name: string
  model: string
  provider: string | null
  system_prompt: string
  description: string
  tone: string
  style: string
  traits: string[]
  tools: string[]
  temperature: number
  max_tokens: number
  enabled: boolean
  is_external?: boolean
  type?: string
}

interface ToolCall {
  id: string
  name: string
  params: Record<string, unknown>
  status: 'running' | 'completed' | 'error'
  result?: string
  error?: string
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  model?: string
  agent_name?: string
  tools?: ToolCall[]
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
  const [activeAgent, setActiveAgent] = useState<AgentConfig | null>(null)
  const [availableAgents, setAvailableAgents] = useState<AgentConfig[]>([])
  const [agentSelectorOpen, setAgentSelectorOpen] = useState(false)
  const [pendingNewSession, setPendingNewSession] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const activeAgentRef = useRef<AgentConfig | null>(null)

  // Keep ref in sync with state
  activeAgentRef.current = activeAgent

  // Tool display names for badges
  const TOOL_DISPLAY_NAMES: Record<string, string> = {
    terminal: 'Терминал',
    file_read: 'Чтение файла',
    file_write: 'Запись файла',
    search_files: 'Поиск файлов',
    web_search: 'Поиск в интернете',
    code_exec: 'Python',
  }

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

  // Load available agents (both SynPin and external)
  useEffect(() => {
    const loadAgents = async () => {
      try {
        // Load SynPin agents
        const agentsRes = await fetch(`${API_BASE}/api/agents`)
        const agentsData = await agentsRes.json()
        const synpinAgents = (agentsData.agents || []).map((a: AgentConfig) => ({ ...a, is_external: false }))

        // Load external agents
        const extRes = await fetch(`${API_BASE}/api/external-agents`)
        const extData = await extRes.json()
        const extAgents = (extData.agents || []).filter((a: AgentConfig) => a.enabled)

        const allAgents = [...synpinAgents, ...extAgents]
        setAvailableAgents(allAgents)

        // Set default active agent (first enabled one)
        if (allAgents.length > 0 && !activeAgent) {
          setActiveAgent(allAgents[0])
        }
      } catch (e) {
        console.error('[agents] load error:', e)
      }
    }
    loadAgents()
  }, [])

  // Load chat history when active agent changes
  useEffect(() => {
    if (!activeAgent) return
    const loadHistory = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/chat/history?agent_slug=${activeAgent.slug}&channel_id=web`)
        if (!res.ok) return
        const data = await res.json()
        const msgs = data.messages || []
        if (msgs.length > 0) {
          const restored: Message[] = msgs.map((m: { role: string; content: string }, i: number) => ({
            id: `restored-${i}`,
            role: m.role as 'user' | 'assistant',
            content: m.content,
            timestamp: new Date(),
          }))
          setMessages(restored)
        } else {
          setMessages([])
        }
      } catch (e) {
        console.error('[history] load error:', e)
      }
    }
    loadHistory()
  }, [activeAgent])

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

    // Create assistant message placeholder with tools array
    const assistantId = (Date.now() + 1).toString()
    setMessages(prev => [...prev, {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      tools: [],
    }])

    const activeTools: ToolCall[] = []
    let toolIndex = 0

    try {
      // Build history: just existing messages (userMsg not included yet — it's in req.message)
      const history = messages.map(m => ({ role: m.role, content: m.content }))

      // Build merged system prompt from agent config
      let systemPrompt: string | undefined
      let agentName: string | undefined
      let model = 'general-agent'
      let temperature = 0.7
      let maxTokens: number | undefined
      let chatEndpoint = `${API_BASE}/api/chat/stream`
      let enabledTools: string[] = []

      if (activeAgent) {
        agentName = activeAgent.name
        temperature = activeAgent.temperature || 0.7
        maxTokens = activeAgent.max_tokens
        enabledTools = activeAgent.tools || []

        // Route to Hermes endpoint if external agent
        if (activeAgent.is_external && activeAgent.type === 'hermes') {
          chatEndpoint = `${API_BASE}/api/chat/hermes/stream`
          // Build SynPin context for external agent
          const ctx: string[] = [
            `Ты работаешь внутри платформы SynPin — системы управления агентами (agent-driven organization).`,
            `Ты подключён как внешний агент (external agent) в организации SynPin.`,
          ]
          if (activeAgent.name) ctx.push(`Твоё имя в SynPin: ${activeAgent.name}`)
          if (activeAgent.role_name) ctx.push(`Твоя роль: ${activeAgent.role_name}`)
          if (activeAgent.department_name) ctx.push(`Твой департамент: ${activeAgent.department_name}`)
          if (activeAgent.system_prompt) ctx.push(activeAgent.system_prompt)
          ctx.push(`Если тебя спрашивают где ты или что ты — ты внутри SynPin и можешь помогать с задачами организации.`)
          systemPrompt = ctx.join('\n')
        } else {
          // SynPin agent — build system prompt
          model = activeAgent.model
          const parts: string[] = []
          if (activeAgent.name) parts.push(`Имя: ${activeAgent.name}`)
          if (activeAgent.description) parts.push(activeAgent.description)
          if (activeAgent.role_name) parts.push(`Роль: ${activeAgent.role_name}`)
          if (activeAgent.department_name) parts.push(`Департамент: ${activeAgent.department_name}`)
          if (activeAgent.system_prompt) parts.push(activeAgent.system_prompt)
          if (activeAgent.tone) parts.push(`Тон общения: ${activeAgent.tone}`)
          if (activeAgent.style) parts.push(`Стиль ответов: ${activeAgent.style}`)
          if (activeAgent.traits && activeAgent.traits.length > 0) parts.push(`Характеристики: ${activeAgent.traits.join(', ')}`)
          if (parts.length > 0) systemPrompt = parts.join('\n\n')
        }
      }

      const response = await fetch(chatEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userInput,
          model,
          provider: activeAgent?.provider || undefined,
          history,
          system_prompt: systemPrompt,
          agent_name: agentName,
          agent_slug: activeAgent?.slug || undefined,
          channel_id: 'web',
          new_session: pendingNewSession,
          temperature,
          max_tokens: maxTokens,
          tools: enabledTools,
        }),
      })

      // Reset pending flag after first request
      if (pendingNewSession) {
        setPendingNewSession(false)
      }

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
          } else if (parsed.type === 'tool_start') {
            const toolName = String(parsed.tool || '')
            const ti = toolIndex++
            const tc: ToolCall = {
              id: `${assistantId}-tool-${ti}`,
              name: toolName,
              params: (parsed.params as Record<string, unknown>) || {},
              status: 'running',
            }
            activeTools.push(tc)
            setMessages(prev =>
              prev.map(m => m.id === assistantId
                ? { ...m, tools: [...(m.tools || []), tc] }
                : m
              )
            )
          } else if (parsed.type === 'tool_end') {
            const toolName = String(parsed.tool || '')
            const idx = activeTools.findIndex(t => t.name === toolName && t.status === 'running')
            if (idx !== -1) {
              const tc = activeTools[idx]
              if (tc) {
                tc.status = parsed.success ? 'completed' : 'error'
                tc.result = String(parsed.result || '')
                tc.error = parsed.error ? String(parsed.error) : undefined
                setMessages(prev =>
                  prev.map(m => m.id === assistantId
                    ? { ...m, tools: [...activeTools] }
                    : m
                  )
                )
              }
            }
          } else if (parsed.type === 'done') {
            const model = parsed.model as string | undefined
            const agentName = parsed.agent_name as string | undefined
            setMessages(prev =>
              prev.map(m => m.id === assistantId
                ? { ...m, model: model || 'assistant', agent_name: agentName }
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
  }, [input, isTyping, messages, activeAgent])

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
    // Assistant: time — agent_name · model
    return (
      <>
        <span className="message-time">{formatTime(msg.timestamp)}</span>
        <span className="meta-sep"> — </span>
        {msg.agent_name && (
          <>
            <span className="meta-badge gold">{msg.agent_name}</span>
            <span className="meta-dot"> · </span>
          </>
        )}
        {msg.model && msg.model !== msg.agent_name && (
          <span className="meta-badge">{msg.model}</span>
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

  // Refresh agents list (called after tool/agent changes in Settings)
  const refreshAgents = useCallback(async () => {
    try {
      const agentsRes = await fetch(`${API_BASE}/api/agents`)
      const agentsData = await agentsRes.json()
      const synpinAgents = (agentsData.agents || []).map((a: AgentConfig) => ({ ...a, is_external: false }))
      const extRes = await fetch(`${API_BASE}/api/external-agents`)
      const extData = await extRes.json()
      const extAgents = (extData.agents || []).filter((a: AgentConfig) => a.enabled)
      const allAgents = [...synpinAgents, ...extAgents]
      setAvailableAgents(allAgents)
      const current = activeAgentRef.current
      if (current) {
        const fresh = allAgents.find(a => a.slug === current.slug)
        if (fresh) setActiveAgent(fresh)
      }
    } catch (e) {
      console.error('[agents] refresh error:', e)
    }
  }, [])

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
          <button className="new-chat-btn" onClick={() => {
            setMessages([])
            setPendingNewSession(true)
          }}>
            <span className="new-chat-icon">+</span>
            Новый чат
          </button>

          {/* Agent Selector */}
          <div className="agent-selector">
            <button
              className="agent-selector-trigger"
              onClick={() => setAgentSelectorOpen(!agentSelectorOpen)}
            >
              <span className="agent-selector-avatar" style={{ background: activeAgent?.is_external ? '#f97316' : '#6b7280' }}>
                {activeAgent?.is_external ? 'H' : activeAgent?.name?.[0] || '?'}
              </span>
              <div className="agent-selector-info">
                <span className="agent-selector-name">{activeAgent?.name || 'Выберите агента'}</span>
                <span className="agent-selector-role">{activeAgent?.role_name || activeAgent?.type || ''}</span>
              </div>
              <svg className={`agent-selector-arrow ${agentSelectorOpen ? 'open' : ''}`} width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M6 9l6 6 6-6" />
              </svg>
            </button>

            {agentSelectorOpen && (
              <div className="agent-selector-dropdown">
                {availableAgents.map(agent => (
                  <button
                    key={agent.slug}
                    className={`agent-selector-item ${activeAgent?.slug === agent.slug ? 'active' : ''}`}
                    onClick={() => {
                      setActiveAgent(agent)
                      setAgentSelectorOpen(false)
                      setMessages([])
                    }}
                  >
                    <span className="agent-selector-item-avatar" style={{ background: agent.is_external ? '#f97316' : '#6b7280' }}>
                      {agent.is_external ? 'H' : agent.name[0]}
                    </span>
                    <div className="agent-selector-item-info">
                      <span className="agent-selector-item-name">
                        {agent.name}
                        {agent.is_external && <span className="agent-badge extern">extern</span>}
                      </span>
                      <span className="agent-selector-item-role">{agent.role_name || agent.type}</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

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
          <SettingsPage onBack={() => setPage('chat')} onAgentsChange={refreshAgents} />
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
                      {/* Tool blocks between avatar and bubble */}
                      {msg.tools && msg.tools.length > 0 && (
                        <div className="message-tools">
                          {msg.tools.map(tc => (
                            <div key={tc.id}
                              className={`tool-block ${tc.status === 'running' ? 'running' : tc.status === 'error' ? 'error' : 'done'}`}
                              title={tc.status === 'running' ? `Выполняется: ${tc.name}` : tc.status === 'error' ? `Ошибка: ${tc.error}` : `Готово: ${tc.name}`}>
                              <span className="tool-block-name">{TOOL_DISPLAY_NAMES[tc.name] || tc.name}</span>
                              <span className={`tool-block-status ${tc.status}`}>
                                {tc.status === 'running' ? '⟳' : tc.status === 'error' ? '✕' : '✓'}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
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
