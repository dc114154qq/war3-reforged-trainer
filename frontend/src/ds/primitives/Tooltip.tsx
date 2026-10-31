import type { ReactNode } from 'react'
import * as RadixTooltip from '@radix-ui/react-tooltip'
import { cx } from '../util'
import s from './Tooltip.module.css'

interface TooltipCardProps {
  title: ReactNode
  /** Shown as "(Q)" after the title, in gold, like the game. */
  hotkey?: string
  children?: ReactNode
  /** Small state line under the body, e.g. "已开启". */
  footer?: ReactNode
  className?: string
}

/** The in-game tooltip box: near-black, ornate corners, serif title, hotkey in gold. */
export function TooltipCard({ title, hotkey, children, footer, className }: TooltipCardProps) {
  return (
    <div className={cx('ds-frame-ornate', s.card, className)}>
      <p className={s.title}>
        {title}
        {hotkey && <>(<span className={s.hotkey}>{hotkey}</span>)</>}
      </p>
      {children && <div className={s.body}>{children}</div>}
      {footer && <p className={s.footer}>{footer}</p>}
    </div>
  )
}

interface TooltipProps extends Omit<TooltipCardProps, 'children' | 'className'> {
  /** The element that shows the tooltip on hover or focus. */
  children: ReactNode
  body?: ReactNode
  side?: 'top' | 'bottom' | 'left' | 'right'
}

/** Hover/focus tooltip for any element. Command buttons use the fixed tooltip in CommandCard instead. */
export function Tooltip({ children, body, side = 'top', ...card }: TooltipProps) {
  return (
    <RadixTooltip.Root>
      <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content side={side} sideOffset={8} collisionPadding={12} className={s.floating}>
          <TooltipCard {...card}>{body}</TooltipCard>
        </RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  )
}

export const TooltipProvider = RadixTooltip.Provider
