/**
 * ChatInput — input form (textarea + attach button + emoji + submit).
 * Used both inside ChatView (full chat) and standalone in empty state.
 */

import { forwardRef, type FormEvent, type ChangeEvent, type KeyboardEvent, type ClipboardEvent, type DragEvent } from 'react'
import { EmojiPicker } from './EmojiPicker'
import { ImageAttachment, fileToAttachment, type ImageAttachment as ImageAttachmentType } from './ImageAttachment'

export interface ChatInputProps {
  input: string
  attachments: ImageAttachmentType[]
  isTyping: boolean
  setInput: (v: string) => void
  setAttachments: (a: ImageAttachmentType[] | ((prev: ImageAttachmentType[]) => ImageAttachmentType[])) => void
  onSubmit: (e: FormEvent) => Promise<void>
  onKeyDown: (e: KeyboardEvent<HTMLTextAreaElement>) => void
  textareaRef: React.RefObject<HTMLTextAreaElement | null>
  attachRef: React.RefObject<{ openPicker: () => void } | null>
  // Drag-drop handlers (only needed in ChatView; pass undefined for empty state)
  onDragEnter?: (e: DragEvent) => void
  onDragLeave?: (e: DragEvent) => void
  onDragOver?: (e: DragEvent) => void
  onDrop?: (e: DragEvent) => void
}

export const ChatInput = forwardRef<HTMLDivElement, ChatInputProps>(function ChatInput(props, _ref) {
  const {
    input, attachments, isTyping,
    setInput, setAttachments,
    onSubmit, onKeyDown, textareaRef, attachRef,
  } = props

  const handleEmojiSelect = (emoji: string) => {
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
  }

  const handleInputChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 150) + 'px'
  }

  const handleAddImages = async (files: File[]) => {
    const newAttachments = await Promise.all(files.map(fileToAttachment))
    setAttachments(prev => [...prev, ...newAttachments])
  }

  const handleRemoveImage = (id: string) => {
    setAttachments(prev => prev.filter(a => a.id !== id))
  }

  const handlePaste = (e: ClipboardEvent) => {
    const items = e.clipboardData?.items
    if (!items) return
    const files: File[] = []
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (!item) continue
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile()
        if (file) files.push(file)
      }
    }
    if (files.length > 0) {
      e.preventDefault()
      handleAddImages(files)
    }
  }

  return (
    <form onSubmit={onSubmit} className="input-container">
      <ImageAttachment
        ref={attachRef as any}
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
  )
})