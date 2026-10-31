import { Suspense } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { PAGES, isReady } from '../pages/registry'
import { chapterOf, pageMeta, type PageId } from '../routes'
import { useNav } from '../state/nav'
import { useT } from '../i18n'
import { Chat } from './Chat'
import s from './Stage.module.css'

export function Stage() {
  const page = useNav(st => st.page)
  const Page = PAGES[page]
  return (
    <main className={`ds-stage ${s.stage}`} data-testid="stage" data-page={page} data-ready={isReady(page)}>
      <PageHeader page={page} />
      {/* No initial={false}: it would disable mount animations inside every page. */}
      <AnimatePresence mode="wait">
        <motion.div
          key={page}
          data-page-view={page}
          className={s.content}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1, transition: { duration: 0.1 } }}
          exit={{ opacity: 0, transition: { duration: 0.06 } }}
        >
          <Suspense fallback={null}><Page /></Suspense>
        </motion.div>
      </AnimatePresence>
      <Chat />
    </main>
  )
}

function PageHeader({ page }: { page: PageId }) {
  const t = useT()
  const setPage = useNav(st => st.setPage)
  const chapter = chapterOf(page)
  return (
    <div className={s.header}>
      <h1 className={s.title}>{t(pageMeta(page).label)}</h1>
      {chapter.pages.length > 1 && (
        <nav className={s.tabs} aria-label={`${t(chapter.label)}${t('的页面')}`}>
          {chapter.pages.map(p => (
            <button
              key={p.id}
              type="button"
              className={s.tab}
              data-active={p.id === page || undefined}
              aria-current={p.id === page ? 'page' : undefined}
              data-testid={`page-${p.id}`}
              onClick={() => setPage(p.id)}
            >
              {t(p.label)}
            </button>
          ))}
        </nav>
      )}
    </div>
  )
}
