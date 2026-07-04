/**
 * Providers settings section — connected providers, catalog, test, modals.
 * Extracted from SettingsPage.tsx (lines 1747-2257, 2514-2678).
 */

import { useState, useEffect, useCallback, forwardRef, useImperativeHandle } from 'react'
import { API_BASE } from '../../config'
import { PROVIDER_CATALOG, providerKey, providerIconUrl, type ProviderInfo } from '../../lib/providers'
import { LoadingSpinner } from '../LoadingSpinner'
import { pluralize } from './types'
import type { ApiProvider } from './types'

// ── ProvidersSection ───────────────────────────────────────────────

export const ProvidersSection = forwardRef<{ refresh: () => void }, {
  onAddProvider: (type: 'openai' | 'anthropic') => void
  onAddFromCatalog: (p: ProviderInfo) => void
  onEditProvider: (p: ApiProvider) => void
}>(
  function ProvidersSection({ onAddProvider, onAddFromCatalog, onEditProvider }, ref) {
    const [connected, setConnected] = useState<ApiProvider[]>([])
    const [loading, setLoading] = useState(true)
    const [searchQuery, setSearchQuery] = useState('')
    const [testing, setTesting] = useState<string | null>(null)

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

    useEffect(() => { fetchProviders() }, [])

    useImperativeHandle(ref, () => ({ refresh: fetchProviders }), [fetchProviders])

    const handleDisconnect = async (name: string) => {
      try {
        const res = await fetch(`${API_BASE}/api/providers/${encodeURIComponent(name)}`, { method: 'DELETE' })
        if (res.ok) fetchProviders()
      } catch (e) { console.error('[providers] delete error:', e) }
    }

    const handleTest = async (conn: ApiProvider) => {
      setTesting(conn.name)
      try {
        const res = await fetch(`${API_BASE}/api/providers/${encodeURIComponent(conn.name)}/test`, { method: 'POST' })
        const data = await res.json()
        setConnected(prev => prev.map(c =>
          c.name === conn.name ? { ...c, _testStatus: data.status === 'ok' ? 'ok' as const : 'error' as const } : c
        ))
      } catch {
        setConnected(prev => prev.map(c =>
          c.name === conn.name ? { ...c, _testStatus: 'error' as const } : c
        ))
      } finally { setTesting(null) }
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

    return (
      <div className="providers-page">
        <div className="providers-top-actions">
          <button className="providers-add-btn anthropic" onClick={() => onAddProvider('anthropic')}>+ Add Anthropic Compatible</button>
          <button className="providers-add-btn openai" onClick={() => onAddProvider('openai')}>+ Add OpenAI Compatible</button>
        </div>

        {loading ? (
          <LoadingSpinner text="Загрузка провайдеров..." />
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
                  <div key={conn.name} className="connected-provider-card" onClick={() => onEditProvider(conn)}>
                    <div className="cp-icon-wrap">
                      {hasIcon ? (
                        <img src={iconUrl!} alt={displayName} className="cp-icon-img"
                          onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
                      ) : (
                        <svg className="cp-fallback-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
                        </svg>
                      )}
                    </div>
                    <div className="cp-info">
                      <span className="cp-name">{displayName}</span>
                      {conn.models.length > 0 && <span className="cp-models">{conn.models.join(', ')}</span>}
                    </div>
                    {conn._testStatus === 'ok' && (
                      <svg className="cp-test-result ok" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
                        onClick={e => { e.stopPropagation(); handleTest(conn) }} aria-label="Тест подключения">
                        <path d="M22 4L12 14.01l-3-3" />
                      </svg>
                    )}
                    {conn._testStatus === 'error' && (
                      <svg className="cp-test-result error" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
                        onClick={e => { e.stopPropagation(); handleTest(conn) }} aria-label="Тест подключения">
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
                        onClick={e => { e.stopPropagation(); handleTest(conn) }} aria-label="Тест подключения">
                        <path d="M22 11.08V12a10 10 0 11-5.9-9.1" />
                        <path d="M22 4L12 14.01l-3-3" />
                      </svg>
                    )}
                    <button className="cp-disconnect-btn" onClick={e => { e.stopPropagation(); handleDisconnect(conn.name) }} title="Отключить">
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

        <div className="providers-search-bar">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
          </svg>
          <input type="text" className="providers-search-input" placeholder="Поиск провайдеров..."
            value={searchQuery} onChange={e => setSearchQuery(e.target.value)} />
        </div>

        {groupedCatalog.oauth.length > 0 && <ProviderGridSection title="OAuth Providers" providers={groupedCatalog.oauth} onConnect={p => onAddFromCatalog(p)} />}
        {groupedCatalog.freeTier.length > 0 && <ProviderGridSection title="Free Tier Providers" providers={groupedCatalog.freeTier} onConnect={p => onAddFromCatalog(p)} />}
        {groupedCatalog.apiKey.length > 0 && <ProviderGridSection title="API Key Providers" providers={groupedCatalog.apiKey} onConnect={p => onAddFromCatalog(p)} />}
      </div>
    )
  }
)

// ── ProviderGridSection ────────────────────────────────────────────

function ProviderGridSection({ title, providers, onConnect }: { title: string; providers: ProviderInfo[]; onConnect: (p: ProviderInfo) => void }) {
  return (
    <section className="providers-section">
      <h2 className="providers-section-title">{title}</h2>
      <div className="provider-catalog-grid">
        {providers.map(provider => {
          const iconUrl = providerIconUrl(provider)
          const isOAuthDisabled = provider.oauthDisabled
          return (
            <button key={provider.id} className={`provider-catalog-card${isOAuthDisabled ? ' oauth-disabled' : ''}`}
              onClick={() => !isOAuthDisabled && onConnect(provider)} title={isOAuthDisabled ? 'OAuth подключение скоро' : provider.name}>
              <div className="pc-icon-wrap">
                {iconUrl ? <img src={iconUrl} alt={provider.name} className="pc-icon-img" onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} /> : null}
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

// ── AddFromCatalogModal ────────────────────────────────────────────

export function AddFromCatalogModal({ provider, editProvider, onClose, onSaved }: {
  provider: ProviderInfo
  editProvider?: ApiProvider
  onClose: () => void
  onSaved: () => void
}) {
  const key = providerKey(provider)
  const isNoAuth = provider.authMethod === 'no-auth'
  const isEdit = !!editProvider
  // Always start with empty input. The '••••••••' sentinel pattern was
  // dangerous: any keystroke (even just clicking into the field) would
  // replace the sentinel and cause Save to send the new value as the
  // api_key, potentially overwriting the existing real key. Backend
  // accepts an empty/missing api_key as "do not change" (see
  // core/synpin/api/providers_router.py — api_key updates only when
  // req.api_key is non-null and non-empty), so a blank input is safe.
  const [apiKey, setApiKey] = useState('')
  const [modelsInput, setModelsInput] = useState(
    isEdit ? editProvider!.models.join(', ') : (provider.defaultModels || []).join(', ')
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<'ok' | 'error' | null>(null)
  const [testMessage, setTestMessage] = useState('')
  const [fetchedModels, setFetchedModels] = useState<string[]>([])

  const parseModels = () => modelsInput.split(',').map(m => m.trim()).filter(Boolean)

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

  const handleTest = async () => {
    setTesting(true); setTestResult(null); setTestMessage(''); setError(''); setFetchedModels([])
    const modelList = parseModels()

    const tryTest = async (useKey: boolean): Promise<{ status: string; message?: string; models?: string[] }> => {
      const tempName = key + '-test-temp'
      const body: Record<string, unknown> = {
        name: tempName, type: provider.type, base_url: provider.baseUrl,
        api_key: useKey ? apiKey : '', models: modelList,
      }
      await fetch(`${API_BASE}/api/providers`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      try {
        const res = await fetch(`${API_BASE}/api/providers/${encodeURIComponent(tempName)}/test`, { method: 'POST' })
        const text = await res.text()
        try { return JSON.parse(text) } catch { return { status: 'error', message: `Сервер вернул не JSON: ${text.slice(0, 100)}` } }
      } finally {
        await fetch(`${API_BASE}/api/providers/${encodeURIComponent(tempName)}`, { method: 'DELETE' }).catch(() => {})
      }
    }

    try {
      if (isNoAuth || !apiKey.trim()) {
        const result = await tryTest(false)
        setTestResult(result.status === 'ok' ? 'ok' : 'error')
        setTestMessage(result.message || '')
        if (result.status === 'ok' && result.models) setFetchedModels(result.models)
      } else {
        let result = await tryTest(true)
        if (result.status === 'ok') {
          setTestResult('ok'); setTestMessage(result.message || '')
          if (result.models) setFetchedModels(result.models)
        } else {
          result = await tryTest(false)
          if (result.status === 'ok') {
            setTestResult('ok'); setTestMessage(result.message + ' (работает без ключа)')
            if (result.models) setFetchedModels(result.models)
          } else {
            setTestResult('error'); setTestMessage(result.message || 'Не удалось подключиться')
          }
        }
      }
    } catch { setTestResult('error'); setTestMessage('Ошибка сети') } finally { setTesting(false) }
  }

  const handleSave = async () => {
    setSaving(true); setError('')
    try {
      const body: Record<string, unknown> = {
        ...(isEdit ? {} : { name: key }),
        type: provider.type, base_url: provider.baseUrl,
        api_key: isNoAuth ? '' : apiKey,
        models: parseModels(),
      }
      const res = await fetch(
        isEdit ? `${API_BASE}/api/providers/${encodeURIComponent(editProvider!.name)}` : `${API_BASE}/api/providers`,
        { method: isEdit ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
      )
      if (res.ok) { onSaved() } else { const data = await res.json().catch(() => ({})); setError(data.detail || 'Ошибка сохранения') }
    } catch { setError('Не удалось подключиться к серверу') } finally { setSaving(false) }
  }

  const iconUrl = providerIconUrl(provider)

  return (
    <div className="modal-inner">
      <div className="catalog-modal-header">
        <div className="catalog-modal-icon">
          {iconUrl ? <img src={iconUrl} alt={provider.name} className="catalog-modal-icon-img" /> : (
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" /></svg>
          )}
        </div>
        <div className="catalog-modal-title-wrap">
          <h2 className="modal-title">{isEdit ? 'Редактировать' : provider.name}</h2>
          <span className="catalog-modal-url">{provider.baseUrl}</span>
        </div>
      </div>
      <div className="modal-body">
        {!isNoAuth && (
          <div className="settings-field">
            <label>API Key <span className="field-hint">{isEdit ? '(оставьте пустым, чтобы не менять)' : '(необязательно — если не знаешь, оставь пустым)'}</span></label>
            <input type="password" className="settings-input" placeholder={isEdit ? 'оставьте пустым, чтобы не менять' : (provider.apiKeyHint || 'sk-...')} value={apiKey} onChange={e => setApiKey(e.target.value)} />
          </div>
        )}
        {isNoAuth && <div className="catalog-modal-info"><span>🔓 Этот провайдер работает без API ключа</span></div>}
        <div className="catalog-modal-test-row">
          <button className="catalog-modal-test-btn" onClick={handleTest} disabled={testing}>
            {testing ? 'Тестирование...' : 'Тест подключения'}
          </button>
          {testResult === 'ok' && <span className="catalog-test-badge ok">✓ {testMessage}</span>}
          {testResult === 'error' && <span className="catalog-test-badge error">✗ {testMessage}</span>}
        </div>
        <div className="settings-field">
          <label>Модели <span className="field-hint">(через запятую)</span></label>
          <input type="text" className="settings-input models-input" value={modelsInput} onChange={e => setModelsInput(e.target.value)} placeholder="gpt-4o, gpt-4o-mini" />
        </div>
        {chipModels.length > 0 && (
          <div className="model-chips-container">
            {chipModels.map(model => {
              const isActive = currentModels.includes(model)
              const isKnown = allKnownModels.includes(model)
              return (
                <button key={model} className={`model-chip${isActive ? ' active' : ''}${!isKnown ? ' custom' : ''}`}
                  onClick={() => toggleModel(model)} type="button">
                  {model}{!isKnown && <span className="chip-remove">×</span>}
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

// ── AddProviderModal ───────────────────────────────────────────────

export function AddProviderModal({ type, onClose, onSaved }: { type: 'openai' | 'anthropic'; onClose: () => void; onSaved: () => void }) {
  const isAnthropic = type === 'anthropic'
  const [name, setName] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSave = async () => {
    if (!name.trim()) { setError('Название обязательно'); return }
    setSaving(true); setError('')
    try {
      const slug = name.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')
      const body: Record<string, unknown> = {
        name: slug, type: isAnthropic ? 'anthropic' : 'openai-compatible',
        base_url: baseUrl, api_key: apiKey, models: model ? [model] : [],
      }
      const res = await fetch(`${API_BASE}/api/providers`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      if (res.ok) { onSaved() } else { const data = await res.json().catch(() => ({})); setError(data.detail || 'Ошибка сохранения') }
    } catch { setError('Не удалось подключиться к серверу') } finally { setSaving(false) }
  }

  return (
    <div className="modal-inner">
      <h2 className="modal-title">{isAnthropic ? 'Add Anthropic Compatible' : 'Add OpenAI Compatible'}</h2>
      <p className="modal-subtitle">{isAnthropic ? 'Подключите провайдер, совместимый с Anthropic API' : 'Подключите провайдер, совместимый с OpenAI API'}</p>
      <div className="modal-body">
        <div className="settings-field"><label>Название</label><input type="text" className="settings-input" placeholder="my-provider" value={name} onChange={e => setName(e.target.value)} /></div>
        <div className="settings-field"><label>Base URL</label><input type="text" className="settings-input" placeholder={isAnthropic ? 'https://api.anthropic.com' : 'https://api.openai.com/v1'} value={baseUrl} onChange={e => setBaseUrl(e.target.value)} /></div>
        <div className="settings-field"><label>Модель</label><input type="text" className="settings-input" placeholder={isAnthropic ? 'claude-sonnet-4' : 'gpt-4o'} value={model} onChange={e => setModel(e.target.value)} /></div>
        <div className="settings-field"><label>API Key</label><input type="password" className="settings-input" placeholder="sk-..." value={apiKey} onChange={e => setApiKey(e.target.value)} /></div>
        {error && <div className="modal-error">{error}</div>}
      </div>
      <div className="modal-footer">
        <button className="settings-btn-secondary" onClick={onClose}>Отмена</button>
        <button className="settings-btn-primary" onClick={handleSave} disabled={saving}>{saving ? 'Сохранение...' : 'Сохранить'}</button>
      </div>
    </div>
  )
}

// ── EditCustomProviderModal ────────────────────────────────────────

export function EditCustomProviderModal({ provider, onClose, onSaved }: { provider: ApiProvider; onClose: () => void; onSaved: () => void }) {
  const [name] = useState(provider.name)
  const [baseUrl, setBaseUrl] = useState(provider.base_url)
  const [model, setModel] = useState(provider.models.join(', '))
  const [apiKey, setApiKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSave = async () => {
    if (!name.trim()) { setError('Название обязательно'); return }
    setSaving(true); setError('')
    try {
      const models = model.split(',').map(m => m.trim()).filter(Boolean)
      const body: Record<string, unknown> = { type: provider.type, base_url: baseUrl, api_key: apiKey || undefined, models }
      const res = await fetch(`${API_BASE}/api/providers/${encodeURIComponent(provider.name)}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      if (res.ok) { onSaved() } else { const data = await res.json().catch(() => ({})); setError(data.detail || 'Ошибка сохранения') }
    } catch { setError('Не удалось подключиться к серверу') } finally { setSaving(false) }
  }

  return (
    <div className="modal-inner">
      <h2 className="modal-title">Редактировать провайдер</h2>
      <p className="modal-subtitle">{provider.type}</p>
      <div className="modal-body">
        <div className="settings-field"><label>Название</label><input type="text" className="settings-input" value={name} disabled /></div>
        <div className="settings-field"><label>Base URL</label><input type="text" className="settings-input" value={baseUrl} onChange={e => setBaseUrl(e.target.value)} /></div>
        <div className="settings-field"><label>Модели (через запятую)</label><input type="text" className="settings-input" value={model} onChange={e => setModel(e.target.value)} /></div>
        <div className="settings-field"><label>API Key (оставь пустым без изменений)</label><input type="password" className="settings-input" placeholder="sk-..." value={apiKey} onChange={e => setApiKey(e.target.value)} /></div>
        {error && <div className="modal-error">{error}</div>}
      </div>
      <div className="modal-footer">
        <button className="settings-btn-secondary" onClick={onClose}>Отмена</button>
        <button className="settings-btn-primary" onClick={handleSave} disabled={saving}>{saving ? 'Сохранение...' : 'Сохранить'}</button>
      </div>
    </div>
  )
}
