import { useState, useEffect } from 'react'

interface SettingsPageProps {
  onBack: () => void
}

type Tab = 'agents' | 'general' | 'providers'

export function SettingsPage({ onBack }: SettingsPageProps) {
  const [activeTab, setActiveTab] = useState<Tab>('general')
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true))
  }, [])

  const handleBack = () => {
    setVisible(false)
    setTimeout(onBack, 300)
  }

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: 'general', label: 'Основное', icon: '⚙️' },
    { id: 'agents', label: 'Агенты', icon: '🤖' },
    { id: 'providers', label: 'Провайдеры', icon: '🔌' },
  ]

  return (
    <div className={`settings-page ${visible ? 'visible' : ''}`}>
      <div className="settings-header">
        <button className="settings-back-btn" onClick={handleBack}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          Назад
        </button>
        <h1 className="settings-title">Настройки</h1>
      </div>

      {/* Tab navigation */}
      <div className="settings-tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`settings-tab ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span className="tab-icon">{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="settings-body">
        {activeTab === 'general' && <GeneralSettings />}
        {activeTab === 'agents' && <AgentsSettings />}
        {activeTab === 'providers' && <ProvidersSettings />}
      </div>
    </div>
  )
}

// ─── General Settings ────────────────────────────────────────

function GeneralSettings() {
  return (
    <div className="settings-sections">
      {/* Server */}
      <section className="settings-card">
        <h2 className="settings-card-title">🖥 Сервер</h2>
        <div className="settings-field">
          <label>Порт API</label>
          <input type="number" className="settings-input" defaultValue={2088} />
        </div>
        <div className="settings-field">
          <label>Порт Dev (Vite)</label>
          <input type="number" className="settings-input" defaultValue={2099} />
        </div>
        <div className="settings-field">
          <label>Host</label>
          <input type="text" className="settings-input" defaultValue="0.0.0.0" />
        </div>
      </section>

      {/* UI */}
      <section className="settings-card">
        <h2 className="settings-card-title">🎨 Интерфейс</h2>
        <div className="settings-field">
          <label>Тема</label>
          <select className="settings-select" defaultValue="dark">
            <option value="dark">Тёмная</option>
            <option value="light" disabled>Светлая (скоро)</option>
          </select>
        </div>
        <div className="settings-field">
          <label>Язык</label>
          <select className="settings-select" defaultValue="ru">
            <option value="ru">Русский</option>
            <option value="en">English</option>
          </select>
        </div>
        <div className="settings-field-row">
          <label className="settings-toggle">
            <input type="checkbox" defaultChecked />
            <span>Показывать метаданные сообщений</span>
          </label>
        </div>
        <div className="settings-field-row">
          <label className="settings-toggle">
            <input type="checkbox" defaultChecked />
            <span>Анимированная обводка при стриминге</span>
          </label>
        </div>
        <div className="settings-field-row">
          <label className="settings-toggle">
            <input type="checkbox" defaultChecked />
            <span>Автоскролл к новым сообщениям</span>
          </label>
        </div>
      </section>

      {/* Feed */}
      <section className="settings-card">
        <h2 className="settings-card-title">📡 Лента активности</h2>
        <div className="settings-field">
          <label>Макс. записей</label>
          <input type="number" className="settings-input" defaultValue={50} />
        </div>
        <div className="settings-field">
          <label>Период</label>
          <select className="settings-select" defaultValue="24h">
            <option value="1h">1 час</option>
            <option value="6h">6 часов</option>
            <option value="24h">24 часа</option>
            <option value="7d">7 дней</option>
            <option value="30d">30 дней</option>
          </select>
        </div>
        <div className="settings-field-row">
          <label className="settings-toggle">
            <input type="checkbox" defaultChecked />
            <span>Новые идеи</span>
          </label>
        </div>
        <div className="settings-field-row">
          <label className="settings-toggle">
            <input type="checkbox" defaultChecked />
            <span>Обновления задач</span>
          </label>
        </div>
        <div className="settings-field-row">
          <label className="settings-toggle">
            <input type="checkbox" />
            <span>Обновления памяти</span>
          </label>
        </div>
      </section>
    </div>
  )
}

