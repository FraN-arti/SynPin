/**
 * Toggle — reusable settings toggle switch.
 * Extracted from SettingsPage.tsx.
 *
 * The visual track + knob are drawn via `::before` (track) and
 * `::after` (knob) on the <label>, not on <input>. Pseudo-elements
 * on <input type="checkbox"> have flaky cross-browser support for
 * `position: absolute` + `transform` — Edge/older Chrome render the
 * knob offset from the input instead of inside it.
 *
 * The real <input> is hidden but still clickable; clicking the
 * label toggles it (native label/checkbox association).
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
        <span className="settings-toggle-label">{label}</span>
      </label>
      {description && (
        <span className="settings-toggle-desc">{description}</span>
      )}
    </div>
  )
}