import { useEffect, useRef, useState, type ReactNode } from 'react'

/**
 * PageTransition — unified fade-out/fade-in on content swap.
 *
 * Used for two levels of the SynPin app:
 *  1. Top-level main content (kanban ↔ settings ↔ otdel-chat ↔ chat).
 *  2. Settings page tab content (general ↔ agents ↔ providers ↔ ...).
 *
 * Behaviour:
 *  - On first mount, no animation — the page just appears. The very
 *    first connect keeps its existing soft entrance from
 *    `.main-area`; PageTransition shouldn't stack on top of that.
 *  - On any subsequent `pageKey` change, fade out (opacity 0,
 *    FADE_OUT_MS), swap children, fade in (opacity 1, FADE_IN_MS).
 *
 * Why opacity only, no transform:
 *  - opacity composites on the GPU, no reflow, no paint.
 *  - `transform: translateY(…)` (the more common slide-up pattern)
 *    has been the cause of multiple "throb" bugs in this app
 *    (scrollbar visibility flips when the transform resolves, micro
 *    layout shift at animation end). Sticking to opacity avoids the
 *    entire class of bug.
 *
 * Timing values (FADE_OUT_MS, FADE_IN_MS) MUST match the CSS animation
 * durations in index.css. Mismatch leaves a visible "stuck at opacity
 * 0" gap between the two phases.
 */

const FADE_OUT_MS = 200
const FADE_DURATION_MS = FADE_OUT_MS // alias for the swap timer (must match the longer phase)

export interface PageTransitionProps {
  /** Unique key for the current "page" — change triggers a transition. */
  pageKey: string
  children: ReactNode
}

type Phase = 'in' | 'out'

export function PageTransition({ pageKey, children }: PageTransitionProps) {
  // First-mount sentinel. We use a ref (not state) because we never
  // need to re-render based on it — only the effect below reads it.
  const isFirstRender = useRef(true)
  // The children we last rendered. Stays stable while we fade out,
  // then we swap to the new children before fading in.
  const [renderedChildren, setRenderedChildren] = useState<ReactNode>(children)
  const [renderedKey, setRenderedKey] = useState<string>(pageKey)
  const [phase, setPhase] = useState<Phase>('in')

  useEffect(() => {
    // Skip the animation on the very first render.
    if (isFirstRender.current) {
      isFirstRender.current = false
      return
    }
    // Already in sync — no-op. Guards against re-renders that don't
    // actually change the page (parent state churn).
    if (pageKey === renderedKey) return

    // 1. Fade out current.
    setPhase('out')

    // 2. After fade-out completes, swap children + fade in.
    const t = setTimeout(() => {
      setRenderedKey(pageKey)
      setRenderedChildren(children)
      setPhase('in')
    }, FADE_DURATION_MS)

    return () => clearTimeout(t)
    // We intentionally exclude `children` from deps — the parent
    // re-renders often but only the `pageKey` change drives the
    // transition. We snapshot the children at swap time via the
    // setter call above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageKey, renderedKey])

  return (
    <div
      className="page-transition"
      data-phase={phase}
      aria-busy={phase === 'out' ? 'true' : undefined}
    >
      {renderedChildren}
    </div>
  )
}
