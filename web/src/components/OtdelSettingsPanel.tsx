import { useState, useEffect, useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:2088'

interface OtdelData {
  otdelid: string
  name: string
  description: string
  color: string
  mentor_role: string
  escalation: string
  agent_count: number
}

interface Role {
  rolesid: string
  name: string
  color: string
}

interface Agent {
  slug: string
  name: string
  role_name: string
  department_name: string
}

interface OtdelSettingsPanelProps {
  otdel: OtdelData
  open: boolean
  onClose: () => void
  onSaved: () => void
}

export function OtdelSettingsPanel({ otdel, open, onClose, onSaved }: OtdelSettingsPanelProps) {
  const [form, setForm] = useState({
    name: otdel.name,
    description: otdel.description,
    color: otdel.color || '#f97316',
    mentor_role: otdel.mentor_role || '',
  })
  const [roles, setRoles] = useState<Role[]>([])
  const [agents, setAgents] = useState<Agent[]>([])
  const [saving, setSaving] = useState(false)

  // Reload form when otdel changes
  useEffect(() => {
    setForm({
      name: otdel.name,
      description: otdel.description,
      color: otdel.color || '#f97316',
      mentor_role: otdel.mentor_role || '',
    })
  }, [otdel.otdelid])

  const loadData = useCallback(async () => {
    try {
      const [rolesRes, agentsRes] = await Promise.all([
        fetch(`${API_BASE}/api/roles`),
        fetch(`${API_BASE}/api/agents`),
      ])
      if (rolesRes.ok) {
        const d = await rolesRes.json()
        setRoles(d.roles || [])
      }
      if (agentsRes.ok) {
        const d = await agentsRes.json()
        setAgents(d.agents || [])
      }
    } catch {}
  }, [])

  useEffect(() => {
    if (open) loadData()
  }, [open, loadData])

  const handleSave = async () => {
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/api/otdels/${otdel.otdelid}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name.trim(),
          description: form.description,
          color: form.color,
          mentor_role: form.mentor_role,
        }),
      })
      if (res.ok) {
        onSaved()
        onClose()
      }
    } catch {} finally { setSaving(false) }
  }

  // Find mentor role name for display
  const mentorRoleName = roles.find(r => r.rolesid === form.mentor_role)?.name || ''

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
          {/* Preview */}
          <div className="otdel-settings-preview">
            <span className="otdel-settings-preview-dot" style={{ background: form.color }} />
            <span className="otdel-settings-preview-name">{form.name || 'Название'}</span>
          </div>

          {/* Name */}
          <div className="settings-field">
            <label>Название</label>
            <input
              className="settings-input"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              placeholder="Backend, Frontend, DevOps..."
            />
          </div>

          {/* Description */}
          <div className="settings-field">
            <label>Описание</label>
            <textarea
              className="settings-input"
              rows={2}
              value={form.description}
              onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
              placeholder="Что делает этот отдел..."
            />
          </div>

          {/* Color */}
          <div className="settings-field">
            <label>Цвет</label>
            <div className="department-color-row">
              <input
                type="color"
                className="department-color-picker"
                value={form.color}
                onChange={e => setForm(f => ({ ...f, color: e.target.value }))}
              />
              <span className="department-color-value">{form.color}</span>
            </div>
          </div>

          {/* Mentor */}
          <div className="settings-field">
            <label>Ментор (роль)</label>
            <select
              className="settings-input"
              value={form.mentor_role}
              onChange={e => setForm(f => ({ ...f, mentor_role: e.target.value }))}
            >
              <option value="">Не назначен</option>
              {roles.map(r => (
                <option key={r.rolesid} value={r.rolesid}>{r.name}</option>
              ))}
            </select>
            {mentorRoleName && (
              <span className="otdel-mentor-hint">
                Ментор будет отображаться цветом роли: <span style={{ color: roles.find(r => r.rolesid === form.mentor_role)?.color }}>{mentorRoleName}</span>
              </span>
            )}
          </div>

          {/* Workers info */}
          <div className="settings-field">
            <label>Работники</label>
            <div className="otdel-workers-info">
              {agents.length === 0 ? (
                <>
                  <span className="otdel-workers-empty">Нет агентов в системе</span>
                  <span className="otdel-workers-hint">
                    Назначение работников будет доступно после создания агентов
                  </span>
                </>
              ) : (
                <>
                  <span className="otdel-workers-count">{agents.length} агентов доступно</span>
                  <span className="otdel-workers-hint">
                    Назначение работников будет доступно после создания агентов
                  </span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="otdel-settings-footer">
          <button className="settings-btn-secondary" onClick={onClose}>Отмена</button>
          <button
            className="settings-btn-primary"
            disabled={saving || !form.name.trim()}
            onClick={handleSave}
          >
            {saving ? 'Сохранение...' : 'Сохранить'}
          </button>
        </div>
      </div>
    </>
  )
}
