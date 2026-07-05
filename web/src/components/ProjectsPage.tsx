/**
 * ProjectsPage — overview of all projects with detail view.
 * Shows project cards with progress, departments, and deadlines.
 * Live-updates via WebSocket.
 *
 * Design: follows the SynPin design system (glassmorphism, CSS vars, themes).
 */
import { useState, useEffect, useCallback, useMemo } from 'react'
import { API_BASE } from '../config'
import { LoadingSpinner } from './LoadingSpinner'
import { MouseTooltip } from './MouseTooltip'

interface ProjectGoal {
  id: string
  title: string
  status: 'backlog' | 'in_progress' | 'completed'
  description: string
  completed_at?: string
}

interface ProjectDepartment {
  id: string
  name?: string
  role: string
  is_main: boolean
  joined_at: string
}

interface ArchiveEntry {
  id: string
  type: string
  title: string
  task_id?: string
  task_ids?: string[]
  department?: string
  summary?: string
  completed_at?: string
  archived_at?: string
}

interface Project {
  id: string
  name: string
  description: string
  status: 'active' | 'paused' | 'completed' | 'archived'
  priority: string
  main_department: string
  departments: ProjectDepartment[]
  goals: ProjectGoal[]
  archive: ArchiveEntry[]
  work_dir?: string
  created_at: string
  updated_at: string
  deadline?: string
  tags: string[]
}

interface Department {
  id: string
  name: string
  description?: string
  color?: string
  head?: string
  head_name?: string
  workers?: string[]
  workers_names?: { id: string; name?: string }[]
}

interface Task {
  id: string
  title: string
  status: string
  department: string
  project_id?: string
  project_goal_id?: string
}

type StatusFilter = 'all' | 'active' | 'paused' | 'completed'

interface ProjectsPageProps {
  wsOn: (event: string, handler: (msg: any) => void) => () => void
}

// ── Helpers ────────────────────────────────────────────────────────────

const STATUS_LABELS: Record<string, string> = {
  active: 'Активен',
  paused: 'Приостановлен',
  completed: 'Завершён',
  archived: 'В архиве',
}

const PRIORITY_LABELS: Record<string, string> = {
  critical: 'Критический',
  high: 'Высокий',
  medium: 'Средний',
  low: 'Низкий',
}

const TASK_STATUS_LABELS: Record<string, string> = {
  todo: 'К выполнению',
  in_progress: 'В работе',
  done: 'Выполнено',
  blocked: 'Заблокировано',
  review: 'На проверке',
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'active': return 'var(--green)'
    case 'paused': return 'var(--yellow)'
    case 'completed': return 'var(--blue, #3b82f6)'
    case 'archived': return 'var(--text-dim)'
    default: return 'var(--text-dim)'
  }
}

function getStatusTagClass(status: string): string {
  switch (status) {
    case 'active': return 'tt-tag-green'
    case 'paused': return 'tt-tag-yellow'
    case 'completed': return 'tt-tag-blue'
    default: return 'tt-tag-gray'
  }
}

function getPriorityTagClass(priority: string): string {
  switch (priority) {
    case 'critical': return 'tt-tag-red'
    case 'high': return 'tt-tag-orange'
    case 'medium': return 'tt-tag-yellow'
    case 'low': return 'tt-tag-green'
    default: return 'tt-tag-gray'
  }
}

function getTaskStatusColor(status: string): string {
  switch (status) {
    case 'done': return 'var(--green)'
    case 'in_progress': return 'var(--orange)'
    case 'blocked': return 'var(--red)'
    case 'review': return 'var(--blue, #3b82f6)'
    default: return 'var(--text-dim)'
  }
}

