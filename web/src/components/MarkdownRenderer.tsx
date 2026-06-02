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
