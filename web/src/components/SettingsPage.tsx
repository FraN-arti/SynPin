import { useState } from 'react'

interface SettingsPageProps {
  onBack: () => void
}

export function SettingsPage({ onBack }: SettingsPageProps) {
  const [fadeIn, setFadeIn] = useState(false)

  // Trigger fade-in after mount
  useState(() => {
    requestAnimationFrame(() => setFadeIn(true))
  })

  const handleBack = () => {
    setFadeIn(false)
    setTimeout(onBack, 300)
  }

  return (
    <div className={`settings-page ${fadeIn ? 'visible' : ''}`}>
      <div className="settings-header">
        <button className="settings-back-btn" onClick={handleBack}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          Назад
        </button>
        <h1 className="settings-title">Настройки</h1>
      </div>

      <div className="settings-content">
        <section className="settings-section">
          <h2 className="settings-section-title">Провайдер</h2>
          <div className="settings-option">
            <label className="settings-label">Модель</label>
            <select className="settings-select" defaultValue="general-agent">
              <option value="general-agent">general-agent (9router)</option>
            </select>
          </div>
        </section>

        <section className="settings-section">
          <h2 className="settings-section-title">Интерфейс</h2>
          <div className="settings-option">
            <label className="settings-label">Тема</label>
            <select className="settings-select" defaultValue="dark">
              <option value="dark">Тёмная</option>
              <option value="light" disabled>Светлая (скоро)</option>
            </select>
          </div>
        </section>
      </div>
    </div>
  )
}
