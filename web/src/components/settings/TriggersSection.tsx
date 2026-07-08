/**
 * TriggersSection — auto-saving settings for trigger plugins.
 *
 * Design (per Артур 2026-07-06):
 *   - NO buttons. Every change is auto-saved (debounced) — same UX as
 *     General settings.
 *   - Global config per plugin (one set of values, not per-instance).
 *   - Multiselect of otdels = "which otdels use this plugin".
 *     Toggling an otdel on/off creates or deletes the corresponding
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
  otdel_id?: string
  _otdel_id?: string
  config: Record<string, any>
  enabled: boolean
}

interface Otdel {
  otdelid: string
  name: string
  head: string
}

export function TriggersSection({ wsOn }: { wsOn?: (type: string, handler: (data: any) => void) => () => void } = {}) {
  const [defs, setDefs] = useState<Definition[]>([])
  const [instances, setInstances] = useState<Instance[]>([])
  const [otdels, setOtdels] = useState<Otdel[]>([])
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

  const loadOtdels = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/otdels`)
      if (res.ok) {
        const data = await res.json()
        setOtdels(data.otdels || [])
      }
    } catch {}
  }, [])

  useEffect(() => {
    Promise.all([loadDefs(), loadInstances(), loadOtdels()]).then(() => setLoaded(true))
  }, [loadDefs, loadInstances, loadOtdels])

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
          Каждый плагин реагирует на событие (застой задачи, тишина отдела) и будит агента в выбранных отделах.
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
                otdels={otdels}
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
  def, instances, otdels, onReload,
}: {
  def: Definition
  instances: Instance[]
  otdels: Otdel[]
  onReload: () => Promise<void>
}) {
  // ── Global config (one set of values for this plugin) ─────────
  const [config, setConfig] = useState<Record<string, any>>(() => {
    const out: Record<string, any> = {}
    for (const f of def.config_schema) out[f.name] = f.default
    // If instances exist, seed from the first one (they all share config)
    if (instances.length > 0) {
      Object.assign(out, instances[0]?.config || {})
    }
    return out
  })
  const cfgTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastSavedCfgRef = useRef(JSON.stringify(config))

  // ── Otdel multiselect ─────────────────────────────────────────
  const [selectedOtdelIds, setSelectedOtdelIds] = useState<string[]>(() => {
    return Array.from(new Set(
      instances.map(i => i._otdel_id || i.otdel_id || '').filter(Boolean)
    ))
  })
  const otdelTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const lastSavedOtdelsRef = useRef<string[]>(selectedOtdelIds)

  // ── Plugin enabled/disabled (global toggle) ───────────────────
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
      setConfig(prev => ({ ...prev, ...(instances[0]?.config || {}) }))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [instances.length])

  // ── Auto-save: config (debounced 800ms) ─────────────────────────
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

  // ── Auto-save: otdel multiselect (debounced 600ms) ────────────
  const reconcileOtdels = useCallback(async (nextIds: string[]) => {
    const currentIds = lastSavedOtdelsRef.current
    const toAdd = nextIds.filter(id => !currentIds.includes(id))
    const toRemove = currentIds.filter(id => !nextIds.includes(id))

    const configToWrite = pendingConfigRef.current ?? config

    try {
      await Promise.all([
        ...toAdd.map(async oid => {
          const res = await fetch(`${API_BASE}/api/triggers/instances`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              type: def.type,
              otdel_id: oid,
              config: configToWrite,
              action: { type: 'agent_prompt' },
              enabled: true,
            }),
          })
          if (res.ok) {
            const created = await res.json()
            pendingConfigRef.current = null
            return created
          }
          return null
        }),
        ...toRemove.map(async oid => {
          const inst = instances.find(i => (i._otdel_id || i.otdel_id) === oid)
          if (inst) {
            return fetch(`${API_BASE}/api/triggers/instances/${inst.id}`, { method: 'DELETE' })
          }
          return null
        }),
      ])
      lastSavedOtdelsRef.current = nextIds
      lastSavedCfgRef.current = JSON.stringify(configToWrite)
      await onReload()
    } catch {}
  }, [def.type, config, instances, onReload])

  const handleOtdelChange = (nextIds: string[]) => {
    setSelectedOtdelIds(nextIds)
    if (otdelTimerRef.current) clearTimeout(otdelTimerRef.current)
    otdelTimerRef.current = setTimeout(() => {
      const sortedCurrent = [...lastSavedOtdelsRef.current].sort()
      const sortedNext = [...nextIds].sort()
      if (JSON.stringify(sortedCurrent) !== JSON.stringify(sortedNext)) {
        reconcileOtdels(nextIds)
      }
    }, 600)
  }

  // ── Otdel picker options ───────────────────────────────────────
  const otdelOptions: PickerOption[] = otdels.map(o => ({
    id: o.otdelid,
    label: o.name,
    searchText: o.name,
  }))

  const cfgDirty = JSON.stringify(config) !== lastSavedCfgRef.current

  // Pulse the block outline briefly when the enabled state flips —
  // gives the click the same kind of "ring" feedback as the
  // #10 Glow Ring checkbox concept. The animation is added/removed
  // via a key remount: every time allEnabled changes, we toggle
  // a CSS class that runs a one-shot keyframe animation.
  const [pulseKey, setPulseKey] = useState(0)
  const prevEnabledRef = useRef(allEnabled)
  useEffect(() => {
    if (prevEnabledRef.current !== allEnabled) {
      prevEnabledRef.current = allEnabled
      setPulseKey(k => k + 1)
    }
  }, [allEnabled])

  // Click anywhere in the block (except on form controls / buttons)
  // toggles all instances. Inner inputs and selects stop propagation
  // so typing in a field doesn't accidentally flip the plugin state.
  const handleBlockClick = (e: React.MouseEvent) => {
    const target = e.target as HTMLElement
    if (target.closest('input, select, textarea, button, [role="button"][data-no-toggle]')) {
      return
    }
    handleToggleEnabled()
  }
  const handleBlockKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      handleToggleEnabled()
    }
  }

  return (
    <div
      key={pulseKey}
      className={`trigger-plugin-block ${allEnabled ? 'trigger-plugin-enabled' : 'trigger-plugin-disabled'} trigger-pulse`}
      role="button"
      tabIndex={0}
      onClick={handleBlockClick}
      onKeyDown={handleBlockKeyDown}
      aria-pressed={allEnabled}
      title={allEnabled ? 'Нажми чтобы выключить плагин' : 'Нажми чтобы включить плагин'}
    >
      <div className="trigger-plugin-header">
        <div className="trigger-plugin-info">
          <h4 className="trigger-plugin-name">{def.name}</h4>
          <p className="trigger-plugin-desc">{def.description}</p>
          <div className="trigger-plugin-meta">
            <span className="trigger-plugin-tag">tick: {def.tick_interval_s}s</span>
          </div>
        </div>
        <div className="trigger-plugin-status">
          {def.global_toggle && (
            <div className="trigger-status-toggle">
              <span className={
                cfgDirty
                  ? 'trigger-dirty'
                  : (selectedOtdelIds.length > 0 ? 'trigger-saved' : 'trigger-dirty')
              }>
                {cfgDirty
                  ? 'не сохранено'
                  : (selectedOtdelIds.length > 0
                      ? `✓ ${selectedOtdelIds.length} отдел${selectedOtdelIds.length === 1 ? '' : selectedOtdelIds.length < 5 ? 'а' : 'ов'}`
                      : 'выбери отдел')}
              </span>
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

      {/* Otdel multiselect */}
      <div className="settings-field">
        <label>Отделы ({selectedOtdelIds.length} выбрано)</label>
        <PickerMenu
          multi
          options={otdelOptions}
          value={selectedOtdelIds}
          onChange={handleOtdelChange}
          placeholder="Выбери отделы, для которых работает плагин"
          searchable
          searchPlaceholder="Поиск отдела..."
          triggerWidth="100%"
          emptyMessage="Нет отделов — создай их в настройках"
        />
      </div>
    </div>
  )
}
