/**
 * EventsSection — settings tab for the EventBus.
 *
 * For MVP: in-app channel only (toggle + auto-fade timeout + max visible).
 * Future: a list of configured delivery channels (Telegram, desktop, email).
 *
 * Layout follows the same row pattern as CronSection's `.cron-limit-row`:
 * label | control — so each setting sits on one horizontal line,
 * matching the rest of the settings UI.
 */

import { useEffect, useState } from 'react'
import { API_BASE } from '../../config'
import { SettingsCard } from '../SettingsCard'
import { LoadingSpinner } from '../LoadingSpinner'
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

  if (!settings) {
    return <LoadingSpinner text="Загрузка..." />
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

        <div className="events-setting-row events-setting-row--divider">
          <div className="events-setting-label-block">
            <label htmlFor="fade-seconds">Автоисчезание</label>
            <span className="events-setting-sublabel">
              Через сколько секунд тост уйдёт сам, если его не закрыть вручную
            </span>
          </div>
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
        </div>

        <div className="events-setting-row events-setting-row--divider">
          <div className="events-setting-label-block">
            <label htmlFor="max-visible">Максимум тостов</label>
            <span className="events-setting-sublabel">
              Сколько одновременно видно в углу. Старые уходят, новые встают в стек
            </span>
          </div>
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
        </div>
      </SettingsCard>

      <SettingsCard title="Каналы доставки">
        <p className="settings-card-desc">
          В будущем здесь появятся каналы: Telegram, Desktop, Email и другие.
          Сейчас доступен только in-app.
        </p>
      </SettingsCard>
    </div>
  )
}