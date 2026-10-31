import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Button } from '../primitives/Button'
import type { IconName } from '../icons/generated'
import s from './HoldToConfirm.module.css'

interface HoldToConfirmProps {
  children: ReactNode
  onConfirm(): void
  /** How long to hold, in ms. */
  holdMs?: number
  icon?: IconName
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
}

const offsetOf = (el: SVGElement) => Number.parseFloat(getComputedStyle(el).strokeDashoffset) || 0

/**
 * Destructive actions without a modal: press and hold until the rim fills.
 * Letting go early drains the rim and shows a hint. Space and Enter work the same way.
 * The action fires from the rim animation's own finish, so the rim is always full when it runs.
 */
export function HoldToConfirm({ children, onConfirm, holdMs = 600, icon, size = 'md', disabled }: HoldToConfirmProps) {
  const [holding, setHolding] = useState(false)
  const [hint, setHint] = useState(false)
  const [confirmed, setConfirmed] = useState(0)
  const rimRef = useRef<SVGRectElement>(null)
  const anim = useRef<Animation | null>(null)
  const hintTimer = useRef<number | undefined>(undefined)
  const confirm = useRef(onConfirm)
  confirm.current = onConfirm

  useEffect(() => () => { anim.current?.cancel(); window.clearTimeout(hintTimer.current) }, [])

  const start = () => {
    const rim = rimRef.current
    if (disabled || !rim || holding) return
    // Resume from wherever a drain left the rim (1 = empty, 0 = full).
    const from = offsetOf(rim)
    anim.current?.cancel()
    setHolding(true)
    setHint(false)
    const fill = rim.animate([{ strokeDashoffset: from }, { strokeDashoffset: 0 }], { duration: holdMs * from, easing: 'linear', fill: 'forwards' })
    anim.current = fill
    fill.onfinish = () => {
      if (anim.current !== fill) return
      fill.cancel()
      anim.current = null
      setHolding(false)
      setConfirmed(n => n + 1)
      confirm.current()
    }
  }

  const release = () => {
    const rim = rimRef.current
    if (!holding || !rim) return
    const from = offsetOf(rim)
    anim.current?.cancel()
    const drain = rim.animate([{ strokeDashoffset: from }, { strokeDashoffset: 1 }], { duration: 150, easing: 'ease-out' })
    anim.current = drain
    setHolding(false)
    setHint(true)
    window.clearTimeout(hintTimer.current)
    hintTimer.current = window.setTimeout(() => setHint(false), 1600)
  }

  const isHoldKey = (key: string) => key === ' ' || key === 'Enter'

  return (
    <Button
      variant="danger"
      size={size}
      icon={icon}
      disabled={disabled}
      data-holding={holding || undefined}
      className={s.button}
      aria-description={`按住 ${holdMs / 1000} 秒确认`}
      onPointerDown={e => { if (e.button === 0) start() }}
      onPointerUp={release}
      onPointerLeave={release}
      onPointerCancel={release}
      onKeyDown={e => { if (isHoldKey(e.key)) { e.preventDefault(); if (!e.repeat) start() } }}
      onKeyUp={e => { if (isHoldKey(e.key)) { e.preventDefault(); release() } }}
      onBlur={release}
    >
      {hint ? '按住不放以确认' : children}
      <svg className={s.rim} aria-hidden="true">
        <rect ref={rimRef} x="1" y="1" pathLength={1} />
      </svg>
      {confirmed > 0 && <span key={confirmed} className={s.flash} />}
    </Button>
  )
}
