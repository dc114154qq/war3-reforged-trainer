import { create } from 'zustand'
import { CHAPTERS, chapterOf, isPageId, type ChapterId, type PageId } from '../routes'

const STORAGE_KEY = 'war3-page'

function initialPage(): PageId {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (isPageId(saved)) return saved
  } catch { /* storage unavailable */ }
  return 'unit'
}

interface NavState {
  page: PageId
  /** Last page visited in each chapter, so switching chapters returns to it. */
  lastInChapter: Partial<Record<ChapterId, PageId>>
  setPage(page: PageId): void
  setChapter(chapter: ChapterId): void
}

export const useNav = create<NavState>()((set, get) => ({
  page: initialPage(),
  lastInChapter: {},

  setPage(page) {
    set(st => ({ page, lastInChapter: { ...st.lastInChapter, [chapterOf(page).id]: page } }))
    try { localStorage.setItem(STORAGE_KEY, page) } catch { /* storage unavailable */ }
  },

  setChapter(chapter) {
    const target = get().lastInChapter[chapter] ?? CHAPTERS.find(c => c.id === chapter)!.pages[0].id
    get().setPage(target)
  },
}))
