/**
 * DoneStep — final screen. Shows a brief summary of what was set
 * up during the wizard and a "Перейти к SynPin" button.
 *
 * The wizard root component (index.tsx) handles calling
 * POST /api/setup/complete when onFinish is invoked, so this
 * component just calls onFinish directly.
 */

import { useEffect, useRef } from 'react'
import '../shared.css'
import './DoneStep.css'

interface DoneStepProps {
  onFinish: () => void
}

export function DoneStep({ onFinish }: DoneStepProps) {
  const onFinishRef = useRef(onFinish)
  onFinishRef.current = onFinish

  // Auto-advance: 4s timer so the user can read the summary.
  useEffect(() => {
    const t = setTimeout(() => onFinishRef.current(), 4000)
    return () => clearTimeout(t)
  }, [])

  return (
    <div className="wizard-card done-card">
      <div className="wizard-logo done-logo">
        <span className="syn">Syn</span>
        <span className="pin">Pin</span>
      </div>

      <h1 className="wizard-title done-title">Всё готово</h1>

      <div className="done-summary">
        <div className="done-row">
          <div className="done-icon done-icon--provider">✓</div>
          <div>
            <div className="done-label">Провайдер</div>
            <div className="done-value">OpenCode Free · 3 модели</div>
          </div>
        </div>
        <div className="done-row">
          <div className="done-icon done-icon--agent">★</div>
          <div>
            <div className="done-label">Главный агент</div>
            <div className="done-value">Создан и назначен</div>
          </div>
        </div>
      </div>

      <button className="wizard-btn-primary done-cta" onClick={onFinish}>
        Перейти к SynPin
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M5 12h14M12 5l7 7-7 7" />
        </svg>
      </button>

      <button className="wizard-skip" onClick={onFinish}>
        Настрою позже
      </button>
    </div>
  )
}