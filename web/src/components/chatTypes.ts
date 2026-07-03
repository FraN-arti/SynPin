/**
 * Shared chat types used by App.tsx, Sidebar.tsx, ToolTimeline.tsx,
 * and any future chat-related components.
 */

import type { ToolCall } from './ToolTimeline'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  thinking?: string  // reasoning/thinking content (<think> tags or similar)
  timestamp: Date
  model?: string
  agent_name?: string
  prompt_tokens?: number
  completion_tokens?: number
  tools?: ToolCall[]
  images?: string[]  // base64 data URLs of attached images
}