import React, { useState, useEffect, useCallback, useRef } from 'react'
import { API_BASE } from '../config'
import { DndContext, closestCenter, useDraggable, useDroppable, DragEndEvent } from '@dnd-kit/core'
import { SortableContext, useSortable, arrayMove, horizontalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

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
  description: string
  color: string
  order: number
  enabled: boolean
  status?: string
}

interface LabelConfig {
  id: string
  name: string
  color: string
  text_color: string
  description?: string
}

interface WidgetConfig {
  default_column?: string | null
}

interface DepartmentItem {
  id: string
  otdelid?: string
  departmentsid?: string
  name: string
  head?: string
}

interface KanbanBoardProps {
  onBack: () => void
  wsOn?: (type: string, handler: (data: any) => void) => () => void
}

// ── Constants ──────────────────────────────────────────────────────────────

const PRIORITY_COLORS: Record<string, string> = {
  low: '#22c55e',
  medium: '#f59e0b',
  high: '#f97316',
  critical: '#ef4444',
}

const PRIORITY_LABELS: Record<string, string> = {
  low: 'Низкий',
  medium: 'Средний',
  high: 'Высокий',
  critical: 'Критический',
}

const PRIORITY_ORDER: Record<string, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
}

/** Sort tasks: critical → high → medium → low */
function sortByPriority(tasks: Task[]): Task[] {
  return [...tasks].sort(
    (a, b) => (PRIORITY_ORDER[a.priority] ?? 3) - (PRIORITY_ORDER[b.priority] ?? 3),
  )
}

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

// ── Draggable Task Card ────────────────────────────────────────────────────

function DraggableTaskCard({
  task,
  deptMap,
  onSelect,
}: {
  task: Task
  deptMap: Record<string, string>
  onSelect: (task: Task) => void
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } = useDraggable({
    id: `task-${task.id}`,
    data: { type: 'task', task },
  })

  const style: React.CSSProperties = {
    transform: CSS.Translate.toString(transform),
    transition: 'opacity 0.2s ease, transform 0.15s ease',
    opacity: isDragging ? 0.4 : 1,
    zIndex: isDragging ? 50 : 0,
    borderLeft: `3px solid ${PRIORITY_COLORS[task.priority] || '#22c55e'}`,
    position: isDragging ? 'relative' as const : undefined,
  }

  const deptName = deptMap[task.department] || task.department || ''

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`kanban-card ${isDragging ? 'kanban-card-dragging' : ''}`}
      onClick={() => {
        if (!isDragging) onSelect(task)
      }}
    >
      {/* Drag handle — only the grip icon initiates drag */}
      <span
        className="kanban-card-drag-handle"
        {...listeners}
        {...attributes}
        title="Перетащить"
      >⠿</span>
      {/* Task: compact view — priority dot + title + desc + dept */}
      <div className="kanban-card-top">
        <span
          className="kanban-card-priority"
          style={{ background: PRIORITY_COLORS[task.priority] || '#22c55e' }}
          title={PRIORITY_LABELS[task.priority] || task.priority}
        />
        <span className="kanban-card-title">{task.title}</span>
      </div>
      {task.description && (
        <div className="kanban-card-desc">{task.description}</div>
      )}
      {deptName && (
        <div className="kanban-card-dept">{deptName}</div>
      )}
      {task.deadline && (
        <div className="kanban-card-deadline">⏰ {formatDate(task.deadline)}</div>
      )}
    </div>
  )
}

// ── Sortable Column ────────────────────────────────────────────────────────

