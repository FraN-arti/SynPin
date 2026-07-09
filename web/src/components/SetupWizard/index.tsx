/**
 * SetupWizard — first-run wizard for new SynPin installations.
 *
 * Shown when:
 *   - wizard.json.completed is false or missing (production)
 *   - WIZARD_S=1 env var is set (forced dev mode)
 *   - URL route is /start/
 *
 * Any exit from the wizard (skip, "Перейти к SynPin") calls
 * POST /api/setup/complete to write wizard.json { completed: true }
 * so the wizard never shows again (unless WIZARD_S=1 overrides).
 *
 * Steps: welcome → provider → agent → done.
 */

import { useCallback, useState } from 'react'
import { API_BASE } from '../../config'
import { BootLoader } from '../BootLoader'
import { WelcomeStep } from './steps/WelcomeStep'
import { ProviderStep } from './steps/ProviderStep'
import { AgentStep } from './steps/AgentStep'
import { DoneStep } from './steps/DoneStep'
import './shared.css'

type WizardStep = 'welcome' | 'provider' | 'agent' | 'done'

interface SetupWizardProps {
  onComplete: () => void
}

export function SetupWizard({ onComplete }: SetupWizardProps) {
  const [step, setStep] = useState<WizardStep>('welcome')

  // Mark wizard as completed on any exit. The POST is fire-and-forget
  // (network errors are tolerated — worst case the user sees the
  // wizard again on next load). Only call when NOT in dev-override
  // mode (WIZARD_S=1), so the wizard can be re-triggered in dev.
  const handleExit = useCallback(() => {
    fetch(`${API_BASE}/api/setup/complete`, { method: 'POST' }).catch(() => {})
    onComplete()
  }, [onComplete])

  return (
    <div className="setup-wizard">
      <div className="wizard-glow" />

      {step === 'welcome' && (
        <WelcomeStep
          onNext={() => setStep('provider')}
          onSkip={handleExit}
        />
      )}

      {step === 'provider' && (
        <ProviderStep
          onNext={() => setStep('agent')}
          onBack={() => setStep('welcome')}
        />
      )}

      {step === 'agent' && (
        <AgentStep
          onNext={() => setStep('done')}
          onBack={() => setStep('provider')}
        />
      )}

      {step === 'done' && (
        <DoneStep onFinish={handleExit} />
      )}

      {!['welcome', 'provider', 'agent', 'done'].includes(step) && (
        <BootLoader status={`Шаг: ${step}`} />
      )}
    </div>
  )
}

// Re-export for backward compat
export default SetupWizard