import { create } from 'zustand'

/**
 * "Show the details on the page" from the notice dialog: the map catalog page may not be
 * mounted yet when the request is made, so the request is kept here until it is handled.
 */
export const useMapIssues = create<{ pending: boolean; request(): void; handled(): void }>()(set => ({
  pending: false,
  request: () => set({ pending: true }),
  handled: () => set({ pending: false }),
}))
