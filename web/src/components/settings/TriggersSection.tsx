/**
 * TriggersSection — auto-saving settings for trigger plugins.
 *
 * Design (per Артур 2026-07-06):
 *   - NO buttons. Every change is auto-saved (debounced) — same UX as
 *     General settings.
 *   - Global config per plugin (one set of values, not per-instance).
 *   - Multiselect of connections = "which connections use this plugin".
 *     Toggling a connection on/off creates or deletes the corresponding
 *     instance on the backend; the global config is patched in place.
 *   - No "Action" picker — for idle_head the action is always
 *     `agent_prompt` (other types in schema are reserved for future
 *     plugins that need them).
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { API_BASE } from '../../config'
import { SettingsCard } from '../SettingsCard'
import { LoadingSpinner } from '../LoadingSpinner'
import { PickerMenu, PickerOption } from '../PickerMenu'
import { Toggle } from './Toggle'

interface ConfigField {
  name: string
  type: 'number' | 'string' | 'boolean'
  default: any
  min?: number
  label: string
}

interface Definition {
  type: string
  name: string
  description: string
  category: string
  icon: string
  color: string
  config_schema: ConfigField[]
  tick_interval_s: number
  global_toggle: boolean
}

interface Instance {
  id: string
  type: string
  connection_id?: string
  _connection_id?: string
  config: Record<string, any>
  enabled: boolean
}

interface Connection {
  id: string
  label?: string
  from: string
  to: string
  active: boolean
}

export function TriggersSection({ wsOn }: { wsOn?: (type: string, handler: (data: any) => void) => () => void } = {}) {
  const [defs, setDefs] = useState<Definition[]>([])
  const [instances, setInstances] = useState<Instance[]>([])
  const [connections, setConnections] = useState<Connection[]>([])
  const [otdelNames, setOtdelNames] = useState<Record<string, string>>({})
  const [loaded, setLoaded] = useState(false)

  const loadDefs = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/triggers/definitions`)
      if (res.ok) {
        const data = await res.json()
        setDefs(data.definitions || [])
      }
    } catch {}
  }, [])

  const loadInstances = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/triggers/instances`)
      if (res.ok) {
        const data = await res.json()
        setInstances(data.instances || [])
      }
    } catch {}
  }, [])

  const loadConnections = useCallback(async () => {
    try {
      const [cRes, oRes] = await Promise.all([
        fetch(`${API_BASE}/api/connections`),
        fetch(`${API_BASE}/api/otdels`),
      ])
      if (cRes.ok) {
        const data = await cRes.json()
        setConnections((data.connections || []).filter((c: Connection) => c.active))
      }
      if (oRes.ok) {
        const data = await oRes.json()
        const names: Record<string, string> = {}
        for (const o of (data.otdels || [])) {
          names[o.otdelid] = o.name
          names[`otdel:${o.otdelid}`] = o.name
        }
        setOtdelNames(names)
      }
    } catch {}
  }, [])

  useEffect(() => {
    Promise.all([loadDefs(), loadInstances(), loadConnections()]).then(() => setLoaded(true))
  }, [loadDefs, loadInstances, loadConnections])

  // Live updates: when any trigger instance changes on the server
  // (via WS broadcast), refetch the instance list so toggles / config
  // stay in sync without a manual page refresh.
  useEffect(() => {
    if (!wsOn) return
    return wsOn('triggers:instance_changed', () => { loadInstances() })
  }, [wsOn, loadInstances])

  if (!loaded) {
    return <LoadingSpinner text="Загрузка плагинов..." />
  }

  return (
    <div className="settings-sections">
      <SettingsCard title="Плагины автоматизации">
        <p className="settings-hint">
          {defs.length} плагин{defs.length === 1 ? '' : defs.length < 5 ? 'а' : 'ов'} найдено автоматически.
          Каждый плагин реагирует на событие (застой задачи, тишина отдела) и будит агента по выбранным связям.
          Изменения сохраняются автоматически.
        </p>
        <div className="settings-divider-thin" />

        {defs.length === 0 ? (
          <p className="settings-empty-state">Плагины не найдены</p>
        ) : (
          <div className="triggers-grid">
            {defs.map(def => (
              <PluginBlock
                key={def.type}
                def={def}
                instances={instances.filter(i => i.type === def.type)}
                connections={connections}
                otdelNames={otdelNames}
                onReload={loadInstances}
              />
            ))}
          </div>
        )}
      </SettingsCard>
    </div>
  )
}

// ── Single plugin block ────────────────────────────────────────────

function PluginBlock({
  def, instances, connections, otdelNames, onReload,
}: {
  def: Definition
  instances: Instance[]
  connections: Connection[]
  otdelNames: Record<string, string>
  onReload: () => Promise<void>
}) {
  // ── Global config (one set of values for this plugin) ─────────
  const [config, setConfig] = useState<Record<string, any>>(() => {
    const out: Record<string, any> = {}
    for (const f of def.config_schema) out[f.name] = f.default
    // If instances exist, seed from the first one (they all share config)
    if (instances.length > 0) {
      Object.assign(out, instances[0].config || {})
    }
    return out
  })
  const cfgTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastSavedCfgRef = useRef(JSON.stringify(config))

  // ── Connection multiselect ─────────────────────────────────────
  const [selectedConnIds, setSelectedConnIds] = useState<string[]>(() => {
    // Derive from existing instances: their _connection_id is the source of truth
    return Array.from(new Set(
      instances.map(i => i._connection_id || i.connection_id || '').filter(Boolean)
    ))
  })
  const connTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastSavedConnsRef = useRef<string[]>(selectedConnIds)

  // ── Plugin enabled/disabled (global toggle) ───────────────────
  // True if any instance exists AND all are enabled. False if all
  // are disabled. If there are no instances yet, the plugin is
  // "off" until the user picks at least one connection.
  const allEnabled = instances.length > 0 && instances.every(i => i.enabled)

  const handleToggleEnabled = async () => {
    if (instances.length === 0) return
    const next = !allEnabled
    try {
      await Promise.all(
        instances.map(inst =>
          fetch(`${API_BASE}/api/triggers/instances/${inst.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: next }),
          })
        )
      )
      await onReload()
    } catch {}
  }

  // ── Sync config when instances load (initial mount) ────────────
  useEffect(() => {
    if (instances.length > 0) {
      setConfig(prev => ({ ...prev, ...instances[0].config }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [instances.length])

  // ── Auto-save: config (debounced 800ms) ─────────────────────────
  // If there are no instances yet, buffer the change in pendingConfigRef
  // and let reconcileConnections pick it up when the first connection
  // is added. This way the user can set idle_minutes before/after
  // choosing connections without losing the value.
  const pendingConfigRef = useRef<Record<string, any> | null>(null)

  const saveConfig = useCallback(async (next: Record<string, any>) => {
    if (instances.length === 0) {
      pendingConfigRef.current = next
      return
    }
    try {
      await Promise.all(
        instances.map(inst =>
          fetch(`${API_BASE}/api/triggers/instances/${inst.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ config: next }),
          })
        )
      )
      lastSavedCfgRef.current = JSON.stringify(next)
      await onReload()
    } catch {}
  }, [instances, onReload])

  const handleConfigChange = (field: string, value: any) => {
    const next = { ...config, [field]: value }
    setConfig(next)
    if (cfgTimerRef.current) clearTimeout(cfgTimerRef.current)
    cfgTimerRef.current = setTimeout(() => {
      if (JSON.stringify(next) !== lastSavedCfgRef.current) {
        saveConfig(next)
      }
    }, 800)
  }

  // ── Auto-save: connection multiselect (debounced 600ms) ────────
  const reconcileConnections = useCallback(async (nextIds: string[]) => {
    const currentIds = lastSavedConnsRef.current
    const toAdd = nextIds.filter(id => !currentIds.includes(id))
    const toRemove = currentIds.filter(id => !nextIds.includes(id))

    // Use the most recent config the user has set, even if save was
    // pending because there were no instances at the time.
    const configToWrite = pendingConfigRef.current ?? config

    try {
      await Promise.all([
        ...toAdd.map(async cid => {
          const res = await fetch(`${API_BASE}/api/triggers/instances`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              type: def.type,
              connection_id: cid,
              config: configToWrite,
              action: { type: 'agent_prompt' },
              enabled: true,
            }),
          })
          if (res.ok) {
            const created = await res.json()
            // Clear pending once at least one instance exists
            pendingConfigRef.current = null
            return created
          }
          return null
        }),
        ...toRemove.map(async cid => {
          const inst = instances.find(i => (i._connection_id || i.connection_id) === cid)
          if (inst) {
            return fetch(`${API_BASE}/api/triggers/instances/${inst.id}`, { method: 'DELETE' })
          }
          return null
        }),
      ])
      lastSavedConnsRef.current = nextIds
      lastSavedCfgRef.current = JSON.stringify(configToWrite)
      await onReload()
    } catch {}
  }, [def.type, config, instances, onReload])

  const handleConnChange = (nextIds: string[]) => {
    setSelectedConnIds(nextIds)
    if (connTimerRef.current) clearTimeout(connTimerRef.current)
    connTimerRef.current = setTimeout(() => {
      const sortedCurrent = [...lastSavedConnsRef.current].sort()
      const sortedNext = [...nextIds].sort()
      if (JSON.stringify(sortedCurrent) !== JSON.stringify(sortedNext)) {
        reconcileConnections(nextIds)
      }
    }, 600)
  }

  // ── Connection picker options ─────────────────────────────────
  const connOptions: PickerOption[] = connections.map(c => {
    const fromName = c.from === 'agent:primary' ? 'Главный агент' : (otdelNames[c.from] || c.from)
    const toName = c.to === 'agent:primary' ? 'Главный агент' : (otdelNames[c.to] || c.to)
    return {
      id: c.id,
      label: `${fromName} → ${toName}`,
      searchText: `${fromName} ${toName} ${c.label || ''}`,
      badge: c.label,
    }
  })

  const cfgDirty = JSON.stringify(config) !== lastSavedCfgRef.current

  return (
    <div className={`trigger-plugin-block ${allEnabled ? '' : 'trigger-plugin-disabled'}`}>
      <div className="trigger-plugin-header">
        <div className="trigger-plugin-info">
          <h4 className="trigger-plugin-name">{def.name}</h4>
          <p className="trigger-plugin-desc">{def.description}</p>
          <div className="trigger-plugin-meta">
            <span className="trigger-plugin-tag">tick: {def.tick_interval_s}s</span>
          </div>
        </div>
        <div className="trigger-plugin-status">
          {selectedConnIds.length === 0 && (
            <span className="trigger-dirty">выбери связи</span>
          )}
          {!cfgDirty && selectedConnIds.length > 0 && allEnabled && (
            <span className="trigger-saved">✓ {selectedConnIds.length} связ{selectedConnIds.length === 1 ? 'ь' : selectedConnIds.length < 5 ? 'и' : 'ей'}</span>
          )}
          {cfgDirty && selectedConnIds.length === 0 && (
            <span className="trigger-dirty">применится при выборе связей</span>
          )}
          {cfgDirty && selectedConnIds.length > 0 && allEnabled && (
            <span className="trigger-dirty">не сохранено</span>
          )}
          {def.global_toggle && (
            <div className="trigger-status-toggle">
              <span className="trigger-saved">
                {cfgDirty ? 'не сохранено' : (selectedConnIds.length > 0 ? `✓ ${selectedConnIds.length} связ${selectedConnIds.length === 1 ? 'ь' : selectedConnIds.length < 5 ? 'и' : 'ей'}` : 'выбери связи')}
              </span>
              <Toggle
                label=""
                checked={allEnabled}
                onChange={handleToggleEnabled}
              />
            </div>
          )}
        </div>
      </div>

      {/* Global config fields */}
      {def.config_schema.map(field => (
        <div key={field.name} className="settings-field">
          <label>{field.label}</label>
          <input
            className="settings-input"
            type={field.type === 'number' ? 'number' : 'text'}
            min={field.min}
            value={config[field.name] ?? field.default}
            onChange={e => handleConfigChange(
              field.name,
              field.type === 'number' ? Number(e.target.value) : e.target.value,
            )}
          />
        </div>
      ))}

      {/* Connection multiselect */}
      <div className="settings-field">
        <label>Связи ({selectedConnIds.length} выбрано)</label>
        <PickerMenu
          multi
          options={connOptions}
          value={selectedConnIds}
          onChange={handleConnChange}
          placeholder="Выбери связи, для которых работает плагин"
          searchable
          searchPlaceholder="Поиск связи..."
          triggerWidth="100%"
          emptyMessage="Нет связей — создай их в настройках"
        />
      </div>
    </div>
  )
}
