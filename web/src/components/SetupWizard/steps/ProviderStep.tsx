/**
 * ProviderStep — auto-configures OpenCode Free on mount.
 *
 * First-run design: instead of asking the user to paste an API key
 * before they can try SynPin, we register OpenCode Free (a no-auth
 * public endpoint) by default. The user can swap in a paid
 * provider later via Settings → Providers.
 *
 * Auto-POST fires on mount. After success, shows a check + "Дальше"
 * button. No auto-advance — the user clicks when ready.
 */

import { useEffect, useState } from 'react'
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
        if (!cancelled) setStatus({ kind: 'idle' })
      })
      .catch(err => {
        if (!cancelled) setStatus({ kind: 'error', message: String(err) })
      })
    return () => { cancelled = true }
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
            <div className="provider-meta">6 бесплатных моделей · без ключа</div>
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