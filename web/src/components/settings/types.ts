/**
 * Shared types and constants for Settings sections.
 * Extracted from SettingsPage.tsx to enable modular section files.
 */

// ── Tab definitions ────────────────────────────────────────────────

export type Tab = 'general' | 'agents' | 'providers' | 'memory' | 'channels' | 'departments' | 'skills' | 'connections' | 'kanban' | 'deadlines' | 'projects' | 'widgets' | 'cron' | 'tools'

export interface TabDef {
  id: Tab
  label: string
}

export const SYSTEM_TABS: TabDef[] = [
  { id: 'general', label: 'Общие' },
  { id: 'agents', label: 'Агенты' },
  { id: 'providers', label: 'Провайдеры' },
  { id: 'memory', label: 'Память' },
  { id: 'tools', label: 'Инструменты' },
  { id: 'skills', label: 'Скиллы' },
  { id: 'cron', label: 'Крон' },
]

export const SPACE_TABS: TabDef[] = [
  { id: 'channels', label: 'Каналы' },
  { id: 'connections', label: 'Связи' },
  { id: 'departments', label: 'Отделы' },
  { id: 'widgets', label: 'Виджеты' },
]

export const SECTION_INFO: Record<Tab, { title: string; description: string }> = {
  general: { title: 'Общие настройки', description: 'Тема, язык, сервер и статистика' },
  agents: { title: 'Агенты', description: 'Управление AI-агентами и их параметрами' },
  providers: { title: 'Провайдеры', description: 'Подключение LLM-провайдеров' },
  memory: { title: 'Память', description: 'Управление памятью системы' },
  channels: { title: 'Каналы', description: 'Подключение мессенджеров и каналов' },
  departments: { title: 'Отделы', description: 'Структура организации и роли' },
  skills: { title: 'Скиллы', description: 'База знаний и процедур' },
  connections: { title: 'Связи', description: 'Структура и эскалации между отделами' },
  kanban: { title: 'Канбан', description: 'Настройки доски задач' },
  projects: { title: 'Проекты', description: 'Управление проектами и их настройки' },
  deadlines: { title: 'Дедлайны', description: 'Настройки системы дедлайнов' },
  widgets: { title: 'Виджеты', description: 'Управление виджетами на главной панели' },
  cron: { title: 'Крон-задачи', description: 'Расписание, лимиты и проактивность' },
  tools: { title: 'Инструменты', description: 'Управление инструментами агентов: включение и области доступа' },
}

// Tabs that can be dragged to widget zones
export const DRAGGABLE_TABS = new Set(['departments', 'kanban'])

// ── Data interfaces ────────────────────────────────────────────────

export interface OverviewStats {
  agents: number
  agents_internal: number
  agents_external: number
  total_messages: number
  total_sessions: number
  config_files: number
  uptime: string
}

export interface SettingsData {
  server: {
    host: string
    port: number
    dev_port: number
    cors_origins: string[]
    rate_limit: { enabled: boolean; requests_per_minute: number }
  }
  ui: {
    theme: string
    language: string
    border_radius: number
    sidebar: { default_open: boolean; show_icons: boolean }
    chat: {
      show_metadata: boolean
      metadata_delay_ms: number
      max_message_length: number
      auto_scroll: boolean
      streaming_border: boolean
    }
  }
  models: {
    vision: string
    image_gen: string
    web_search: string
    web_extract: string
    summarization: string
  }
  feed: {
    enabled: boolean
    max_items: number
    time_range: string
    filters: {
      new_ideas: boolean
      task_updates: boolean
      memory_updates: boolean
      board_updates: boolean
    }
    sort: string
    group_by: string
  }
  sessions: {
    auto_reset_enabled: boolean
    auto_reset_mode: 'daily' | 'weekly' | 'never'
    auto_reset_time: string
    max_history: number
    archive_on_reset: boolean
  }
}

export interface AgentData {
  slug: string
  agentid: string
  name: string
  role: string
  department: string
  model: string
  provider: string | null
  skills: string[]
  tools: string[]
  enabled: boolean
  is_primary?: boolean
  description: string
  tone: string
  style: string
  traits: string[]
  system_prompt: string
  max_iterations: number
  temperature: number
  max_tokens: number
  context_window: number
  memory: Record<string, unknown>
  is_external?: boolean
}

export interface ExternalAgentData {
  slug: string
  agentid: string
  name: string
  type: string
  description: string
  enabled: boolean
  is_primary?: boolean
  role: string
  role_name: string
  department: string
  department_name: string
  available: boolean
  models: string[]
  chat_url: string
  icon_letter: string
  color: string
  is_external: true
}

export interface ApiProvider {
  name: string
  type: string
  base_url: string
  api_key: string
  models: string[]
  enabled: boolean
  _testStatus?: 'ok' | 'error' | null
}

export interface DepartmentData {
  departmentsid: string
  name: string
  description: string
  color: string
  head_agent: string
  agents: string[]
}

export interface RoleData {
  roleid: string
  name: string
  description: string
  permissions: string[]
}

export interface OtdelData {
  otdelid: string
  name: string
  description: string
  department: string
  head_agent: string
  workers: string[]
  channel_id: string
  enabled: boolean
}

// ── Helpers ────────────────────────────────────────────────────────

export function pluralize(n: number, one: string, few: string, many: string): string {
  const abs = Math.abs(n) % 100
  const last = abs % 10
  if (abs > 10 && abs < 20) return many
  if (last > 1 && last < 5) return few
  if (last === 1) return one
  return many
}
