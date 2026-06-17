/**
 * SettingsCard — reusable card wrapper for settings sections.
 *
 * Standardises the repeated pattern:
 *   <section className="settings-card [settings-card-disabled]">
 *     <h2 className="settings-card-title">Title [<span badge>]</h2>
 *     [<p className="settings-card-desc">...</p>]
 *     {children}
 *   </section>
 *
 * 41+ usages across SettingsPage and MemorySection.
 */

import { type ReactNode } from 'react'

interface SettingsCardProps {
  /** Section title (rendered as h2) */
  title: string
  /** Optional badge shown next to the title */
  badge?: string
  /** Optional description paragraph below the title */
  description?: string
  /** Dim the card and disable pointer events */
  disabled?: boolean
  /** Additional CSS class names */
  className?: string
  /** Inline styles (e.g. for one-off opacity overrides) */
  style?: React.CSSProperties
  /** Card content */
  children: ReactNode
}

export function SettingsCard({
  title,
  badge,
  description,
  disabled,
  className,
  style,
  children,
}: SettingsCardProps) {
  const classes = [
    'settings-card',
    disabled && 'settings-card-disabled',
    className,
  ].filter(Boolean).join(' ')

  return (
    <section className={classes} style={style}>
      <h2 className="settings-card-title">
        {title}
        {badge && <span className="settings-card-badge">{badge}</span>}
      </h2>
      {description && <p className="settings-card-desc">{description}</p>}
      {children}
    </section>
  )
}
