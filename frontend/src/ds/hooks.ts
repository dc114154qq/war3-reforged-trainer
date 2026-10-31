import { useEffect, useState } from 'react'

/**
 * Tracks whether the trainer window has focus. Use it to stop polling-driven motion and
 * simulations while the player is in the game. Starts as focused: some hosts never send
 * a focus event at startup.
 */
export function useWindowFocused(): boolean {
  const [focused, setFocused] = useState(true)
  useEffect(() => {
    const on = () => setFocused(true)
    const off = () => setFocused(false)
    window.addEventListener('focus', on)
    window.addEventListener('blur', off)
    return () => {
      window.removeEventListener('focus', on)
      window.removeEventListener('blur', off)
    }
  }, [])
  return focused
}

/** Sets html[data-idle] while the window is unfocused; base.css pauses CSS animations then. */
export function useIdleAttribute() {
  const focused = useWindowFocused()
  useEffect(() => {
    document.documentElement.toggleAttribute('data-idle', !focused)
  }, [focused])
}
