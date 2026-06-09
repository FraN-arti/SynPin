import { useState, useEffect, useCallback } from 'react'

import { API_BASE } from '../config'

interface OtdelData {
  otdelid: string
  name: string
  description: string
  color: string
  mentor_role: string
  escalation: string
  agent_count: number
  head: string
  workers: string[]
  compaction_limit?: number
  keep_recent?: number
}

interface Agent {
  slug: string
  agentid: string
  name: string
  description: string
  role: string
  role_name: string
  department: string
  department_name: string
  enabled: boolean
}

interface Department {
  departmentsid: string
  name: string
  color: string
}

interface OtdelSettingsPanelProps {
  otdel: OtdelData
  open: boolean
  onClose: () => void
  onSaved: () => void
}

export function OtdelSettingsPanel({ otdel, open, onClose, onSaved }: OtdelSettingsPanelProps) {
  const [fullOtdel, setFullOtdel] = useState<OtdelData | null>(null)
  const [head, setHead] = useState('')
  const [workers, setWorkers] = useState<Set<string>>(new Set())
  const [agents, setAgents] = useState<Agent[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [saving, setSaving] = useState(false)
  const [compactionLimit, setCompactionLimit] = useState<number>(100)
  const [keepRecent, setKeepRecent] = useState<number>(10)

  // Load full otdel data + agents + departments when opened
  const loadData = useCallback(async () => {
    try {
      const [otdelRes, agentsRes, deptsRes] = await Promise.all([
        fetch(`${API_BASE}/api/otdels/${otdel.otdelid}`),
        fetch(`${API_BASE}/api/agents`),
        fetch(`${API_BASE}/api/departments`),
      ])

      if (otdelRes.ok) {
        const data = await otdelRes.json()
        setFullOtdel(data)
        setHead(data.head || '')
        setWorkers(new Set(data.workers || []))
        setCompactionLimit(data.compaction_limit ?? 100)
        setKeepRecent(data.keep_recent ?? 10)
      }

      if (agentsRes.ok) {
        const data = await agentsRes.json()
        setAgents((data.agents || []).filter((a: Agent) => a.enabled))
      }

      if (deptsRes.ok) {
        const data = await deptsRes.json()
        setDepartments(data.departments || [])
      }
    } catch {}
  }, [otdel.otdelid])

  useEffect(() => {
    if (open) loadData()
  }, [open, loadData])

  // Agents filtered by mentor_role (for "Глава" dropdown)
  const roleAgents = fullOtdel?.mentor_role
    ? agents.filter(a => a.role === fullOtdel.mentor_role)
    : []

  // Agents grouped by DEPARTMENTS from admin settings (not agent's department field)
  // This ensures we show the correct department structure
  const agentsByDept = new Map<string, Agent[]>()
  const validDeptIds = new Set(departments.map(d => d.departmentsid))

  // Initialize all departments (even empty ones)
  for (const dept of departments) {
    agentsByDept.set(dept.departmentsid, [])
  }

  // Place agents under matching departments
  const unmatched: Agent[] = []
  for (const agent of agents) {
    if (agent.slug === head) continue // Head is not a worker
    if (agent.department && validDeptIds.has(agent.department)) {
      agentsByDept.get(agent.department)!.push(agent)
    } else {
      unmatched.push(agent)
    }
  }

  // Agents with no matching department
  if (unmatched.length > 0) {
    agentsByDept.set('', unmatched)
  }

  // Remove empty departments (no agents)
  for (const [key, list] of agentsByDept) {
    if (list.length === 0) agentsByDept.delete(key)
  }

  // Get department name by id
  const getDeptName = (id: string) => {
    if (!id) return 'Без департамента'
    return departments.find(d => d.departmentsid === id)?.name || id
  }

  const toggleWorker = (slug: string) => {
    setWorkers(prev => {
      const next = new Set(prev)
      if (next.has(slug)) next.delete(slug)
      else next.add(slug)
      return next
    })
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/api/otdels/${otdel.otdelid}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          head,
          workers: Array.from(workers),
          compaction_limit: compactionLimit,
          keep_recent: keepRecent,
        }),
      })
      if (res.ok) {
        onSaved()
        onClose()
      }
    } catch {} finally { setSaving(false) }
  }

  return (
    <>
      {/* Backdrop */}
      {open && <div className="otdel-settings-backdrop" onClick={onClose} />}

      {/* Panel */}
      <div className={`otdel-settings-panel ${open ? 'open' : ''}`}>
        <div className="otdel-settings-header">
          <h2>Настройки отдела</h2>
          <button className="otdel-settings-close" onClick={onClose}>×</button>
        </div>

        <div className="otdel-settings-body">
          {/* Глава */}
          <div className="settings-field">
            <label>Глава</label>
            {!fullOtdel?.mentor_role ? (
              <span className="otdel-workers-hint" style={{ fontStyle: 'italic' }}>
                Назначьте роль ментора в основных настройках отдела
              </span>
            ) : roleAgents.length === 0 ? (
              <span className="otdel-workers-hint" style={{ fontStyle: 'italic' }}>
                Нет агентов с ролью «{fullOtdel.mentor_role}»
              </span>
            ) : (
              <select
                className="settings-input"
                value={head}
                onChange={e => setHead(e.target.value)}
              >
                <option value="">Не назначен</option>
                {roleAgents.map(a => (
                  <option key={a.slug} value={a.slug}>{a.name}</option>
                ))}
              </select>
            )}
          </div>

          {/* Работники */}
          <div className="settings-field">
            <label>Работники</label>
            <div className="otdel-workers-list">
              {agents.length === 0 ? (
                <span className="otdel-workers-hint">
                  Нет агентов в системе
                </span>
              ) : (
                Array.from(agentsByDept.entries()).map(([deptId, deptAgents]) => (
                  <div key={deptId} className="otdel-workers-dept">
                    <div className="otdel-workers-dept-header">
                      <span className="otdel-workers-dept-dot" style={{ background: departments.find(d => d.departmentsid === deptId)?.color || '#737373' }} />
                      <span className="otdel-workers-dept-name">{getDeptName(deptId)}</span>
                    </div>
                    <div className="otdel-workers-items">
                      {deptAgents.map(agent => (
                        <button
                          key={agent.slug}
                          className={`otdel-worker-chip ${workers.has(agent.slug) ? 'active' : ''}`}
                          onClick={() => toggleWorker(agent.slug)}
                          title={agent.description || agent.name}
                        >
                          <span className="otdel-worker-chip-dot" />
                          <span>{agent.name}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Компакция */}
          <div className="settings-field">
            <label>Компакция</label>
            <div className="otdel-compaction-settings">
              <div className="compaction-row">
                <span className="compaction-label">Лимит сообщений</span>
                <input
                  type="number"
                  className="settings-input compaction-input"
                  value={compactionLimit}
                  onChange={e => setCompactionLimit(Math.max(10, parseInt(e.target.value) || 10))}
                  min={10}
                  max={500}
                />
              </div>
              <div className="compaction-row">
                <span className="compaction-label">Сохранять последних</span>
                <input
                  type="number"
                  className="settings-input compaction-input"
                  value={keepRecent}
                  onChange={e => setKeepRecent(Math.max(1, parseInt(e.target.value) || 1))}
                  min={1}
                  max={50}
                />
              </div>
              <div className="compaction-hint">
                При превышении лимита старые сообщения заменяются summaries
              </div>
            </div>
          </div>
        </div>

        <div className="otdel-settings-footer">
          <button className="settings-btn-secondary" onClick={onClose}>Отмена</button>
          <button
            className="settings-btn-primary"
            disabled={saving}
            onClick={handleSave}
          >
            {saving ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </div>
    </>
  )
}
