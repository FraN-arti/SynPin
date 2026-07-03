/**
 * ChatView — main chat view with message list, drag-drop image overlay,
 * thinking blocks, tool timeline, and input form (textarea + attach +
 * emoji + submit). Self-contained: receives all state and callbacks
 * via props, owns no global state.
 *
 * Extracted from App.tsx in v0.5.1.55 to keep the composition root
 * small.
 */

import { useState, useRef, useCallback, useMemo, type FormEvent, type ChangeEvent, type KeyboardEvent, type ClipboardEvent, type DragEvent } from 'react'
import { MarkdownRenderer } from './MarkdownRenderer'
import { EmojiPicker } from './EmojiPicker'
import { ImageAttachment, fileToAttachment, type ImageAttachment as ImageAttachmentType } from './ImageAttachment'
import { ToolTimeline, TOOL_DISPLAY_NAMES } from './ToolTimeline'
import type { Message } from './chatTypes'

export interface ChatViewProps {
  messages: Message[]
  isTyping: boolean
  revealedMeta: Set<string>
  expandedThinking: Set<string>
  compactionNotice: string | null
  // refs
  messagesContainerRef: React.Ref<HTMLDivElement | null>
  chatEndRef: React.Ref<HTMLDivElement | null>
  textareaRef: React.RefObject<HTMLTextAreaElement | null>
  attachRef: React.RefObject<{ openPicker: () => void } | null>
  // input
  input: string
  attachments: ImageAttachmentType[]
  // setters
  setInput: (v: string) => void
  setAttachments: (a: ImageAttachmentType[] | ((prev: ImageAttachmentType[]) => ImageAttachmentType[])) => void
  setExpandedThinking: (s: Set<string> | ((prev: Set<string>) => Set<string>)) => void
  // callbacks
  onSubmit: (e: FormEvent) => Promise<void>
  onKeyDown: (e: KeyboardEvent<HTMLTextAreaElement>) => void
  synpinLogo: string
}

function formatTime(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

function renderMeta(msg: Message) {
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

export function ChatView(props: ChatViewProps) {
  const {
    messages, isTyping, revealedMeta, expandedThinking, compactionNotice,
    messagesContainerRef, chatEndRef, textareaRef, attachRef,
    input, attachments,
    setInput, setAttachments, setExpandedThinking,
    onSubmit, onKeyDown, synpinLogo,
  } = props

  // Local drag-state for image drop overlay
  const [dragOver, setDragOver] = useState(false)
  const dragCounterRef = useRef(0)

  const handleEmojiSelect = useCallback((emoji: string) => {
    const el = textareaRef.current
    if (!el) return
    const start = el.selectionStart
    const end = el.selectionEnd
    const newValue = input.slice(0, start) + emoji + input.slice(end)
    setInput(newValue)
    requestAnimationFrame(() => {
      el.focus()
      el.selectionStart = el.selectionEnd = start + emoji.length
    })
  }, [input, setInput, textareaRef])

  const handleInputChange = useCallback((e: ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 150) + 'px'
  }, [setInput])

  const handleAddImages = useCallback(async (files: File[]) => {
    const newAttachments = await Promise.all(files.map(fileToAttachment))
    setAttachments(prev => [...prev, ...newAttachments])
  }, [setAttachments])

  const handleRemoveImage = useCallback((id: string) => {
    setAttachments(prev => prev.filter(a => a.id !== id))
  }, [setAttachments])

  const handlePaste = useCallback((e: ClipboardEvent) => {
    const images = (e as any).clipboardData ? extractImagesFromPaste(e) : []
    if (images.length > 0) {
      e.preventDefault()
      handleAddImages(images)
    }
  }, [handleAddImages])

  const handleDragEnter = useCallback((e: DragEvent) => {
    e.preventDefault()
    dragCounterRef.current++
    const types = Array.from(e.dataTransfer.types)
    if (types.includes('Files') || types.includes('text/plain')) {
      setDragOver(true)
    }
  }, [])

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault()
    dragCounterRef.current--
    if (dragCounterRef.current === 0) setDragOver(false)
  }, [])

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault()
  }, [])

  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault()
    dragCounterRef.current = 0
    setDragOver(false)
    const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'))
    if (files.length > 0) handleAddImages(files)
  }, [handleAddImages])

  // Stable handler that returns a memoized callback for thinking toggle
  const toggleThinking = useCallback((id: string) => {
    setExpandedThinking(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [setExpandedThinking])

  const renderInput = useMemo(() => (
    <form onSubmit={onSubmit} className="input-container">
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
          onChange={handleInputChange}
          onKeyDown={onKeyDown}
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
  ), [attachments, handleAddImages, handleRemoveImage, handleEmojiSelect, handleInputChange, handlePaste, input, isTyping, onSubmit, onKeyDown, textareaRef, attachRef])

  return (
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
                          onClick={() => toggleThinking(msg.id)}
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
        {renderInput}
      </div>
    </div>
  )
}

// Local helper — extract images from clipboard event. ImageAttachment
// exports a similar function but we re-use it via the event's clipboardData
// to avoid importing the helper directly (kept simple here).
function extractImagesFromPaste(e: ClipboardEvent): File[] {
  const items = e.clipboardData?.items
  if (!items) return []
  const files: File[] = []
  for (let i = 0; i < items.length; i++) {
    const item = items[i]
    if (!item) continue
    if (item.type.startsWith('image/')) {
      const file = item.getAsFile()
      if (file) files.push(file)
    }
  }
  return files
}