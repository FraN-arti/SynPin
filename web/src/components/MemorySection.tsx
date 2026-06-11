import { useState, useEffect, useRef } from 'react'

// ─── Memory Section ──────────────────────────────────────────

import { API_BASE as API } from '../config'

// Local dropdown (same CSS as SettingsPage CustomDropdown)
interface DropdownOption { value: string; label: string; disabled?: boolean; badge?: string }
function SmallDropdown({ value, options, onChange }: { value: string; options: DropdownOption[]; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const selected = options.find(o => o.value === value)
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  return (
    <div className="custom-dropdown" ref={ref} style={{ width: '100%' }}>
      <button className={`custom-dropdown-trigger ${open ? 'open' : ''}`} onClick={() => setOpen(!open)} type="button">
        <span className="dropdown-selected">{selected?.label || value}</span>
        <svg className="dropdown-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M6 9l6 6 6-6" /></svg>
      </button>
      <div className={`custom-dropdown-menu ${open ? 'open' : ''}`}>
        {options.map(option => (
          <button
            key={option.value}
            className={`custom-dropdown-item ${option.value === value ? 'selected' : ''} ${option.disabled ? 'disabled' : ''}`}
            onClick={() => { if (!option.disabled) { onChange(option.value); setOpen(false) } }}
            disabled={option.disabled}
          >
            <span>{option.label}</span>
            {option.badge && <span className="settings-card-badge" style={{ marginLeft: 6, fontSize: 9 }}>{option.badge}</span>}
            {option.value === value && <svg className="dropdown-check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M5 12l5 5L20 7" /></svg>}
          </button>
        ))}
      </div>
    </div>
  )
}

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

interface MemoryProviderConfig {
  provider: string
  api_key: string
  endpoint: string
  max_chars: number
  auto_refactor: boolean
}

interface MemorySettingsConfig {
  enabled: boolean
  max_chars: number
  auto_refactor: boolean
}

export function MemorySection() {
  const [loading, setLoading] = useState(false)

  // User profile state (read-only display)
  const [userData, setUserData] = useState<MemoryEntry | null>(null)

  // Config state (compaction & memory)
  const [compactionForm, setCompactionForm] = useState<CompactionConfig>({
    enabled: true, trigger_percent: 80, keep_recent: 10, strategy: 'truncate',
  })
  const [providerForm, setProviderForm] = useState<MemoryProviderConfig>({
    provider: 'built-in', api_key: '', endpoint: '', max_chars: 10000, auto_refactor: false,
  })
  const [memorySettings, setMemorySettings] = useState<MemorySettingsConfig>({
    enabled: true, max_chars: 10000, auto_refactor: false,
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
        if (data.memory_provider) setProviderForm(data.memory_provider)
        if (data.memory) setMemorySettings(data.memory)
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
              <SmallDropdown
                value={compactionForm.strategy}
                options={[
                  { value: 'truncate', label: 'Truncate — обрезка' },
                  { value: 'summarize', label: 'Summarize — через LLM', disabled: true, badge: 'скоро' },
                ]}
                onChange={v => {
                  const next = { ...compactionForm, strategy: v }
                  setCompactionForm(next)
                  saveConfig({ compaction: next })
                }}
              />
            </div>
          </div>
        </section>

        {/* Block 3: Memory Provider */}
        <section className="settings-card memory-settings-half">
          <h2 className="settings-card-title">🧠 Memory Provider</h2>
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
        </section>

        {/* Block 4: Memory Settings */}
        <section className="settings-card memory-settings-half">
          <h2 className="settings-card-title">⚙️ Настройка памяти</h2>
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
                <label>Макс. символов (всего)</label>
                <span className="settings-field-hint">Общий лимит памяти на агента — при достижении начнёт забывать старое</span>
              </div>
              <input
                type="number"
                className="settings-input"
                min={10000}
                max={1000000}
                value={memorySettings.max_chars}
                onChange={e => setMemorySettings({ ...memorySettings, max_chars: Math.min(1000000, Math.max(10000, Number(e.target.value))) })}
                onBlur={() => saveConfig({ memory: memorySettings })}
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
              <span className="settings-field-hint-inline">Автоматически объединять дублирующие записи (скоро)</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
