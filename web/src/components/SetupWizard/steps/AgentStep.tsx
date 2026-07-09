/**
 * AgentStep — placeholder. Full implementation comes next:
 *   - form for agent name + tone + model picker
 *   - POST /api/agents
 *   - POST /api/agents/{slug}/primary to mark as primary
 *   - transitions to DoneStep
 *
 * For now: a short "ready" state so the wizard flow is testable.
 */

import '../shared.css'

interface AgentStepProps {
  onNext: () => void
  onBack: () => void
}

export function AgentStep({ onNext, onBack }: AgentStepProps) {
  return (
    <div className="wizard-card">
      <h1 className="wizard-title">Первый агент</h1>
      <p className="wizard-subtitle">
        Скоро — форма создания главного агента.
      </p>

      <div className="wizard-placeholder">
        <p>Здесь будет: имя, модель, тон, кнопка «Сделать главным»</p>
      </div>

      <button className="wizard-btn-primary" onClick={onNext}>
        Дальше
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M5 12h14M12 5l7 7-7 7" />
        </svg>
      </button>

      <button className="wizard-skip" onClick={onBack}>
        ← Назад
      </button>
    </div>
  )
}