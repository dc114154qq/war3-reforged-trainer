import { useEffect, useRef, useState, type ReactNode } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { Button, RawcodePlate, announce } from '../../../ds'
import { api } from '../../../lib/api'
import { useSystem } from '../../state/system'
import { fill, t as tr, useT } from '../../i18n'
import s from './Codex.module.css'

/**
 * The codex layout: a searchable list on the left and, for the selected entry, a sheet of
 * vellum sliding in from the right, like a page pulled from a tome.
 */
export function CodexLayout({ toolbar, list, sheet, footer }: {
  toolbar: ReactNode
  list: ReactNode
  /** The open entry; null closes the sheet. */
  sheet: { key: string; content: ReactNode } | null
  footer?: ReactNode
}) {
  const reduce = useReducedMotion()
  return (
    <div className={s.codex}>
      <div className={s.main}>
        <div className={s.toolbar}>{toolbar}</div>
        <div className={s.list}>{list}</div>
        {footer && <p className={s.footer}>{footer}</p>}
      </div>
      <AnimatePresence mode="wait" initial={false}>
        {sheet && (
          <motion.aside
            key={sheet.key}
            className={s.sheet}
            initial={reduce ? { opacity: 0 } : { opacity: 0, x: 28 }}
            animate={{ opacity: 1, x: 0 }}
            exit={reduce ? { opacity: 0 } : { opacity: 0, x: 16 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          >
            {sheet.content}
          </motion.aside>
        )}
      </AnimatePresence>
    </div>
  )
}

/** Header of a sheet: rawcode, name, a second name and small facts. */
export function SheetHead({ code, name, sub, facts }: { code: string; name: string; sub?: string; facts?: ReactNode }) {
  return (
    <header className={s.sheetHead}>
      <RawcodePlate code={code} />
      <h2 className={s.sheetName}>{name || code}</h2>
      {sub && <p className={s.sheetSub}>{sub}</p>}
      {facts && <div className={s.facts}>{facts}</div>}
    </header>
  )
}

export function SheetText({ children }: { children: ReactNode }) {
  return <div className={s.sheetText}>{children}</div>
}

export function SheetActions({ children }: { children: ReactNode }) {
  return <footer className={s.sheetActions}>{children}</footer>
}

export function Fact({ label, children }: { label: string; children: ReactNode }) {
  return <span className={s.fact}><span className={s.factLabel}>{label}</span>{children}</span>
}

/** Search text that waits for typing to pause before it counts. */
export function useDebounced<T>(value: T, ms = 250): T {
  const [settled, setSettled] = useState(value)
  useEffect(() => {
    const id = window.setTimeout(() => setSettled(value), ms)
    return () => window.clearTimeout(id)
  }, [value, ms])
  return settled
}

/**
 * Run a search whenever its inputs change, dropping answers that arrive after a newer
 * request went out. Also re-runs when the language changes (names come back translated).
 */
export function useSearch<T>(fetch: () => Promise<T>, deps: unknown[]): { data: T | null; loading: boolean } {
  const language = useSystem(st => st.status.language)
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(false)
  const revision = useRef(0)
  useEffect(() => {
    const mine = ++revision.current
    setLoading(true)
    fetch().then(
      result => { if (mine === revision.current) setData(result) },
      () => {},
    ).finally(() => { if (mine === revision.current) setLoading(false) })
    return () => { revision.current++ }
  }, [...deps, language]) // eslint-disable-line react-hooks/exhaustive-deps
  return { data, loading }
}

export async function copyCode(code: string) {
  try {
    await navigator.clipboard.writeText(code)
    announce(fill(tr('已复制 {code}'), { code }))
  } catch {
    window.dispatchEvent(new CustomEvent('war3-error', { detail: '复制失败，请选中完整文字后复制。' }))
  }
}

/** Give the selected unit an item, ability or new unit through the Elephant actions. */
export function GiveButton({ action, params, label, done }: { action: string; params: Record<string, unknown>; label: string; done: string }) {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const [busy, setBusy] = useState(false)
  const give = async () => {
    setBusy(true)
    try {
      const result = await api.executeElephantAction(action, params)
      if (result?.success) announce(done)
      else window.dispatchEvent(new CustomEvent('war3-error', { detail: result?.error || '操作未完成' }))
    } catch {
      // reported by callApi
    } finally {
      setBusy(false)
    }
  }
  return (
    <Button variant="cast" icon={action === 'add_ability' ? 'add-ability' : 'add-item'} disabled={!connected || busy} onClick={() => void give()} title={connected ? undefined : t('连接游戏后可用')}>
      {label}
    </Button>
  )
}

/** Match and catalogue counts; the backend sends at most 200 rows, so say when the list is cut. */
export function Count({ match, total, shown, loading }: { match: number; total: number; shown: number; loading?: boolean }) {
  const t = useT()
  return (
    <span className={s.count} data-loading={loading || undefined}>
      {fill(t('匹配 {match} / 收录 {total}'), { match, total })}
      {shown < match && `　${fill(t('只列出前 {n} 条，请缩小搜索范围'), { n: shown })}`}
    </span>
  )
}
