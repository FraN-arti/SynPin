/**
 * Kanban settings section — columns, labels, widget, board settings.
 * Extracted from SettingsPage.tsx (lines 2764-3699).
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { API_BASE } from '../../config'
import { SettingsCard } from '../SettingsCard'
import { MultiSelectMenu } from '../MultiSelectMenu'
import { DropdownMenu as CustomDropdown } from '../DropdownMenu'
import { LoadingSpinner } from '../LoadingSpinner'
import { useUndoWithProgress } from '../../hooks/useUndoWithProgress'
import { Toggle } from './Toggle'

// ── Interfaces ─────────────────────────────────────────────────────

interface KanbanColumnItem {
  id: string
  label: string
  description: string
  color: string
  order: number
  enabled: boolean
  status?: string
}

interface KanbanLabelItem {
  id: string
  name: string
  color: string
  text_color: string
  description?: string
}

interface KanbanWidgetConfigData {
  mode: string
  max_items: number
  show_columns: string[]
  show_deadline: boolean
  show_department: boolean
  compact: boolean
}

interface KanbanColumnForWidget {
  id: string
  label: string
  status: string | null
  color: string
  enabled: boolean
}

// ── KanbanSection (main) ───────────────────────────────────────────

export function KanbanSection() {
  const [stats, setStats] = useState<Record<string, unknown> | null>(null)
  const [boardSettingsKey] = useState(0)

  useEffect(() => {
    fetch(`${API_BASE}/api/kanban/stats`)
      .then(r => r.json())
      .then(setStats)
      .catch(() => {})
  }, [])

  return (
    <div className="settings-sections">
      {/* Stats Overview */}
      <SettingsCard title="Глобальный Канбан">
        <p style={{ color: 'var(--gray-500)', fontSize: '14px', lineHeight: '1.6', marginBottom: '16px' }}>
          Глобальная доска задач для управления работой всех отделов и агентов.
        </p>
        {stats && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '16px' }}>
            <div style={{ padding: '12px', background: 'var(--gray-900)', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: '700', color: 'var(--text)' }}>{stats.total as number}</div>
              <div style={{ fontSize: '11px', color: 'var(--gray-500)' }}>Всего задач</div>
            </div>
            <div style={{ padding: '12px', background: 'var(--gray-900)', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: '700', color: 'var(--orange)' }}>{(stats.by_status as Record<string, number>)?.in_progress || 0}</div>
              <div style={{ fontSize: '11px', color: 'var(--gray-500)' }}>В работе</div>
            </div>
            <div style={{ padding: '12px', background: 'var(--gray-900)', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: '700', color: 'var(--yellow)' }}>{(stats.by_status as Record<string, number>)?.review || 0}</div>
              <div style={{ fontSize: '11px', color: 'var(--gray-500)' }}>На ревью</div>
            </div>
            <div style={{ padding: '12px', background: 'var(--gray-900)', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: '700', color: 'var(--green)' }}>{(stats.by_status as Record<string, number>)?.done || 0}</div>
              <div style={{ fontSize: '11px', color: 'var(--gray-500)' }}>Выполнено</div>
            </div>
          </div>
        )}
      </SettingsCard>

      <KanbanColumnsConfig />

      {/* Status Reference */}
      <SettingsCard title="Справочник статусов">
        <p className="settings-hint">Какие статусы использует система и что они означают</p>
        <div className="settings-divider-thin" />
        <div className="status-reference-grid">
          <div className="status-ref-item">
            <span className="status-ref-badge" style={{ background: 'rgba(107,114,128,0.2)', color: '#9ca3af' }}>BACKLOG</span>
            <span className="status-ref-desc">Создан, ожидает назначения</span>
          </div>
          <div className="status-ref-item">
            <span className="status-ref-badge" style={{ background: 'rgba(59,130,246,0.2)', color: '#60a5fa' }}>TODO</span>
            <span className="status-ref-desc">Назначен, готов к выполнению</span>
          </div>
          <div className="status-ref-item">
            <span className="status-ref-badge" style={{ background: 'rgba(168,85,247,0.2)', color: '#c084fc' }}>READY</span>
            <span className="status-ref-desc">В очереди на выполнение</span>
          </div>
          <div className="status-ref-item">
            <span className="status-ref-badge" style={{ background: 'rgba(249,115,22,0.2)', color: '#fb923c' }}>IN PROGRESS</span>
            <span className="status-ref-desc">Агенты работают над задачей</span>
          </div>
          <div className="status-ref-item">
            <span className="status-ref-badge" style={{ background: 'rgba(245,158,11,0.2)', color: '#fbbf24' }}>REVIEW</span>
            <span className="status-ref-desc">Готово, глава проверяет</span>
          </div>
          <div className="status-ref-item">
            <span className="status-ref-badge" style={{ background: 'rgba(236,72,153,0.2)', color: '#f472b6' }}>REVISION</span>
            <span className="status-ref-desc">Отправлено на доработку</span>
          </div>
          <div className="status-ref-item">
            <span className="status-ref-badge" style={{ background: 'rgba(239,68,68,0.2)', color: '#f87171' }}>BLOCKED</span>
            <span className="status-ref-desc">Заблокировано, нужна помощь человека</span>
          </div>
          <div className="status-ref-item">
            <span className="status-ref-badge" style={{ background: 'rgba(34,197,94,0.2)', color: '#4ade80' }}>DONE</span>
            <span className="status-ref-desc">Выполнено и принято</span>
          </div>
          <div className="status-ref-item">
            <span className="status-ref-badge" style={{ background: 'rgba(107,114,128,0.3)', color: '#9ca3af' }}>ARCHIVE</span>
            <span className="status-ref-desc">В архиве, скрыто с доски</span>
          </div>
        </div>
      </SettingsCard>

      {/* Board Settings */}
      <BoardSettingsConfig refreshKey={boardSettingsKey} />

      <KanbanLabelsConfig />

      {/* Widget Config + Bulk Cleanup — side by side */}
      <div className="kanban-settings-row">
        <KanbanWidgetConfig />
        <KanbanBulkCleanup />
      </div>

      {/* Automation — Coming Soon */}
      <SettingsCard title="Автоматизация" style={{ opacity: 0.5, pointerEvents: 'none' }}>
        <p className="settings-hint">Автоматическое назначение, утверждение и передача задач между отделами</p>
        <Toggle label="Авто назначение главы" defaultChecked={true} onChange={() => {}} />
        <Toggle label="Summon при завершении" defaultChecked={false} onChange={() => {}} />
        <Toggle label="Утверждение при простое" defaultChecked={false} onChange={() => {}} />
        <Toggle label="Запрос человека при блоке" defaultChecked={false} onChange={() => {}} />
      </SettingsCard>
    </div>
  )
}

