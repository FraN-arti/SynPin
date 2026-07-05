/**
 * Deadlines settings section — configure deadline behavior.
 */
import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from '../../config'
import { SettingsCard } from '../SettingsCard'
import { ColorPicker } from '../ColorPicker'
import { Toggle } from './Toggle'

export function DeadlinesSection() {
  const [settings, setSettings] = useState({
    auto_escalate_overdue: false,
    notify_human_on_block: false,
    auto_archive_days: 30,
  })
  const [deadlineColors, setDeadlineColors] = useState<Record<string, string>>({
    overdue: '#ef4444', today: '#f97316', tomorrow: '#f59e0b', week: '#a3a3a3',
  })

  useEffect(() => {
    fetch(`${API_BASE}/api/kanban/config/settings`)
      .then(r => r.json())
      .then(data => {
        setSettings({
          auto_escalate_overdue: data.auto_escalate_overdue ?? false,
          notify_human_on_block: data.notify_human_on_block ?? false,
          auto_archive_days: data.auto_archive_days ?? 30,
        })
        if (data.deadline_colors) {
          setDeadlineColors({ ...deadlineColors, ...data.deadline_colors })
        }
      })
      .catch(() => {})
  }, [])

  const save = useCallback(async (patch: Record<string, unknown>) => {
    try {
      await fetch(`${API_BASE}/api/kanban/config/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      })
    } catch (e) {
      console.error('[deadlines] save error:', e)
    }
  }, [])

  return (
    <div className="settings-sections">
      <SettingsCard title="Дедлайны">
        <p className="settings-hint">Настройки автоматической обработки задач с дедлайнами</p>

        <div className="settings-divider-thin" />

        <Toggle
          label="Авто-утверждение при просрочке"
          checked={settings.auto_escalate_overdue}
          onChange={v => { setSettings(s => ({ ...s, auto_escalate_overdue: v })); save({ auto_escalate_overdue: v }) }}
        />
        <span className="settings-hint">Просроченные задачи автоматически перемещаются в колонку блокировок</span>

        <div className="settings-divider-thin" />

        <div className="settings-section-label">Цвета дат</div>
        <p className="settings-hint">Настройте цветовое оформление сроков на странице дедлайнов</p>
        <div style={{ display: 'flex', gap: '8px', marginTop: '8px', flexWrap: 'wrap' }}>
          {[
            { label: 'Просрочено', key: 'overdue', default: '#ef4444' },
            { label: 'Сегодня', key: 'today', default: '#f97316' },
            { label: 'Завтра', key: 'tomorrow', default: '#f59e0b' },
            { label: 'Неделя', key: 'week', default: '#a3a3a3' },
          ].map(item => {
            const currentColor = deadlineColors[item.key] || item.default
            return (
              <label key={item.key} style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '5px 10px', background: 'var(--glass-bg)',
                border: '1px solid var(--glass-border)', borderRadius: 'var(--radius, 8px)',
                cursor: 'pointer', transition: 'border-color 0.15s',
              }}>
                <ColorPicker
                  value={currentColor}
                  onChange={c => {
                    const next = { ...deadlineColors, [item.key]: c }
                    setDeadlineColors(next)
                    save({ deadline_colors: next })
                  }}
                />
                <span style={{ fontSize: '12px', color: currentColor, fontWeight: 600 }}>{item.label}</span>
              </label>
            )
          })}
        </div>
      </SettingsCard>
    </div>
  )
}