import { create } from 'zustand'
import { api } from '../../lib/api'

/**
 * Elephant parameters (hero level, unit scale and so on). The backend reports changes through
 * notifications and through the `parameters` field of action results; both land here.
 */
interface ParamState {
  values: Record<string, string>
  merge(values: Record<string, string> | null | undefined): void
  reload(): Promise<void>
}

export const useParams = create<ParamState>()((set, get) => ({
  values: {},
  merge(values) {
    if (values) set(st => ({ values: { ...st.values, ...values } }))
  },
  async reload() {
    try { get().merge(await api.getElephantParameters()) } catch { /* reported by callApi */ }
  },
}))
