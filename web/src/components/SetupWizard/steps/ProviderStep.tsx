/**
 * ProviderStep — placeholder for LLM provider setup.
 * Currently a "coming soon" stub. The real implementation will
 * read from /api/themes/tweakcn/list, render a radio-card picker
 * (per select.html #5), and POST to /api/setup.
 */

import '../shared.css'

interface ProviderStepProps {
  onNext: () => void
  onBack: () => void
}

export function ProviderStep({ onNext, onBack }: ProviderStepProps) {
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