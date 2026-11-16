import { create } from 'zustand'
import { CHAPTERS, chapterOf, isPageId, type ChapterId, type PageId } from '../routes'
import { readViewValue, writeViewValue } from './viewMemory'

const STORAGE_KEY = 'war3-page'

function initialPage(): PageId {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'upgrade_catalog') {
      localStorage.setItem('war3-catalog-kind', 'upgrade')
      localStorage.setItem(STORAGE_KEY, 'catalogs')
      return 'catalogs'
    }
    if (isPageId(saved)) return saved
  } catch { /* storage unavailable */ }
  return 'unit'
}

interface NavState {
  page: PageId
  /** Last page visited in each chapter, so switching chapters returns to it. */
  lastInChapter: Partial<Record<ChapterId, PageId>>
  chapterOrder: ChapterId[]
  setPage(page: PageId): void
  setChapter(chapter: ChapterId): void
  moveChapter(source: ChapterId, target: ChapterId, after?: boolean): void
  resetChapterOrder(): void
}

const initial = initialPage()
const last = readViewValue<Partial<Record<ChapterId, PageId>>>('last-pages', {}, (value): value is Partial<Record<ChapterId, PageId>> =>
  !!value && typeof value === 'object' && !Array.isArray(value) && Object.entries(value).every(([chapter, page]) => isPageId(page) && chapterOf(page).id === chapter))
last[chapterOf(initial).id] = initial

/** Drop old/duplicate ids and append any chapters added in a later app version. */
export function normalizeChapterOrder(value: unknown): ChapterId[] {
  const known = CHAPTERS.map(c => c.id)
  return [...new Set([...(Array.isArray(value) ? value.filter((id): id is ChapterId => known.includes(id)) : []), ...known])]
}

export const orderedChapters = () => useNav.getState().chapterOrder.map(id => CHAPTERS.find(c => c.id === id)!)

export const useNav = create<NavState>()((set, get) => ({
  page: initial,
  lastInChapter: last,
  chapterOrder: normalizeChapterOrder(readViewValue<unknown>('chapter-order', null, (_): _ is unknown => true)),

  setPage(page) {
    if (!isPageId(page)) return
    const lastInChapter = { ...get().lastInChapter, [chapterOf(page).id]: page }
    set({ page, lastInChapter })
    writeViewValue('last-pages', lastInChapter)
    try { localStorage.setItem(STORAGE_KEY, page) } catch { /* storage unavailable */ }
  },

  setChapter(chapter) {
    const target = get().lastInChapter[chapter] ?? CHAPTERS.find(c => c.id === chapter)!.pages[0].id
    get().setPage(target)
  },

  moveChapter(source, target, after = false) {
    if (source === target || !CHAPTERS.some(c => c.id === source) || !CHAPTERS.some(c => c.id === target)) return
    const order = get().chapterOrder.filter(id => id !== source)
    order.splice(order.indexOf(target) + Number(after), 0, source)
    set({ chapterOrder: order })
    writeViewValue('chapter-order', order)
  },

  resetChapterOrder() {
    const order = CHAPTERS.map(c => c.id)
    set({ chapterOrder: order })
    writeViewValue('chapter-order', order)
  },
}))
