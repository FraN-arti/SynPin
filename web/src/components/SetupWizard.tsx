/**
 * SetupWizard — first-run wizard for new SynPin installations.
 *
 * Shown when providers.yaml is empty/missing (virgin detection).
 * Can be triggered:
 *   - Auto-opened by `synpin start` if virgin
 *   - Manually via `d + enter` in dev console (dev mode only)
 *
 * Currently: Step 1 (Welcome page). More steps added iteratively.
 */

import { useState } from 'react'
import './SetupWizard.css'

type WizardStep = 'welcome' | 'provider' | 'agents' | 'done'

interface SetupWizardProps {
  /** Called when wizard finishes or user exits */
  onComplete: () => void
}

export function SetupWizard({ onComplete }: SetupWizardProps) {
  const [step, setStep] = useState<WizardStep>('welcome')

  return (
    <div className="setup-wizard">
      {/* Background glow */}
      <div className="wizard-glow" />

      {step === 'welcome' && (
        <WelcomeStep onNext={() => setStep('provider')} onSkip={onComplete} />
      )}

      {step === 'provider' && (
        <ProviderStep
          onNext={() => setStep('done')}
          onBack={() => setStep('welcome')}
        />
      )}

      {step === 'done' && (
        <DoneStep onFinish={onComplete} />
      )}
    </div>
  )
}

// ── Step: Welcome ───────────────────────────────────────────────

function WelcomeStep({ onNext, onSkip }: { onNext: () => void; onSkip: () => void }) {
  return (
    <div className="wizard-card">
      {/* Logo */}
      <div className="wizard-logo">
        <span className="logo-syn">Syn</span>
        <span className="logo-pin">Pin</span>
      </div>

      <h1 className="wizard-title">Добро пожаловать</h1>

      <p className="wizard-subtitle">
        Multi-Agent Framework для автоматизации задач.
        <br />
        Настройка займёт пару минут.
      </p>

      <div className="wizard-features">
        <Feature
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z" />
              <path d="M2 17l10 5 10-5" />
              <path d="M2 12l10 5 10-5" />
            </svg>
          }
          title="Мульти-агентная система"
          description="Несколько агентов работают параллельно"
        />
        <Feature
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="7" />
              <rect x="14" y="3" width="7" height="7" />
              <rect x="14" y="14" width="7" height="7" />
              <rect x="3" y="14" width="7" height="7" />
            </svg>
          }
          title="Канбан-доска"
          description="Управляйте задачами визуально"
        />
        <Feature
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          }
          title="Cron-задачи"
          description="Автоматические действия по расписанию"
        />
      </div>

      <button className="wizard-btn-primary" onClick={onNext}>
        Начать настройку
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M5 12h14M12 5l7 7-7 7" />
        </svg>
      </button>

      <p className="wizard-skip" onClick={onSkip}>
        Настрою позже
      </p>
    </div>
  )
}

// ── Step: Provider (placeholder) ────────────────────────────────

function ProviderStep({
  onNext,
  onBack,
}: {
  onNext: () => void
  onBack: () => void
}) {
  return (
    <div className="wizard-card">
      <button className="wizard-back" onClick={onBack}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
        Назад
      </button>

      <h1 className="wizard-title">Провайдеры</h1>
      <p className="wizard-subtitle">
        Подключите LLM API для работы агентов.
      </p>

      <div className="wizard-placeholder">
        <p>Следующий шаг — настройка API-ключей</p>
      </div>

      <button className="wizard-btn-primary" onClick={onNext}>
        Продолжить
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M5 12h14M12 5l7 7-7 7" />
        </svg>
      </button>
    </div>
  )
}

// ── Step: Done ──────────────────────────────────────────────────

function DoneStep({ onFinish }: { onFinish: () => void }) {
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

// ── Helpers ─────────────────────────────────────────────────────

function Feature({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode
  title: string
  description: string
}) {
  return (
    <div className="wizard-feature">
      <div className="wizard-feature-icon">{icon}</div>
      <div>
        <div className="wizard-feature-title">{title}</div>
        <div className="wizard-feature-desc">{description}</div>
      </div>
    </div>
  )
}
