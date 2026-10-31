import type { ReactNode } from 'react'
import * as RadixDialog from '@radix-ui/react-dialog'
import s from './Dialog.module.css'

interface DialogProps {
  open: boolean
  onOpenChange(open: boolean): void
  title: string
  /** One plain sentence under the title; screen readers announce it. */
  description?: string
  children?: ReactNode
  /** Buttons, right-aligned; put the confirming action last. */
  actions?: ReactNode
  /** lg: work dialogs with forms and progress (640px). */
  size?: 'md' | 'lg'
  /** vellum: messages, ink on parchment. iron: forms, on the dark stage surface. */
  surface?: 'vellum' | 'iron'
}

/**
 * The game-menu dialog: iron header, grand corners, vellum body.
 * Esc and the overlay close it; focus is trapped while open.
 */
export function Dialog({ open, onOpenChange, title, description, children, actions, size = 'md', surface = 'vellum' }: DialogProps) {
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className={s.overlay} />
        {/* Without a description, tell Radix explicitly that none is intended. */}
        <RadixDialog.Content className={`ds-frame-grand ${s.content}`} data-size={size} data-surface={surface} {...(description ? {} : { 'aria-describedby': undefined })}>
          <header className={s.header}>
            <RadixDialog.Title className={s.title}>{title}</RadixDialog.Title>
          </header>
          <div className={s.body}>
            {description && <RadixDialog.Description className={s.description}>{description}</RadixDialog.Description>}
            {children}
          </div>
          {actions && <footer className={s.actions}>{actions}</footer>}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  )
}

export const DialogClose = RadixDialog.Close
