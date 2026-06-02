import { marked } from 'marked'
import hljs from 'highlight.js'

// Configure marked with a custom renderer for code highlighting
const renderer = new marked.Renderer()

renderer.code = function(token) {
  const { text, lang } = token
  if (lang && hljs.getLanguage(lang)) {
    try {
      const highlighted = hljs.highlight(text, { language: lang }).value
      return `<pre><code class="hljs language-${lang}">${highlighted}</code></pre>`
    } catch {
      // fall through
    }
  }
  // Auto-highlight if no language specified
  try {
    const highlighted = hljs.highlightAuto(text).value
    return `<pre><code class="hljs">${highlighted}</code></pre>`
  } catch {
    return `<pre><code>${text}</code></pre>`
  }
}

marked.setOptions({
  renderer,
  breaks: true,
  gfm: true,
})

export function renderMarkdown(text: string): string {
  return marked.parse(text, { async: false }) as string
}
