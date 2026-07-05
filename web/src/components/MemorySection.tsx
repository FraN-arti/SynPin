import { useState, useEffect } from 'react'

// ─── Memory Section ──────────────────────────────────────────

import { API_BASE as API } from '../config'
import { LoadingSpinner } from './LoadingSpinner'
import { SettingsCard } from './SettingsCard'
import { DropdownMenu, type DropdownOption } from './DropdownMenu'

// Re-use the global portal-based DropdownMenu. See DropdownMenu.tsx — the
// portal escapes any clipping/stacking-context ancestor, so the menu can
// never be hidden by surrounding sections.
type SmallDropdownProps = {
  value: string
  options: DropdownOption[]
  onChange: (v: string) => void
}
const SmallDropdown = ({ value, options, onChange }: SmallDropdownProps) => (
  <DropdownMenu value={value} options={options} onChange={onChange} />
)

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
  summary_volume: number
  strategy: string
}

interface MemoryProviderConfig {
  provider: string
  api_key: string
  endpoint: string
  max_chars: number
  auto_refactor: boolean
}

interface MemorySettingsConfig {
  enabled: boolean
  max_chars: number          // MEMORY.md (agent notes) limit
  max_chars_user: number     // USER.md (shared profile) limit
  auto_refactor: boolean
}

