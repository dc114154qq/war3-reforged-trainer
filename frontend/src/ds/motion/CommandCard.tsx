import { useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useAnimate } from 'motion/react'
import { Icon } from '../icons/Icon'
import type { IconName } from '../icons/generated'
import { TooltipCard } from '../primitives/Tooltip'
import { DUR, SPRING } from '../tokens'
import { isTypingTarget } from '../util'
import s from './CommandCard.module.css'

/** Grid order of the 4×3 card, matching the classic grid hotkey layout. */
export const GRID_KEYS = ['Q', 'W', 'E', 'R', 'A', 'S', 'D', 'F', 'Z', 'X', 'C', 'V'] as const
export type GridKey = (typeof GRID_KEYS)[number]

export interface CommandSpec {
  key: GridKey
  icon: IconName
  title: string
  description: string
  onPress(): void
  /** True while the backend call runs. Drives the cooldown sweep; presses are ignored meanwhile. */
  pending?: boolean
  /** Typical duration of the call. The sweep reaches 90% at this point and waits for the result. */
  estimateMs?: number
  /** For toggles: true when on (gold rim). Leave undefined for one-shot commands. */
  active?: boolean
  disabled?: boolean
}

interface CommandCardProps {
  commands: CommandSpec[]
  /** Listen for Q…V on the window. Off while another surface owns the keyboard. */
  hotkeys?: boolean
  /** Stagger the slots in; use only for the connect moment. */
  entrance?: boolean
  label?: string
}

/**
 * The 4×3 command card. Empty keys show as sunken sockets, as in the game. The tooltip
 * appears at a fixed spot above the card instead of following the pointer.
 */
export function CommandCard({ commands, hotkeys = true, entrance = false, label = '命令卡' }: CommandCardProps) {
  const byKey = new Map(commands.map(c => [c.key, c]))
  const latest = useRef(byKey)
  latest.current = byKey
  const [tip, setTip] = useState<GridKey | null>(null)
  const [press, setPress] = useState<{ key: GridKey; n: number } | null>(null)

  const trigger = useCallback((cmd: CommandSpec) => {
    if (cmd.disabled || cmd.pending) return
    setPress(p => ({ key: cmd.key, n: (p?.n ?? 0) + 1 }))
    cmd.onPress()
  }, [])

  useEffect(() => {
    if (!hotkeys) return
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.altKey || e.metaKey || e.repeat || isTypingTarget(e.target)) return
      if (document.querySelector('[role="dialog"]')) return
      const cmd = latest.current.get(e.key.toUpperCase() as GridKey)
      if (!cmd) return
      e.preventDefault()
      trigger(cmd)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [hotkeys, trigger])

  const tipCmd = tip ? byKey.get(tip) : undefined

  return (
    <section className={s.card} aria-label={label}>
      <div className={s.grid}>
        {GRID_KEYS.map((k, i) => {
          const cmd = byKey.get(k)
          return cmd ? (
            <CommandButton
              key={k}
              spec={cmd}
              index={i}
              entrance={entrance}
              pressN={press?.key === k ? press.n : 0}
              onTrigger={() => trigger(cmd)}
              onTip={setTip}
            />
          ) : (
            <span key={`socket-${k}`} className={s.socket} aria-hidden="true" />
          )
        })}
      </div>
      <AnimatePresence>
        {tipCmd && (
          <motion.div
            className={s.tip}
            role="tooltip"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, transition: { duration: 0.08 } }}
            transition={{ duration: DUR.press }}
          >
            <TooltipCard
              title={tipCmd.title}
              hotkey={tipCmd.key}
              footer={tipCmd.active === undefined ? undefined : tipCmd.active ? '已开启' : '未开启'}
            >
              {tipCmd.description}
            </TooltipCard>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  )
}

function CommandButton({ spec, index, entrance, pressN, onTrigger, onTip }: {
  spec: CommandSpec
  index: number
  entrance: boolean
  pressN: number
  onTrigger(): void
  onTip(key: GridKey | null): void
}) {
  const [scope, animate] = useAnimate<HTMLButtonElement>()
  const sweepRef = useRef<HTMLSpanElement>(null)
  const running = useRef<Animation | null>(null)
  const [flash, setFlash] = useState(0)
  const estimate = spec.estimateMs ?? 800

  // Same press feedback for clicks and hotkeys.
  useEffect(() => {
    if (!pressN || !scope.current) return
    animate(scope.current, { scale: [1, 0.9, 1], filter: ['brightness(1)', 'brightness(0.72)', 'brightness(1)'] }, { duration: 0.22, times: [0, 0.35, 1] })
  }, [pressN, animate, scope])

  // Cooldown sweep: run to 90% over the estimate and hold; when the call returns,
  // finish the turn quickly and flash the rim.
  useEffect(() => {
    const el = sweepRef.current
    if (!el) return
    if (spec.pending) {
      running.current?.cancel()
      el.dataset.on = ''
      running.current = el.animate(
        [{ '--sweep': '0deg' }, { '--sweep': '324deg' }],
        { duration: estimate, easing: 'cubic-bezier(0.25, 0.6, 0.35, 1)', fill: 'forwards' },
      )
      return
    }
    const current = running.current
    if (!current) return
    const from = getComputedStyle(el).getPropertyValue('--sweep').trim() || '0deg'
    current.cancel()
    const finish = el.animate([{ '--sweep': from }, { '--sweep': '360deg' }], { duration: 140, easing: 'ease-out', fill: 'forwards' })
    running.current = finish
    finish.onfinish = () => {
      if (running.current !== finish) return
      delete el.dataset.on
      finish.cancel()
      running.current = null
      setFlash(n => n + 1)
    }
  }, [spec.pending, estimate])

  useEffect(() => () => running.current?.cancel(), [])

  return (
    <motion.div
      className={s.slot}
      initial={entrance ? { opacity: 0, scale: 0.8 } : false}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ ...SPRING.pop, delay: entrance ? 0.46 + index * 0.025 : 0 }}
    >
      <button
        ref={scope}
        type="button"
        className={s.cmd}
        disabled={spec.disabled}
        aria-label={`${spec.title}（${spec.key}）`}
        aria-pressed={spec.active}
        aria-busy={spec.pending || undefined}
        data-autocast={spec.active || undefined}
        data-testid={`cmd-${spec.key}`}
        onClick={onTrigger}
        onPointerEnter={() => onTip(spec.key)}
        onPointerLeave={() => onTip(null)}
        onFocus={() => onTip(spec.key)}
        onBlur={() => onTip(null)}
      >
        <Icon name={spec.icon} className={s.icon} />
        <span className={s.hotkey}>{spec.key}</span>
        <span ref={sweepRef} className={s.sweep} />
        {flash > 0 && <span key={flash} className={s.flash} />}
        {spec.active && <span className={s.autocast} />}
      </button>
    </motion.div>
  )
}
