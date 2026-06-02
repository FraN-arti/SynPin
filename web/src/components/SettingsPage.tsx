import { useState, useEffect, useRef, useCallback } from 'react'
import { PROVIDER_CATALOG, PROVIDERS_BY_CATEGORY, type ProviderInfo } from '../lib/providers'

interface SettingsPageProps {
  onBack: () => void
}

type Tab = 'general' | 'agents' | 'providers' | 'memory' | 'channels'

const TABS: { id: Tab; label: string }[] = [
  { id: 'general', label: 'Основное' },
  { id: 'agents', label: 'Агенты' },
  { id: 'providers', label: 'Провайдеры' },
  { id: 'memory', label: 'Память' },
  { id: 'channels', label: 'Каналы' },
]

const SECTION_INFO: Record<Tab, { title: string; description: string }> = {
  general: { title: 'Основное', description: 'Настройки системы: порты, интерфейс, лента активности' },
  agents: { title: 'AI Агенты', description: 'Роли, модели, личности и системные промты агентов' },
  providers: { title: 'Провайдеры', description: 'Подключённые провайдеры и доступные для подключения' },
  memory: { title: 'Память', description: 'Архитектура памяти: агентская, командная, системная' },
  channels: { title: 'Каналы связи', description: 'Feishu, WhatsApp, Telegram — мультимодальная связь с системой' },
}

export function SettingsPage({ onBack }: SettingsPageProps) {
  const [activeTab, setActiveTab] = useState<Tab>('general')
  const [visible, setVisible] = useState(false)
  const [activeModal, setActiveModal] = useState<string | null>(null)

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
            {activeModal === 'add-provider-openai' && <AddProviderModal type="openai" onClose={() => setActiveModal(null)} />}
            {activeModal === 'add-provider-anthropic' && <AddProviderModal type="anthropic" onClose={() => setActiveModal(null)} />}
            {activeModal === 'add-channel' && <AddChannelModal onClose={() => setActiveModal(null)} />}
          </div>
        </div>
      )}

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
          {activeTab === 'agents' && <AgentsSection />}
          {activeTab === 'providers' && <ProvidersSection onAddProvider={(type) => setActiveModal(`add-provider-${type}`)} />}
          {activeTab === 'memory' && <MemorySection />}
          {activeTab === 'channels' && <ChannelsSection onAddChannel={() => setActiveModal('add-channel')} />}
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

function GeneralSection() {
  const handleAutosave = useCallback((key: string, value: string | boolean) => {
    console.log(`[autosave] ${key} =`, value)
    // TODO: POST to /api/settings
  }, [])

  return (
    <div className="settings-grid">
      <section className="settings-card">
        <h2 className="settings-card-title">🖥 Сервер</h2>
        <div className="settings-field">
          <label>Порт API</label>
          <input type="number" className="settings-input" defaultValue={2088}
            onChange={e => handleAutosave('server.port', e.target.value)} />
        </div>
        <div className="settings-field">
          <label>Порт Dev (Vite)</label>
          <input type="number" className="settings-input" defaultValue={2099}
            onChange={e => handleAutosave('server.dev_port', e.target.value)} />
        </div>
        <div className="settings-field">
          <label>Host</label>
          <input type="text" className="settings-input" defaultValue="0.0.0.0"
            onChange={e => handleAutosave('server.host', e.target.value)} />
        </div>
      </section>

      <section className="settings-card">
        <h2 className="settings-card-title">🎨 Интерфейс</h2>
        <div className="settings-field">
          <label>Тема</label>
          <CustomDropdown
            value="dark"
            onChange={v => handleAutosave('ui.theme', v)}
            options={[
              { value: 'dark', label: 'Тёмная' },
              { value: 'dark-oled', label: 'Тёмная (OLED)' },
              { value: 'light', label: 'Светлая (скоро)', disabled: true },
            ]}
          />
        </div>
        <div className="settings-field">
          <label>Язык</label>
          <CustomDropdown
            value="ru"
            onChange={v => handleAutosave('ui.language', v)}
            options={[
              { value: 'ru', label: 'Русский' },
              { value: 'en', label: 'English' },
            ]}
          />
        </div>
        <Toggle label="Показывать метаданные сообщений" defaultChecked
          onChange={v => handleAutosave('ui.chat.show_metadata', v)} />
        <Toggle label="Анимированная обводка при стриминге" defaultChecked
          onChange={v => handleAutosave('ui.chat.streaming_border', v)} />
        <Toggle label="Автоскролл к новым сообщениям" defaultChecked
          onChange={v => handleAutosave('ui.chat.auto_scroll', v)} />
      </section>

      <section className="settings-card">
        <h2 className="settings-card-title">📡 Лента активности</h2>
        <div className="settings-field">
          <label>Макс. записей</label>
          <input type="number" className="settings-input" defaultValue={50}
            onChange={e => handleAutosave('feed.max_items', e.target.value)} />
        </div>
        <div className="settings-field">
          <label>Период</label>
          <CustomDropdown
            value="24h"
            onChange={v => handleAutosave('feed.time_range', v)}
            options={[
              { value: '1h', label: '1 час' },
              { value: '6h', label: '6 часов' },
              { value: '24h', label: '24 часа' },
              { value: '7d', label: '7 дней' },
              { value: '30d', label: '30 дней' },
            ]}
          />
        </div>
        <Toggle label="Новые идеи" defaultChecked
          onChange={v => handleAutosave('feed.filters.new_ideas', v)} />
        <Toggle label="Обновления задач" defaultChecked
          onChange={v => handleAutosave('feed.filters.task_updates', v)} />
        <Toggle label="Обновления памяти"
          onChange={v => handleAutosave('feed.filters.memory_updates', v)} />
        <Toggle label="Обновления канбана" defaultChecked
          onChange={v => handleAutosave('feed.filters.board_updates', v)} />
      </section>
    </div>
  )
}