export function MemorySection() {
  const [loading, setLoading] = useState(false)

  // User profile state (read-only display)
  const [userData, setUserData] = useState<MemoryEntry | null>(null)

  // Config state (compaction & memory)
  const [compactionForm, setCompactionForm] = useState<CompactionConfig>({
    enabled: true, trigger_percent: 80, summary_volume: 0.2, strategy: 'summarize',
  })
  const [providerForm, setProviderForm] = useState<MemoryProviderConfig>({
    provider: 'built-in', api_key: '', endpoint: '', max_chars: 10000, auto_refactor: false,
  })
  const [memorySettings, setMemorySettings] = useState<MemorySettingsConfig>({
    enabled: true, max_chars: 10000, max_chars_user: 1375, auto_refactor: true,
  })
  const [otdelCompaction, setOtdelCompaction] = useState({
    enabled: true, compaction_limit: 100,
  })
  const [contextWindowDefault, setContextWindowDefault] = useState(128000)
  const [configLoaded, setConfigLoaded] = useState(false)
  const [sessionConfigLoaded, setSessionConfigLoaded] = useState(false)
  const [sessionSettings, setSessionSettings] = useState({
    auto_reset_enabled: true,
    auto_reset_mode: 'daily' as 'daily' | 'weekly' | 'never',
    auto_reset_time: '00:00',
    archive_on_reset: true,
    archive_retention_days: 30,
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
      // Load memory-specific config (compaction, memory provider, otdel compaction)
      const memRes = await fetch(`${API}/api/config/memory`)
      if (memRes.ok) {
        const data = await memRes.json()
        if (data.compaction) setCompactionForm(data.compaction)
        if (data.memory_provider) setProviderForm(data.memory_provider)
        if (data.memory) setMemorySettings(data.memory)
        if (data.otdel_compaction) setOtdelCompaction(data.otdel_compaction)
        if (data.context_window?.default) setContextWindowDefault(data.context_window.default)
        setConfigLoaded(true)
      }
      // Load session settings from settings.yaml (unified source)
      const settingsRes = await fetch(`${API}/api/config/settings`)
      if (settingsRes.ok) {
        const data = await settingsRes.json()
        const s = data.sessions || {}
        const ar = s.auto_reset || {}
        setSessionSettings({
          auto_reset_enabled: ar.enabled ?? true,
          auto_reset_mode: ar.mode ?? 'daily',
          auto_reset_time: ar.reset_time ?? '00:00',
          archive_on_reset: s.archive_on_reset ?? true,
          archive_retention_days: s.archive_retention_days ?? 30,
        })
        setSessionConfigLoaded(true)
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

  const saveSessionSettings = async (key: string, value: unknown) => {
    setSessionSettings(prev => {
      const next = { ...prev, [key]: value }
      // Build nested format for backend
      const payload: Record<string, unknown> = {}
      if (['auto_reset_enabled', 'auto_reset_mode', 'auto_reset_time'].includes(key)) {
        payload.auto_reset = {
          enabled: next.auto_reset_enabled,
          mode: next.auto_reset_mode,
          reset_time: next.auto_reset_time,
        }
      } else {
        payload[key] = value
      }
      // Fire save
      fetch(`${API}/api/config/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessions: payload }),
      }).catch(e => console.error('[memory] session settings save error:', e))
      return next
    })
  }

  // ── Render ──────────────────────────────────────────

  return (
    <div className="memory-section">
      {/* Block 1: User Profile (Global, Read-Only) */}
      <SettingsCard title="Профиль пользователя" loading={loading}>
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
            <LoadingSpinner text="Загрузка..." />
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
      </SettingsCard>

      {/* Compaction + Sessions side by side */}
      <div className="memory-settings-row">
        {/* Block 2: Compaction */}
        <SettingsCard title="Компакция" className="memory-settings-half" loading={!configLoaded}>
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
            <div className="settings-field" style={{ gridTemplateColumns: '1fr' }}>
              <label style={{ display: 'block', marginBottom: '10px' }}>Объем суммаризации: <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{compactionForm.summary_volume}</span></label>
              <div className="radius-slider-row">
                <span className="radius-label">5%</span>
                <input
                  type="range"
                  className="radius-slider"
                  min={0.05}
                  max={0.5}
                  step={0.05}
                  value={compactionForm.summary_volume}
                  onChange={e => {
                    const next = { ...compactionForm, summary_volume: parseFloat(e.target.value) }
                    setCompactionForm(next)
                  }}
                  onMouseUp={() => saveConfig({ compaction: compactionForm })}
                />
                <span className="radius-label">50%</span>
              </div>
            </div>
            <div className="settings-field">
              <div className="settings-field-label">
                <label>Стратегия</label>
                <span className="settings-field-hint">Summarize — саммари через LLM, Truncate — обрезка</span>
              </div>
              <SmallDropdown
                value={compactionForm.strategy}
                options={[
                  { value: 'summarize', label: 'Summarize — саммари' },
                  { value: 'truncate', label: 'Truncate — обрезка' },
                ]}
                onChange={v => {
                  const next = { ...compactionForm, strategy: v }
                  setCompactionForm(next)
                  saveConfig({ compaction: next })
                }}
              />
            </div>
          </div>
        </SettingsCard>

        {/* Block 3: Memory Provider */}
        <SettingsCard title="Memory Provider" className="memory-settings-half" loading={!configLoaded}>
          <p className="memory-card-desc">Где агенты хранят долгосрочную память. Built-in использует MEMORY.md / USER.md файлы.</p>

          <div className="memory-config-form">
            <div className="settings-field">
              <div className="settings-field-label">
                <label>Провайдер</label>
                <span className="settings-field-hint">Выберите провайдер памяти для агентов</span>
              </div>
              <SmallDropdown
                value={providerForm.provider}
                options={[
                  { value: 'built-in', label: 'Built-in (MEMORY.md / USER.md)' },
                  { value: 'hindsight', label: 'Hindsight', disabled: true, badge: 'скоро' },
                  { value: 'holographic', label: 'Holographic', disabled: true, badge: 'скоро' },
                  { value: 'honcho', label: 'Honcho', disabled: true, badge: 'скоро' },
                  { value: 'mem0', label: 'Mem0', disabled: true, badge: 'скоро' },
                  { value: 'openviking', label: 'OpenViking', disabled: true, badge: 'скоро' },
                  { value: 'retaindb', label: 'RetainDB', disabled: true, badge: 'скоро' },
                  { value: 'supermemory', label: 'SuperMemory', disabled: true, badge: 'скоро' },
                  { value: 'byterover', label: 'ByteRover', disabled: true, badge: 'скоро' },
                ]}
                onChange={v => {
                  const next = { ...providerForm, provider: v }
                  setProviderForm(next)
                  saveConfig({ memory_provider: next })
                }}
              />
            </div>

            {providerForm.provider !== 'built-in' && (
              <>
                <div className="settings-field">
                  <div className="settings-field-label">
                    <label>API Key</label>
                    <span className="settings-field-hint">Ключ доступа к провайдеру</span>
                  </div>
                  <input
                    type="password"
                    className="settings-input"
                    placeholder="sk-..."
                    value={providerForm.api_key}
                    onChange={e => setProviderForm({ ...providerForm, api_key: e.target.value })}
                    onBlur={() => saveConfig({ memory_provider: providerForm })}
                  />
                </div>
                <div className="settings-field">
                  <div className="settings-field-label">
                    <label>Endpoint</label>
                    <span className="settings-field-hint">Кастомный URL (если self-hosted)</span>
                  </div>
                  <input
                    type="text"
                    className="settings-input"
                    placeholder="https://..."
                    value={providerForm.endpoint}
                    onChange={e => setProviderForm({ ...providerForm, endpoint: e.target.value })}
                    onBlur={() => saveConfig({ memory_provider: providerForm })}
                  />
                </div>
              </>
            )}
          </div>
        </SettingsCard>

        {/* Block 4: Memory Settings */}
        <SettingsCard title="Настройка памяти" className="memory-settings-half" loading={!configLoaded}>
          <p className="memory-card-desc">Параметры работы долгосрочной памяти агентов.</p>

          <div className="memory-config-form">
            <div className="settings-field-row">
              <label className="settings-toggle">
                <input
                  type="checkbox"
                  checked={memorySettings.enabled}
                  onChange={e => {
                    const next = { ...memorySettings, enabled: e.target.checked }
                    setMemorySettings(next)
                    saveConfig({ memory: next })
                  }}
                />
                <span>Память включена</span>
              </label>
            </div>

            <div className="settings-field">
              <div className="settings-field-label">
                <label>Макс. символов (профиль)</label>
                <span className="settings-field-hint">Лимит на USER.md — общий профиль пользователя. Рекомендуется держать коротким.</span>
              </div>
              <input
                type="number"
                className="settings-input"
                min={100}
                max={100000}
                value={memorySettings.max_chars_user}
                onChange={e => setMemorySettings({ ...memorySettings, max_chars_user: Math.min(100000, Math.max(100, Number(e.target.value))) })}
                onBlur={() => saveConfig({ memory: memorySettings })}
              />
            </div>

            <div className="settings-field">
              <div className="settings-field-label">
                <label>Макс. символов (память)</label>
                <span className="settings-field-hint">Лимит на MEMORY.md для каждого агента — заметки, планы, контекст.</span>
              </div>
              <input
                type="number"
                className="settings-input"
                min={1000}
                max={1000000}
                value={memorySettings.max_chars}
                onChange={e => setMemorySettings({ ...memorySettings, max_chars: Math.min(1000000, Math.max(1000, Number(e.target.value))) })}
                onBlur={() => saveConfig({ memory: memorySettings })}
              />
            </div>

            <div className="settings-field">
              <div className="settings-field-label">
                <label>Контекстное окно (токены)</label>
                <span className="settings-field-hint">Глобальный лимит контекста для новых агентов. Можно переопределить в карточке агента.</span>
              </div>
              <input
                type="number"
                className="settings-input"
                min={4000}
                max={1000000}
                value={contextWindowDefault}
                onChange={e => setContextWindowDefault(Math.min(1000000, Math.max(4000, Number(e.target.value))) )}
                onBlur={() => saveConfig({ context_window: { default: contextWindowDefault } })}
              />
            </div>

            <div className="settings-field-row">
              <label className="settings-toggle">
                <input
                  type="checkbox"
                  checked={memorySettings.auto_refactor}
                  onChange={e => {
                    const next = { ...memorySettings, auto_refactor: e.target.checked }
                    setMemorySettings(next)
                    saveConfig({ memory: next })
                  }}
                />
                <span>Авто-рефакторинг</span>
              </label>
              <span className="settings-field-hint-inline">При превышении лимита символов — автоматически суммаризовать память, сохраняя важные факты</span>
            </div>
          </div>
        </SettingsCard>
      </div>

      <div className="memory-settings-row">
        {/* Block 4: Otdel Compaction */}
        <SettingsCard title="Отделы" className="memory-settings-half" loading={!configLoaded}>
          <p className="memory-card-desc">Настройки компакции чатов отделов. Глобальные правила для всех отделов.</p>

          <div className="memory-config-form">
            <div className="settings-field-row">
              <label className="settings-toggle">
                <input
                  type="checkbox"
                  checked={otdelCompaction.enabled}
                  onChange={e => {
                    const next = { ...otdelCompaction, enabled: e.target.checked }
                    setOtdelCompaction(next)
                    saveConfig({ otdel_compaction: next })
                  }}
                />
                <span>Компакция чатов</span>
              </label>
              <span className="settings-field-hint-inline">Автоматически сжимать историю сообщений в отделах</span>
            </div>

            <div className="settings-field-row">
              <label>Лимит сообщений</label>
              <input
                type="number"
                className="settings-input"
                value={otdelCompaction.compaction_limit}
                min={20}
                max={500}
                onChange={e => {
                  const next = { ...otdelCompaction, compaction_limit: Math.max(20, parseInt(e.target.value) || 20) }
                  setOtdelCompaction(next)
                }}
                onBlur={() => saveConfig({ otdel_compaction: otdelCompaction })}
              />
              <span className="settings-field-hint-inline">При превышении — старые сообщения заменяются summary</span>
            </div>
          </div>
        </SettingsCard>

        {/* Block 5: Agent Sessions */}
        <SettingsCard title="Сессии агентов" className="memory-settings-half" loading={!sessionConfigLoaded}>
          <p className="memory-card-desc">Глобальные настройки сброса и архивации сессий.</p>

          <div className="memory-config-form">
            <div className="settings-field-row">
              <label>Авто-сброс</label>
              <SmallDropdown
                value={sessionSettings.auto_reset_mode}
                onChange={v => saveSessionSettings('auto_reset_mode', v)}
                options={[
                  { value: 'daily', label: 'Ежедневно' },
                  { value: 'weekly', label: 'Еженедельно' },
                  { value: 'never', label: 'Отключено' },
                ]}
              />
            </div>

            {sessionSettings.auto_reset_mode !== 'never' && (
              <div className="settings-field-row">
                <label>Время сброса</label>
                <input
                  type="time"
                  className="settings-input"
                  value={sessionSettings.auto_reset_time}
                  onChange={e => saveSessionSettings('auto_reset_time', e.target.value)}
                />
              </div>
            )}

            <div className="settings-field-row">
              <label className="settings-toggle">
                <input
                  type="checkbox"
                  checked={sessionSettings.archive_on_reset}
                  onChange={e => saveSessionSettings('archive_on_reset', e.target.checked)}
                />
                <span>Архивировать при сбросе</span>
              </label>
            </div>

            {sessionSettings.archive_on_reset && (
              <div className="settings-field-row">
                <label>Хранить архив (дней)</label>
                <input
                  type="number"
                  className="settings-input"
                  value={sessionSettings.archive_retention_days}
                  min={7}
                  max={365}
                  onChange={e => saveSessionSettings('archive_retention_days', parseInt(e.target.value) || 30)}
                />
                <span className="settings-field-hint-inline">Старые архивы удаляются автоматически</span>
              </div>
            )}
          </div>
        </SettingsCard>
      </div>
    </div>
  )
}