// ─── Agents Settings ─────────────────────────────────────────

const sampleAgents = [
  {
    id: 'architect',
    name: 'Архитектор',
    role: 'head',
    department: 'dev',
    model: 'general-agent',
    enabled: true,
    traits: 'analytical, thinks before answering',
  },
  {
    id: 'developer',
    name: 'Разработчик',
    role: 'worker',
    department: 'dev',
    model: 'general-agent',
    enabled: true,
    traits: 'pragmatic, writes clean code',
  },
  {
    id: 'qa-engineer',
    name: 'QA Инженер',
    role: 'worker',
    department: 'qa',
    model: 'general-agent',
    enabled: true,
    traits: 'meticulous, finds edge cases',
  },
]

function AgentsSettings() {
  const [agents] = useState(sampleAgents)

  const roleLabels: Record<string, string> = {
    worker: 'Работник',
    head: 'Руководитель',
    director: 'Директор',
  }

  const roleColors: Record<string, string> = {
    worker: '#6b7280',
    head: '#f59e0b',
    director: '#ef4444',
  }

  return (
    <div className="settings-sections">
      <div className="agents-header">
        <span className="agents-count">{agents.length} агентов</span>
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

// ─── Providers Settings ──────────────────────────────────────

const sampleProviders = [
  {
    id: '9router',
    name: '9Router',
    type: 'openai-compatible',
    baseUrl: 'http://localhost:20128/v1',
    model: 'general-agent',
    isDefault: true,
    connected: true,
  },
  {
    id: 'openai',
    name: 'OpenAI',
    type: 'openai',
    baseUrl: 'https://api.openai.com/v1',
    model: 'gpt-4o',
    isDefault: false,
    connected: false,
  },
  {
    id: 'anthropic',
    name: 'Anthropic',
    type: 'anthropic',
    baseUrl: 'https://api.anthropic.com',
    model: 'claude-sonnet-4',
    isDefault: false,
    connected: false,
  },
]

function ProvidersSettings() {
  const [providers] = useState(sampleProviders)

  return (
    <div className="settings-sections">
      <div className="providers-header">
        <span className="providers-count">{providers.filter(p => p.connected).length} подключено</span>
        <button className="settings-btn-primary">+ Добавить провайдер</button>
      </div>

      {providers.map(provider => (
        <div key={provider.id} className={`settings-card provider-card ${!provider.connected ? 'disconnected' : ''}`}>
          <div className="provider-header">
            <div className="provider-identity">
              <span className={`provider-status ${provider.connected ? 'connected' : 'disconnected'}`} />
              <span className="provider-name">{provider.name}</span>
              <span className="provider-type">{provider.type}</span>
            </div>
            {provider.isDefault && <span className="provider-badge">Default</span>}
          </div>

          {provider.connected ? (
            <div className="provider-details">
              <div className="settings-field">
                <label>Base URL</label>
                <input type="text" className="settings-input" defaultValue={provider.baseUrl} />
              </div>
              <div className="settings-field">
                <label>Модель по умолчанию</label>
                <input type="text" className="settings-input" defaultValue={provider.model} />
              </div>
              <div className="settings-field">
                <label>API Key</label>
                <input type="password" className="settings-input" defaultValue="sk-••••••••" />
              </div>
              <div className="provider-actions">
                <button className="settings-btn-secondary">Сохранить</button>
                {!provider.isDefault && <button className="settings-btn-danger">Отключить</button>}
              </div>
            </div>
          ) : (
            <div className="provider-connect">
              <p>Нажмите для подключения</p>
              <button className="settings-btn-primary">Подключить</button>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
