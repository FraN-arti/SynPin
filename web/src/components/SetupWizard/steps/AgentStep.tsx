/**
 * AgentStep — create the first agent during onboarding.
 *
 * Flow:
 *   1. Fetch free models from OpenCode Free via GET /api/providers/opencode-free/models
 *      (filtered to models ending with '-free' or named 'big-pickle')
 *   2. User picks: name, model (custom SynPin select)
 *   3. POST /api/agents → created
 *   4. PUT /api/agents/{slug} with { is_primary: true } → primary
 *   5. Transition to DoneStep
 *
 * No welcome memory note — the agent already knows its system:
 * skills, tools, departments are all loaded into the system prompt
 * via _build_system_prompt_with_memory. The user can ask anything
 * and the agent will orient itself.
 */

import { useState, useEffect, useRef } from 'react'
import { API_BASE } from '../../../config'
import '../shared.css'
import './AgentStep.css'

interface AgentStepProps {
  onNext: () => void
  onBack: () => void
}

type Status =
  | { kind: 'idle' }
  | { kind: 'creating' }
  | { kind: 'done'; agentName: string }
  | { kind: 'error'; message: string }

// Fallback when API call fails — must match OPENCODE_FREE_MODELS
// in setup_router.py (actual free models from OpenCode Free catalog)
const FALLBACK_MODELS = [
  'big-pickle',
  'deepseek-v4-flash-free',
  'mimo-v2.5-free',
  'hy3-free',
  'nemotron-3-ultra-free',
  'north-mini-code-free',
]

export function AgentStep({ onNext, onBack }: AgentStepProps) {
  const [name, setName] = useState('')
  const [model, setModel] = useState(FALLBACK_MODELS[0])
  const [models, setModels] = useState<string[]>(FALLBACK_MODELS)
  const [status, setStatus] = useState<Status>({ kind: 'idle' })
  const [modelsOpen, setModelsOpen] = useState(false)
  const nameRef = useRef<HTMLInputElement>(null)
  const selectRef = useRef<HTMLDivElement>(null)
  const onNextRef = useRef(onNext)
  onNextRef.current = onNext

  // Focus the name field on mount.
  useEffect(() => {
    setTimeout(() => nameRef.current?.focus(), 400)
  }, [])

  // Fetch free models from OpenCode Free on mount.
  useEffect(() => {
    fetch(`${API_BASE}/api/providers/opencode-free/models`)
      .then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`))
      .then(data => {
        const list: string[] = data.models || data
        if (Array.isArray(list) && list.length > 0) {
          // Filter to free models only: suffix -free or name "big-pickle"
          const free = list.filter(m => m.endsWith('-free') || m === 'big-pickle')
          if (free.length > 0) {
            setModels(free)
            setModel(free[0])
          }
        }
      })
      .catch(() => { /* use defaults */ })
  }, [])

  // Close custom select on outside click.
  useEffect(() => {
    if (!modelsOpen) return
    const handle = (e: MouseEvent) => {
      if (selectRef.current && !selectRef.current.contains(e.target as Node)) {
        setModelsOpen(false)
      }
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [modelsOpen])

  const canCreate = name.trim().length > 0 && status.kind === 'idle'

  const handleCreate = async () => {
    if (!canCreate) return
    setStatus({ kind: 'creating' })

    try {
      // Step 1: create the agent
      const createRes = await fetch(`${API_BASE}/api/agents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim(),
          model,
          provider: 'opencode-free',
        }),
      })
      if (!createRes.ok) {
        const err = await createRes.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${createRes.status}`)
      }
      const agent = await createRes.json()
      const slug = agent.slug || agent.agentid

      // Step 2: make it primary
      const primaryRes = await fetch(`${API_BASE}/api/agents/${slug}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_primary: true }),
      })
      if (!primaryRes.ok) {
        console.warn('Failed to set primary:', primaryRes.status)
      }

      setStatus({ kind: 'done', agentName: name.trim() })
      setTimeout(() => onNextRef.current(), 800)
    } catch (err) {
      console.error('[AgentStep] create failed:', err)
      setStatus({ kind: 'error', message: String(err) })
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && canCreate) handleCreate()
  }

  return (
    <div className="wizard-card agent-wizard-card">
      <h1 className="wizard-title">Первый агент</h1>
      <p className="wizard-subtitle">
        Этот агент станет <em className="hl">главным</em> — он координирует всех остальных.
      </p>

      {/* Name field */}
      <div className="agent-field">
        <label className="agent-label">Имя</label>
        <input
          ref={nameRef}
          className="agent-input"
          type="text"
          placeholder="Например: Ассистент, Умка, Оракул..."
          value={name}
          onChange={e => setName(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={status.kind !== 'idle'}
          maxLength={40}
          autoComplete="off"
          spellCheck={false}
        />
      </div>

      {/* Model picker — custom SynPin select */}
      <div className="agent-field">
        <label className="agent-label">Модель</label>
        <div className="agent-select-wrapper" ref={selectRef}>
          <button
            className={`agent-select-btn ${modelsOpen ? 'open' : ''}`}
            onClick={() => setModelsOpen(!modelsOpen)}
            disabled={status.kind !== 'idle'}
            type="button"
          >
            <span className="agent-select-value">{model}</span>
            <svg className="agent-select-arrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M6 9l6 6 6-6" />
            </svg>
          </button>
          {modelsOpen && (
            <div className="agent-select-dropdown">
              {models.map(m => (
                <button
                  key={m}
                  className={`agent-select-option ${m === model ? 'active' : ''}`}
                  onClick={() => { setModel(m); setModelsOpen(false) }}
                  type="button"
                >
                  {m}
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="agent-model-hint">
          Бесплатные модели OpenCode Free. Позже можно сменить в Настройки → Агенты.
        </div>
      </div>

      {/* Primary badge */}
      <div className="agent-primary-badge">
        <div className="agent-primary-icon">★</div>
        <div className="agent-primary-text">
          <strong>Главный агент</strong>
          <span>Координирует отделы, делегирует задачи, следит за прогрессом.</span>
        </div>
      </div>

      {/* CTA + status */}
      {status.kind === 'idle' && (
        <>
          {!name.trim() && (
            <div className="agent-hint-required">Введите имя агента, чтобы продолжить</div>
          )}
          <button className="wizard-btn-primary agent-cta" onClick={handleCreate} disabled={!canCreate}>
            Создать и сделать главным
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </>
      )}

      {status.kind === 'creating' && (
        <div className="agent-status-row">
          <div className="provider-spinner" />
          <span>Создаю агента…</span>
        </div>
      )}

      {status.kind === 'done' && (
        <div className="agent-status-row success">
          <div className="provider-check">✓</div>
          <span><strong>{status.agentName}</strong> — главный агент готов</span>
        </div>
      )}

      {status.kind === 'error' && (
        <div className="agent-status-row error">
          <div className="provider-error">!</div>
          <span>{status.message}</span>
          <button className="wizard-skip" onClick={() => setStatus({ kind: 'idle' })}>
            Попробовать снова
          </button>
        </div>
      )}

      <button className="wizard-skip" onClick={onBack} disabled={status.kind === 'creating'}>
        ← Назад
      </button>
    </div>
  )
}