import { useCallback, useRef, useState, type ReactNode } from 'react'
import { cx } from '../../../ds'
import s from './Layout.module.css'

/** Scrolling body of a page. Pages that manage their own scrolling (tables) pass fill. */
export function PageBody({ children, fill = false, className }: { children: ReactNode; fill?: boolean; className?: string }) {
  return <div className={cx(s.body, fill && s.fill, className)}>{children}</div>
}

/**
 * A titled block inside a page: serif label with a hairline, actions on the right.
 * Plain structure, no card: pages are documents, not dashboards.
 */
export function Section({ title, actions, children, className, id }: {
  title: ReactNode
  actions?: ReactNode
  children?: ReactNode
  className?: string
  id?: string
}) {
  return (
    <section className={cx(s.section, className)} aria-labelledby={id}>
      <header className={s.head}>
        <h2 className={s.title} id={id}>{title}</h2>
        {actions && <div className={s.actions}>{actions}</div>}
      </header>
      {children}
    </section>
  )
}

/** A row of controls. */
export function Row({ children, className, wrap = true }: { children: ReactNode; className?: string; wrap?: boolean }) {
  return <div className={cx(s.row, !wrap && s.nowrap, className)}>{children}</div>
}

/** Short explanation under a section title. */
export function Hint({ children }: { children: ReactNode }) {
  return <p className={s.hint}>{children}</p>
}

/** Result or progress line; errors in red, announced to screen readers. */
export function Status({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'error' | 'busy' }) {
  if (!children) return null
  return <p className={s.status} data-tone={tone} role={tone === 'error' ? 'alert' : 'status'}>{children}</p>
}

/**
 * Track which async actions are running, by key, so buttons and command-card slots can
 * show progress and refuse a second press.
 */
export function usePending() {
  const [pending, setPending] = useState<Record<string, boolean>>({})
  // The ref, not state, decides: state updates are not visible until the next render.
  const inflight = useRef(new Set<string>())
  const run = useCallback(async <T,>(key: string, fn: () => Promise<T>): Promise<T | undefined> => {
    if (inflight.current.has(key)) return undefined
    inflight.current.add(key)
    setPending(p => ({ ...p, [key]: true }))
    try {
      return await fn()
    } catch {
      return undefined // callApi already reported it
    } finally {
      inflight.current.delete(key)
      setPending(p => ({ ...p, [key]: false }))
    }
  }, [])
  return { pending, run }
}
