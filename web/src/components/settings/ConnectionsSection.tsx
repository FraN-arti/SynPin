/**
 * Connections settings section — CRUD connections + escalation history.
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
}

interface EscalationRecord {
  id: string
  task_id: string
  from: string
  to: string
  reason: string
  status: string
  timestamp: string
  resolved_at: string | null
  resolution: string
}

export function ConnectionsSection({ wsOn }: { wsOn?: (type: string, handler: (data: any) => void) => () => void }) {
  const [connections, setConnections] = useState<Connection[]>([])
  const [history, setHistory] = useState<EscalationRecord[]>([])
  const [otdels, setOtdels] = useState<{ id: string; name: string }[]>([])
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<Connection | null>(null)
  const [form, setForm] = useState({ from: '', to: '', type: 'escalation', label: '', description: '' })
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

  useEffect(() => {
    loadConnections(); loadHistory(); loadOtdels()
  }, [loadConnections, loadHistory, loadOtdels])

  useEffect(() => {
    if (!wsOn) return
    const unsubs = [
      wsOn('connections:created', () => loadConnections()),
      wsOn('connections:updated', () => loadConnections()),
      wsOn('connections:deleted', () => { loadConnections(); loadHistory() }),
      wsOn('connections:escalation_started', () => loadHistory()),
      wsOn('connections:escalation_complete', () => loadHistory()),
    ]
    return () => { unsubs.forEach(u => u()) }
  }, [wsOn, loadConnections, loadHistory])

  const otdelName = (id: string) => otdels.find(o => o.id === id)?.name || id

  const openCreate = () => {
    setEditing(null)
    setForm({ from: '', to: '', type: 'escalation', label: '', description: '' })
    setShowModal(true)
  }

  const openEdit = (conn: Connection) => {
    setEditing(conn)
    setForm({ from: conn.from, to: conn.to, type: conn.type, label: conn.label, description: conn.description })
    setShowModal(true)
  }

  const handleSave = async () => {
    if (!form.from || !form.to) return
    setSaving(true)
    try {
      if (editing) {
        // Update existing
        await fetch(`${API_BASE}/api/connections/${editing.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ label: form.label, description: form.description, type: form.type }),
        })
      } else {
        // Create new
        await fetch(`${API_BASE}/api/connections`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            from_otdel: form.from, to_otdel: form.to,
            type: form.type, label: form.label, description: form.description,
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

  const typeLabels: Record<string, string> = { peer: 'Равноправная', escalation: 'Эскалация', delegation: 'Делегирование' }
  const statusLabels: Record<string, string> = { pending: 'В процессе', completed: 'Завершено', rejected: 'Отклонено' }

  return (
    <div className="settings-sections">
      <SettingsCard title="Связи между отделами">
        <p className="settings-hint">Настройте структурные связи между отделами для эскалации и делегирования</p>
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
                <span className="connection-type-badge" data-type={conn.type}>{typeLabels[conn.type] || conn.type}</span>
                <span className="connection-from">{otdelName(conn.from)}</span>
                <span className="connection-arrow">→</span>
                <span className="connection-to">{otdelName(conn.to)}</span>
                {conn.label && <span className="connection-label">{conn.label}</span>}
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
                <select className="settings-input" value={form.from} onChange={e => setForm(f => ({ ...f, from: e.target.value }))}
                  disabled={!!editing}>
                  <option value="">— выбрать отдел —</option>
                  {otdels.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
              </div>
              <div className="settings-field">
                <label>Куда</label>
                <select className="settings-input" value={form.to} onChange={e => setForm(f => ({ ...f, to: e.target.value }))}
                  disabled={!!editing}>
                  <option value="">— выбрать отдел —</option>
                  {otdels.filter(o => o.id !== form.from).map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                </select>
              </div>
              <div className="settings-field">
                <label>Тип связи</label>
                <CustomDropdown value={form.type} onChange={v => setForm(f => ({ ...f, type: v }))}
                  options={[
                    { value: 'escalation', label: 'Эскалация (вверх)' },
                    { value: 'delegation', label: 'Делегирование (вниз)' },
                    { value: 'peer', label: 'Равноправная' },
                  ]} />
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
      <SettingsCard title="История эскалаций">
        {history.length === 0 ? (
          <p className="settings-hint">Эскалаций пока не было</p>
        ) : (
          <div className="escalation-history">
            {history.slice(0, 20).map(rec => (
              <div key={rec.id} className={`escalation-row status-${rec.status}`}>
                <span className="escalation-task">{rec.task_id}</span>
                <span className="escalation-from">{otdelName(rec.from)}</span>
                <span className="escalation-arrow">→</span>
                <span className="escalation-to">{otdelName(rec.to)}</span>
                <span className="escalation-reason">{rec.reason}</span>
                <span className={`escalation-status status-${rec.status}`}>{statusLabels[rec.status] || rec.status}</span>
              </div>
            ))}
          </div>
        )}
      </SettingsCard>
    </div>
  )
}
