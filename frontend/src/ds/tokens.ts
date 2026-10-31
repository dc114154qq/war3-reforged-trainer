// JS-side tokens: motion constants and data-driven colours. CSS colours live in tokens.css.
import type { Transition } from 'motion/react'

/** Durations in seconds, matching --dur-* in tokens.css. */
export const DUR = {
  press: 0.12,
  fast: 0.16,
  base: 0.24,
  slow: 0.38,
  /** In-game bounty text: lives 2 s, starts fading after 1 s. */
  bounty: 2,
  /** The connect reveal, the app's one orchestrated moment. */
  reveal: 1.1,
} as const

export const EASE = {
  out: [0.2, 0.8, 0.2, 1],
  inOut: [0.45, 0, 0.55, 1],
  snap: [0.2, 0.9, 0.25, 1.15],
} as const

export const SPRING = {
  /** Layout moves: tab marks, blips. */
  layout: { type: 'spring', stiffness: 520, damping: 40 },
  /** Things that pop in: command slots, selection rings. */
  pop: { type: 'spring', stiffness: 420, damping: 26 },
  /** Digits rolling on the odometer. */
  digit: { type: 'spring', stiffness: 260, damping: 26 },
} satisfies Record<string, Transition>

/** Warcraft III player colours, slot 0 = red. Used where colour comes from data. */
export const PLAYER_COLORS = [
  '#FF0303', '#0042FF', '#1CE6B9', '#540081', '#FFFC00', '#FE8A0E',
  '#20C000', '#E55BB0', '#959697', '#7EBFF1', '#106246', '#4E2A04',
] as const

export const PLAYER_NAMES = ['红', '蓝', '青', '紫', '黄', '橙', '绿', '粉', '灰', '浅蓝', '深绿', '棕'] as const

export type Quality = 'poor' | 'common' | 'uncommon' | 'rare' | 'epic' | 'legendary'

export const QUALITY_LABEL: Record<Quality, string> = {
  poor: '粗糙', common: '普通', uncommon: '优秀', rare: '精良', epic: '史诗', legendary: '传说',
}

/** Fog colour ramp for the canvas reveal: base and wisp highlight, as RGB. */
export const FOG = { base: [6, 9, 17], wisp: [30, 36, 50] } as const
