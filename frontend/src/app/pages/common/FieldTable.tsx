import { useEffect, useRef, type CSSProperties, type ReactNode } from 'react'
import { EditableText, Frost, Icon, Keycap } from '../../../ds'
import { useT } from '../../i18n'
import s from './FieldTable.module.css'

export interface FieldRow {
  id: string
  /** Rows are grouped under a header per distinct group, in order of first appearance. */
  group?: string
  name: string
  /** Secondary name, e.g. the English or editor field name. */
  sub?: string
  value: string
  type?: string
  address?: string
  note?: string
  locked?: boolean
  readOnly?: boolean
  /** Backend status word, e.g. 只读, 已修改, 未开放; shown as a tag. */
  status?: string
}

/** Tone of a status tag: changed values glow, unsupported ones recede. */
function statusTone(status: string) {
  if (/已修改|已写入/.test(status)) return 'changed'
  if (/未开放|未确认|不支持|失败/.test(status)) return 'unsupported'
  if (/只读/.test(status)) return 'readonly'
  return 'plain'
}

interface FieldTableProps {
  label: string
  rows: FieldRow[]
  /** Show group headers (turn off while filtering by one group or searching). */
  grouped?: boolean
  selectedId: string | null
  onSelect(id: string): void
  onCommit(row: FieldRow, value: string, rect: DOMRect | null): void
  /** Lock button per row; omit for tables without locks. */
  onToggleLock?(row: FieldRow): void
  /** Row whose value editor is open (W opens it for the selected row). */
  editingId?: string | null
  onEditingChange?(id: string | null): void
  empty: ReactNode
  /** Keycaps shown beside the selected field's description. */
  keys?: { key: string; label: string }[]
}

/**
 * The field ledger: group banners, inline editing, frost on locked rows, and the selected
 * field's description at the bottom. Used by the unit, ability and item field pages.
 */
export function FieldTable({
  label, rows, grouped = true, selectedId, onSelect, onCommit, onToggleLock, editingId, onEditingChange, empty, keys,
}: FieldTableProps) {
  const t = useT()
  const bodyRef = useRef<HTMLDivElement>(null)
  const selected = rows.find(r => r.id === selectedId)
  const withLock = !!onToggleLock
  const hasType = rows.some(r => r.type)
  const hasAddress = rows.some(r => r.address)
  const hasStatus = rows.some(r => r.status)

  useEffect(() => {
    if (selectedId) bodyRef.current?.querySelector(`[data-row="${CSS.escape(selectedId)}"]`)?.scrollIntoView({ block: 'nearest' })
  }, [selectedId])

  const groups: { name: string | null; rows: FieldRow[] }[] = []
  if (grouped) {
    for (const row of rows) {
      const name = row.group ?? ''
      const last = groups.find(g => g.name === name)
      if (last) last.rows.push(row)
      else groups.push({ name, rows: [row] })
    }
  } else groups.push({ name: null, rows })

  const move = (step: number) => {
    if (!rows.length) return
    const i = selectedId ? rows.findIndex(r => r.id === selectedId) : -1
    onSelect(rows[Math.min(rows.length - 1, Math.max(0, i + step))].id)
  }

  const cols = [
    'minmax(150px, 1.4fr)', 'minmax(110px, 1fr)', hasType ? '64px' : '', hasStatus ? '76px' : '', hasAddress ? '116px' : '', withLock ? '34px' : '',
  ].filter(Boolean).join(' ')

  return (
    <section className={s.ledger} aria-label={label} style={{ '--cols': cols } as CSSProperties}>
      <div className={s.head} aria-hidden="true">
        <span>{t('字段')}</span>
        <span>{t('当前值')}</span>
        {hasType && <span>{t('类型')}</span>}
        {hasStatus && <span>{t('状态')}</span>}
        {hasAddress && <span>{t('地址')}</span>}
        {withLock && <span />}
      </div>
      <div
        ref={bodyRef}
        className={s.body}
        role="table"
        aria-label={label}
        tabIndex={0}
        onKeyDown={e => {
          if (e.target !== e.currentTarget) return
          if (e.key === 'ArrowDown') { e.preventDefault(); move(1) }
          if (e.key === 'ArrowUp') { e.preventDefault(); move(-1) }
        }}
      >
        {rows.length === 0 && <p className={s.empty}>{empty}</p>}
        {groups.map(g => (
          <div key={g.name ?? 'all'} role="rowgroup">
            {g.name && <div className={s.group}><span>{t(g.name)}</span></div>}
            {g.rows.map(row => (
              <div
                key={row.id}
                role="row"
                className={s.row}
                data-row={row.id}
                data-selected={row.id === selectedId || undefined}
                data-locked={row.locked || undefined}
                onClick={() => onSelect(row.id)}
              >
                <span role="cell" className={s.name} title={row.note || undefined}>
                  {row.name}
                  {row.sub && <span className={s.sub}>{row.sub}</span>}
                </span>
                <span role="cell" className={s.value}>
                  <EditableText
                    className={s.valueBox}
                    value={row.value}
                    label={row.name}
                    readOnly={row.readOnly}
                    editing={editingId === row.id}
                    onEditingChange={open => onEditingChange?.(open ? row.id : null)}
                    onCommit={(value, rect) => { if (value !== row.value) onCommit(row, value, rect) }}
                  >
                    {withLock && <Frost locked={!!row.locked} />}
                  </EditableText>
                </span>
                {hasType && <span role="cell" className={s.mono}>{row.type}</span>}
                {hasStatus && (
                  <span role="cell">
                    {row.status && <span className={s.status} data-tone={statusTone(row.status)}>{t(row.status)}</span>}
                  </span>
                )}
                {hasAddress && <span role="cell" className={s.mono}>{row.address}</span>}
                {withLock && (
                  <span role="cell">
                    <button
                      type="button"
                      className={s.lock}
                      aria-pressed={!!row.locked}
                      aria-label={`${row.locked ? t('解锁') : t('锁定')} ${row.name}`}
                      title={row.locked ? t('解锁') : t('锁定')}
                      disabled={row.readOnly}
                      onClick={e => { e.stopPropagation(); onSelect(row.id); onToggleLock?.(row) }}
                    >
                      <Icon name="lock" tone={row.locked ? 'frost' : 'muted'} />
                    </button>
                  </span>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
      <footer className={s.detail}>
        {selected ? (
          <>
            <span className={s.detailName}>{selected.name}</span>
            <span className={s.detailDesc}>{selected.note || selected.sub || ''}</span>
            {keys && (
              <span className={s.keys}>
                {keys.map(k => <span key={k.key}><Keycap>{k.key}</Keycap>{k.label}</span>)}
              </span>
            )}
          </>
        ) : (
          <span className={s.hint}>{t('点一行看说明，点数值直接修改，回车写入。')}</span>
        )}
      </footer>
    </section>
  )
}
