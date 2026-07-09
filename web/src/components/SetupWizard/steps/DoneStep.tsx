/**
 * DoneStep — final step, success state.
 * Calls onFinish which reloads the page (App re-reads setup status
 * and skips the wizard on next mount).
 */

import '../shared.css'
import './DoneStep.css'

interface DoneStepProps {
  onFinish: () => void
}

export function DoneStep({ onFinish }: DoneStepProps) {
  return (
    <div className="wizard-card wizard-done">
      <div className="wizard-logo">
        <span className="logo-syn">Syn</span>
        <span className="logo-pin">Pin</span>
      </div>

      <div className="wizard-check">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
          <polyline points="22 4 12 14.01 9 11.01" />
        </svg>
      </div>

      <h1 className="wizard-title">Готово!</h1>
      <p className="wizard-subtitle">
        SynPin настроен и готов к работе.
      </p>

      <button className="wizard-btn-primary" onClick={onFinish}>
        Перейти к SynPin
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M5 12h14M12 5l7 7-7 7" />
        </svg>
      </button>
    </div>
  )
}