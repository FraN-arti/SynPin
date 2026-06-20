import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { EmojiPicker } from './EmojiPicker'
import { MarkdownRenderer } from './MarkdownRenderer'
import { useChatScroll } from '../hooks/useChatScroll'
import { ImageAttachment, fileToAttachment, extractImagesFromPaste, type ImageAttachment as ImageAttachmentType } from './ImageAttachment'

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
  images?: string[]  // base64 data URLs of attached images
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
  const [loading, setLoading] = useState(true)
  const [input, setInput] = useState('')
  const [attachments, setAttachments] = useState<ImageAttachmentType[]>([])
  const [agents, setAgents] = useState<Agent[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [sending, setSending] = useState(false)
  const [thinkingAgents, setThinkingAgents] = useState<Map<string, string>>(new Map()) // slug → name
  const [compacting, setCompacting] = useState<{ before: number; after: number } | null>(null)
  const [workerStatuses, setWorkerStatuses] = useState<Map<string, 'idle' | 'thinking' | 'done'>>(new Map())
  const [showWorkers, setShowWorkers] = useState(false)
  const { sentinelRef: messagesEndRef } = useChatScroll(messages)
  const attachRef = useRef<{ openPicker: () => void }>(null)

  // ── Stuck state protection ──────────────────────────────────────
  const clearStuckState = useCallback(() => {
    setSending(false)
    setThinkingAgents(new Map())
    setWorkerStatuses(new Map())
    // Remove empty assistant placeholders
    setMessages(prev => prev.filter(m => !(m.role === 'assistant' && !m.content && !m.streaming)))
  }, [])

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
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/otdels/${otdel.otdelid}/chat/history?limit=20`)
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
    setLoading(false)
  }, [otdel.otdelid])

  useEffect(() => {
    loadHistory()
  }, [loadHistory])

  // Periodic history refresh — catch missed WS messages
  useEffect(() => {
    const interval = setInterval(() => {
      if (!sending) return // Only refresh when idle
      loadHistory()
    }, 10000) // Check every 10 seconds when sending (fallback for missed WS)
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
        // head_delegate sends workers as an ARRAY of {slug, task} objects
        const workersParam = params?.workers || []
        const taskForAll = params?.task || params?.instruction || ''
        const workersList = Array.isArray(workersParam) && workersParam.length > 0
          ? workersParam
          : [{ slug: params?.worker || params?.target || '', task: taskForAll }]
        for (const w of workersList) {
          if (!w?.slug) continue
          // Track worker status only
          setWorkerStatuses(prev => new Map(prev).set(w.slug, 'thinking'))
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
        } else {
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
    if (!input.trim() && attachments.length === 0) return

    // If stuck, clear it first
    if (sending) {
      clearStuckState()
    }

    const text = input.trim()
    const userImages = attachments.map(a => a.dataUrl)
    setInput('')
    setAttachments([])
    setSending(true)
    // Reset worker statuses for new round
    setWorkerStatuses(new Map())

    const textarea = document.querySelector('.otdel-bottom-input .chat-textarea') as HTMLTextAreaElement
    if (textarea) textarea.style.height = 'auto'

    // Send via WebSocket — backend will push the message back with its own id
    wsSend('otdel:send', {
      otdel_id: otdel.otdelid,
      message: text || (userImages.length > 0 ? `[Изображение${userImages.length > 1 ? ` (${userImages.length})` : ''}]` : ''),
      images: userImages.length > 0 ? userImages : undefined,
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
    const types = Array.from(e.dataTransfer.types)
    if (types.includes('Files') || types.includes('text/plain')) setDragOver(true)
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


  const isLeftSide = (msg: ChatMessage) => {
    return msg.role === 'user' || msg.sender === 'user' || msg.is_head === true
  }

  return (
    <div
      className="otdel-chat-view"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      style={{ position: 'relative' }}
    >
      <div className={`chat-drop-overlay ${dragOver ? 'active' : ''}`}>
        <div className="chat-drop-overlay-inner">
          <div className="chat-drop-overlay-icon">↓</div>
          <div className="chat-drop-overlay-text">Перетащите изображение</div>
          <div className="chat-drop-overlay-hint">PNG, JPEG, WebP, GIF — до 10 МБ</div>
        </div>
      </div>
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

      {/* Workers Toggle */}
      <button
        className="otdel-workers-toggle"
        onClick={() => setShowWorkers(v => !v)}
      >
        <span className={`toggle-arrow ${showWorkers ? 'open' : ''}`}>▼</span>
        {showWorkers ? 'Скрыть сотрудников' : 'Показать сотрудников'}
      </button>

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
          <div className={`otdel-worker-status-bar${showWorkers ? '' : ' collapsed'}`}>
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

      {/* Messages */}
      <div className="otdel-messages-area">
        {loading ? (
          <div className="loading-spinner">
            <div className="loading-ring" />
            <span>Загрузка чата...</span>
          </div>
        ) : messages.length === 0 ? (
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
                      {msg.images && msg.images.length > 0 && (
                        <div className="message-images">
                          {msg.images.map((src, i) => (
                            <img key={i} src={src} alt={`Изображение ${i + 1}`} className="message-image" />
                          ))}
                        </div>
                      )}
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
        <ImageAttachment
          ref={attachRef}
          images={attachments}
          onAdd={handleAddImages}
          onRemove={handleRemoveImage}
          disabled={sending}
        />
        <div className="input-bar">
          <button
            type="button"
            className="attach-btn"
            onClick={() => attachRef.current?.openPicker()}
            disabled={sending}
            title="Прикрепить изображение"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
            </svg>
          </button>
          <EmojiPicker onSelect={handleEmojiSelect} />
          <textarea
            className="chat-textarea"
            placeholder={compacting ? 'Компакция истории...' : sending ? 'Агенты работают... (Enter — отправить ещё)' : attachments.length > 0 ? 'Опиши что на картинке...' : 'Спроси что-нибудь...'}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            onPaste={handlePaste}
            rows={1}
          />
          <button className={`send-btn ${sending ? 'stop-mode' : ''}`}
            onClick={handleSend}
            disabled={!sending && !input.trim() && attachments.length === 0}
            title={sending ? 'Остановить' : 'Отправить'}
          >
            {sending ? (
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="6" width="12" height="12" rx="2" />
              </svg>
            ) : '→'}
          </button>
        </div>
      </div>
    </div>
  )
}
