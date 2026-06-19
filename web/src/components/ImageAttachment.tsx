/**
 * ImageAttachment — preview strip + file picker for chat images.
 *
 * Supports: 📎 button click, drag-n-drop on chat area, Ctrl+V paste.
 * Exposes imperative `openPicker()` via ref for external trigger.
 */

import { useRef, useCallback, forwardRef, useImperativeHandle } from 'react'

export interface ImageAttachment {
  id: string
  dataUrl: string   // base64 data URL — sent to backend
  preview: string   // same as dataUrl for preview (could be a blob URL)
  name: string      // original filename
  size: number      // bytes
}

interface ImageAttachmentProps {
  images: ImageAttachment[]
  onAdd: (files: File[]) => void
  onRemove: (id: string) => void
  disabled?: boolean
}

const MAX_FILE_SIZE = 10 * 1024 * 1024 // 10 MB per image
const ACCEPTED_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif']

export const ImageAttachment = forwardRef<{ openPicker: () => void }, ImageAttachmentProps>(
  function ImageAttachment({ images, onAdd, onRemove, disabled }, ref) {
    const inputRef = useRef<HTMLInputElement>(null)

    useImperativeHandle(ref, () => ({
      openPicker: () => inputRef.current?.click(),
    }))

    const processFiles = useCallback((fileList: FileList | File[]) => {
      const files = Array.from(fileList).filter(f => {
        if (!ACCEPTED_TYPES.includes(f.type)) return false
        if (f.size > MAX_FILE_SIZE) return false
        return true
      })
      if (files.length > 0) onAdd(files)
    }, [onAdd])

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files) processFiles(e.target.files)
      // Reset so same file can be re-selected
      e.target.value = ''
    }

    if (images.length === 0) return (
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_TYPES.join(',')}
        multiple
        onChange={handleFileChange}
        style={{ display: 'none' }}
      />
    )

    return (
      <div className="image-attachments">
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_TYPES.join(',')}
          multiple
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
        {images.map(img => (
          <div key={img.id} className="image-attachment-thumb">
            <img src={img.preview} alt={img.name} className="image-attachment-img" />
            <button
              className="image-attachment-remove"
              onClick={() => onRemove(img.id)}
              disabled={disabled}
              title={`Удалить ${img.name}`}
              type="button"
            >
              ×
            </button>
            <span className="image-attachment-size">
              {img.size > 1024 * 1024
                ? `${(img.size / 1024 / 1024).toFixed(1)} MB`
                : `${Math.round(img.size / 1024)} KB`}
            </span>
          </div>
        ))}
      </div>
    )
  }
)

// ── Helpers ───────────────────────────────────────────────────────

let _idCounter = 0

/** Convert File → ImageAttachment (async: reads as data URL). */
export function fileToAttachment(file: File): Promise<ImageAttachment> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      resolve({
        id: `img-${Date.now()}-${_idCounter++}`,
        dataUrl: reader.result as string,
        preview: reader.result as string,
        name: file.name,
        size: file.size,
      })
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

/** Extract images from a paste event (Ctrl+V). */
export function extractImagesFromPaste(e: React.ClipboardEvent): File[] {
  const files: File[] = []
  // Check clipboardData.items for image types
  for (let i = 0; i < e.clipboardData.items.length; i++) {
    const item = e.clipboardData.items[i]
    if (item.type.startsWith('image/')) {
      const file = item.getAsFile()
      if (file) files.push(file)
    }
  }
  return files
}
