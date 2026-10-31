export const cx = (...parts: Array<string | false | null | undefined>) => parts.filter(Boolean).join(' ')

/** True when keyboard focus is somewhere that types text, so single-key shortcuts must stay quiet. */
export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return !!target.closest('input, textarea, select, [contenteditable="true"]')
}

export const rectOf = (anchor: Element | DOMRect | null | undefined): DOMRect | null =>
  !anchor ? null : anchor instanceof Element ? anchor.getBoundingClientRect() : anchor