function SortableColumn({
  col,
  tasks,
  deptMap,
  onSelectTask,
}: {
  col: ColumnConfig
  tasks: Task[]
  deptMap: Record<string, string>
  onSelectTask: (task: Task) => void
}) {
  const {
    attributes: sortableAttrs,
    listeners: sortableListeners,
    setNodeRef: setSortableRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: col.id })

  const {
    setNodeRef: setDroppableRef,
    isOver,
  } = useDroppable({
    id: `col-body-${col.status || col.id}`,
    data: { type: 'column-body', status: col.status || col.id },
  })

  const containerRef = useCallback(
    (el: HTMLDivElement | null) => {
      setSortableRef(el)
    },
    [setSortableRef],
  )

  const bodyRef = useCallback(
    (el: HTMLDivElement | null) => {
      setDroppableRef(el)
      if (!el) return
      const check = () => {
        if (el.scrollHeight > el.clientHeight + 5) {
          el.classList.add('has-overflow')
        } else {
          el.classList.remove('has-overflow')
        }
      }
      check()
      const obs = new MutationObserver(check)
      obs.observe(el, { childList: true, subtree: true })
    },
    [setDroppableRef],
  )

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    zIndex: isDragging ? 10 : 0,
  }

  // Task 6: sort tasks by priority
  const sortedTasks = sortByPriority(tasks)

  return (
    <div
      ref={containerRef}
      style={style}
      className={`kanban-column ${isDragging ? 'dragging' : ''} ${isOver ? 'drop-target' : ''}`}
    >
      {/* Task 8: column header with gradient background */}
      <div
        className="kanban-column-header"
        style={{ background: `linear-gradient(135deg, ${col.color}22, ${col.color}08)` }}
        {...sortableAttrs}
        {...sortableListeners}
      >
        <span className="kanban-col-drag-handle">⠿</span>
        <span>{col.label}</span>
        <span className="kanban-column-count">{tasks.length}</span>
      </div>
      <div
        ref={bodyRef}
        className={`kanban-column-body ${isOver ? 'drag-over' : ''}`}
      >
        {sortedTasks.map(task => (
          <DraggableTaskCard
            key={task.id}
            task={task}
            deptMap={deptMap}
            onSelect={onSelectTask}
          />
        ))}
        {sortedTasks.length === 0 && (
          <div className="kanban-column-empty">Пусто</div>
        )}
      </div>
    </div>
  )
}

