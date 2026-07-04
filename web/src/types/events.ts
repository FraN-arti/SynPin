/**
 * Event shape — matches backend core/synpin/events/bus.py:Event dataclass.
 * One event = one noteworthy thing that happened (main agent replied,
 * otdel completed, cron fired, etc). Frontend shows them as toasts.
 */
export type EventLevel = 'info' | 'success' | 'warning' | 'error'
export type EventSource = 'main_agent' | 'agent' | 'otdel' | 'cron' | 'system'

export interface AppEvent {
  id: string
  title: string
  body: string
  level: EventLevel
  source: EventSource
  source_ref: string | null
  created_at: number
  read_at: number | null
}

export interface InAppSettings {
  enabled: boolean
  auto_fade_seconds: number
  max_visible: number
}