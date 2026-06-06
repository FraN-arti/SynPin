import { useState, useEffect, useRef, useCallback, forwardRef, useImperativeHandle } from 'react'
import { PROVIDER_CATALOG, providerKey, providerIconUrl, type ProviderInfo } from '../lib/providers'
import { MemorySection } from './MemorySection'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:2088'

interface SettingsPageProps {
  onBack: () => void
  onAgentsChange?: () => void
}

type Tab = 'general' | 'agents' | 'providers' | 'memory' | 'channels' | 'skills'

const TABS: { id: Tab; label: string }[] = [
  { id: 'general', label: 'Основное' },
  { id: 'agents', label: 'Агенты' },
  { id: 'providers', label: 'Провайдеры' },
  { id: 'memory', label: 'Память' },
  { id: 'channels', label: 'Каналы' },
  { id: 'skills', label: 'Скиллы' },
]

const SECTION_INFO: Record<Tab, { title: string; description: string }> = {
  general: { title: 'Основное', description: 'Настройки системы: порты, интерфейс, лента активности' },
  agents: { title: 'AI Агенты', description: 'Роли, модели, личности и системные промты агентов' },
  providers: { title: 'Провайдеры', description: 'Подключённые провайдеры и доступные для подключения' },
  memory: { title: 'Память', description: 'Архитектура памяти: агентская, командная, системная' },
  channels: { title: 'Каналы связи', description: 'Feishu, WhatsApp, Telegram — мультимодальная связь с системой' },
  skills: { title: 'Скиллы', description: 'База скиллов системы — подходы, шаблоны, процедуры' },
}

