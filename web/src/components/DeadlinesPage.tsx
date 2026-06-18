/**
 * DeadlinesPage — overview of all task deadlines.
 * Shows overdue, today, this week, and upcoming deadlines.
 * Live-updates via WebSocket.
 */
import { useState, useEffect, useCallback, useMemo } from 'react'
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
}

interface DeadlinesPageProps {
  wsOn?: (type: string, handler: (data: unknown) => void) => () => void
}

const STATUS_LABELS: Record<string, string> = {
  backlog: 'Бэклог', todo: 'TODO', ready: 'READY',
  in_progress: 'В работе', review: 'Ревью', revision: 'Доработка',
  blocked: 'Блокировка', done: 'Выполнено',
}

const STATUS_COLORS: Record<string, string> = {
  backlog: '#6b7280', todo: '#3b82f6', ready: '#a855f7',
  in_progress: '#f97316', review: '#f59e0b', revision: '#ec4899',
  blocked: '#ef4444', done: '#22c55e',
}

const PRIORITY_LABELS: Record<string, string> = {
  critical: 'Критический', high: 'Высокий', medium: 'Средний', low: 'Низкий',
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' })
}

function daysUntil(iso: string): number {
  const now = new Date()
  const dl = new Date(iso)
  const diff = dl.getTime() - now.getTime()
  return Math.ceil(diff / (1000 * 60 * 60 * 24))
}

type FilterType = 'all' | 'overdue' | 'today' | 'week'

