import { useEffect, useState, useRef } from 'react'
import { API_BASE as API } from '../../config'
import { SettingsCard } from '../SettingsCard'

// ─── Cron Section ───────────────────────────────────────────────
//
// Three cards:
//  1. Stats       — totals by status, next run, last run, agent limits
//  2. Tasks       — list of all jobs with pause / resume / delete / run-now
//  3. Proactivity — global limit + cron:fired log (proactive triggers live
//                   in the agent prompt; this card documents the policy)
//
// All data flows from /api/cron/* endpoints.

interface CronStats {
  total: number
  by_status: Record<string, number>
  next_run: null | {
    id: string
    name: string
    at: string
    in_seconds: number
  }
  last_run: null | {
    id: string
    name: string
    at: string
    ago_seconds: number
    result: 'success' | 'error' | 'skipped'
    result_message: string
    duration_ms: number | null
  }
  agent_limit: number
  agent_limit_default: number
  agent_limit_count: Record<string, number>
}

interface CronJob {
  id: string
  name: string
  created_by: string
  description: string
  schedule_type: 'once' | 'cron' | 'interval'
  schedule_expr: string
  timezone: string
  action_type: 'send_message' | 'run_prompt'
  action_target: string
  action_message: string
  action_agent: string
  delivery: 'private' | 'otdel' | 'silent'
  status: 'active' | 'paused' | 'completed' | 'missed'
  last_run_at: string | null
  next_run_at: string | null
  run_count: number
  last_result: 'success' | 'error' | 'skipped'
  last_result_message: string
  last_duration_ms: number | null
  created_at: string
  updated_at: string
}

function fmtRelative(seconds: number): string {
  if (seconds < 0) return 'только что'
  if (seconds < 60) return `${Math.round(seconds)}с`
  if (seconds < 3600) return `${Math.round(seconds / 60)}м`
  if (seconds < 86400) return `${Math.round(seconds / 3600)}ч ${Math.round((seconds % 3600) / 60)}м`
  return `${Math.round(seconds / 86400)}д`
}

