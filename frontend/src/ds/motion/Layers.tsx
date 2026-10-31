import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { create } from 'zustand'
import { DUR } from '../tokens'
import { rectOf } from '../util'
import s from './Layers.module.css'

/* ---- Bounty text ------------------------------------------------------------------ */

export type BountyTone = 'gold' | 'lumber' | 'plain'

interface BountyItem { id: number; x: number; y: number; text: string; tone: BountyTone }

const useBounties = create<{ items: BountyItem[] }>(() => ({ items: [] }))
let seq = 1

export interface BountyOptions {
  /** Element or rect the text starts from. */
  anchor: Element | DOMRect | null | undefined
  text: string
  tone?: BountyTone
  /** above: rises off the anchor (a changed value). below: rises into it (a counter in the top band). */
  from?: 'above' | 'below'
}

/**
 * Float a "+N" like the gold a peasant brings home: constant rise,
 * two seconds of life, fading after the first. Needs <BountyLayer> mounted (DsProvider does it).
 */
export function bounty({ anchor, text, tone = 'plain', from = 'above' }: BountyOptions) {
  const rect = rectOf(anchor)
  if (!rect) return
  const y = from === 'below' ? rect.bottom + 34 : rect.top - 6
  useBounties.setState(st => ({ items: [...st.items, { id: seq++, x: rect.left, y, text, tone }] }))
}

export function BountyLayer() {
  const items = useBounties(st => st.items)
  const remove = (id: number) => useBounties.setState(st => ({ items: st.items.filter(i => i.id !== id) }))
  return (
    <div className={s.bountyLayer} aria-hidden="true">
      {items.map(item => (
        <motion.span
          key={item.id}
          className={s.bounty}
          data-tone={item.tone}
          style={{ left: item.x, top: item.y }}
          initial={{ y: 0, opacity: 1 }}
          animate={{ y: -50, opacity: [1, 1, 0] }}
          transition={{ y: { duration: DUR.bounty, ease: 'linear' }, opacity: { duration: DUR.bounty, times: [0, 0.5, 1] } }}
          onAnimationComplete={() => remove(item.id)}
        >
          {item.text}
        </motion.span>
      ))}
    </div>
  )
}

/* ---- Announcer: the game's yellow message text ------------------------------------- */

interface Line { id: number; text: string }
const useAnnouncements = create<{ line: Line | null }>(() => ({ line: null }))

/**
 * Short yellow line above the console, like "not enough gold". For results and simple
 * failures; anything that needs detail or a decision goes in a <Dialog>.
 */
export function announce(text: string) {
  useAnnouncements.setState({ line: { id: seq++, text } })
}

export function Announcer() {
  const line = useAnnouncements(st => st.line)
  const [shown, setShown] = useState<Line | null>(null)

  useEffect(() => {
    if (!line) return
    setShown(line)
    const t = window.setTimeout(() => setShown(cur => (cur?.id === line.id ? null : cur)), 3000)
    return () => window.clearTimeout(t)
  }, [line])

  return (
    <div className={s.announcer} role="status" aria-live="polite">
      <AnimatePresence>
        {shown && (
          <motion.p
            key={shown.id}
            className={s.announcement}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, transition: { duration: 0.4 } }}
            transition={{ duration: DUR.press }}
          >
            {shown.text}
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  )
}
