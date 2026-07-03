import { lazy, Suspense } from 'react'
import { useState, useRef, useEffect, useCallback } from 'react'
import './index.css'
import synpinLogo from './images/synpin.png'
import { MarkdownRenderer } from './components/MarkdownRenderer'
import { EmojiPicker } from './components/EmojiPicker'
import { Sidebar, type AgentConfig } from './components/Sidebar'
import type { Message } from './components/chatTypes'
import { ChatSkeleton } from './components/ChatSkeleton'
import { PageTransition } from './components/PageTransition'
import { ToolTimeline, TOOL_DISPLAY_NAMES } from './components/ToolTimeline'
import { useChatSubmit } from './hooks/useChatSubmit'
import { useChatHistory } from './hooks/useChatHistory'

// Tiny fallback for lazy chunks — just a centered dot. Better than
// nothing while Settings/Kanban/Projects/etc. code is loading.
const PageFallback = () => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 1, minHeight: '300px', color: 'var(--text-dim)' }}>
    <span>загрузка…</span>
  </div>
)

// Heavy pages — lazy-loaded to keep initial bundle small.
// Settings + Kanban + Projects alone are ~2400 lines of TSX that
// users don't need until they navigate there.
const SettingsPage = lazy(() => import('./components/SettingsPage').then(m => ({ default: m.SettingsPage })))
const KanbanBoard = lazy(() => import('./components/KanbanBoard').then(m => ({ default: m.KanbanBoard })))
const ProjectsPage = lazy(() => import('./components/ProjectsPage').then(m => ({ default: m.ProjectsPage })))
const ConnectionsCanvas = lazy(() => import('./components/ConnectionsCanvas').then(m => ({ default: m.ConnectionsCanvas })))
const DeadlinesPage = lazy(() => import('./components/DeadlinesPage').then(m => ({ default: m.DeadlinesPage })))
const OtdelChatView = lazy(() => import('./components/OtdelChatView').then(m => ({ default: m.OtdelChatView })))
const OtdelSettingsPanel = lazy(() => import('./components/OtdelSettingsPanel').then(m => ({ default: m.OtdelSettingsPanel })))
const SetupWizard = lazy(() => import('./components/SetupWizard').then(m => ({ default: m.SetupWizard })))
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
import { useGlobalTooltip } from './hooks/useGlobalTooltip'
import { useChatScroll } from './hooks/useChatScroll'
import { ImageAttachment, fileToAttachment, extractImagesFromPaste, type ImageAttachment as ImageAttachmentType } from './components/ImageAttachment'

import { API_BASE } from './config'

