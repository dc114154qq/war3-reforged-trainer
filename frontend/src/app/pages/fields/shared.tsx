import { Checkbox, TextField, bounty } from '../../../ds'
import { num } from '../../state/resources'
import { useT } from '../../i18n'
import s from './Fields.module.css'

/** A row of the ability or item field tables, as the backend sends it. */
export interface RawFieldRow {
  _iid: string
  field: string
  name: string
  value: string
  status: string
  searchText?: string
}

export interface FieldFilter {
  query: string
  showZero: boolean
  showUnsupported: boolean
}

const ZERO = new Set(['0', '0.0', '0.00'])
const UNSUPPORTED = new Set(['未开放', '未确认', '不支持'])

/** The same filter 2.1.22 applied on top of the backend's own. */
export function filterFields<T extends RawFieldRow>(rows: T[], { query, showZero, showUnsupported }: FieldFilter): T[] {
  const q = query.trim().toLowerCase()
  return rows.filter(r => {
    if (!showZero && ZERO.has(r.value)) return false
    if (!showUnsupported && UNSUPPORTED.has(r.status)) return false
    if (!q) return true
    return [r.field, r.name, r.searchText ?? '', r.value].some(x => x.toLowerCase().includes(q))
  })
}

/** Search, the two visibility switches and the backend's summary line. */
export function FieldFilters({ filter, onChange, summary, shown, total }: {
  filter: FieldFilter
  onChange(next: FieldFilter): void
  summary: string
  shown: number
  total: number
}) {
  const t = useT()
  return (
    <div className={s.filters}>
      <TextField
        variant="search"
        className={s.search}
        aria-label={t('筛选字段')}
        placeholder={t('按字段标识、名称、说明或数值筛选')}
        value={filter.query}
        onChange={e => onChange({ ...filter, query: e.target.value })}
      />
      <Checkbox label={t('显示数值为 0 的项')} checked={filter.showZero} onChange={e => onChange({ ...filter, showZero: e.target.checked })} />
      <Checkbox label={t('显示未支持字段')} checked={filter.showUnsupported} onChange={e => onChange({ ...filter, showUnsupported: e.target.checked })} />
      <span className={s.summary}>
        {total > 0 && `${shown} / ${total}　`}
        {t(summary)}
      </span>
    </div>
  )
}

const fmt = (n: number) => String(Number(n.toFixed(4)))

/** Float the change of a written value off its cell: "+20" for numbers, "已写入" otherwise. */
export function floatChange(rect: DOMRect | null, before: string, after: string, written: string) {
  const a = num(before), b = num(after)
  const text = a !== null && b !== null && a !== b ? `${b > a ? '+' : '−'}${fmt(Math.abs(b - a))}` : written
  bounty({ anchor: rect, text })
}
