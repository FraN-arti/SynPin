import { useState, useEffect, useCallback, useRef } from 'react'
import { API_BASE } from '../config'

interface Task {
  id: string
  title: string
  description: string
  department: string
  status: string
  priority: string
  deadline: string | null
  created_at: string
  updated_at: string
  assigned_head: string | null
  assigned_workers: { agent_id: string; subtask: string; status: string }[]
  history: { timestamp: string; actor: string; action: string; detail: string; target_department?: string }[]
  results: { file_path: string; description: string }[]
  summon_chain: string[]
  current_department: string
  tags: string[]
}

interface ColumnConfig {
  id: string
  label: string
  color: string
  order: number
  enabled: boolean
}

interface LabelConfig {
  id: string
  name: string
  color: string
  text_color: string
}

interface KanbanBoardProps {
  onBack: () => void
  wsOn?: (type: string, handler: (data: any) => void) => () => void
}

const PRIORITY_COLORS: Record<string, string> = {
  low: '#6b7280',
  medium: '#f59e0b',
  high: '#f97316',
  critical: '#ef4444',
}

export function KanbanBoard({ onBack, wsOn }: KanbanBoardProps) {
  const [board, setBoard] = useState<Record<string, Task[]>>({})
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [columns, setColumns] = useState<ColumnConfig[]>([])
  const [labels, setLabels] = useState<LabelConfig[]>([])

  // Build label lookup map
  const labelMap: Record<string, LabelConfig> = {}
  for (const l of labels) {
    labelMap[l.name.toLowerCase()] = l
  }

  const loadBoard = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/kanban/tasks/board`)
      const data = await res.json()
      setBoard(data)
    } catch (e) {
      console.error('[kanban] load error:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadColumns = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/kanban/config/columns`)
      if (res.ok) {
        const data = await res.json()
        const cols = Array.isArray(data) ? data : data.columns || []
        setColumns(cols.filter((c: ColumnConfig) => c.enabled).sort((a: ColumnConfig, b: ColumnConfig) => a.order - b.order))
      }
    } catch (e) {
      console.error('[kanban] load columns error:', e)
    }
  }, [])

  const loadLabels = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/kanban/config/labels`)
      if (res.ok) {
        const data = await res.json()
        setLabels(Array.isArray(data) ? data : data.labels || [])
      }
    } catch (e) {
      console.error('[kanban] load labels error:', e)
    }
  }, [])

  useEffect(() => {
    loadBoard()
    loadColumns()
    loadLabels()
  }, [loadBoard, loadColumns, loadLabels])

  // WebSocket live updates
  useEffect(() => {
    if (!wsOn) return
    const unsub1 = wsOn('kanban:task_updated', () => {
      loadBoard()
    })
    const unsub2 = wsOn('kanban:task_created', () => {
      loadBoard()
    })
    return () => {
      unsub1()
      unsub2()
    }
  }, [wsOn, loadBoard])

  // Refresh when a task is selected (fallback polling if WS not available)
  useEffect(() => {
    if (!selectedTask) return
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/kanban/tasks/${selectedTask.id}`)
        if (res.ok) {
          const data = await res.json()
          setSelectedTask(data)
          loadBoard()
        }
      } catch {}
    }, 3000)
    return () => clearInterval(interval)
  }, [selectedTask, loadBoard])

  const formatDate = (s: string) => {
    if (!s) return ''
    const d = new Date(s)
    return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
  }

  const formatTime = (s: string) => {
    if (!s) return ''
    const d = new Date(s)
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  }

  const totalTasks = Object.values(board).reduce((sum, col) => sum + col.length, 0)

  // If no columns loaded from config, show loading
  const effectiveColumns = columns.length > 0 ? columns : []

  return (
    <div className="kanban-page">
      {/* Header */}
      <div className="kanban-header">
        <button className="nav-back-btn" onClick={onBack} title="Назад">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
        </button>
        <h2 className="kanban-title">Глобальный Канбан</h2>
        <div className="kanban-header-right">
          <span className="kanban-count">{totalTasks} задач</span>
          <button className="kanban-create-btn" onClick={() => setShowCreateModal(true)}>
            + Создать задачу
          </button>
        </div>
      </div>

      {/* Board */}
      {loading ? (
        <div className="kanban-loading">Загрузка доски...</div>
      ) : (
        <div className="kanban-columns">
          {effectiveColumns.map(col => {
            const tasks = board[col.id] || []
            return (
              <div key={col.id} className="kanban-column">
                <div className="kanban-column-header">
                  <span className="kanban-col-indicator" style={{ background: col.color }} />
                  <span>{col.label}</span>
                  <span className="kanban-column-count">{tasks.length}</span>
                </div>
                <div
                  ref={el => {
                    if (!el) return
                    const check = () => {
                      if (el.scrollHeight > el.clientHeight + 5) {
                        el.classList.add('has-overflow')
                      } else {
                        el.classList.remove('has-overflow')
                      }
                    }
                    check()
                    // Recheck on content changes
                    const obs = new MutationObserver(check)
                    obs.observe(el, { childList: true, subtree: true })
                  }}
                  className="kanban-column-body"
                >
                  {tasks.map(task => (
                    <div
                      key={task.id}
                      className="kanban-card"
                      onClick={() => setSelectedTask(task)}
                    >
                      <div className="kanban-card-header">
                        <span className="kanban-card-id">{task.id}</span>
                        <span
                          className="kanban-card-priority"
                          style={{ background: PRIORITY_COLORS[task.priority] || '#6b7280' }}
                          title={task.priority}
                        />
                      </div>
                      <div className="kanban-card-title">{task.title}</div>
                      {task.department && (
                        <div className="kanban-card-dept">{task.department}</div>
                      )}
                      {task.tags.length > 0 && (
                        <div className="kanban-card-tags">
                          {task.tags.map(t => {
                            const label = labelMap[t.toLowerCase()]
                            return (
                              <span
                                key={t}
                                className="kanban-tag"
                                style={label ? { background: label.color, color: label.text_color } : undefined}
                              >
                                {t}
                              </span>
                            )
                          })}
                        </div>
                      )}
                      {task.deadline && (
                        <div className="kanban-card-deadline">⏰ {formatDate(task.deadline)}</div>
                      )}
                    </div>
                  ))}
                  {tasks.length === 0 && (
                    <div className="kanban-column-empty">Пусто</div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Bottom area — stats and more will go here */}
      <div className="kanban-bottom">
        <div className="kanban-bottom-placeholder">
          <span className="kanban-bottom-icon">📊</span>
          <span>Статистика и аналитика — скоро</span>
        </div>
      </div>

      {/* Task Detail Modal */}
      {selectedTask && (
        <div className="kanban-modal-overlay" onClick={() => setSelectedTask(null)}>
          <div className="kanban-modal" onClick={e => e.stopPropagation()}>
            <div className="kanban-modal-header">
              <div>
                <span className="kanban-modal-id">{selectedTask.id}</span>
                <span
                  className="kanban-modal-priority"
                  style={{ background: PRIORITY_COLORS[selectedTask.priority] || '#6b7280' }}
                >
                  {selectedTask.priority}
                </span>
              </div>
              <button className="kanban-modal-close" onClick={() => setSelectedTask(null)}>✕</button>
            </div>
            <h3 className="kanban-modal-title">{selectedTask.title}</h3>
            {selectedTask.description && (
              <p className="kanban-modal-desc">{selectedTask.description}</p>
            )}

            {/* Meta */}
            <div className="kanban-modal-meta">
              <span>📂 {selectedTask.department || 'Не назначен'}</span>
              <span>📊 {selectedTask.status}</span>
              {selectedTask.assigned_head && <span>👤 {selectedTask.assigned_head}</span>}
              {selectedTask.deadline && <span>⏰ {formatDate(selectedTask.deadline)}</span>}
            </div>

            {/* Workers */}
            {selectedTask.assigned_workers.length > 0 && (
              <div className="kanban-modal-section">
                <h4>Команда</h4>
                {selectedTask.assigned_workers.map((w, i) => (
                  <div key={i} className="kanban-worker">
                    <span className="kanban-worker-agent">{w.agent_id}</span>
                    <span className="kanban-worker-task">{w.subtask}</span>
                    <span className={`kanban-worker-status ${w.status}`}>{w.status}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Summon chain */}
            {selectedTask.summon_chain.length > 0 && (
              <div className="kanban-modal-section">
                <h4>Цепочка передач</h4>
                <div className="kanban-summon-chain">
                  {selectedTask.summon_chain.map((dept, i) => (
                    <span key={i}>
                      <span className="kanban-summon-dept">{dept}</span>
                      {i < selectedTask.summon_chain.length - 1 && <span className="kanban-summon-arrow"> → </span>}
                    </span>
                  ))}
                  <span className="kanban-summon-arrow"> → </span>
                  <span className="kanban-summon-dept current">{selectedTask.current_department}</span>
                </div>
              </div>
            )}

            {/* History */}
            <div className="kanban-modal-section">
              <h4>История действий ({selectedTask.history.length})</h4>
              <div className="kanban-history">
                {selectedTask.history.map((h, i) => (
                  <div key={i} className={`kanban-history-entry ${h.action}`}>
                    <span className="kanban-history-time">{formatTime(h.timestamp)}</span>
                    <span className="kanban-history-actor">{h.actor}</span>
                    <span className="kanban-history-action">{h.action}</span>
                    <span className="kanban-history-detail">{h.detail}</span>
                    {h.target_department && (
                      <span className="kanban-history-target">→ {h.target_department}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Tags */}
            {selectedTask.tags.length > 0 && (
              <div className="kanban-modal-section">
                <h4>Теги</h4>
                <div className="kanban-card-tags">
                  {selectedTask.tags.map(t => {
                    const label = labelMap[t.toLowerCase()]
                    return (
                      <span
                        key={t}
                        className="kanban-tag"
                        style={label ? { background: label.color, color: label.text_color } : undefined}
                      >
                        {t}
                      </span>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Create Task Modal */}
      {showCreateModal && (
        <CreateTaskModal
          onClose={() => setShowCreateModal(false)}
          onCreated={() => { setShowCreateModal(false); loadBoard() }}
        />
      )}
    </div>
  )
}

// ── Create Task Modal ──────────────────────────────────────────────────────

function CreateTaskModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [department, setDepartment] = useState('')
  const [priority, setPriority] = useState('medium')
  const [deadline, setDeadline] = useState('')
  const [tags, setTags] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/api/kanban/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim(),
          department: department.trim(),
          priority,
          deadline: deadline || null,
          tags: tags.split(',').map(t => t.trim()).filter(Boolean),
        }),
      })
      if (res.ok) onCreated()
    } catch (e) {
      console.error('[kanban] create error:', e)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="kanban-modal-overlay" onClick={onClose}>
      <div className="kanban-modal kanban-create-modal" onClick={e => e.stopPropagation()}>
        <div className="kanban-modal-header">
          <h3>Новая задача</h3>
          <button className="kanban-modal-close" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="kanban-form-group">
            <label>Название *</label>
            <input
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="Создать MCP интеграцию"
              autoFocus
            />
          </div>
          <div className="kanban-form-group">
            <label>Описание</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Подробное описание задачи..."
              rows={3}
            />
          </div>
          <div className="kanban-form-row">
            <div className="kanban-form-group">
              <label>Отдел</label>
              <input
                value={department}
                onChange={e => setDepartment(e.target.value)}
                placeholder="реализации"
              />
            </div>
            <div className="kanban-form-group">
              <label>Приоритет</label>
              <select value={priority} onChange={e => setPriority(e.target.value)}>
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </div>
          </div>
          <div className="kanban-form-row">
            <div className="kanban-form-group">
              <label>Дедлайн</label>
              <input
                type="date"
                value={deadline}
                onChange={e => setDeadline(e.target.value)}
              />
            </div>
            <div className="kanban-form-group">
              <label>Теги (через запятую)</label>
              <input
                value={tags}
                onChange={e => setTags(e.target.value)}
                placeholder="mcp, integration"
              />
            </div>
          </div>
          <div className="kanban-form-actions">
            <button type="button" className="kanban-btn-cancel" onClick={onClose}>Отмена</button>
            <button type="submit" className="kanban-btn-submit" disabled={!title.trim() || saving}>
              {saving ? 'Создание...' : 'Создать'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