function App() {
  // Unified navigation: one state variable for everything in the
  // central area. The sidebar is the only navigator — every "back"
  // button was a workaround for having two navigation state variables
  // (page + activeOtdelId) that could desync. Single source of truth.
  type View =
    | { type: 'chat' }
    | { type: 'otdel'; id: string }
    | { type: 'settings' }
    | { type: 'kanban' }
    | { type: 'connections' }
    | { type: 'deadlines' }
    | { type: 'projects' }
    | { type: 'setup' }
  // ── Virgin detection ──────────────────────────────────────────────
  const [needsSetup, setNeedsSetup] = useState<boolean | null>(null)
  const [view, setView] = useState<View>({ type: 'chat' })

  // Virgin detection: if providers are empty, show setup wizard
  useEffect(() => {
    const isStartRoute = window.location.pathname === '/start/'
      || window.location.pathname.startsWith('/start')

    fetch('/api/setup/status')
      .then(r => r.json())
      .then(data => {
        const needSetup = data.needs_setup === true

        if (isStartRoute) {
          // /start/ forces wizard regardless of virgin state
          setView({ type: 'setup' })
        } else {
          setNeedsSetup(needSetup)
        }
      })
      .catch(() => {
        if (isStartRoute) {
          setView({ type: 'setup' })
        } else {
          setNeedsSetup(false)
        }
      })
  }, [])

  // Switch to setup wizard when virgin system is detected
  useEffect(() => {
    if (needsSetup === true) {
      setView({ type: 'setup' })
    }
  }, [needsSetup])

  const [otdelSettingsOpen, setOtdelSettingsOpen] = useState(false)
  // null = not loaded yet (show skeleton), [] = loaded but empty chat
  const [messages, setMessages] = useState<Message[] | null>(null)
  const [input, setInput] = useState('')
  const [attachments, setAttachments] = useState<ImageAttachmentType[]>([])
  const [compactionNotice, setCompactionNotice] = useState<string | null>(null)
  const [isTyping, setIsTyping] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    const saved = localStorage.getItem('synpin-sidebar')
    return saved === 'open'
  })
  const [sidebarReady, setSidebarReady] = useState(false)
  const [logoVisible, setLogoVisible] = useState(false)
  const [revealedMeta, setRevealedMeta] = useState<Set<string>>(new Set())
  const [expandedThinking, setExpandedThinking] = useState<Set<string>>(new Set())
  const [activeAgent, setActiveAgent] = useState<AgentConfig | null>(null)
  const [availableAgents, setAvailableAgents] = useState<AgentConfig[]>([])
  // false until the initial /api/agents fetch resolves. Used to keep
  // <ChatSkeleton> on screen during the F5 "flash of empty state"
  // window — before the primary agent has been resolved and history
  // loading can start.
  const [agentsLoaded, setAgentsLoaded] = useState(false)
  const [agentSearch, setAgentSearch] = useState('')
  const [primarySlug, setPrimarySlug] = useState('')
  // Otdels for sidebar — loaded from /api/otdels
  const [sidebarDepartments, setSidebarDepartments] = useState<Department[]>([])

  // Chat auto-scroll — unified sentinel pattern
  const { sentinelRef: chatEndRef } = useChatScroll(messages)

  // DndContext sensors
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  // WebSocket — single connection for all real-time messaging
  const { send: wsSend, on: wsOn, connected: wsConnected } = useWebSocket()

  // Widget layout (left/right zones on main page) — needs wsOn
  const { layout, removeWidget, handleDragEnd } = useWidgetLayout(wsOn)

  // Global tooltip — intercepts all title attributes, shows mouse-following tooltip
  const globalTooltip = useGlobalTooltip()

  // ── Stuck state protection ──────────────────────────────────────
  const clearStuckState = useCallback(() => {
    setIsTyping(false)
    // Remove empty assistant placeholders (stuck from previous session)
    setMessages(prev => {
      if (!prev) return prev
      const cleaned = prev.filter(m => !(m.role === 'assistant' && !m.content && !m.tools?.length))
      return cleaned.length === prev.length ? prev : cleaned
    })
  }, [])

  // Handle WS connection state changes:
  // - Always clear stale placeholders when switching to chat view or WS changes
  const wasConnectedRef = useRef(false)
    const isStreamingRef = useRef(false)
    useEffect(() => {
    if (wasConnectedRef.current && !wsConnected) {
      // WS disconnected — clear typing and remove stuck placeholders
      clearStuckState()
    }
    // Always clear stale placeholders when connected and in chat view
    // BUT NOT during active streaming — isStreamingRef guards fresh placeholders
    if (wsConnected && !isStreamingRef.current) {
      const hasEmptyPlaceholder = (messages ?? []).some(m => m.role === 'assistant' && !m.content)
      if (hasEmptyPlaceholder && activeAgent && view.type === 'chat') {
        clearStuckState()
      }
    }
    wasConnectedRef.current = wsConnected
  }, [wsConnected, messages, clearStuckState, activeAgent, view])

  // Server version — single source of truth is the backend.
  // Strategy: fetch /api/version on mount (works even if WS isn't
  // connected yet or broadcast was sent before client joined), then
  // subscribe to the WS 'version:changed' event for future updates
  // (e.g. server upgrades without page reload).
  const [serverVersion, setServerVersion] = useState<string>('…')
  useEffect(() => {
    let cancelled = false
    fetch(`${API_BASE}/api/version`)
      .then(r => r.ok ? r.json() : null)
      .then((data: { version?: string } | null) => {
        if (!cancelled && data?.version) setServerVersion(`v${data.version}`)
      })
      .catch(() => { /* keep placeholder; WS will fill it in */ })
    return () => { cancelled = true }
  }, [])
  // Push updates from the server (startup broadcast + future changes)
  useEffect(() => {
    const off = wsOn('version:changed', (msg: { version: string }) => {
      setServerVersion(`v${msg.version}`)
    })
    return off
  }, [wsOn])

  // Cron job completed — message arrives as a full message (not streamed)
  // Lives as a persistent useEffect so it's ALWAYS listening, not just during handleSend
  useEffect(() => {
    const off = wsOn('chat:cron', (msg) => {
      if (msg.agent_slug !== activeAgent?.slug) return
      const raw = msg.message as any
      const chatMsg = {
        id: raw.id || `cron-${Date.now()}`,
        role: 'assistant',
        content: typeof raw.content === 'string' ? raw.content : JSON.stringify(raw.content ?? ''),
        sender: raw.sender || msg.agent_slug,
        sender_name: raw.sender_name || raw.agent_name || '',
        timestamp: raw.timestamp || new Date().toISOString(),
        is_head: raw.is_head || false,
        model: raw.model || '',
        provider: raw.provider || '',
      } as any
      setMessages(prev => {
        if (!prev) return [chatMsg]
        if (prev.some(m => m.id === chatMsg.id)) return prev
        return [...prev, chatMsg]
      })
    })
    return off
  }, [wsOn, activeAgent?.slug])

  // Listen for primary agent changes
  useEffect(() => {
    const off = wsOn('agent:primary_changed', (msg: { slug: string }) => {
      setPrimarySlug(msg.slug)
      // Sync is_primary in agents list
      setAvailableAgents(prev => prev.map(a => ({
        ...a,
        is_primary: a.slug === msg.slug,
      })))
    })
    return off
  }, [wsOn])

  // Listen for agent list changes (create/update/delete) — refresh sidebar
  useEffect(() => {
    const off = wsOn('agent:list_changed', () => {
      fetch(`${API_BASE}/api/agents`)
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (!data?.agents) return
          const allAgents = (Object.entries(data.agents) as [string, any][]).map(([slug, cfg]): AgentConfig => ({
            slug,
            agentid: cfg.agentid || slug,
            name: cfg.name || slug,
            role: cfg.role || '',
            role_name: cfg.role_name || '',
            department: cfg.department || '',
            department_name: cfg.department_name || '',
            model: cfg.model || '',
            provider: cfg.provider || null,
            system_prompt: cfg.system_prompt || '',
            description: cfg.description || '',
            tone: cfg.tone || '',
            style: cfg.style || '',
            traits: cfg.traits || [],
            tools: cfg.tools || [],
            temperature: cfg.temperature ?? 0.7,
            max_tokens: cfg.max_tokens ?? 4096,
            enabled: cfg.enabled ?? true,
            is_primary: cfg.is_primary ?? false,
            is_external: cfg.is_external ?? false,
            type: cfg.type || '',
          }))
          setAvailableAgents(allAgents)
          // Sync active agent if it was updated
          const current = activeAgentRef.current
          if (current) {
            const fresh = allAgents.find(a => a.slug === current.slug)
            if (fresh) setActiveAgent(fresh)
          }
        })
        .catch(() => {})
      // Re-fetch primary agent slug (may have changed after create/delete)
      fetch(`${API_BASE}/api/config/primary-agent`)
        .then(r => r.ok ? r.json() : null)
        .then(data => { if (data?.slug) setPrimarySlug(data.slug) })
        .catch(() => {})
    })
    return off
  }, [wsOn])

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

  // Listen for otdel list changes (create/update/delete) — refresh sidebar departments
  useEffect(() => {
    const off = wsOn('otdels:list_changed', () => {
      refreshDepartments()
    })
    return off
  }, [wsOn, refreshDepartments])

  // Listen for real-time otdel messages
  useEffect(() => {
    const off = wsOn('otdel:message', (msg: any) => {
      // Fire a custom event so the OtdelChatView component can handle it
      window.dispatchEvent(new CustomEvent('otdel:message', { detail: msg }))
    })
    return off
  }, [wsOn])

  // Listen for kanban task updates
  useEffect(() => {
    const off = wsOn('kanban:task_created', (msg: any) => {
      window.dispatchEvent(new CustomEvent('kanban:refresh', { detail: msg }))
    })
    return off
  }, [wsOn])

  useEffect(() => {
    const off = wsOn('kanban:task_updated', (msg: any) => {
      window.dispatchEvent(new CustomEvent('kanban:refresh', { detail: msg }))
    })
    return off
  }, [wsOn])

  useEffect(() => {
    const off = wsOn('kanban:tasks_deleted', (msg: any) => {
      window.dispatchEvent(new CustomEvent('kanban:refresh', { detail: msg }))
    })
    return off
  }, [wsOn])

  // Listen for project updates
  useEffect(() => {
    const off = wsOn('project:updated', (msg: any) => {
      window.dispatchEvent(new CustomEvent('project:refresh', { detail: msg }))
    })
    return off
  }, [wsOn])

  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const attachRef = useRef<{ openPicker: () => void }>(null)
  const activeAgentRef = useRef<AgentConfig | null>(null)
  const messagesRef = useRef<Message[] | null>(null)

  // Keep refs in sync with state
  activeAgentRef.current = activeAgent
  messagesRef.current = messages

  // Tool display names imported from ToolTimeline module (shared with otdel chat)

    // Save sidebar state
    useEffect(() => {
      localStorage.setItem('synpin-sidebar', sidebarOpen ? 'open' : 'closed')
    }, [sidebarOpen])

    // Reveal metadata 0.5s after streaming completes
    useEffect(() => {
      if (!isTyping && messages && messages.length > 0) {
        const timer = setTimeout(() => {
          setRevealedMeta(prev => {
            const next = new Set(prev)
            // Reveal ALL assistant messages — show meta for every assistant reply
            for (const msg of messages) {
              if (msg.role === 'assistant') {
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
  // The inline script in index.html already applied from localStorage cache.
  // We only need to sync if API has a DIFFERENT theme than what's cached.
  useEffect(() => {
    const syncTheme = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/config/settings`)
        if (!res.ok) return
        const settings = await res.json()
        const theme = settings?.ui?.theme
        if (!theme) return

        // Apply border_radius (skip if TweakCN handles it)
        if (theme !== 'tweakcn' && settings.ui.border_radius) {
          document.documentElement.style.setProperty('--radius', `${settings.ui.border_radius}px`)
        }

        // Check what's currently applied (set by inline script or previous apply)
        const root = document.documentElement
        const cached = (() => {
          try { return JSON.parse(localStorage.getItem('synpin_theme') || '{}') } catch { return {} }
        })()

        // If API theme matches cached theme — already applied by inline script, skip
        if (cached.name === theme) return

        // Theme changed externally (another tab?) — apply it
        root.classList.remove('light-theme', 'dark-theme', 'oled-theme')
        for (let i = root.style.length - 1; i >= 0; i--) {
          const prop = root.style[i]
          if (prop && prop.startsWith('--')) root.style.removeProperty(prop)
        }

        const themeCache: { name: string; vars?: Record<string, string> } = { name: theme }

        if (theme === 'dark') {
          // Default dark
        } else if (theme === 'dark-oled') {
          root.classList.add('oled-theme')
        } else if (theme === 'light') {
          root.classList.add('light-theme')
        } else if (theme === 'tweakcn') {
          root.classList.add('dark-theme')
          const themesRes = await fetch(`${API_BASE}/api/themes/tweakcn/list`)
          if (themesRes.ok) {
            const themesData = await themesRes.json()
            const savedTheme = themesData?.themes?.[0]
            if (savedTheme) {
              const vars = savedTheme.dark || savedTheme.light
              if (vars) {
                Object.entries(vars).forEach(([key, value]) => {
                  root.style.setProperty(key, value as string)
                })
                themeCache.vars = vars as Record<string, string>
              }
            }
          }
        }

        localStorage.setItem('synpin_theme', JSON.stringify(themeCache))
      } catch {}
    }
    syncTheme()
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
        setAgentsLoaded(true)
      } catch (e) {
        console.error('[agents] load error:', e)
        setAgentsLoaded(true) // unblock UI even on error so user sees something
      }
    }
    loadAgents()
  }, [])

  // Load chat history when active agent changes OR when returning to chat view
  // Load chat history on agent switch — extracted to hooks/useChatHistory.ts
  useChatHistory({ activeAgent, viewType: view.type, setMessages, setIsTyping })
  // Auto-scroll handled by useChatScroll hook (sentinel pattern)

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 150) + 'px'
  }

  // ── Compaction indicator ─────────────────────────────────────────
  useEffect(() => {
    const unsubCompacting = wsOn('chat:compacting', (msg) => {
      if (msg.agent_slug !== activeAgent?.slug) return
      setCompactionNotice(msg.notice || 'Компакция истории...')
      // Auto-clear after 5 seconds
      setTimeout(() => setCompactionNotice(null), 5000)
    })
    return unsubCompacting
  }, [wsOn, activeAgent])

  // Chat submit/streaming — extracted to hooks/useChatSubmit.ts
  const { handleSubmit, handleKeyDown } = useChatSubmit({
    input, attachments, isTyping, activeAgent,
    textareaRef, messagesRef, isStreamingRef,
    setInput, setAttachments, setMessages, setIsTyping, setCompactionNotice,
        wsSend, wsOn,
  })

  const formatTime = (date: Date | string) => {
      const d = typeof date === 'string' ? new Date(date) : date
      return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
    }

  const renderMeta = (msg: Message) => {
    if (msg.role === 'user') {
      return <span className="message-time">{formatTime(msg.timestamp)}</span>
    }
    // Assistant: time — agent_name · model · tokens
    const totalTokens = (msg.prompt_tokens || 0) + (msg.completion_tokens || 0)
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
        {totalTokens > 0 && (
          <>
            <span className="meta-dot"> · </span>
            <span className="meta-badge dim">{totalTokens.toLocaleString('ru-RU')}т</span>
          </>
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

  // ── Image attachments ─────────────────────────────────────────
  const handleAddImages = useCallback(async (files: File[]) => {
    const newAttachments = await Promise.all(files.map(fileToAttachment))
    setAttachments(prev => [...prev, ...newAttachments])
  }, [])

  const handleRemoveImage = useCallback((id: string) => {
    setAttachments(prev => prev.filter(a => a.id !== id))
  }, [])

  const handlePaste = useCallback((e: React.ClipboardEvent) => {
    const images = extractImagesFromPaste(e)
    if (images.length > 0) {
      e.preventDefault()
      handleAddImages(images)
    }
  }, [handleAddImages])

  // Drag-n-drop state
  const [dragOver, setDragOver] = useState(false)
  const dragCounterRef = useRef(0)

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    dragCounterRef.current++
    // Check for files — types may be DOMStringList in some browsers
    const types = Array.from(e.dataTransfer.types)
    if (types.includes('Files') || types.includes('text/plain')) {
      setDragOver(true)
    }
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    dragCounterRef.current--
    if (dragCounterRef.current === 0) setDragOver(false)
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    dragCounterRef.current = 0
    setDragOver(false)
    const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'))
    if (files.length > 0) handleAddImages(files)
  }, [handleAddImages])

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
      <ImageAttachment
        ref={attachRef}
        images={attachments}
        onAdd={handleAddImages}
        onRemove={handleRemoveImage}
        disabled={isTyping}
      />
      <div className="input-form">
        <button
          type="button"
          className="attach-btn"
          onClick={() => attachRef.current?.openPicker()}
          disabled={isTyping}
          title="Прикрепить изображение"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
          </svg>
        </button>
        <EmojiPicker onSelect={handleEmojiSelect} />
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder={attachments.length > 0 ? 'Опиши что на картинке...' : 'Спроси что-нибудь...'}
          className="input-field"
          rows={1}
        />
        <button
          type="submit"
          disabled={!isTyping && !input.trim() && attachments.length === 0}
          className={`input-submit ${isTyping ? 'stop-mode' : ''}`}
          title={isTyping ? 'Остановить' : 'Отправить'}
        >
          {isTyping ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          )}
        </button>
      </div>
    </form>
  )

  return (
    <div className="app-container">
      {globalTooltip}
      {/* Fixed Logo — always visible, never moves */}
      <div
        className={`app-logo ${logoVisible ? 'visible' : ''}`}
        onClick={() => setSidebarOpen(!sidebarOpen)}
      >
        <img src={synpinLogo} alt="SynPin" />
      </div>

      {/* Sidebar — extracted to components/Sidebar.tsx (154 lines) */}
              <Sidebar
                open={sidebarOpen}
                ready={sidebarReady}
                agents={availableAgents}
                primarySlug={primarySlug}
                activeAgent={activeAgent}
                view={view}
                serverVersion={serverVersion}
                setActiveAgent={setActiveAgent}
                setMessages={setMessages}
                setView={setView}
                setPrimarySlug={setPrimarySlug}
                setAvailableAgents={setAvailableAgents}
                setAgentSearch={setAgentSearch}
                agentSearch={agentSearch}
              />

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
            onDepartmentClick={(id) => setView({ type: 'otdel', id })}
            activeOtdelId={view.type === 'otdel' ? view.id : null}
            wsOn={wsOn}
          />
          <main className="main-area">
        {(() => {
          // Compute a single pageKey that uniquely identifies the
          // currently-rendered "page". When any of these change, we
          // fade out + swap + fade in. First render skips the animation
          // (see PageTransition's isFirstRender ref).
          let pageKey: string
          if (view.type === 'kanban') pageKey = 'kanban'
          else if (view.type === 'connections') pageKey = 'connections'
          else if (view.type === 'deadlines') pageKey = 'deadlines'
          else if (view.type === 'projects') pageKey = 'projects'
          else if (view.type === 'setup') pageKey = 'setup'
          else if (view.type === 'settings') pageKey = 'settings'
          else if (view.type === 'otdel') pageKey = `otdel-${view.id}`
          else if (!agentsLoaded || (activeAgent && messages === null)) pageKey = 'chat-loading'
          else if (!activeAgent || !messages || messages.length === 0) pageKey = 'chat-empty'
          else pageKey = `chat-${activeAgent.slug}`

          let body: React.ReactNode
          if (view.type === 'kanban') {
            body = <KanbanBoard wsOn={wsOn} />
          } else if (view.type === 'deadlines') {
            body = <DeadlinesPage wsOn={wsOn} />
          } else if (view.type === 'projects') {
            body = <ProjectsPage wsOn={wsOn} />
          } else if (view.type === 'setup') {
            body = <SetupWizard onComplete={() => { window.location.reload() }} />
          } else if (view.type === 'connections') {
            body = <ConnectionsCanvas wsOn={wsOn} />
          } else if (view.type === 'settings') {
            body = <SettingsPage onAgentsChange={refreshAgents} onDepartmentsChange={refreshDepartments} wsOn={wsOn} />
          } else if (view.type === 'otdel') {
            const otdel = sidebarDepartments.find(d => d.id === view.id)
            if (otdel) {
              body = (
                <>
                  <OtdelChatView
                    key={otdel.id}
                    otdel={{ ...otdel, otdelid: otdel.id }}
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
            } else {
              body = null
            }
          } else if (!agentsLoaded || (activeAgent && messages === null)) {
            // Either the initial agent list is still loading (no agent
            // resolved yet, and we don't want to flash the empty state),
            // or an agent is set and its history is being fetched. In
            // both cases show the skeleton — it reserves layout space and
            // signals "loading" with no entrance animation. The skeleton
            // disappears the moment the relevant data arrives.
            body = <ChatSkeleton />
          } else if (!activeAgent || !messages || messages.length === 0) {
            // No agent selected (or no messages in the conversation) —
            // show the friendly empty state.
            body = (
              <div className="empty-state">
                <img src={synpinLogo} alt="SynPin" className="empty-logo-img" />
                <h1 className="empty-title">Чем могу помочь?</h1>
                {renderInput()}
              </div>
            )
          } else {
            body = (
              <div
                className="chat-view-wrapper"
                onDragEnter={handleDragEnter}
                onDragLeave={handleDragLeave}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                style={{ position: 'relative', display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}
              >
                <div className={`chat-drop-overlay ${dragOver ? 'active' : ''}`}>
                  <div className="chat-drop-overlay-inner">
                    <div className="chat-drop-overlay-icon">↓</div>
                    <div className="chat-drop-overlay-text">Перетащите изображение</div>
                    <div className="chat-drop-overlay-hint">PNG, JPEG, WebP, GIF — до 10 МБ</div>
                  </div>
                </div>
                <div className="messages-area">
                  <div className="messages-container" ref={messagesContainerRef}>
                    {messages.map((msg) => {
                      const isLastAssistant = msg.role === 'assistant' && msg.id === messages[messages.length - 1]?.id && isTyping
                      return (
                        <div key={msg.id} className={`message-row ${msg.role}`}>
                          <div className={`message-avatar ${msg.role} ${isLastAssistant && msg.content ? 'streaming' : ''}`}>
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
                          <div className={`message-wrapper ${isLastAssistant && msg.content ? 'streaming' : ''}`}>
                            <div className="message-bubble">
                              {msg.images && msg.images.length > 0 && (
                                <div className="message-images">
                                  {msg.images.map((src, i) => (
                                    <img key={i} src={src} alt={`Изображение ${i + 1}`} className="message-image" />
                                  ))}
                                </div>
                              )}
                              {msg.thinking && (
                                <div className={`thinking-block ${expandedThinking.has(msg.id) || (isLastAssistant && isTyping) ? 'expanded' : ''}`}>
                                  <button
                                    className="thinking-toggle"
                                    onClick={() => setExpandedThinking(prev => {
                                      const next = new Set(prev)
                                      if (next.has(msg.id)) next.delete(msg.id)
                                      else next.add(msg.id)
                                      return next
                                    })}
                                  >
                                    <span className="thinking-icon">💭</span>
                                    <span>Рассуждение</span>
                                    <span className="thinking-chevron">›</span>
                                  </button>
                                  <div className="thinking-content">
                                    <MarkdownRenderer content={msg.thinking} />
                                  </div>
                                </div>
                              )}
                              <MarkdownRenderer content={msg.content} isStreaming={isLastAssistant} />
                            </div>
                          </div>
                          <div className={`message-footer ${msg.role} ${msg.role === 'user' || revealedMeta.has(msg.id) ? 'visible' : ''}`}>
                            {msg.role === 'user' || revealedMeta.has(msg.id) ? renderMeta(msg) : null}
                          </div>
                        </div>
                      )
                    })}
                    <div ref={chatEndRef} />
                  </div>
                </div>

                {compactionNotice && (
                  <div className="compaction-banner">
                    <span className="compaction-icon">🗜️</span>
                    <span className="compaction-text">{compactionNotice}</span>
                  </div>
                )}

                <div className="bottom-input">
                  {renderInput()}
                </div>
              </div>
            )
          }
          return <PageTransition pageKey={pageKey}><Suspense fallback={<PageFallback />}>{body}</Suspense></PageTransition>
        })()}
          </main>
          <WidgetDropZone
            side="right"
            widgets={layout.right}
            departments={sidebarDepartments}
            onRemove={removeWidget}
            isDragging={!!activeDragId}
            onDepartmentClick={(id) => setView({ type: 'otdel', id })}
            activeOtdelId={view.type === 'otdel' ? view.id : null}
            wsOn={wsOn}
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
