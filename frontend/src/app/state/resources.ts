import { create } from 'zustand'
import { api } from '../../lib/api'
import type { ResourceSnapshot } from '../../lib/types'

export type SetKind = 'gold' | 'lumber' | 'food_used' | 'food_cap'
/** add_resource: 'both' adds the same amount to gold and lumber. */
export type AddKind = 'gold' | 'lumber' | 'both'

interface ResourceState {
  snapshot: ResourceSnapshot | null
  /** Cached values only; never reads game memory, so it is safe to poll. */
  poll(): Promise<void>
  set(kind: SetKind, value: string): Promise<ResourceSnapshot | null>
  add(kind: AddKind, delta: string): Promise<ResourceSnapshot | null>
}

// A poll that started before a write can answer after it with the old values, which would
// make the number jump back until the next poll; such answers are dropped.
let writes = 0

export const useResources = create<ResourceState>()(set => ({
  snapshot: null,

  async poll() {
    const seen = writes
    try {
      const snapshot = await api.getResourceSnapshot()
      if (snapshot && seen === writes) set({ snapshot })
    } catch { /* reported by callApi */ }
  },

  async set(kind, value) {
    writes++
    try {
      const result = await api.setResource(kind, value)
      if (result?.data) set({ snapshot: result.data })
      return result?.success ? result.data : null
    } catch {
      return null
    }
  },

  async add(kind, delta) {
    writes++
    try {
      const result = await api.addResource(kind, delta)
      if (result?.data) set({ snapshot: result.data })
      return result?.success ? result.data : null
    } catch {
      return null
    }
  },
}))

/** Parse a backend number string; empty or non-numeric means "not read yet". */
export function num(value: string | number | undefined | null): number | null {
  if (value === undefined || value === null || value === '') return null
  const n = Number(String(value).replace(/,/g, ''))
  return Number.isFinite(n) ? n : null
}
