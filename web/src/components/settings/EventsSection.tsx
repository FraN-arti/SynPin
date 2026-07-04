/**
 * EventsSection — settings tab for the EventBus.
 *
 * For MVP: in-app channel only (toggle + auto-fade timeout + clear-all).
 * Future: a list of configured delivery channels (Telegram, desktop, email).
 */

import { useEffect, useState } from 'react'
import { API_BASE } from '../../config'
import { SettingsCard } from '../SettingsCard'
import { Toggle } from './Toggle'

interface InAppSettings {
  enabled: boolean
  auto_fade_seconds: number
  max_visible: number
}

export function EventsSection() {
  const [settings, setSettings] = useState<InAppSettings | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetch(`${API_BASE}/api/events/settings`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.in_app) setSettings(data.in_app) })
      .catch(() => {})
  }, [])

  const update = async (patch: Partial<InAppSettings>): Promise<InAppSettings | null> => {
    setSaving(true)
    try {
      const res = await fetch(`${API_BASE}/api/events/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(patch),
      })
      if (!res.ok) return null
      const data = await res.json()
      const next = data?.in_app as InAppSettings
      setSettings(next)
      return next
    } finally {
      setSaving(false)
    }
  }

  const handleClear = async () => {
    if (!confirm('Очистить все события? Это действие нельзя отменить.')) return
    await fetch(`${API_BASE}/api/events/clear`, { method: 'POST' }).catch(() => {})
  }

  if (!settings) {
    return <div className="settings-sections">Загрузка…</div>
  }

  return (
    <div className="settings-sections">
      <SettingsCard title="In-app уведомления">
        <div className="settings-field">
          <Toggle
            label="Показывать уведомления в приложении"
            checked={settings.enabled}
            onChange={(v) => update({ enabled: v })}
          />
        </div>
        <div className="settings-field">
          <label htmlFor="fade-seconds">Автоисчезание через (секунд)</label>
          <input
            id="fade-seconds"
            type="number"
            min={1}
            max={60}
            className="settings-input"
            value={settings.auto_fade_seconds}
            disabled={saving}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10)
              if (!Number.isNaN(v)) update({ auto_fade_seconds: v })
            }}
          />
        </div>
        <div className="settings-field">
          <label htmlFor="max-visible">Максимум одновременно видимых тостов</label>
          <input
            id="max-visible"
            type="number"
            min={1}
            max={20}
            className="settings-input"
            value={settings.max_visible}
            disabled={saving}
            onChange={(e) => {
              const v = parseInt(e.target.value, 10)
              if (!Number.isNaN(v)) update({ max_visible: v })
            }}
          />
        </div>
      </SettingsCard>

      <SettingsCard title="Каналы доставки">
        <p className="settings-section-desc" style={{ margin: 0 }}>
          В будущем здесь появятся каналы: Telegram, Desktop, Email и другие.
          Сейчас доступен только in-app.
        </p>
      </SettingsCard>

      <SettingsCard title="Действия">
        <div className="provider-actions">
          <button className="settings-btn-danger" onClick={handleClear}>
            Очистить все события
          </button>
        </div>
      </SettingsCard>
    </div>
  )
}