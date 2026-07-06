/**
 * Connections settings section — CRUD connections + approval history.
 * Supports create, edit, and delete with modal forms.
 */

import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from '../../config'
import { SettingsCard } from '../SettingsCard'
import { DropdownMenu as CustomDropdown } from '../DropdownMenu'

interface Connection {
  id: string
  from: string
  to: string
  type: string
  label: string
  description: string
  active: boolean
  auto_trigger?: { on_status: string; timeout_s: number } | null
}

interface EscalationRecord {
  id: string
  task_id: string
  from: string
  from_name?: string
  to: string
  to_name?: string
  reason: string
  status: string
  timestamp: string
  resolved_at: string | null
  resolution: string
}

interface KanbanStatus {
  value: string
  name: string
}

export function ConnectionsSection({ wsOn }: { wsOn?: (type: string, handler: (data: any) => void) => () => void }) {
  const [connections, setConnections] = useState<Connection[]>([])
  const [history, setHistory] = useState<EscalationRecord[]>([])
  const [otdels, setOtdels] = useState<{ id: string; name: string }[]>([])
  const [kanbanStatuses, setKanbanStatuses] = useState<KanbanStatus[]>([])
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<Connection | null>(null)
  const [form, setForm] = useState({
    from: '', to: '', label: '', description: '',
    autoOnStatus: 'blocked', autoTimeoutMin: '60',
  })
  const [saving, setSaving] = useState(false)

  const loadConnections = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/connections`)
      if (res.ok) { const data = await res.json(); setConnections(data.connections || []) }
    } catch {}
  }, [])

  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/connections/history`)
      if (res.ok) { const data = await res.json(); setHistory(data.history || []) }
    } catch {}
  }, [])

  const loadOtdels = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/otdels`)
      if (res.ok) {
        const data = await res.json()
        setOtdels((data.otdels || []).map((o: any) => ({ id: o.otdelid, name: o.name })))
      }
    } catch {}
  }, [])

  const loadKanbanStatuses = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/kanban/statuses`)
      if (res.ok) {
        const data = await res.json()
        setKanbanStatuses(data.statuses || [])
      }
    } catch {}
  }, [])

  // Endpoint options for the connection form: every otdel + the
  // virtual "primary agent" slot (whose id is `agent:primary`).
  const endpointOptions = [
    { id: 'agent:primary', name: 'Главный агент' },
    ...otdels,
  ]

  const endpointName = (id: string) =>
    id === 'agent:primary'
      ? 'Главный агент'
      : otdels.find(o => o.id === id)?.name || id

  useEffect(() => {
    loadConnections(); loadHistory(); loadOtdels(); loadKanbanStatuses()
  }, [loadConnections, loadHistory, loadOtdels, loadKanbanStatuses])

  useEffect(() => {
    if (!wsOn) return
    const unsubs = [
      wsOn('connections:created', () => loadConnections()),
      wsOn('connections:updated', () => loadConnections()),
      wsOn('connections:deleted', () => { loadConnections(); loadHistory() }),
      wsOn('connections:approval_started', () => loadHistory()),
      wsOn('connections:approval_complete', () => loadHistory()),
    ]
    return () => { unsubs.forEach(u => u()) }
  }, [wsOn, loadConnections, loadHistory])

  const otdelName = (id: string) => endpointName(id)

  const openCreate = () => {
    setEditing(null)
    setForm({
      from: '', to: '', label: '', description: '',
      autoOnStatus: 'blocked', autoTimeoutMin: '60',
    })
    setShowModal(true)
  }

  const openEdit = (conn: Connection) => {
    setEditing(conn)
    setForm({
      from: conn.from, to: conn.to,
      label: conn.label, description: conn.description,
      autoOnStatus: conn.auto_trigger?.on_status || 'blocked',
      autoTimeoutMin: conn.auto_trigger
        ? String(Math.round(conn.auto_trigger.timeout_s / 60))
        : '60',
    })
    setShowModal(true)
  }

  const handleSave = async () => {
    if (!form.from || !form.to) return
    // Type is implementation detail: every connection defaults to
    // `approval` so auto_trigger semantics apply. The user only
    // chooses label + description + auto-escalation settings.
    const payload: any = {
      type: 'approval',
      label: form.label, description: form.description,
    }
    const minutes = Number(form.autoTimeoutMin) || 0
    if (minutes > 0) {
      payload.auto_trigger = {
        on_status: form.autoOnStatus,
        timeout_s: minutes * 60,
      }
    } else {
      payload.auto_trigger = null
    }

    setSaving(true)
    try {
      if (editing) {
        // Update existing
        await fetch(`${API_BASE}/api/connections/${editing.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
      } else {
        // Create new
        await fetch(`${API_BASE}/api/connections`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            from_ref: form.from, to_ref: form.to,
            label: form.label, description: form.description,
            auto_trigger: payload.auto_trigger,
          }),
        })
      }
      setShowModal(false)
      setEditing(null)
      loadConnections()
    } catch {} finally { setSaving(false) }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Удалить связь? Все связанные данные будут удалены.')) return
    try { await fetch(`${API_BASE}/api/connections/${id}`, { method: 'DELETE' }); loadConnections() } catch {}
  }

  const statusLabels: Record<string, string> = { pending: 'В процессе', completed: 'Завершено', rejected: 'Отклонено' }

  return (
    <div className="settings-sections">
      <SettingsCard title="Связи между отделами">
        <p className="settings-hint">Настройте структурные связи между отделами для утверждения и совместной работы</p>
        <div className="settings-divider-thin" />

        {connections.length === 0 ? (
          <div className="settings-empty-state">
            <p>Связи не настроены</p>
            <p className="settings-empty-hint">Создайте первую связь между отделами</p>
          </div>
        ) : (
          <div className="connections-list">
            {connections.map(conn => (
              <div key={conn.id} className="connection-row">
                <span className="connection-from">{otdelName(conn.from)}</span>
                <span className="connection-arrow">→</span>
                <span className="connection-to">{otdelName(conn.to)}</span>
                {conn.label && <span className="connection-label">{conn.label}</span>}
                {conn.auto_trigger && (
                  <span
                    className="connection-auto-tag"
                    title={`Авто-эскалация: задачи в статусе "${conn.auto_trigger.on_status}" дольше ${Math.round(conn.auto_trigger.timeout_s / 60)} мин → ${otdelName(conn.to)}`}
                  >
                    ⚡ {conn.auto_trigger.on_status} &gt; {Math.round(conn.auto_trigger.timeout_s / 60)} мин
                  </span>
                )}
                <button className="btn-action btn-action-edit"
                  onClick={() => openEdit(conn)} title="Редактировать">✏️</button>
                <button className="btn-action btn-action-delete" onClick={() => handleDelete(conn.id)} title="Удалить">×</button>
              </div>
            ))}
          </div>
        )}

        <button className="settings-btn-primary" style={{ marginTop: '12px' }} onClick={openCreate}>+ Добавить связь</button>
      </SettingsCard>

      {/* Create/Edit modal */}
      {showModal && (
        <div className="modal-overlay" onClick={() => { setShowModal(false); setEditing(null) }}>
          <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: 480 }}>
            <div className="modal-header">
              <h2>{editing ? 'Редактировать связь' : 'Новая связь'}</h2>
              <button className="modal-close" onClick={() => { setShowModal(false); setEditing(null) }}>×</button>
            </div>
            <div className="modal-body">
              <div className="settings-field">
                <label>Откуда</label>
                <CustomDropdown
                  value={form.from}
                  onChange={v => setForm(f => ({ ...f, from: v }))}
                  options={[
                    { value: '', label: '— выбрать —' },
                    ...endpointOptions.map(o => ({ value: o.id, label: o.name })),
                  ]}

                  disabled={!!editing}
                />
              </div>
              <div className="settings-field">
                <label>Куда</label>
                <CustomDropdown
                  value={form.to}
                  onChange={v => setForm(f => ({ ...f, to: v }))}
                  options={[
                    { value: '', label: '— выбрать —' },
                    ...endpointOptions.filter(o => o.id !== form.from).map(o => ({ value: o.id, label: o.name })),
                  ]}

                  disabled={!!editing}
                />
              </div>
              <div className="settings-field">
                <label>Название</label>
                <input className="settings-input" placeholder="Ревью кода, Кооперация..."
                  value={form.label} onChange={e => setForm(f => ({ ...f, label: e.target.value }))} />
              </div>
              <div className="settings-field">
                <label>Описание</label>
                <input className="settings-input" placeholder="Описание связи..."
                  value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
              </div>

              <div className="settings-divider-thin" style={{ margin: '14px 0' }} />
              <div className="settings-field-group-title">
                Авто-эскалация задач
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label className="settings-field-label">Статус задачи</label>
                  <CustomDropdown
                    value={form.autoOnStatus}
                    onChange={v => setForm(f => ({ ...f, autoOnStatus: v }))}
                    options={[
                      ...kanbanStatuses.map(s => ({ value: s.value, label: s.name })),
                    ]}
                  />
                </div>
                <div>
                  <label className="settings-field-label">Через (минут)</label>
                  <input
                    type="number"
                    min={1}
                    className="settings-input"
                    placeholder="60"
                    value={form.autoTimeoutMin}
                    onChange={e => setForm(f => ({ ...f, autoTimeoutMin: e.target.value }))}
                  />
                </div>
              </div>
              <p className="settings-hint" style={{ marginTop: 6 }}>
                Задача в указанном статусе, которая висит дольше заданного времени,
                будет автоматически перенесена в целевой отдел.
                Оставьте поле пустым или 0, чтобы отключить авто-эскалацию.
              </p>
            </div>
            <div className="modal-footer">
              <button className="settings-btn-secondary" onClick={() => { setShowModal(false); setEditing(null) }}>Отмена</button>
              <button className="settings-btn-primary" disabled={saving || !form.from || !form.to} onClick={handleSave}>
                {saving ? 'Сохранение...' : editing ? 'Сохранить' : 'Создать'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Escalation history */}
      <SettingsCard title="История утверждений">
        {history.length === 0 ? (
          <p className="settings-hint">Утверждений пока не было</p>
        ) : (
          <div className="approval-history">
            {history.slice(0, 20).map(rec => (
              <div key={rec.id} className={`approval-row status-${rec.status}`}>
                <span className="approval-task">{rec.task_id}</span>
                <span className="approval-from">{rec.from_name || otdelName(rec.from)}</span>
                <span className="approval-arrow">→</span>
                <span className="approval-to">{rec.to_name || otdelName(rec.to)}</span>
                <span className="approval-reason">{rec.reason}</span>
                <span className={`approval-status status-${rec.status}`}>{statusLabels[rec.status] || rec.status}</span>
              </div>
            ))}
          </div>
        )}
      </SettingsCard>
    </div>
  )
}