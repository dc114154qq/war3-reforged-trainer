import { Suspense } from 'react'
import { PAGES, isReady } from '../pages/registry'
import { chapterOf, pageMeta, type PageId } from '../routes'
import { useNav } from '../state/nav'
import { useT } from '../i18n'
import { Chat } from './Chat'
import s from './Stage.module.css'
import { FrontendReady } from '../startup'

export function Stage() {
  const t = useT()
  const page = useNav(st => st.page)
  const Page = PAGES[page]
  return (
    <main className={`ds-stage ${s.stage}`} data-testid="stage" data-page={page} data-ready={isReady(page)}>
      <PageHeader page={page} />
      {/* Page availability must not depend on an exit animation/rAF completing. */}
        <div
          key={page}
          data-page-view={page}
          className={s.content}
        >
          <Suspense fallback={<div role="status">{t('正在加载页面…')}</div>}><Page /><FrontendReady /></Suspense>
        </div>
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
