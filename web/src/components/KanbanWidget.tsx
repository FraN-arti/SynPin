import { useState, useEffect, useCallback, useRef } from 'react'
import { API_BASE } from '../config'
import { LoadingSpinner } from './LoadingSpinner'

interface WidgetConfig {
  mode: string
  max_items: number
  show_columns: string[]  // column.id list (new format) or status list (legacy)
  show_deadline: boolean
  show_department: boolean
  compact: boolean
}

interface Column {
  id: string
  label: string
  description: string
  color: string
  order: number
  enabled: boolean
  status: string | null  // TaskStatus value or null for user-added columns
}

interface Task {
  id: string
  title: string
  status: string
  department: string
  priority: string
  deadline: string | null
}

interface KanbanWidgetProps {
  onNavigateToBoard?: () => void
  wsOn?: (type: string, handler: (data: any) => void) => () => void
}

// Color fallback for tasks whose status isn't in our map (user-added
// columns with a custom status). The frontend is the last line of
// defense — if the backend ever returns a status we don't know, we
// show it in muted gray rather than crash.
const STATUS_COLORS: Record<string, string> = {
  backlog: '#6b7280',
  todo: '#3b82f6',
  in_progress: '#f97316',
  review: '#f59e0b',
  revision: '#a855f7',
  blocked: '#ef4444',
  done: '#22c55e',
}

export function KanbanWidget({ onNavigateToBoard, wsOn }: KanbanWidgetProps) {
  const [config, setConfig] = useState<WidgetConfig>({
    mode: 'active',
    max_items: 10,
    show_columns: [],  // Will be filled in by loadConfig. Empty array = show all enabled columns.
    show_deadline: true,
    show_department: true,
    compact: true,
  })
  const [columns, setColumns] = useState<Column[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [deptMap, setDeptMap] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)

  const loadConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/kanban/config/widget`)
      if (res.ok) {
        const data = await res.json()
        setConfig(data)
      }
    } catch (e) {
      console.error('[kanban-widget] config error:', e)
    }
  }, [])

  const loadColumns = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/kanban/config/columns`)
      if (res.ok) {
        setColumns(await res.json())
      }
    } catch (e) {
      console.error('[kanban-widget] columns error:', e)
    }
  }, [])

  const loadDeptMap = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/otdels`)
      if (res.ok) {
        const data = await res.json()
        const otdels = Array.isArray(data) ? data : (data.otdels || [])
        const map: Record<string, string> = {}
        for (const o of otdels) {
          const id = o.otdelid || o.id || o.departmentsid || ''
          if (id) map[id] = o.name || id
        }
        setDeptMap(map)
      }
    } catch (e) {
      // non-critical
    }
  }, [])

  // Track whether initial config+columns are loaded
  const configRef = useRef(config)
  const columnsRef = useRef(columns)
  configRef.current = config
  columnsRef.current = columns

  const loadTasks = useCallback(async () => {
    // Guard: don't load tasks until config + columns have been fetched at least once
    if (columnsRef.current.length === 0 && configRef.current.show_columns.length > 0) {
      // Columns not loaded yet and we need them for filtering — skip
      return
    }
    try {
      const res = await fetch(`${API_BASE}/api/kanban/tasks/board`)
      if (res.ok) {
        const data = await res.json()
        const allTasks: Task[] = []
        for (const [colKey, colTasks] of Object.entries(data)) {
          for (const t of (colTasks as Task[])) {
            allTasks.push({ ...t, status: colKey })
          }
        }

        let allowed: Set<string> | null = null
        const cfg = configRef.current
        const cols = columnsRef.current
        if (cfg.show_columns && cfg.show_columns.length > 0) {
          allowed = new Set()
          for (const entry of cfg.show_columns) {
            const col = cols.find(c => c.id === entry)
            if (col && col.status) {
              allowed.add(col.status)
            } else if (col && !col.status) {
              console.warn(
                `[kanban-widget] show_columns includes column '${entry}' which has no status; ` +
                `tasks in that column won't appear here. Edit the column to set a status.`
              )
            } else {
              allowed.add(entry)
            }
          }
        }

        let filtered = allTasks
        if (allowed !== null) {
          filtered = allTasks.filter(t => allowed!.has(t.status))
        }

        const priorityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }
        filtered.sort((a, b) => (priorityOrder[a.priority] ?? 4) - (priorityOrder[b.priority] ?? 4))

        if (cfg.max_items > 0) {
          filtered = filtered.slice(0, cfg.max_items)
        }

        setTasks(filtered)
      }
    } catch (e) {
      console.error('[kanban-widget] tasks error:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  // Load order: config+columns first, then tasks
  useEffect(() => {
    let cancelled = false
    const init = async () => {
      await Promise.all([loadConfig(), loadColumns()])
      if (!cancelled) {
        loadDeptMap()
        // Yield to let React flush config+columns state to refs
        // Need multiple ticks for React to commit state
        await new Promise(r => setTimeout(r, 50))
        if (!cancelled) loadTasks()
      }
    }
    init()
    return () => { cancelled = true }
  }, [])

  // WebSocket live updates for config changes + task mutations
  useEffect(() => {
    if (!wsOn) return
    const unsub1 = wsOn('kanban:widget_updated', async (msg: any) => {
      console.log('[kanban-widget] WS received widget_updated', msg.widget)
      if (msg.widget) {
        setConfig(msg.widget)
        await new Promise(r => setTimeout(r, 0)) // yield to React
      } else {
        await loadConfig()
        await new Promise(r => setTimeout(r, 0))
      }
      loadTasks()
    })
    const unsub2 = wsOn('kanban:columns_updated', async () => {
      await loadColumns()
      await new Promise(r => setTimeout(r, 0)) // yield to React
      loadTasks()
    })
    const unsub3 = wsOn('kanban:labels_updated', () => {
      loadTasks()
    })
    // Task CRUD — drag-drop, create, delete all change the board
    const unsub4 = wsOn('kanban:task_updated', () => {
      loadTasks()
    })
    const unsub5 = wsOn('kanban:task_created', () => {
      loadTasks()
    })
    // Task deleted — remove from state directly (no fetch needed)
    const unsub6 = wsOn('kanban:task_deleted', (msg: any) => {
      if (msg.task_id) {
        setTasks(prev => prev.filter(t => t.id !== msg.task_id))
      } else {
        loadTasks()
      }
    })
    return () => { unsub1(); unsub2(); unsub3(); unsub4(); unsub5(); unsub6() }
  }, [wsOn, loadConfig, loadColumns, loadTasks])

  if (loading) {
    return (
      <div className="kanban-widget">
        <LoadingSpinner text="Загрузка..." />
      </div>
    )
  }

  return (
    <div className={`kanban-widget${config.compact ? ' compact' : ''}`}>
      {tasks.length === 0 && (
        <div className="widget-empty">Нет задач</div>
      )}
      {tasks.map(task => (
        <button
          key={task.id}
          className="kanban-widget-task"
          onClick={onNavigateToBoard}
          title={`${task.title} — ${task.status}`}
        >
          <span
            className="kanban-widget-status-dot"
            style={{ background: STATUS_COLORS[task.status] || '#6b7280' }}
          />
          <span className="kanban-widget-task-title">{task.title}</span>
          {config.show_department && task.department && (
            <span className="kanban-widget-task-dept">{deptMap[task.department] || task.department || 'Без отдела'}</span>
          )}
          {config.show_deadline && task.deadline && (
            <span className="kanban-widget-task-deadline">
              {new Date(task.deadline).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}