export function SettingsPage({ onBack, onAgentsChange }: SettingsPageProps) {
  const [activeTab, setActiveTab] = useState<Tab>('general')
  const [visible, setVisible] = useState(false)
  const [activeModal, setActiveModal] = useState<string | null>(null)
  const [addingProvider, setAddingProvider] = useState<ProviderInfo | null>(null)
  const [editingProvider, setEditingProvider] = useState<ApiProvider | null>(null)
  const providersRef = useRef<{ refresh: () => void }>(null)

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true))
  }, [])

  const handleBack = () => {
    setVisible(false)
    setTimeout(onBack, 300)
  }

  const handleTabChange = (tab: Tab) => {
    setActiveTab(tab)
  }

  return (
    <>
      {/* Modal overlay */}
      {activeModal && (
        <div className="modal-overlay" onClick={() => setActiveModal(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            {activeModal === 'add-provider-openai' && <AddProviderModal type="openai" onClose={() => setActiveModal(null)} onSaved={() => { setActiveModal(null); providersRef.current?.refresh() }} />}
            {activeModal === 'add-provider-anthropic' && <AddProviderModal type="anthropic" onClose={() => setActiveModal(null)} onSaved={() => { setActiveModal(null); providersRef.current?.refresh() }} />}
            {activeModal === 'add-channel' && <AddChannelModal onClose={() => setActiveModal(null)} />}
          </div>
        </div>
      )}

      {/* Add from catalog modal — at root level, outside .settings-page */}
      {addingProvider && (
        <div className="modal-overlay" onClick={() => setAddingProvider(null)}>
          <div className="modal-content modal-lg" onClick={e => e.stopPropagation()}>
            <AddFromCatalogModal
              provider={addingProvider}
              onClose={() => setAddingProvider(null)}
              onSaved={() => { setAddingProvider(null); providersRef.current?.refresh() }}
            />
          </div>
        </div>
      )}

      {/* Edit provider modal — at root level, outside .settings-page */}
      {editingProvider && (() => {
        const catalogEntry = PROVIDER_CATALOG.find(p => providerKey(p) === editingProvider.name)
        if (catalogEntry) {
          return (
            <div className="modal-overlay" onClick={() => setEditingProvider(null)}>
              <div className="modal-content modal-lg" onClick={e => e.stopPropagation()}>
                <AddFromCatalogModal
                  provider={catalogEntry}
                  editProvider={editingProvider}
                  onClose={() => setEditingProvider(null)}
                  onSaved={() => { setEditingProvider(null); providersRef.current?.refresh() }}
                />
              </div>
            </div>
          )
        }
        // Custom provider — not in catalog
        return (
          <div className="modal-overlay" onClick={() => setEditingProvider(null)}>
            <div className="modal-content modal-lg" onClick={e => e.stopPropagation()}>
              <EditCustomProviderModal
                provider={editingProvider}
                onClose={() => setEditingProvider(null)}
                onSaved={() => { setEditingProvider(null); providersRef.current?.refresh() }}
              />
            </div>
          </div>
        )
      })()}

      <div className={`settings-page ${visible ? 'visible' : ''}`}>
        {/* Header */}
        <div className="settings-top-bar">
          <button className="settings-back-btn" onClick={handleBack}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
          </button>
          <div className="settings-section-header">
            <h1 className="settings-section-title">{SECTION_INFO[activeTab].title}</h1>
            <p className="settings-section-desc">{SECTION_INFO[activeTab].description}</p>
          </div>
        </div>

        {/* Horizontal tab navigation */}
        <nav className="settings-nav-tabs">
          {TABS.map(tab => (
            <button
              key={tab.id}
              className={`settings-nav-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => handleTabChange(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Tab content with fade animation */}
        <div className="settings-body" key={activeTab}>
          {activeTab === 'general' && <GeneralSection />}
          {activeTab === 'agents' && <AgentsSection onAgentsChange={onAgentsChange} />}
          {activeTab === 'providers' && <ProvidersSection ref={providersRef} onAddProvider={(type) => setActiveModal(`add-provider-${type}`)} onAddFromCatalog={(p) => setAddingProvider(p)} onEditProvider={(p) => setEditingProvider(p)} />}
          {activeTab === 'memory' && <MemorySection />}
          {activeTab === 'channels' && <ChannelsSection onAddChannel={() => setActiveModal('add-channel')} />}
          {activeTab === 'skills' && <SkillsSection />}
        </div>
      </div>
    </>
  )
}

// ─── Custom Dropdown ─────────────────────────────────────────

interface DropdownOption {
  value: string
  label: string
  disabled?: boolean
}

interface CustomDropdownProps {
  value: string
  options: DropdownOption[]
  onChange: (value: string) => void
  width?: string
}

function CustomDropdown({ value, options, onChange, width }: CustomDropdownProps) {
  const [open, setOpen] = useState(false)
  const [highlighted, setHighlighted] = useState(-1)
  const ref = useRef<HTMLDivElement>(null)
  const selected = options.find(o => o.value === value)

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const handleSelect = (option: DropdownOption) => {
    if (option.disabled) return
    onChange(option.value)
    setOpen(false)
    setHighlighted(-1)
  }

  return (
    <div className="custom-dropdown" ref={ref} style={{ width }}>
      <button
        className={`custom-dropdown-trigger ${open ? 'open' : ''}`}
        onClick={() => setOpen(!open)}
        type="button"
      >
        <span className="dropdown-selected">{selected?.label || value}</span>
        <svg className="dropdown-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      <div className={`custom-dropdown-menu ${open ? 'open' : ''}`}>
        {options.map((option, i) => (
          <button
            key={option.value}
            className={`custom-dropdown-item ${option.value === value ? 'selected' : ''} ${option.disabled ? 'disabled' : ''} ${i === highlighted ? 'highlighted' : ''}`}
            onClick={() => handleSelect(option)}
            onMouseEnter={() => setHighlighted(i)}
            disabled={option.disabled}
          >
            {option.label}
            {option.value === value && (
              <svg className="dropdown-check" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                <path d="M5 12l5 5L20 7" />
              </svg>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}

// ─── General Section ─────────────────────────────────────────

interface OverviewStats {
  agents: number
  agents_internal: number
  agents_external: number
  total_messages: number
  total_sessions: number
  config_files: number
  uptime: string
}

interface SettingsData {
  server: {
    host: string
    port: number
    dev_port: number
    cors_origins: string[]
    rate_limit: { enabled: boolean; requests_per_minute: number }
  }
  ui: {
    theme: string
    language: string
    sidebar: { default_open: boolean; show_icons: boolean }
    chat: {
      show_metadata: boolean
      metadata_delay_ms: number
      max_message_length: number
      auto_scroll: boolean
      streaming_border: boolean
    }
  }
  models: {
    vision: string
    image_gen: string
    web_search: string
    web_extract: string
    summarization: string
  }
  feed: {
    enabled: boolean
    max_items: number
    time_range: string
    filters: {
      new_ideas: boolean
      task_updates: boolean
      memory_updates: boolean
      board_updates: boolean
    }
    sort: string
    group_by: string
  }
}

function GeneralSection() {
  const [settings, setSettings] = useState<SettingsData | null>(null)
  const [overview, setOverview] = useState<OverviewStats | null>(null)
  const [availableModels, setAvailableModels] = useState<{ provider: string; model: string }[]>([])
  const [customThemes, setCustomThemes] = useState<{ id: string; name: string; source_url: string; dark?: Record<string, string>; light?: Record<string, string>; raw?: { light: Record<string, string>; dark: Record<string, string> } }[]>([])
  const [tweakcnUrl, setTweakcnUrl] = useState('')
  const [tweakcnLoading, setTweakcnLoading] = useState(false)
  const [tweakcnError, setTweakcnError] = useState('')
  const [tweakcnSuccess, setTweakcnSuccess] = useState('')
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Load settings
  useEffect(() => {
    fetch(`${API_BASE}/api/config/settings`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setSettings(data) })
      .catch(() => {})
  }, [])

  // Load available models from providers
  useEffect(() => {
    fetch(`${API_BASE}/api/providers`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.providers) {
          const models: { provider: string; model: string }[] = []
          for (const p of data.providers) {
            for (const m of (p.models || [])) {
              models.push({ provider: p.name, model: m })
            }
          }
          setAvailableModels(models)
        }
      })
      .catch(() => {})
  }, [])

  // Load stats
  useEffect(() => {
    fetch(`${API_BASE}/api/stats/overview`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setOverview(data) })
      .catch(() => {})
  }, [])

  // Load custom themes
  useEffect(() => {
    fetch(`${API_BASE}/api/themes/tweakcn/list`)
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data?.themes) setCustomThemes(data.themes) })
      .catch(() => {})
  }, [])

  // Apply theme when it changes
  useEffect(() => {
    if (!settings) return

    const root = document.documentElement
    const theme = settings.ui.theme

    // Clear ALL classes first
    root.classList.remove('light-theme', 'dark-theme', 'oled-theme')

    // Clear all inline custom properties
    const existingVars = root.style;
    for (let i = existingVars.length - 1; i >= 0; i--) {
      const prop = existingVars[i];
      if (prop && prop.startsWith('--')) {
        root.style.removeProperty(prop);
      }
    }

    // Apply theme
    if (theme === 'dark') {
      // Default dark - no classes needed, CSS :root handles it
    } else if (theme === 'dark-oled') {
      root.classList.add('oled-theme')
    } else if (theme === 'light') {
      root.classList.add('light-theme')
    } else if (theme === 'tweakcn') {
      root.classList.add('dark-theme')
      // Find the 'current' theme (or first available)
      const current = customThemes.find(t => t.id === 'current') || customThemes[0]
      if (current) {
        const vars = current.dark || current.light
        if (vars) {
          Object.entries(vars).forEach(([key, value]) => {
            root.style.setProperty(key, value as string)
          })
        }
      }
    }
  }, [settings?.ui.theme, customThemes])

  // Debounced save
  const saveSettings = useCallback((patch: Partial<SettingsData>) => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(async () => {
      try {
        await fetch(`${API_BASE}/api/config/settings`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(patch),
        })
      } catch {}
    }, 400)
  }, [])

  const updateServer = useCallback((key: string, value: any) => {
    setSettings(prev => prev ? { ...prev, server: { ...prev.server, [key]: value } } : prev)
    saveSettings({ server: { [key]: value } as any })
  }, [saveSettings])

  const updateUI = useCallback((path: string, value: string | boolean | number) => {
    setSettings(prev => {
      if (!prev) return prev
      const ui = { ...prev.ui }
      if (path.startsWith('chat.')) {
        const key = path.slice(5) as keyof typeof ui.chat
        ui.chat = { ...ui.chat, [key]: value }
      } else if (path.startsWith('sidebar.')) {
        const key = path.slice(8) as keyof typeof ui.sidebar
        ui.sidebar = { ...ui.sidebar, [key]: value }
      } else {
        ;(ui as any)[path] = value
      }
      return { ...prev, ui }
    })
    const parts = path.split('.')
    if (parts.length === 1) {
      saveSettings({ ui: { [path]: value } as any })
    } else {
      const key0 = parts[0]!
      const key1 = parts[1]!
      saveSettings({ ui: { [key0]: { [key1]: value } } as any })
    }
  }, [saveSettings])

  const updateModels = useCallback((key: string, value: string) => {
    setSettings(prev => prev ? { ...prev, models: { ...prev.models, [key]: value } } : prev)
    saveSettings({ models: { [key]: value } as any })
  }, [saveSettings])

  const updateFeed = useCallback((key: string, value: string | number | boolean) => {
    setSettings(prev => {
      if (!prev) return prev
      const feed = { ...prev.feed }
      if (key.startsWith('filters.')) {
        const fkey = key.slice(8) as keyof typeof feed.filters
        feed.filters = { ...feed.filters, [fkey]: value }
      } else {
        ;(feed as any)[key] = value
      }
      return { ...prev, feed }
    })
    if (key.startsWith('filters.')) {
      saveSettings({ feed: { filters: { [key.slice(8)]: value } } as any })
    } else {
      saveSettings({ feed: { [key]: value } as any })
    }
  }, [saveSettings])

  // Import TweakCN theme
  const handleTweakcnImport = useCallback(async () => {
    if (!tweakcnUrl.trim()) return

    setTweakcnLoading(true)
    setTweakcnError('')
    setTweakcnSuccess('')

    try {
      const res = await fetch(`${API_BASE}/api/themes/tweakcn/import`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: tweakcnUrl.trim() }),
      })

      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Failed to import theme')
      }

      const data = await res.json()

      // Save the theme with fixed ID 'current' (overwrites existing)
      const saveRes = await fetch(`${API_BASE}/api/themes/tweakcn/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: 'current',
          name: data.name,
          url: data.source_url,
          light: data.light,
          dark: data.dark,
          raw: data.raw,
        }),
      })

      if (!saveRes.ok) throw new Error('Failed to save theme')

      // Apply the theme immediately
      const root = document.documentElement
      const vars = data.dark  // TweakCN themes are always dark

      // Clear all custom properties first
      const existingVars = root.style;
      for (let i = existingVars.length - 1; i >= 0; i--) {
        const prop = existingVars[i];
        if (prop && prop.startsWith('--')) {
          root.style.removeProperty(prop);
        }
      }

      // Apply new theme variables
      Object.entries(vars).forEach(([key, value]) => {
        root.style.setProperty(key, value as string)
      })

      // Refresh custom themes list
      const listRes = await fetch(`${API_BASE}/api/themes/tweakcn/list`)
      if (listRes.ok) {
        const listData = await listRes.json()
        if (listData?.themes) setCustomThemes(listData.themes)
      }

      setTweakcnSuccess(`Тема "${data.name}" загружена и применена!`)
      setTweakcnUrl('')
      setTimeout(() => setTweakcnSuccess(''), 3000)
    } catch (err: any) {
      setTweakcnError(err.message || 'Ошибка при загрузке темы')
    } finally {
      setTweakcnLoading(false)
    }
  }, [tweakcnUrl, settings, updateUI])

  if (!settings) {
    return <div className="settings-loading">Загрузка...</div>
  }

  return (
    <div className="general-settings">
      {/* ─── 📊 Обзор системы ─── */}
      <section className="settings-card">
        <h2 className="settings-card-title">📊 Обзор системы</h2>
        <div className="stats-summary">
          <div className="stats-card">
            <span className="stats-card-value">{overview?.agents ?? '—'}</span>
            <span className="stats-card-label">Агентов</span>
            <span className="stats-card-detail">
              {overview?.agents_internal ?? 0} внутр. + {overview?.agents_external ?? 0} внешн.
            </span>
          </div>
          <div className="stats-card">
            <span className="stats-card-value">{overview?.total_messages ?? '—'}</span>
            <span className="stats-card-label">Сообщений</span>
            <span className="stats-card-detail">{overview?.total_sessions ?? 0} сессий</span>
          </div>
          <div className="stats-card">
            <span className="stats-card-value">{overview?.config_files ?? '—'}</span>
            <span className="stats-card-label">Конфигов</span>
            <span className="stats-card-detail">YAML файлов</span>
          </div>
          <div className="stats-card">
            <span className="stats-card-value">{overview?.uptime ?? '—'}</span>
            <span className="stats-card-label">Аптайм</span>
            <span className="stats-card-detail">с момента запуска</span>
          </div>
        </div>
      </section>

      <div className="settings-divider" />

      {/* ─── 🖥 Сервер ─── */}
      <section className="settings-card">
        <h2 className="settings-card-title">🖥 Сервер</h2>
        <div className="settings-row-2">
          <div className="settings-field">
            <label>Хост</label>
            <input type="text" className="settings-input"
              value={settings.server.host}
              onChange={e => updateServer('host', e.target.value)} />
          </div>
          <div className="settings-field">
            <label>Порт API</label>
            <input type="number" className="settings-input"
              value={settings.server.port}
              onChange={e => updateServer('port', parseInt(e.target.value) || 2088)} />
          </div>
        </div>
        <div className="settings-row-2">
          <div className="settings-field">
            <label>Порт Dev (Vite)</label>
            <input type="number" className="settings-input"
              value={settings.server.dev_port}
              onChange={e => updateServer('dev_port', parseInt(e.target.value) || 2099)} />
          </div>
          <div className="settings-field">
            <label>Rate Limit (req/min)</label>
            <input type="number" className="settings-input"
              value={settings.server.rate_limit?.requests_per_minute ?? 60}
              onChange={e => updateServer('rate_limit', {
                enabled: settings.server.rate_limit?.enabled ?? true,
                requests_per_minute: parseInt(e.target.value) || 60,
              })} />
          </div>
        </div>
        <Toggle
          label="Rate Limiting"
          checked={settings.server.rate_limit?.enabled ?? true}
          onChange={v => updateServer('rate_limit', {
            enabled: v,
            requests_per_minute: settings.server.rate_limit?.requests_per_minute ?? 60,
          })} />
      </section>

      <div className="settings-divider" />

      <div className="settings-row-2">
        {/* ─── 🎨 Интерфейс ─── */}
        <section className="settings-card">
          <h2 className="settings-card-title">Интерфейс</h2>
        <div className="settings-row-2">
          <div className="settings-field">
            <label>Тема</label>
            <CustomDropdown
              value={settings.ui.theme}
              onChange={v => updateUI('theme', v)}
              options={[
                { value: 'dark', label: 'Тёмная' },
                { value: 'dark-oled', label: 'Тёмная (OLED)' },
                { value: 'light', label: 'Светлая' },
                { value: 'tweakcn', label: 'TweakCN' },
              ]}
            />
          </div>
          <div className="settings-field">
            <label>Язык</label>
            <CustomDropdown
              value={settings.ui.language}
              onChange={v => updateUI('language', v)}
              options={[
                { value: 'ru', label: 'Русский' },
                { value: 'en', label: 'English' },
              ]}
            />
          </div>
        </div>

        {/* TweakCN Import Section */}
        {settings.ui.theme === 'tweakcn' && (
          <div className="tweakcn-section">
            <div className="settings-divider-thin" />
            <h3 className="settings-subsection-title">TweakCN Theme</h3>
            <div className="tweakcn-input-row">
              <input
                type="text"
                className="settings-input"
                placeholder="https://tweakcn.com/themes/..."
                value={tweakcnUrl}
                onChange={e => setTweakcnUrl(e.target.value)}
                disabled={tweakcnLoading}
              />
              <button
                className="settings-btn-primary"
                onClick={handleTweakcnImport}
                disabled={tweakcnLoading || !tweakcnUrl.trim()}>
                {tweakcnLoading ? 'Загрузка...' : 'Сохранить'}
              </button>
            </div>
            {tweakcnError && <div className="tweakcn-error">{tweakcnError}</div>}
            {tweakcnSuccess && <div className="tweakcn-success">{tweakcnSuccess}</div>}
            {customThemes.length > 0 && customThemes[0] && (
              <div className="tweakcn-saved-info">
                <span className="tweakcn-saved-label">Текущая тема: {customThemes[0].name}</span>
              </div>
            )}
          </div>
        )}

        <div className="settings-divider-thin" />
        <h3 className="settings-subsection-title">Чат</h3>
        <Toggle
          label="Показывать метаданные сообщений"
          checked={settings.ui.chat.show_metadata}
          onChange={v => updateUI('chat.show_metadata', v)} />
        <Toggle
          label="Анимированная обводка при стриминге"
          checked={settings.ui.chat.streaming_border}
          onChange={v => updateUI('chat.streaming_border', v)} />
        <Toggle
          label="Автоскролл к новым сообщениям"
          checked={settings.ui.chat.auto_scroll}
          onChange={v => updateUI('chat.auto_scroll', v)} />
        <div className="settings-field">
          <label>Макс. длина сообщения</label>
          <input type="number" className="settings-input"
            value={settings.ui.chat.max_message_length}
            onChange={e => updateUI('chat.max_message_length', parseInt(e.target.value) || 4000)} />
        </div>
        <div className="settings-divider-thin" />
        <h3 className="settings-subsection-title">Сайдбар</h3>
        <Toggle
          label="Открыт по умолчанию"
          checked={settings.ui.sidebar.default_open}
          onChange={v => updateUI('sidebar.default_open', v)} />
        <Toggle
          label="Показывать иконки"
          checked={settings.ui.sidebar.show_icons}
          onChange={v => updateUI('sidebar.show_icons', v)} />
        </section>

        {/* ─── 🤖 Настройка моделей ─── */}
        <section className="settings-card">
          <h2 className="settings-card-title">Настройка моделей</h2>
          <p className="settings-card-desc">Модели для специализированных задач</p>
          <div className="settings-field">
            <label>Визион (анализ изображений)</label>
            <CustomDropdown
              value={settings.models?.vision || ''}
              onChange={v => updateModels('vision', v)}
              options={[
                { value: '', label: 'Не настроено' },
                ...availableModels.map(m => ({ value: `${m.provider}/${m.model}`, label: `${m.model} (${m.provider})` })),
              ]}
            />
          </div>
          <div className="settings-field">
            <label>Генерация изображений</label>
            <CustomDropdown
              value={settings.models?.image_gen || ''}
              onChange={v => updateModels('image_gen', v)}
              options={[
                { value: '', label: 'Не настроено' },
                ...availableModels.map(m => ({ value: `${m.provider}/${m.model}`, label: `${m.model} (${m.provider})` })),
              ]}
            />
          </div>
          <div className="settings-field">
            <label>Веб-поиск</label>
            <CustomDropdown
              value={settings.models?.web_search || ''}
              onChange={v => updateModels('web_search', v)}
              options={[
                { value: '', label: 'Не настроено' },
                ...availableModels.map(m => ({ value: `${m.provider}/${m.model}`, label: `${m.model} (${m.provider})` })),
              ]}
            />
          </div>
          <div className="settings-field">
            <label>Веб-экстракт</label>
            <CustomDropdown
              value={settings.models?.web_extract || ''}
              onChange={v => updateModels('web_extract', v)}
              options={[
                { value: '', label: 'Не настроено' },
                ...availableModels.map(m => ({ value: `${m.provider}/${m.model}`, label: `${m.model} (${m.provider})` })),
              ]}
            />
          </div>
          <div className="settings-field">
            <label>Суммаризация</label>
            <CustomDropdown
              value={settings.models?.summarization || ''}
              onChange={v => updateModels('summarization', v)}
              options={[
                { value: '', label: 'Не настроено' },
                ...availableModels.map(m => ({ value: `${m.provider}/${m.model}`, label: `${m.model} (${m.provider})` })),
              ]}
            />
          </div>
        </section>
      </div>

      <div className="settings-divider" />

      {/* ─── 📡 Лента активности ─── */}
      <section className="settings-card">
        <h2 className="settings-card-title">📡 Лента активности</h2>
        <div className="settings-row-2">
          <div className="settings-field">
            <label>Макс. записей</label>
            <input type="number" className="settings-input"
              value={settings.feed.max_items}
              onChange={e => updateFeed('max_items', parseInt(e.target.value) || 50)} />
          </div>
          <div className="settings-field">
            <label>Период</label>
            <CustomDropdown
              value={settings.feed.time_range}
              onChange={v => updateFeed('time_range', v)}
              options={[
                { value: '1h', label: '1 час' },
                { value: '6h', label: '6 часов' },
                { value: '24h', label: '24 часа' },
                { value: '7d', label: '7 дней' },
                { value: '30d', label: '30 дней' },
              ]}
            />
          </div>
        </div>
        <Toggle
          label="Лента включена"
          checked={settings.feed.enabled}
          onChange={v => updateFeed('enabled', v)} />
        <div className="settings-divider-thin" />
        <h3 className="settings-subsection-title">Фильтры</h3>
        <Toggle
          label="Новые идеи"
          checked={settings.feed.filters.new_ideas}
          onChange={v => updateFeed('filters.new_ideas', v)} />
        <Toggle
          label="Обновления задач"
          checked={settings.feed.filters.task_updates}
          onChange={v => updateFeed('filters.task_updates', v)} />
        <Toggle
          label="Обновления памяти"
          checked={settings.feed.filters.memory_updates}
          onChange={v => updateFeed('filters.memory_updates', v)} />
        <Toggle
          label="Обновления канбана"
          checked={settings.feed.filters.board_updates}
          onChange={v => updateFeed('filters.board_updates', v)} />
        <div className="settings-divider-thin" />
        <div className="settings-row-2">
          <div className="settings-field">
            <label>Сортировка</label>
            <CustomDropdown
              value={settings.feed.sort}
              onChange={v => updateFeed('sort', v)}
              options={[
                { value: 'newest', label: 'Сначала новые' },
                { value: 'oldest', label: 'Сначала старые' },
              ]}
            />
          </div>
          <div className="settings-field">
            <label>Группировка</label>
            <CustomDropdown
              value={settings.feed.group_by}
              onChange={v => updateFeed('group_by', v)}
              options={[
                { value: 'none', label: 'Без группировки' },
                { value: 'department', label: 'По департаменту' },
                { value: 'type', label: 'По типу' },
              ]}
            />
          </div>
        </div>
      </section>

      <div className="settings-divider" />
    </div>
  )
}
// ─── Toggle Component ────────────────────────────────────────

