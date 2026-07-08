/**
 * General settings section — server, UI, themes, models, feed.
 * Extracted from SettingsPage.tsx (lines 270-820).
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { API_BASE } from '../../config'
import { SettingsCard } from '../SettingsCard'
import { DropdownMenu as CustomDropdown } from '../DropdownMenu'
import { LoadingSpinner } from '../LoadingSpinner'
import { Toggle } from './Toggle'
import type { SettingsData, OverviewStats } from './types'

// ── Autopilot Block (max_iterations) ────────────────────────────────────────
function AutopilotBlock() {
  const [maxIterations, setMaxIterations] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/protocol/settings`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setMaxIterations(typeof data.max_iterations === 'number' ? data.max_iterations : 15)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => { load() }, [load])

  const persist = useCallback((patch: Record<string, unknown>) => {
    return fetch(`${API_BASE}/api/protocol/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    }).then(r => {
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      return r.json()
    }).catch(e => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  const onMaxChange = (raw: number) => {
    if (Number.isNaN(raw)) return
    const next = Math.max(1, Math.min(50, Math.floor(raw)))
    setMaxIterations(next)
    void persist({ max_iterations: next })
  }

  const loading = maxIterations === null

  return (
    <SettingsCard title="Автопилот">
      <p className="settings-hint">
        Настройки автопилота — глобальный лимит итераций для всех отделов.
      </p>
      <div className="settings-divider-thin" />
      {loading ? (
        <LoadingSpinner text="Загрузка..." />
      ) : (
        <>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12 }}>
            <label
              htmlFor="autopilot-max-iterations"
              style={{ color: 'var(--text-secondary)', fontSize: 13, whiteSpace: 'nowrap' }}
            >
              Максимум итераций
            </label>
            <input
              id="autopilot-max-iterations"
              type="number"
              min={1}
              max={50}
              className="settings-input"
              value={maxIterations!}
              onChange={(e) => onMaxChange(Number(e.target.value))}
              style={{ width: 60, padding: '4px 6px', fontSize: 13 }}
            />
            <span style={{ color: 'var(--gray-500)', fontSize: 12 }}>
              (1–50, по умолчанию: 15)
            </span>
          </div>
          <p className="settings-hint" style={{ marginTop: 6, marginLeft: 0 }}>
            Сколько раундов делегирования может пройти отдел за одно задание
          </p>
          {error && (
            <div style={{ color: 'var(--red, #f87171)', fontSize: 12, marginTop: 8 }}>
              {error}
            </div>
          )}
        </>
      )}
    </SettingsCard>
  )
}

export function GeneralSection() {
  const [settings, setSettings] = useState<SettingsData | null>(null)
  const [overview, setOverview] = useState<OverviewStats | null>(null)
  const [systemInfo, setSystemInfo] = useState<Record<string, unknown> | null>(null)
  const [availableModels, setAvailableModels] = useState<{ provider: string; model: string }[]>([])
  const [customThemes, setCustomThemes] = useState<{ id: string; name: string; source_url: string; dark?: Record<string, string>; light?: Record<string, string>; raw?: { light: Record<string, string>; dark: Record<string, string> } }[]>([])
  const [tweakcnUrl, setTweakcnUrl] = useState('')
  const [tweakcnLoading, setTweakcnLoading] = useState(false)
  const [tweakcnError, setTweakcnError] = useState('')
  const [tweakcnSuccess, setTweakcnSuccess] = useState('')
  const [webSearchProviders, setWebSearchProviders] = useState<Record<string, { enabled: boolean; api_key: string; search_engine_id?: string }>>({})
  const [editingProvider, setEditingProvider] = useState<string | null>(null)
  const [providerApiKey, setProviderApiKey] = useState('')
  const [providerCx, setProviderCx] = useState('')
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/config/settings`).then(r => r.ok ? r.json() : null).then(data => { if (data) setSettings(data) }).catch((e) => console.error('[general] load settings failed:', e))
  }, [])

  useEffect(() => {
    fetch(`${API_BASE}/api/providers`).then(r => r.ok ? r.json() : null).then(data => {
      if (data?.providers) {
        const models: { provider: string; model: string }[] = []
        for (const p of data.providers) { for (const m of (p.models || [])) { models.push({ provider: p.name, model: m }) } }
        setAvailableModels(models)
      }
    }).catch((e) => console.error('[general] save settings failed:', e))
  }, [])

  useEffect(() => {
    fetch(`${API_BASE}/api/stats/overview`).then(r => r.ok ? r.json() : null).then(data => { if (data) setOverview(data) }).catch((e) => console.error('[general] load stats failed:', e))
  }, [])

  useEffect(() => {
    fetch(`${API_BASE}/api/stats/system`).then(r => r.ok ? r.json() : null).then(data => { if (data && !data.error) setSystemInfo(data) }).catch((e) => console.error('[general] save settings failed:', e))
  }, [])

  useEffect(() => {
    fetch(`${API_BASE}/api/themes/tweakcn/list`).then(r => r.ok ? r.json() : null).then(data => { if (data?.themes) setCustomThemes(data.themes) }).catch((e) => console.error('[general] save settings failed:', e))
  }, [])

  useEffect(() => {
    fetch(`${API_BASE}/api/config/web-search`).then(r => r.ok ? r.json() : null).then(data => { if (data?.providers) setWebSearchProviders(data.providers) }).catch((e) => console.error('[general] save settings failed:', e))
  }, [])

  const tweakcnVarsRef = useRef<Record<string, string> | null>(null)

  const applyThemeLocally = useCallback(async (theme: string, cnThemes?: typeof customThemes, directVars?: Record<string, string>) => {
    const root = document.documentElement
    root.classList.remove('light-theme', 'dark-theme', 'oled-theme')

    // Snapshot user's border_radius BEFORE clearing inline vars.
    // After theme apply we restore it — unless a TweakCN preset
    // explicitly defines --radius in its vars (in which case the
    // designer-chosen radius wins).
    const userRadius = settings?.ui?.border_radius

    const existingVars = root.style
    for (let i = existingVars.length - 1; i >= 0; i--) {
      const prop = existingVars[i]
      if (prop && prop.startsWith('--')) { root.style.removeProperty(prop) }
    }

    const themeCache: { name: string; vars?: Record<string, string> } = { name: theme }

    if (theme === 'dark') {
      // Default dark
    } else if (theme === 'dark-oled') {
      root.classList.add('oled-theme')
    } else if (theme === 'light') {
      root.classList.add('light-theme')
    } else if (theme === 'tweakcn') {
      root.classList.add('dark-theme')
      let vars = directVars
      if (!vars) {
        const themes = cnThemes || customThemes
        const current = themes.find(t => t.id === 'current') || themes[0]
        if (current) vars = current.dark || current.light
      }
      if (!vars && tweakcnVarsRef.current) { vars = tweakcnVarsRef.current }
      if (!vars) {
        try {
          const res = await fetch(`${API_BASE}/api/themes/tweakcn/list`)
          if (res.ok) { const data = await res.json(); const saved = data?.themes?.[0]; if (saved) vars = saved.dark || saved.light }
        } catch {}
      }
      if (vars) {
        Object.entries(vars).forEach(([key, value]) => { root.style.setProperty(key, value as string) })
        themeCache.vars = vars as Record<string, string>
        tweakcnVarsRef.current = vars as Record<string, string>
      }
    }

    // Restore user's border_radius — unless a TweakCN preset
    // explicitly defined it. We check tweakcnVarsRef directly because
    // after removeProperty the CSS fallback (8px) would always win
    // and we'd never restore the user's value.
    const isTweakcn = theme === 'tweakcn'
    const tweakcnVars = tweakcnVarsRef.current
    const presetHasRadius = isTweakcn && !!tweakcnVars && '--radius' in tweakcnVars
    if (userRadius && !presetHasRadius) {
      root.style.setProperty('--radius', `${userRadius}px`)
    }

    localStorage.setItem('synpin_theme', JSON.stringify(themeCache))
  }, [customThemes, settings])

  const saveSettings = useCallback((patch: Partial<SettingsData>) => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(async () => {
      try {
        await fetch(`${API_BASE}/api/config/settings`, {
          method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(patch),
        })
      } catch {}
    }, 400)
  }, [])

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
        ;(ui as Record<string, unknown>)[path] = value
      }
      if (path === 'theme') { applyThemeLocally(value as string) }
      return { ...prev, ui }
    })
    const parts = path.split('.')
    if (parts.length === 1) {
      saveSettings({ ui: { [path]: value } } as unknown as Partial<SettingsData>)
    } else {
      const key0 = parts[0]!
      const key1 = parts[1]!
      saveSettings({ ui: { [key0]: { [key1]: value } } } as unknown as Partial<SettingsData>)
    }
  }, [saveSettings, applyThemeLocally])

  const updateModels = useCallback((key: string, value: string) => {
    setSettings(prev => prev ? { ...prev, models: { ...prev.models, [key]: value } } : prev)
    saveSettings({ models: { [key]: value } } as unknown as Partial<SettingsData>)
  }, [saveSettings])

  const updateFeed = useCallback((key: string, value: string | number | boolean) => {
    setSettings(prev => {
      if (!prev) return prev
      const feed = { ...prev.feed }
      if (key.startsWith('filters.')) {
        const fkey = key.slice(8) as keyof typeof feed.filters
        feed.filters = { ...feed.filters, [fkey]: value as boolean }
      } else {
        ;(feed as Record<string, unknown>)[key] = value
      }
      return { ...prev, feed }
    })
    if (key.startsWith('filters.')) {
      saveSettings({ feed: { filters: { [key.slice(8)]: value } } } as unknown as Partial<SettingsData>)
    } else {
      saveSettings({ feed: { [key]: value } } as unknown as Partial<SettingsData>)
    }
  }, [saveSettings])



  const saveWebSearchProvider = useCallback(async (provider: string, data: { enabled?: boolean; api_key?: string; search_engine_id?: string }) => {
    try {
      const res = await fetch(`${API_BASE}/api/config/web-search`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, ...data }),
      })
      if (res.ok) {
        await res.json()
        setWebSearchProviders(prev => ({
          ...prev,
          [provider]: { ...prev[provider], ...data },
        } as Record<string, { enabled: boolean; api_key: string; search_engine_id?: string }>))
      }
    } catch (e) {
      console.error('[web-search] save error:', e)
    }
  }, [])

  const handleTweakcnImport = useCallback(async () => {
    if (!tweakcnUrl.trim()) return
    setTweakcnLoading(true); setTweakcnError(''); setTweakcnSuccess('')
    try {
      const res = await fetch(`${API_BASE}/api/themes/tweakcn/import`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: tweakcnUrl.trim() }),
      })
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail || 'Failed to import theme') }
      const data = await res.json()
      const saveRes = await fetch(`${API_BASE}/api/themes/tweakcn/save`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: 'current', name: data.name, url: data.source_url, light: data.light, dark: data.dark, raw: data.raw }),
      })
      if (!saveRes.ok) throw new Error('Failed to save theme')
      applyThemeLocally('tweakcn', [{ id: 'current', name: data.name, dark: data.dark, light: data.light } as Record<string, unknown> as typeof customThemes[number]])
      const listRes = await fetch(`${API_BASE}/api/themes/tweakcn/list`)
      if (listRes.ok) { const listData = await listRes.json(); if (listData?.themes) setCustomThemes(listData.themes) }
      setTweakcnSuccess(`Тема "${data.name}" загружена и применена!`)
      setTweakcnUrl('')
      setTimeout(() => setTweakcnSuccess(''), 3000)
    } catch (err: unknown) {
      setTweakcnError((err as Error).message || 'Ошибка при загрузке темы')
    } finally { setTweakcnLoading(false) }
  }, [tweakcnUrl, applyThemeLocally])

  if (!settings) { return <LoadingSpinner text="Загрузка..." /> }

  return (
    <div className="general-settings">
            <SettingsCard title="Обзор системы">
        <div className="stats-summary">
          <div className="stats-card">
            <span className="stats-card-value">{overview?.agents ?? '—'}</span>
            <span className="stats-card-label">Агентов</span>
            <span className="stats-card-detail">{overview?.agents_internal ?? 0} внутр. + {overview?.agents_external ?? 0} внешн.</span>
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
      </SettingsCard>

            {systemInfo && (
        <SettingsCard title="Информация о системе">
          <div className="stats-summary">
            <div className="stats-card">
              <span className="stats-card-value">{(systemInfo.synpin_version as string) ?? '—'}</span>
              <span className="stats-card-label">SynPin</span>
              <span className="stats-card-detail">версия</span>
            </div>
            <div className="stats-card">
              <span className="stats-card-value">{(systemInfo.hostname as string) ?? '—'}</span>
              <span className="stats-card-label">Хост</span>
              <span className="stats-card-detail">{(systemInfo.platform as string) ?? ''}</span>
            </div>
            <div className="stats-card">
              <span className="stats-card-value">{Array.isArray(systemInfo.ip_addresses) ? (systemInfo.ip_addresses as string[])[0] ?? '—' : '—'}</span>
              <span className="stats-card-label">IP адрес</span>
              <span className="stats-card-detail">Python {String(systemInfo.python_version ?? '')}</span>
            </div>
            <div className="stats-card">
              <span className="stats-card-value">{(() => { const t = systemInfo.time as Record<string, string> | undefined; return t?.time ?? '—' })()}</span>
              <span className="stats-card-label">{(() => { const t = systemInfo.time as Record<string, string> | undefined; return t?.weekday ?? '' })()}</span>
              <span className="stats-card-detail">{(() => { const t = systemInfo.time as Record<string, string> | undefined; return t?.timezone ?? '' })()}</span>
            </div>
          </div>
        </SettingsCard>
      )}

      <SettingsCard title="Интерфейс">
          <div className="settings-row-2">
            <div className="settings-field">
              <label>Тема</label>
              <CustomDropdown value={settings.ui.theme} onChange={v => updateUI('theme', v)} options={[
                { value: 'dark', label: 'Тёмная' }, { value: 'dark-oled', label: 'Тёмная (OLED)' },
                { value: 'light', label: 'Светлая' }, { value: 'tweakcn', label: 'TweakCN' },
              ]} />
            </div>
            <div className="settings-field" style={{ opacity: 0.5 }}>
              <label>Язык <span style={{ fontSize: '10px', color: 'var(--text-dim)' }}>🚧 скоро</span></label>
              <CustomDropdown value={settings.ui.language} onChange={() => {}} options={[
                { value: 'ru', label: 'Русский' }, { value: 'en', label: 'English' },
              ]} disabled />
            </div>
            </div>
            <div className="settings-divider-thin" />
            <div className="settings-field">
            <label>Скругление углов: <span style={{ color: 'var(--accent)', fontWeight: 600 }}>{settings.ui.border_radius ?? 8}px</span></label>
            <div className="radius-slider-row">
              <span className="radius-label">1px</span>
              <input type="range" min={1} max={20} value={settings.ui.border_radius ?? 8}
                onChange={e => { const val = parseInt(e.target.value); updateUI('border_radius', val); document.documentElement.style.setProperty('--radius', `${val}px`) }}
                className="radius-slider" />
              <span className="radius-label">20px</span>
            </div>
            </div>
            {settings.ui.theme === 'tweakcn' && (
            <div className="tweakcn-section">
              <div className="settings-divider-thin" />
              <h3 className="settings-subsection-title">TweakCN Theme</h3>
              <div className="tweakcn-input-row">
                <input type="text" className="settings-input" placeholder="https://tweakcn.com/themes/..."
                  value={tweakcnUrl} onChange={e => setTweakcnUrl(e.target.value)} disabled={tweakcnLoading} />
                <button className="settings-btn-primary" onClick={handleTweakcnImport} disabled={tweakcnLoading || !tweakcnUrl.trim()}>
                  {tweakcnLoading ? 'Загрузка...' : 'Сохранить'}
                </button>
              </div>
              {tweakcnError && <div className="tweakcn-error">{tweakcnError}</div>}
              {tweakcnSuccess && <div className="tweakcn-success">{tweakcnSuccess}</div>}
              {customThemes.length > 0 && customThemes[0] && (
                <div className="tweakcn-saved-info"><span className="tweakcn-saved-label">Текущая тема: {customThemes[0].name}</span></div>
              )}
            </div>
          )}
        </SettingsCard>

                <AutopilotBlock />

                <div className="settings-row-2">
        <SettingsCard title="Настройка моделей" description="Модели для специализированных задач">
          <div className="settings-field">
            <label>Визион (анализ изображений)</label>
            <CustomDropdown value={settings.models?.vision || ''} onChange={v => updateModels('vision', v)} searchable
              options={[{ value: '', label: 'Не настроено' }, ...availableModels.map(m => ({ value: `${m.provider}/${m.model}`, label: `${m.model} (${m.provider})` }))]} />
          </div>
          <div className="settings-field" style={{ opacity: 0.5, pointerEvents: 'none' }}>
            <label>Генерация изображений <span style={{ fontSize: 10, color: 'var(--text-dim)', marginLeft: 6 }}>Скоро</span></label>
            <CustomDropdown value="" onChange={() => {}} searchable
              options={[{ value: '', label: 'Не настроено' }]} disabled />
          </div>
          <div className="settings-field">
            <label>Веб-поиск</label>
            <CustomDropdown
              value={settings.models?.web_search || ''}
              onChange={v => updateModels('web_search', v)}
              searchable
              options={[
                { value: '', label: 'DuckDuckGo (бесплатно)' },
                ...Object.entries(webSearchProviders)
                  .filter(([name, cfg]) => name !== 'duckduckgo' && cfg.enabled && cfg.api_key)
                  .map(([name]) => ({ value: name, label: name.charAt(0).toUpperCase() + name.slice(1) })),
              ]}
            />
            <span className="settings-field-hint" style={{ fontSize: 11, color: 'var(--text-dim)' }}>
              DuckDuckGo доступен всегда. Другие провайдеры — в блоке ниже.
            </span>
          </div>
          <div className="settings-field" style={{ opacity: 0.5, pointerEvents: 'none' }}>
            <label>Веб-экстракт <span style={{ fontSize: 10, color: 'var(--text-dim)', marginLeft: 6 }}>Скоро</span></label>
            <CustomDropdown value="" onChange={() => {}} searchable
              options={[{ value: '', label: 'Не настроено' }]} disabled />
          </div>
          <div className="settings-field">
            <label>Суммаризация</label>
            <CustomDropdown value={settings.models?.summarization || ''} onChange={v => updateModels('summarization', v)} searchable
              options={[{ value: '', label: 'Не настроено' }, ...availableModels.map(m => ({ value: `${m.provider}/${m.model}`, label: `${m.model} (${m.provider})` }))]} />
          </div>
        </SettingsCard>

        <SettingsCard title="Провайдеры поиска">
          {[
            { name: 'tavily', label: 'Tavily', hint: '1000 запросов/мес бесплатно', needsKey: true },
            { name: 'perplexity', label: 'Perplexity', hint: 'AI-поиск с цитатами', needsKey: true },
            { name: 'exa', label: 'EXA', hint: '1000 запросов/мес, AI-оптимизированный', needsKey: true },
            { name: 'bing', label: 'Bing Search', hint: '~1000 запросов/мес бесплатно', needsKey: true },
            { name: 'serpapi', label: 'SerpAPI', hint: '250 запросов/мес бесплатно', needsKey: true },
            { name: 'google', label: 'Google CSE', hint: '100 запросов/день', needsKey: true, hasCx: true },
          ].map(p => (
            <div key={p.name} className="settings-field-row" style={{ borderBottom: '1px solid var(--border)', paddingBottom: 12, marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1 }}>
                <label className="settings-toggle">
                  <input
                    type="checkbox"
                    checked={webSearchProviders[p.name]?.enabled || false}
                    onChange={e => saveWebSearchProvider(p.name, { enabled: e.target.checked })}
                  />
                  <span>{p.label}</span>
                </label>
                <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>{p.hint}</span>
              </div>
              {webSearchProviders[p.name]?.enabled && (
                <div style={{ display: 'flex', gap: 8, marginTop: 8, width: '100%' }}>
                  <input
                    type="password"
                    className="settings-input"
                    placeholder={p.name === 'google' ? 'API Key' : 'API Key'}
                    value={editingProvider === p.name ? providerApiKey : (webSearchProviders[p.name]?.api_key ? '••••••••' : '')}
                    onFocus={() => { setEditingProvider(p.name); setProviderApiKey(''); setProviderCx(webSearchProviders[p.name]?.search_engine_id || '') }}
                    onBlur={() => setTimeout(() => setEditingProvider(null), 200)}
                    onChange={e => setProviderApiKey(e.target.value)}
                    style={{ flex: 1 }}
                  />
                  {p.hasCx && editingProvider === p.name && (
                    <input
                      type="text"
                      className="settings-input"
                      placeholder="Search Engine ID (CX)"
                      value={providerCx}
                      onChange={e => setProviderCx(e.target.value)}
                      style={{ flex: 1 }}
                    />
                  )}
                  {editingProvider === p.name && providerApiKey && (
                    <button
                      className="settings-btn-primary"
                      onClick={() => {
                        saveWebSearchProvider(p.name, {
                          api_key: providerApiKey,
                          ...(p.hasCx ? { search_engine_id: providerCx } : {}),
                        })
                        setEditingProvider(null)
                      }}
                    >
                      Сохранить
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </SettingsCard>
        </div>

      <SettingsCard title="Лента активности" badge="скоро" disabled>
        <div className="settings-row-2">
          <div className="settings-field">
            <label>Макс. записей</label>
            <input type="number" className="settings-input" value={settings.feed.max_items} onChange={e => updateFeed('max_items', parseInt(e.target.value) || 50)} />
          </div>
          <div className="settings-field">
            <label>Период</label>
            <CustomDropdown value={settings.feed.time_range} onChange={v => updateFeed('time_range', v)} options={[
              { value: '1h', label: '1 час' }, { value: '6h', label: '6 часов' }, { value: '24h', label: '24 часа' },
              { value: '7d', label: '7 дней' }, { value: '30d', label: '30 дней' },
            ]} />
          </div>
        </div>
        <Toggle label="Лента включена" checked={settings.feed.enabled} onChange={v => updateFeed('enabled', v)} />
        <div className="settings-divider-thin" />
        <h3 className="settings-subsection-title">Фильтры</h3>
        <Toggle label="Новые идеи" checked={settings.feed.filters.new_ideas} onChange={v => updateFeed('filters.new_ideas', v)} />
        <Toggle label="Обновления задач" checked={settings.feed.filters.task_updates} onChange={v => updateFeed('filters.task_updates', v)} />
        <Toggle label="Обновления памяти" checked={settings.feed.filters.memory_updates} onChange={v => updateFeed('filters.memory_updates', v)} />
        <Toggle label="Обновления канбана" checked={settings.feed.filters.board_updates} onChange={v => updateFeed('filters.board_updates', v)} />
        <div className="settings-divider-thin" />
        <div className="settings-row-2">
          <div className="settings-field">
            <label>Сортировка</label>
            <CustomDropdown value={settings.feed.sort} onChange={v => updateFeed('sort', v)} options={[
              { value: 'newest', label: 'Сначала новые' }, { value: 'oldest', label: 'Сначала старые' },
            ]} />
          </div>
          <div className="settings-field">
            <label>Группировка</label>
            <CustomDropdown value={settings.feed.group_by} onChange={v => updateFeed('group_by', v)} options={[
              { value: 'none', label: 'Без группировки' }, { value: 'department', label: 'По отделу' }, { value: 'type', label: 'По типу' },
            ]} />
          </div>
        </div>
      </SettingsCard>
    </div>
  )
}