// ── KanbanColumnsConfig ────────────────────────────────────────────

function KanbanColumnsConfig() {
  const DEFAULT_COLUMN_AUTO = '__auto__'
  const [columns, setColumns] = useState<KanbanColumnItem[]>([])
  const [defaultColumn, setDefaultColumn] = useState<string>(DEFAULT_COLUMN_AUTO)
  const [autoArchiveDays, setAutoArchiveDays] = useState<number>(30)
  const [autoDeleteColumns, setAutoDeleteColumns] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [savedId, setSavedId] = useState<string | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { pendingDelete, undoProgress, start: startUndo, undo: undoDelete } =
    useUndoWithProgress<KanbanColumnItem>({
      onExpire: ({ id }) => {
        fetch(`${API_BASE}/api/kanban/config/columns/${id}`, { method: 'DELETE' })
          .catch(e => console.error('[kanban] delete column error:', e))
      },
      onUndo: ({ id: _id, index, extras }) => {
        const col: KanbanColumnItem = extras ?? ({ id: _id, label: _id } as KanbanColumnItem)
        setColumns(prev => {
          const newCols = [...prev]
          newCols.splice(index, 0, col)
          return newCols
        })
      },
    })

  useEffect(() => {
    fetch(`${API_BASE}/api/kanban/config/columns`)
      .then(r => r.json())
      .then(data => setColumns(Array.isArray(data) ? data : data.columns || []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetch(`${API_BASE}/api/kanban/config/widget`)
      .then(r => r.json())
      .then(data => setDefaultColumn(data?.default_column || DEFAULT_COLUMN_AUTO))
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetch(`${API_BASE}/api/kanban/config/settings`)
      .then(r => r.json())
      .then(data => {
        if (typeof data?.auto_archive_days === 'number') {
          setAutoArchiveDays(data.auto_archive_days)
        }
        if (Array.isArray(data?.auto_delete_from_columns)) {
          setAutoDeleteColumns(data.auto_delete_from_columns)
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [])

  const patchColumn = async (id: string, updates: Partial<KanbanColumnItem>) => {
    setSaving(true)
    setSavedId(id)
    try {
      await fetch(`${API_BASE}/api/kanban/config/columns/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      })
    } catch (e) {
      console.error('[kanban] patch column error:', e)
    } finally {
      setSaving(false)
      setTimeout(() => setSavedId(null), 600)
    }
  }

  const toggleColumn = (index: number) => {
    const col = columns[index]
    if (!col) return
    const newEnabled = !col.enabled
    setColumns(prev => prev.map((c, i) => i === index ? { ...c, enabled: newEnabled } : c))
    patchColumn(col.id, { enabled: newEnabled })
  }

  const updateColor = (index: number, color: string) => {
    const col = columns[index]
    if (!col) return
    setColumns(prev => prev.map((c, i) => i === index ? { ...c, color } : c))
    patchColumn(col.id, { color })
  }

  const updateLabel = (index: number, label: string) => {
    const col = columns[index]
    if (!col) return
    setColumns(prev => prev.map((c, i) => i === index ? { ...c, label } : c))
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      patchColumn(col.id, { label })
    }, 500)
  }

  const updateDescription = (index: number, description: string) => {
    const col = columns[index]
    if (!col) return
    setColumns(prev => prev.map((c, i) => i === index ? { ...c, description } : c))
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      patchColumn(col.id, { description })
    }, 500)
  }

  const updateStatus = (index: number, status: string) => {
    const col = columns[index]
    if (!col) return
    const newStatus = status === '' ? undefined : status
    setColumns(prev => prev.map((c, i) => i === index ? { ...c, status: newStatus } : c))
    patchColumn(col.id, { status: status === '' ? null : status } as any)
  }

  const STATUS_COLORS: Record<string, string> = {
    backlog: '#9ca3af',
    todo: '#60a5fa',
    ready: '#c084fc',
    in_progress: '#fb923c',
    review: '#fbbf24',
    revision: '#f472b6',
    blocked: '#f87171',
    archive: '#6b7280',
    done: '#4ade80',
  }

  const STATUS_OPTIONS = [
    { value: '', label: 'Не назначен' },
    ...Object.entries(STATUS_COLORS).map(([val, color]) => ({
      value: val,
      label: <span style={{ color, fontWeight: 600 }}>{val.replace('_', ' ').toUpperCase()}</span>,
    })),
  ]

  const addColumn = async () => {
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/api/kanban/config/columns`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          label: 'Новая колонка',
          description: '',
          color: '#3b82f6',
          order: columns.length,
          enabled: true,
        }),
      })
      if (res.ok) {
        const newCol = await res.json()
        setColumns(prev => [...prev, newCol])
        setSavedId(newCol.id)
        setTimeout(() => setSavedId(null), 1500)
      }
    } catch (e) {
      console.error('[kanban] add column error:', e)
    } finally {
      setSaving(false)
    }
  }

  const moveColumn = async (index: number, direction: -1 | 1) => {
    const newIndex = index + direction
    if (newIndex < 0 || newIndex >= columns.length) return

    const newCols = [...columns]
    const temp = newCols[index]!
    newCols[index] = newCols[newIndex]!
    newCols[newIndex] = temp

    newCols.forEach((c, i) => c.order = i)
    setColumns(newCols)

    try {
      await fetch(`${API_BASE}/api/kanban/config/columns`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCols),
      })
    } catch (e) {
      console.error('[kanban] move column error:', e)
    }
  }

  const deleteColumn = (colId: string) => {
    const col = columns.find(c => c.id === colId)
    if (!col) return

    const idx = columns.findIndex(c => c.id === colId)
    setColumns(prev => prev.filter(c => c.id !== colId))

    startUndo({ id: colId, label: col.label, index: idx, extras: { ...col } })
  }

  const saveDefaultColumn = useCallback(async (value: string | null) => {
    try {
      await fetch(`${API_BASE}/api/kanban/config/widget`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ default_column: value }),
      })
    } catch (e) {
      console.error('[kanban] save default column error:', e)
    }
  }, [])

  const saveAutoArchive = useCallback(async (days: number, cols: string[]) => {
    try {
      await fetch(`${API_BASE}/api/kanban/config/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          auto_archive_days: days,
          auto_delete_from_columns: cols,
        }),
      })
    } catch (e) {
      console.error('[kanban] save auto-archive error:', e)
    }
  }, [])

  const enabledColumns = columns.filter(c => c.enabled)
  const firstEnabledColumn = enabledColumns[0] ?? null
  const defaultColumnValue = defaultColumn && enabledColumns.some(c => c.id === defaultColumn)
    ? defaultColumn
    : DEFAULT_COLUMN_AUTO
  const defaultColumnOptions = [
    { value: DEFAULT_COLUMN_AUTO, label: `Первая активная (${firstEnabledColumn?.label || 'нет колонок'})` },
    ...enabledColumns.map(c => ({ value: c.id, label: c.label })),
  ]
  const handleDefaultColumnChange = (value: string) => {
    const next = value === DEFAULT_COLUMN_AUTO ? null : value
    setDefaultColumn(value)
    saveDefaultColumn(next)
  }

  return (
    <SettingsCard title="Конфигурация колонок">
      <p className="settings-hint">Настройте колонки доски: цвета, порядок, видимость</p>
      <div className="settings-divider-thin" />
      {columns.map((col, i) => (
        <div key={col.id} className={`kanban-config-row${saving && savedId === col.id ? ' saving' : ''}`}>
          <label className="kanban-color-trigger" style={{ background: col.color }} title="Изменить цвет">
            <input
              type="color"
              value={col.color}
              onChange={e => { updateColor(i, e.target.value) }}
              className="kanban-color-hidden"
            />
          </label>
          <input
            className="settings-input"
            value={col.label}
            onChange={e => updateLabel(i, e.target.value)}
            placeholder="Название"
            style={{ flex: '0 1 140px', minWidth: 80 }}
          />
          <input
            className="settings-input"
            value={col.description || ''}
            onChange={e => updateDescription(i, e.target.value)}
            placeholder="Описание (для промпта агентов)"
            style={{ flex: '1 1 200px', minWidth: 100, fontSize: '12px', opacity: 0.7 }}
          />
          <CustomDropdown
            value={col.status || ''}
            onChange={v => updateStatus(i, v)}
            options={STATUS_OPTIONS}
          />
          <label className="settings-toggle" style={{ margin: 0, fontSize: '12px' }}>
            <input
              type="checkbox"
              checked={col.enabled}
              onChange={() => toggleColumn(i)}
            />
          </label>
          <button
            className="widget-remove-btn"
            onClick={() => deleteColumn(col.id)}
            title="Удалить колонку"
          >×</button>
          <button
            className="kanban-move-btn"
            onClick={() => moveColumn(i, -1)}
            disabled={i === 0}
            title="Переместить вверх"
          >↑</button>
          <button
            className="kanban-move-btn"
            onClick={() => moveColumn(i, 1)}
            disabled={i === columns.length - 1}
            title="Переместить вниз"
          >↓</button>

        </div>
      ))}
      <div style={{ display: 'flex', gap: '8px', marginTop: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
        <div
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            gap: '8px', width: '100%',
            padding: '6px 12px',
            background: 'var(--glass-bg)',
            border: '1px solid var(--glass-border)',
            borderRadius: 'var(--radius)',
          }}
        >
          <button
            className="kanban-create-btn"
            style={{ padding: '6px 12px', fontSize: '12px' }}
            onClick={addColumn}
          >
            + Добавить колонку
          </button>

          <div style={{
            width: '1px', height: '28px',
            background: 'var(--glass-border)',
            margin: '0 4px', flexShrink: 0,
          }} />

          <div
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            title="Задачи из выбранных колонок старше N дней будут перемещаться в архив автоматически"
          >
            <label style={{ color: 'var(--text-secondary)', fontSize: '13px', whiteSpace: 'nowrap' }}>Переместить через</label>
            <input
              type="number"
              min={0}
              max={365}
              value={autoArchiveDays}
              disabled={enabledColumns.length === 0}
              onChange={e => {
                const v = Math.max(0, Math.min(365, parseInt(e.target.value) || 0))
                setAutoArchiveDays(v)
                saveAutoArchive(v, autoDeleteColumns)
              }}
              className="settings-input settings-input-narrow"
            />
            <label style={{ color: 'var(--text-secondary)', fontSize: '13px', whiteSpace: 'nowrap' }}>дней из</label>
            <MultiSelectMenu
              value={autoDeleteColumns}
              options={enabledColumns.map(c => ({ value: c.id, label: c.label }))}
              onChange={arr => {
                setAutoDeleteColumns(arr)
                saveAutoArchive(autoArchiveDays, arr)
              }}
              disabled={enabledColumns.length === 0}
              width="160px"
              placeholder="Выберите колонки"
            />
            <label style={{ color: 'var(--text-secondary)', fontSize: '13px', whiteSpace: 'nowrap' }}>в архив</label>
          </div>

          <div style={{
            width: '1px', height: '28px',
            background: 'var(--glass-border)',
            margin: '0 4px', flexShrink: 0,
          }} />

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <label style={{ color: 'var(--text-secondary)', fontSize: '13px', whiteSpace: 'nowrap' }}>Новые таски в</label>
            <CustomDropdown
              value={defaultColumnValue}
              options={defaultColumnOptions}
              onChange={handleDefaultColumnChange}
              disabled={enabledColumns.length === 0}
              width="200px"
            />
          </div>
        </div>

      </div>
      {/* Undo Toast */}
      {pendingDelete && (
        <div className={`undo-toast ${pendingDelete ? 'visible' : ''}`}>
          <span className="undo-toast-text">
            «{pendingDelete.label}» удалена
          </span>
          <button className="undo-toast-btn" onClick={undoDelete}>
            Отменить
          </button>
          <div
            className="undo-toast-progress"
            style={{ width: `${undoProgress}%`, transition: 'width 100ms linear' }}
          />
        </div>
      )}
    </SettingsCard>
  )
}

// ── KanbanLabelsConfig ─────────────────────────────────────────────

function KanbanLabelsConfig() {
  const [labels, setLabels] = useState<KanbanLabelItem[]>([])
  const [saving, setSaving] = useState(false)
  const [savedId, setSavedId] = useState<string | null>(null)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const descDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { pendingDelete, undoProgress, start: startUndo, undo: undoDelete } =
    useUndoWithProgress<KanbanLabelItem>({
      onExpire: ({ id }) => {
        fetch(`${API_BASE}/api/kanban/config/labels/${id}`, { method: 'DELETE' })
          .catch(e => console.error('[kanban] delete label error:', e))
      },
      onUndo: ({ id: _id, index, extras }) => {
        const label: KanbanLabelItem = extras ?? ({ id: _id, name: _id } as KanbanLabelItem)
        setLabels(prev => {
          const newLabels = [...prev]
          newLabels.splice(index, 0, label)
          return newLabels
        })
      },
    })

  useEffect(() => {
    fetch(`${API_BASE}/api/kanban/config/labels`)
      .then(r => r.json())
      .then(data => setLabels(Array.isArray(data) ? data : data.labels || []))
      .catch(() => {})
  }, [])

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
      if (descDebounceRef.current) clearTimeout(descDebounceRef.current)
    }
  }, [])

  const patchLabel = async (id: string, updates: Partial<KanbanLabelItem>) => {
    setSaving(true)
    setSavedId(id)
    try {
      await fetch(`${API_BASE}/api/kanban/config/labels/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      })
    } catch (e) {
      console.error('[kanban] patch label error:', e)
    } finally {
      setSaving(false)
      setTimeout(() => setSavedId(null), 600)
    }
  }

  const updateLabelField = (index: number, field: string, value: unknown) => {
    const label = labels[index]
    if (!label) return
    setLabels(prev => prev.map((l, i) => i === index ? { ...l, [field]: value } : l))
    patchLabel(label.id, { [field]: value } as Partial<KanbanLabelItem>)
  }

  const updateLabelName = (index: number, rawName: string) => {
    const label = labels[index]
    if (!label) return
    // Auto-prepend "#" if user didn't type it
    const name = rawName.startsWith('#') ? rawName : '#' + rawName
    setLabels(prev => prev.map((l, i) => i === index ? { ...l, name } : l))
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      patchLabel(label.id, { name })
    }, 500)
  }

  const updateDescription = (index: number, description: string) => {
    const label = labels[index]
    if (!label) return
    setLabels(prev => prev.map((l, i) => i === index ? { ...l, description } : l))
    if (descDebounceRef.current) clearTimeout(descDebounceRef.current)
    descDebounceRef.current = setTimeout(() => {
      patchLabel(label.id, { description } as Partial<KanbanLabelItem>)
    }, 500)
  }

  const addLabel = async () => {
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/api/kanban/config/labels`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: '#Новая метка',
          color: '#3b82f6',
          text_color: '#ffffff',
          description: '',
        }),
      })
      if (res.ok) {
        const newLabel = await res.json()
        setLabels(prev => [...prev, newLabel])
        setSavedId(newLabel.id)
        setTimeout(() => setSavedId(null), 1500)
      }
    } catch (e) {
      console.error('[kanban] add label error:', e)
    } finally {
      setSaving(false)
    }
  }

  const removeLabel = (index: number) => {
    const label = labels[index]
    if (!label) return

    setLabels(prev => prev.filter((_, i) => i !== index))

    startUndo({
      id: label.id,
      label: label.name,
      index,
      extras: { ...label },
    })
  }

  return (
    <SettingsCard title="Конфигурация меток">
      <p className="settings-hint">Настройте метки (теги) для задач: цвет фона и текста</p>
      <div className="settings-divider-thin" />
      {labels.map((label, i) => (
        <div key={label.id} className={`kanban-config-row${saving && savedId === label.id ? ' saving' : ''}`}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', width: '100%' }}>
            <span
              className="kanban-label-chip"
              style={{ background: label.color, color: label.text_color }}
            >
              {label.name}
            </span>
            <input
              className="settings-input label-name-input"
              value={label.name.replace(/^#/, '')}
              onChange={e => updateLabelName(i, e.target.value)}
              placeholder="Название метки"
              style={{ flex: 1, minWidth: 120 }}
            />
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ fontSize: '10px', color: 'var(--gray-500)' }}>Фон</span>
              <input
                type="color"
                className="kanban-color-picker"
                value={label.color}
                onChange={e => updateLabelField(i, 'color', e.target.value)}
                title="Цвет фона"
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <span style={{ fontSize: '10px', color: 'var(--gray-500)' }}>Текст</span>
              <input
                type="color"
                className="kanban-color-picker"
                value={label.text_color}
                onChange={e => updateLabelField(i, 'text_color', e.target.value)}
                title="Цвет текста"
              />
            </div>
            <button
              className="widget-remove-btn"
              onClick={() => removeLabel(i)}
              title="Удалить метку"
            >×</button>

          </div>
          <input
            className="settings-input"
            value={label.description || ''}
            onChange={e => updateDescription(i, e.target.value)}
            placeholder="Описание метки..."
            style={{ width: '100%', marginTop: '4px', fontSize: '12px' }}
          />
        </div>
      ))}
      <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
        <button className="kanban-create-btn" style={{ padding: '6px 12px', fontSize: '12px' }} onClick={addLabel}>
          + Добавить метку
        </button>
      </div>
      {/* Undo Toast */}
      {pendingDelete && (
        <div className={`undo-toast ${pendingDelete ? 'visible' : ''}`}>
          <span className="undo-toast-text">
            «{pendingDelete.label}» удалена
          </span>
          <button className="undo-toast-btn" onClick={undoDelete}>
            Отменить
          </button>
          <div
            className="undo-toast-progress"
            style={{ width: `${undoProgress}%`, transition: 'width 100ms linear' }}
          />
        </div>
      )}
    </SettingsCard>
  )
}

// ── KanbanWidgetConfig ─────────────────────────────────────────────

function KanbanWidgetConfig() {
  const [config, setConfig] = useState<KanbanWidgetConfigData>({
    mode: 'active',
    max_items: 10,
    show_columns: [],
    show_deadline: true,
    show_department: true,
    compact: true,
  })
  const [columns, setColumns] = useState<KanbanColumnForWidget[]>([])
  const [saving, setSaving] = useState(false)

  const saveRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/kanban/config/widget`)
      .then(r => r.json())
      .then(setConfig)
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetch(`${API_BASE}/api/kanban/config/columns`)
      .then(r => r.json())
      .then((cols: KanbanColumnForWidget[]) => {
        setColumns(cols.filter(c => c.enabled !== false))
      })
      .catch(() => {})
  }, [])

  const saveWidgetConfig = useCallback((newConfig: KanbanWidgetConfigData) => {
    if (saveRef.current) clearTimeout(saveRef.current)
    saveRef.current = setTimeout(async () => {
      setSaving(true)
      try {
        console.log('[kanban-settings] saving widget config', newConfig)
        const res = await fetch(`${API_BASE}/api/kanban/config/widget`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(newConfig),
        })
        console.log('[kanban-settings] PUT response', res.status)
      } catch (e) {
        console.error('[kanban] save widget config error:', e)
      } finally {
        setSaving(false)
      }
    }, 300)
  }, [])

  const updateConfig = useCallback((patch: Partial<KanbanWidgetConfigData>) => {
    setConfig(prev => {
      const next = { ...prev, ...patch }
      saveWidgetConfig(next)
      return next
    })
  }, [saveWidgetConfig])

  const toggleShowColumn = (colId: string) => {
    setConfig(prev => {
      const next = {
        ...prev,
        show_columns: prev.show_columns.includes(colId)
          ? prev.show_columns.filter(c => c !== colId)
          : [...prev.show_columns, colId],
      }
      saveWidgetConfig(next)
      return next
    })
  }

  const selectAllColumns = () => {
    const allIds = columns.map(c => c.id)
    updateConfig({ show_columns: allIds })
  }

  const selectNoneColumns = () => {
    updateConfig({ show_columns: [] })
  }

  return (
    <SettingsCard title="Конфигурация виджета" className={saving ? 'saving' : undefined}>
      <p className="settings-hint">Настройте виджет канбан-доски на главной странице</p>

      {/* ── Отображение ── */}
      <div className="settings-section-label">Отображение</div>
      <div className="settings-row-2">
        <div className="settings-field">
          <label>Режим</label>
          <CustomDropdown
            value={config.mode}
            onChange={v => updateConfig({ mode: v })}
            options={[
              { value: 'active', label: 'Активные' },
              { value: 'all', label: 'Все задачи' },
              { value: 'my', label: 'Мои задачи' },
              { value: 'blocked', label: 'Заблокированные' },
            ]}
           
          />
        </div>
        <div className="settings-field">
          <label>Лимит</label>
          <input
            type="number"
            className="settings-input settings-input-narrow"
            value={config.max_items}
            min={1}
            max={50}
            onChange={e => {
              const v = Math.max(1, Math.min(50, parseInt(e.target.value) || 1))
              updateConfig({ max_items: v })
            }}
          />
        </div>
      </div>

      <div className="settings-divider-thin" />

      {/* ── Колонки ── */}
      <div className="settings-section-label">
        Колонки
        <span style={{ display: 'inline-flex', gap: '4px', marginLeft: 'auto' }}>
          <button className="kanban-col-toggle-btn" onClick={selectAllColumns}>Все</button>
          <button className="kanban-col-toggle-btn" onClick={selectNoneColumns}>Нет</button>
        </span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '4px' }}>
        {columns.length === 0 && (
          <span style={{ color: 'var(--text-dim)', fontSize: '12px' }}>
            Нет активных колонок
          </span>
        )}
        {columns.map(col => (
          <label
            key={col.id}
            className="kanban-widget-col-chip"
            style={{
              background: config.show_columns.includes(col.id) ? (col.color ? col.color + '33' : 'var(--glass-bg)') : 'transparent',
              borderColor: config.show_columns.includes(col.id) ? (col.color || 'var(--orange)') : 'var(--glass-border)',
            }}
          >
            <input
              type="checkbox"
              checked={config.show_columns.includes(col.id)}
              onChange={() => toggleShowColumn(col.id)}
            />
            <span
              style={{
                display: 'inline-block', width: '7px', height: '7px',
                borderRadius: '50%', background: col.color || '#6b7280',
              }}
            />
            <span>{col.label}</span>
          </label>
        ))}
      </div>

      <div className="settings-divider-thin" />

      {/* ── Информация ── */}
      <div className="settings-section-label">Информация</div>
      <Toggle
        label="Дедлайн"
        description="Показывать срок выполнения на карточке задачи"
        checked={config.show_deadline}
        onChange={v => updateConfig({ show_deadline: v })}
      />
      <Toggle
        label="Отдел"
        description="Показывать название отдела-владельца задачи"
        checked={config.show_department}
        onChange={v => updateConfig({ show_department: v })}
      />
      <Toggle
        label="Компактный режим"
        description="Уменьшенные карточки для экономии места на доске"
        checked={config.compact}
        onChange={v => updateConfig({ compact: v })}
      />
    </SettingsCard>
  )
}

