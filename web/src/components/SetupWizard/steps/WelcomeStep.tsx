/**
 * WelcomeStep — single-screen welcome. Not 4 screens. One screen.
 * Shows the SynPin mark + a tagline. Click "Дальше" or wait —
 * transitions smoothly to ProviderStep.
 *
 * The onboarding narrative (4 screens) is FOLDED into the existing
 * card UI: the body text is short, the visual is consistent. We
 * don't need 4 separate screens for a 30-second onboarding.
 *
 * The card has a 2-3s slow reveal animation on mount so it doesn't
 * pop in. After that, body and CTA fade in over another second.
 */

import { useState, useEffect } from 'react'
import './WelcomeStep.css'

interface WelcomeStepProps {
  onNext: () => void
  onSkip: () => void
}

export function WelcomeStep({ onNext, onSkip }: WelcomeStepProps) {
  const [revealed, setRevealed] = useState(false)

  useEffect(() => {
    // Slow reveal: card body and CTA appear ~1.5s after the
    // card itself. The card itself fades in instantly (it's the
    // container). The delay is for the *content* — gives the
    // page a moment to breathe before the user sees words.
    const t = setTimeout(() => setRevealed(true), 1500)
    return () => clearTimeout(t)
  }, [])

  return (
    <div className="wizard-card wizard-welcome">
      <div className="welcome-logo">
        <span className="syn">Syn</span>
        <span className="pin">Pin</span>
      </div>

      <h1 className="welcome-title">Добро пожаловать в SynPin</h1>

      <div className={`welcome-body ${revealed ? 'visible' : ''}`}>
        <p>Твой штат AI-сотрудников.</p>
        <p className="welcome-tagline">Операционная система для агентов, которые живут, пока ты спишь.</p>
      </div>

      <div className={`welcome-controls ${revealed ? 'visible' : ''}`}>
        <button className="wizard-btn-primary welcome-cta" onClick={onNext}>
          Дальше
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </button>
        <button className="wizard-skip welcome-skip" onClick={onSkip}>
          Настрою позже
        </button>
      </div>
    </div>
  )
}