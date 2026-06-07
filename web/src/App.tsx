import { useState, useRef, useEffect, useCallback } from 'react'
import './index.css'
import synpinLogo from './images/synpin.png'
import { MarkdownRenderer } from './components/MarkdownRenderer'
import { EmojiPicker } from './components/EmojiPicker'
import { SettingsPage } from './components/SettingsPage'
import { OtdelChatView } from './components/OtdelChatView'
import { OtdelSettingsPanel } from './components/OtdelSettingsPanel'
import {
  WidgetDropZone,
  useWidgetLayout,
  WIDGET_META,
  type Department,
  type WidgetType,
} from './components/WidgetDropZone'
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  closestCenter,
} from '@dnd-kit/core'
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable'
import { useWebSocket } from './hooks/useWebSocket'

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
  is_primary?: boolean
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

// ─── Tool Timeline (collapsible action flow) ────────────────

interface ToolTimelineProps {
  tools: ToolCall[]
  isLive: boolean
  toolNames: Record<string, string>
}

function ToolTimeline({ tools, isLive, toolNames }: ToolTimelineProps) {
  const [expanded, setExpanded] = useState(isLive)

  // Auto-expand when live (tools running), auto-collapse when done
  useEffect(() => {
    if (isLive) setExpanded(true)
  }, [isLive])

  const doneCount = tools.filter(t => t.status === 'completed').length
  const errorCount = tools.filter(t => t.status === 'error').length
  const runningCount = tools.filter(t => t.status === 'running').length
  const total = tools.length

  // Summary line for collapsed state
  const summary = errorCount > 0
    ? `${errorCount} ошибка${errorCount > 1 ? 'и' : ''}`
    : runningCount > 0
      ? `${doneCount}/${total} действий...`
      : `${total} действий ✓`

  // Render chips for collapsed state
  const renderChips = () => (
    <div className="tool-chips">
      {tools.map((tc) => (
        <span key={tc.id} className={`tool-chip ${tc.status}`}>
          {tc.status === 'running' && <span className="tool-spinner" />}
          {tc.status === 'completed' && <span className="tool-check">✓</span>}
          {tc.status === 'error' && <span className="tool-error">✕</span>}
          <span>{toolNames[tc.name] || tc.name}</span>
        </span>
      ))}
    </div>
  )

  return (
    <div className={`tool-timeline ${expanded ? 'expanded' : 'collapsed'}`}>
      {/* Header — always visible */}
      <button
        className="tool-timeline-header"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="tool-timeline-icon">
          {runningCount > 0 ? '⚡' : errorCount > 0 ? '⚠' : '✓'}
        </span>
        <span className="tool-timeline-summary">{summary}</span>
        <span className={`tool-timeline-chevron ${expanded ? 'open' : ''}`}>▾</span>
      </button>

      {/* Collapsed: horizontal chips */}
      {!expanded && renderChips()}

      {/* Expanded: vertical list */}
      {expanded && (
        <div className="tool-timeline-body open">
          {tools.map((tc) => (
            <div key={tc.id} className={`tool-timeline-row ${tc.status}`}>
              <span className="tool-timeline-status">
                {tc.status === 'running' && <span className="tool-spinner" />}
                {tc.status === 'completed' && <span className="tool-check">✓</span>}
                {tc.status === 'error' && <span className="tool-error">✕</span>}
              </span>
              <span className="tool-timeline-name">
                {toolNames[tc.name] || tc.name}
              </span>
              {tc.status === 'error' && tc.error && (
                <span className="tool-timeline-error">{tc.error}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function App() {
  const [page, setPage] = useState<'chat' | 'settings'>('chat')
  const [activeOtdelId, setActiveOtdelId] = useState<string | null>(null)
  const [otdelSettingsOpen, setOtdelSettingsOpen] = useState(false)
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
  const [agentSearch, setAgentSearch] = useState('')
  const [primarySlug, setPrimarySlug] = useState('')
  // Otdels for sidebar — loaded from /api/otdels
  const [sidebarDepartments, setSidebarDepartments] = useState<Department[]>([])

  // Widget layout (left/right zones on main page)
  const { layout, removeWidget, handleDragEnd } = useWidgetLayout()

  // DndContext sensors
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  // WebSocket — single connection for all real-time messaging
  const { send: wsSend, on: wsOn, connected: wsConnected } = useWebSocket()

  const [activeDragId, setActiveDragId] = useState<string | null>(null)

  const refreshDepartments = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/otdels`)
      const data = await res.json()
      const depts = (data.otdels || []).map((d: any) => ({
        id: d.otdelid,
        name: d.name,
        description: d.description || '',
        color: d.color || '#f97316',
        mentor_role: d.mentor_role || '',
        escalation: d.escalation || '',
        agent_count: d.agent_count || 0,
        head: d.head || '',
        workers: d.workers || [],
      }))
      setSidebarDepartments(depts)
    } catch {}
  }, [])

  useEffect(() => {
    refreshDepartments()
  }, [refreshDepartments])

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const activeAgentRef = useRef<AgentConfig | null>(null)
  const messagesRef = useRef<Message[]>([])

  // Keep refs in sync with state
  activeAgentRef.current = activeAgent
  messagesRef.current = messages

  // Tool display names for badges
  const TOOL_DISPLAY_NAMES: Record<string, string> = {
    terminal: 'Терминал',
    file_read: 'Чтение файла',
    file_write: 'Запись файла',
    search_files: 'Поиск файлов',
    web_search: 'Поиск в интернете',
    code_exec: 'Python',
    // memory tools hidden from UI — run silently
  }

  // Tools hidden from UI (run silently in background)
    const HIDDEN_TOOLS = new Set(['memory_read', 'memory_write'])

    // Save sidebar state
    useEffect(() => {
      localStorage.setItem('synpin-sidebar', sidebarOpen ? 'open' : 'closed')
    }, [sidebarOpen])

    // Reveal metadata 0.5s after streaming completes
    useEffect(() => {
      if (!isTyping && messages.length > 0) {
        const timer = setTimeout(() => {
          setRevealedMeta(prev => {
            const next = new Set(prev)
            // Reveal ALL assistant messages that have model or agent_name (from history or done streaming)
            for (const msg of messages) {
              if (msg.role === 'assistant' && (msg.model || msg.agent_name)) {
                next.add(msg.id)
              }
            }
            return next
          })
        }, 500)
        return () => clearTimeout(timer)
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

  // Apply saved theme on initial load
  useEffect(() => {
    const applyTheme = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/config/settings`)
        if (!res.ok) return
        const settings = await res.json()
        const theme = settings?.ui?.theme
        if (!theme) return

        const root = document.documentElement

        // Clear all classes
        root.classList.remove('light-theme', 'dark-theme', 'oled-theme')

        // Clear inline styles
        for (let i = root.style.length - 1; i >= 0; i--) {
          const prop = root.style[i]
          if (prop && prop.startsWith('--')) {
            root.style.removeProperty(prop)
          }
        }

        if (theme === 'dark') {
          // Default dark
        } else if (theme === 'dark-oled') {
          root.classList.add('oled-theme')
        } else if (theme === 'light') {
          root.classList.add('light-theme')
        } else if (theme === 'tweakcn') {
          root.classList.add('dark-theme')
          // Load saved TweakCN theme
          const themesRes = await fetch(`${API_BASE}/api/themes/tweakcn/list`)
          if (themesRes.ok) {
            const themesData = await themesRes.json()
            // 'current' is always first in the list
            const savedTheme = themesData?.themes?.[0]
            if (savedTheme) {
              const vars = savedTheme.dark || savedTheme.light
              if (vars) {
                Object.entries(vars).forEach(([key, value]) => {
                  root.style.setProperty(key, value as string)
                })
              }
            }
          }
        }
      } catch {}
    }
    applyTheme()
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

        // Load primary agent slug
        let primarySlug = ''
        try {
          const primaryRes = await fetch(`${API_BASE}/api/config/primary-agent`)
          const primaryData = await primaryRes.json()
          primarySlug = primaryData.slug || ''
          setPrimarySlug(primarySlug)
        } catch {}

        // Set default active agent: primary first, then first enabled
        if (allAgents.length > 0 && !activeAgent) {
          const primary = primarySlug ? allAgents.find(a => a.slug === primarySlug) : null
          setActiveAgent(primary || allAgents[0])
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

        // Check if last message is user without assistant response (background task ongoing)
        const lastMsg = msgs[msgs.length - 1]
        const hasPendingTask = lastMsg?.role === 'user'

        if (msgs.length > 0) {
          let restored: Message[] = msgs.map((m: { role: string; content: string; model?: string; agent_name?: string }, i: number) => ({
            id: `restored-${i}`,
            role: m.role as 'user' | 'assistant',
            content: m.content,
            timestamp: new Date(),
            model: m.model,
            agent_name: m.agent_name,
          }))

          // Check if restored messages already end with empty assistant (from SSE)
          const lastRestored = restored[restored.length - 1]
          const alreadyHasPlaceholder = lastRestored?.role === 'assistant' && !lastRestored.content

          // Add placeholder if background task is ongoing AND no placeholder exists
          if (hasPendingTask && !alreadyHasPlaceholder) {
            restored.push({
              id: `placeholder-${Date.now()}`,
              role: 'assistant',
              content: '',
              timestamp: new Date(),
              tools: [],
            })
            setIsTyping(true) // Show spinner while polling
          }

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

  // ─── Polling: check for background task completion ──────────────────
  // Only runs after page reload when a task was running (history has user without assistant)
  useEffect(() => {
    if (!activeAgent) return

    const pollInterval = setInterval(async () => {
      // Check for empty assistant placeholder using ref (always current)
      const hasEmptyPlaceholder = messagesRef.current.some(m => m.role === 'assistant' && !m.content)
      if (!hasEmptyPlaceholder) return

      try {
        const res = await fetch(`${API_BASE}/api/chat/history?agent_slug=${activeAgent.slug}&channel_id=web`)
        if (!res.ok) return
        const data = await res.json()
        const serverMsgs = data.messages || []

        // ONLY fill placeholder when server's LAST message is an assistant response
        // This means the LLM has completed and we can safely display the answer
        const lastServerMsg = serverMsgs[serverMsgs.length - 1]
        if (!lastServerMsg || lastServerMsg.role !== 'assistant') return

        // Find the placeholder (empty assistant) and fill it
        setMessages(prev => {
          const placeholderId = prev.map(m => m.id).reverse().find(id => {
            const msg = prev.find(m => m.id === id)
            return msg?.role === 'assistant' && !msg.content
          })
          if (placeholderId) {
            setIsTyping(false)
            return prev.map(m => m.id === placeholderId
              ? { ...m, content: lastServerMsg.content, model: lastServerMsg.model, agent_name: lastServerMsg.agent_name }
              : m
            )
          }
          return prev
        })
      } catch (e) {
        // Polling failed — silent
      }
    }, 3000) // Poll every 3 seconds

    return () => clearInterval(pollInterval)
  }, [activeAgent])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Scroll to bottom when returning from settings to chat
  useEffect(() => {
    if (page === 'chat') {
      requestAnimationFrame(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'instant' })
      })
    }
  }, [page])

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

    const userInput = input
    setInput('')

    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }

    setIsTyping(true)

    // Create user message + assistant placeholder in one atomic update
    const assistantId = (Date.now() + 1).toString()
    setMessages(prev => [...prev, userMsg, {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      tools: [],
    }])

    const activeTools: ToolCall[] = []
    let toolIndex = 0
    let fullContent = ''

    // Build system prompt from agent config
    let systemPrompt: string | undefined
    let agentName: string | undefined

    // Check if this is a Hermes external agent — use SSE fallback
    const isHermesAgent = activeAgent?.is_external && activeAgent?.type === 'hermes'

    if (activeAgent) {
      agentName = activeAgent.name
      if (isHermesAgent) {
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

    // ── Hermes agents: keep SSE (separate endpoint) ──────────────
    if (isHermesAgent) {
      try {
        const history = messagesRef.current.map(m => ({ role: m.role, content: m.content }))
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
            tools: activeAgent?.tools || [],
          }),
        })
        if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        const reader = response.body?.getReader()
        if (!reader) throw new Error('No response body')
        const decoder = new TextDecoder()
        let buffer = ''
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
              fullContent += parsed.content
              setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: fullContent } : m))
            } else if (parsed.type === 'tool_start') {
              const toolName = String(parsed.tool || '')
              if (HIDDEN_TOOLS.has(toolName)) { toolIndex++; continue }
              const tc: ToolCall = { id: `${assistantId}-tool-${toolIndex++}`, name: toolName, params: (parsed.params as Record<string, unknown>) || {}, status: 'running' }
              activeTools.push(tc)
              setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, tools: [...(m.tools || []), tc] } : m))
            } else if (parsed.type === 'tool_end') {
              const toolName = String(parsed.tool || '')
              if (HIDDEN_TOOLS.has(toolName)) { continue }
              const idx = activeTools.findIndex(t => t.name === toolName && t.status === 'running')
              if (idx !== -1 && activeTools[idx]) { activeTools[idx].status = parsed.success ? 'completed' : 'error'; activeTools[idx].result = String(parsed.result || '') }
              setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, tools: [...activeTools] } : m))
            } else if (parsed.type === 'done') {
              setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, model: parsed.model as string, agent_name: parsed.agent_name as string } : m))
              streamDone = true; break
            } else if (parsed.type === 'error') { throw new Error(String(parsed.message || 'Stream error')) }
          }
          if (streamDone) break
        }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : 'Unknown error'
        setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: m.content || `⚠️ Ошибка: ${errorMsg}` } : m))
      } finally {
        setIsTyping(false)
      }
      return
    }

    // ── SynPin agents: WebSocket ─────────────────────────────────
    const cleanupFns: (() => void)[] = []

    const onChunk = wsOn('chat:chunk', (msg) => {
      if (msg.agent_slug !== activeAgent?.slug) return
      fullContent += msg.content
      setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: fullContent } : m))
    })

    const onToolStart = wsOn('chat:tool_start', (msg) => {
      if (msg.agent_slug !== activeAgent?.slug) return
      const toolName = String(msg.tool || '')
      if (HIDDEN_TOOLS.has(toolName)) { toolIndex++; return }
      const tc: ToolCall = { id: `${assistantId}-tool-${toolIndex++}`, name: toolName, params: (msg.params as Record<string, unknown>) || {}, status: 'running' }
      activeTools.push(tc)
      setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, tools: [...(m.tools || []), tc] } : m))
    })

    const onToolEnd = wsOn('chat:tool_end', (msg) => {
      if (msg.agent_slug !== activeAgent?.slug) return
      const toolName = String(msg.tool || '')
      if (HIDDEN_TOOLS.has(toolName)) { return }
      const idx = activeTools.findIndex(t => t.name === toolName && t.status === 'running')
      if (idx !== -1 && activeTools[idx]) {
        activeTools[idx].status = msg.success ? 'completed' : 'error'
        activeTools[idx].result = String(msg.result || '')
        activeTools[idx].error = msg.error ? String(msg.error) : undefined
      }
      setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, tools: [...activeTools] } : m))
    })

    const onDone = wsOn('chat:done', (msg) => {
      if (msg.agent_slug !== activeAgent?.slug) return
      setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, model: msg.model || 'assistant', agent_name: msg.agent_name } : m))
      cleanup()
    })

    const onError = wsOn('chat:error', (msg) => {
      cleanup()
      setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, content: m.content || `⚠️ Ошибка: ${msg.message || 'Stream error'}` } : m))
    })

    const cleanup = () => {
      cleanupFns.forEach(fn => fn())
      setIsTyping(false)
    }

    cleanupFns.push(onChunk, onToolStart, onToolEnd, onDone, onError)

    // Send via WebSocket
    wsSend('chat:send', {
      agent_slug: activeAgent?.slug || '',
      message: userInput,
      system_prompt: systemPrompt,
      channel_id: 'web',
    })
  }, [input, isTyping, activeAgent, wsSend, wsOn])

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
      // Also refresh primary slug
      try {
        const primaryRes = await fetch(`${API_BASE}/api/config/primary-agent`)
        const primaryData = await primaryRes.json()
        setPrimarySlug(primaryData.slug || '')
      } catch {}
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
          {/* Primary Agent — pinned above search */}
          {primarySlug && availableAgents.find(a => a.slug === primarySlug) && (() => {
            const primary = availableAgents.find(a => a.slug === primarySlug)!
            return (
              <div className="primary-agent">
                <button
                  className="agent-list-item active"
                  onClick={() => {
                    setActiveAgent(primary)
                    setMessages([])
                  }}
                >
                  <span className="agent-list-avatar" style={{ background: primary.is_external ? '#f97316' : '#6b7280' }}>
                    {primary.is_external ? 'H' : primary.name[0]}
                  </span>
                  <div className="agent-list-info">
                    <span className="agent-list-name">
                      {primary.name}
                    </span>
                    <span className="agent-list-role">{primary.role_name || primary.type}</span>
                  </div>
                  <span
                    className="star-toggle active"
                    title="Снять с главного"
                    onClick={(e) => {
                      e.stopPropagation()
                      fetch(`${API_BASE}/api/config/primary-agent`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ slug: '' }),
                      }).then(() => setPrimarySlug(''))
                    }}
                  >★</span>
                </button>
              </div>
            )
          })()}

          {/* Agent Search */}
          <div className="agent-search">
            <input
              className="agent-search-input"
              type="text"
              placeholder="Поиск агента..."
              value={agentSearch}
              onChange={(e) => setAgentSearch(e.target.value)}
            />
          </div>

          {/* Agent List — always visible, filtered by search, excludes primary */}
          {(() => {
            const filteredAgents = availableAgents
              .filter(agent => agent.slug !== primarySlug)
              .filter(agent => {
                if (!agentSearch.trim()) return true
                const q = agentSearch.toLowerCase()
                return (
                  agent.name.toLowerCase().includes(q) ||
                  (agent.role_name || '').toLowerCase().includes(q) ||
                  (agent.type || '').toLowerCase().includes(q)
                )
              })
            return (
              <div className={`agent-list ${filteredAgents.length > 3 ? 'has-overflow' : ''}`}>
                {filteredAgents.map(agent => (
                  <button
                    key={agent.slug}
                    className={`agent-list-item ${activeAgent?.slug === agent.slug ? 'active' : ''}`}
                    onClick={() => {
                      setActiveAgent(agent)
                      setMessages([])
                      setAgentSearch('')
                    }}
                  >
                    <span className="agent-list-avatar" style={{ background: agent.is_external ? '#f97316' : '#6b7280' }}>
                      {agent.is_external ? 'H' : agent.name[0]}
                    </span>
                    <div className="agent-list-info">
                      <span className="agent-list-name">
                        {agent.name}
                        {agent.is_external && <span className="agent-badge extern">extern</span>}
                      </span>
                      <span className="agent-list-role">{agent.role_name || agent.type}</span>
                    </div>
                    <span
                      className={`star-toggle ${primarySlug === agent.slug ? 'active' : ''}`}
                      onClick={(e) => {
                        e.stopPropagation()
                        const newPrimary = primarySlug === agent.slug ? '' : agent.slug
                        fetch(`${API_BASE}/api/config/primary-agent`, {
                          method: 'PUT',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ slug: newPrimary }),
                        }).then(() => setPrimarySlug(newPrimary))
                      }}
                    >★</span>
                  </button>
                ))}
                {filteredAgents.length === 0 && agentSearch.trim() && (
                  <div className="agent-list-empty">Ничего не найдено</div>
                )}
              </div>
            )
          })()}

          <div className="sidebar-footer">
            <button className="settings-btn" onClick={() => setPage('settings')}>
              <span>⚙️</span> Настройки
            </button>
            <div className="version-bar">
              <span className="version-label">VERSION</span>
              <span className="version-number">v0.2.2</span>
              <span className="version-status up-to-date" />
            </div>
          </div>
        </div>
      </aside>

      {/* Main Area with Widget Zones */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={(e) => { setActiveDragId(String(e.active.id)); setSidebarOpen(false) }}
        onDragEnd={(e) => { setActiveDragId(null); handleDragEnd(e, layout) }}
      >
        <div className="main-layout">
          <WidgetDropZone
            side="left"
            widgets={layout.left}
            departments={sidebarDepartments}
            onRemove={removeWidget}
            isDragging={!!activeDragId}
            onDepartmentClick={(id) => { setActiveOtdelId(id); setPage('chat') }}
            activeOtdelId={activeOtdelId}
          />
          <main className="main-area">
        {page === 'settings' ? (
          <SettingsPage onBack={() => setPage('chat')} onAgentsChange={refreshAgents} onDepartmentsChange={refreshDepartments} />
        ) : activeOtdelId ? (() => {
          const otdel = sidebarDepartments.find(d => d.id === activeOtdelId)
          if (!otdel) return null
          return (
            <>
              <OtdelChatView
                key={otdel.id}
                otdel={{ ...otdel, otdelid: otdel.id }}
                onBack={() => setActiveOtdelId(null)}
                onOpenSettings={() => setOtdelSettingsOpen(true)}
                wsSend={wsSend}
                wsOn={wsOn}
                wsConnected={wsConnected}
              />
              <OtdelSettingsPanel
                key={`settings-${otdel.id}`}
                otdel={{ ...otdel, otdelid: otdel.id }}
                open={otdelSettingsOpen}
                onClose={() => setOtdelSettingsOpen(false)}
                onSaved={refreshDepartments}
              />
            </>
          )
        })() : messages.length === 0 ? (
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
                      {/* Tool timeline — collapsible action flow */}
                      {msg.tools && msg.tools.length > 0 && (
                        <ToolTimeline
                          tools={msg.tools}
                          isLive={isLastAssistant && isTyping}
                          toolNames={TOOL_DISPLAY_NAMES}
                        />
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
          <WidgetDropZone
            side="right"
            widgets={layout.right}
            departments={sidebarDepartments}
            onRemove={removeWidget}
            isDragging={!!activeDragId}
            onDepartmentClick={(id) => { setActiveOtdelId(id); setPage('chat') }}
            activeOtdelId={activeOtdelId}
          />
        </div>
        <DragOverlay>
          {activeDragId ? (
            <div className="widget-drag-overlay">
              {(() => {
                const meta = WIDGET_META[activeDragId.replace('tab-', '') as WidgetType]
                return meta ? <><span>{meta.icon}</span> {meta.label}</> : activeDragId
              })()}
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  )
}

export default App
