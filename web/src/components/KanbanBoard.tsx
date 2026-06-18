import React, { useState, useEffect, useCallback, useRef } from 'react'
import { API_BASE } from '../config'
import { DndContext, pointerWithin, useDraggable, useDroppable, DragEndEvent, DragOverlay, DragStartEvent } from '@dnd-kit/core'
import { SortableContext, useSortable, arrayMove, horizontalListSortingStrategy } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { PickerMenu } from './PickerMenu'
import { LoadingSpinner } from './LoadingSpinner'
import { KanbanStats } from './KanbanStats'

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
  color?: string
}

interface KanbanBoardProps {
  wsOn?: (type: string, handler: (data: any) => void) => () => void
}

// ── Constants ──────────────────────────────────────────────────────────────

const PRIORITY_COLORS: Record<string, string> = {
  low: '#22c55e',
  medium: '#f59e0b',
  high: '#ef4444',
  critical: '#dc2626',
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
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

const formatDateTime = (s: string) => {
  if (!s) return ''
  const d = new Date(s)
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' }) +
    ' ' + d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

const isDeadlineOverdue = (s: string) => {
  if (!s) return false
  return new Date(s) < new Date()
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
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `task-${task.id}`,
    data: { type: 'task', task },
  })

  // Inline (placeholder) card: invisible while dragging — the visible "ghost"
  // is rendered by <DragOverlay> in the parent <DndContext>. This is what
  // fixes the "card hidden behind neighbour column" bug: DragOverlay lives
  // at document.body level and is not trapped by any column's stacking
  // context. Same pattern as the global DropdownMenu fix.
  const style: React.CSSProperties = {
    borderLeft: `3px solid ${PRIORITY_COLORS[task.priority] || '#22c55e'}`,
    opacity: isDragging ? 0 : 1,
  }

  const deptName = deptMap[task.department] || task.department || ''

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="kanban-card"
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
      <div className="kanban-card-top">
        <span
          className="kanban-card-priority"
          style={{ background: PRIORITY_COLORS[task.priority] || '#22c55e' }}
          title={PRIORITY_LABELS[task.priority] || task.priority}
        />
        <span className="kanban-card-title">{task.title}</span>
      </div>
      {deptName && <div className="kanban-card-dept">{deptName}</div>}
      {task.deadline && (() => {
        const deadlineDate = new Date(task.deadline)
        const now = new Date()
        const hoursLeft = (deadlineDate.getTime() - now.getTime()) / (1000 * 60 * 60)
        const isOverdue = hoursLeft < 0
        const isUrgent = hoursLeft >= 0 && hoursLeft < 1
        const deadlineClass = isOverdue ? 'kanban-card-deadline overdue' : isUrgent ? 'kanban-card-deadline urgent' : 'kanban-card-deadline'
        const icon = isOverdue ? '🚨' : isUrgent ? '⚠️' : '⏰'
        return (
          <div className={deadlineClass}>{icon} {formatDate(task.deadline)}</div>
        )
      })()}
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
    // The droppable id is always the column id — never the status.
    // Statuses are an internal state-machine concern; the UI
    // doesn't need to know about them. Two columns with the same
    // status would otherwise collide (e.g. two custom "In Progress"
    // columns — we don't support that today, but the id is the
    // only stable handle).
    id: `col-body-${col.id}`,
    // We pass the column id (and label) explicitly. The drop handler
    // resolves this to a status via the columns list at drop time.
    data: { type: 'column-body', columnId: col.id, label: col.label },
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

export function KanbanBoard({ wsOn }: KanbanBoardProps) {
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
  const deptColorMap: Record<string, string> = {}
  for (const d of departments) {
    const id = d.id || d.otdelid || d.departmentsid
    if (id) {
      deptMap[id] = d.name
      if (d.color) deptColorMap[id] = d.color
    }
    deptMap[d.name] = d.name
    if (d.color) deptColorMap[d.name] = d.color
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

  // ── Delete task ─────────────────────────────────────────────
  // Manual deletion: invoked from the task-detail modal. We do a
  // confirm() before the API call so an accidental click in the
  // modal doesn't permanently lose work. After a successful
  // delete we close the modal and refresh the board so the
  // neighbouring columns don't show stale data.
  const handleDeleteTask = async (taskId: string) => {
    if (!window.confirm(`Удалить задачу? Это нельзя отменить.`)) return
    try {
      const res = await fetch(`${API_BASE}/api/kanban/tasks/${taskId}`, {
        method: 'DELETE',
      })
      if (res.ok) {
        setSelectedTask(null)
        loadBoard()
      } else {
        const data = await res.json().catch(() => ({}))
        alert(`Не удалось удалить: ${data.detail || res.statusText}`)
      }
    } catch (e) {
      console.error('[kanban] delete task error:', e)
      alert('Ошибка сети при удалении')
    }
  }

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
    const unsubDel1 = wsOn('kanban:task_deleted', () => {
      loadBoard()
    })
    const unsubDel2 = wsOn('kanban:tasks_deleted', () => {
      loadBoard()
    })
    // Deadline notifications
    const unsub6 = wsOn('kanban:deadline_warning', (data: { task_id: string; title: string; minutes_left: number }) => {
      console.warn(`[kanban] ⏰ Deadline approaching: "${data.title}" — ${data.minutes_left} min left`)
      loadBoard()
    })
    const unsub7 = wsOn('kanban:deadline_overdue', (data: { task_id: string; title: string; overdue_hours: number }) => {
      console.error(`[kanban] 🚨 Deadline OVERDUE: "${data.title}" — ${data.overdue_hours}h overdue, escalated to blocked`)
      loadBoard()
    })
    return () => {
      unsub1()
      unsub2()
      unsub3()
      unsub4()
      unsub5()
      unsub6()
      unsub7()
      unsubDel1()
      unsubDel2()
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

  // Resolve default column ID → status for task creation.
  // We always end up with a real TaskStatus enum value, even
  // when the default column is a custom user-added one without
  // a TaskStatus mapping. In that case we fall back to TODO,
  // which is the right semantic default for "queue this for an
  // agent to pick up".
  const defaultColId = defaultColumn || columns.find(c => c.enabled)?.id || null
  const defaultCol = defaultColId ? columns.find(c => c.id === defaultColId) : null
  const defaultTaskStatus = (defaultCol && defaultCol.status) || 'todo'

  const effectiveColumns = columns.length > 0 ? columns : []

  // ── DragOverlay state ───────────────────────────────────────────────────
  // The dragged task is rendered both inline (as a hidden placeholder so the
  // layout doesn't shift) and inside <DragOverlay> (the visible "ghost" that
  // follows the cursor). The overlay is portal-rendered at document.body,
  // so it escapes every stacking-context ancestor — column transforms,
  // modals, headers, etc. This is the global fix for "card hidden behind
  // neighbour column" and works in combination with the global DropdownMenu.
  const [activeTask, setActiveTask] = useState<Task | null>(null)

  const handleDragStart = (event: DragStartEvent) => {
    const data = (event.active.data as any).current
    if (data?.type === 'task') setActiveTask(data.task as Task)
  }

  // Task 4: Handle drag end — supports both column reorder and task move between columns
  const handleDragEnd = (event: DragEndEvent) => {
    setActiveTask(null)
    const { active, over } = event
    if (!over || active.id === over.id) return

    const activeData = (active.data as any).current
    const overData = (over.data as any).current

    // Task drag between columns.
    // Drop target may be EITHER:
    //  - column-body (dropped on empty column or its background)
    //  - another task (dropped on a card) — in that case the target
    //    column is the column of the card we dropped on.
    //
    // The UI doesn't deal in TaskStatus values directly — it deals
    // in column ids. We resolve the column id to a status at drop
    // time via the columns list, then PATCH with that status (or the
    // column id itself as fallback if the column has no status —
    // backend will then look up the column and use its status).
    // The board bucket key after the optimistic update is the
    // resolved status, NOT the column id, so the board's state
    // shape stays in sync with /api/kanban/tasks/board.
    if (activeData?.type === 'task') {
      const task = activeData.task as Task

      // Find the target column. Try column-body drop first, then
      // fall back to "the column the dropped-on card lives in".
      let targetColId: string | null = null
      if (overData?.type === 'column-body') {
        targetColId = (overData.columnId as string) ?? null
      } else if (overData?.type === 'task') {
        const overTask = overData.task as Task
        // The card we dropped on lives in its own column; use that
        // column's id. Find the column whose status bucket contains
        // this task. If the task itself has a status, the column
        // for that status is the right one.
        if (overTask.status) {
          // Look up: which column has overTask.status?
          // (board is grouped by status, so we can search the values.)
          for (const [status, list] of Object.entries(board)) {
            if ((list || []).some(t => t.id === overTask.id)) {
              // Find the column with this status.
              const col = effectiveColumns.find(c => c.status === status)
              if (col) {
                targetColId = col.id
                break
              }
              // No column has that status (data drift). Fall back
              // to using status directly — backend will accept it.
              targetColId = status
              break
            }
          }
        }
      }

      if (!targetColId) return

      // Resolve the column id to a TaskStatus enum value. If the
      // column has no status (e.g. brand-new user-added column with
      // no mapping), we send the column id itself — backend will
      // look it up and fall back to TODO.
      const targetCol = effectiveColumns.find(c => c.id === targetColId)
      const resolvedStatus = targetCol?.status
      const patchValue = resolvedStatus || targetColId
      // For the optimistic board update, the bucket key is the
      // status we expect the backend to assign. If we have no
      // status mapping, we don't know which bucket the task will
      // land in until the PATCH comes back — skip the optimistic
      // move in that case (we'll re-render once loadBoard() runs
      // after the PATCH). The task won't visually "move" until
      // then, but the PATCH still succeeds.
      const optimisticBucket = resolvedStatus

      // Same column: dnd-kit fires this for in-column reorder. We
      // don't support reordering tasks within a column, so no-op.
      if (resolvedStatus && resolvedStatus === task.status) return

      // Optimistic update: move task locally
      setBoard(prev => {
        const next = { ...prev }
        // Remove from old status
        if (next[task.status]) {
          next[task.status] = (next[task.status] || []).filter(t => t.id !== task.id)
        }
        // Add to new status — only if we know the bucket. Without
        // a status mapping, we just delete from old bucket and
        // let the next loadBoard() populate the right one.
        if (optimisticBucket) {
          const movedTask = { ...task, status: optimisticBucket }
          next[optimisticBucket] = [...(next[optimisticBucket] || []), movedTask]
        }
        return next
      })

      // PATCH to backend
      fetch(`${API_BASE}/api/kanban/tasks/${task.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: patchValue }),
      }).catch(e => {
        console.error('[kanban] task move error:', e)
        loadBoard() // Revert on error
      })
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
        <div className="kanban-loading-wrapper">
          <LoadingSpinner text="Загрузка доски..." />
        </div>
      ) : (
        <DndContext collisionDetection={pointerWithin} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
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
          <DragOverlay dropAnimation={null}>
            {activeTask ? (
              <div
                className="kanban-card kanban-card-overlay"
                style={{ borderLeft: `3px solid ${PRIORITY_COLORS[activeTask.priority] || '#22c55e'}` }}
              >
                <span className="kanban-card-drag-handle">⠿</span>
                <div className="kanban-card-top">
                  <span
                    className="kanban-card-priority"
                    style={{ background: PRIORITY_COLORS[activeTask.priority] || '#22c55e' }}
                    title={PRIORITY_LABELS[activeTask.priority] || activeTask.priority}
                  />
                  <span className="kanban-card-title">{activeTask.title}</span>
                </div>
                {deptMap[activeTask.department] && (
                  <div className="kanban-card-dept">{deptMap[activeTask.department]}</div>
                )}
                {activeTask.deadline && (
                  <div className="kanban-card-deadline">⏰ {formatDate(activeTask.deadline)}</div>
                )}
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      )}

      {/* Scroll indicator */}
      <button
        className="kanban-scroll-indicator"
        onClick={() => document.getElementById('kanban-stats')?.scrollIntoView({ behavior: 'smooth' })}
      >
        <span className="kanban-scroll-arrow">▼</span>
        <span>Статистика</span>
      </button>

      {/* Stats section */}
      <KanbanStats wsOn={wsOn} />

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
              <p className="kanban-modal-desc" style={{ fontStyle: 'italic' }}>{selectedTask.description}</p>
            )}

            {/* Department badge with color */}
            <div className="kanban-modal-meta">
              {selectedDeptName && (
                <span
                  className="kanban-dept-badge"
                  style={{
                    background: `${deptColorMap[selectedTask.department] || '#6b7280'}22`,
                    color: deptColorMap[selectedTask.department] || '#6b7280',
                    border: `1px solid ${deptColorMap[selectedTask.department] || '#6b7280'}44`,
                  }}
                >{selectedDeptName}</span>
              )}
              {selectedTask.created_at && (
                <span className="kanban-date-badge created">
                  📅 {formatDateTime(selectedTask.created_at)}
                </span>
              )}
              {selectedTask.deadline && (
                <span className={`kanban-date-badge deadline${isDeadlineOverdue(selectedTask.deadline) ? ' overdue' : ''}`}>
                  ⏰ {formatDate(selectedTask.deadline)}
                </span>
              )}
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
              <div className="kanban-modal-divider" />
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
                <div className="kanban-modal-divider" />
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

            {/* Footer with destructive action — tucked into the
                bottom-right corner of the modal so it doesn't take
                up a full row. The "необратимо" hint sits as a tiny
                italic aside. */}
            <div
              className="kanban-modal-footer"
              style={{
                justifyContent: 'flex-end',
                paddingTop: '12px',
                marginTop: '16px',
                borderTop: '1px solid var(--border, #2a2a3a)',
              }}
            >
              <span className="kanban-modal-footer-hint" style={{ marginRight: 'auto' }}>
                Действие необратимо
              </span>
              <button
                type="button"
                className="kanban-btn kanban-btn-danger"
                style={{ padding: '4px 10px', fontSize: '12px' }}
                onClick={() => handleDeleteTask(selectedTask.id)}
                data-testid="kanban-delete-task"
              >
                🗑 Удалить
              </button>
            </div>
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

  // Department searchable dropdown — picker state lives inside <PickerMenu>.
  const [departments, setDepartments] = useState<DepartmentItem[]>([])

  // Tag picker — state (selected tag names) is owned here; the picker
  // UI itself lives inside <PickerMenu multi>.
  const [availableLabels, setAvailableLabels] = useState<LabelConfig[]>([])

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

  // ── Filtered departments ──
  // PickerMenu handles its own search filtering when `searchable` is true,
  // so we hand it the full list.

  // ── Auto-resize textarea ──
  const handleTextareaInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const el = e.target
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 160) + 'px'
    setDescription(el.value)
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
            <div className="kanban-form-group">
              <label>
                Отдел *{' '}
                {deptError && <span className="kanban-field-error">Выберите отдел</span>}
              </label>
              <PickerMenu
                value={department || null}
                options={departments.map(d => {
                  const id = String(d.otdelid || d.id || d.departmentsid || d.name)
                  return {
                    id,
                    label: d.name,
                    searchText: d.name,
                  }
                })}
                onSelect={(id) => {
                  const d = departments.find(x =>
                    String(x.otdelid || x.id || x.departmentsid || x.name) === id
                  )
                  if (d) {
                    setDepartment(String(d.otdelid || d.id || d.departmentsid || d.name))
                    setDeptError(false)
                  }
                }}
                placeholder="Не указан"
                searchable
                searchPlaceholder="Поиск отдела..."
                emptyMessage="Нет результатов"
                triggerWidth="100%"
                triggerClassName={deptError ? 'picker-trigger kanban-dept-error' : 'picker-trigger kanban-dept-trigger'}
              />
            </div>

            {/* Deadline */}
            <div className="kanban-form-group">
              <label>Дедлайн</label>
              <input type="date" value={deadline} onChange={e => setDeadline(e.target.value)} />
            </div>
          </div>

          {/* Tags as clickable chips + popup — uses multi-select PickerMenu */}
          <div className="kanban-form-group">
            <label>Теги</label>
            <PickerMenu
              multi
              value={tags}
              onChange={setTags}
              options={availableLabels.map(label => ({
                id: label.name,
                label: label.name,
                searchText: label.name,
              }))}
              placeholder="Выберите теги..."
              emptyMessage="Нет тегов"
              triggerWidth="100%"
              triggerClassName="picker-trigger kanban-tags-trigger"
              formatTriggerLabel={(selected) =>
                selected.length === 0
                  ? 'Выберите теги...'
                  : selected.map(o => o.label).join(', ')
              }
            />
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
