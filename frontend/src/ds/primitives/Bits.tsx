import type { ElementType, HTMLAttributes, ReactNode } from 'react'
import { PLAYER_COLORS, PLAYER_NAMES } from '../tokens'
import { cx } from '../util'
import s from './Bits.module.css'

/** A hotkey letter on a small stone cap, gold like the in-game tooltip hotkey. */
export function Keycap({ children }: { children: ReactNode }) {
  return <kbd className={s.keycap}>{children}</kbd>
}

/** Engraved plate for four-character IDs such as Hpal or AHbz. */
export function RawcodePlate({ code, title = '类型 ID' }: { code: string; title?: string }) {
  return <span className={s.rawcode} title={title}>{code}</span>
}

/** Player colour chip; slot is 0-based. */
export function PlayerSwatch({ slot, withLabel = false }: { slot: number; withLabel?: boolean }) {
  const swatch = <i className={s.swatch} style={{ background: PLAYER_COLORS[slot] }} aria-hidden={withLabel || undefined} />
  if (!withLabel) return <span role="img" aria-label={`玩家 ${slot + 1}（${PLAYER_NAMES[slot]}）`}>{swatch}</span>
  return (
    <span className={s.player}>
      {swatch}
      玩家 {slot + 1}（{PLAYER_NAMES[slot]}）
    </span>
  )
}

/** Category heading inside lists and tables: label, then a hairline that fades out. */
export function GroupHeader({ children, as: Tag = 'div' }: { children: ReactNode; as?: ElementType }) {
  return <Tag className={s.group}>{children}</Tag>
}

/** Nine-slice frame. ornate for tooltips, maps and portraits; grand for dialogs. */
export function Frame({ variant = 'ornate', as: Tag = 'div', className, ...rest }: HTMLAttributes<HTMLElement> & {
  variant?: 'ornate' | 'grand'
  as?: ElementType
}) {
  return <Tag className={cx(variant === 'grand' ? 'ds-frame-grand' : 'ds-frame-ornate', className)} {...rest} />
}
