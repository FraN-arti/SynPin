/**
 * WelcomeStep — multi-screen onboarding. The first encounter with
 * SynPin. Walks the user through 4 short story beats before they
 * ever see a form.
 *
 * Design language (matches SynPin's "единый стиль" 2026-07-08):
 *   - Orange title, gold accent words, italic hand-written comments
 *   - Staggered fade-in: background → logo → title → body → cta
 *   - Glassmorphism card with neumorphic inner shadow
 *   - Progress dots at the bottom (4 dots, active = orange glow)
 *
 * Each screen is one thought. The user doesn't see a list of
 * features — they see a story. (See D:/tests/syte/wizard-onboarding.html
 * for the full plan.)
 *
 * Flow:
 *   0 "Welcome"      → personal greeting, promise
 *   1 "Что это"       → not a chat. a team.
 *   2 "Как устроен"   → голова думает, исполнители делают, канбан показывает
 *   3 "Что дальше"    → через 2 минуты — рабочая среда
 *   → ProviderStep (вне этого файла)
 */

import { useState, useEffect, useRef } from 'react'
import './WelcomeStep.css'

interface WelcomeStepProps {
  onNext: () => void
  onSkip: () => void
}

const SCREENS = [
  {
    id: 'welcome',
    // Title fades in with stagger. Body is "you" voice (second person).
    title: 'Добро пожаловать в SynPin',
    // gold word "штат" inside the body, hand-written italic comment on the side
    body: (
      <>
        Твой <em className="hl">штат</em> AI-сотрудников.
        <span className="comment">// каждый со своей ролью</span>
      </>
    ),
    bodyDelay: 200,
  },
  {
    id: 'what',
    title: 'Не чат. Команда.',
    body: (
      <>
        SynPin — <em className="hl">операционная система</em> для агентов.
        <br />
        Они <em className="hl">живут</em>, пока ты спишь: ставят напоминания, ведут канбан, эскалируют заблокированное.
        <span className="comment">// не форма с кнопкой. процесс.</span>
      </>
    ),
    bodyDelay: 200,
  },
  {
    id: 'how',
    title: 'Голова думает. Руки делают.',
    body: (
      <>
        <em className="hl">Главный агент</em> координирует.
        <br />
        <em className="hl">Исполнители</em> ведут задачи.
        <br />
        <em className="hl">Канбан</em> показывает прогресс.
        <span className="comment">// иерархия, не очередь чатов</span>
      </>
    ),
    bodyDelay: 200,
  },
  {
    id: 'promise',
    title: 'Через 2 минуты — готово.',
    body: (
      <>
        Один провайдер. Один агент. Один отдел.
        <br />
        Всё остальное — потом, когда захочешь.
        <span className="comment">// ничего больше не нужно прямо сейчас</span>
      </>
    ),
    bodyDelay: 200,
  },
] as const

export function WelcomeStep({ onNext, onSkip }: WelcomeStepProps) {
  const [step, setStep] = useState(0)
  const [mounted, setMounted] = useState(false)
  const stepRef = useRef(step)
  stepRef.current = step

  // First-mount trigger — gates the entire fade-in sequence. Without
  // this, every state change re-fires the stagger from 0 and the
  // animation looks like a strobe.
  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 50)
    return () => clearTimeout(t)
  }, [])

  const current = SCREENS[step]
  const isLast = step === SCREENS.length - 1
  const isFirst = step === 0

  // Step transition: reset mounted, then re-fade. Each step gets its
  // own animation run, so transitions feel like deliberate beats.
  useEffect(() => {
    setMounted(false)
    const t = setTimeout(() => setMounted(true), 100)
    return () => clearTimeout(t)
  }, [step])

  const handleNext = () => {
    if (isLast) {
      onNext()
    } else {
      setStep(s => s + 1)
    }
  }

  const handleBack = () => {
    if (!isFirst) setStep(s => s - 1)
  }

  return (
    <div className="wizard-card wizard-onboarding">
      {/* Animated ambient glow — larger than the regular wizard
          background, with subtle pulse. The pulse is timed so the
          user notices it without it being distracting. */}
      <div className="onboarding-glow" />

      {/* Logo — fades in first, holds throughout. On the last screen
          it gets a slight scale-up to feel like a "stamp of completion"
          before the CTA. */}
      <div className={`wizard-logo onboarding-logo ${mounted ? 'visible' : ''}`}>
        <span className="logo-syn">Syn</span>
        <span className="logo-pin">Pin</span>
      </div>

      {/* Title — the headline. Stagger in 200ms after logo. */}
      <h1
        className={`wizard-title onboarding-title ${mounted ? 'visible' : ''}`}
        style={{ transitionDelay: '200ms' }}
      >
        {current.title}
      </h1>

      {/* Body — the story beat. Stagger in 400ms. */}
      <p
        className={`wizard-subtitle onboarding-body ${mounted ? 'visible' : ''}`}
        style={{ transitionDelay: `${200 + current.bodyDelay}ms` }}
      >
        {current.body}
      </p>

      {/* Controls — appear at 600ms. The CTA is only "Поехали" on the
          last screen; earlier screens just show "Дальше". */}
      <div
        className={`onboarding-controls ${mounted ? 'visible' : ''}`}
        style={{ transitionDelay: '600ms' }}
      >
        {!isFirst && (
          <button className="wizard-btn-back" onClick={handleBack}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 12H5M12 19l-7-7 7-7" />
            </svg>
            Назад
          </button>
        )}

        <button className="wizard-btn-primary onboarding-cta" onClick={handleNext}>
          {isLast ? 'Поехали' : 'Дальше'}
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M5 12h14M12 5l7 7-7 7" />
          </svg>
        </button>
      </div>

      {/* Progress dots — 4 dots, active = orange with glow. Clicking
          a dot jumps directly to that screen. */}
      <div
        className={`onboarding-dots ${mounted ? 'visible' : ''}`}
        style={{ transitionDelay: '800ms' }}
      >
        {SCREENS.map((s, i) => (
          <button
            key={s.id}
            className={`onboarding-dot ${i === step ? 'active' : ''} ${i < step ? 'past' : ''}`}
            onClick={() => setStep(i)}
            aria-label={`Шаг ${i + 1}: ${s.title}`}
          />
        ))}
      </div>

      {/* Skip — only on the last screen, small. Earlier screens
          already have "Назад" + dots so there's always a way out. */}
      {isLast && (
        <button
          className={`wizard-skip onboarding-skip ${mounted ? 'visible' : ''}`}
          onClick={onSkip}
          style={{ transitionDelay: '1000ms' }}
        >
          Настрою позже
        </button>
      )}
    </div>
  )
}