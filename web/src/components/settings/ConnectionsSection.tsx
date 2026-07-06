/**
 * Connections settings section — CRUD connections.
 * Supports create, edit, and delete with modal forms.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { API_BASE } from '../../config'
import { SettingsCard } from '../SettingsCard'
import { DropdownMenu as CustomDropdown } from '../DropdownMenu'
import { LoadingSpinner } from '../LoadingSpinner'

interface Connection {
  id: string
  from: string
  to: string
  type: string
  label: string
  description: string
  active: boolean
}

export function ConnectionsSection({ wsOn }: { wsOn?: (type: string, handler: (data: any) => void) => () => void }) {
  const [connections, setConnections] = useState<Connection[]>([])
  const [otdels, setOtdels] = useState<{ id: string; name: string }[]>([])
  const [loaded, setLoaded] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [editing, setEditing] = useState<Connection | null>(null)
  const [form, setForm] = useState({
    from: '', to: '', label: '', description: '',
  })
  const [saving, setSaving] = useState(false)

  const loadConnections = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/connections`)
      if (res.ok) { const data = await res.json(); setConnections(data.connections || []) }
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

  // Endpoint options for the connection form: every otdel + the
  // virtual "primary agent" slot (whose id is `agent:primary`).
  const endpointOptions = [
    { id: 'agent:primary', name: 'Главный агент' },
    ...otdels,
  ]

  const endpointName = (id: string) => {
    if (id === 'agent:primary') return 'Главный агент'
    const bare = id.replace(/^otdel:/, '')
    return otdels.find(o => o.id === bare)?.name || id
  }

  useEffect(() => {
    Promise.all([loadConnections(), loadOtdels()]).then(() => setLoaded(true))
  }, [loadConnections, loadOtdels])

  useEffect(() => {
    if (!wsOn) return
    const unsubs = [
      wsOn('connections:created', () => loadConnections()),
      wsOn('connections:updated', () => loadConnections()),
      wsOn('connections:deleted', () => loadConnections()),
    ]
    return () => { unsubs.forEach(u => u()) }
  }, [wsOn, loadConnections])

  const otdelName = (id: string) => endpointName(id)

  const openCreate = () => {
    setEditing(null)
    setForm({ from: '', to: '', label: '', description: '' })
    setShowModal(true)
  }

  const openEdit = (conn: Connection) => {
    setEditing(conn)
    setForm({
      from: conn.from, to: conn.to,
      label: conn.label, description: conn.description,
    })
    setShowModal(true)
  }

  const handleSave = async () => {
    if (!form.from || !form.to) return

    setSaving(true)
    try {
      if (editing) {
        await fetch(`${API_BASE}/api/connections/${editing.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            label: form.label, description: form.description,
          }),
        })
      } else {
        await fetch(`${API_BASE}/api/connections`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            from_ref: form.from, to_ref: form.to,
            label: form.label, description: form.description,
          }),
        })
      }
      setShowModal(false)
      setEditing(null)
      loadConnections()
    } catch {} finally { setSaving(false) }
  }

  const handleDelete = async (id: string) => {
    try { await fetch(`${API_BASE}/api/connections/${id}`, { method: 'DELETE' }); loadConnections() } catch {}
  }

  // Hold-to-delete state: tracks which connection is being held
  const [holdTarget, setHoldTarget] = useState<string | null>(null)
  const holdTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const holdProgressRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [holdProgress, setHoldProgress] = useState(0)

  const startHold = (id: string) => {
    setHoldTarget(id)
    setHoldProgress(0)
    let progress = 0
    holdProgressRef.current = setInterval(() => {
      progress += 2
      setHoldProgress(progress)
      if (progress >= 100) {
        if (holdProgressRef.current) clearInterval(holdProgressRef.current)
      }
    }, 30)
    holdTimerRef.current = setTimeout(() => {
      if (holdProgressRef.current) clearInterval(holdProgressRef.current)
      setHoldTarget(null)
      setHoldProgress(0)
      handleDelete(id)
    }, 1500)
  }

  const cancelHold = () => {
    if (holdTimerRef.current) clearTimeout(holdTimerRef.current)
    if (holdProgressRef.current) clearInterval(holdProgressRef.current)
    setHoldTarget(null)
    setHoldProgress(0)
  }

  return (
    <div className="settings-sections">
      <SettingsCard title="Связи между отделами">
        {!loaded ? (
          <LoadingSpinner text="Загрузка связей..." />
        ) : <>
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
                <button className="icon-btn"
                  onClick={() => openEdit(conn)} title="Редактировать">✏️</button>
                <button
                  className={`icon-btn icon-btn-danger ${holdTarget === conn.id ? 'holding' : ''}`}
                  onMouseDown={() => startHold(conn.id)}
                  onMouseUp={cancelHold}
                  onMouseLeave={cancelHold}
                  title="Зажмите для удаления"
                >
                  {holdTarget === conn.id ? (
                    <svg width="16" height="16" viewBox="0 0 20 20">
                      <circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.25" />
                      <circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" strokeWidth="2"
                        strokeDasharray="44 100"
                        strokeDashoffset={44 - (holdProgress * 0.44)}
                        strokeLinecap="round"
                        transform="rotate(-90 10 10)" />
                    </svg>
                  ) : '×'}
                </button>
              </div>
            ))}
          </div>
        )}

        <button className="settings-btn-primary" style={{ marginTop: '12px' }} onClick={openCreate}>+ Добавить связь</button>
        </>}
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
                <textarea className="settings-input" placeholder="Описание связи..."
                  rows={2} style={{ resize: 'none', overflow: 'hidden', minHeight: 40, maxHeight: 120 }}
                  value={form.description}
                  onChange={e => {
                    setForm(f => ({ ...f, description: e.target.value }))
                    const el = e.target
                    el.style.height = 'auto'
                    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
                  }}
                />
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
    </div>
  )
}