// ─── Toggle Component ────────────────────────────────────────

function Toggle({ label, defaultChecked, onChange }: { label: string; defaultChecked?: boolean; onChange?: (v: boolean) => void }) {
  return (
    <div className="settings-field-row">
      <label className="settings-toggle">
        <input type="checkbox" defaultChecked={defaultChecked}
          onChange={e => onChange?.(e.target.checked)} />
        <span>{label}</span>
      </label>
    </div>
  )
}

// ─── Agents Section ──────────────────────────────────────────

const sampleAgents = [
  { id: 'architect', name: 'Архитектор', role: 'head', department: 'dev', model: 'general-agent', enabled: true, traits: 'analytical, thinks before answering' },
  { id: 'developer', name: 'Разработчик', role: 'worker', department: 'dev', model: 'general-agent', enabled: true, traits: 'pragmatic, writes clean code' },
  { id: 'qa-engineer', name: 'QA Инженер', role: 'worker', department: 'qa', model: 'general-agent', enabled: true, traits: 'meticulous, finds edge cases' },
]

function AgentsSection() {
  const [agents] = useState(sampleAgents)
  const roleLabels: Record<string, string> = { worker: 'Работник', head: 'Руководитель', director: 'Директор' }
  const roleColors: Record<string, string> = { worker: '#6b7280', head: '#f59e0b', director: '#ef4444' }

  return (
    <div className="settings-sections">
      <div className="section-header-row">
        <span className="section-count">{agents.length} агентов</span>
        <button className="settings-btn-primary">+ Добавить агента</button>
      </div>
      {agents.map(agent => (
        <div key={agent.id} className={`settings-card agent-card ${!agent.enabled ? 'disabled' : ''}`}>
          <div className="agent-header">
            <div className="agent-identity">
              <span className="agent-avatar">{agent.name[0]}</span>
              <div>
                <span className="agent-name">{agent.name}</span>
                <span className="agent-role" style={{ color: roleColors[agent.role] }}>
                  {roleLabels[agent.role]} · {agent.department}
                </span>
              </div>
            </div>
            <label className="settings-toggle">
              <input type="checkbox" defaultChecked={agent.enabled} />
              <span>Активен</span>
            </label>
          </div>
          <div className="agent-details">
            <div className="settings-field">
              <label>Модель</label>
              <input type="text" className="settings-input" defaultValue={agent.model} />
            </div>
            <div className="settings-field">
              <label>Характер</label>
              <input type="text" className="settings-input" defaultValue={agent.traits} />
            </div>
            <div className="settings-field">
              <label>Системный промпт</label>
              <textarea className="settings-textarea" rows={3} defaultValue="Custom system prompt..." />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ─── Providers Section ───────────────────────────────────────

interface ConnectedProvider {
  id: string
  providerId: string  // catalog ID
  name: string
  type: string
  baseUrl: string
  model: string
  apiKey: string
  isDefault: boolean
}

function ProvidersSection({ onAddProvider }: { onAddProvider: (type: 'openai' | 'anthropic') => void }) {
  const [connected, setConnected] = useState<ConnectedProvider[]>([
    { id: 'conn-1', providerId: '9router', name: '9Router', type: 'openai-compatible', baseUrl: 'http://localhost:20128/v1', model: 'general-agent', apiKey: 'sk-***', isDefault: true },
  ])

  const [searchQuery, setSearchQuery] = useState('')

  const filteredCatalog = PROVIDER_CATALOG.filter(p =>
    !connected.some(c => c.providerId === p.id) &&
    (p.name.toLowerCase().includes(searchQuery.toLowerCase()) || !searchQuery)
  )

  const groupedCatalog = {
    oauth: filteredCatalog.filter(p => p.category === 'oauth'),
    freeTier: filteredCatalog.filter(p => p.category === 'free-tier'),
    apiKey: filteredCatalog.filter(p => p.category === 'api-key'),
  }

  const handleConnect = (provider: ProviderInfo) => {
    const newConn: ConnectedProvider = {
      id: `conn-${Date.now()}`,
      providerId: provider.id,
      name: provider.name,
      type: provider.type,
      baseUrl: provider.baseUrl,
      model: provider.defaultModels[0],
      apiKey: '',
      isDefault: connected.length === 0,
    }
    setConnected([...connected, newConn])
  }

  const handleDisconnect = (connId: string) => {
    setConnected(connected.filter(c => c.id !== connId))
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
      {connected.length > 0 && (
        <section className="providers-section">
          <h2 className="providers-section-title">Подключённые провайдеры</h2>
          <div className="connected-providers-grid">
            {connected.map(conn => (
              <div key={conn.id} className="connected-provider-card">
                <div className="cp-header">
                  <span className="cp-icon">{PROVIDER_CATALOG.find(p => p.id === conn.providerId)?.icon || '🔌'}</span>
                  <span className="cp-status-dot" />
                </div>
                <div className="cp-info">
                  <span className="cp-name">{conn.name}</span>
                  <span className="cp-model">{conn.model}</span>
                </div>
                <div className="cp-actions">
                  {conn.isDefault && <span className="cp-badge">Default</span>}
                  <button className="cp-disconnect-btn" onClick={() => handleDisconnect(conn.id)} title="Отключить">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M18 6L6 18M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
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
}

function ProviderGridSection({ title, providers, onConnect }: { title: string; providers: ProviderInfo[]; onConnect: (p: ProviderInfo) => void }) {
  return (
    <section className="providers-section">
      <h2 className="providers-section-title">{title}</h2>
      <div className="provider-catalog-grid">
        {providers.map(provider => (
          <button key={provider.id} className="provider-catalog-card" onClick={() => onConnect(provider)}>
            <span className="pc-icon">{provider.icon}</span>
            <span className="pc-name">{provider.name}</span>
            <span className="pc-models">{provider.defaultModels.slice(0, 2).join(', ')}</span>
          </button>
        ))}
      </div>
    </section>
  )
}

// ─── Memory Section ──────────────────────────────────────────

function MemorySection() {
  return (
    <div className="settings-grid">
      <section className="settings-card">
        <h2 className="settings-card-title">👤 Память агентов</h2>
        <Toggle label="Включена" defaultChecked />
        <Toggle label="Автосохранение по окончании сессии" defaultChecked />
        <Toggle label="Сохранять уроки из ошибок" defaultChecked />
        <Toggle label="Сохранять активные решения" defaultChecked />
        <div className="settings-field">
          <label>Макс. сессий на агента</label>
          <input type="number" className="settings-input" defaultValue={50} />
        </div>
        <div className="settings-field">
          <label>Макс. длина summary (символы)</label>
          <input type="number" className="settings-input" defaultValue={500} />
        </div>
      </section>

      <section className="settings-card">
        <h2 className="settings-card-title">👥 Командная память</h2>
        <Toggle label="Включена" defaultChecked />
        <Toggle label="Автoshare новых паттернов" defaultChecked />
        <Toggle label="Автoshare архитектурных решений" defaultChecked />
        <Toggle label="Автoshare лучших практик" defaultChecked />
        <Toggle label="Автoshare найденных багов" defaultChecked />
      </section>

      <section className="settings-card">
        <h2 className="settings-card-title">🔍 Поиск</h2>
        <Toggle label="SQLite FTS5 (основной)" defaultChecked />
        <Toggle label="Векторный поиск (дополнительный)" />
        <div className="settings-field">
          <label>Вес точного совпадения</label>
          <input type="number" className="settings-input" defaultValue={10} />
        </div>
        <div className="settings-field">
          <label>Вес пословного совпадения</label>
          <input type="number" className="settings-input" defaultValue={5} />
        </div>
      </section>

      <section className="settings-card">
        <h2 className="settings-card-title">🗑 Lifecycle</h2>
        <div className="settings-field">
          <label>Архивировать сессии через (дней)</label>
          <input type="number" className="settings-input" defaultValue={90} />
        </div>
        <div className="settings-field">
          <label>Удалить архивные через (дней)</label>
          <input type="number" className="settings-input" defaultValue={365} />
        </div>
        <div className="settings-field">
          <label>Компактировать память при ({'>'} записей)</label>
          <input type="number" className="settings-input" defaultValue={50} />
        </div>
      </section>
    </div>
  )
}

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

function AddProviderModal({ type, onClose }: { type: 'openai' | 'anthropic'; onClose: () => void }) {
  const isAnthropic = type === 'anthropic'

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
          <input type="text" className="settings-input" placeholder="My Provider" />
        </div>
        <div className="settings-field">
          <label>Base URL</label>
          <input type="text" className="settings-input"
            placeholder={isAnthropic ? 'https://api.anthropic.com' : 'https://api.openai.com/v1'} />
        </div>
        <div className="settings-field">
          <label>Модель</label>
          <input type="text" className="settings-input"
            placeholder={isAnthropic ? 'claude-sonnet-4' : 'gpt-4o'} />
        </div>
        <div className="settings-field">
          <label>API Key</label>
          <input type="password" className="settings-input" placeholder="sk-..." />
        </div>
      </div>
      <div className="modal-footer">
        <button className="settings-btn-secondary" onClick={onClose}>Отмена</button>
        <button className="settings-btn-primary" onClick={onClose}>Сохранить</button>
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