function fmtTimestamp(iso: string | null): string {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: '2-digit',
      hour: '2-digit', minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function deliveryLabel(d: CronJob['delivery']): string {
  switch (d) {
    case 'private': return 'В чат'
    case 'otdel': return 'В отдел'
    case 'silent': return 'Без уведомлений'
  }
}

function statusColor(s: CronJob['status']): string {
  switch (s) {
    case 'active': return 'var(--orange, #f97316)'
    case 'paused': return '#94a3b8'
    case 'completed': return '#10b981'
    case 'missed': return '#ef4444'
  }
}

export function CronSection({ wsOn }: { wsOn?: (type: string, handler: (data: any) => void) => () => void } = {}) {
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState<CronStats | null>(null)
  const [jobs, setJobs] = useState<CronJob[]>([])
  const [filter, setFilter] = useState<'all' | 'active' | 'paused' | 'completed' | 'missed'>('all')
  const [pageSize] = useState(10)
  const [page, setPage] = useState(0)
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [holdProgress, setHoldProgress] = useState(0)  // 0..1, animation for hold-to-confirm
  const holdTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const holdStartRef = useRef<number>(0)
  const holdFrameRef = useRef<number | null>(null)
  const [agentLimit, setAgentLimit] = useState<number>(3)
  const [limitInput, setLimitInput] = useState<string>('3')
  const [savingLimit, setSavingLimit] = useState(false)
  const limitSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [retentionDays, setRetentionDays] = useState<number>(30)
  const [retentionInput, setRetentionInput] = useState<string>('30')
  const [retentionDefault, setRetentionDefault] = useState<number>(30)
  const [savingRetention, setSavingRetention] = useState(false)
  const retentionSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const loadAll = async () => {
    setLoading(true)
    try {
      const [statsRes, jobsRes, limitRes, retentionRes] = await Promise.all([
        fetch(`${API}/api/cron/stats`),
        fetch(`${API}/api/cron/jobs`),
        fetch(`${API}/api/cron/agent-limit`),
        fetch(`${API}/api/cron/retention`),
      ])
      if (statsRes.ok) setStats(await statsRes.json())
      if (jobsRes.ok) {
        const data = await jobsRes.json()
        setJobs(data.jobs || [])
      }
      if (limitRes.ok) {
        const data = await limitRes.json()
        setAgentLimit(data.agent_limit_per_creator)
        setLimitInput(String(data.agent_limit_per_creator))
      }
      if (retentionRes.ok) {
        const data = await retentionRes.json()
        setRetentionDays(data.retention_days)
        setRetentionInput(String(data.retention_days))
        setRetentionDefault(data.retention_default)
      }
    } catch (e) {
      console.error('Failed to load cron data', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAll()
    // Polling fallback every 60s
    const id = setInterval(loadAll, 60000)
    return () => clearInterval(id)
  }, [])

  // WS realtime — subscribe to cron:fired events for instant stats refresh.
  // This is the primary path; polling is just a safety net.
  useEffect(() => {
    if (!wsOn) return
    const off = wsOn('cron:fired', () => {
      // Light refresh — just stats + jobs, not the full page
      loadAll()
    })
    return off
  }, [wsOn])

  const filteredJobs = filter === 'all'
    ? jobs
    : jobs.filter(j => j.status === filter)

  // Reset page when filter changes
  useEffect(() => { setPage(0) }, [filter])

  // Clear selection when filter changes — selected IDs may not be on the
  // new page and would confuse the user.
  useEffect(() => { setSelected(new Set()) }, [filter])
  // Clear selection after a refresh if some jobs were deleted elsewhere
  useEffect(() => {
    setSelected(prev => {
      const existing = new Set<string>()
      for (const j of jobs) existing.add(j.id)
      const next = new Set<string>()
      for (const id of prev) if (existing.has(id)) next.add(id)
      return next
    })
  }, [jobs])

  // Hold-to-confirm bulk delete (1.5s). Mouse down starts, up cancels,
// timeout completes. Animates a 0→1 progress that drives a SVG ring.
  const HOLD_MS = 1500
  const startHold = () => {
    if (holdTimerRef.current) return
    holdStartRef.current = performance.now()
    setHoldProgress(0)
    const tick = () => {
      const elapsed = performance.now() - holdStartRef.current
      const p = Math.min(1, elapsed / HOLD_MS)
      setHoldProgress(p)
      if (p < 1) {
        holdFrameRef.current = requestAnimationFrame(tick)
      } else {
        // Fire the actual delete
        const ids = Array.from(selected)
        Promise.all(ids.map(id =>
          fetch(`${API}/api/cron/jobs/${id}`, { method: 'DELETE' })
        )).then(() => {
          setSelected(new Set())
          setHoldProgress(0)
          loadAll()
        })
      }
    }
    holdFrameRef.current = requestAnimationFrame(tick)
    holdTimerRef.current = setTimeout(() => {
      // safety net in case rAF stops firing
    }, HOLD_MS + 100)
  }
  const cancelHold = () => {
    if (holdFrameRef.current) cancelAnimationFrame(holdFrameRef.current)
    if (holdTimerRef.current) clearTimeout(holdTimerRef.current)
    holdFrameRef.current = null
    holdTimerRef.current = null
    setHoldProgress(0)
  }
  // Cleanup hold timers on unmount
  useEffect(() => () => cancelHold(), [])

  const toggleSelected = (id: string) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }
  const selectAllOnPage = () => {
    setSelected(prev => {
      const next = new Set(prev)
      for (const j of pagedJobs) next.add(j.id)
      return next
    })
  }
  const deselectAllOnPage = () => {
    setSelected(prev => {
      const next = new Set(prev)
      for (const j of pagedJobs) next.delete(j.id)
      return next
    })
  }

  const totalPages = Math.max(1, Math.ceil(filteredJobs.length / pageSize))
  const pagedJobs = filteredJobs.slice(page * pageSize, (page + 1) * pageSize)

  const handlePause = async (id: string) => {
    await fetch(`${API}/api/cron/jobs/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'paused' }),
    })
    loadAll()
  }
  const handleResume = async (id: string) => {
    await fetch(`${API}/api/cron/jobs/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'active' }),
    })
    loadAll()
  }
  const handleDelete = async (id: string) => {
    // Inline confirmation — no native confirm() dialog.
    // UI swaps the Delete button with [Yes] [Cancel] inline.
    if (confirmDeleteId !== id) {
      setConfirmDeleteId(id)
      return
    }
    await fetch(`${API}/api/cron/jobs/${id}`, { method: 'DELETE' })
    setConfirmDeleteId(null)
    loadAll()
  }
  const cancelDelete = () => setConfirmDeleteId(null)
  const handleRunNow = async (id: string) => {
    await fetch(`${API}/api/cron/jobs/${id}/run`, { method: 'POST' })
    loadAll()
  }
  const scheduleLimitSave = (val: number) => {
    if (limitSaveTimerRef.current) clearTimeout(limitSaveTimerRef.current)
    limitSaveTimerRef.current = setTimeout(async () => {
      if (val < 1) return
      setSavingLimit(true)
      try {
        const res = await fetch(`${API}/api/cron/agent-limit`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ agent_limit_per_creator: val }),
        })
        if (res.ok) {
          await loadAll()
        } else {
          console.error('Failed to save agent limit:', res.status, await res.text())
        }
      } catch (e) {
        console.error('Agent limit save error:', e)
      } finally {
        setSavingLimit(false)
      }
    }, 600) // 600ms debounce — saves when user stops typing
  }

  const scheduleRetentionSave = (val: number) => {
    if (retentionSaveTimerRef.current) clearTimeout(retentionSaveTimerRef.current)
    retentionSaveTimerRef.current = setTimeout(async () => {
      if (val < 1) return
      setSavingRetention(true)
      try {
        const res = await fetch(`${API}/api/cron/retention`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ retention_days: val }),
        })
        if (res.ok) {
          // Confirm by reading back from API; don't blindly trust
          // state. If the server-side save didn't take, we'll catch
          // the mismatch in loadAll() on the next tick.
          await loadAll()
        } else {
          console.error('Failed to save retention:', res.status, await res.text())
        }
      } catch (e) {
        console.error('Retention save error:', e)
      } finally {
        setSavingRetention(false)
      }
    }, 600)
  }

  // Cleanup on unmount
  useEffect(() => () => {
    if (limitSaveTimerRef.current) clearTimeout(limitSaveTimerRef.current)
    if (retentionSaveTimerRef.current) clearTimeout(retentionSaveTimerRef.current)
  }, [])

  return (
    <div className="cron-section">
      {/* Card 1: Stats */}
      <SettingsCard title="Статистика" loading={loading && !stats}>
        {stats && (
          <>
            <div className="cron-stats-grid">
              <StatBlock label="Всего" value={stats.total} />
              <StatBlock label="Активных" value={stats.by_status.active || 0} color="var(--orange, #f97316)" />
              <StatBlock label="На паузе" value={stats.by_status.paused || 0} color="#94a3b8" />
              <StatBlock label="Завершено" value={stats.by_status.completed || 0} color="#10b981" />
              <StatBlock label="Ошибка" value={stats.by_status.missed || 0} color="#ef4444" tooltip="Задача не выполнилась — огонь прошёл, агент упал, или сервер был офлайн в момент срабатывания. Наведи на конкретную задачу в списке ниже для деталей." />
            </div>

            <div className="cron-stats-run">
              {stats.next_run ? (
                <div className="cron-stat-line">
                  <span className="cron-stat-label">Ближайший запуск:</span>
                  <span className="cron-stat-value">
                    через <b>{fmtRelative(stats.next_run.in_seconds)}</b>
                    {' '}— <code>{stats.next_run.name}</code>
                  </span>
                  <span className="cron-stat-meta">({fmtTimestamp(stats.next_run.at)})</span>
                </div>
              ) : (
                <div className="cron-stat-line">
                  <span className="cron-stat-label">Ближайший запуск:</span>
                  <span className="cron-stat-empty">нет запланированных</span>
                </div>
              )}

              {stats.last_run ? (
                <div className="cron-stat-line" title={stats.last_run.result_message || ''}>
                  <span className="cron-stat-label">Последний запуск:</span>
                  <span className="cron-stat-value">
                    <b>{fmtRelative(stats.last_run.ago_seconds)}</b> назад
                    {' '}— <code>{stats.last_run.name}</code>
                  </span>
                  <span className={`cron-stat-result cron-result-${stats.last_run.result}`}>
                    {stats.last_run.result}
                    {stats.last_run.duration_ms != null && ` · ${stats.last_run.duration_ms}мс`}
                  </span>
                </div>
              ) : (
                <div className="cron-stat-line">
                  <span className="cron-stat-label">Последний запуск:</span>
                  <span className="cron-stat-empty">ещё не запускалось</span>
                </div>
              )}
            </div>
          </>
        )}
      </SettingsCard>

      {/* Card 2: Tasks list */}
      <SettingsCard title="Задачи" loading={loading && jobs.length === 0}>
        <div className="cron-filters">
          {(['all', 'active', 'paused', 'completed', 'missed'] as const).map(f => (
            <button
              key={f}
              className={`cron-filter-btn ${filter === f ? 'active' : ''}`}
              onClick={() => setFilter(f)}
            >
              {f === 'all' ? 'Все' :
               f === 'active' ? 'Активные' :
               f === 'paused' ? 'На паузе' :
               f === 'completed' ? 'Завершённые' : 'Ошибка'}
              {f !== 'all' && stats && (
                <span className="cron-filter-count">
                  {stats.by_status[f] || 0}
                </span>
              )}
            </button>
          ))}

          {/* Spacer pushes bulk-action to the right */}
          <div className="cron-filters-spacer" />

          {/* Bulk action — appears when at least one job is selected.
              Fades in/out instead of mount/unmount to feel smoother. */}
          <div className={`cron-bulk-action ${selected.size > 0 ? 'visible' : ''}`}>
            <span className="cron-bulk-count">Выбрано: {selected.size}</span>
            {selected.size === pagedJobs.length && pagedJobs.length > 0 ? (
              <button onClick={deselectAllOnPage} className="cron-link-btn">Снять все</button>
            ) : (
              <button onClick={selectAllOnPage} className="cron-link-btn">Выбрать все</button>
            )}
            <button
              onMouseDown={startHold}
              onMouseUp={cancelHold}
              onMouseLeave={cancelHold}
              onTouchStart={startHold}
              onTouchEnd={cancelHold}
              className={`cron-hold-btn ${holdProgress > 0 ? 'holding' : ''}`}
              disabled={selected.size === 0}
              title="Удерживай 1.5с чтобы удалить"
              style={{
                '--hold-progress': holdProgress,
              } as React.CSSProperties}
            >
              <svg className="cron-hold-ring" viewBox="0 0 24 24">
                <circle
                  className="cron-hold-ring-bg"
                  cx="12" cy="12" r="10"
                />
                <circle
                  className="cron-hold-ring-progress"
                  cx="12" cy="12" r="10"
                  strokeDasharray={`${2 * Math.PI * 10}`}
                  strokeDashoffset={`${2 * Math.PI * 10 * (1 - holdProgress)}`}
                />
              </svg>
              <span className="cron-hold-label">
                {holdProgress > 0 ? 'Удерживай...' : `Удалить (${selected.size})`}
              </span>
            </button>
          </div>
        </div>

        {pagedJobs.length === 0 ? (
          <div className="cron-empty">
            {filter === 'all'
              ? 'Крон-задач пока нет. Агенты могут создавать их через cron_manage tool.'
              : `Нет задач со статусом "${filter}".`}
          </div>
        ) : (
          <>
          <div className="cron-jobs" key={page}>
            {pagedJobs.map(job => (
              <div
              key={job.id}
              className={`cron-job ${job.status} ${selected.has(job.id) ? 'cron-job-selected' : ''}`}
            >
              <label className="cron-job-checkbox" title="Выбрать">
                <input
                  type="checkbox"
                  checked={selected.has(job.id)}
                  onChange={() => toggleSelected(job.id)}
                />
              </label>
              <div className="cron-job-body">
                <div className="cron-job-header">
                  <span className="cron-job-name">{job.name}</span>
                  <span className="cron-job-status" style={{ color: statusColor(job.status) }}>
                    {job.status}
                  </span>
                </div>

                <div className="cron-job-meta">
                  <span><b>Тип:</b> {job.schedule_type} — <code>{job.schedule_expr}</code></span>
                  <span><b>Действие:</b> {job.action_type}
                    {job.action_target && <> → <code>{job.action_target}</code></>}
                  </span>
                  <span><b>Доставка:</b> {deliveryLabel(job.delivery)}</span>
                  <span><b>Создал:</b> {job.created_by}</span>
                </div>

                {(job.next_run_at || job.last_run_at) && (
                  <div className="cron-job-schedule">
                    {job.next_run_at && (
                      <span className="cron-job-next">
                        <b>Следующий:</b> {fmtTimestamp(job.next_run_at)}
                      </span>
                    )}
                    {job.last_run_at && (
                      <span
                        className={`cron-job-last cron-result-${job.last_result}`}
                        title={job.last_result_message || ''}
                      >
                        <b>Последний:</b> {fmtTimestamp(job.last_run_at)} ({job.last_result}
                        {job.last_duration_ms != null && `, ${job.last_duration_ms}мс`})
                      </span>
                    )}
                  </div>
                )}

                <div className="cron-job-actions">
                  {job.status === 'active' && (
                    <button onClick={() => handlePause(job.id)} className="cron-action-btn">Пауза</button>
                  )}
                  {job.status === 'paused' && (
                    <button onClick={() => handleResume(job.id)} className="cron-action-btn">Возобновить</button>
                  )}
                  <button onClick={() => handleRunNow(job.id)} className="cron-action-btn">Запустить</button>
                  {confirmDeleteId === job.id ? (
                  <>
                    <span className="cron-confirm-text">Удалить?</span>
                    <button onClick={() => handleDelete(job.id)} className="cron-action-btn cron-action-danger">Да</button>
                    <button onClick={cancelDelete} className="cron-action-btn">Нет</button>
                  </>
                ) : (
                  <button onClick={() => handleDelete(job.id)} className="cron-action-btn cron-action-danger">Удалить</button>
                )}
                </div>
              </div>
              </div>
            ))}
          </div>
          {totalPages > 1 && (
            <div className="cron-pagination">
              <button
                className="cron-page-btn"
                disabled={page === 0}
                onClick={() => setPage(p => Math.max(0, p - 1))}
              >
                ← Пред
              </button>
              <span className="cron-page-info">
                {page + 1} / {totalPages}
                <span className="cron-page-total"> ({filteredJobs.length})</span>
              </span>
              <button
                className="cron-page-btn"
                disabled={page >= totalPages - 1}
                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              >
                След →
              </button>
            </div>
          )}
          </>
        )}
      </SettingsCard>

      {/* Card 3: Proactivity — global limit + policy */}
      <SettingsCard title="Проактивность">
        <p className="cron-card-desc">
          Лимит на количество активных cron-задач у одного создателя
          (агента или пользователя). Защищает от спама. Изменение
          применяется мгновенно, но существующие задачи не удаляются.
        </p>

        <div className="cron-limit-row">
          <label className="cron-limit-label">Глобальный лимит на создателя:</label>
          <input
            type="number"
            className="cron-limit-input"
            min={1}
            max={50}
            value={limitInput}
            onChange={e => {
              const next = e.target.value
              setLimitInput(next)
              const parsed = parseInt(next, 10)
              if (!isNaN(parsed) && parsed >= 1) scheduleLimitSave(parsed)
            }}
          />
          <span className="cron-limit-hint">
            {savingLimit ? '⏳ сохраняю...' :
             agentLimit !== parseInt(limitInput, 10) ? `не сохранено (${limitInput})` :
             agentLimit === stats?.agent_limit_default ? `по умолчанию: ${agentLimit}` :
             `текущий: ${agentLimit} (по умолчанию: ${stats?.agent_limit_default ?? 3})`}
          </span>
        </div>

        {stats && Object.keys(stats.agent_limit_count).length > 0 && (
          <div className="cron-limit-usage">
            <div className="cron-limit-usage-label">Использование по создателям:</div>
            {Object.entries(stats.agent_limit_count).map(([creator, count]) => (
              <div key={creator} className="cron-limit-usage-row">
                <span className="cron-limit-usage-name">{creator}</span>
                <span className="cron-limit-usage-count">
                  {count} / {stats.agent_limit}
                </span>
                <div className="cron-limit-bar">
                  <div
                    className="cron-limit-bar-fill"
                    style={{ width: `${Math.min(100, (count / stats.agent_limit) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="cron-policy">
          <h4 className="cron-policy-title">Политика доставки</h4>
          <ul className="cron-policy-list">
            <li><b>В чат (private)</b> — результат попадает в чат пользователю. Подходит для напоминаний и личных вопросов.</li>
            <li><b>В отдел (otdel)</b> — результат попадает в чат отдела + триггерит head-агента. Для командных задач.</li>
            <li><b>Без уведомлений (silent)</b> — только запись в лог/память. Без спама в чате. Для фоновых проверок.</li>
          </ul>
          <p className="cron-policy-hint">
            Триггеры проактивного cron (по ключевым словам типа «завтра», «через час»)
            живут в системном промпте агента. Эта секция только отображает
            фактические лимиты и текущее использование.
          </p>
        </div>
      </SettingsCard>

      {/* Card 4: Retention — auto-cleanup of old completed/missed jobs */}
      <SettingsCard title="Автоочистка">
        <p className="cron-card-desc">
          Завершённые и ошибочные крон-задачи старше указанного количества дней
          удаляются автоматически (раз в час). Активные и приостановленные
          задачи НЕ трогаются. Изменение применяется мгновенно.
        </p>

        <div className="cron-limit-row">
          <label className="cron-limit-label">Удалять выполненные старше (дней):</label>
          <input
            type="number"
            className="cron-limit-input"
            min={1}
            max={365}
            value={retentionInput}
            onChange={e => {
              const next = e.target.value
              setRetentionInput(next)
              const parsed = parseInt(next, 10)
              if (!isNaN(parsed) && parsed >= 1) scheduleRetentionSave(parsed)
            }}
          />
          <span className="cron-limit-hint">
            {savingRetention ? '⏳ сохраняю...' :
             retentionDays !== parseInt(retentionInput, 10) ? `не сохранено (${retentionInput})` :
             retentionDays === retentionDefault ? `по умолчанию: ${retentionDays}` :
             `текущий: ${retentionDays} (по умолчанию: ${retentionDefault})`}
          </span>
        </div>

        <p className="cron-policy-hint">
          Диапазон: 1–365 дней. Если папка <code>data/cron/jobs/</code> разрастается —
          уменьшите значение, чтобы старые записи вычищались быстрее.
          Активные напоминания и расписания никогда не удаляются автоматически.
        </p>
      </SettingsCard>
    </div>
  )
}

// ── Small inline components ─────────────────────────────────────

function StatBlock({
  label, value, color, tooltip,
}: { label: string; value: number; color?: string; tooltip?: string }) {
  return (
    <div className="cron-stat-block" title={tooltip || ''}>
      <div className="cron-stat-value" style={{ color: color || 'inherit' }}>{value}</div>
      <div className="cron-stat-label">{label}</div>
    </div>
  )
}