function getDaysLeft(deadline?: string): number | null {
  if (!deadline) return null
  const now = new Date()
  const dl = new Date(deadline)
  return Math.ceil((dl.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

// ── Component ──────────────────────────────────────────────────────────

export function ProjectsPage({ wsOn }: ProjectsPageProps) {
  const [projects, setProjects] = useState<Project[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)

  // Department name lookup
  const deptMap: Record<string, string> = {}
  for (const d of departments) { deptMap[d.id] = d.name }
  const [filter, setFilter] = useState<StatusFilter>('all')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedProject, setSelectedProject] = useState<Project | null>(null)
  const [projectTasks, setProjectTasks] = useState<Task[]>([])
  const [deptSearch, setDeptSearch] = useState('')
  const [newProject, setNewProject] = useState({
    name: '',
    description: '',
    main_department: '',
    selected_departments: [] as string[],
    department_roles: {} as Record<string, string>,
    goals_text: '',
    work_dir: '',
  })

  // Edit modal state
  const [showEditModal, setShowEditModal] = useState(false)
  const [editForm, setEditForm] = useState({
    name: '',
    description: '',
    status: '',
    priority: '',
    work_dir: '',
    deadline: '',
    tags: '',
  })
  const [editSaving, setEditSaving] = useState(false)

  // Delete confirmation state
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  // Quick status change
  const [showStatusDropdown, setShowStatusDropdown] = useState(false)

  // ── Data loading ───────────────────────────────────────────────────

  const loadProjects = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/projects`, { cache: 'no-store' })
      if (!res.ok) { setProjects([]); return }
      const data = await res.json()
      setProjects(data.projects || [])
    } catch (e) {
      console.error('[projects] load error:', e)
      setProjects([])
    } finally {
      setLoading(false)
    }
  }, [])

  const loadDepartments = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/otdels`, { cache: 'no-store' })
      if (!res.ok) return
      const data = await res.json()
      setDepartments((data.otdels || []).map((d: any) => ({
        id: d.otdelid,
        name: d.name,
        description: d.description || '',
        color: d.color || '#f97316',
        head: d.head || '',
        head_name: d.head_name || '',
        workers: d.workers || [],
        workers_names: d.workers_names || [],
      })))
    } catch (e) {
      console.error('[departments] load error:', e)
    }
  }, [])

  const loadProjectTasks = useCallback(async (projectId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/kanban/tasks?project_id=${projectId}`, { cache: 'no-store' })
      if (!res.ok) return
      const data = await res.json()
      setProjectTasks(Array.isArray(data) ? data : [])
    } catch (e) {
      console.error('[project-tasks] load error:', e)
    }
  }, [])

  // ── Effects ────────────────────────────────────────────────────────

  useEffect(() => {
    loadProjects()
    loadDepartments()
  }, [loadProjects, loadDepartments])

  useEffect(() => {
    const off1 = wsOn('project:created', () => loadProjects())
    const off2 = wsOn('project:updated', () => loadProjects())
    const off3 = wsOn('project:deleted', () => {
      loadProjects()
      setSelectedProject(null)
    })
    return () => { off1(); off2(); off3() }
  }, [wsOn, loadProjects])

  useEffect(() => {
    if (selectedProject) {
      loadProjectTasks(selectedProject.id)
    }
  }, [selectedProject, loadProjectTasks])

  // ── Derived state ──────────────────────────────────────────────────

  const filteredProjects = useMemo(() => {
    if (filter === 'all') return projects
    return projects.filter(p => p.status === filter)
  }, [projects, filter])

  const filteredDepartments = useMemo(() => {
    if (!deptSearch.trim()) return departments
    const q = deptSearch.toLowerCase()
    return departments.filter(d =>
      d.name.toLowerCase().includes(q) || d.id.toLowerCase().includes(q)
    )
  }, [departments, deptSearch])

  // Stats for detail view (from real tasks)
  const taskStats = useMemo(() => {
    const total = projectTasks.length
    const done = projectTasks.filter(t => t.status === 'done').length
    const inProgress = projectTasks.filter(t => t.status === 'in_progress').length
    const progress = total > 0 ? (done / total) * 100 : 0
    return { total, done, inProgress, progress }
  }, [projectTasks])

  // ── Handlers ───────────────────────────────────────────────────────

  const toggleDepartment = (deptId: string) => {
    setNewProject(prev => {
      const selected = prev.selected_departments.includes(deptId)
        ? prev.selected_departments.filter(id => id !== deptId)
        : [...prev.selected_departments, deptId]
      const mainDept = prev.main_department === deptId ? '' : prev.main_department
      return { ...prev, selected_departments: selected, main_department: mainDept }
    })
  }

  const setMainDepartment = (deptId: string) => {
    setNewProject(prev => ({
      ...prev,
      main_department: deptId,
      selected_departments: prev.selected_departments.includes(deptId)
        ? prev.selected_departments
        : [...prev.selected_departments, deptId],
    }))
  }

  const updateDepartmentRole = (deptId: string, role: string) => {
    setNewProject(prev => ({
      ...prev,
      department_roles: { ...prev.department_roles, [deptId]: role },
    }))
  }

  const parseGoals = (text: string) =>
    text.split('\n').map(l => l.trim()).filter(l => l.length > 0).map(l => ({ title: l, description: '' }))

  const resetForm = () => {
    setNewProject({
      name: '', description: '', main_department: '',
      selected_departments: [], department_roles: {}, goals_text: '', work_dir: '',
    })
    setDeptSearch('')
  }

  const handleCreate = async () => {
    if (!newProject.name.trim() || !newProject.main_department) return
    const goals = parseGoals(newProject.goals_text)
    const payload = {
      name: newProject.name,
      description: newProject.description,
      main_department: newProject.main_department,
      departments: newProject.selected_departments.map(id => ({
        id,
        role: newProject.department_roles[id] || '',
        is_main: id === newProject.main_department,
      })),
      goals: goals.map((g) => ({
        title: g.title,
        status: 'backlog' as const,
        description: g.description,
      })),
      work_dir: newProject.work_dir || undefined,
    }
    try {
      const res = await fetch(`${API_BASE}/api/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (res.ok) {
        setShowCreateModal(false)
        resetForm()
        loadProjects()
      }
    } catch (e) {
      console.error('[projects] create error:', e)
    }
  }

  // ── Edit project ──────────────────────────────────────────────────

  const openEditModal = useCallback(() => {
    if (!selectedProject) return
    setEditForm({
      name: selectedProject.name,
      description: selectedProject.description,
      status: selectedProject.status,
      priority: selectedProject.priority,
      work_dir: selectedProject.work_dir || '',
      deadline: selectedProject.deadline ? selectedProject.deadline.split('T')[0] as string : '',
      tags: selectedProject.tags.join(', '),
    })
    setShowEditModal(true)
  }, [selectedProject])

  const handleUpdate = async () => {
    if (!selectedProject || !editForm.name.trim()) return
    setEditSaving(true)
    try {
      const payload: Record<string, unknown> = {
        name: editForm.name,
        description: editForm.description,
        status: editForm.status,
        priority: editForm.priority,
        work_dir: editForm.work_dir || null,
        deadline: editForm.deadline ? new Date(editForm.deadline).toISOString() : null,
        tags: editForm.tags.split(',').map(t => t.trim()).filter(Boolean),
      }
      const res = await fetch(`${API_BASE}/api/projects/${selectedProject.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (res.ok) {
        const data = await res.json()
        setSelectedProject(data.project)
        setShowEditModal(false)
        loadProjects()
      }
    } catch (e) {
      console.error('[projects] update error:', e)
    } finally {
      setEditSaving(false)
    }
  }

  // ── Delete project ────────────────────────────────────────────────

  const handleDelete = async () => {
    if (!selectedProject) return
    try {
      const res = await fetch(`${API_BASE}/api/projects/${selectedProject.id}`, {
        method: 'DELETE',
      })
      if (res.ok) {
        setShowDeleteConfirm(false)
        setSelectedProject(null)
        loadProjects()
      }
    } catch (e) {
      console.error('[projects] delete error:', e)
    }
  }

  // ── Quick status change ─────────────────────────────────────────

  const changeStatus = async (newStatus: string) => {
    if (!selectedProject || newStatus === selectedProject.status) {
      setShowStatusDropdown(false)
      return
    }
    try {
      const res = await fetch(`${API_BASE}/api/projects/${selectedProject.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      })
      if (res.ok) {
        const data = await res.json()
        setSelectedProject(data.project)
        loadProjects()
      }
    } catch (e) {
      console.error('[projects] status change error:', e)
    }
    setShowStatusDropdown(false)
  }

  // ── Loading state ──────────────────────────────────────────────────

  if (loading) {
    return (
      <div className="projects-page">
        <LoadingSpinner text="Загрузка проектов..." />
      </div>
    )
  }

  // ── Detail View ────────────────────────────────────────────────────

  if (selectedProject) {
    const p = selectedProject
    return (
      <div className="projects-page">
        {/* Header */}
        <div className="projects-detail-header">
          <button className="projects-back-btn" onClick={() => { setSelectedProject(null); setShowStatusDropdown(false) }}>
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M12 4L6 10L12 16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
          <div className="projects-header">
            <div className="projects-title-row">
              <h1 className="projects-title">{p.name}</h1>
              <div className="project-status-wrapper">
                <button
                  className="project-status-badge clickable"
                  style={{ backgroundColor: getStatusColor(p.status) }}
                  onClick={() => setShowStatusDropdown(!showStatusDropdown)}
                >
                  {STATUS_LABELS[p.status] || p.status}
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none" style={{ marginLeft: 4 }}>
                    <path d="M2.5 4L5 6.5L7.5 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </button>
                {showStatusDropdown && (
                  <div className="project-status-dropdown">
                    {(['active', 'paused', 'completed', 'archived'] as const).map(s => (
                      <button
                        key={s}
                        className={`project-status-option ${p.status === s ? 'current' : ''}`}
                        onClick={() => changeStatus(s)}
                      >
                        <span className="project-status-dot" style={{ backgroundColor: getStatusColor(s) }} />
                        {STATUS_LABELS[s]}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <div className="projects-description-italic">{p.description || 'Без описания'}</div>
          </div>
          <div className="project-actions">
            <button className="project-action-btn" onClick={openEditModal}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M10.5 1.5L12.5 3.5L4 12H2V10L10.5 1.5Z" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Редактировать
            </button>
            <button className="project-action-btn danger" onClick={() => setShowDeleteConfirm(true)}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M2 4H12M5 4V2.5C5 2.22 5.22 2 5.5 2H8.5C8.78 2 9 2.22 9 2.5V4M11 4V11.5C11 11.78 10.78 12 10.5 12H3.5C3.22 12 3 11.78 3 11.5V4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Удалить
            </button>
          </div>
        </div>

        {/* Progress */}
        <div className="project-detail-section">
          <h3>Прогресс</h3>
          <p className="project-section-hint">Общий процент выполнения задач проекта. Рассчитывается как отношение задач со статусом "done" к общему числу задач.</p>
          <div className="project-progress">
            <div className="project-progress-bar">
              <div className="project-progress-fill" style={{ width: `${taskStats.progress}%` }} />
            </div>
            <span className="project-progress-text">
              {taskStats.done} / {taskStats.total} задач ({Math.round(taskStats.progress)}%)
            </span>
          </div>
        </div>

        {/* Goals */}
        {p.goals.length > 0 && (
          <div className="project-detail-section">
            <h3>Цели проекта ({p.goals.length})</h3>
            <div className="project-goals-list-detail">
              {p.goals.map(goal => (
                <MouseTooltip
                  key={goal.id}
                  content={
                    <div>
                      <div className="tt-title">{goal.title}</div>
                      {goal.description && <div style={{ marginTop: 4, color: 'var(--text-dim)' }}>{goal.description}</div>}
                      <div className="tt-row" style={{ marginTop: 4 }}>
                        <span className="tt-label">Статус:</span>
                        <span className={`tt-tag ${goal.status === 'completed' ? 'tt-tag-green' : goal.status === 'in_progress' ? 'tt-tag-orange' : 'tt-tag-gray'}`}>
                          {goal.status === 'completed' ? 'Завершена' : goal.status === 'in_progress' ? 'В работе' : 'В планах'}
                        </span>
                      </div>
                    </div>
                  }
                >
                  <div className={`project-goal-item ${goal.status}`}>
                    <span className="project-goal-icon">
                      {goal.status === 'completed' ? '✓' : goal.status === 'in_progress' ? '○' : '…'}
                    </span>
                    <span className="project-goal-title">{goal.title}</span>
                  </div>
                </MouseTooltip>
              ))}
            </div>
          </div>
        )}

        {/* Departments — block layout */}
        {p.departments.length > 0 && (
          <div className="project-detail-section">
            <h3>Отделы проекта ({p.departments.length})</h3>
            <div className="project-departments-grid">
              {p.departments.map(dept => {
                const deptInfo = departments.find(d => d.id === dept.id)
                return (
                  <div key={dept.id} className={`project-dept-block ${dept.is_main ? 'main' : ''}`}>
                    <div className="dept-block-header">
                      <span className="dept-block-name">{deptInfo?.name || dept.id}</span>
                      {dept.is_main && <span className="dept-block-main-badge">★ Основной</span>}
                    </div>
                    {dept.role && <div className="dept-block-role">{dept.role}</div>}
                    <div className="dept-block-divider" />
                    <div className="dept-block-body">
                      {deptInfo?.head_name || deptInfo?.head ? (
                        <div className="dept-block-head">
                          <span className="dept-block-head-label">Глава:</span>
                          <span className="dept-block-head-name">{deptInfo?.head_name || deptInfo?.head}</span>
                        </div>
                      ) : (
                        <div className="dept-block-head dim">Глава не назначен</div>
                      )}
                      {deptInfo?.workers_names && deptInfo.workers_names.length > 0 && (
                        <div className="dept-block-workers">
                          <span className="dept-block-workers-label">Сотрудники ({deptInfo.workers_names.length}):</span>
                          <span className="dept-block-workers-list">{deptInfo.workers_names.map(w => w.name || w.id).join(', ')}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Tasks */}
        <div className="project-detail-section">
          <h3>Задачи проекта ({projectTasks.length})</h3>
          <p className="project-section-hint">Задачи из Kanban-доски, привязанные к этому проекту через поле project_id. Отображаются все задачи независимо от статуса.</p>
          {projectTasks.length === 0 ? (
            <p className="project-empty-tasks">Нет задач в этом проекте</p>
          ) : (
            <div className="project-tasks-list">
              {projectTasks.map(task => (
                <MouseTooltip
                  key={task.id}
                  content={
                    <div>
                      <div className="tt-title">{task.title}</div>
                      <div className="tt-row" style={{ marginTop: 4 }}>
                        <span className="tt-label">ID:</span>
                        <span className="tt-value" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}>{task.id}</span>
                      </div>
                      <div className="tt-row">
                        <span className="tt-label">Отдел:</span>
                        <span className="tt-value">{task.department || '—'}</span>
                      </div>
                      <div className="tt-row">
                        <span className="tt-label">Статус:</span>
                        <span className="tt-value">{TASK_STATUS_LABELS[task.status] || task.status}</span>
                      </div>
                    </div>
                  }
                >
                  <div className="project-task-item">
                    <span className="project-task-id">{task.id}</span>
                    <span className="project-task-title">{task.title}</span>
                    <span className="project-task-dept">{deptMap[task.department] || task.department || 'Без отдела'}</span>
                    <span className="project-task-status" style={{ color: getTaskStatusColor(task.status) }}>
                      {task.status}
                    </span>
                  </div>
                </MouseTooltip>
              ))}
            </div>
          )}
        </div>

        {/* Archive */}
        {p.archive.length > 0 && (
          <div className="project-detail-section">
            <h3>Архив ({p.archive.length})</h3>
            <div className="project-archive-list">
              {p.archive.map(entry => (
                <MouseTooltip
                  key={entry.id}
                  content={
                    <div>
                      <div className="tt-title">{entry.title}</div>
                      <div className="tt-row" style={{ marginTop: 4 }}>
                        <span className="tt-label">Тип:</span>
                        <span className="tt-value">{entry.type === 'milestone' ? 'Веха' : 'Задача'}</span>
                      </div>
                      {entry.completed_at && (
                        <div className="tt-row">
                          <span className="tt-label">Завершено:</span>
                          <span className="tt-value">{formatDate(entry.completed_at)}</span>
                        </div>
                      )}
                      {entry.summary && <div style={{ marginTop: 6, color: 'var(--text-dim)', fontSize: 11 }}>{entry.summary}</div>}
                    </div>
                  }
                >
                  <div className="project-archive-item">
                    <span className="project-archive-icon">{entry.type === 'milestone' ? '🏁' : '📌'}</span>
                    <span className="project-archive-title">{entry.title}</span>
                    <span className="project-archive-date">
                      {entry.completed_at ? formatDate(entry.completed_at) : ''}
                    </span>
                  </div>
                </MouseTooltip>
              ))}
            </div>
          </div>
        )}

        {/* ── Edit Modal ──────────────────────────────────────────────── */}
        {showEditModal && (
          <div className="modal-overlay" onClick={() => setShowEditModal(false)}>
            <div className="modal-content" style={{ maxWidth: 480 }} onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <h2>Редактировать проект</h2>
                <button className="modal-close" onClick={() => setShowEditModal(false)}>×</button>
              </div>
              <div className="projects-form">
                <div className="projects-form-group">
                  <label>Название <span className="required">*</span></label>
                  <input
                    type="text"
                    value={editForm.name}
                    onChange={e => setEditForm({ ...editForm, name: e.target.value })}
                    placeholder="Название проекта"
                    autoFocus
                  />
                </div>
                <div className="projects-form-group">
                  <label>Описание</label>
                  <textarea
                    value={editForm.description}
                    onChange={e => setEditForm({ ...editForm, description: e.target.value })}
                    placeholder="Описание проекта"
                    rows={2}
                  />
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div className="projects-form-group">
                    <label>Статус</label>
                    <select
                      className="settings-select"
                      value={editForm.status}
                      onChange={e => setEditForm({ ...editForm, status: e.target.value })}
                    >
                      <option value="active">Активен</option>
                      <option value="paused">Приостановлен</option>
                      <option value="completed">Завершён</option>
                      <option value="archived">В архиве</option>
                    </select>
                  </div>
                  <div className="projects-form-group">
                    <label>Приоритет</label>
                    <select
                      className="settings-select"
                      value={editForm.priority}
                      onChange={e => setEditForm({ ...editForm, priority: e.target.value })}
                    >
                      <option value="low">Низкий</option>
                      <option value="medium">Средний</option>
                      <option value="high">Высокий</option>
                      <option value="critical">Критический</option>
                    </select>
                  </div>
                </div>
                <div className="projects-form-group">
                  <label>Дедлайн</label>
                  <input
                    type="date"
                    value={editForm.deadline}
                    onChange={e => setEditForm({ ...editForm, deadline: e.target.value })}
                  />
                </div>
                <div className="projects-form-group">
                  <label>Рабочий каталог</label>
                  <input
                    type="text"
                    value={editForm.work_dir}
                    onChange={e => setEditForm({ ...editForm, work_dir: e.target.value })}
                    placeholder="D:\projects\my-project"
                  />
                </div>
                <div className="projects-form-group">
                  <label>Теги</label>
                  <input
                    type="text"
                    value={editForm.tags}
                    onChange={e => setEditForm({ ...editForm, tags: e.target.value })}
                    placeholder="тег1, тег2, тег3"
                  />
                  <span className="projects-form-hint">Через запятую</span>
                </div>
              </div>
              <div className="modal-footer">
                <button className="projects-btn-cancel" onClick={() => setShowEditModal(false)}>Отмена</button>
                <button
                  className="projects-btn-create"
                  onClick={handleUpdate}
                  disabled={!editForm.name.trim() || editSaving}
                >
                  {editSaving ? 'Сохранение...' : 'Сохранить'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Delete Confirmation ──────────────────────────────────────── */}
        {showDeleteConfirm && (
          <div className="modal-overlay" onClick={() => setShowDeleteConfirm(false)}>
            <div className="modal-content" style={{ maxWidth: 400 }} onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <h2>Удалить проект?</h2>
                <button className="modal-close" onClick={() => setShowDeleteConfirm(false)}>×</button>
              </div>
              <div style={{ padding: '0 24px 24px', color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.6 }}>
                <p style={{ margin: 0 }}>
                  Проект <strong style={{ color: 'var(--white)' }}>"{p.name}"</strong> будет удалён навсегда.
                </p>
                <p style={{ margin: '8px 0 0', fontSize: 13, color: 'var(--text-dim)' }}>
                  Задачи будут отвязаны от проекта (без удаления).
                </p>
              </div>
              <div className="modal-footer">
                <button className="projects-btn-cancel" onClick={() => setShowDeleteConfirm(false)}>Отмена</button>
                <button
                  className="projects-btn-create danger"
                  onClick={handleDelete}
                >
                  Удалить проект
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  // ── List View ──────────────────────────────────────────────────────

  const projectCount = projects.length

  return (
    <div className="projects-page">
      {/* Header */}
      <div className="projects-top-bar">
        <div className="projects-header projects-header--list">
          <div className="projects-title-row">
            <h1 className="projects-title">Проекты</h1>
            <span className="count-badge">{projectCount}</span>
          </div>
          <p className="projects-subtitle">Управление проектами: создание, настройка отделов и целей, отслеживание прогресса</p>
        </div>
        <button className="projects-create-btn" onClick={() => setShowCreateModal(true)}>
          + Создать проект
        </button>
      </div>

      {/* Metric cards */}
      <div className="projects-metrics">
        {([
          ['all', 'Всего', projects.length],
          ['active', 'Активные', projects.filter(p => p.status === 'active').length],
          ['paused', 'Приостановлены', projects.filter(p => p.status === 'paused').length],
          ['completed', 'Завершены', projects.filter(p => p.status === 'completed').length],
        ] as const).map(([key, label, count]) => (
          <button
            key={key}
            className={`project-metric-card ${filter === key ? 'active' : ''}`}
            onClick={() => setFilter(key)}
          >
            <span className="metric-value">{count}</span>
            <span className="metric-label">{label}</span>
          </button>
        ))}
      </div>

      {/* Projects list */}
      <div className="projects-list">
        {filteredProjects.length === 0 ? (
          <div className="empty-state">
            <span className="empty-state-icon">📁</span>
            <p>Проектов пока нет</p>
            <p className="empty-state-hint">Создайте первый проект, чтобы начать</p>
          </div>
        ) : (
          filteredProjects.map(project => (
            <MouseTooltip
              key={project.id}
              content={
                <div>
                  <div className="tt-title">{project.name}</div>
                  <div className="tt-row" style={{ marginTop: 4 }}>
                    <span className="tt-label">Статус:</span>
                    <span className={`tt-tag ${getStatusTagClass(project.status)}`}>{STATUS_LABELS[project.status]}</span>
                  </div>
                  <div className="tt-row">
                    <span className="tt-label">Приоритет:</span>
                    <span className={`tt-tag ${getPriorityTagClass(project.priority)}`}>{PRIORITY_LABELS[project.priority] || project.priority}</span>
                  </div>
                  <div className="tt-row">
                    <span className="tt-label">Отделы:</span>
                    <span className="tt-value">{project.departments.length}</span>
                  </div>
                  <div className="tt-row">
                    <span className="tt-label">Цели:</span>
                    <span className="tt-value">{project.goals.length}</span>
                  </div>
                  <div className="tt-row">
                    <span className="tt-label">Создан:</span>
                    <span className="tt-value">{formatDate(project.created_at)}</span>
                  </div>
                  {project.deadline && (
                    <div className="tt-row">
                      <span className="tt-label">Дедлайн:</span>
                      <span className="tt-value">{formatDate(project.deadline)}</span>
                    </div>
                  )}
                </div>
              }
            >
              <div
                className={`project-card ${project.status}`}
                onClick={() => setSelectedProject(project)}
              >
                <div className="project-card-header">
                  <div className="project-card-title">
                    <h3>{project.name}</h3>
                    <span
                      className="project-status-badge"
                      style={{ backgroundColor: getStatusColor(project.status) }}
                    >{project.status}</span>
                  </div>
                  <span className="project-priority-badge">
                    {PRIORITY_LABELS[project.priority] || project.priority}
                  </span>
                </div>

                {project.description && (
                  <p className="project-card-description">{project.description}</p>
                )}

                {/* Departments */}
                {project.departments.length > 0 && (
                  <div className="project-departments">
                    <span className="project-departments-label">Отделы:</span>
                    <div className="project-departments-list">
                      {project.departments.map(dept => {
                        const deptInfo = departments.find(d => d.id === dept.id)
                        const deptName = dept.name || deptInfo?.name || dept.id
                        return (
                          <span key={dept.id} className={`project-department-badge ${dept.is_main ? 'main' : ''}`}>
                            {deptName}{dept.is_main && ' ★'}
                          </span>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* Deadline */}
                {project.deadline && (
                  <div className="project-deadline">
                    <span>📅</span>
                    <span>
                      {formatDate(project.deadline)}
                      {(() => {
                        const d = getDaysLeft(project.deadline)
                        if (d === null) return null
                        if (d < 0) return <span className="overdue"> (просрочено)</span>
                        if (d === 0) return <span className="today"> (сегодня)</span>
                        if (d <= 7) return <span className="warning"> (осталось {d} дн.)</span>
                        return <span> (осталось {d} дн.)</span>
                      })()}
                    </span>
                  </div>
                )}

                {/* Goals */}
                {project.goals.length > 0 && (
                  <div className="project-goals">
                    <span className="project-goals-label">Цели:</span>
                    <div className="project-goals-list">
                      {project.goals.slice(0, 3).map(goal => (
                        <span key={goal.id} className={`project-goal-badge ${goal.status}`}>
                          {goal.status === 'completed' ? '✓' : goal.status === 'in_progress' ? '○' : '…'} {goal.title}
                        </span>
                      ))}
                      {project.goals.length > 3 && (
                        <span className="project-goals-more">+{project.goals.length - 3}</span>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </MouseTooltip>
          ))
        )}
      </div>

      {/* ── Create Modal ──────────────────────────────────────────── */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content modal-content--wide" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Новый проект</h2>
              <button className="modal-close" onClick={() => setShowCreateModal(false)} aria-label="Закрыть">×</button>
            </div>

            <div className="modal-body">
              <div className="modal-form">
                {/* Название */}
                <div className="modal-form-row">
                  <label htmlFor="np-name" className="modal-form-label">
                    Название <span className="modal-form-required">*</span>
                  </label>
                  <input
                    id="np-name"
                    type="text"
                    className="modal-form-input"
                    value={newProject.name}
                    onChange={e => setNewProject({ ...newProject, name: e.target.value })}
                    placeholder="Например: Разработка мобильного приложения"
                    autoFocus
                  />
                </div>

                {/* Описание */}
                <div className="modal-form-row">
                  <label htmlFor="np-desc" className="modal-form-label">
                    Описание
                  </label>
                  <textarea
                    id="np-desc"
                    className="modal-form-input"
                    value={newProject.description}
                    onChange={e => setNewProject({ ...newProject, description: e.target.value })}
                    placeholder="О чём этот проект, какова его цель..."
                    rows={2}
                  />
                </div>

                {/* Рабочий каталог */}
                <div className="modal-form-row">
                  <label htmlFor="np-workdir" className="modal-form-label">
                    Рабочий каталог
                  </label>
                  <input
                    id="np-workdir"
                    type="text"
                    className="modal-form-input"
                    value={newProject.work_dir}
                    onChange={e => setNewProject({ ...newProject, work_dir: e.target.value })}
                    placeholder="D:\projects\my-project"
                  />
                </div>

                {/* Отделы */}
                <div className="modal-form-row">
                  <label className="modal-form-label">
                    Отделы <span className="modal-form-required">*</span>
                  </label>
                  <div className="dept-search-wrap">
                    <svg className="dept-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                      <circle cx="11" cy="11" r="8" />
                      <path d="m21 21-4.3-4.3" />
                    </svg>
                    <input
                      type="text"
                      className="dept-search-input"
                      value={deptSearch}
                      onChange={e => setDeptSearch(e.target.value)}
                      placeholder="Поиск отделов..."
                    />
                    {deptSearch && (
                      <button className="dept-search-clear" onClick={() => setDeptSearch('')} aria-label="Очистить">×</button>
                    )}
                  </div>
                  <div className="dept-list">
                    {filteredDepartments.length === 0 ? (
                      <div className="dept-empty">
                        {deptSearch ? 'Отделы не найдены' : 'Нет доступных отделов'}
                      </div>
                    ) : (
                      filteredDepartments.map(dept => {
                        const isSelected = newProject.selected_departments.includes(dept.id)
                        const isMain = newProject.main_department === dept.id
                        return (
                          <div
                            key={dept.id}
                            className={`dept-row ${isSelected ? 'selected' : ''}`}
                            onClick={() => toggleDepartment(dept.id)}
                          >
                            <span className={`dept-checkbox ${isSelected ? 'checked' : ''}`} aria-hidden="true">
                              {isSelected && (
                                <svg width="10" height="10" viewBox="0 0 10 10">
                                  <path d="M2 5l2.5 2.5L8 3" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                                </svg>
                              )}
                            </span>
                            <span className="dept-name">{dept.name}</span>
                            {isMain && <span className="dept-star" title="Основной отдел">★</span>}
                            {isSelected && (
                              <div className="dept-options" onClick={e => e.stopPropagation()}>
                                <button
                                  type="button"
                                  className={`dept-radio ${isMain ? 'checked' : ''}`}
                                  onClick={() => setMainDepartment(dept.id)}
                                  title={isMain ? 'Основной отдел' : 'Сделать основным'}
                                  aria-label={isMain ? 'Основной отдел' : 'Сделать основным'}
                                >
                                  {isMain && <span className="dept-radio-dot" />}
                                </button>
                                <span className="dept-radio-text">Основной</span>
                                <input
                                  type="text"
                                  className="dept-role-input"
                                  value={newProject.department_roles[dept.id] || ''}
                                  onChange={e => updateDepartmentRole(dept.id, e.target.value)}
                                  placeholder="Роль"
                                />
                              </div>
                            )}
                          </div>
                        )
                      })
                    )}
                  </div>
                  {newProject.selected_departments.length > 0 && !newProject.main_department && (
                    <span className="dept-warning">Выберите основной отдел</span>
                  )}
                </div>

                {/* Цели проекта */}
                <div className="modal-form-row">
                  <label htmlFor="np-goals" className="modal-form-label">
                    Цели проекта
                  </label>
                  <textarea
                    id="np-goals"
                    className="modal-form-input"
                    value={newProject.goals_text}
                    onChange={e => setNewProject({ ...newProject, goals_text: e.target.value })}
                    placeholder={"Запуск бета-версии к 1 июля\nНабор 100 пользователей\nИнтеграция с Telegram"}
                    rows={3}
                  />
                </div>
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setShowCreateModal(false)}>
                Отмена
              </button>
              <button
                className="btn-primary"
                onClick={handleCreate}
                disabled={!newProject.name.trim() || !newProject.main_department}
              >
                Создать проект
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
