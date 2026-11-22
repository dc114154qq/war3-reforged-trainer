import { create } from 'zustand'
import { announce } from '../../ds'
import type { UiNotice } from '../../lib/api'
import { t } from '../i18n'

/** Plain status text can use the bottom line. Failures always open the dialog. */
const SHORT = 48
const isShort = (n: UiNotice) => n.kind !== 'error' && !n.logPath && !n.details?.length && !n.title && n.message.length <= SHORT

interface NoticeState {
  queue: UiNotice[]
  push(notice: UiNotice | string): void
  dismiss(): void
}

// Backend notification ids are unique per notice; the same failure can also arrive as a
// war3-error event from callApi, so ids and messages are both de-duplicated.
const seenIds = new Set<number>()

export const useNotices = create<NoticeState>()((set, get) => ({
  queue: [],

  push(input) {
    const notice: UiNotice = typeof input === 'string' ? { message: input } : input
    if (!notice?.message) return
    if (notice.id) {
      if (seenIds.has(notice.id)) return
      seenIds.add(notice.id)
    }
    if (get().queue.some(n => n.title === notice.title && n.message === notice.message && n.logPath === notice.logPath)) return
    if (isShort(notice)) {
      announce(t(notice.message))
      return
    }
    set(st => ({ queue: [...st.queue, notice] }))
  },

  dismiss() { set(st => ({ queue: st.queue.slice(1) })) },
}))
