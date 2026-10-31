import type { CSSProperties, KeyboardEvent, ReactNode } from 'react'
import { cx } from '../../../ds'
import s from './DataTable.module.css'

export interface Column<T> {
  key: string
  label: ReactNode
  /** CSS grid track, e.g. '120px' or 'minmax(160px, 2fr)'. Default: minmax(0, 1fr). */
  width?: string
  /** Monospace: only for addresses, handles and four-character ids. */
  mono?: boolean
  align?: 'left' | 'right'
  render?(row: T): ReactNode
}

interface DataTableProps<T> {
  label: string
  columns: Column<T>[]
  rows: T[]
  rowKey(row: T): string
  /** Shown instead of rows when there are none: say what to do. */
  empty: ReactNode
  selected?: string | null
  onSelect?(row: T): void
  /** Double-click or Enter: the row's main action. */
  onActivate?(row: T): void
  /** Grow and scroll inside the parent (for pages that fill the stage). */
  fill?: boolean
  maxHeight?: number
  className?: string
}

/** Dense read-only table: hairline rows, hover tint, bronze marker on the selected row. */
export function DataTable<T>({
  label, columns, rows, rowKey, empty, selected, onSelect, onActivate, fill, maxHeight, className,
}: DataTableProps<T>) {
  const template = columns.map(c => c.width ?? 'minmax(0, 1fr)').join(' ')
  const interactive = !!(onSelect || onActivate)

  const onKey = (e: KeyboardEvent<HTMLDivElement>, row: T) => {
    if (e.key === 'Enter') { e.preventDefault(); (onActivate ?? onSelect)?.(row) }
    else if (e.key === ' ') { e.preventDefault(); onSelect?.(row) }
    else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      const next = (e.key === 'ArrowDown' ? e.currentTarget.nextElementSibling : e.currentTarget.previousElementSibling) as HTMLElement | null
      next?.focus()
      next?.click()
    }
  }

  return (
    <div className={cx(s.table, fill && s.fill, className)} role="table" aria-label={label} style={{ '--cols': template, maxHeight } as CSSProperties}>
      <div className={s.head} role="row">
        {columns.map(c => (
          <span key={c.key} role="columnheader" className={cx(c.align === 'right' && s.right)}>{c.label}</span>
        ))}
      </div>
      <div className={s.body} role="rowgroup">
        {rows.length === 0 ? (
          <p className={s.empty}>{empty}</p>
        ) : rows.map(row => {
          const key = rowKey(row)
          return (
            <div
              key={key}
              role="row"
              className={cx(s.row, interactive && s.interactive)}
              data-selected={selected === key || undefined}
              aria-selected={interactive ? selected === key : undefined}
              tabIndex={interactive ? 0 : undefined}
              onClick={onSelect ? () => onSelect(row) : undefined}
              onDoubleClick={onActivate ? () => onActivate(row) : undefined}
              onKeyDown={interactive ? e => onKey(e, row) : undefined}
            >
              {columns.map(c => (
                <span key={c.key} role="cell" className={cx(s.cell, c.mono && s.mono, c.align === 'right' && s.right)}>
                  {c.render ? c.render(row) : String((row as Record<string, unknown>)[c.key] ?? '')}
                </span>
              ))}
            </div>
          )
        })}
      </div>
    </div>
  )
}
