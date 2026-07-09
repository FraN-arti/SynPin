/**
 * AgentStep — create the first agent during onboarding.
 *
 * Flow:
 *   1. Fetch models from OpenCode Free via GET /api/providers/opencode-free/models
 *      (or use the hardcoded fallback if the endpoint fails)
 *   2. User picks: name, tone (preset chips), model (dropdown from OpenCode Free)
 *   3. POST /api/agents → created
 *   4. PUT /api/agents/{slug} with { is_primary: true } → primary
 *   5. Transition to DoneStep
 *
 * The "Сделать главным" toggle is explained inline — "Голова думает, руки делают"
 * connects back to the onboarding narrative (screen 2).
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

// Tone presets — each has a label and a short description. The user
// picks one chip. The description is shown below the name field
// as a preview of what the tone looks like.
const TONES = [
  { value: 'professional', label: 'Профессиональный', desc: 'Чётко, по делу, без лишнего.' },
  { value: 'friendly', label: 'Дружелюбный', desc: 'Тепло, с заботой, без сухости.' },
  { value: 'creative', label: 'Творческий', desc: 'Метафоры, неожиданные повороты.' },
  { value: 'neutral', label: 'Нейтральный', desc: 'Баланс между формальным и свободным.' },
] as const

const DEFAULT_MODELS = [
  'gpt-5-nano',
  'claude-haiku-4-5',
  'gemini-2.5-flash',
]

export function AgentStep({ onNext, onBack }: AgentStepProps) {
  const [name, setName] = useState('')
  const [tone, setTone] = useState<string>('professional')
  const [model, setModel] = useState(DEFAULT_MODELS[0])
  const [models, setModels] = useState<string[]>(DEFAULT_MODELS)
  const [status, setStatus] = useState<Status>({ kind: 'idle' })
  const nameRef = useRef<HTMLInputElement>(null)
  // Ref for onNext to avoid stale closures in setTimeout.
  const onNextRef = useRef(onNext)
  onNextRef.current = onNext

  // Focus the name field on mount so the user starts typing immediately.
  useEffect(() => {
    setTimeout(() => nameRef.current?.focus(), 400)
  }, [])

  // Fetch available models from OpenCode Free on mount. If the
  // endpoint fails (e.g. network), we keep the DEFAULT_MODELS
  // fallback — the agent still gets created.
  useEffect(() => {
    fetch(`${API_BASE}/api/providers/opencode-free/models`)
      .then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`))
      .then(data => {
        const list: string[] = data.models || data
        if (Array.isArray(list) && list.length > 0) {
          setModels(list)
          setModel(list[0])
        }
      })
      .catch(() => { /* use defaults */ })
  }, [])

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
          tone,
          role: 'main',
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
        // Agent was created but not marked as primary. This is not
        // fatal — the user can set primary manually in Settings.
        // We still show success but note the issue.
        console.warn('Failed to set primary:', primaryRes.status)
      }

      setStatus({ kind: 'done', agentName: name.trim() })
      // Brief pause so the user sees the success state before
      // advancing to DoneStep.
      setTimeout(() => onNextRef.current(), 800)
    } catch (err) {
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
          placeholder="Например: Алиса, Ассистент, Умка..."
          value={name}
          onChange={e => setName(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={status.kind !== 'idle'}
          maxLength={40}
          autoComplete="off"
          spellCheck={false}
        />
      </div>

      {/* Tone picker */}
      <div className="agent-field">
        <label className="agent-label">Тон</label>
        <div className="agent-tones">
          {TONES.map(t => (
            <button
              key={t.value}
              className={`agent-tone-chip ${tone === t.value ? 'active' : ''}`}
              onClick={() => setTone(t.value)}
              disabled={status.kind !== 'idle'}
              type="button"
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="agent-tone-desc">
          {TONES.find(t => t.value === tone)?.desc}
        </div>
      </div>

      {/* Model picker */}
      <div className="agent-field">
        <label className="agent-label">Модель</label>
        <select
          className="agent-select"
          value={model}
          onChange={e => setModel(e.target.value)}
          disabled={status.kind !== 'idle'}
        >
          {models.map(m => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        <div className="agent-model-hint">
          Выберите любую модель. Позже можно сменить в Настройки → Агенты.
        </div>
      </div>

      {/* Primary badge — explains what "главный" means */}
      <div className="agent-primary-badge">
        <div className="agent-primary-icon">★</div>
        <div className="agent-primary-text">
          <strong>Главный агент</strong>
          <span>Координирует отделы, делегирует задачи, следит за прогрессом.</span>
        </div>
      </div>

      {/* CTA + status */}
      {status.kind === 'idle' && (
        <button className="wizard-btn-primary agent-cta" onClick={handleCreate} disabled={!canCreate}>
          Создать и сделать главным
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </button>
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