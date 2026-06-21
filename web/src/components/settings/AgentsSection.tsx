/**
 * Agents settings section — CRUD, roles, departments, tools, external agents.
 * Extracted from SettingsPage.tsx (lines 838-1744).
 */

import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from '../../config'
import { LoadingSpinner } from '../LoadingSpinner'
import { DropdownMenu } from '../DropdownMenu'
import type { AgentData, ExternalAgentData } from './types'

interface RoleInfo { rolesid: string; name: string; description: string; color: string }
interface DeptInfo { departmentsid: string; name: string; description: string; color: string }

interface AgentsSectionProps {
  onAgentsChange?: () => void
  wsOn?: (type: string, handler: (data: any) => void) => () => void
}

export function AgentsSection({ onAgentsChange, wsOn }: AgentsSectionProps) {
  const [agents, setAgents] = useState<AgentData[]>([])
  const [providers, setProviders] = useState<{ name: string; models: string[] }[]>([])
  const [hoveredAgent, setHoveredAgent] = useState<string | null>(null)
  const [overlayShift, setOverlayShift] = useState<Record<string, number>>({})
  const [roles, setRoles] = useState<RoleInfo[]>([])
  const [departments, setDepartments] = useState<DeptInfo[]>([])
  const [defaultRole, setDefaultRole] = useState('')
  const [defaultDept, setDefaultDept] = useState('')
  const [newRole, setNewRole] = useState({ name: '', description: '', color: '#f59e0b' })
  const [newDept, setNewDept] = useState({ name: '', description: '', color: '#3b82f6' })
  const [externalAgents, setExternalAgents] = useState<ExternalAgentData[]>([])
  const [externalDetected, setExternalDetected] = useState(false)
  const [detecting, setDetecting] = useState(false)
  const [showSetup, setShowSetup] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createForm, setCreateForm] = useState({
    name: '', role: '', department: '', model: '',
    description: '', system_prompt: '', temperature: 0.7,
  })
  const [creating, setCreating] = useState(false)
  const [formTouched, setFormTouched] = useState(false)

  useEffect(() => {
    if (!hoveredAgent) return
    const timer = setTimeout(() => {
      const wrapper = document.querySelector('.agent-card-wrapper:hover') ||
                      document.querySelector('.agent-expanded-overlay')
      if (!wrapper) return
      const rect = wrapper.getBoundingClientRect()
      const vh = window.innerHeight
      const overlayHeight = rect.height * 3.2
      const overlayTop = rect.top - rect.height * 0.6
      const overflow = (overlayTop + overlayHeight) - vh
      if (overflow > 0) {
        setOverlayShift(prev => ({ ...prev, [hoveredAgent]: overflow + 16 }))
      }
    }, 10)
    return () => clearTimeout(timer)
  }, [hoveredAgent])

  const roleMap: Record<string, { name: string; color: string }> = {}
  for (const r of roles) roleMap[r.rolesid] = { name: r.name, color: r.color }
  // Fallback for default role IDs not in roles.yaml
  if (!roleMap['worker']) roleMap['worker'] = { name: 'Сотрудник', color: '#6b7280' }
  const deptMap: Record<string, { name: string; color: string }> = {}
  for (const d of departments) deptMap[d.departmentsid] = { name: d.name, color: d.color }

  const fetchAgents = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/agents`)
      if (res.ok) { const data = await res.json(); setAgents(data.agents || []) }
    } catch (e) { console.error('[agents] fetch error:', e) }
  }, [])

  const fetchProviders = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/providers`)
      if (res.ok) { const data = await res.json(); setProviders(data.providers || []) }
    } catch (e) { console.error('[agents] providers fetch error:', e) }
  }, [])

  const fetchRoles = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/roles`)
      if (res.ok) { const data = await res.json(); setRoles(data.roles || []); setDefaultRole(data.is_default || '') }
    } catch (e) { console.error('[roles] fetch error:', e) }
  }, [])

  const fetchDepartments = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/departments`)
      if (res.ok) { const data = await res.json(); setDepartments(data.departments || []); setDefaultDept(data.is_default || '') }
    } catch (e) { console.error('[departments] fetch error:', e) }
  }, [])

  const detectExternalAgents = useCallback(async () => {
    setDetecting(true)
    try {
      const res = await fetch(`${API_BASE}/api/external-agents/detect`)
      if (res.ok) { const data = await res.json(); setExternalAgents(data.agents || []); setExternalDetected(true) }
    } catch (e) { console.error('[external-agents] detect error:', e); setExternalDetected(true) }
    finally { setDetecting(false) }
  }, [])

  useEffect(() => {
    fetchAgents(); fetchProviders(); fetchRoles(); fetchDepartments(); detectExternalAgents()
  }, [fetchAgents, fetchProviders, fetchRoles, fetchDepartments, detectExternalAgents])

  // Listen for primary agent changes via WebSocket
  useEffect(() => {
    if (!wsOn) return
    const off = wsOn('agent:primary_changed', () => {
      fetchAgents()
      detectExternalAgents()
    })
    return off
  }, [wsOn, fetchAgents, detectExternalAgents])

  const handleAddRole = async () => {
    if (!newRole.name.trim()) return
    const rolesid = newRole.name.trim().toLowerCase().replace(/\s+/g, '-')
    const updated = [...roles, { rolesid, ...newRole }]
    const res = await fetch(`${API_BASE}/api/roles`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ roles: updated, is_default: defaultRole }),
    })
    if (res.ok) { const data = await res.json(); setRoles(data.roles) }
    setNewRole({ name: '', description: '', color: '#f59e0b' })
  }

  const handleAddDept = async () => {
    if (!newDept.name.trim()) return
    try {
      const res = await fetch(`${API_BASE}/api/departments`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newDept.name.trim(), description: newDept.description, color: newDept.color }),
      })
      if (res.ok) fetchDepartments()
    } catch (e) { console.error('[departments] add error:', e) }
    setNewDept({ name: '', description: '', color: '#3b82f6' })
  }

  const handleRemoveRole = async (rolesid: string) => {
    const updated = roles.filter(r => r.rolesid !== rolesid)
    const newDefault = defaultRole === rolesid ? '' : defaultRole
    const res = await fetch(`${API_BASE}/api/roles`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ roles: updated, is_default: newDefault }),
    })
    if (res.ok) { const data = await res.json(); setRoles(data.roles); setDefaultRole(data.is_default || '') }
  }

  const handleRoleColorChange = async (rolesid: string, newColor: string) => {
    const updated = roles.map(r => r.rolesid === rolesid ? { ...r, color: newColor } : r)
    try {
      const res = await fetch(`${API_BASE}/api/roles`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ roles: updated, is_default: defaultRole }),
      })
      if (res.ok) { const data = await res.json(); setRoles(data.roles) }
    } catch (e) { console.error('[roles] color change error:', e) }
  }

  const handleSetDefaultRole = async (rolesid: string) => {
    const newDefault = defaultRole === rolesid ? '' : rolesid
    try {
      const res = await fetch(`${API_BASE}/api/roles`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ roles, is_default: newDefault }),
      })
      if (res.ok) fetchRoles()
    } catch (e) { console.error('[roles] set default error:', e) }
  }

  const handleDeptColorChange = async (departmentsid: string, newColor: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/departments/${departmentsid}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ color: newColor }),
      })
      if (res.ok) fetchDepartments()
    } catch (e) { console.error('[departments] color change error:', e) }
  }

  const handleSetDefaultDept = async (departmentsid: string) => {
    const newDefault = defaultDept === departmentsid ? '' : departmentsid
    try {
      const res = await fetch(`${API_BASE}/api/departments`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ departments, is_default: newDefault }),
      })
      if (res.ok) fetchDepartments()
    } catch (e) { console.error('[departments] set default error:', e) }
  }

  const handleRemoveDept = async (departmentsid: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/departments/${departmentsid}`, { method: 'DELETE' })
      if (res.ok) fetchDepartments()
    } catch (e) { console.error('[departments] remove error:', e) }
  }

  const handleAgentRoleChange = async (agent: AgentData, newRole: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/agents/${agent.slug}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: newRole }),
      })
      if (res.ok) fetchAgents()
    } catch (e) { console.error('[agents] role change error:', e) }
  }

  const handleAgentDeptChange = async (agent: AgentData, newDept: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/agents/${agent.slug}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ department: newDept }),
      })
      if (res.ok) fetchAgents()
    } catch (e) { console.error('[agents] dept change error:', e) }
  }

  const handleToggle = async (agent: AgentData) => {
    try {
      const res = await fetch(`${API_BASE}/api/agents/${agent.slug}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !agent.enabled }),
      })
      if (res.ok) fetchAgents()
    } catch (e) { console.error('[agents] toggle error:', e) }
  }

  const handleModelChange = async (agent: AgentData, newModel: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/agents/${agent.slug}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: newModel }),
      })
      if (res.ok) fetchAgents()
    } catch (e) { console.error('[agents] model change error:', e) }
  }

  const handleAgentFieldChange = async (agent: AgentData, field: string, value: unknown) => {
    try {
      const res = await fetch(`${API_BASE}/api/agents/${agent.slug}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: value }),
      })
      if (res.ok) fetchAgents()
    } catch (e) { console.error('[agents] field change error:', e) }
  }

  const handleCreateAgent = async () => {
    setFormTouched(true)
    if (!createForm.name.trim()) return
    setCreating(true)
    try {
      const res = await fetch(`${API_BASE}/api/agents`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(createForm),
      })
      if (res.ok) {
        setShowCreateModal(false)
        setCreateForm({ name: '', role: '', department: '', model: '', description: '', system_prompt: '', temperature: 0.7 })
        setFormTouched(false)
        fetchAgents()
      }
    } catch (e) { console.error('[agents] create error:', e) } finally { setCreating(false) }
  }

  const handleDeleteAgent = async (slug: string) => {
    if (!confirm('Удалить агента?')) return
    try {
      const res = await fetch(`${API_BASE}/api/agents/${slug}`, { method: 'DELETE' })
      if (res.ok) { setHoveredAgent(null); fetchAgents() }
    } catch (e) { console.error('[agents] delete error:', e) }
  }

  const handleExternalToggle = async (agent: ExternalAgentData) => {
    try {
      const res = await fetch(`${API_BASE}/api/external-agents/${agent.slug}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !agent.enabled }),
      })
      if (res.ok) detectExternalAgents()
    } catch (e) { console.error('[external-agents] toggle error:', e) }
  }

  const handleExternalRoleChange = async (agent: ExternalAgentData, newRole: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/external-agents/${agent.slug}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: newRole }),
      })
      if (res.ok) detectExternalAgents()
    } catch (e) { console.error('[external-agents] role change error:', e) }
  }

  const handleExternalDeptChange = async (agent: ExternalAgentData, newDept: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/external-agents/${agent.slug}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ department: newDept }),
      })
      if (res.ok) detectExternalAgents()
    } catch (e) { console.error('[external-agents] dept change error:', e) }
  }

  const handleExternalFieldChange = async (agent: ExternalAgentData, field: string, value: unknown) => {
    try {
      const res = await fetch(`${API_BASE}/api/external-agents/${agent.slug}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: value }),
      })
      if (res.ok) detectExternalAgents()
    } catch (e) { console.error('[external-agents] field change error:', e) }
  }

  const modelOptions: string[] = []
  for (const p of providers) {
    if (p.models.length === 0) modelOptions.push(`${p.name}/(no models)`)
    else for (const m of p.models) modelOptions.push(`${p.name}/${m}`)
  }

  return (
    <div>
      {/* Create Agent button */}
      <div className="create-agent-bar">
        <button className="create-agent-btn" onClick={() => setShowCreateModal(true)}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 5v14M5 12h14" />
          </svg>
          Создать агента
        </button>
      </div>

      {/* Create Agent modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => { setShowCreateModal(false); setFormTouched(false) }}>
          <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: 520 }}>
            <div className="modal-header">
              <h2>Новый агент</h2>
              <button className="modal-close" onClick={() => { setShowCreateModal(false); setFormTouched(false) }}>×</button>
            </div>
            <div className="modal-body">
              <div className="settings-field">
                <label>Имя *</label>
                <input className={`settings-input ${formTouched && !createForm.name.trim() ? 'field-error' : ''}`}
                  placeholder="Например: Маркетолог"
                  value={createForm.name} onChange={e => setCreateForm({ ...createForm, name: e.target.value })} />
                {formTouched && !createForm.name.trim() && <span className="field-error-text">Обязательное поле</span>}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="settings-field">
                  <label>Роль</label>
                  <DropdownMenu
                    value={createForm.role}
                    onChange={v => setCreateForm({ ...createForm, role: v })}
                    options={[
                      { value: '', label: '— не указана —' },
                      ...roles.map(r => ({ value: r.rolesid, label: r.name })),
                    ]}
                    width="100%"
                  />
                </div>
                <div className="settings-field">
                  <label>Департамент</label>
                  <DropdownMenu
                    value={createForm.department}
                    onChange={v => setCreateForm({ ...createForm, department: v })}
                    options={[
                      { value: '', label: '— не указан —' },
                      ...departments.map(d => ({ value: d.departmentsid, label: d.name })),
                    ]}
                    width="100%"
                  />
                </div>
              </div>
              <div className="settings-field">
                <label>Модель</label>
                <DropdownMenu
                  value={createForm.model}
                  onChange={v => setCreateForm({ ...createForm, model: v })}
                  options={[
                    { value: '', label: '— выбрать позже —' },
                    ...modelOptions.map(opt => ({ value: opt, label: opt })),
                  ]}
                  width="100%"
                />
              </div>
              <div className="settings-field">
                <label>Описание</label>
                <input className="settings-input" placeholder="Кратко о роли агента..."
                  value={createForm.description} onChange={e => setCreateForm({ ...createForm, description: e.target.value })} />
              </div>
              <div className="settings-field">
                <label>System Prompt</label>
                <textarea className="settings-input" rows={4} placeholder="Инструкции для агента..."
                  value={createForm.system_prompt} onChange={e => setCreateForm({ ...createForm, system_prompt: e.target.value })} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="settings-btn-secondary" onClick={() => { setShowCreateModal(false); setFormTouched(false) }}>Отмена</button>
              <button className={`settings-btn-primary ${formTouched && !createForm.name.trim() ? 'btn-warn' : ''}`}
                disabled={creating} onClick={handleCreateAgent}>
                {creating ? 'Создание...' : 'Создать'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Roles & Departments section */}
      <div className="roles-depts-section">
        <div className="roles-depts-grid">
          {/* Roles column */}
          <div className="roles-depts-column">
            <h3 className="roles-depts-title">Роли</h3>
            <p className="roles-depts-hint">Определяют уровень ответственности агента в команде. Используются для формирования системного промта и организации чатов.</p>
            <div className="roles-depts-list">
              {roles.map(role => (
                <div key={role.rolesid} className="roles-depts-item">
                  <button className={`roles-depts-default ${defaultRole === role.rolesid ? 'active' : ''}`}
                    onClick={() => handleSetDefaultRole(role.rolesid)}
                    title={defaultRole === role.rolesid ? 'Убрать роль по умолчанию' : 'Назначить роль по умолчанию'}>
                    <span className="roles-depts-default-dot" />
                  </button>
                  <label className="roles-depts-color clickable" style={{ background: role.color }} title="Изменить цвет">
                    <input type="color" value={role.color} onChange={e => handleRoleColorChange(role.rolesid, e.target.value)} />
                  </label>
                  <div className="roles-depts-info">
                    <span className="roles-depts-name" style={{ color: role.color }}>{role.name}</span>
                    <span className="roles-depts-desc">{role.description}</span>
                  </div>
                  <button className="roles-depts-remove" onClick={() => handleRemoveRole(role.rolesid)} title="Удалить">×</button>
                </div>
              ))}
            </div>
            <div className="roles-depts-add">
              <input className="settings-input roles-depts-input" placeholder="Название роли..." value={newRole.name} onChange={e => setNewRole({ ...newRole, name: e.target.value })} />
              <input className="settings-input roles-depts-input roles-depts-input-sm" placeholder="Описание..." value={newRole.description} onChange={e => setNewRole({ ...newRole, description: e.target.value })} />
              <input type="color" className="roles-depts-color-picker" value={newRole.color} onChange={e => setNewRole({ ...newRole, color: e.target.value })} />
              <button className="roles-depts-add-btn" onClick={handleAddRole} title="Добавить роль">+</button>
            </div>
          </div>

          {/* Departments column */}
          <div className="roles-depts-column">
            <h3 className="roles-depts-title">Департаменты</h3>
            <p className="roles-depts-hint">Определяют область специализации агента. Влияют на контекст системного промта и распределение задач.</p>
            <div className="roles-depts-list">
              {departments.map(dept => (
                <div key={dept.departmentsid} className="roles-depts-item">
                  <button className={`roles-depts-default ${defaultDept === dept.departmentsid ? 'active' : ''}`}
                    onClick={() => handleSetDefaultDept(dept.departmentsid)}
                    title={defaultDept === dept.departmentsid ? 'Убрать отдел по умолчанию' : 'Назначить отдел по умолчанию'}>
                    <span className="roles-depts-default-dot" />
                  </button>
                  <label className="roles-depts-color clickable" style={{ background: dept.color }} title="Изменить цвет">
                    <input type="color" value={dept.color} onChange={e => handleDeptColorChange(dept.departmentsid, e.target.value)} />
                  </label>
                  <div className="roles-depts-info">
                    <span className="roles-depts-name" style={{ color: dept.color }}>{dept.name}</span>
                    <span className="roles-depts-desc">{dept.description}</span>
                  </div>
                  <button className="roles-depts-remove" onClick={() => handleRemoveDept(dept.departmentsid)} title="Удалить">×</button>
                </div>
              ))}
            </div>
            <div className="roles-depts-add">
              <input className="settings-input roles-depts-input" placeholder="Название отдела..." value={newDept.name} onChange={e => setNewDept({ ...newDept, name: e.target.value })} />
              <input className="settings-input roles-depts-input roles-depts-input-sm" placeholder="Описание..." value={newDept.description} onChange={e => setNewDept({ ...newDept, description: e.target.value })} />
              <input type="color" className="roles-depts-color-picker" value={newDept.color} onChange={e => setNewDept({ ...newDept, color: e.target.value })} />
              <button className="roles-depts-add-btn" onClick={handleAddDept} title="Добавить отдел">+</button>
            </div>
          </div>
        </div>
      </div>

      {/* Внешние агенты section */}
      {!externalDetected ? (
        <LoadingSpinner text="Обнаружение внешних агентов..." minHeight={80} />
      ) : externalAgents.length > 0 ? (
        <section className="agents-role-section">
          <h2 className="agents-role-title">
            <span className="agents-role-dot" style={{ background: '#6b7280' }} />
            Внешние агенты
          </h2>
          {/* Gateway warning when agents exist but unavailable */}
          {externalAgents.some(a => !a.available) && (
            <div className="external-gateway-warning">
              <span>⚠️ Гатевей не запущен — агенты не могут получать задачи.</span>
              <button className="settings-link-btn" onClick={() => setShowSetup(v => !v)}>
                {showSetup ? 'Скрыть инструкцию' : 'Инструкция по настройке'}
              </button>
            </div>
          )}
          <div className={`external-agents-setup compact${showSetup ? ' open' : ''}`}>
            <div className="setup-steps">
              <div className="setup-step">
                <span className="setup-step-num">1</span>
                <div>
                  <strong style={{ color: 'var(--orange)' }}>Включите API сервер в Hermes</strong>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    Добавьте в <code>~/.hermes/.env</code>: <code>API_SERVER_ENABLED=true</code>
                  </div>
                </div>
              </div>
              <div className="setup-step">
                <span className="setup-step-num">2</span>
                <div>
                  <strong style={{ color: 'var(--orange)' }}>Запустите шлюз</strong>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                    <code>hermes gateway</code> — API на <code>http://127.0.0.1:8642</code>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div className="settings-grid">
            {externalAgents.map(agent => (
              <div key={agent.slug} className="agent-card-wrapper"
                onClick={() => setHoveredAgent(prev => prev === agent.slug ? null : agent.slug)}
                onMouseLeave={() => { if (hoveredAgent === agent.slug) { setHoveredAgent(null); setOverlayShift(prev => { const n = { ...prev }; delete n[agent.slug]; return n }) } }}>
                <section className={`settings-card agent-card external-agent ${!agent.enabled ? 'disabled' : ''}`}>
                  <div className="agent-header">
                    <div className="agent-identity">
                      <span className="agent-avatar external" style={{ background: agent.color }}>{agent.icon_letter}</span>
                      <div>
                        <span className="agent-name">{agent.name}<span className="agent-badge extern">extern</span></span>
                        <span className="agent-role" style={{ color: roleMap[agent.role]?.color || '#6b7280' }}>{deptMap[agent.department]?.name || 'Без отдела'}</span>
                      </div>
                    </div>
                    <div className="agent-status-icon">
                      {!agent.available ? (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2.5"><circle cx="12" cy="12" r="10" /><path d="M15 9l-6 6M9 9l6 6" /></svg>
                      ) : agent.enabled ? (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2.5"><circle cx="12" cy="12" r="10" /><path d="M8 12l3 3 5-6" /></svg>
                      ) : (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2.5"><circle cx="12" cy="12" r="10" /><path d="M15 9l-6 6M9 9l6 6" /></svg>
                      )}
                    </div>
                  </div>
                  <div className="agent-model-text"><span className="agent-model-label">ТИП</span><span className="agent-model-value">{agent.type}</span></div>
                  <div className="agent-model-text"><span className="agent-model-label">ОПИСАНИЕ</span><span className="agent-model-value" style={{ fontSize: '11px', opacity: 0.7 }}>{agent.description}</span></div>
                </section>
                {hoveredAgent === agent.slug && (
                  <div className="agent-expanded-overlay external" onClick={e => e.stopPropagation()} style={overlayShift[agent.slug] != null ? { marginTop: -overlayShift[agent.slug]! } : undefined}>
                    <div className="agent-expanded-content">
                      <div className="agent-expanded-header">
                        <span className="agent-expanded-avatar external" style={{ background: agent.color }}>{agent.icon_letter}</span>
                        <div>
                          <span className="agent-expanded-name">{agent.name}<span className="agent-badge extern">extern</span></span>
                          <span className="agent-expanded-role" style={{ color: roleMap[agent.role]?.color || '#6b7280' }}>{roleMap[agent.role]?.name || agent.role} · {deptMap[agent.department]?.name || 'Без отдела'}</span>
                        </div>
                      </div>
                      <div className="agent-expanded-body">
                        <div className="expanded-field">
                          <label>Роль</label>
                          <DropdownMenu
                            value={agent.role}
                            onChange={v => handleExternalRoleChange(agent, v)}
                            options={roles.map(r => ({ value: r.rolesid, label: r.name }))}
                            width="100%"
                          />
                        </div>
                        <div className="expanded-field">
                          <label>Департамент</label>
                          <DropdownMenu
                            value={agent.department}
                            onChange={v => handleExternalDeptChange(agent, v)}
                            options={departments.map(d => ({ value: d.departmentsid, label: d.name }))}
                            width="100%"
                          />
                        </div>
                        {agent.models.length > 0 && (
                          <div className="expanded-field">
                            <label>Модель</label>
                            <DropdownMenu
                              value={agent.models[0] || ''}
                              onChange={() => {}}
                              options={agent.models.map(m => ({ value: m, label: m }))}
                              width="100%"
                              disabled
                            />
                          </div>
                        )}
                        <div className="expanded-toggle-row">
                          <label className="settings-toggle"><input type="checkbox" checked={agent.enabled} onChange={() => handleExternalToggle(agent)} /><span>Активен</span></label>
                        </div>
                        {!agent.available && <div className="external-unavailable">⚠️ Сервис недоступен. Убедитесь что Hermes Gateway запущен.</div>}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      ) : (
        <section className="agents-role-section">
          <h2 className="agents-role-title">
            <span className="agents-role-dot" style={{ background: '#6b7280' }} />
            Внешние агенты
          </h2>
          <div className="external-agents-setup">
            <div className="setup-icon">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
            </div>
            <h3 className="setup-title" style={{ color: 'var(--orange)' }}>Подключение внешних агентов</h3>
            <p className="setup-desc">
              Внешние агенты — это самостоятельные AI-агенты, работающие отдельно от SynPin.
              Они подключаются через ACP (Agent Communication Protocol) и получают задачи из отделов.
            </p>
            <div className="setup-steps">
              <div className="setup-step">
                <span className="setup-step-num">1</span>
                <div>
                  <strong style={{ color: 'var(--orange)' }}>Включите API сервер в Hermes</strong>
                  Добавьте в <code>~/.hermes/.env</code>:<br/>
                  <code>API_SERVER_ENABLED=true</code><br/>
                  <code>API_SERVER_KEY=ваш-ключ</code>
                </div>
              </div>
              <div className="setup-step">
                <span className="setup-step-num">2</span>
                <div>
                  <strong style={{ color: 'var(--orange)' }}>Запустите шлюз</strong>
                  <code>hermes gateway</code> — API сервер поднимется на <code>http://127.0.0.1:8642</code>
                </div>
              </div>
              <div className="setup-step">
                <span className="setup-step-num">3</span>
                <div>
                  <strong style={{ color: 'var(--orange)' }}>Обнаружение автоматическое</strong>
                  SynPin проверяет <code>localhost:8642</code> при загрузке страницы.
                  Когда шлюз запущен — Hermes появится здесь с кнопкой «Активировать».
                </div>
              </div>
            </div>
            <button className="settings-btn-primary" onClick={detectExternalAgents} disabled={detecting} style={{ marginTop: '12px' }}>
              {detecting ? 'Проверяю...' : 'Проверить снова'}
            </button>
          </div>
        </section>
      )}

      {/* Agents grouped by role */}
      {(() => {
        const grouped: Record<string, AgentData[]> = {}
        for (const agent of agents) {
          const key = agent.role || '_unassigned'
          if (!grouped[key]) grouped[key] = []
          grouped[key].push(agent)
        }
        const roleOrder = roles.map(r => r.rolesid)
        const allKeys = [...roleOrder.filter(k => grouped[k]), ...Object.keys(grouped).filter(k => !roleOrder.includes(k))]
        return allKeys.map(roleId => (
          <section key={roleId} className="agents-role-section">
            <h2 className="agents-role-title">
              <span className="agents-role-dot" style={{ background: roleMap[roleId]?.color || '#6b7280' }} />
              {roleMap[roleId]?.name || roleId}
            </h2>
            <div className="settings-grid">
              {(grouped[roleId] || []).map(agent => (
                <div key={agent.slug} className="agent-card-wrapper"
                  onClick={() => setHoveredAgent(prev => prev === agent.slug ? null : agent.slug)}
                  onMouseLeave={() => { if (hoveredAgent === agent.slug) { setHoveredAgent(null); setOverlayShift(prev => { const n = { ...prev }; delete n[agent.slug]; return n }) } }}>
                  <section className={`settings-card agent-card ${!agent.enabled ? 'disabled' : ''}`}>
                    <div className="agent-header">
                      <div className="agent-identity">
                        <span className="agent-avatar">{agent.name[0]}</span>
                        <div>
                          <span className="agent-name">{agent.name}</span>
                          <span className="agent-role" style={{ color: roleMap[agent.role]?.color || '#6b7280' }}>{deptMap[agent.department]?.name || 'Без отдела'}</span>
                        </div>
                      </div>
                      <div className="agent-status-icon">
                        {agent.enabled ? (
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2.5"><circle cx="12" cy="12" r="10" /><path d="M8 12l3 3 5-6" /></svg>
                        ) : (
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2.5"><circle cx="12" cy="12" r="10" /><path d="M15 9l-6 6M9 9l6 6" /></svg>
                        )}
                      </div>
                    </div>
                    <div className="agent-model-text"><span className="agent-model-label">МОДЕЛЬ</span><span className="agent-model-value">{agent.model || '—'}</span></div>
                    {agent.skills.length > 0 && (
                      <div className="agent-skills-compact">
                        {agent.skills.slice(0, 3).map(skill => <span key={skill} className="model-chip" style={{ fontSize: '10px', padding: '1px 6px' }}>{skill}</span>)}
                        {agent.skills.length > 3 && <span className="model-chip" style={{ fontSize: '10px', padding: '1px 6px', opacity: 0.6 }}>+{agent.skills.length - 3}</span>}
                      </div>
                    )}
                  </section>
                  {hoveredAgent === agent.slug && (
                    <div className="agent-expanded-overlay" onClick={e => e.stopPropagation()} style={overlayShift[agent.slug] != null ? { marginTop: -overlayShift[agent.slug]! } : undefined}>
                      <div className="agent-expanded-content">
                        <div className="agent-expanded-header">
                          <span className="agent-expanded-avatar">{agent.name[0]}</span>
                          <div>
                            <span className="agent-expanded-name">{agent.name}</span>
                            <span className="agent-expanded-role" style={{ color: roleMap[agent.role]?.color || '#6b7280' }}>{roleMap[agent.role]?.name || agent.role} · {deptMap[agent.department]?.name || 'Без отдела'}</span>
                          </div>
                        </div>
                        <div className="agent-expanded-body">
                          <div className="expanded-field"><label>Agent ID</label><span className="agentid-display">{agent.agentid}</span></div>
                          <div className="expanded-field">
                            <label>Роль</label>
                            <DropdownMenu
                              value={agent.role}
                              onChange={v => handleAgentRoleChange(agent, v)}
                              options={roles.map(r => ({ value: r.rolesid, label: r.name }))}
                              width="100%"
                            />
                          </div>
                          <div className="expanded-field">
                            <label>Департамент</label>
                            <DropdownMenu
                              value={agent.department}
                              onChange={v => handleAgentDeptChange(agent, v)}
                              options={departments.map(d => ({ value: d.departmentsid, label: d.name }))}
                              width="100%"
                            />
                          </div>
                          <div className="expanded-field">
                            <label>Модель</label>
                            <DropdownMenu
                              value={agent.model || ''}
                              onChange={v => handleModelChange(agent, v)}
                              options={[
                                { value: '', label: '— выбрать —' },
                                ...modelOptions.map(opt => ({ value: opt, label: opt })),
                              ]}
                              width="100%"
                            />
                          </div>
                          {agent.provider && <div className="expanded-field"><label>Провайдер</label><span>{agent.provider}</span></div>}
                          <div className="expanded-field">
                            <label>Контекстное окно (токены)</label>
                            <input type="number" className="settings-input" value={agent.context_window || ''} placeholder="128000"
                              onBlur={e => { const val = Number(e.target.value); if (val > 0 && val !== agent.context_window) handleAgentFieldChange(agent, 'context_window', val) }} />
                          </div>
                          {agent.skills && agent.skills.length > 0 && (
                            <div className="expanded-field">
                              <label>Скиллы</label>
                              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                {agent.skills.map(skill => <span key={skill} className="model-chip" style={{ fontSize: '11px', padding: '1px 8px' }}>{skill}</span>)}
                              </div>
                            </div>
                          )}
                          <div className="expanded-field">
                            <label>System Prompt</label>
                            <textarea className="settings-input expanded-textarea" rows={4} defaultValue={agent.system_prompt}
                              onBlur={e => { if (e.target.value !== agent.system_prompt) handleAgentFieldChange(agent, 'system_prompt', e.target.value) }} />
                          </div>
                          {agent.description && <div className="expanded-field"><label>Описание</label><span className="expanded-description">{agent.description}</span></div>}
                          <div className="expanded-toggle-row">
                            <label className="settings-toggle"><input type="checkbox" checked={agent.enabled} onChange={() => handleToggle(agent)} /><span>Активен</span></label>
                            <label className="settings-toggle" style={{ marginLeft: 12 }}>
                              <input
                                type="checkbox"
                                checked={agent.is_primary || false}
                                onChange={() => handleAgentFieldChange(agent, 'is_primary', !agent.is_primary)}
                              />
                              <span>Главный агент ★</span>
                            </label>
                            <button className="expanded-delete-btn" onClick={() => handleDeleteAgent(agent.slug)} title="Удалить агента">
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
                              </svg>
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        ))
      })()}
    </div>
  )
}
