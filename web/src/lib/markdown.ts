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

// === Custom color spans ===
// Syntax: @@gold важно @@, @@sea-breeze новое @@, @@orange вним @@
// Renders to <span class="md-color md-color-{slug}">text</span>.
//
// Why pre/post-processing instead of a marked inline extension:
// marked's inlineText tokenizer gobbles any run of "ordinary" chars up
// to the next stop char (`<`, `!`, `[`, `` ` ``, `*`, `_`, `\`). Since
// `@` is not a stop char, inlineText eats `@@...` whole before our
// extension gets a turn. The cleanest fix is to substitute the spans
// with sentinel placeholders before parse, then restore them after —
// marked passes the placeholders through as text and never touches
// them.
const COLOR_TOKEN_RE = /@@([a-z][a-z0-9-]*)((?:\s|[^\s@])*?)@@/gi
// Sentinel format: U+0000 zero-width control + payload + U+0000.
// Real text never contains NUL — if it ever did, escape it first.
const SENTINEL_OPEN = '\u0000CS:'
const SENTINEL_CLOSE = '\u0000'

function escapeNul(text: string): string {
  return text.replace(/\u0000/g, '\uFFFD')
}

function unescapeNul(text: string): string {
  return text.replace(/\uFFFD/g, '\u0000')
}

// Returns { placeholders, restore(html) }.
// placeholders: map from sentinel -> HTML span.
// restore: replace sentinels in marked output with their spans.
function extractColorSpans(text: string): { text: string; restore: (html: string) => string } {
  const placeholders: { sentinel: string; html: string }[] = []
  const replaced = escapeNul(text).replace(COLOR_TOKEN_RE, (_match, rawName: string, rawBody: string) => {
    const slug = rawName.toLowerCase()
    // Escape HTML in body — never trust LLM output
    const safe = rawBody
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
    const html = `<span class="md-color md-color-${slug}">${safe}</span>`
    const sentinel = `${SENTINEL_OPEN}${placeholders.length}${SENTINEL_CLOSE}`
    placeholders.push({ sentinel, html })
    return sentinel
  })
  return {
    text: replaced,
    restore: (html: string) => {
      let out = html
      for (const { sentinel, html: span } of placeholders) {
        out = out.split(sentinel).join(span)
      }
      return unescapeNul(out)
    },
  }
}

marked.setOptions({
  renderer,
  breaks: true,
  gfm: true,
})

export function renderMarkdown(text: string): string {
  if (!text) return ''
  const { text: prepared, restore } = extractColorSpans(text)
  const html = marked.parse(prepared, { async: false }) as string
  return restore(html)
}
