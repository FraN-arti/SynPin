/**
 * KanbanStats — statistics and analytics for the global Kanban board.
 * Displayed below the kanban columns, accessible via smooth scroll.
 * Updates live via WebSocket events.
 */
import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from '../config'
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'

interface KanbanStatsProps {
  wsOn?: (type: string, handler: (data: unknown) => void) => () => void
}

interface ExtendedStats {
  total: number
  by_status: Record<string, number>
  by_department: Record<string, number>
  by_priority: Record<string, number>
  overdue: number
  avg_completion_hours: number
  timeline: { date: string; completed: number; created: number }[]
  active: number
  done: number
}

const STATUS_COLORS: Record<string, string> = {
  backlog: '#6b7280', todo: '#3b82f6', ready: '#a855f7',
  in_progress: '#f97316', review: '#f59e0b', revision: '#ec4899',
  blocked: '#ef4444', done: '#22c55e',
}

const STATUS_LABELS: Record<string, string> = {
  backlog: 'Бэклог', todo: 'TODO', ready: 'READY',
  in_progress: 'В работе', review: 'Ревью', revision: 'Доработка',
  blocked: 'Блокировка', done: 'Выполнено',
}

const PRIORITY_COLORS: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', medium: '#f59e0b', low: '#6b7280',
}

const PRIORITY_LABELS: Record<string, string> = {
  critical: 'Критический', high: 'Высокий', medium: 'Средний', low: 'Низкий',
}

