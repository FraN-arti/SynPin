import { SettingsCard } from '../SettingsCard'

export function SkillsSection() {
  return (
    <div className="settings-sections">
      <SettingsCard title="Скиллы системы">
        <p style={{ color: 'var(--gray-500)', fontSize: '14px', lineHeight: '1.6' }}>
          База скиллов — подходы, шаблоны и процедуры, которые система использует для решения задач.
        </p>
        <div style={{ marginTop: '16px', padding: '12px', background: 'var(--gray-900)', borderRadius: '8px', border: '1px solid var(--gray-800)' }}>
          <span style={{ color: 'var(--gray-400)', fontSize: '13px' }}>🚧 В разработке — здесь будет список скиллов с возможностью добавления, редактирования и привязки к агентам</span>
        </div>
      </SettingsCard>
    </div>
  )
}
