import { useMemo } from 'react'
import { renderMarkdown } from '../lib/markdown'

interface MarkdownRendererProps {
  content: string
  isStreaming?: boolean
}

export function MarkdownRenderer({ content, isStreaming }: MarkdownRendererProps) {
  const html = useMemo(() => {
    if (!content) return ''
    return renderMarkdown(content)
  }, [content])

  // Empty message — show typing dots
  if (!content) {
    return (
      <span className="typing-dots bubble">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
      </span>
    )
  }

  // During streaming, render raw text to avoid broken HTML from incomplete markdown
  if (isStreaming) {
    return <span className="raw-text">{content}</span>
  }

  return (
    <div
      className="markdown-body"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}
