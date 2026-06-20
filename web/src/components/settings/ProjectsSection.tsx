/**
 * ProjectsSection — settings section for Projects.
 * Manages project settings and configurations.
 */
import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from '../../config'
import { SECTION_INFO } from './types'

interface ProjectSettings {
  // Future: project-specific settings
  auto_archive_completed: boolean
  show_goals_in_kanban: boolean
  default_task_priority: string
}

const DEFAULT_SETTINGS: ProjectSettings = {
  auto_archive_completed: false,
  show_goals_in_kanban: true,
  default_task_priority: 'medium',
}

export function ProjectsSection() {
  const [settings, setSettings] = useState<ProjectSettings>(DEFAULT_SETTINGS)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  // Load settings
  const loadSettings = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/config/settings`)
      if (!res.ok) return
      const data = await res.json()
      // Merge with defaults
      setSettings({
        ...DEFAULT_SETTINGS,
        ...data.projects,
      })
    } catch (e) {
      console.error('[projects-settings] load error:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadSettings()
  }, [loadSettings])

  // Save settings
  const saveSettings = useCallback(async (newSettings: ProjectSettings) => {
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/api/config/settings`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ projects: newSettings }),
      })
      if (res.ok) {
        setSettings(newSettings)
      }
    } catch (e) {
      console.error('[projects-settings] save error:', e)
    } finally {
      setSaving(false)
    }
  }, [])

  if (loading) {
    return (
      <div className="settings-section">
        <div className="settings-section-loading">
          <span className="tool-spinner" />
        </div>
      </div>
    )
  }

  return (
    <div className="settings-section">
      <div className="settings-section-header">
        <h2>{SECTION_INFO.projects.title}</h2>
        <p>{SECTION_INFO.projects.description}</p>
      </div>

      <div className="settings-section-content">
        {/* Auto archive */}
        <div className="settings-row">
          <div className="settings-row-info">
            <div className="settings-row-label">Автоархивация завершённых</div>
            <div className="settings-row-description">
              Автоматически архивировать задачи при переводе в статус "done"
            </div>
          </div>
          <label className="settings-toggle">
            <input
              type="checkbox"
              checked={settings.auto_archive_completed}
              onChange={e => saveSettings({ ...settings, auto_archive_completed: e.target.checked })}
              disabled={saving}
            />
            <span className="settings-toggle-slider" />
          </label>
        </div>

        {/* Show goals in kanban */}
        <div className="settings-row">
          <div className="settings-row-info">
            <div className="settings-row-label">Показывать цели в Kanban</div>
            <div className="settings-row-description">
              Отображать привязку к целям проекта на карточках задач
            </div>
          </div>
          <label className="settings-toggle">
            <input
              type="checkbox"
              checked={settings.show_goals_in_kanban}
              onChange={e => saveSettings({ ...settings, show_goals_in_kanban: e.target.checked })}
              disabled={saving}
            />
            <span className="settings-toggle-slider" />
          </label>
        </div>

        {/* Default task priority */}
        <div className="settings-row">
          <div className="settings-row-info">
            <div className="settings-row-label">Приоритет по умолчанию</div>
            <div className="settings-row-description">
              Приоритет для новых задач, создаваемых в рамках проекта
            </div>
          </div>
          <select
            className="settings-select"
            value={settings.default_task_priority}
            onChange={e => saveSettings({ ...settings, default_task_priority: e.target.value })}
            disabled={saving}
          >
            <option value="low">Низкий</option>
            <option value="medium">Средний</option>
            <option value="high">Высокий</option>
          </select>
        </div>
      </div>
    </div>
  )
}
