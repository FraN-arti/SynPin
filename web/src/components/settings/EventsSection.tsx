/**
 * EventsSection — settings tab for the EventBus.
 *
 * For MVP: in-app channel only (toggle + auto-fade timeout + clear-all).
 * Future: a list of configured delivery channels (Telegram, desktop, email).
 *
 * Layout follows the same row pattern as CronSection's `.cron-limit-row`:
 * label | control | hint — so each setting sits on one horizontal line,
 * matching the rest of the settings UI.
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

const DEFAULT_SETTINGS: InAppSettings = {
  enabled: true,
  auto_fade_seconds: 8,
  max_visible: 4,
}

function parseIntClamped(raw: string, min: number, max: number, fallback: number): number {
  const v = parseInt(raw, 10)
  if (Number.isNaN(v)) return fallback
  return Math.max(min, Math.min(max, v))
}

export function EventsSection() {
  const [settings, setSettings] = useState<InAppSettings | null>(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/events/settings`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.in_app) setSettings({ ...DEFAULT_SETTINGS, ...data.in_app })
      })
      .catch(() => {})
  }, [])

  const update = async (patch: Partial<InAppSettings>) => {
    const res = await fetch(`${API_BASE}/api/events/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    })
    if (!res.ok) return
    const data = await res.json()
    if (data?.in_app) setSettings({ ...DEFAULT_SETTINGS, ...data.in_app })
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
        <p className="settings-card-desc">
          Тосты в правом нижнем углу когда что-то происходит в SynPin.
          Сейчас триггер срабатывает на ответ любого агента.
        </p>

        <div className="settings-field-row">
          <Toggle
            label="Показывать уведомления"
            checked={settings.enabled}
            onChange={(v) => update({ enabled: v })}
          />
        </div>

        <div className="events-setting-row">
          <label className="events-setting-label" htmlFor="fade-seconds">
            Автоисчезание через (секунд)
          </label>
          <input
            id="fade-seconds"
            type="number"
            min={1}
            max={60}
            className="events-setting-input"
            value={settings.auto_fade_seconds}
            onChange={(e) => update({
              auto_fade_seconds: parseIntClamped(e.target.value, 1, 60, DEFAULT_SETTINGS.auto_fade_seconds),
            })}
          />
          <span className="events-setting-hint">от 1 до 60</span>
        </div>

        <div className="events-setting-row">
          <label className="events-setting-label" htmlFor="max-visible">
            Максимум одновременно видимых тостов
          </label>
          <input
            id="max-visible"
            type="number"
            min={1}
            max={20}
            className="events-setting-input"
            value={settings.max_visible}
            onChange={(e) => update({
              max_visible: parseIntClamped(e.target.value, 1, 20, DEFAULT_SETTINGS.max_visible),
            })}
          />
          <span className="events-setting-hint">от 1 до 20</span>
        </div>
      </SettingsCard>

      <SettingsCard title="Каналы доставки">
        <p className="settings-card-desc">
          В будущем здесь появятся каналы: Telegram, Desktop, Email и другие.
          Сейчас доступен только in-app.
        </p>
      </SettingsCard>

      <SettingsCard title="Действия">
        <p className="settings-card-desc">
          Очистить историю событий. Непрочитанные счётчики обнулятся,
          в стеке тостов ничего не останется.
        </p>
        <div className="provider-actions">
          <button className="settings-btn-danger" onClick={handleClear}>
            Очистить все события
          </button>
        </div>
      </SettingsCard>
    </div>
  )
}