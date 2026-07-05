/**
 * Departments (Otdels) settings section.
 * Extracted from SettingsPage.tsx (lines 2323-2510).
 *
 * Hosts a single "Протокол отделов" block (retry limit). The retry
 * behaviour is GLOBAL — every otdel shares the same knob — so it lives
 * here, not in OtdelSettingsPanel.
 */

import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from '../../config'
import { DropdownMenu } from '../DropdownMenu'
import { LoadingSpinner } from '../LoadingSpinner'
import { ColorPicker } from '../ColorPicker'
import { SettingsCard } from '../SettingsCard'
import { Toggle } from './Toggle'

interface Otdel {
  otdelid: string
  name: string
  description: string
  color: string
  mentor_role: string
  escalation: string
  agent_count: number
}

export function DepartmentsSection({ onDepartmentsChange }: { onDepartmentsChange?: () => void }) {
  const [otdels, setOtdels] = useState<Otdel[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [editing, setEditing] = useState<Otdel | null>(null)
  const [roles, setRoles] = useState<{ rolesid: string; name: string }[]>([])
  const [form, setForm] = useState({ name: '', description: '', color: '#f97316', mentor_role: '', escalation: '' })
  const [saving, setSaving] = useState(false)

  const loadOtdels = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/otdels`)
      const data = await res.json()
      setOtdels(data.otdels || [])
    } catch {}
    finally { setLoading(false) }
  }

  useEffect(() => {
    loadOtdels()
    fetch(`${API_BASE}/api/roles`).then(r => r.json()).then(d => setRoles(d.roles || [])).catch((e) => console.error('[departments] load roles failed:', e))
  }, [])

  const resetForm = () => setForm({ name: '', description: '', color: '#f97316', mentor_role: '', escalation: '' })

  const openCreate = () => { resetForm(); setShowCreate(true) }
  const openEdit = (otdel: Otdel) => {
    setForm({ name: otdel.name, description: otdel.description, color: otdel.color || '#f97316', mentor_role: otdel.mentor_role || '', escalation: otdel.escalation || '' })
    setEditing(otdel)
  }

  const handleCreate = async () => {
    if (!form.name.trim()) return
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/api/otdels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name.trim(),
          description: form.description,
          color: form.color,
          mentor_role: form.mentor_role,
          escalation: form.escalation,
        }),
      })
      if (res.ok) {
        await loadOtdels()
        setShowCreate(false)
        resetForm()
        onDepartmentsChange?.()
      }
    } catch {} finally { setSaving(false) }
  }

  const handleUpdate = async () => {
    if (!editing || !form.name.trim()) return
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/api/otdels/${editing.otdelid}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name.trim(),
          description: form.description,
          color: form.color,
          mentor_role: form.mentor_role,
          escalation: form.escalation,
        }),
      })
      if (res.ok) {
        await loadOtdels()
        setEditing(null)
        resetForm()
        onDepartmentsChange?.()
      }
    } catch {} finally { setSaving(false) }
  }

  const handleDelete = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/otdels/${id}`, { method: 'DELETE' })
      if (res.ok) {
        await loadOtdels()
        onDepartmentsChange?.()
      }
    } catch {}
  }

  const isModalOpen = showCreate || !!editing

  const renderModal = () => (
    <div className="modal-overlay" onClick={() => { setShowCreate(false); setEditing(null); resetForm() }}>
      <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: 520 }}>
        <div className="modal-header">
          <h2>{editing ? 'Настройки отдела' : 'Новый отдел'}</h2>
          <button className="modal-close" onClick={() => { setShowCreate(false); setEditing(null); resetForm() }}>×</button>
        </div>
        <div className="modal-body">
          <div className="settings-field">
            <label>Название *</label>
            <input className="settings-input" placeholder="Backend, Frontend, DevOps..."
              value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
          </div>
          <div className="settings-field">
            <label>Описание</label>
            <textarea className="settings-input" rows={3} placeholder="Что делает этот отдел..."
              value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
          </div>
          <div className="settings-field">
            <label>Цвет</label>
            <div className="department-color-row">
              <ColorPicker
                value={form.color}
                onChange={c => setForm(f => ({ ...f, color: c }))}
              />
              <span className="department-color-value">{form.color}</span>
            </div>
          </div>
          <div className="settings-field">
            <label>Ментор (роль)</label>
            <DropdownMenu
              value={form.mentor_role}
              onChange={v => setForm(f => ({ ...f, mentor_role: v }))}
              options={[
                { value: '', label: 'Не назначен' },
                ...roles.map(r => ({ value: r.rolesid, label: r.name })),
              ]}
             
            />
          </div>
          <div className="settings-field">
            <label>Утверждение</label>
            <input className="settings-input" placeholder="Пока не реализовано"
              value={form.escalation} onChange={e => setForm(f => ({ ...f, escalation: e.target.value }))} disabled />
          </div>
        </div>
        <div className="modal-footer">
          <button className="settings-btn-secondary" onClick={() => { setShowCreate(false); setEditing(null); resetForm() }}>Отмена</button>
          <button className="settings-btn-primary" disabled={saving || !form.name.trim()} onClick={editing ? handleUpdate : handleCreate}>
            {saving ? 'Сохранение...' : editing ? 'Сохранить' : 'Создать'}
          </button>
        </div>
      </div>
    </div>
  )

  if (loading) return <LoadingSpinner text="Загрузка..." />

  return (
    <div className="settings-sections">
      <ProtocolBlock />
      <div className="section-header-row">
        <span className="section-count">{otdels.length} отделов</span>
        <button className="settings-btn-primary" onClick={openCreate}>+ Создать отдел</button>
      </div>

      {otdels.length === 0 && (
        <div className="settings-empty-state">
          <p>Отделы не созданы</p>
          <p className="settings-empty-hint">Создайте первый отдел для организации командной работы агентов</p>
        </div>
      )}

      {otdels.map(otdel => (
        <div key={otdel.otdelid} className="settings-card department-card">
          <div className="department-header">
            <div className="department-identity">
              <span className="department-color-dot" style={{ background: otdel.color }} />
              <div>
                <span className="department-name">{otdel.name}</span>
                <span className="department-meta">{otdel.mentor_role ? `Ментор: ${roles.find(r => r.rolesid === otdel.mentor_role)?.name || otdel.mentor_role}` : 'Без ментора'} · {otdel.agent_count} агентов</span>
              </div>
            </div>
            <div className="department-actions">
              <button className="settings-btn-secondary" onClick={() => openEdit(otdel)}>Настройки</button>
              <button className="settings-btn-danger" onClick={() => handleDelete(otdel.otdelid)}>Удалить</button>
            </div>
          </div>
          {otdel.description && <p className="department-desc">{otdel.description}</p>}
        </div>
      ))}

      {isModalOpen && renderModal()}
    </div>
  )
}

