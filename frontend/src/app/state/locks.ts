import { create } from 'zustand'
import { api } from '../../lib/api'
import type { LockItem } from '../../lib/types'

/**
 * Locks held by the backend, which re-applies them on a timer. Lock ids follow the backend:
 * `unit:<field key>` for a unit field, `resource:<group iid>:<kind>` for a resource.
 */
interface LockState {
  items: LockItem[]
  loaded: boolean
  reload(): Promise<void>
  set(items: LockItem[] | undefined): void
  remove(id: string): Promise<boolean>
  applyOnce(): Promise<string | null>
}

export const useLocks = create<LockState>()(set => ({
  items: [],
  loaded: false,

  async reload() {
    try {
      const items = await api.getLocks()
      set({ items: items ?? [], loaded: true })
    } catch { /* reported by callApi */ }
  },

  set(items) { if (items) set({ items, loaded: true }) },

  async remove(id) {
    try {
      const result = await api.removeLock(id)
      if (result?.success) set({ items: result.locks })
      return !!result?.success
    } catch {
      return false
    }
  },

  async applyOnce() {
    try {
      const result = await api.applyLocksOnce()
      return result?.success ? (result.message ?? '') : null
    } catch {
      return null
    }
  },
}))

export const unitLockId = (fieldIid: string) => `unit:${fieldIid}`
export const resourceLockId = (groupIid: string, kind: string) => `resource:${groupIid}:${kind}`
