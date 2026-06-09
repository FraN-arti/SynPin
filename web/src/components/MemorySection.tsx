import { useState, useEffect } from 'react'

// ─── Memory Section ──────────────────────────────────────────

import { API_BASE as API } from '../config'

// Parse entry into structured {key, value} or return raw text
function parseEntry(entry: string): { key: string; value: string } {
  const match = entry.match(/^([^:—\-]+)[\s]*[:—\-]\s*(.+)$/s)
  if (match) {
    return { key: (match[1] || '').trim(), value: (match[2] || '').trim() }
  }
  return { key: '', value: entry }
}

// Map of known field labels for icons
const fieldIcons: Record<string, string> = {
  'Имя': '👤', 'Name': '👤',
  'GitHub': '🐙', 'Github': '🐙',
  'Email': '📧', 'Почта': '📧',
  'Роль': '💼', 'Role': '💼',
  'Город': '🏙', 'City': '🏙', 'Расположение': '📍',
  'Язык': '🌐', 'Language': '🌐',
  'Часовой пояс': '🕐', 'Timezone': '🕐',
  'Предпочтения': '⚙️', 'Preferences': '⚙️',
  'Стиль': '🎨', 'Style': '🎨',
}

function getFieldIcon(key: string): string {
  const lower = key.toLowerCase()
  for (const [pattern, icon] of Object.entries(fieldIcons)) {
    if (lower.includes(pattern.toLowerCase())) return icon
  }
  return '📝'
}

interface MemoryEntry {
  entries: string[]
  content: string
  target: string
  usage: string
  entry_count: number
}

interface CompactionConfig {
  enabled: boolean
  trigger_percent: number
  keep_recent: number
  strategy: string
}

interface SessionAutoResetConfig {
  enabled: boolean
  mode: string
  reset_time: string
  interval_hours: number
}

interface SessionsConfig {
  auto_reset: SessionAutoResetConfig
  archive_on_reset: boolean
  max_history: number
}

