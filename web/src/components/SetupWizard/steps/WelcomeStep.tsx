/**
 * WelcomeStep — first step of the wizard.
 * Shows the SynPin mark, 3 features, and a CTA to begin setup.
 */

import './WelcomeStep.css'

interface WelcomeStepProps {
  onNext: () => void
  onSkip: () => void
}

export function WelcomeStep({ onNext, onSkip }: WelcomeStepProps) {
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

      <button className="wizard-skip" onClick={onSkip}>
        Настрою позже
      </button>
    </div>
  )
}

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