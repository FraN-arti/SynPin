/**
 * ProviderStep — auto-configures OpenCode Free on mount.
 *
 * First-run design: instead of asking the user to paste an API key
 * before they can try SynPin, we register OpenCode Free (a no-auth
 * public endpoint) by default. The user can swap in a paid
 * provider later via Settings → Providers. This way the first
 * 60 seconds of onboarding are: wizard loads → system has a working
 * LLM → first agent step.
 *
 * The UI shows what's happening (a tiny status line) so the user
 * isn't confused. After save_setup returns, the wizard advances
 * to AgentStep.
 */

import { useEffect, useRef, useState } from 'react'
import { API_BASE } from '../../../config'
import '../shared.css'
import './ProviderStep.css'

interface ProviderStepProps {
  onNext: () => void
  onBack: () => void
}

type Status =
  | { kind: 'idle' }
  | { kind: 'saving' }
  | { kind: 'error'; message: string }

export function ProviderStep({ onNext, onBack }: ProviderStepProps) {
  const [status, setStatus] = useState<Status>({ kind: 'saving' })
  // Use a ref for onNext so the mount effect never depends on the
  // callback identity. This prevents stale-closure flashes where
  // the old onNext fires before the new one is captured.
  const onNextRef = useRef(onNext)
  onNextRef.current = onNext

  // Auto-POST on mount. Empty providers list → backend registers
  // OpenCode Free by default (see setup_router.py).
  useEffect(() => {
    let cancelled = false
    fetch(`${API_BASE}/api/setup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ providers: [] }),
    })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(() => {
        if (!cancelled) {
          setStatus({ kind: 'idle' })
          // Brief pause so the user sees the success state before
          // the next card slides in. 600ms is enough to register
          // the change without feeling like a wait.
          setTimeout(() => {
            if (!cancelled) onNextRef.current()
          }, 600)
        }
      })
      .catch(err => {
        if (!cancelled) {
          setStatus({ kind: 'error', message: String(err) })
        }
      })
    return () => { cancelled = true }
    // Empty deps: runs once on mount, never re-runs.
    // onNextRef always points to the latest callback.
  }, [])

  return (
    <div className="wizard-card">
      <h1 className="wizard-title">Провайдер</h1>
      <p className="wizard-subtitle">
        Подключаем OpenCode Free — бесплатные модели без ключа.
      </p>

      <div className="provider-card">
        {status.kind === 'saving' && (
          <>
            <div className="provider-spinner" />
            <div className="provider-status">Подключаю…</div>
          </>
        )}
        {status.kind === 'idle' && (
          <>
            <div className="provider-check">✓</div>
            <div className="provider-name">OpenCode Free</div>
            <div className="provider-meta">3 модели · без ключа</div>
          </>
        )}
        {status.kind === 'error' && (
          <>
            <div className="provider-error">!</div>
            <div className="provider-status">Ошибка: {status.message}</div>
          </>
        )}
      </div>

      <p className="provider-footnote">
        Поменять провайдера или добавить свой ключ — позже, в Настройки → Провайдеры.
      </p>

      {status.kind === 'idle' && (
        <button className="wizard-btn-primary" onClick={onNext}>
          Дальше
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </button>
      )}

      <button className="wizard-skip" onClick={onBack}>
        ← Назад
      </button>
    </div>
  )
}