export function KanbanStats({ wsOn }: KanbanStatsProps) {
  const [stats, setStats] = useState<ExtendedStats | null>(null)

  const loadStats = useCallback(() => {
    fetch(`${API_BASE}/api/kanban/stats/extended`)
      .then(r => r.json())
      .then(setStats)
      .catch((e) => console.error('[kanbanstats] load stats failed:', e))
  }, [])

  useEffect(() => { loadStats() }, [loadStats])

  // Live updates — re-fetch on any kanban change
  useEffect(() => {
    if (!wsOn) return
    const events = [
      'kanban:task_created', 'kanban:task_updated', 'kanban:task_deleted',
      'kanban:tasks_deleted', 'kanban:columns_updated', 'kanban:labels_updated',
    ]
    const unsubs = events.map(e => wsOn(e, () => loadStats()))
    return () => { unsubs.forEach(u => u()) }
  }, [wsOn, loadStats])

  if (!stats) return null

  const statusData = Object.entries(stats.by_status).map(([key, val]) => ({
    name: STATUS_LABELS[key] || key,
    value: val,
    color: STATUS_COLORS[key] || '#6b7280',
  }))

  const deptData = Object.entries(stats.by_department)
    .sort((a, b) => b[1] - a[1])
    .map(([name, val]) => ({ name, value: val }))

  const priorityData = Object.entries(stats.by_priority).map(([key, val]) => ({
    name: PRIORITY_LABELS[key] || key,
    value: val,
    color: PRIORITY_COLORS[key] || '#6b7280',
  }))

  return (
    <div className="kanban-stats" id="kanban-stats">
      {/* ── Metric Cards ── */}
      <div className="stats-metrics-row">
        <div className="stats-metric-card">
          <div className="stats-metric-value">{stats.total}</div>
          <div className="stats-metric-label">Всего задач</div>
        </div>
        <div className="stats-metric-card accent">
          <div className="stats-metric-value">{stats.active}</div>
          <div className="stats-metric-label">Активных</div>
        </div>
        <div className="stats-metric-card success">
          <div className="stats-metric-value">{stats.done}</div>
          <div className="stats-metric-label">Выполнено</div>
        </div>
        <div className="stats-metric-card danger">
          <div className="stats-metric-value">{stats.overdue}</div>
          <div className="stats-metric-label">Просрочено</div>
        </div>
        <div className="stats-metric-card">
          <div className="stats-metric-value">{stats.avg_completion_hours}ч</div>
          <div className="stats-metric-label">Среднее время</div>
        </div>
      </div>

      {/* ── Charts Row 1: Timeline + Status Donut ── */}
      <div className="stats-charts-row" style={{ gridTemplateColumns: '3fr 1fr' }}>
        <div className="stats-chart-card wide">
          <h3 className="stats-chart-title">Активность за 30 дней</h3>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={stats.timeline}>
              <defs>
                <linearGradient id="gradCompleted" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gradCreated" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f97316" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis
                dataKey="date"
                tick={{ fill: '#737373', fontSize: 10 }}
                tickFormatter={d => d.slice(5)}
                axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
              />
              <YAxis tick={{ fill: '#737373', fontSize: 10 }} axisLine={{ stroke: 'rgba(255,255,255,0.1)' }} />
              <Tooltip
                contentStyle={{
                  background: 'rgba(10,10,20,0.95)',
                  border: '1px solid rgba(255,255,255,0.15)',
                  borderRadius: '8px',
                  color: '#ffffff',
                  fontSize: '12px',
                  padding: '8px 12px',
                }}
                itemStyle={{ color: '#ffffff' }}
                labelStyle={{ color: '#a3a3a3' }}
              />
              <Legend
                wrapperStyle={{ fontSize: '11px', color: '#a3a3a3' }}
                iconType="circle"
                iconSize={8}
              />
              <Area
                type="monotone"
                dataKey="completed"
                name="Выполнено"
                stroke="#22c55e"
                fill="url(#gradCompleted)"
                strokeWidth={2}
              />
              <Area
                type="monotone"
                dataKey="created"
                name="Создано"
                stroke="#f97316"
                fill="url(#gradCreated)"
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="stats-chart-card narrow">
          <h3 className="stats-chart-title">По статусам</h3>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={statusData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={80}
                paddingAngle={2}
                dataKey="value"
              >
                {statusData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: 'rgba(10,10,20,0.95)',
                  border: '1px solid rgba(255,255,255,0.15)',
                  borderRadius: '8px',
                  color: '#ffffff',
                  fontSize: '12px',
                  padding: '8px 12px',
                }}
                itemStyle={{ color: '#ffffff' }}
                labelStyle={{ color: '#a3a3a3' }}
              />
              <Legend
                wrapperStyle={{ fontSize: '11px', color: '#a3a3a3' }}
                iconType="circle"
                iconSize={8}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Charts Row 2: Departments + Priorities ── */}
      <div className="stats-charts-row">
        <div className="stats-chart-card half">
          <h3 className="stats-chart-title">По отделам</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={deptData} layout="vertical" cursor="default">
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis type="number" tick={{ fill: '#737373', fontSize: 10 }} axisLine={{ stroke: 'rgba(255,255,255,0.1)' }} />
              <YAxis
                type="category"
                dataKey="name"
                tick={{ fill: '#a3a3a3', fontSize: 11 }}
                width={120}
                axisLine={{ stroke: 'rgba(255,255,255,0.1)' }}
              />
              <Tooltip
                contentStyle={{
                  background: 'rgba(10,10,20,0.95)',
                  border: '1px solid rgba(255,255,255,0.15)',
                  borderRadius: '8px',
                  color: '#ffffff',
                  fontSize: '12px',
                  padding: '8px 12px',
                }}
                itemStyle={{ color: '#ffffff' }}
                labelStyle={{ color: '#a3a3a3' }}
              />
              <Bar
                dataKey="value"
                fill="#f97316"
                radius={[0, 4, 4, 0]}
                activeBar={{ fill: '#fb923c', fillOpacity: 0.85, filter: 'drop-shadow(0 0 8px rgba(249,115,22,0.4))' }}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="stats-chart-card half">
          <h3 className="stats-chart-title">По приоритетам</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={priorityData} cursor="default">
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis dataKey="name" tick={{ fill: '#a3a3a3', fontSize: 11 }} axisLine={{ stroke: 'rgba(255,255,255,0.1)' }} />
              <YAxis tick={{ fill: '#737373', fontSize: 10 }} axisLine={{ stroke: 'rgba(255,255,255,0.1)' }} />
              <Tooltip
                contentStyle={{
                  background: 'rgba(10,10,20,0.95)',
                  border: '1px solid rgba(255,255,255,0.15)',
                  borderRadius: '8px',
                  color: '#ffffff',
                  fontSize: '12px',
                  padding: '8px 12px',
                }}
                itemStyle={{ color: '#ffffff' }}
                labelStyle={{ color: '#a3a3a3' }}
              />
              <Bar
                dataKey="value"
                radius={[4, 4, 0, 0]}
                activeBar={{ fillOpacity: 0.85, filter: 'drop-shadow(0 0 8px rgba(249,115,22,0.4))' }}
              >
                {priorityData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  )
}
