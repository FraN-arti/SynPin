/**
 * Sidebar — agent list (primary pinned, search-filtered, star to set primary),
 * navigation footer (Projects, Deadlines, Connections, Kanban, Settings),
 * and live version bar (auto-updated via WebSocket from server).
 *
 * Receives all data + callbacks as props — keeps App.tsx from being a god
 * component. AgentConfig shape is duplicated here (not imported) to keep
 * this module's surface independent from App.tsx internals.
 */

import type { Message } from './chatTypes'
import { API_BASE } from '../config'

export type View =
  | { type: 'chat' }
  | { type: 'otdel'; id: string }
  | { type: 'settings' }
  | { type: 'kanban' }
  | { type: 'connections' }
  | { type: 'deadlines' }
  | { type: 'projects' }
  | { type: 'setup' }

export interface AgentConfig {
  slug: string
  agentid: string
  name: string
  role: string
  role_name: string
  department: string
  department_name: string
  model: string
  provider: string | null
  system_prompt: string
  description: string
  tone: string
  style: string
  traits: string[]
  tools: string[]
  temperature: number
  max_tokens: number
  enabled: boolean
  is_primary?: boolean
  is_external?: boolean
  type?: string
}

export interface SidebarProps {
  open: boolean
  ready: boolean
  agents: AgentConfig[]
  primarySlug: string
  activeAgent: AgentConfig | null
  view: View
  serverVersion: string
  // Setters
  setActiveAgent: (a: AgentConfig | null) => void
  setMessages: (m: Message[] | null | ((prev: Message[] | null) => Message[] | null)) => void
  setView: (v: View) => void
  setPrimarySlug: (s: string) => void
  setAvailableAgents: (a: AgentConfig[] | ((prev: AgentConfig[]) => AgentConfig[])) => void
  setAgentSearch: (s: string) => void
  // Internal state
  agentSearch: string
}

export function Sidebar({
  open, ready, agents, primarySlug, activeAgent, view, serverVersion,
  setActiveAgent, setMessages, setView, setPrimarySlug, setAvailableAgents,
  setAgentSearch, agentSearch,
}: SidebarProps) {
  const primary = primarySlug ? agents.find(a => a.slug === primarySlug) : null

  const handleAgentClick = (agent: AgentConfig) => {
    if (activeAgent?.slug !== agent.slug) {
      setActiveAgent(agent)
      setMessages([])
      setView({ type: 'chat' })
    } else if (view.type !== 'chat') {
      setView({ type: 'chat' })
    }
    setAgentSearch('')
  }

  const togglePrimary = async (slug: string) => {
    const newPrimary = primarySlug === slug ? '' : slug
    await fetch(`${API_BASE}/api/config/primary-agent`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: newPrimary }),
    })
    setPrimarySlug(newPrimary)
    // Sync is_primary in agents list
    setAvailableAgents(prev => prev.map(a => ({ ...a, is_primary: a.slug === newPrimary })))
  }

  const filteredAgents = agents
    .filter(agent => agent.slug !== primarySlug)
    .filter(agent => {
      if (!agentSearch.trim()) return true
      const q = agentSearch.toLowerCase()
      return (
        agent.name.toLowerCase().includes(q) ||
        (agent.role_name || '').toLowerCase().includes(q) ||
        (agent.type || '').toLowerCase().includes(q)
      )
    })

  return (
    <aside className={`sidebar ${open && ready ? 'open' : ''}`}>
      <div className="sidebar-content">
        {/* Primary Agent — pinned above search */}
        {primary && (
          <div className="primary-agent">
            <button
              className={`agent-list-item ${activeAgent?.slug === primary.slug ? 'active' : ''}`}
              onClick={() => handleAgentClick(primary)}
            >
              <span className="agent-list-avatar" style={{ background: primary.is_external ? '#f97316' : '#6b7280' }}>
                {primary.is_external ? 'H' : primary.name[0]}
              </span>
              <div className="agent-list-info">
                <span className="agent-list-name">
                  {primary.name}
                  {primary.is_external && <span className="agent-badge extern">extern</span>}
                </span>
                <span className="agent-list-role">{primary.role_name || primary.type}</span>
              </div>
              <span
                className="star-toggle active"
                title="Снять с главного"
                onClick={(e) => { e.stopPropagation(); togglePrimary(primary.slug) }}
              >★</span>
            </button>
          </div>
        )}

        {/* Agent Search */}
        <div className="agent-search">
          <input
            className="agent-search-input"
            type="text"
            placeholder="Поиск агента..."
            value={agentSearch}
            onChange={(e) => setAgentSearch(e.target.value)}
          />
        </div>

        {/* Agent List */}
        <div className={`agent-list ${filteredAgents.length > 3 ? 'has-overflow' : ''}`}>
          {filteredAgents.map(agent => (
            <button
              key={agent.slug}
              className={`agent-list-item ${activeAgent?.slug === agent.slug ? 'active' : ''}`}
              onClick={() => handleAgentClick(agent)}
            >
              <span className="agent-list-avatar" style={{ background: agent.is_external ? '#f97316' : '#6b7280' }}>
                {agent.is_external ? 'H' : agent.name[0]}
              </span>
              <div className="agent-list-info">
                <span className="agent-list-name">
                  {agent.name}
                  {agent.is_external && <span className="agent-badge extern">extern</span>}
                </span>
                <span className="agent-list-role">{agent.role_name || agent.type}</span>
              </div>
              {!agent.is_external && (
                <span
                  className={`star-toggle ${primarySlug === agent.slug ? 'active' : ''}`}
                  onClick={(e) => { e.stopPropagation(); togglePrimary(agent.slug) }}
                >★</span>
              )}
            </button>
          ))}
          {filteredAgents.length === 0 && agentSearch.trim() && (
            <div className="agent-list-empty">Ничего не найдено</div>
          )}
        </div>
      </div>

      <div className="sidebar-footer">
        <button className={`settings-btn ${view.type === 'projects' ? 'active' : ''}`} onClick={() => setView({ type: 'projects' })}>
          <span>📁</span> Проекты
        </button>
        <button className={`settings-btn ${view.type === 'deadlines' ? 'active' : ''}`} onClick={() => setView({ type: 'deadlines' })}>
          <span>⏰</span> Дедлайны
        </button>
        <button className={`settings-btn ${view.type === 'connections' ? 'active' : ''}`} onClick={() => setView({ type: 'connections' })}>
          <span>🔗</span> Связи
        </button>
        <button className={`settings-btn ${view.type === 'kanban' ? 'active' : ''}`} onClick={() => setView({ type: 'kanban' })}>
          <span>📋</span> Задачи
        </button>
        <button className={`settings-btn ${view.type === 'settings' ? 'active' : ''}`} onClick={() => setView({ type: 'settings' })}>
          <span>⚙️</span> Настройки
        </button>
        <div className="version-bar">
          <span className="version-label">VERSION</span>
          <span className="version-number" title="Live version from server (auto-updates via WebSocket)">{serverVersion}</span>
          <span className="version-status up-to-date" />
        </div>
      </div>
    </aside>
  )
}