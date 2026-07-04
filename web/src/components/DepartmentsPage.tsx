/**
 * DepartmentsPage — full-screen grid of department cards.
 *
 * Replaces the cramped widget-in-sidebar view with a dedicated page that
 * matches the project's bento-style design language (see ProjectsPage).
 * Each card shows: color dot, name, mentor role, escalation, agent count,
 * head agent, short description. Click → opens OtdelChatView via view switch.
 *
 * Data source: GET /api/otdels (already used by Sidebar widget — same shape).
 * Live refresh: listens for `otdels:list_changed` WS event.
 */

import { useCallback, useEffect, useState } from 'react'
import { API_BASE } from '../config'
import { LoadingSpinner } from './LoadingSpinner'

export interface Department {
  id: string
  name: string
  description: string
  color: string
  mentor_role: string
  escalation: string
  agent_count: number
  head: string
  workers: string[]
}

interface DepartmentsPageProps {
  /** Switch view to open OtdelChatView for given otdel */
  onOpenOtdel: (otdelId: string) => void
  /** Optional: WS subscribe helper, used to refresh on backend changes */
  wsOn?: (type: string, handler: (data: any) => void) => () => void
}

export function DepartmentsPage({ onOpenOtdel, wsOn }: DepartmentsPageProps) {
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)

  const loadDepartments = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/otdels`, { cache: 'no-store' })
      if (!res.ok) return
      const data = await res.json()
      setDepartments(
        (data.otdels || []).map((d: any) => ({
          id: d.otdelid,
          name: d.name,
          description: d.description || '',
          color: d.color || '#f97316',
          mentor_role: d.mentor_role || '',
          escalation: d.escalation || '',
          agent_count: d.agent_count ?? 0,
          head: d.head || '',
          workers: d.workers || [],
        }))
      )
    } catch (err) {
      console.error('Failed to load departments:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDepartments()
  }, [loadDepartments])

  // Refresh on backend "list changed" event (create/update/delete)
  useEffect(() => {
    if (!wsOn) return
    const off = wsOn('otdels:list_changed', () => {
      loadDepartments()
    })
    return off
  }, [wsOn, loadDepartments])

  if (loading) {
    return (
      <div className="departments-page">
        <LoadingSpinner text="Загрузка отделов..." />
      </div>
    )
  }

  return (
    <div className="departments-page">
      <div className="departments-top-bar">
        <div className="departments-title-row">
          <h1 className="departments-title">Отделы</h1>
          <span className="departments-count-badge">{departments.length}</span>
        </div>
        <p className="departments-subtitle">
          Многоагентные отделы. Клик по карточке откроет чат отдела.
        </p>
      </div>

      {departments.length === 0 ? (
        <div className="departments-empty">
          <span className="departments-empty-icon">🏢</span>
          <p>Отделов пока нет.</p>
          <p className="departments-empty-hint">
            Создайте отделы в Настройки → Отделы, чтобы они появились здесь.
          </p>
        </div>
      ) : (
        <div className="departments-grid">
          {departments.map(dept => (
            <div
              key={dept.id}
              className="department-tile"
              onClick={() => onOpenOtdel(dept.id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onOpenOtdel(dept.id)
                }
              }}
            >
              <div className="department-tile-accent" style={{ background: dept.color }} />
              <div className="department-tile-body">
                <div className="department-tile-header">
                  <span
                    className="department-color-dot"
                    style={{ background: dept.color }}
                  />
                  <h3 className="department-tile-name">{dept.name}</h3>
                </div>

                {dept.description && (
                  <p className="department-tile-description">{dept.description}</p>
                )}

                <div className="department-tile-footer">
                  <span className="department-tile-count">
                    {dept.agent_count}{' '}
                    {dept.agent_count === 1 ? 'агент' : dept.agent_count < 5 ? 'агента' : 'агентов'}
                  </span>
                  <span className="department-tile-cta">Открыть чат →</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}