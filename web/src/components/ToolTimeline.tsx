/**
 * ToolTimeline — compact row of tool badges shown above assistant messages
 * during streaming. Same visual used in main chat (App.tsx) and otdel chat
 * (OtdelChatView.tsx). Status icons: ⏳ running, ✓ completed, ✗ error.
 *
 * Hidden tools (memory_read, memory_write) are filtered upstream — this
 * component assumes it only sees user-visible tools.
 */

export interface ToolCall {
  id: string
  name: string
  params: Record<string, unknown>
  status: 'running' | 'completed' | 'error'
  result?: string
  error?: string
}

export interface ToolTimelineProps {
  tools: ToolCall[]
  isLive: boolean
  toolNames: Record<string, string>
}

export function ToolTimeline({ tools, toolNames }: ToolTimelineProps) {
  return (
    <div className="tool-badges-row">
      {tools.map((tc, idx) => (
        <span
          key={tc.id || `tc-${idx}`}
          className={`tool-mini-badge ${tc.status}`}
          title={`${tc.name}: ${tc.result || tc.error || ''}`}
        >
          {tc.status === 'running' ? '⏳' : tc.status === 'completed' ? '✓' : '✗'} {toolNames[tc.name] || tc.name}
        </span>
      ))}
    </div>
  )
}

// Tools hidden from UI (run silently in background). Used by App.tsx and
// OtdelChatView.tsx when filtering tool_start/tool_end events.
export const HIDDEN_TOOLS = new Set(['memory_read', 'memory_write'])

// Display name overrides for known tool names. Anything missing falls back
// to the raw name in ToolTimeline.
export const TOOL_DISPLAY_NAMES: Record<string, string> = {
  terminal: 'Терминал',
  file_read: 'Чтение файла',
  file_write: 'Запись файла',
  search_files: 'Поиск файлов',
  web_search: 'Поиск в интернете',
  code_exec: 'Python',
  // memory tools hidden from UI — run silently
}