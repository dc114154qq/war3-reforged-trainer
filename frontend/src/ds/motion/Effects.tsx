import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { DUR } from '../tokens'
import s from './Effects.module.css'

/* ---- Frost: the lock visual -------------------------------------------------------- */

const SHARDS = [
  { clip: 'polygon(0 0, 38% 0, 30% 55%, 0 100%)', x: -7, y: 12, r: -9 },
  { clip: 'polygon(38% 0, 70% 0, 58% 48%, 30% 55%)', x: -2, y: 9, r: 5 },
  { clip: 'polygon(70% 0, 100% 0, 100% 100%, 62% 100%, 58% 48%)', x: 6, y: 13, r: 10 },
  { clip: 'polygon(0 100%, 30% 55%, 58% 48%, 62% 100%)', x: 1, y: 16, r: -4 },
]

/**
 * Lay inside a positioned value cell. Locking spreads frost in from the right edge (where
 * the lock button sits); unlocking cracks it and drops the shards. Bump `pulse` each time
 * the lock holds a value against the game, and the ice flashes once.
 *
 * Mounting while already locked shows the ice without the spread, so re-rendered lists
 * do not replay it.
 */
export function Frost({ locked, pulse = 0 }: { locked: boolean; pulse?: number }) {
  const [phase, setPhase] = useState<'off' | 'on' | 'shatter'>(locked ? 'on' : 'off')
  const lockedAtMount = useRef(locked)
  const prev = useRef(locked)

  useEffect(() => {
    if (locked === prev.current) return
    prev.current = locked
    if (locked) {
      lockedAtMount.current = false
      setPhase('on')
      return
    }
    setPhase('shatter')
    const t = window.setTimeout(() => setPhase('off'), 460)
    return () => window.clearTimeout(t)
  }, [locked])

  if (phase === 'off') return null

  if (phase === 'shatter') {
    return (
      <span className={s.frost} aria-hidden="true">
        {SHARDS.map((sh, i) => (
          <motion.span
            key={i}
            className={s.ice}
            style={{ clipPath: sh.clip }}
            initial={{ opacity: 1 }}
            animate={{ x: sh.x, y: sh.y, rotate: sh.r, opacity: 0 }}
            transition={{ delay: 0.08, duration: 0.32, ease: [0.4, 0, 0.9, 0.6] }}
          />
        ))}
        <svg className={s.cracks} viewBox="0 0 100 100" preserveAspectRatio="none">
          <motion.path
            d="M38 0 L30 55 L0 100 M30 55 L58 48 L70 0 M58 48 L62 100"
            initial={{ pathLength: 0, opacity: 1 }}
            animate={{ pathLength: 1, opacity: [1, 1, 0] }}
            transition={{ duration: 0.36, times: [0, 0.3, 1] }}
          />
        </svg>
      </span>
    )
  }

  return (
    <motion.span
      className={`${s.frost} ${s.ice}`}
      aria-hidden="true"
      initial={lockedAtMount.current ? false : { clipPath: 'circle(0% at 100% 50%)' }}
      animate={{ clipPath: 'circle(160% at 100% 50%)' }}
      transition={{ duration: DUR.slow, ease: [0.2, 0.8, 0.2, 1] }}
    >
      <Crystals className={s.right} />
      <Crystals className={s.left} />
      {pulse > 0 && (
        <motion.span
          key={pulse}
          className={s.pulse}
          initial={{ opacity: 0.95 }}
          animate={{ opacity: 0 }}
          transition={{ duration: 0.7, ease: 'easeOut' }}
        />
      )}
    </motion.span>
  )
}

function Crystals({ className }: { className: string }) {
  return (
    <svg className={`${s.crystals} ${className}`} viewBox="0 0 64 36" preserveAspectRatio="xMaxYMid meet">
      <path d="M64 3 L50 10 L42 8 M50 10 L52 17 M50 10 L38 18 L30 16 M38 18 L39 25 M38 18 L33 26 M64 33 L52 27 L46 30 M52 27 L54 20 M52 27 L44 22 L40 24 M44 22 L43 15" />
    </svg>
  )
}

/* ---- Selection circle -------------------------------------------------------------- */

export type SelectionState = 'none' | 'hover' | 'selected'
export type Relation = 'ally' | 'neutral' | 'enemy'

const RING_COLOR: Record<Relation, string> = {
  ally: 'var(--select-ally)',
  neutral: 'var(--select-neutral)',
  enemy: 'var(--select-enemy)',
}

/**
 * The segmented circle under a selected unit: pops in with a spring when selected,
 * thin and yellow on hover. Place it absolutely under a portrait.
 */
export function SelectionRing({ state, relation = 'ally', className }: { state: SelectionState; relation?: Relation; className?: string }) {
  const selected = state === 'selected'
  const color = selected ? RING_COLOR[relation] : 'var(--select-neutral)'
  return (
    <AnimatePresence>
      {state !== 'none' && (
        <motion.svg
          key={state}
          className={className}
          viewBox="0 0 100 30"
          aria-hidden="true"
          style={{ overflow: 'visible' }}
          initial={{ opacity: 0, scale: selected ? 1.24 : 1 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, transition: { duration: 0.1 } }}
          transition={selected ? { type: 'spring', stiffness: 460, damping: 17 } : { duration: DUR.press }}
        >
          <ellipse
            cx="50"
            cy="15"
            rx="47"
            ry="12.5"
            fill="none"
            pathLength={100}
            strokeDasharray={selected ? '10.5 2' : '6 3'}
            stroke={color}
            strokeWidth={selected ? 2.6 : 1.3}
            opacity={selected ? 1 : 0.8}
            style={selected ? { filter: `drop-shadow(0 0 3px ${color})` } : undefined}
          />
        </motion.svg>
      )}
    </AnimatePresence>
  )
}
