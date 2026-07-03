/**
 * MarkdownRenderer — renders assistant chat messages as HTML.
 *
 * Two responsibilities beyond raw markdown:
 *  1. **Empty content → typing indicator.** When `content` is empty
 *     (assistant placeholder bubble, no text yet) we render the three
 *     vertical thinking bars from chat.css. Bars are CSS-driven
 *     (`typing-bar-scale` keyframe), no JS.
 *  2. **Copy buttons on code blocks.** After markdown renders, we walk
 *     every `<pre>` in the resulting DOM and append a "Copy" button
 *     that copies the code text to clipboard with a 1.5s "Copied!"
 *     confirmation. Pure DOM enhancement — doesn't touch the markdown
 *     pipeline.
 *
 * Why useEffect + DOM mutation instead of a marked extension:
 *   - The renderer's `code` callback in lib/markdown.ts outputs HTML
 *     strings, which then go through `dangerouslySetInnerHTML`. To
 *     inject a button as React we'd have to thread state through a
 *     second pass and re-render — overcomplicated for a UI nicety.
 *   - Mutation in useEffect runs once per content change and is the
 *     same pattern ChatGPT/Claude use for their copy buttons.
 *
 * Hook-order note: ALL hooks (useMemo, useEffect, useRef) run before
 * any conditional return. Don't early-return before useEffect — React
 * will throw "Rendered more hooks than during the previous render"
 * when content goes from empty to non-empty (empty path = 0 effects,
 * non-empty path = 1 effect).
 */

import { useEffect, useMemo, useRef } from 'react'
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

  const containerRef = useRef<HTMLDivElement>(null)

  // Wire up copy buttons on every <pre> after render. Runs even when
  // content is empty (no-op since the empty branch returns early
  // below — but the hook call itself is unconditional).
  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const blocks = container.querySelectorAll<HTMLPreElement>('pre')
    blocks.forEach((pre) => {
      // Idempotent: skip if a button already exists (StrictMode runs
      // effects twice in dev).
      if (pre.querySelector('.md-copy-btn')) return
      const btn = document.createElement('button')
      btn.type = 'button'
      btn.className = 'md-copy-btn'
      btn.textContent = 'Copy'
      btn.title = 'Copy code to clipboard'
      btn.addEventListener('click', async () => {
        // Get the raw text — pre > code, fall back to pre.textContent.
        const code = pre.querySelector('code')
        const text = code ? code.textContent ?? '' : pre.textContent ?? ''
        try {
          await navigator.clipboard.writeText(text)
          btn.textContent = 'Copied!'
          btn.classList.add('md-copy-btn--success')
          setTimeout(() => {
            btn.textContent = 'Copy'
            btn.classList.remove('md-copy-btn--success')
          }, 1500)
        } catch {
          // Clipboard API blocked (insecure context, permission denied).
          // Fall back to legacy execCommand.
          const ta = document.createElement('textarea')
          ta.value = text
          ta.style.position = 'fixed'
          ta.style.left = '-9999px'
          document.body.appendChild(ta)
          ta.select()
          try {
            document.execCommand('copy')
            btn.textContent = 'Copied!'
            btn.classList.add('md-copy-btn--success')
            setTimeout(() => {
              btn.textContent = 'Copy'
              btn.classList.remove('md-copy-btn--success')
            }, 1500)
          } catch {
            btn.textContent = 'Failed'
          }
          document.body.removeChild(ta)
        }
      })
      pre.appendChild(btn)
    })
  }, [html])

  // Empty content → typing dots (now vertical bars, see chat.css).
  if (!content) {
    return (
      <span className="typing-dots bubble">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
      </span>
    )
  }

  // During streaming, render raw text to avoid broken HTML from incomplete markdown.
  if (isStreaming) {
    return <span className="raw-text">{content}</span>
  }

  return (
    <div
      ref={containerRef}
      className="markdown-body"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  )
}