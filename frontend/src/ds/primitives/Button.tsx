import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { Icon } from '../icons/Icon'
import type { IconName } from '../icons/generated'
import { cx } from '../util'
import s from './Button.module.css'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /**
   * cast: the one filled style, cast bronze; at most one per view, for the main action.
   * iron: everything else. danger: destructive, usually inside <HoldToConfirm>.
   */
  variant?: 'cast' | 'iron' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  icon?: IconName
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'iron', size = 'md', icon, className, children, type = 'button', ...rest },
  ref,
) {
  return (
    <button ref={ref} type={type} className={cx(s.button, s[variant], s[size], className)} {...rest}>
      {icon && <Icon name={icon} tone={variant === 'cast' ? 'current' : variant === 'danger' ? 'current' : 'bone'} className={s.icon} />}
      {children}
    </button>
  )
})