// ── Protocol Block (retry limit) ─────────────────────────────────────────────
//
// Lives at the TOP of the section so the user sees it before any otdel
// noise. Keeps the section header anchored to "Отделы" while signalling
// that head-protocol knobs are global across the install.

function ProtocolBlock() {
  const [enabled, setEnabled] = useState<boolean | null>(null)
  const [max, setMax] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/protocol/settings`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setEnabled(Boolean(data.retry_limit_enabled))
      setMax(typeof data.max_retries === 'number' ? data.max_retries : 3)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => { load() }, [load])

  // Fire-and-forget on change (mirrors KanbanSection's pattern). Value
  // is the source of truth; the persist call returns whatever the server
  // echoes back so we stay in sync with last-write-wins ordering and
  // any field-level clamping the backend applies.
  const persist = useCallback((patch: Record<string, unknown>) => {
    return fetch(`${API_BASE}/api/protocol/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    }).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json()
    }).catch(e => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  const onToggle = (next: boolean) => {
    const prev = enabled
    setEnabled(next)
    void persist({ retry_limit_enabled: next }).then(data => {
      if (!data) return
      // Server is the authority — reflect whatever it returned.
      setEnabled(Boolean(data.retry_limit_enabled))
      setMax(typeof data.max_retries === 'number' ? data.max_retries : 3)
    }).catch(() => setEnabled(prev))
  }

  const onMaxChange = (raw: number) => {
    if (Number.isNaN(raw)) return
    const next = Math.max(1, Math.min(10, Math.floor(raw)))
    setMax(next)
    void persist({ max_retries: next })
  }

  const loading = enabled === null || max === null

  return (
    <SettingsCard title="Протокол отделов">
      <p className="settings-hint">
        Глобальные правила работы глав отделов. Применяются ко всем отделам сразу.
      </p>
      <div className="settings-divider-thin" />
      {loading ? (
        <LoadingSpinner text="Загрузка..." />
      ) : (
        <>
          <Toggle
            label="Включить лимит ретраев"
            checked={enabled!}
            onChange={(v) => onToggle(v)}
          />
          <p className="settings-hint" style={{ marginLeft: 24, marginTop: -8 }}>
            {enabled
              ? 'Глава обязана принять решение после исчерпания попыток.'
              : 'Лимит выключен. Решение остановиться принимает глава сама.'}
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12 }}>
            <label
              htmlFor="protocol-max-retries"
              style={{ color: 'var(--text-secondary)', fontSize: 13, whiteSpace: 'nowrap' }}
            >
              Максимум попыток ретрая
            </label>
            <input
              id="protocol-max-retries"
              type="number"
              min={1}
              max={10}
              className="settings-input"
              value={max!}
              onChange={(e) => onMaxChange(Number(e.target.value))}
              disabled={!enabled}
              style={{ width: 60, padding: '4px 6px', fontSize: 13 }}
            />
            <span style={{ color: 'var(--gray-500)', fontSize: 12 }}>
              (максимум: 10)
            </span>
          </div>
          {error && (
            <div style={{ color: 'var(--red, #f87171)', fontSize: 12, marginTop: 8 }}>
              {error}
            </div>
          )}
        </>
      )}
    </SettingsCard>
  )
}
