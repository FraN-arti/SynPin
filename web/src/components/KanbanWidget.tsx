import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from '../config'

interface WidgetConfig {
  mode: string
  max_items: number
  show_columns: string[]
  show_deadline: boolean
  show_department: boolean
  compact: boolean
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
    show_columns: ['in_progress', 'review', 'blocked'],
    show_deadline: true,
    show_department: true,
    compact: true,
  })
  const [tasks, setTasks] = useState<Task[]>([])
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

  const loadTasks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/kanban/tasks/board`)
      if (res.ok) {
        const data = await res.json()
        // Flatten board into task list
        const allTasks: Task[] = []
        for (const [colKey, colTasks] of Object.entries(data)) {
          for (const t of (colTasks as Task[])) {
            allTasks.push({ ...t, status: colKey })
          }
        }

        // Filter by show_columns
        let filtered = allTasks
        if (config.show_columns && config.show_columns.length > 0) {
          filtered = allTasks.filter(t => config.show_columns.includes(t.status))
        }

        // Sort by priority
        const priorityOrder: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 }
        filtered.sort((a, b) => (priorityOrder[a.priority] ?? 4) - (priorityOrder[b.priority] ?? 4))

        // Limit
        if (config.max_items > 0) {
          filtered = filtered.slice(0, config.max_items)
        }

        setTasks(filtered)
      }
    } catch (e) {
      console.error('[kanban-widget] tasks error:', e)
    } finally {
      setLoading(false)
    }
  }, [config])

  useEffect(() => { loadConfig() }, [loadConfig])
  useEffect(() => { loadTasks() }, [loadTasks])

  // WebSocket live updates for config changes
  useEffect(() => {
    if (!wsOn) return
    const unsub1 = wsOn('kanban:widget_updated', () => {
      loadConfig()
    })
    const unsub2 = wsOn('kanban:columns_updated', () => {
      loadTasks()
    })
    const unsub3 = wsOn('kanban:labels_updated', () => {
      loadTasks()
    })
    return () => { unsub1(); unsub2(); unsub3() }
  }, [wsOn, loadConfig, loadTasks])

  if (loading) {
    return (
      <div className="kanban-widget">
        <div className="widget-empty">Загрузка...</div>
      </div>
    )
  }

  return (
    <div className="kanban-widget">
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
            <span className="kanban-widget-task-dept">{task.department}</span>
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
