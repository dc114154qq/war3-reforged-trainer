import { useEffect, useRef, useState } from 'react'
import { motion, type Transition } from 'motion/react'
import { useSystem } from '../state/system'
import { useT } from '../i18n'
import s from './DayNightClock.module.css'

type Phase = 'off' | 'connecting' | 'on'

/**
 * The Warcraft III day/night clock as the connection indicator: night while waiting,
 * a spin while connecting, sunrise once connected. Clicking it connects or refreshes.
 */
export function DayNightClock() {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const connecting = useSystem(st => st.connecting)
  const status = useSystem(st => st.status)
  const connect = useSystem(st => st.connect)
  const phase: Phase = connecting ? 'connecting' : connected ? 'on' : 'off'
  const [rotation, setRotation] = useState(connected ? 0 : 180)
  const first = useRef(true)

  useEffect(() => {
    if (first.current) {
      first.current = false
      return
    }
    // Rotation only moves forward, so every change reads as time passing.
    setRotation(r => {
      if (phase === 'connecting') return r + 360
      if (phase === 'on') return Math.ceil((r + 1) / 360) * 360
      return Math.floor(r / 360) * 360 + 180
    })
  }, [phase])

  const transition: Transition =
    phase === 'connecting' ? { duration: 1.1, ease: [0.45, 0, 0.55, 1], repeat: Infinity }
    : phase === 'on' ? { type: 'spring', stiffness: 70, damping: 11 }
    : { duration: 0.6, ease: 'easeInOut' }

  const label = phase === 'on' ? t('已连接') : phase === 'connecting' ? t('连接中') : t('未连接')
  const detail = connected
    ? `${t('已连接')} Warcraft III ${status.gameVersion ?? ''}，PID ${status.pid ?? ''}`
    : t(status.statusMessage)

  return (
    <button
      type="button"
      className={s.clock}
      onClick={() => void connect()}
      disabled={connecting}
      data-testid="clock"
      data-phase={phase}
      aria-label={`${label}。${connected ? t('连接/刷新') : t('点击连接魔兽争霸 III')}`}
      title={detail}
    >
      <svg viewBox="0 0 96 50" className={s.svg} aria-hidden="true">
        <defs>
          <linearGradient id="clock-plate" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#3b342c" />
            <stop offset="1" stopColor="#171410" />
          </linearGradient>
          <linearGradient id="clock-day" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#7fb0d6" />
            <stop offset="1" stopColor="#f2c875" />
          </linearGradient>
          <linearGradient id="clock-night" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#22366a" />
            <stop offset="1" stopColor="#0b1226" />
          </linearGradient>
          <radialGradient id="clock-sun">
            <stop offset="0" stopColor="#fff6c4" />
            <stop offset="0.45" stopColor="#ffd84a" />
            <stop offset="1" stopColor="#ffd84a" stopOpacity="0" />
          </radialGradient>
          <clipPath id="clock-window">
            <path d="M28 28 A20 20 0 0 1 68 28 Z" />
          </clipPath>
        </defs>
        <path
          className={s.plate}
          d="M3 0 H93 C91 7 85 11 80 14 C76 34 64 48 48 48 C32 48 20 34 16 14 C11 11 5 7 3 0 Z"
          fill="url(#clock-plate)"
        />
        <g clipPath="url(#clock-window)">
          <g transform="translate(48 28)">
            <motion.g initial={false} animate={{ rotate: rotation }} transition={transition}>
              <path d="M-20 0 A20 20 0 0 1 20 0 Z" fill="url(#clock-day)" />
              <circle cx="0" cy="-11" r="9" fill="url(#clock-sun)" />
              <circle cx="0" cy="-11" r="4.2" fill="#fff0a8" />
              <path d="M20 0 A20 20 0 0 1 -20 0 Z" fill="url(#clock-night)" />
              <circle cx="0" cy="11" r="4.6" fill="#dfe8f7" />
              <circle cx="2.2" cy="9.6" r="4.1" fill="#1a2b57" />
              <circle cx="-9" cy="6" r="0.8" fill="#dfe8f7" />
              <circle cx="8" cy="4" r="0.6" fill="#dfe8f7" />
              <circle cx="11" cy="12" r="0.7" fill="#dfe8f7" />
              <circle cx="-12" cy="13" r="0.5" fill="#dfe8f7" />
            </motion.g>
          </g>
        </g>
        <path className={s.rim} d="M25 28 A23 23 0 0 1 71 28" />
        <path className={s.horizon} d="M23 28 H73" />
        <text className={s.label} x="48" y="41.5" textAnchor="middle">{label}</text>
      </svg>
    </button>
  )
}
