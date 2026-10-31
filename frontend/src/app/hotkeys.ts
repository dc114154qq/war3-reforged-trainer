import { useEffect } from 'react'
import { CHAPTERS } from './routes'
import { useNav } from './state/nav'
import { openChat } from './shell/Chat'

/**
 * Window-level keys of the shell: Alt+1…6 switch chapters, Enter opens the chat box.
 * Command-card keys (Q…V) belong to <CommandCard>. These are local to the trainer window;
 * the 68 global hotkeys are registered by the backend and are not affected.
 */
export function useShellHotkeys() {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey && !e.ctrlKey && !e.metaKey && /^[1-6]$/.test(e.key)) {
        e.preventDefault()
        useNav.getState().setChapter(CHAPTERS[Number(e.key) - 1].id)
        return
      }
      if (e.key !== 'Enter' || e.ctrlKey || e.altKey || e.metaKey) return
      const target = e.target instanceof HTMLElement ? e.target : null
      // Enter keeps its meaning on controls and inside dialogs or menus.
      if (target?.closest('input, textarea, select, button, a, [role="dialog"], [role="menu"], [data-radix-popper-content-wrapper]')) return
      if (document.querySelector('[role="dialog"]')) return
      e.preventDefault()
      openChat()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
}
