import { useEffect, useRef } from 'react'
import { motion } from 'motion/react'
import { Icon } from '../icons/Icon'
import { cx } from '../util'
import s from './Bars.module.css'

/** In-game health colour: green, then yellow, then red as the bar empties. */
export function lifeGradient(ratio: number): string {
  if (ratio > 0.66) return 'linear-gradient(180deg, #52dc63 0%, #2aa23c 55%, #1b7a2b 100%)'
  if (ratio > 0.33) return 'linear-gradient(180deg, #f3d553 0%, #c99b1b 55%, #9a720c 100%)'
  return 'linear-gradient(180deg, #f2674a 0%, #c43420 55%, #8f1a10 100%)'
}

const clamp01 = (n: number) => Math.min(1, Math.max(0, n))
const fmt = (n: number) => String(Number(n.toFixed(1)))

export interface StatBarProps {
  kind: 'life' | 'mana'
  value: number
  max: number
  /** Shows the frost overlay when the value is locked. */
  frozen?: boolean
  /** Hide the 生命/魔法 label, e.g. in the compact console. */
  bare?: boolean
  /** Label text; defaults to 生命 or 魔法. Pass the translated text in English mode. */
  label?: string
  className?: string
}

/**
 * Life or mana bar. When the value drops, a pale trail stays where the bar was and
 * catches up 350 ms later, so damage reads at a glance.
 */
export function StatBar({ kind, value, max, frozen = false, bare = false, label: labelText, className }: StatBarProps) {
  const ratio = max > 0 ? clamp01(value / max) : 0
  const prev = useRef(ratio)
  const falling = ratio < prev.current - 1e-6
  useEffect(() => { prev.current = ratio })
  const width = `${ratio * 100}%`
  const label = labelText ?? (kind === 'life' ? '生命' : '魔法')

  return (
    <div
      className={cx(s.bar, bare && s.bare, className)}
      data-kind={kind}
      data-frozen={frozen || undefined}
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
    >
      {!bare && <span className={s.label}>{label}</span>}
      <div className={s.track}>
        <motion.i
          className={s.ghost}
          initial={false}
          animate={{ width }}
          transition={falling ? { delay: 0.35, duration: 0.55, ease: [0.3, 0, 0.2, 1] } : { duration: 0.2 }}
        />
        <motion.i
          className={s.fill}
          initial={false}
          animate={{ width }}
          transition={{ duration: 0.2, ease: 'easeOut' }}
          style={kind === 'life' ? { background: lifeGradient(ratio) } : undefined}
        />
        {frozen && <Icon name="lock" tone="current" className={s.frozenIcon} />}
        <span className={s.text}>{fmt(value)} / {Math.round(max)}</span>
      </div>
    </div>
  )
}

/** Hero experience: thin purple bar with the next threshold on the right. */
export function XpBar({ xp, floor, next, className }: { xp: number; floor: number; next: number | null; className?: string }) {
  const ratio = next ? clamp01((xp - floor) / (next - floor)) : 1
  return (
    <div className={cx(s.xp, className)} role="meter" aria-label="经验" aria-valuenow={xp} aria-valuemin={floor} aria-valuemax={next ?? xp}>
      <span className={s.xpTrack}><i style={{ width: `${ratio * 100}%` }} /></span>
      <span className={s.xpText}>{next ? `经验 ${xp} / ${next}` : '已满级'}</span>
    </div>
  )
}

/**
 * The loading-screen bar: a sunken channel filling with molten gold.
 * Without max it runs indeterminate (a glint sweeping the channel).
 */
export function ProgressBar({ value = 0, max, label, className }: { value?: number; max?: number; label: string; className?: string }) {
  const determinate = max !== undefined && max > 0
  const ratio = determinate ? clamp01(value / max) : 0
  return (
    <div
      className={cx(s.progress, className)}
      role="progressbar"
      aria-label={label}
      aria-valuemin={determinate ? 0 : undefined}
      aria-valuemax={determinate ? max : undefined}
      aria-valuenow={determinate ? value : undefined}
      data-indeterminate={!determinate || undefined}
    >
      <i style={determinate ? { width: `${ratio * 100}%` } : undefined} />
    </div>
  )
}
