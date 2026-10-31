import type { ReactNode } from 'react'
import s from './sg.module.css'

export function Section({ id, title, lead, children }: { id: string; title: string; lead: string; children: ReactNode }) {
  return (
    <section id={id} className={s.section} aria-labelledby={`${id}-title`}>
      <header className={s.sectionHead}>
        <h2 id={`${id}-title`} className={s.sectionTitle}>{title}</h2>
        <p className={s.lead}>{lead}</p>
      </header>
      {children}
    </section>
  )
}

export function Demo({ title, note, children, wide = false }: { title: string; note?: string; children: ReactNode; wide?: boolean }) {
  return (
    <div className={wide ? `${s.demo} ${s.wide}` : s.demo}>
      <h3 className={s.demoTitle}>{title}</h3>
      {note && <p className={s.note}>{note}</p>}
      <div className={s.demoBody}>{children}</div>
    </div>
  )
}