export function MemorySection() {
  const [loading, setLoading] = useState(false)

  // User profile state (read-only display)
  const [userData, setUserData] = useState<MemoryEntry | null>(null)

  // Config state (compaction & sessions)
  const [compactionForm, setCompactionForm] = useState<CompactionConfig>({
    enabled: true, trigger_percent: 80, keep_recent: 10, strategy: 'truncate',
  })
  const [sessionsForm, setSessionsForm] = useState<SessionsConfig>({
    auto_reset: { enabled: true, mode: 'daily', reset_time: '00:00', interval_hours: 24 },
    archive_on_reset: true,
    max_history: 100,
  })

  // Load data on mount
  useEffect(() => {
    loadUserData()
    loadConfig()
  }, [])

  const loadUserData = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API}/api/memory/user`)
      if (res.ok) setUserData(await res.json())
    } catch (e) {
      console.error('[memory] load error:', e)
    } finally {
      setLoading(false)
    }
  }

  const loadConfig = async () => {
    try {
      const res = await fetch(`${API}/api/config/memory`)
      if (res.ok) {
        const data = await res.json()
        if (data.compaction) setCompactionForm(data.compaction)
        if (data.sessions) setSessionsForm(data.sessions)
      }
    } catch (e) {
      console.error('[memory] config load error:', e)
    }
  }

  // ── Config Save ──────────────────────────────────────────

  const saveConfig = async (payload: Record<string, unknown>) => {
    try {
      const res = await fetch(`${API}/api/config/memory`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      return res.ok
    } catch (e) {
      console.error('[memory] config save error:', e)
      return false
    }
  }

  // ── Render ──────────────────────────────────────────

  return (
    <div className="memory-section">
      {/* Block 1: User Profile (Global, Read-Only) */}
      <section className="settings-card">
        <h2 className="settings-card-title">👤 Профиль пользователя</h2>
        <p className="memory-card-desc">Общая информация о пользователе. Доступна всем агентам. Заполняется автоматически при общении.</p>

        <div className="memory-header">
          <div className="memory-usage">
            {userData?.usage || '0/0'}
          </div>
          <span className="memory-count">
            {userData?.entry_count || 0} записей
          </span>
        </div>

        {/* Entry list (read-only, deduplicated by key) */}
        <div className="memory-entries">
          {loading ? (
            <div className="memory-loading">Загрузка...</div>
          ) : userData?.entries && userData.entries.length > 0 ? (
            (() => {
              /* Keep only the last entry per unique key (most complete wins) */
              const seen = new Map<number, string>()
              userData.entries.forEach((entry, i) => {
                const p = parseEntry(entry)
                if (p.key) seen.set(i, p.key)
              })
              const uniqueByValue = new Map<string, number>()
              userData.entries.forEach((entry, i) => {
                const p = parseEntry(entry)
                const dedupeKey = p.key || entry.trim()
                if (p.key) {
                  uniqueByValue.set(dedupeKey, i)  /* last wins */
                }
              })
              const keepIndices = new Set<number>()
              userData.entries.forEach((entry, i) => {
                const p = parseEntry(entry)
                if (!p.key) { keepIndices.add(i); return }
                const dedupeKey = p.key
                if (uniqueByValue.get(dedupeKey) === i) keepIndices.add(i)
              })
              return userData.entries
                .filter((_, i) => keepIndices.has(i))
                .map((entry, i) => (
              <div key={i} className="memory-entry">
                {(() => {
                  const parsed = parseEntry(entry)
                  return parsed.key ? (
                    <div className="memory-entry-text memory-entry-structured">
                      <span className="memory-entry-key">
                        <span className="memory-entry-icon">{getFieldIcon(parsed.key)}</span>
                        {parsed.key}
                      </span>
                      <span className="memory-entry-value">{parsed.value}</span>
                    </div>
                  ) : (
                    <div className="memory-entry-text">{entry}</div>
                  )
                })()}
              </div>
            ))
            })()
          ) : (
            <div className="memory-empty">Агенты ещё ничего не записали о пользователе</div>
          )}
        </div>
      </section>

      {/* Compaction + Sessions side by side */}
      <div className="memory-settings-row">
        {/* Block 2: Compaction */}
        <section className="settings-card memory-settings-half">
          <h2 className="settings-card-title">🗜 Компакция</h2>
          <p className="memory-card-desc">Автоматическое сжатие истории сообщений когда контекст заполняется. Не даёт диалогу «упасть» из-за переполнения.</p>

          <div className="memory-config-form">
            <div className="settings-field-row">
              <label className="settings-toggle">
                <input
                  type="checkbox"
                  checked={compactionForm.enabled}
                  onChange={e => {
                    const next = { ...compactionForm, enabled: e.target.checked }
                    setCompactionForm(next)
                    saveConfig({ compaction: next })
                  }}
                />
                <span>Включена</span>
              </label>
            </div>
            <div className="settings-field">
              <div className="settings-field-label">
                <label>Порог (%)</label>
                <span className="settings-field-hint">Триггер сжатия при достижении лимита токенов</span>
              </div>
              <input
                type="number"
                className="settings-input"
                min={10}
                max={100}
                value={compactionForm.trigger_percent}
                onChange={e => {
                  const next = { ...compactionForm, trigger_percent: Math.min(100, Math.max(10, Number(e.target.value))) }
                  setCompactionForm(next)
                }}
                onBlur={() => saveConfig({ compaction: compactionForm })}
              />
            </div>
            <div className="settings-field">
              <div className="settings-field-label">
                <label>Оставить последних</label>
                <span className="settings-field-hint">Последние N сообщений остаются без изменений — агент помнит недавний контекст</span>
              </div>
              <input
                type="number"
                className="settings-input"
                min={1}
                max={50}
                value={compactionForm.keep_recent}
                onChange={e => {
                  const next = { ...compactionForm, keep_recent: Math.min(50, Math.max(1, Number(e.target.value))) }
                  setCompactionForm(next)
                }}
                onBlur={() => saveConfig({ compaction: compactionForm })}
              />
            </div>
            <div className="settings-field">
              <div className="settings-field-label">
                <label>Стратегия</label>
                <span className="settings-field-hint">Truncate — обрезка, Summarize — саммари</span>
              </div>
              <select
                className="settings-input"
                value={compactionForm.strategy}
                onChange={e => {
                  const next = { ...compactionForm, strategy: e.target.value }
                  setCompactionForm(next)
                  saveConfig({ compaction: next })
                }}
              >
                <option value="truncate">Truncate</option>
                <option value="summarize">Summarize</option>
              </select>
            </div>
          </div>
        </section>

        {/* Block 3: Sessions */}
        <section className="settings-card memory-settings-half">
          <h2 className="settings-card-title">💬 Сессии</h2>
          <p className="memory-card-desc">Периодическая очистка контекста сессии. Старые диалоги архивируются, начинается чистый разговор.</p>

          <div className="memory-config-form">
            <div className="settings-field-row">
              <label className="settings-toggle">
                <input
                  type="checkbox"
                  checked={sessionsForm.auto_reset.enabled}
                  onChange={e => {
                    const next = { ...sessionsForm, auto_reset: { ...sessionsForm.auto_reset, enabled: e.target.checked } }
                    setSessionsForm(next)
                    saveConfig({ sessions: next })
                  }}
                />
                <span>Авто-сброс</span>
              </label>
            </div>
            <div className="settings-field">
              <div className="settings-field-label">
                <label>Режим</label>
                <span className="settings-field-hint">Daily — раз в сутки, Timer — по интервалу, Time — в указанное время</span>
              </div>
              <select
                className="settings-input"
                value={sessionsForm.auto_reset.mode}
                onChange={e => {
                  const next = { ...sessionsForm, auto_reset: { ...sessionsForm.auto_reset, mode: e.target.value } }
                  setSessionsForm(next)
                  saveConfig({ sessions: next })
                }}
              >
                <option value="daily">Daily</option>
                <option value="timer">Timer</option>
                <option value="time">Time</option>
              </select>
            </div>
            {sessionsForm.auto_reset.mode === 'time' && (
              <div className="settings-field">
                <div className="settings-field-label">
                  <label>Время (HH:MM)</label>
                  <span className="settings-field-hint">Конкретное время сброса сессии</span>
                </div>
                <input
                  type="text"
                  className="settings-input"
                  placeholder="00:00"
                  value={sessionsForm.auto_reset.reset_time}
                  onChange={e => {
                    const next = { ...sessionsForm, auto_reset: { ...sessionsForm.auto_reset, reset_time: e.target.value } }
                    setSessionsForm(next)
                  }}
                  onBlur={() => saveConfig({ sessions: sessionsForm })}
                />
              </div>
            )}
            {sessionsForm.auto_reset.mode === 'timer' && (
              <div className="settings-field">
                <div className="settings-field-label">
                  <label>Интервал (ч)</label>
                  <span className="settings-field-hint">Сброс каждые N часов</span>
                </div>
                <input
                  type="number"
                  className="settings-input"
                  min={1}
                  value={sessionsForm.auto_reset.interval_hours}
                  onChange={e => {
                    const next = { ...sessionsForm, auto_reset: { ...sessionsForm.auto_reset, interval_hours: Math.max(1, Number(e.target.value)) } }
                    setSessionsForm(next)
                  }}
                  onBlur={() => saveConfig({ sessions: sessionsForm })}
                />
              </div>
            )}
            <div className="settings-field-row">
              <label className="settings-toggle">
                <input
                  type="checkbox"
                  checked={sessionsForm.archive_on_reset}
                  onChange={e => {
                    const next = { ...sessionsForm, archive_on_reset: e.target.checked }
                    setSessionsForm(next)
                    saveConfig({ sessions: next })
                  }}
                />
                <span>Архивировать</span>
              </label>
              <span className="settings-field-hint-inline">Перед сбросом сохранять историю в архив, чтобы ничего не потерялось</span>
            </div>
            <div className="settings-field">
              <div className="settings-field-label">
                <label>Макс. сообщений</label>
                <span className="settings-field-hint">Лимит сообщений в активной сессии — при достижении контекст начнёт сжиматься</span>
              </div>
              <input
                type="number"
                className="settings-input"
                min={10}
                max={1000}
                value={sessionsForm.max_history}
                onChange={e => {
                  const next = { ...sessionsForm, max_history: Math.min(1000, Math.max(10, Number(e.target.value))) }
                  setSessionsForm(next)
                }}
                onBlur={() => saveConfig({ sessions: sessionsForm })}
              />
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
