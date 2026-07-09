/**
 * BootLoader — shown in the brief moment between App mount and the
 * first routing decision (setup check, agent load, etc). Replaces
 * the empty-state flash with a branded splash that matches the
 * index.html boot loader, but rendered via React (so it can
 * react to theme state and disappear smoothly).
 *
 * Why not just let the index.html loader handle it? Because the
 * HTML loader has no idea what comes next — it can't show "checking
 * setup" or "loading agents". The App's loader is the second leg
 * of the same handshake: HTML loader paints the dark/light bg +
 * the SynPin mark, App's loader takes over the moment React
 * mounts and shows the in-app progress (or just holds the mark
 * while async checks run).
 */
import './BootLoader.css'

interface BootLoaderProps {
  /** Optional short status line under the bar. */
  status?: string
}

export function BootLoader({ status }: BootLoaderProps) {
  return (
    <div className="app-boot-loader">
      <div className="app-boot-mark">
        <span className="syn">Syn</span>
        <span className="pin">Pin</span>
      </div>
      <div className="app-boot-bar" />
      {status && <div className="app-boot-status">{status}</div>}
    </div>
  )
}