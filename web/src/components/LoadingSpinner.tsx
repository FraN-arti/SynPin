/**
 * LoadingSpinner — reusable centered loading indicator.
 *
 * Renders a pulsing ring with ambient glow + text label.
 * Uses CSS variables for theming (--accent colors).
 *
 * Usage:
 *   <LoadingSpinner text="Загрузка доски..." />
 *   <LoadingSpinner text="Загрузка..." />
 */

interface LoadingSpinnerProps {
  /** Text label shown below the spinner */
  text?: string
  /** Override min-height (default 120px) */
  minHeight?: number
}

export function LoadingSpinner({ text, minHeight }: LoadingSpinnerProps) {
  return (
    <div className="loading-spinner" style={minHeight ? { minHeight } : undefined}>
      <div className="loading-ring">
        <div className="loading-ring-glow" />
      </div>
      {text && <div className="loading-text">{text}</div>}
    </div>
  )
}
