import { useCallback, useLayoutEffect, useState, type Dispatch, type RefObject, type SetStateAction } from 'react'

const PREFIX = 'war3-view-v1:'
const memory = new Map<string, unknown>()
type Guard<T> = (value: unknown) => value is T

function sameShape(value: unknown, initial: unknown): boolean {
  if (initial === null) return value === null
  if (typeof value !== typeof initial) return false
  if (typeof value === 'number') return Number.isFinite(value)
  if (typeof value === 'string') return value.length <= 65536
  if (typeof value === 'boolean') return true
  if (!value || !initial || Array.isArray(value) || Array.isArray(initial)) return false
  return Object.entries(initial).every(([key, template]) => sameShape((value as Record<string, unknown>)[key], template))
}

export function readViewValue<T>(key: string, initial: T, valid?: Guard<T>): T {
  const guard = valid ?? ((value: unknown): value is T => sameShape(value, initial))
  try {
    const value = memory.has(key) ? memory.get(key) : JSON.parse(localStorage.getItem(PREFIX + key) ?? 'null')
    if (guard(value)) return value
  } catch { /* Storage can be unavailable or contain old/damaged settings. */ }
  return initial
}

export function writeViewValue(key: string, value: unknown) {
  memory.set(key, value)
  try { localStorage.setItem(PREFIX + key, JSON.stringify(value)) } catch { /* Still retained for this app session. */ }
}

export const optionalText = (value: unknown): value is string | null => value === null || (typeof value === 'string' && value.length <= 65536)
export const nonnegative = (value: unknown): value is number => Number.isSafeInteger(value) && Number(value) >= 0 && Number(value) <= 10000000
export const choice = <T extends string>(values: readonly T[]): Guard<T> =>
  (value: unknown): value is T => typeof value === 'string' && values.includes(value as T)

/** Only explicit display preferences and input drafts belong here, never live game objects. */
export function useViewState<T>(key: string, initial: T, valid?: Guard<T>): [T, Dispatch<SetStateAction<T>>] {
  const [stored, setStored] = useState(() => ({ key, value: readViewValue(key, initial, valid) }))
  let value = stored.value
  if (stored.key !== key) {
    value = readViewValue(key, initial, valid)
    setStored({ key, value })
  }
  const update = useCallback<Dispatch<SetStateAction<T>>>(next => {
    // Read the latest value so rapid successive functional updates compose.
    const current = readViewValue(key, initial, valid)
    const result = typeof next === 'function' ? (next as (previous: T) => T)(current) : next
    writeViewValue(key, result)
    setStored({ key, value: result })
  }, [key]) // Initial/validator describe the stable schema, not a changing input.
  return [value, update]
}

type Position = { top: number; left: number }
type Positions = Record<string, Position>
const positionsValid = (value: unknown): value is Positions => !!value && typeof value === 'object' && !Array.isArray(value)
  && Object.keys(value).length <= 100 && Object.values(value).every(p => p && nonnegative(p.top) && nonnegative(p.left))

/** Restore nested scroll regions after asynchronous lists appear; pages still unmount normally. */
export function usePageScrollMemory(rootRef: RefObject<HTMLDivElement | null>, page: string) {
  useLayoutEffect(() => {
    const root = rootRef.current
    if (!root) return
    const storageKey = 'scroll:' + page
    const positions = { ...readViewValue<Positions>(storageKey, {}, positionsValid) }
    const savedKeys = Object.keys(positions)
    const onlyNamed = savedKeys.every(key => /^[\w-]+:\d+$/.test(key))
    const completed = new WeakSet<HTMLElement>()
    const applied = new WeakMap<HTMLElement, Position>()
    let frame = 0, saveTimer = 0
    const keyOf = (node: HTMLElement) => {
      const named = node.dataset.scrollRegion
      if (named) {
        const siblings = [...root.querySelectorAll<HTMLElement>('[data-scroll-region]')].filter(e => e.dataset.scrollRegion === named)
        return named + ':' + siblings.indexOf(node)
      }
      const parts: string[] = []
      let current: HTMLElement | null = node
      while (current && current !== root) {
        parts.unshift(current.tagName + ':' + [...(current.parentElement?.children ?? [])].indexOf(current))
        current = current.parentElement
      }
      return parts.join('/')
    }
    const restore = () => {
      if (!savedKeys.length) return
      for (const node of root.querySelectorAll<HTMLElement>(onlyNamed ? '[data-scroll-region]' : '*')) {
        if (completed.has(node)) continue
        const position = positions[keyOf(node)]
        if (!position) continue
        const style = getComputedStyle(node)
        if (!/(auto|scroll)/.test(style.overflowX + style.overflowY)) continue
        node.scrollTop = position.top
        node.scrollLeft = position.left
        applied.set(node, { top: node.scrollTop, left: node.scrollLeft })
        if (Math.abs(node.scrollTop - position.top) < 1 && Math.abs(node.scrollLeft - position.left) < 1) completed.add(node)
      }
    }
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(() => { frame = 0; restore() })
    }
    const save = () => writeViewValue(storageKey, positions)
    const onScroll = (event: Event) => {
      const node = event.target
      if (!(node instanceof HTMLElement) || !root.contains(node)) return
      const expected = applied.get(node)
      if (expected && Math.abs(node.scrollTop - expected.top) < 1 && Math.abs(node.scrollLeft - expected.left) < 1) return
      completed.add(node)
      applied.delete(node)
      positions[keyOf(node)] = { top: Math.round(node.scrollTop), left: Math.round(node.scrollLeft) }
      clearTimeout(saveTimer)
      saveTimer = window.setTimeout(save, 150)
    }
    // Explicit scrolling takes priority over a delayed restore of a not-yet-populated list.
    const userScroll = (event: Event) => {
      if (event instanceof KeyboardEvent && !['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End', ' '].includes(event.key)) return
      let node = event.target instanceof HTMLElement ? event.target : null
      while (node && node !== root) { completed.add(node); applied.delete(node); node = node.parentElement }
    }
    const observer = new MutationObserver(schedule)
    const resize = new ResizeObserver(schedule)
    observer.observe(root, { childList: true, subtree: true })
    resize.observe(root)
    root.addEventListener('scroll', onScroll, true)
    root.addEventListener('wheel', userScroll, { passive: true })
    root.addEventListener('touchmove', userScroll, { passive: true })
    root.addEventListener('keydown', userScroll)
    restore()
    schedule()
    return () => {
      observer.disconnect(); resize.disconnect(); cancelAnimationFrame(frame); clearTimeout(saveTimer)
      root.removeEventListener('scroll', onScroll, true)
      root.removeEventListener('wheel', userScroll); root.removeEventListener('touchmove', userScroll); root.removeEventListener('keydown', userScroll)
      save()
    }
  }, [page])
}