// ── BoardSettingsConfig ───────────────────────────────────────────

function BoardSettingsConfig({ refreshKey }: { refreshKey?: number }) {
  const [settings, setSettings] = useState({
    max_active_tasks: 50,
    auto_archive_days: 30,
    notifications_enabled: true,
    archive_column: '' as string,
    blocked_column: '' as string,
  })
  const loadSettings = useCallback(() => {
    fetch(`${API_BASE}/api/kanban/config/settings`)
      .then(r => r.json())
      .then(data => {
        setSettings({
          max_active_tasks: data.max_active_tasks ?? 50,
          auto_archive_days: data.auto_archive_days ?? 30,
          notifications_enabled: data.notifications_enabled ?? true,
          archive_column: data.archive_column ?? '',
          blocked_column: data.blocked_column ?? '',
        })
      })
      .catch(() => {})
  }, [])

  useEffect(() => { loadSettings() }, [loadSettings, refreshKey])



  const save = useCallback(async (patch: Record<string, unknown>) => {
    try {
      await fetch(`${API_BASE}/api/kanban/config/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      })
    } catch (e) {
      console.error('[kanban] save board settings error:', e)
    }
  }, [])

  const update = (patch: Partial<typeof settings>) => {
    setSettings(prev => ({ ...prev, ...patch }))
    save(patch)
  }

  const archiveDaysOptions = [
    { value: 7, label: '7 дней' },
    { value: 14, label: '14 дней' },
    { value: 30, label: '30 дней' },
    { value: 90, label: '90 дней' },
    { value: 0, label: 'Никогда' },
  ]

  return (
    <SettingsCard title="Настройки доски">
      <p className="settings-hint">Лимиты, архивация и уведомления глобальной доски задач</p>
      <div className="settings-row-2">
        <div className="settings-field">
          <label>Максимум активных задач</label>
          <input
            type="number"
            className="settings-input settings-input-narrow"
            value={settings.max_active_tasks}
            min={1}
            onChange={e => update({ max_active_tasks: Math.max(1, parseInt(e.target.value) || 1) })}
          />
          <span className="settings-hint">Лимит одновременно открытых задач</span>
        </div>
        <div className="settings-field">
          <label>Автоудаление задач через</label>
          <CustomDropdown
            value={String(settings.auto_archive_days)}
            onChange={v => update({ auto_archive_days: parseInt(v) })}
            options={archiveDaysOptions.map(o => ({ value: String(o.value), label: o.label }))}
          />
          <span className="settings-hint">Задачи старше этого срока перемещаются в архив. Колонки выбираются в блоке «Конфигурация колонок»</span>
        </div>
      </div>

      <div className="settings-divider-thin" />
      <div className="settings-field">
        <label>Уведомления <span style={{ fontSize: '10px', color: 'var(--text-dim)' }}>🚧 скоро</span></label>
        <div style={{ opacity: 0.5, pointerEvents: 'none' }}>
          <Toggle
            label="Уведомления о задачах"
            checked={settings.notifications_enabled}
            onChange={() => {}}
          />
        </div>
        <span className="settings-hint">Создание, смена статуса, утверждение и дедлайны задач</span>
      </div>
      <div className="settings-divider-thin" />
      <div className="settings-hint" style={{ fontSize: '12px', lineHeight: 1.5 }}>
        <strong>Маппинг колонок:</strong>{' '}
        назначьте колонке статус{' '}
        <span style={{ color: '#6b7280', fontWeight: 600 }}>ARCHIVE</span> — архивные задачи попадут туда.{' '}
        Назначьте статус{' '}
        <span style={{ color: '#f87171', fontWeight: 600 }}>BLOCKED</span> — заблокированные задачи автоматически переместятся в эту колонку.
      </div>
    </SettingsCard>
  )
}

// ── KanbanBulkCleanup ─────────────────────────────────────────────

function KanbanBulkCleanup() {
  const [tasks, setTasks] = useState<{ id: string; title: string; status: string; department: string }[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{ action: string; processed: number } | null>(null)
  const [confirmAction, setConfirmAction] = useState<string | null>(null)

  const loadTasks = useCallback(async () => {
    setLoading(true)
    try {
      const url = filterStatus === 'all'
        ? `${API_BASE}/api/kanban/tasks`
        : `${API_BASE}/api/kanban/tasks?status=${filterStatus}`
      const res = await fetch(url)
      if (res.ok) {
        const data = await res.json()
        setTasks(data.map((t: Record<string, unknown>) => ({
          id: t.id as string,
          title: t.title as string,
          status: (t.status as string) || '',
          department: (t.department as string) || '',
        })))
      }
    } catch (e) {
      console.error('[kanban] load tasks for cleanup error:', e)
    } finally {
      setLoading(false)
    }
  }, [filterStatus])

  useEffect(() => { loadTasks() }, [loadTasks])

  const toggleTask = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const selectAll = () => setSelected(new Set(tasks.map(t => t.id)))
  const selectNone = () => setSelected(new Set())

  const executeBulk = async (action: 'delete' | 'archive') => {
    if (selected.size === 0) return
    setConfirmAction(null)
    setLoading(true)
    setResult(null)
    try {
      const res = await fetch(`${API_BASE}/api/kanban/tasks/bulk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task_ids: [...selected], action }),
      })
      if (res.ok) {
        const data = await res.json()
        setResult({ action, processed: data.processed })
        setSelected(new Set())
        loadTasks()
      }
    } catch (e) {
      console.error('[kanban] bulk action error:', e)
    } finally {
      setLoading(false)
    }
  }

  const statusLabels: Record<string, string> = {
    backlog: 'Бэклог', todo: 'К выполнению', in_progress: 'В работе',
    review: 'Ревью', revision: 'Ревизия', blocked: 'Заблокировано', archive: 'Архив', done: 'Выполнено',
  }

  return (
    <SettingsCard title="Массовая чистка">
      <p className="settings-hint">Выберите задачи для удаления или архивации</p>

      {/* Фильтр + управление */}
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '8px', flexWrap: 'wrap' }}>
        <CustomDropdown
          value={filterStatus}
          onChange={v => { setFilterStatus(v); setSelected(new Set()) }}
          options={[
            { value: 'all', label: 'Все статусы' },
            ...Object.entries(statusLabels).map(([val, label]) => ({ value: val, label })),
          ]}
          width="160px"
        />

        <button className="settings-link-btn" onClick={selectAll}>Выбрать все</button>
        <button className="settings-link-btn" onClick={selectNone}>Снять</button>

        <span style={{ marginLeft: 'auto', fontSize: '12px', color: 'var(--text-muted)' }}>
          {selected.size} из {tasks.length}
        </span>
      </div>

      {/* Список задач */}
      <div className="bulk-task-list">
        {loading && tasks.length === 0 && (
          <div style={{ padding: '20px 0' }}>
            <LoadingSpinner text="Загрузка..." minHeight={60} />
          </div>
        )}
        {!loading && tasks.length === 0 && (
          <div style={{ padding: '12px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
            Нет задач
          </div>
        )}
        {tasks.map(task => (
          <label
            key={task.id}
            className={`bulk-task-row${selected.has(task.id) ? ' selected' : ''}`}
          >
            <input
              type="checkbox"
              checked={selected.has(task.id)}
              onChange={() => toggleTask(task.id)}
            />
            <span className="bulk-task-title">{task.title}</span>
            <span className="bulk-task-status">{statusLabels[task.status] || task.status}</span>
          </label>
        ))}
      </div>

      {/* Действия */}
      {selected.size > 0 && (
        <div style={{ display: 'flex', gap: '8px', marginTop: '10px', alignItems: 'center' }}>
          {confirmAction ? (
            <>
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                {confirmAction === 'delete'
                  ? `Удалить ${selected.size} задач? Безвозвратно.`
                  : `Архивировать ${selected.size} задач?`}
              </span>
              <button
                className="btn-action-delete"
                onClick={() => executeBulk(confirmAction as 'delete' | 'archive')}
              >
                Да
              </button>
              <button className="settings-link-btn" onClick={() => setConfirmAction(null)}>
                Отмена
              </button>
            </>
          ) : (
            <>
              <button
                className="kanban-create-btn"
                style={{ padding: '6px 14px', fontSize: '12px' }}
                onClick={() => setConfirmAction('archive')}
              >
                Архивировать ({selected.size})
              </button>
              <button
                className="btn-action-delete"
                style={{ padding: '6px 14px', fontSize: '12px' }}
                onClick={() => setConfirmAction('delete')}
              >
                Удалить ({selected.size})
              </button>
            </>
          )}
        </div>
      )}

      {/* Результат */}
      {result && (
        <div style={{ marginTop: '8px', fontSize: '12px', color: 'var(--green)' }}>
          {result.action === 'delete' ? 'Удалено' : 'Архивировано'}: {result.processed} задач
        </div>
      )}
    </SettingsCard>
  )
}