export function KanbanBoard({ onBack, wsOn }: KanbanBoardProps) {
  const [board, setBoard] = useState<Record<string, Task[]>>({})
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [loading, setLoading] = useState(true)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [columns, setColumns] = useState<ColumnConfig[]>([])
  const [labels, setLabels] = useState<LabelConfig[]>([])
  const [defaultColumn, setDefaultColumn] = useState<string | null>(null)
  const [departments, setDepartments] = useState<DepartmentItem[]>([])

  // Build label lookup map
  const labelMap: Record<string, LabelConfig> = {}
  for (const l of labels) {
    labelMap[l.name.toLowerCase()] = l
  }

  // Build department name lookup map (id → name)
  const deptMap: Record<string, string> = {}
  for (const d of departments) {
    const id = d.id || d.otdelid || d.departmentsid
    if (id) deptMap[id] = d.name
    // Also map by name in case tasks store the name directly
    deptMap[d.name] = d.name
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
        setColumns(
          cols
            .filter((c: ColumnConfig) => c.enabled)
            .sort((a: ColumnConfig, b: ColumnConfig) => a.order - b.order),
        )
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

  const loadWidgetConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/kanban/config/widget`)
      if (res.ok) {
        const data = (await res.json()) as WidgetConfig
        setDefaultColumn(data.default_column ?? null)
      }
    } catch (e) {
      console.error('[kanban] load widget config error:', e)
    }
  }, [])

  const loadDepartments = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/otdels`)
      if (res.ok) {
        const data = await res.json()
        setDepartments(Array.isArray(data) ? data : data.otdels || data.departments || [])
      }
    } catch (e) {
      console.error('[kanban] load departments error:', e)
    }
  }, [])

  useEffect(() => {
    loadBoard()
    loadColumns()
    loadLabels()
    loadWidgetConfig()
    loadDepartments()
  }, [loadBoard, loadColumns, loadLabels, loadWidgetConfig, loadDepartments])

  // WebSocket live updates
  useEffect(() => {
    if (!wsOn) return
    const unsub1 = wsOn('kanban:task_updated', () => {
      loadBoard()
    })
    const unsub2 = wsOn('kanban:task_created', () => {
      loadBoard()
    })
    const unsub3 = wsOn('kanban:columns_updated', () => {
      loadColumns()
      loadBoard()
    })
    const unsub4 = wsOn('kanban:labels_updated', () => {
      loadLabels()
      loadBoard()
    })
    const unsub5 = wsOn('kanban:widget_updated', () => {
      loadWidgetConfig()
    })
    return () => {
      unsub1()
      unsub2()
      unsub3()
      unsub4()
      unsub5()
    }
  }, [wsOn, loadBoard, loadColumns, loadLabels, loadWidgetConfig])

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

  const totalTasks = Object.values(board).reduce((sum, col) => sum + col.length, 0)

  // Resolve default column ID → status for task creation
  const defaultColId = defaultColumn || columns.find(c => c.enabled)?.id || null
  const defaultTaskStatus = defaultColId
    ? columns.find(c => c.id === defaultColId)?.status || 'backlog'
    : 'backlog'

  const effectiveColumns = columns.length > 0 ? columns : []

  // Task 4: Handle drag end — supports both column reorder and task move between columns
  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id) return

    const activeData = (active.data as any).current
    const overData = (over.data as any).current

    // Task drag between columns
    if (activeData?.type === 'task') {
      const task = activeData.task as Task
      const newStatus = overData?.type === 'column-body' ? overData.status : null

      if (newStatus && newStatus !== task.status) {
        // Optimistic update: move task locally
        setBoard(prev => {
          const next = { ...prev }
          // Remove from old status
          if (next[task.status]) {
            next[task.status] = (next[task.status] || []).filter(t => t.id !== task.id)
          }
          // Add to new status
          const movedTask = { ...task, status: newStatus }
          next[newStatus] = [...(next[newStatus] || []), movedTask]
          return next
        })

        // PATCH to backend
        fetch(`${API_BASE}/api/kanban/tasks/${task.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: newStatus }),
        }).catch(e => {
          console.error('[kanban] task move error:', e)
          loadBoard() // Revert on error
        })
      }
      return
    }

    // Column reorder
    const oldIndex = columns.findIndex(c => c.id === active.id)
    const newIndex = columns.findIndex(c => c.id === over.id)
    if (oldIndex === -1 || newIndex === -1) return
    const newCols = arrayMove(columns, oldIndex, newIndex)
    newCols.forEach((c, i) => (c.order = i))
    setColumns(newCols)
    fetch(`${API_BASE}/api/kanban/config/columns`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(newCols),
    }).catch(e => console.error('[kanban] save column order error:', e))
  }

  // Resolve department name for selected task
  const selectedDeptName = selectedTask
    ? deptMap[selectedTask.department] || selectedTask.department || ''
    : ''

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
          {/* Task 9: task count badge as pill */}
          <span className="kanban-task-count-badge">{totalTasks}</span>
          <button className="kanban-create-btn" onClick={() => setShowCreateModal(true)}>
            + Создать задачу
          </button>
        </div>
      </div>

      {/* Board */}
      {loading ? (
        <div className="kanban-loading">Загрузка доски...</div>
      ) : (
        <DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext
            items={effectiveColumns.map(c => c.id)}
            strategy={horizontalListSortingStrategy}
          >
            <div className="kanban-columns">
              {effectiveColumns.map(col => (
                <SortableColumn
                  key={col.id}
                  col={col}
                  tasks={board[col.status || col.id] || []}
                  deptMap={deptMap}
                  onSelectTask={setSelectedTask}
                />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}

      {/* Bottom area — stats and more will go here */}
      <div className="kanban-bottom">
        <div className="kanban-bottom-placeholder">
          <span className="kanban-bottom-icon">📊</span>
          <span>Статистика и аналитика — скоро</span>
        </div>
      </div>

      {/* Task Detail Modal — Task 2: cleaned up */}
      {selectedTask && (
        <div className="kanban-modal-overlay" onClick={() => setSelectedTask(null)}>
          {/* Task 7: max-height 90vh with scroll */}
          <div className="kanban-modal" onClick={e => e.stopPropagation()}>
            <div className="kanban-modal-header">
              {/* Task 2: Move title to right side of priority block */}
              <div className="kanban-modal-header-left">
                <span
                  className="kanban-modal-priority"
                  style={{ background: PRIORITY_COLORS[selectedTask.priority] || '#6b7280' }}
                >
                  {PRIORITY_LABELS[selectedTask.priority] || selectedTask.priority}
                </span>
                <h3 className="kanban-modal-title">{selectedTask.title}</h3>
              </div>
              <button className="kanban-modal-close" onClick={() => setSelectedTask(null)}>✕</button>
            </div>

            {selectedTask.description && (
              <p className="kanban-modal-desc">{selectedTask.description}</p>
            )}

            {/* Task 2: Show department NAME, not ID. Removed status line. */}
            <div className="kanban-modal-meta">
              {selectedDeptName && <span>📂 {selectedDeptName}</span>}
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
                      <span className="kanban-summon-dept">{deptMap[dept] || dept}</span>
                      {i < selectedTask.summon_chain.length - 1 && (
                        <span className="kanban-summon-arrow"> → </span>
                      )}
                    </span>
                  ))}
                  <span className="kanban-summon-arrow"> → </span>
                  <span className="kanban-summon-dept current">
                    {deptMap[selectedTask.current_department] || selectedTask.current_department}
                  </span>
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
                      <span className="kanban-history-target">
                        → {deptMap[h.target_department] || h.target_department}
                      </span>
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
          onCreated={() => {
            setShowCreateModal(false)
            loadBoard()
          }}
          defaultStatus={defaultTaskStatus}
        />
      )}
    </div>
  )
}

// ── Create Task Modal ──────────────────────────────────────────────────────

function CreateTaskModal({
  onClose,
  onCreated,
  defaultStatus,
}: {
  onClose: () => void
  onCreated: () => void
  defaultStatus?: string | null
}) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [department, setDepartment] = useState('')
  const [priority, setPriority] = useState('medium')
  const [deadline, setDeadline] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [saving, setSaving] = useState(false)
  const [deptError, setDeptError] = useState(false)

  // Auto-expanding textarea
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Department searchable dropdown
  const [departments, setDepartments] = useState<DepartmentItem[]>([])
  const [deptSearch, setDeptSearch] = useState('')
  const [deptOpen, setDeptOpen] = useState(false)
  const deptDropdownRef = useRef<HTMLDivElement>(null)
  const deptSearchInputRef = useRef<HTMLInputElement>(null)

  // Tag picker
  const [availableLabels, setAvailableLabels] = useState<LabelConfig[]>([])
  const [tagsOpen, setTagsOpen] = useState(false)
  const tagsPopupRef = useRef<HTMLDivElement>(null)
  const tagsTriggerRef = useRef<HTMLDivElement>(null)

  // ── Fetch departments & labels ──
  useEffect(() => {
    fetch(`${API_BASE}/api/otdels`)
      .then(r => r.json())
      .then(data =>
        setDepartments(Array.isArray(data) ? data : data.otdels || data.departments || []),
      )
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetch(`${API_BASE}/api/kanban/config/labels`)
      .then(r => r.json())
      .then(data => setAvailableLabels(Array.isArray(data) ? data : data.labels || []))
      .catch(() => {})
  }, [])

  // ── Click outside handlers ──
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (deptDropdownRef.current && !deptDropdownRef.current.contains(e.target as Node)) {
        setDeptOpen(false)
      }
    }
    if (deptOpen) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [deptOpen])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (
        tagsPopupRef.current &&
        !tagsPopupRef.current.contains(e.target as Node) &&
        tagsTriggerRef.current &&
        !tagsTriggerRef.current.contains(e.target as Node)
      ) {
        setTagsOpen(false)
      }
    }
    if (tagsOpen) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [tagsOpen])

  // ── Filtered departments ──
  const filteredDepts = departments.filter(d =>
    d.name.toLowerCase().includes(deptSearch.toLowerCase()),
  )

  const selectedDept = departments.find(d => {
    const id = d.id || d.otdelid || d.departmentsid
    return id === department || d.name === department
  })

  // ── Auto-resize textarea ──
  const handleTextareaInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
    setDescription(el.value)
  }

  // ── Toggle department ──
  const selectDept = (d: DepartmentItem) => {
    const id = d.id || d.otdelid || d.departmentsid
    setDepartment(id || d.name)
    setDeptOpen(false)
    setDeptSearch('')
    setDeptError(false)
  }

  // ── Toggle tag ──
  const toggleTag = (name: string) => {
    setTags(prev => (prev.includes(name) ? prev.filter(t => t !== name) : [...prev, name]))
  }

  // ── Submit — Task 10: validate department required ──
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    if (!department.trim()) {
      setDeptError(true)
      return
    }
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/api/kanban/tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim(),
          department: department.trim(),
          status: defaultStatus || 'backlog',
          priority,
          deadline: deadline || null,
          tags,
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
          <button className="kanban-modal-close" onClick={onClose}>
            ✕
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          {/* Title */}
          <div className="kanban-form-group">
            <label>Название *</label>
            <input
              value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder="Создать MCP интеграцию"
              autoFocus
            />
          </div>

          {/* Description — auto-expanding textarea */}
          <div className="kanban-form-group">
            <label>Описание</label>
            <textarea
              ref={textareaRef}
              value={description}
              onChange={handleTextareaInput}
              placeholder="Подробное описание задачи..."
              rows={1}
              className="auto-grow-textarea"
            />
          </div>

          {/* Priority inline selector */}
          <div className="kanban-form-group">
            <label>Приоритет</label>
            <div className="priority-inline">
              {[
                { value: 'low', label: 'Низкий', color: '#22c55e' },
                { value: 'medium', label: 'Средний', color: '#f59e0b' },
                { value: 'high', label: 'Высокий', color: '#ef4444' },
              ].map((p, idx) => (
                <React.Fragment key={p.value}>
                  {idx > 0 && <span className="priority-separator">|</span>}
                  <button
                    type="button"
                    className={`priority-inline-btn ${priority === p.value ? 'active' : ''}`}
                    onClick={() => setPriority(p.value)}
                  >
                    <span className="priority-dot" style={{ background: p.color }} />
                    {p.label}
                  </button>
                </React.Fragment>
              ))}
            </div>
          </div>

          {/* Department searchable dropdown — Task 10: required field */}
          <div className="kanban-form-row">
            <div
              className="kanban-form-group"
              style={{ position: 'relative' }}
              ref={deptDropdownRef}
            >
              <label>
                Отдел *{' '}
                {deptError && <span className="kanban-field-error">Выберите отдел</span>}
              </label>
              <div
                className={`kanban-dept-trigger ${deptError ? 'kanban-dept-error' : ''}`}
                onClick={() => {
                  setDeptOpen(prev => !prev)
                  setDeptError(false)
                  setTimeout(() => deptSearchInputRef.current?.focus(), 0)
                }}
              >
                <span className={selectedDept ? '' : 'kanban-dept-placeholder'}>
                  {selectedDept?.name || 'Не указан'}
                </span>
                <span className="kanban-dept-arrow">{deptOpen ? '▴' : '▾'}</span>
              </div>
              {deptOpen && (
                <div className="kanban-dept-dropdown">
                  <input
                    ref={deptSearchInputRef}
                    className="kanban-dept-search"
                    value={deptSearch}
                    onChange={e => setDeptSearch(e.target.value)}
                    placeholder="Поиск отдела..."
                  />
                  <div className="kanban-dept-list">
                    {filteredDepts.length === 0 && (
                      <div className="kanban-dept-empty">Нет результатов</div>
                    )}
                    {filteredDepts.map(d => (
                      <div
                        key={d.otdelid || d.id || d.name}
                        className={`kanban-dept-item ${
                          department === (d.otdelid || d.id || d.departmentsid || d.name)
                            ? 'active'
                            : ''
                        }`}
                        onClick={() => selectDept(d)}
                      >
                        <span>{d.name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Deadline */}
            <div className="kanban-form-group">
              <label>Дедлайн</label>
              <input type="date" value={deadline} onChange={e => setDeadline(e.target.value)} />
            </div>
          </div>

          {/* Tags as clickable chips + popup */}
          <div className="kanban-form-group" style={{ position: 'relative' }}>
            <label>Теги</label>
            <div className="kanban-tags-row">
              {/* Selected tags as chips */}
              {tags.map(tagName => {
                const label = availableLabels.find(l => l.name === tagName)
                return (
                  <span
                    key={tagName}
                    className="kanban-tag-chip"
                    style={label ? { background: label.color, color: label.text_color } : undefined}
                    onClick={() => toggleTag(tagName)}
                    title={
                      label?.description
                        ? `${label.description}\nНажмите чтобы убрать`
                        : 'Нажмите чтобы убрать'
                    }
                  >
                    {tagName} ✕
                  </span>
                )
              })}
              {/* Add button */}
              <div
                ref={tagsTriggerRef}
                className="kanban-tag-add"
                onClick={() => setTagsOpen(prev => !prev)}
                title="Добавить тег"
              >
                +
              </div>
            </div>
            {/* Tag picker popup */}
            {tagsOpen && (
              <div
                ref={tagsPopupRef}
                className="tag-picker-popup"
                onMouseLeave={() => setTagsOpen(false)}
              >
                {availableLabels.length === 0 && (
                  <div className="tag-picker-empty">Нет тегов</div>
                )}
                {availableLabels.map(label => (
                  <div
                    key={label.id}
                    className={`tag-block ${tags.includes(label.name) ? 'selected' : ''}`}
                    style={{ background: label.color, color: label.text_color }}
                    onClick={() => toggleTag(label.name)}
                    title={label.description || label.name}
                  >
                    {tags.includes(label.name) && <span className="tag-check">✓</span>}
                    {label.name}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="kanban-form-actions">
            <button type="button" className="kanban-btn-cancel" onClick={onClose}>
              Отмена
            </button>
            <button
              type="submit"
              className="kanban-btn-submit"
              disabled={!title.trim() || !department.trim() || saving}
            >
              {saving ? 'Создание...' : 'Создать'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