function Toggle({ label, defaultChecked, checked, onChange }: { label: string; defaultChecked?: boolean; checked?: boolean; onChange?: (v: boolean) => void }) {
  const isControlled = checked !== undefined
  return (
    <div className="settings-field-row">
      <label className="settings-toggle">
        <input type="checkbox" {...(isControlled ? { checked } : { defaultChecked })}
          onChange={e => onChange?.(e.target.checked)} />
        <span>{label}</span>
      </label>
    </div>
  )
}

// ─── Agents Section ──────────────────────────────────────────

interface AgentData {
  slug: string
  agentid: string
  name: string
  role: string
  department: string
  model: string
  provider: string | null
  skills: string[]
  tools: string[]
  enabled: boolean
  description: string
  tone: string
  style: string
  traits: string[]
  system_prompt: string
  max_iterations: number
  temperature: number
  max_tokens: number
  context_window: number
  memory: Record<string, unknown>
  is_external?: boolean
}

interface ExternalAgentData {
  slug: string
  agentid: string
  name: string
  type: string
  description: string
  enabled: boolean
  role: string
  role_name: string
  department: string
  department_name: string
  available: boolean
  models: string[]
  chat_url: string
  icon_letter: string
  color: string
  is_external: true
}

function AgentsSection({ onAgentsChange }: { onAgentsChange?: () => void }) {
  const [agents, setAgents] = useState<AgentData[]>([])
  const [providers, setProviders] = useState<{name: string; models: string[]}[]>([])
  const [hoveredAgent, setHoveredAgent] = useState<string | null>(null)
  const [overlayShift, setOverlayShift] = useState<Record<string, number>>({})
  const [roles, setRoles] = useState<{rolesid: string; name: string; description: string; color: string}[]>([])
  const [departments, setDepartments] = useState<{departmentsid: string; name: string; description: string; color: string}[]>([])
  const [newRole, setNewRole] = useState({ name: '', description: '', color: '#f59e0b' })
  const [newDept, setNewDept] = useState({ name: '', description: '', color: '#3b82f6' })
  const [externalAgents, setExternalAgents] = useState<ExternalAgentData[]>([])
  const [externalDetected, setExternalDetected] = useState(false)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createForm, setCreateForm] = useState({
    name: '', role: '', department: '', model: '',
    description: '', system_prompt: '', temperature: 0.7,
  })
  const [creating, setCreating] = useState(false)
  const [formTouched, setFormTouched] = useState(false)
  const [toolsRegistry, setToolsRegistry] = useState<Record<string, {display: string; description: string; category: string; implemented: boolean; builtin?: boolean}>>({})
  const [toolsCategories, setToolsCategories] = useState<Record<string, {display: string}>>({})

  // Auto-calculate overlay shift when agent card is hovered
  useEffect(() => {
    if (!hoveredAgent) return
    const timer = setTimeout(() => {
      const wrapper = document.querySelector(`.agent-card-wrapper:hover`) ||
                      document.querySelector(`.agent-expanded-overlay`)
      if (!wrapper) return
      const rect = wrapper.getBoundingClientRect()
      const vh = window.innerHeight
      const overlayHeight = rect.height * 3.2 // 320% from CSS
      const overlayTop = rect.top - rect.height * 0.6 // top: -60%
      const overflow = (overlayTop + overlayHeight) - vh
      if (overflow > 0) {
        setOverlayShift(prev => ({ ...prev, [hoveredAgent]: overflow + 16 }))
      }
    }, 10)
    return () => clearTimeout(timer)
  }, [hoveredAgent])

  // Build lookup maps from roles/departments
  const roleMap: Record<string, {name: string; color: string}> = {}
  for (const r of roles) roleMap[r.rolesid] = { name: r.name, color: r.color }
  const deptMap: Record<string, {name: string; color: string}> = {}
  for (const d of departments) deptMap[d.departmentsid] = { name: d.name, color: d.color }

  const handleAddRole = async () => {
    if (!newRole.name.trim()) return
    const rolesid = newRole.name.trim().toLowerCase().replace(/\s+/g, '-')
    const updated = [...roles, { rolesid, ...newRole }]
    const res = await fetch(`${API_BASE}/api/roles`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ roles: updated }),
    })
    if (res.ok) {
      const data = await res.json()
      setRoles(data.roles)
    }
    setNewRole({ name: '', description: '', color: '#f59e0b' })
  }

  const handleAddDept = async () => {
    if (!newDept.name.trim()) return
    const departmentsid = newDept.name.trim().toLowerCase().replace(/\s+/g, '-')
    const updated = [...departments, { departmentsid, ...newDept }]
    const res = await fetch(`${API_BASE}/api/departments`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ departments: updated }),
    })
    if (res.ok) {
      const data = await res.json()
      setDepartments(data.departments)
    }
    setNewDept({ name: '', description: '', color: '#3b82f6' })
  }

  const handleRemoveRole = async (rolesid: string) => {
    const updated = roles.filter(r => r.rolesid !== rolesid)
    const res = await fetch(`${API_BASE}/api/roles`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ roles: updated }),
    })
    if (res.ok) {
      const data = await res.json()
      setRoles(data.roles)
    }
  }

  const handleRoleColorChange = async (rolesid: string, newColor: string) => {
    const updated = roles.map(r => r.rolesid === rolesid ? { ...r, color: newColor } : r)
    try {
      const res = await fetch(`${API_BASE}/api/roles`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ roles: updated }),
      })
      if (res.ok) {
        const data = await res.json()
        setRoles(data.roles)
      }
    } catch (e) { console.error('[roles] color change error:', e) }
  }

  const handleDeptColorChange = async (departmentsid: string, newColor: string) => {
    const updated = departments.map(d => d.departmentsid === departmentsid ? { ...d, color: newColor } : d)
    try {
      const res = await fetch(`${API_BASE}/api/departments`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ departments: updated }),
      })
      if (res.ok) {
        const data = await res.json()
        setDepartments(data.departments)
      }
    } catch (e) { console.error('[departments] color change error:', e) }
  }

  const handleRemoveDept = async (departmentsid: string) => {
    const updated = departments.filter(d => d.departmentsid !== departmentsid)
    const res = await fetch(`${API_BASE}/api/departments`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ departments: updated }),
    })
    if (res.ok) {
      const data = await res.json()
      setDepartments(data.departments)
    }
  }

  const handleAgentRoleChange = async (agent: AgentData, newRole: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/agents/${agent.slug}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: newRole }),
      })
      if (res.ok) fetchAgents()
    } catch (e) { console.error('[agents] role change error:', e) }
  }

  const handleAgentDeptChange = async (agent: AgentData, newDept: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/agents/${agent.slug}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ department: newDept }),
      })
      if (res.ok) fetchAgents()
    } catch (e) { console.error('[agents] dept change error:', e) }
  }

  const fetchAgents = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/agents`)
      if (res.ok) {
        const data = await res.json()
        setAgents(data.agents || [])
      }
    } catch (e) {
      console.error('[agents] fetch error:', e)
    }
  }, [])

  const fetchProviders = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/providers`)
      if (res.ok) {
        const data = await res.json()
        setProviders(data.providers || [])
      }
    } catch (e) {
      console.error('[agents] providers fetch error:', e)
    }
  }, [])

  const fetchRoles = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/roles`)
      if (res.ok) {
        const data = await res.json()
        setRoles(data.roles || [])
      }
    } catch (e) {
      console.error('[roles] fetch error:', e)
    }
  }, [])

  const fetchDepartments = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/departments`)
      if (res.ok) {
        const data = await res.json()
        setDepartments(data.departments || [])
      }
    } catch (e) {
      console.error('[departments] fetch error:', e)
    }
  }, [])

  const detectExternalAgents = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/external-agents/detect`)
      if (res.ok) {
        const data = await res.json()
        setExternalAgents(data.agents || [])
        setExternalDetected(true)
      }
    } catch (e) {
      console.error('[external-agents] detect error:', e)
      setExternalDetected(true)
    }
  }, [])

  const fetchTools = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/tools`)
      if (res.ok) {
        const data = await res.json()
        setToolsRegistry(data.tools || {})
        setToolsCategories(data.categories || {})
      }
    } catch (e) {
      console.error('[tools] fetch error:', e)
    }
  }, [])

  const handleExternalToggle = async (agent: ExternalAgentData) => {
    try {
      const res = await fetch(`${API_BASE}/api/external-agents/${agent.slug}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !agent.enabled }),
      })
      if (res.ok) {
        detectExternalAgents()
      }
    } catch (e) {
      console.error('[external-agents] toggle error:', e)
    }
  }

  const handleExternalRoleChange = async (agent: ExternalAgentData, newRole: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/external-agents/${agent.slug}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: newRole }),
      })
      if (res.ok) {
        detectExternalAgents()
      }
    } catch (e) {
      console.error('[external-agents] role change error:', e)
    }
  }

  const handleToolToggle = async (agentid: string, toolName: string, currentTools: string[]) => {
    const newTools = currentTools.includes(toolName)
      ? currentTools.filter(t => t !== toolName)
      : [...currentTools, toolName]
    try {
      const res = await fetch(`${API_BASE}/api/tools/${agentid}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tools: newTools }),
      })
      if (res.ok) {
        fetchAgents()
        onAgentsChange?.()
      }
    } catch (e) {
      console.error('[tools] toggle error:', e)
    }
  }

  const handleExternalDeptChange = async (agent: ExternalAgentData, newDept: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/external-agents/${agent.slug}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ department: newDept }),
      })
      if (res.ok) {
        detectExternalAgents()
      }
    } catch (e) {
      console.error('[external-agents] dept change error:', e)
    }
  }

  useEffect(() => {
    fetchAgents()
    fetchProviders()
    fetchRoles()
    fetchDepartments()
    detectExternalAgents()
    fetchTools()
  }, [fetchAgents, fetchProviders, fetchRoles, fetchDepartments, detectExternalAgents, fetchTools])

  const handleToggle = async (agent: AgentData) => {
    try {
      const res = await fetch(`${API_BASE}/api/agents/${agent.slug}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !agent.enabled }),
      })
      if (res.ok) {
        fetchAgents()
      }
    } catch (e) {
      console.error('[agents] toggle error:', e)
    }
  }

  const handleModelChange = async (agent: AgentData, newModel: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/agents/${agent.slug}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: newModel }),
      })
      if (res.ok) {
        fetchAgents()
      }
    } catch (e) {
      console.error('[agents] model change error:', e)
    }
  }

  const handleAgentFieldChange = async (agent: AgentData, field: string, value: unknown) => {
    try {
      const res = await fetch(`${API_BASE}/api/agents/${agent.slug}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [field]: value }),
      })
      if (res.ok) {
        fetchAgents()
      }
    } catch (e) {
      console.error('[agents] field change error:', e)
    }
  }

  const handleCreateAgent = async () => {
    setFormTouched(true)
    if (!createForm.name.trim()) return
    setCreating(true)
    try {
      const res = await fetch(`${API_BASE}/api/agents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(createForm),
      })
      if (res.ok) {
        setShowCreateModal(false)
        setCreateForm({ name: '', role: '', department: '', model: '', description: '', system_prompt: '', temperature: 0.7 })
        setFormTouched(false)
        fetchAgents()
      }
    } catch (e) {
      console.error('[agents] create error:', e)
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteAgent = async (slug: string) => {
    if (!confirm('Удалить агента?')) return
    try {
      const res = await fetch(`${API_BASE}/api/agents/${slug}`, { method: 'DELETE' })
      if (res.ok) {
        setHoveredAgent(null)
        fetchAgents()
      }
    } catch (e) {
      console.error('[agents] delete error:', e)
    }
  }

  // Build provider/model options
  const modelOptions: string[] = []
  for (const p of providers) {
    if (p.models.length === 0) {
      modelOptions.push(`${p.name}/(no models)`)
    } else {
      for (const m of p.models) {
        modelOptions.push(`${p.name}/${m}`)
      }
    }
  }

  return (
    <div>
      {/* Create Agent button */}
      <div className="create-agent-bar">
        <button className="create-agent-btn" onClick={() => setShowCreateModal(true)}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M12 5v14M5 12h14" />
          </svg>
          Создать агента
        </button>
      </div>

      {/* Create Agent modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => { setShowCreateModal(false); setFormTouched(false) }}>
          <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: 520 }}>
            <div className="modal-header">
              <h2>Новый агент</h2>
              <button className="modal-close" onClick={() => { setShowCreateModal(false); setFormTouched(false) }}>×</button>
            </div>
            <div className="modal-body">
              <div className="settings-field">
                <label>Имя *</label>
                <input className={`settings-input ${formTouched && !createForm.name.trim() ? 'field-error' : ''}`}
                  placeholder="Например: Маркетолог"
                  value={createForm.name} onChange={e => setCreateForm({ ...createForm, name: e.target.value })} />
                {formTouched && !createForm.name.trim() && (
                  <span className="field-error-text">Обязательное поле</span>
                )}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div className="settings-field">
                  <label>Роль</label>
                  <select className="settings-input" style={{ cursor: 'pointer' }}
                    value={createForm.role} onChange={e => setCreateForm({ ...createForm, role: e.target.value })}>
                    <option value="">— не указана —</option>
                    {roles.map(r => <option key={r.rolesid} value={r.rolesid}>{r.name}</option>)}
                  </select>
                </div>
                <div className="settings-field">
                  <label>Департамент</label>
                  <select className="settings-input" style={{ cursor: 'pointer' }}
                    value={createForm.department} onChange={e => setCreateForm({ ...createForm, department: e.target.value })}>
                    <option value="">— не указан —</option>
                    {departments.map(d => <option key={d.departmentsid} value={d.departmentsid}>{d.name}</option>)}
                  </select>
                </div>
              </div>
              <div className="settings-field">
                <label>Модель</label>
                <select className="settings-input" style={{ cursor: 'pointer' }}
                  value={createForm.model} onChange={e => setCreateForm({ ...createForm, model: e.target.value })}>
                  <option value="">— выбрать позже —</option>
                  {modelOptions.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                </select>
              </div>
              <div className="settings-field">
                <label>Описание</label>
                <input className="settings-input" placeholder="Кратко о роли агента..."
                  value={createForm.description} onChange={e => setCreateForm({ ...createForm, description: e.target.value })} />
              </div>
              <div className="settings-field">
                <label>System Prompt</label>
                <textarea className="settings-input" rows={4} placeholder="Инструкции для агента..."
                  value={createForm.system_prompt} onChange={e => setCreateForm({ ...createForm, system_prompt: e.target.value })} />
              </div>
            </div>
            <div className="modal-footer">
              <button className="settings-btn-secondary" onClick={() => { setShowCreateModal(false); setFormTouched(false) }}>Отмена</button>
              <button className={`settings-btn-primary ${formTouched && !createForm.name.trim() ? 'btn-warn' : ''}`}
                disabled={creating}
                onClick={handleCreateAgent}>
                {creating ? 'Создание...' : 'Создать'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Roles & Departments section */}
      <div className="roles-depts-section">
        <div className="roles-depts-grid">
          {/* Roles column */}
          <div className="roles-depts-column">
            <h3 className="roles-depts-title">Роли</h3>
            <p className="roles-depts-hint">Определяют уровень ответственности агента в команде. Используются для формирования системного промта и организации чатов.</p>
            <div className="roles-depts-list">
              {roles.map(role => (
                <div key={role.rolesid} className="roles-depts-item">
                  <label className="roles-depts-color clickable" style={{ background: role.color }} title="Изменить цвет">
                    <input type="color" value={role.color} onChange={e => handleRoleColorChange(role.rolesid, e.target.value)} />
                  </label>
                  <div className="roles-depts-info">
                    <span className="roles-depts-name" style={{ color: role.color }}>{role.name}</span>
                    <span className="roles-depts-desc">{role.description}</span>
                  </div>
                  <button className="roles-depts-remove" onClick={() => handleRemoveRole(role.rolesid)} title="Удалить">×</button>
                </div>
              ))}
            </div>
            <div className="roles-depts-add">
              <input className="settings-input roles-depts-input" placeholder="Название роли..."
                value={newRole.name} onChange={e => setNewRole({ ...newRole, name: e.target.value })} />
              <input className="settings-input roles-depts-input roles-depts-input-sm" placeholder="Описание..."
                value={newRole.description} onChange={e => setNewRole({ ...newRole, description: e.target.value })} />
              <input type="color" className="roles-depts-color-picker" value={newRole.color}
                onChange={e => setNewRole({ ...newRole, color: e.target.value })} />
              <button className="roles-depts-add-btn" onClick={handleAddRole} title="Добавить роль">+</button>
            </div>
          </div>

          {/* Departments column */}
          <div className="roles-depts-column">
            <h3 className="roles-depts-title">Департаменты</h3>
            <p className="roles-depts-hint">Определяют область специализации агента. Влияют на контекст системного промта и распределение задач.</p>
            <div className="roles-depts-list">
              {departments.map(dept => (
                <div key={dept.departmentsid} className="roles-depts-item">
                  <label className="roles-depts-color clickable" style={{ background: dept.color }} title="Изменить цвет">
                    <input type="color" value={dept.color} onChange={e => handleDeptColorChange(dept.departmentsid, e.target.value)} />
                  </label>
                  <div className="roles-depts-info">
                    <span className="roles-depts-name" style={{ color: dept.color }}>{dept.name}</span>
                    <span className="roles-depts-desc">{dept.description}</span>
                  </div>
                  <button className="roles-depts-remove" onClick={() => handleRemoveDept(dept.departmentsid)} title="Удалить">×</button>
                </div>
              ))}
            </div>
            <div className="roles-depts-add">
              <input className="settings-input roles-depts-input" placeholder="Название департамента..."
                value={newDept.name} onChange={e => setNewDept({ ...newDept, name: e.target.value })} />
              <input className="settings-input roles-depts-input roles-depts-input-sm" placeholder="Описание..."
                value={newDept.description} onChange={e => setNewDept({ ...newDept, description: e.target.value })} />
              <input type="color" className="roles-depts-color-picker" value={newDept.color}
                onChange={e => setNewDept({ ...newDept, color: e.target.value })} />
              <button className="roles-depts-add-btn" onClick={handleAddDept} title="Добавить департамент">+</button>
            </div>
          </div>
        </div>
      </div>

      {/* Divider */}
      <div className="roles-depts-divider" />

      {/* External Agents section */}
      {externalDetected && externalAgents.length > 0 && (
        <section className="agents-role-section">
          <h2 className="agents-role-title">
            <span className="agents-role-dot" style={{ background: '#6b7280' }} />
            External Agents
          </h2>
          <div className="settings-grid">
            {externalAgents.map(agent => (
              <div key={agent.slug} className="agent-card-wrapper"
                onClick={() => setHoveredAgent(prev => prev === agent.slug ? null : agent.slug)}
                                onMouseLeave={() => { if (hoveredAgent === agent.slug) { setHoveredAgent(null); setOverlayShift(prev => { const n = { ...prev }; delete n[agent.slug]; return n }) } }}>
                <section className={`settings-card agent-card external-agent ${!agent.enabled ? 'disabled' : ''}`}>
                  <div className="agent-header">
                    <div className="agent-identity">
                      <span className="agent-avatar external" style={{ background: agent.color }}>{agent.icon_letter}</span>
                      <div>
                        <span className="agent-name">
                          {agent.name}
                          <span className="agent-badge extern">extern</span>
                        </span>
                        <span className="agent-role" style={{ color: roleMap[agent.role]?.color || '#6b7280' }}>
                          {deptMap[agent.department]?.name || agent.department}
                        </span>
                      </div>
                    </div>
                    <div className="agent-status-icon">
                      {!agent.available ? (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2.5"><circle cx="12" cy="12" r="10" /><path d="M15 9l-6 6M9 9l6 6" /></svg>
                      ) : agent.enabled ? (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2.5"><circle cx="12" cy="12" r="10" /><path d="M8 12l3 3 5-6" /></svg>
                      ) : (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2.5"><circle cx="12" cy="12" r="10" /><path d="M15 9l-6 6M9 9l6 6" /></svg>
                      )}
                    </div>
                  </div>
                  <div className="agent-model-text">
                    <span className="agent-model-label">ТИП</span>
                    <span className="agent-model-value">{agent.type}</span>
                  </div>
                  <div className="agent-model-text">
                    <span className="agent-model-label">ОПИСАНИЕ</span>
                    <span className="agent-model-value" style={{ fontSize: '11px', opacity: 0.7 }}>{agent.description}</span>
                  </div>
                </section>
                {hoveredAgent === agent.slug && (
                  <div className="agent-expanded-overlay" onClick={(e) => e.stopPropagation()} style={overlayShift[agent.slug] != null ? { marginTop: -overlayShift[agent.slug]! } : undefined}>
                    <div className="agent-expanded-content">
                      <div className="agent-expanded-header">
                        <span className="agent-expanded-avatar external" style={{ background: agent.color }}>{agent.icon_letter}</span>
                        <div>
                          <span className="agent-expanded-name">
                            {agent.name}
                            <span className="agent-badge extern">extern</span>
                          </span>
                          <span className="agent-expanded-role" style={{ color: roleMap[agent.role]?.color || '#6b7280' }}>
                            {roleMap[agent.role]?.name || agent.role} · {deptMap[agent.department]?.name || agent.department}
                          </span>
                        </div>
                      </div>
                      <div className="agent-expanded-body">
                        <div className="expanded-field">
                          <label>Agent ID</label>
                          <span className="agentid-display">{agent.agentid}</span>
                        </div>
                        <div className="expanded-field">
                          <label>Роль</label>
                          <select className="settings-input" value={agent.role} onChange={e => handleExternalRoleChange(agent, e.target.value)} style={{ cursor: 'pointer' }}>
                            {roles.map(r => (<option key={r.rolesid} value={r.rolesid}>{r.name}</option>))}
                          </select>
                        </div>
                        <div className="expanded-field">
                          <label>Департамент</label>
                          <select className="settings-input" value={agent.department} onChange={e => handleExternalDeptChange(agent, e.target.value)} style={{ cursor: 'pointer' }}>
                            {departments.map(d => (<option key={d.departmentsid} value={d.departmentsid}>{d.name}</option>))}
                          </select>
                        </div>
                        {agent.models.length > 0 && (
                          <div className="expanded-field">
                            <label>Модели</label>
                            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                              {agent.models.map(model => (
                                <span key={model} className="model-chip" style={{ fontSize: '11px', padding: '1px 8px' }}>{model}</span>
                              ))}
                            </div>
                          </div>
                        )}
                        <div className="expanded-toggle-row">
                          <label className="settings-toggle">
                            <input type="checkbox" checked={agent.enabled} onChange={() => handleExternalToggle(agent)} />
                            <span>Активен</span>
                          </label>
                        </div>
                        {!agent.available && (
                          <div className="external-unavailable">
                            ⚠️ Сервис недоступен. Убедитесь что Hermes Gateway запущен.
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Agents grouped by role */}
      {(() => {
        const grouped: Record<string, AgentData[]> = {}
        for (const agent of agents) {
          const key = agent.role || '_unassigned'
          if (!grouped[key]) grouped[key] = []
          grouped[key].push(agent)
        }
        const roleOrder = roles.map(r => r.rolesid)
        const allKeys = [...roleOrder.filter(k => grouped[k]), ...Object.keys(grouped).filter(k => !roleOrder.includes(k))]
        return allKeys.map(roleId => (
          <section key={roleId} className="agents-role-section">
            <h2 className="agents-role-title">
              <span className="agents-role-dot" style={{ background: roleMap[roleId]?.color || '#6b7280' }} />
              {roleMap[roleId]?.name || roleId}
            </h2>
            <div className="settings-grid">
              {(grouped[roleId] || []).map(agent => (
                <div key={agent.slug} className="agent-card-wrapper"
                  onClick={() => setHoveredAgent(prev => prev === agent.slug ? null : agent.slug)}
                                  onMouseLeave={() => { if (hoveredAgent === agent.slug) { setHoveredAgent(null); setOverlayShift(prev => { const n = { ...prev }; delete n[agent.slug]; return n }) } }}>
                  <section className={`settings-card agent-card ${!agent.enabled ? 'disabled' : ''}`}>
                    <div className="agent-header">
                      <div className="agent-identity">
                        <span className="agent-avatar">{agent.name[0]}</span>
                        <div>
                          <span className="agent-name">{agent.name}</span>
                          <span className="agent-role" style={{ color: roleMap[agent.role]?.color || '#6b7280' }}>
                            {deptMap[agent.department]?.name || agent.department}
                          </span>
                        </div>
                      </div>
                      <div className="agent-status-icon">
                        {agent.enabled ? (
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2.5"><circle cx="12" cy="12" r="10" /><path d="M8 12l3 3 5-6" /></svg>
                        ) : (
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2.5"><circle cx="12" cy="12" r="10" /><path d="M15 9l-6 6M9 9l6 6" /></svg>
                        )}
                      </div>
                    </div>
                    <div className="agent-model-text">
                      <span className="agent-model-label">МОДЕЛЬ</span>
                      <span className="agent-model-value">{agent.model || '—'}</span>
                    </div>
                    {agent.skills.length > 0 && (
                      <div className="agent-skills-compact">
                        {agent.skills.slice(0, 3).map(skill => (
                          <span key={skill} className="model-chip" style={{ fontSize: '10px', padding: '1px 6px' }}>{skill}</span>
                        ))}
                        {agent.skills.length > 3 && (
                          <span className="model-chip" style={{ fontSize: '10px', padding: '1px 6px', opacity: 0.6 }}>+{agent.skills.length - 3}</span>
                        )}
                      </div>
                    )}
                  </section>
                  {hoveredAgent === agent.slug && (
                    <div className="agent-expanded-overlay" onClick={(e) => e.stopPropagation()} style={overlayShift[agent.slug] != null ? { marginTop: -overlayShift[agent.slug]! } : undefined}>
                      <div className="agent-expanded-content">
                        <div className="agent-expanded-header">
                          <span className="agent-expanded-avatar">{agent.name[0]}</span>
                          <div>
                            <span className="agent-expanded-name">{agent.name}</span>
                            <span className="agent-expanded-role" style={{ color: roleMap[agent.role]?.color || '#6b7280' }}>
                              {roleMap[agent.role]?.name || agent.role} · {deptMap[agent.department]?.name || agent.department}
                            </span>
                          </div>
                        </div>
                        <div className="agent-expanded-body">
                          <div className="expanded-field">
                            <label>Agent ID</label>
                            <span className="agentid-display">{agent.agentid}</span>
                          </div>
                          <div className="expanded-field">
                            <label>Роль</label>
                            <select className="settings-input" value={agent.role} onChange={e => handleAgentRoleChange(agent, e.target.value)} style={{ cursor: 'pointer' }}>
                              {roles.map(r => (<option key={r.rolesid} value={r.rolesid}>{r.name}</option>))}
                            </select>
                          </div>
                          <div className="expanded-field">
                            <label>Департамент</label>
                            <select className="settings-input" value={agent.department} onChange={e => handleAgentDeptChange(agent, e.target.value)} style={{ cursor: 'pointer' }}>
                              {departments.map(d => (<option key={d.departmentsid} value={d.departmentsid}>{d.name}</option>))}
                            </select>
                          </div>
                          <div className="expanded-field">
                            <label>Модель</label>
                            <select className="settings-input" value={agent.model} onChange={e => handleModelChange(agent, e.target.value)} style={{ cursor: 'pointer' }}>
                              <option value="">— выбрать —</option>
                              {modelOptions.map(opt => (<option key={opt} value={opt}>{opt}</option>))}
                            </select>
                          </div>
                          {agent.provider && (
                            <div className="expanded-field"><label>Провайдер</label><span>{agent.provider}</span></div>
                          )}
                          <div className="expanded-field">
                            <label>Контекстное окно (токены)</label>
                            <input
                              type="number"
                              className="settings-input"
                              value={agent.context_window || ''}
                              placeholder="128000"
                              onBlur={e => {
                                const val = Number(e.target.value)
                                if (val > 0 && val !== agent.context_window) handleAgentFieldChange(agent, 'context_window', val)
                              }}
                            />
                          </div>
                          {agent.skills.length > 0 && (
                            <div className="expanded-field">
                              <label>Скиллы</label>
                              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                                {agent.skills.map(skill => (
                                  <span key={skill} className="model-chip" style={{ fontSize: '11px', padding: '1px 8px' }}>{skill}</span>
                                ))}
                              </div>
                            </div>
                          )}
                          {/* Tools */}
                          <div className="expanded-field">
                            <label>Инструменты</label>
                            <div className="tools-grid">
                              {Object.entries(toolsCategories).map(([catKey, cat]) => {
                                const catTools = Object.entries(toolsRegistry).filter(([, t]) => t.category === catKey && !t.builtin)
                                if (catTools.length === 0) return null
                                return (
                                  <div key={catKey} className="tools-category">
                                    <span className="tools-category-label">{cat.display}</span>
                                    <div className="tools-chips">
                                      {catTools.map(([name, tool]) => {
                                        const isEnabled = (agent.tools || []).includes(name)
                                        const isImplemented = tool.implemented !== false
                                        return (
                                          <button key={name}
                                            className={`tool-chip ${isEnabled ? 'active' : ''} ${!isImplemented ? 'dimmed' : ''}`}
                                            onClick={() => isImplemented && handleToolToggle(agent.agentid, name, agent.tools || [])}
                                            title={tool.description + (!isImplemented ? ' (будет доступно позже)' : '')}>
                                            <span className="tool-chip-name">{tool.display}</span>
                                          </button>
                                        )
                                      })}
                                    </div>
                                  </div>
                                )
                              })}
                            </div>
                          </div>
                          <div className="expanded-field">
                            <label>System Prompt</label>
                            <textarea className="settings-input expanded-textarea" rows={4}
                              defaultValue={agent.system_prompt}
                              onBlur={e => { if (e.target.value !== agent.system_prompt) handleAgentFieldChange(agent, 'system_prompt', e.target.value) }} />
                          </div>
                          {agent.description && (
                            <div className="expanded-field"><label>Описание</label><span className="expanded-description">{agent.description}</span></div>
                          )}
                          <div className="expanded-toggle-row">
                            <label className="settings-toggle">
                              <input type="checkbox" checked={agent.enabled} onChange={() => handleToggle(agent)} />
                              <span>Активен</span>
                            </label>
                            <button className="expanded-delete-btn" onClick={() => handleDeleteAgent(agent.slug)} title="Удалить агента">
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
                              </svg>
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        ))
      })()}
    </div>
  )
}


// ─── Providers Section ───────────────────────────────────────

interface ApiProvider {
  name: string
  type: string
  base_url: string
  api_key: string
  models: string[]
  default: boolean
  _testStatus?: 'ok' | 'error' | null  // test result cache
}

const ProvidersSection = forwardRef<{ refresh: () => void }, { onAddProvider: (type: 'openai' | 'anthropic') => void; onAddFromCatalog: (p: ProviderInfo) => void; onEditProvider: (p: ApiProvider) => void }>(
  function ProvidersSection({ onAddProvider, onAddFromCatalog, onEditProvider }, ref) {
  const [connected, setConnected] = useState<ApiProvider[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [testing, setTesting] = useState<string | null>(null)  // name of provider being tested

  // Fetch providers from API with polling
  const fetchProviders = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/providers`)
      if (res.ok) {
        const data = await res.json()
        setConnected(data.providers || [])
      }
    } catch (e) {
      console.error('[providers] fetch error:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  // No polling — refresh happens on action (add/delete/edit)
  useEffect(() => {
    fetchProviders()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Expose fetchProviders to parent via ref
  useImperativeHandle(ref, () => ({ refresh: fetchProviders }), [fetchProviders])

  const handleDisconnect = async (name: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/providers/${encodeURIComponent(name)}`, {
        method: 'DELETE',
      })
      if (res.ok) {
        fetchProviders()
      }
    } catch (e) {
      console.error('[providers] delete error:', e)
    }
  }

  const handleTest = async (conn: ApiProvider) => {
    setTesting(conn.name)
    try {
      const res = await fetch(`${API_BASE}/api/providers/${encodeURIComponent(conn.name)}/test`, {
        method: 'POST',
      })
      const data = await res.json()
      setConnected(prev => prev.map(c =>
        c.name === conn.name
          ? { ...c, _testStatus: data.status === 'ok' ? ('ok' as const) : ('error' as const) }
          : c
      ))
    } catch (e) {
      setConnected(prev => prev.map(c =>
        c.name === conn.name ? { ...c, _testStatus: 'error' as const } : c
      ))
    } finally {
      setTesting(null)
    }
  }

  const handleEditProvider = (conn: ApiProvider) => {
    onEditProvider(conn)
  }

  const filteredCatalog = PROVIDER_CATALOG.filter(p =>
    !connected.some(c => c.name === providerKey(p)) &&
    (p.name.toLowerCase().includes(searchQuery.toLowerCase()) || !searchQuery)
  )

  const groupedCatalog = {
    oauth: filteredCatalog.filter(p => p.category === 'oauth'),
    freeTier: filteredCatalog.filter(p => p.category === 'free-tier'),
    apiKey: filteredCatalog.filter(p => p.category === 'api-key'),
  }

  const handleConnect = (provider: ProviderInfo) => {
    onAddFromCatalog(provider)
  }

  return (
    <div className="providers-page">
      {/* Top buttons */}
      <div className="providers-top-actions">
        <button className="providers-add-btn anthropic" onClick={() => onAddProvider('anthropic')}>
          + Add Anthropic Compatible
        </button>
        <button className="providers-add-btn openai" onClick={() => onAddProvider('openai')}>
          + Add OpenAI Compatible
        </button>
      </div>

      {/* Connected providers */}
      {loading ? (
        <div className="providers-loading">
          <div className="spinner" />
          <span>Загрузка провайдеров...</span>
        </div>
      ) : connected.length > 0 ? (
        <section className="providers-section">
          <div className="providers-section-header">
            <h2 className="providers-section-title">Подключённые провайдеры</h2>
            <span className="providers-count">{connected.length} {pluralize(connected.length, 'провайдер', 'провайдера', 'провайдеров')}</span>
          </div>
          <div className="connected-providers-grid">
            {connected.map(conn => {
              const catalogEntry = PROVIDER_CATALOG.find(p => providerKey(p) === conn.name)
              const displayName = catalogEntry?.name || conn.name
              const iconUrl = catalogEntry ? providerIconUrl(catalogEntry) : null
              const hasIcon = !!catalogEntry && !!iconUrl

              return (
                <div key={conn.name} className="connected-provider-card" onClick={() => handleEditProvider(conn)}>
                  <div className="cp-icon-wrap">
                    {hasIcon ? (
                      <img src={iconUrl} alt={displayName} className="cp-icon-img"
                        onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
                    ) : (
                      <svg className="cp-fallback-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                      </svg>
                    )}
                  </div>
                  <div className="cp-info">
                    <span className="cp-name">{displayName}</span>
                    {conn.models.length > 0 && (
                      <span className="cp-models">{conn.models.join(', ')}</span>
                    )}
                  </div>

                  {/* Test button — manual test on click */}
                  {conn._testStatus === 'ok' && (
                    <svg className="cp-test-result ok" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
                      onClick={e => { e.stopPropagation(); handleTest(conn) }}
                      aria-label="Тест подключения">
                      <path d="M22 4L12 14.01l-3-3" />
                    </svg>
                  )}
                  {conn._testStatus === 'error' && (
                    <svg className="cp-test-result error" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
                      onClick={e => { e.stopPropagation(); handleTest(conn) }}
                      aria-label="Тест подключения">
                      <path d="M18 6L6 18M6 6l12 12" />
                    </svg>
                  )}
                  {testing === conn.name && (
                    <svg className="cp-test-result loading" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M21 12a9 9 0 11-6.2-8.6" />
                    </svg>
                  )}
                  {!conn._testStatus && testing !== conn.name && (
                    <svg className="cp-test-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                      onClick={e => { e.stopPropagation(); handleTest(conn) }}
                      aria-label="Тест подключения">
                      <path d="M22 11.08V12a10 10 0 11-5.9-9.1" />
                      <path d="M22 4L12 14.01l-3-3" />
                    </svg>
                  )}

                  <button className="cp-disconnect-btn"
                    onClick={e => { e.stopPropagation(); handleDisconnect(conn.name) }}
                    title="Отключить">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M18 6L6 18M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              )
            })}
          </div>
        </section>
      ) : (
        <section className="providers-section">
          <div className="connected-providers-empty">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
            </svg>
            <p>Нет подключённых провайдеров</p>
            <span>Используйте кнопки выше или каталог ниже</span>
          </div>
        </section>
      )}

      {/* Search */}
      <div className="providers-search-bar">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
        </svg>
        <input
          type="text"
          className="providers-search-input"
          placeholder="Поиск провайдеров..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
        />
      </div>

      {/* Provider catalog sections */}
      {groupedCatalog.oauth.length > 0 && (
        <ProviderGridSection title="OAuth Providers" providers={groupedCatalog.oauth} onConnect={handleConnect} />
      )}
      {groupedCatalog.freeTier.length > 0 && (
        <ProviderGridSection title="Free Tier Providers" providers={groupedCatalog.freeTier} onConnect={handleConnect} />
      )}
      {groupedCatalog.apiKey.length > 0 && (
        <ProviderGridSection title="API Key Providers" providers={groupedCatalog.apiKey} onConnect={handleConnect} />
      )}
    </div>
  )
})

function pluralize(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod100 >= 11 && mod100 <= 19) return many
  if (mod10 === 1) return one
  if (mod10 >= 2 && mod10 <= 4) return few
  return many
}

// ─── Add from Catalog Modal ──────────────────────────────────

function AddFromCatalogModal({ provider, editProvider, onClose, onSaved }: {
  provider: ProviderInfo
  editProvider?: ApiProvider
  onClose: () => void
  onSaved: () => void
}) {
  const key = providerKey(provider)
  const isNoAuth = provider.authMethod === 'no-auth'
  const isEdit = !!editProvider
  const [apiKey, setApiKey] = useState(isEdit ? '••••••••' : '')
  const [modelsInput, setModelsInput] = useState(
    isEdit ? editProvider!.models.join(', ') : (provider.defaultModels || []).join(', ')
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<'ok' | 'error' | null>(null)
  const [testMessage, setTestMessage] = useState('')
  const [fetchedModels, setFetchedModels] = useState<string[]>([])

  /** Fetch models from provider API AFTER test connection succeeds */
  // No auto-fetch on mount — models appear only after successful test

  /** Parse models from comma-separated input */
  const parseModels = () => modelsInput.split(',').map(m => m.trim()).filter(Boolean)

  /** All known models for chips: fetched from API (after test) or catalog defaults (edit mode) */
  const allKnownModels = fetchedModels.length > 0
    ? fetchedModels
    : (isEdit ? (provider.defaultModels || []) : [])
  const customModels = parseModels().filter(m => !allKnownModels.includes(m))
  const chipModels = [...new Set([...allKnownModels, ...customModels])]
  const currentModels = parseModels()

  const toggleModel = (model: string) => {
    const models = parseModels()
    if (models.includes(model)) {
      setModelsInput(models.filter(m => m !== model).join(', '))
    } else {
      setModelsInput(models.length > 0 ? modelsInput + ', ' + model : model)
    }
  }

  /** Smart test: try with key → try without → final result */
  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    setTestMessage('')
    setError('')
    setFetchedModels([])

    const modelList = parseModels()

    const tryTest = async (useKey: boolean): Promise<{status: string; message?: string; models?: string[]}> => {
      const tempName = key + '-test-temp'
      const body: Record<string, unknown> = {
        name: tempName,
        type: provider.type,
        base_url: provider.baseUrl,
        api_key: useKey ? apiKey : '',
        models: modelList,
      }
      // Create temp
      await fetch(`${API_BASE}/api/providers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      try {
        const res = await fetch(`${API_BASE}/api/providers/${encodeURIComponent(tempName)}/test`, {
          method: 'POST',
        })
        // Safely parse JSON — backend might return non-JSON on error
        const text = await res.text()
        try {
          return JSON.parse(text)
        } catch {
          return { status: 'error', message: `Сервер вернул не JSON: ${text.slice(0, 100)}` }
        }
      } finally {
        // Cleanup temp
        await fetch(`${API_BASE}/api/providers/${encodeURIComponent(tempName)}`, { method: 'DELETE' }).catch(() => {})
      }
    }

    try {
      if (isNoAuth || !apiKey.trim() || apiKey === '••••••••') {
        // No-auth provider or empty/masked key — test without key
        const result = await tryTest(false)
        setTestResult(result.status === 'ok' ? 'ok' : 'error')
        setTestMessage(result.message || '')
        if (result.status === 'ok' && result.models) {
          setFetchedModels(result.models)
        }
      } else {
        // Has key — try WITH key first
        let result = await tryTest(true)
        if (result.status === 'ok') {
          setTestResult('ok')
          setTestMessage(result.message || '')
          if (result.models) setFetchedModels(result.models)
        } else {
          // Failed with key — try WITHOUT key (provider might not need it)
          result = await tryTest(false)
          if (result.status === 'ok') {
            setTestResult('ok')
            setTestMessage(result.message + ' (работает без ключа)')
            if (result.models) setFetchedModels(result.models)
          } else {
            setTestResult('error')
            setTestMessage(result.message || 'Не удалось подключиться')
          }
        }
      }
    } catch (e) {
      setTestResult('error')
      setTestMessage('Ошибка сети')
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setError('')
    try {
      const body: Record<string, unknown> = {
        name: isEdit ? editProvider!.name : key,
        type: provider.type,
        base_url: provider.baseUrl,
        api_key: isNoAuth ? '' : (apiKey === '••••••••' ? '' : apiKey),
        models: parseModels(),
      }
      const res = await fetch(
        isEdit
          ? `${API_BASE}/api/providers/${encodeURIComponent(editProvider!.name)}`
          : `${API_BASE}/api/providers`,
        {
          method: isEdit ? 'PUT' : 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }
      )
      if (res.ok) {
        onSaved()
      } else {
        const data = await res.json().catch(() => ({}))
        setError(data.detail || 'Ошибка сохранения')
      }
    } catch (e) {
      setError('Не удалось подключиться к серверу')
    } finally {
      setSaving(false)
    }
  }

  const iconUrl = providerIconUrl(provider)

  return (
    <div className="modal-inner">
      {/* Provider header */}
      <div className="catalog-modal-header">
        <div className="catalog-modal-icon">
          {iconUrl ? (
            <img src={iconUrl} alt={provider.name} className="catalog-modal-icon-img" />
          ) : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
            </svg>
          )}
        </div>
        <div className="catalog-modal-title-wrap">
          <h2 className="modal-title">{isEdit ? 'Редактировать' : provider.name}</h2>
          <span className="catalog-modal-url">{provider.baseUrl}</span>
        </div>
      </div>

      <div className="modal-body">
        {/* API Key — hidden for no-auth providers */}
        {!isNoAuth && (
          <div className="settings-field">
            <label>API Key <span className="field-hint">{isEdit ? '(оставьте пустым, чтобы не менять)' : '(необязательно — если не знаешь, оставь пустым)'}</span></label>
            <input type="password" className="settings-input" placeholder={provider.apiKeyHint || 'sk-...'}
              value={apiKey} onChange={e => setApiKey(e.target.value)} />
          </div>
        )}

        {isNoAuth && (
          <div className="catalog-modal-info">
            <span>🔓 Этот провайдер работает без API ключа</span>
          </div>
        )}

        {/* Test button */}
        <div className="catalog-modal-test-row">
          <button className="catalog-modal-test-btn" onClick={handleTest} disabled={testing}>
            {testing ? 'Тестирование...' : 'Тест подключения'}
          </button>
          {testResult === 'ok' && <span className="catalog-test-badge ok">✓ {testMessage}</span>}
          {testResult === 'error' && <span className="catalog-test-badge error">✗ {testMessage}</span>}
        </div>

        {/* Models — single-line comma-separated input */}
        <div className="settings-field">
          <label>Модели <span className="field-hint">(через запятую)</span></label>
          <input type="text" className="settings-input models-input"
            value={modelsInput} onChange={e => setModelsInput(e.target.value)}
            placeholder="gpt-4o, gpt-4o-mini" />
        </div>

        {/* Model chips — only shown after test or when editing with existing models */}
        {chipModels.length > 0 && (
          <div className="model-chips-container">
            {chipModels.map(model => {
              const isActive = currentModels.includes(model)
              const isKnown = allKnownModels.includes(model)
              return (
                <button
                  key={model}
                  className={`model-chip${isActive ? ' active' : ''}${!isKnown ? ' custom' : ''}`}
                  onClick={() => toggleModel(model)}
                  type="button"
                >
                  {model}
                  {!isKnown && <span className="chip-remove">×</span>}
                </button>
              )
            })}
          </div>
        )}

        {error && <div className="modal-error">{error}</div>}
      </div>

      <div className="modal-footer">
        <button className="settings-btn-secondary" onClick={onClose}>Отмена</button>
        <button className="settings-btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Сохранение...' : (isEdit ? 'Сохранить' : 'Подключить')}
        </button>
      </div>
    </div>
  )
}

function ProviderGridSection({ title, providers, onConnect }: { title: string; providers: ProviderInfo[]; onConnect: (p: ProviderInfo) => void }) {
  return (
    <section className="providers-section">
      <h2 className="providers-section-title">{title}</h2>
      <div className="provider-catalog-grid">
        {providers.map(provider => {
          const iconUrl = providerIconUrl(provider)
          const isOAuthDisabled = provider.oauthDisabled

          return (
            <button
              key={provider.id}
              className={`provider-catalog-card${isOAuthDisabled ? ' oauth-disabled' : ''}`}
              onClick={() => !isOAuthDisabled && onConnect(provider)}
              title={isOAuthDisabled ? 'OAuth подключение скоро' : provider.name}
            >
              <div className="pc-icon-wrap">
                {iconUrl ? (
                  <img src={iconUrl} alt={provider.name} className="pc-icon-img"
                    onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
                ) : null}
              </div>
              <span className="pc-name">{provider.name}</span>
              <span className="pc-models">{(provider.defaultModels || []).slice(0, 2).join(', ')}</span>
              {isOAuthDisabled && <span className="pc-oauth-badge">🔒 OAuth</span>}
            </button>
          )
        })}
      </div>
    </section>
  )
}

// MemorySection imported from ./MemorySection
// ─── Channels Section ────────────────────────────────────────

const sampleChannels = [
  { id: 'feishu-main', name: 'Feishu — Основной', type: 'feishu', status: 'connected', binding: 'Основной агент', mode: 'websocket' },
  { id: 'whatsapp-board', name: 'WhatsApp — Совет директоров', type: 'whatsapp', status: 'disconnected', binding: 'Совет директоров', mode: 'webhook' },
  { id: 'telegram-qa', name: 'Telegram — QA команда', type: 'telegram', status: 'disconnected', binding: 'QA департамент', mode: 'polling' },
]

function ChannelsSection({ onAddChannel }: { onAddChannel: () => void }) {
  const [channels] = useState(sampleChannels)
  const typeIcons: Record<string, string> = { feishu: '🟢', whatsapp: '💬', telegram: '✈️', slack: '💜', discord: '🎮', email: '📧' }

  return (
    <div className="settings-sections">
      <div className="section-header-row">
        <span className="section-count">{channels.filter(c => c.status === 'connected').length} подключено</span>
        <button className="settings-btn-primary" onClick={onAddChannel}>+ Добавить канал</button>
      </div>
      {channels.map(channel => (
        <div key={channel.id} className={`settings-card channel-card ${channel.status !== 'connected' ? 'disconnected' : ''}`}>
          <div className="channel-header">
            <div className="channel-identity">
              <span className="channel-icon">{typeIcons[channel.type] || '📡'}</span>
              <span className={`channel-status-dot ${channel.status}`} />
              <div>
                <span className="channel-name">{channel.name}</span>
                <span className="channel-meta">{channel.type} · {channel.mode} · {channel.binding}</span>
              </div>
            </div>
            <span className={`channel-status-badge ${channel.status}`}>
              {channel.status === 'connected' ? 'Подключён' : 'Отключён'}
            </span>
          </div>
          {channel.status === 'connected' && (
            <div className="channel-details">
              <div className="settings-field">
                <label>Привязка</label>
                <CustomDropdown
                  value="main"
                  onChange={() => {}}
                  options={[
                    { value: 'main', label: 'Основной агент' },
                    { value: 'department:dev', label: 'Департамент: Разработка' },
                    { value: 'department:qa', label: 'Департамент: QA' },
                    { value: 'agent:architect', label: 'Агент: Архитектор' },
                  ]}
                />
              </div>
              <Toggle label="Уведомления" defaultChecked />
              <Toggle label="Загрузка файлов" defaultChecked />
              <Toggle label="Слэш-команды" defaultChecked />
              <div className="provider-actions">
                <button className="settings-btn-secondary">Сохранить</button>
                <button className="settings-btn-danger">Отключить</button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ─── Modals ──────────────────────────────────────────────────

function AddProviderModal({ type, onClose, onSaved }: { type: 'openai' | 'anthropic'; onClose: () => void; onSaved: () => void }) {
  const isAnthropic = type === 'anthropic'
  const [name, setName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSave = async () => {
    if (!name.trim()) {
      setError('Название обязательно')
      return
    }
    setSaving(true)
    setError('')
    try {
      const slug = name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')
      const body: Record<string, unknown> = {
        name: slug,
        type: isAnthropic ? 'anthropic' : 'openai-compatible',
        base_url: baseUrl,
        api_key: apiKey,
        models: model ? [model] : [],
      }
      const res = await fetch(`${API_BASE}/api/providers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (res.ok) {
        onSaved()
      } else {
        const data = await res.json().catch(() => ({}))
        setError(data.detail || 'Ошибка сохранения')
      }
    } catch (e) {
      setError('Не удалось подключиться к серверу')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-inner">
      <h2 className="modal-title">
        {isAnthropic ? 'Add Anthropic Compatible' : 'Add OpenAI Compatible'}
      </h2>
      <p className="modal-subtitle">
        {isAnthropic
          ? 'Подключите провайдер, совместимый с Anthropic API'
          : 'Подключите провайдер, совместимый с OpenAI API'}
      </p>
      <div className="modal-body">
        <div className="settings-field">
          <label>Название</label>
          <input type="text" className="settings-input" placeholder="my-provider"
            value={name} onChange={e => setName(e.target.value)} />
        </div>
        <div className="settings-field">
          <label>Base URL</label>
          <input type="text" className="settings-input"
            placeholder={isAnthropic ? 'https://api.anthropic.com' : 'https://api.openai.com/v1'}
            value={baseUrl} onChange={e => setBaseUrl(e.target.value)} />
        </div>
        <div className="settings-field">
          <label>Модель</label>
          <input type="text" className="settings-input"
            placeholder={isAnthropic ? 'claude-sonnet-4' : 'gpt-4o'}
            value={model} onChange={e => setModel(e.target.value)} />
        </div>
        <div className="settings-field">
          <label>API Key</label>
          <input type="password" className="settings-input" placeholder="sk-..."
            value={apiKey} onChange={e => setApiKey(e.target.value)} />
        </div>
        {error && <div className="modal-error">{error}</div>}
      </div>
      <div className="modal-footer">
        <button className="settings-btn-secondary" onClick={onClose}>Отмена</button>
        <button className="settings-btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Сохранение...' : 'Сохранить'}
        </button>
      </div>
    </div>
  )
}

function EditCustomProviderModal({ provider, onClose, onSaved }: { provider: ApiProvider; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(provider.name)
  const [baseUrl, setBaseUrl] = useState(provider.base_url)
  const [model, setModel] = useState(provider.models.join(', '))
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSave = async () => {
    if (!name.trim()) {
      setError('Название обязательно')
      return
    }
    setSaving(true)
    setError('')
    try {
      const models = model.split(',').map(m => m.trim()).filter(Boolean)
      const body: Record<string, unknown> = {
        name: name,
        type: provider.type,
        base_url: baseUrl,
        api_key: apiKey || undefined,
        models,
      }
      const res = await fetch(`${API_BASE}/api/providers/${encodeURIComponent(provider.name)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (res.ok) {
        onSaved()
      } else {
        const data = await res.json().catch(() => ({}))
        setError(data.detail || 'Ошибка сохранения')
      }
    } catch (e) {
      setError('Не удалось подключиться к серверу')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-inner">
      <h2 className="modal-title">Редактировать провайдер</h2>
      <p className="modal-subtitle">{provider.type}</p>
      <div className="modal-body">
        <div className="settings-field">
          <label>Название</label>
          <input type="text" className="settings-input" value={name}
            onChange={e => setName(e.target.value)} />
        </div>
        <div className="settings-field">
          <label>Base URL</label>
          <input type="text" className="settings-input" value={baseUrl}
            onChange={e => setBaseUrl(e.target.value)} />
        </div>
        <div className="settings-field">
          <label>Модели (через запятую)</label>
          <input type="text" className="settings-input" value={model}
            onChange={e => setModel(e.target.value)} />
        </div>
        <div className="settings-field">
          <label>API Key (оставь пустым без изменений)</label>
          <input type="password" className="settings-input" placeholder="sk-..."
            value={apiKey} onChange={e => setApiKey(e.target.value)} />
        </div>
        {error && <div className="modal-error">{error}</div>}
      </div>
      <div className="modal-footer">
        <button className="settings-btn-secondary" onClick={onClose}>Отмена</button>
        <button className="settings-btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Сохранение...' : 'Сохранить'}
        </button>
      </div>
    </div>
  )
}

function AddChannelModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="modal-inner">
      <h2 className="modal-title">Добавить канал связи</h2>
      <div className="modal-body">
        <div className="settings-field">
          <label>Название</label>
          <input type="text" className="settings-input" placeholder="Feishu — Основной" />
        </div>
        <div className="settings-field">
          <label>Тип канала</label>
          <CustomDropdown
            value="feishu"
            onChange={() => {}}
            options={[
              { value: 'feishu', label: '🟢 Feishu (Lark)' },
              { value: 'whatsapp', label: '💬 WhatsApp Business' },
              { value: 'telegram', label: '✈️ Telegram' },
              { value: 'slack', label: '💜 Slack' },
              { value: 'discord', label: '🎮 Discord' },
              { value: 'email', label: '📧 Email' },
            ]}
          />
        </div>
        <div className="settings-field">
          <label>Режим подключения</label>
          <CustomDropdown
            value="websocket"
            onChange={() => {}}
            options={[
              { value: 'websocket', label: 'WebSocket' },
              { value: 'webhook', label: 'Webhook' },
              { value: 'polling', label: 'Polling' },
            ]}
          />
        </div>
        <div className="settings-field">
          <label>Привязка к</label>
          <CustomDropdown
            value="main"
            onChange={() => {}}
            options={[
              { value: 'main', label: 'Основной агент' },
              { value: 'department', label: 'Департамент' },
              { value: 'agent', label: 'Конкретный агент' },
            ]}
          />
        </div>
        <div className="settings-field">
          <label>App ID</label>
          <input type="text" className="settings-input" placeholder="cli_a5..." />
        </div>
        <div className="settings-field">
          <label>App Secret</label>
          <input type="password" className="settings-input" placeholder="***" />
        </div>
      </div>
      <div className="modal-footer">
        <button className="settings-btn-secondary" onClick={onClose}>Отмена</button>
        <button className="settings-btn-primary" onClick={onClose}>Сохранить</button>
      </div>
    </div>
  )
}

// ─── Skills Section ──────────────────────────────────────────

function SkillsSection() {
  return (
    <div className="settings-sections">
      <section className="settings-card">
        <h2 className="settings-card-title">🧠 Скиллы системы</h2>
        <p style={{ color: 'var(--gray-500)', fontSize: '14px', lineHeight: '1.6' }}>
          База скиллов — подходы, шаблоны и процедуры, которые система использует для решения задач.
        </p>
        <div style={{ marginTop: '16px', padding: '12px', background: 'var(--gray-900)', borderRadius: '8px', border: '1px solid var(--gray-800)' }}>
          <span style={{ color: 'var(--gray-400)', fontSize: '13px' }}>🚧 В разработке — здесь будет список скиллов с возможностью добавления, редактирования и привязки к агентам</span>
        </div>
      </section>
    </div>
  )
}