export function DeadlinesPage({ wsOn }: DeadlinesPageProps) {
  const [tasks, setTasks] = useState<Task[]>([])
  const [deptMap, setDeptMap] = useState<Record<string, string>>({})
  const [deptColorMap, setDeptColorMap] = useState<Record<string, string>>({})
  const [deadlineColors, setDeadlineColors] = useState<Record<string, string>>({
    overdue: '#ef4444', today: '#f97316', tomorrow: '#f59e0b', week: '#a3a3a3',
  })
  const [filter, setFilter] = useState<FilterType>('all')
  const [showChart, setShowChart] = useState(false)
  const [hoveredDay, setHoveredDay] = useState<{ x: number; y: number; tasks: Task[] } | null>(null)

  const loadTasks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/kanban/tasks`)
      if (res.ok) {
        const data = await res.json()
        setTasks(data.filter((t: Task) => t.deadline && t.status !== 'done'))
      }
    } catch {}
  }, [])

  const loadDepts = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/otdels`)
      if (res.ok) {
        const data = await res.json()
        const list = Array.isArray(data) ? data : (data.otdels || [])
        const map: Record<string, string> = {}
        const colors: Record<string, string> = {}
        for (const o of list) {
          const id = o.otdelid || o.id || ''
          if (id) {
            map[id] = o.name
            if (o.color) colors[id] = o.color
          }
        }
        setDeptMap(map)
        setDeptColorMap(colors)
      }
    } catch {}
  }, [])

  const loadConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/kanban/config/settings`)
      if (res.ok) {
        const data = await res.json()
        if (data.deadline_colors) {
          setDeadlineColors(prev => ({ ...prev, ...data.deadline_colors }))
        }
      }
    } catch {}
  }, [])

  useEffect(() => { loadTasks(); loadDepts(); loadConfig() }, [loadTasks, loadDepts, loadConfig])

  // Live updates
  useEffect(() => {
    if (!wsOn) return
    const events = ['kanban:task_created', 'kanban:task_updated', 'kanban:task_deleted', 'kanban:tasks_deleted']
    const unsubs = events.map(e => wsOn(e, () => loadTasks()))
    return () => { unsubs.forEach(u => u()) }
  }, [wsOn, loadTasks])

  // Categorize tasks
  const categorized = useMemo(() => {
    const overdue: Task[] = []
    const today: Task[] = []
    const week: Task[] = []
    const later: Task[] = []

    for (const t of tasks) {
      if (!t.deadline) continue
      const days = daysUntil(t.deadline)
      if (days < 0) overdue.push(t)
      else if (days === 0) today.push(t)
      else if (days <= 7) week.push(t)
      else later.push(t)
    }

    // Sort each group by deadline
    const sortByDL = (a: Task, b: Task) => new Date(a.deadline!).getTime() - new Date(b.deadline!).getTime()
    overdue.sort(sortByDL)
    today.sort(sortByDL)
    week.sort(sortByDL)
    later.sort(sortByDL)

    return { overdue, today, week, later }
  }, [tasks])

  // Filter
  const filtered = useMemo(() => {
    if (filter === 'overdue') return categorized.overdue
    if (filter === 'today') return categorized.today
    if (filter === 'week') return [...categorized.today, ...categorized.week]
    return [...categorized.overdue, ...categorized.today, ...categorized.week, ...categorized.later]
  }, [categorized, filter])

  const PRIORITY_COLORS: Record<string, string> = {
    critical: '#ef4444', high: '#f97316', medium: '#f59e0b', low: '#6b7280',
  }

  const renderTask = (task: Task, urgency: 'overdue' | 'today' | 'week' | 'later') => {
    const days = daysUntil(task.deadline!)
    const urgencyClass = urgency === 'overdue' ? 'overdue' : urgency === 'today' ? 'today' : ''

    let deadlineText = ''
    if (days < 0) deadlineText = `${Math.abs(days)}д назад`
    else if (days === 0) deadlineText = 'Сегодня'
    else if (days === 1) deadlineText = 'Завтра'
    else deadlineText = formatDate(task.deadline!)

    const deptColor = deptColorMap[task.department] || 'var(--text-muted)'
    const prioColor = PRIORITY_COLORS[task.priority] || 'var(--text-muted)'

    return (
      <div key={task.id} className={`deadline-task-row ${urgencyClass}`}>
        <span className="deadline-task-id">{task.id}</span>
        <span className="deadline-task-sep" />
        <span className="deadline-task-title">{task.title}</span>
        <span className="deadline-task-sep" />
        <span className="deadline-task-dept" style={{ color: deptColor }}>
          {deptMap[task.department] || task.department}
        </span>
        <span className="deadline-task-sep" />
        <span className="deadline-task-status" style={{ color: STATUS_COLORS[task.status] || '#6b7280' }}>
          {STATUS_LABELS[task.status] || task.status}
        </span>
        <span className="deadline-task-sep" />
        <span className="deadline-task-priority" style={{ color: prioColor }}>
          {PRIORITY_LABELS[task.priority] || task.priority}
        </span>
        <span className="deadline-task-sep" />
        <span className={`deadline-task-date ${urgencyClass}`}>
          {deadlineText}
        </span>
      </div>
    )
  }

  return (
    <div className="deadlines-page">
      {/* Header */}
      <div className="deadlines-header">
        <h1 className="deadlines-title">Дедлайны</h1>
      </div>

      {/* Metric cards */}
      <div className="deadlines-metrics">
        <button
          className={`deadline-metric-card ${filter === 'overdue' ? 'active' : ''}`}
          onClick={() => setFilter('overdue')}
        >
          <div className="deadline-metric-value danger">{categorized.overdue.length}</div>
          <div className="deadline-metric-label">Просрочено</div>
        </button>
        <button
          className={`deadline-metric-card ${filter === 'today' ? 'active' : ''}`}
          onClick={() => setFilter('today')}
        >
          <div className="deadline-metric-value accent">{categorized.today.length}</div>
          <div className="deadline-metric-label">Сегодня</div>
        </button>
        <button
          className={`deadline-metric-card ${filter === 'week' ? 'active' : ''}`}
          onClick={() => setFilter('week')}
        >
          <div className="deadline-metric-value">{categorized.week.length}</div>
          <div className="deadline-metric-label">Эта неделя</div>
        </button>
        <button
          className={`deadline-metric-card ${filter === 'all' ? 'active' : ''}`}
          onClick={() => setFilter('all')}
        >
          <div className="deadline-metric-value">{tasks.length}</div>
          <div className="deadline-metric-label">Все с дедлайном</div>
        </button>
      </div>

      {/* Task list */}
      <div className={`deadlines-list ${filter}`}>
        {filtered.length === 0 ? (
          <div className="deadlines-empty">
            <span className="deadlines-empty-icon">🎉</span>
            <span>Нет задач с дедлайном{filter !== 'all' ? ' в этом фильтре' : ''}</span>
          </div>
        ) : (
          <>
            {categorized.overdue.length > 0 && filter === 'all' && (
              <div className="deadline-group">
                <h3 className="deadline-group-title danger">🚨 Просроченные</h3>
                {categorized.overdue.map(t => renderTask(t, 'overdue'))}
              </div>
            )}
            {categorized.today.length > 0 && (filter === 'all' || filter === 'today' || filter === 'week') && (
              <div className="deadline-group">
                <h3 className="deadline-group-title accent">⏰ Сегодня</h3>
                {categorized.today.map(t => renderTask(t, 'today'))}
              </div>
            )}
            {categorized.week.length > 0 && (filter === 'all' || filter === 'week') && (
              <div className="deadline-group">
                <h3 className="deadline-group-title">📅 Эта неделя</h3>
                {categorized.week.map(t => renderTask(t, 'week'))}
              </div>
            )}
            {categorized.later.length > 0 && filter === 'all' && (
              <div className="deadline-group">
                <h3 className="deadline-group-title">📆 Позже</h3>
                {categorized.later.map(t => renderTask(t, 'later'))}
              </div>
            )}
          </>
        )}
      </div>

      {/* Chart toggle button */}
      <button
        className="deadlines-chart-toggle"
        onClick={() => setShowChart(v => !v)}
      >
        <span className={`toggle-arrow ${showChart ? 'open' : ''}`}>▼</span>
        <span>{showChart ? 'Скрыть график' : 'График'}</span>
      </button>

      {/* Calendar / Chart section */}
      <div className={`deadlines-chart-section ${showChart ? 'open' : ''}`}>
        <div className="deadlines-chart-content">
          <h3 className="deadlines-chart-title">Календарь дедлайнов</h3>
          <div className="deadlines-calendar">
            {(() => {
              // Build calendar grid for current + next month
              const now = new Date()
              const months = [now.getMonth(), (now.getMonth() + 1) % 12]
              const years = [now.getFullYear(), now.getMonth() === 11 ? now.getFullYear() + 1 : now.getFullYear()]

              // Build deadline lookup
              const deadlineMap: Record<string, Task[]> = {}
              for (const t of tasks) {
                if (!t.deadline) continue
                const d = new Date(t.deadline)
                const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
                if (!deadlineMap[key]) deadlineMap[key] = []
                deadlineMap[key].push(t)
              }

              const monthNames = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
              const dayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

              return months.map((month, mi) => {
                const year = years[mi] ?? now.getFullYear()
                const firstDay = new Date(year, month, 1)
                const lastDay = new Date(year, month + 1, 0)
                const startPad = (firstDay.getDay() + 6) % 7 // Mon=0
                const days: (number | null)[] = []
                for (let i = 0; i < startPad; i++) days.push(null)
                for (let d = 1; d <= lastDay.getDate(); d++) days.push(d)

                return (
                  <div key={`${year}-${month}`} className="deadline-calendar-month">
                    <h4 className="deadline-calendar-month-title">{monthNames[month]} {year}</h4>
                    <div className="deadline-calendar-grid">
                      {dayNames.map(dn => (
                        <div key={dn} className="deadline-calendar-day-name">{dn}</div>
                      ))}
                      {days.map((day, di) => {
                        if (day === null) return <div key={`pad-${di}`} className="deadline-calendar-day empty" />
                        const dateKey = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
                        const dayTasks = deadlineMap[dateKey] || []
                        const isToday = day === now.getDate() && month === now.getMonth() && year === now.getFullYear()
                        const isOverdue = dayTasks.some(t => daysUntil(t.deadline!) < 0)
                        const hasFuture = dayTasks.some(t => { const d = daysUntil(t.deadline!); return d > 0 && d <= 7 })
                        const dayColor = isOverdue ? deadlineColors.overdue
                          : isToday ? deadlineColors.today
                          : hasFuture ? deadlineColors.week
                          : 'transparent'

                        return (
                          <div
                            key={dateKey}
                            className={`deadline-calendar-day ${isToday ? 'today' : ''} ${dayTasks.length > 0 ? 'has-tasks' : ''} ${isOverdue ? 'overdue' : ''}`}
                            style={dayTasks.length > 0 ? { borderLeft: `2px solid ${dayColor}` } : undefined}
                            onMouseEnter={dayTasks.length > 0 ? (e) => {
                              const rect = e.currentTarget.getBoundingClientRect()
                              setHoveredDay({ x: rect.left + rect.width / 2, y: rect.top - 8, tasks: dayTasks })
                            } : undefined}
                            onMouseLeave={() => setHoveredDay(null)}
                          >
                            <span className="deadline-calendar-day-num">{day}</span>
                            {dayTasks.length > 0 && (
                              <span className="deadline-calendar-badge">{dayTasks.length}</span>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )
              })
            })()}
          </div>
        </div>
      </div>

      {/* Floating calendar tooltip */}
      {hoveredDay && (
        <div
          className="deadline-calendar-tooltip"
          style={{
            position: 'fixed',
            left: hoveredDay.x,
            top: hoveredDay.y,
            transform: 'translateX(-50%) translateY(-100%)',
            zIndex: 9999,
          }}
        >
          {hoveredDay.tasks.map(t => (
            <div key={t.id} className="deadline-calendar-tooltip-item">
              <span className="deadline-calendar-tooltip-id">{t.id}</span>
              <span className="deadline-calendar-tooltip-title">{t.title}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
