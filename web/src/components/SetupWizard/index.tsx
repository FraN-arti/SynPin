/**
 * SetupWizard — first-run wizard for new SynPin installations.
 *
 * Shown when:
 *   - Providers are empty (production virgin detection)
 *   - WIZARD_S=1 env var is set (forced dev mode)
 *   - URL route is /start/
 *
 * Layout: each step is its own file in ./steps/. The root component
 * owns the step state and passes per-step callbacks (onNext, onBack,
 * onSkip, onFinish) to the active step.
 *
 * Steps currently shipped: welcome, provider, done.
 * Future steps (theme, agent, etc) go in the steps/ folder too.
 */

import { useState } from 'react'
import { BootLoader } from '../BootLoader'
import { WelcomeStep } from './steps/WelcomeStep'
import { ProviderStep } from './steps/ProviderStep'
import { AgentStep } from './steps/AgentStep'
import { DoneStep } from './steps/DoneStep'
import './shared.css'

type WizardStep = 'welcome' | 'provider' | 'agent' | 'done'

interface SetupWizardProps {
  /** Called when wizard finishes or user exits via skip/back. */
  onComplete: () => void
}

export function SetupWizard({ onComplete }: SetupWizardProps) {
  const [step, setStep] = useState<WizardStep>('welcome')

  return (
    <div className="setup-wizard">
      <div className="wizard-glow" />

      {step === 'welcome' && (
        <WelcomeStep
          onNext={() => setStep('provider')}
          onSkip={onComplete}
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
        <DoneStep onFinish={onComplete} />
      )}

      {/* If we ever land in a step with no component (e.g. during
          dev while adding new ones), show the boot loader so the
          user doesn't see a blank card. */}
      {!['welcome', 'provider', 'agent', 'done'].includes(step) && (
        <BootLoader status={`Шаг: ${step}`} />
      )}
    </div>
  )
}

// Re-export for backward compat — old import path
// `import { SetupWizard } from './SetupWizard'` still works via
// App.tsx lazy import that resolves to index.tsx by default.
export default SetupWizard