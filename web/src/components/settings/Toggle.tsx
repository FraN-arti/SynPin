/**
 * Toggle — reusable settings toggle switch.
 * Extracted from SettingsPage.tsx.
 */

export function Toggle({
  label,
  description,
  defaultChecked,
  checked,
  onChange,
}: {
  label: string
  description?: string
  defaultChecked?: boolean
  checked?: boolean
  onChange?: (v: boolean) => void
}) {
  const isControlled = checked !== undefined
  return (
    <div className="settings-field-row">
      <label className="settings-toggle">
        <input
          type="checkbox"
          {...(isControlled ? { checked } : { defaultChecked })}
          onChange={e => onChange?.(e.target.checked)}
        />
        <span>{label}</span>
      </label>
      {description && (
        <span className="settings-toggle-desc">{description}</span>
      )}
    </div>
  )
}
