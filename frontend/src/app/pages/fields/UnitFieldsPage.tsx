import { useState } from 'react'
import { Button, Checkbox, Icon, Select, TextField, announce } from '../../../ds'
import { api } from '../../../lib/api'
import type { NativeUnitField, NativeUnitFieldsData } from '../../../lib/types'
import { useCatalogName } from '../../state/catalog'
import { useCommandCard } from '../../state/commands'
import { useSystem } from '../../state/system'
import { useT } from '../../i18n'
import { FieldTable, type FieldRow } from '../common/FieldTable'
import { Status, usePending } from '../common/Layout'
import { floatChange } from './shared'
import s from './Fields.module.css'

const textValue = (v: NativeUnitField['value']) => v === null ? '—' : typeof v === 'boolean' ? (v ? '1' : '0') : String(v)

export default function UnitFieldsPage() {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const english = useSystem(st => st.status.language === 'en')
  const { pending, run } = usePending()
  const [data, setData] = useState<NativeUnitFieldsData | null>(null)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [writableOnly, setWritableOnly] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [feedback, setFeedback] = useState<{ text: string; error?: boolean } | null>(null)
  const [changed, setChanged] = useState<Set<string>>(new Set())
  const name = useCatalogName('unit', data?.unitCode ?? '')
  const busy = Object.values(pending).some(Boolean)

  const read = () => run('read', async () => {
    setFeedback(null); setEditingId(null); setSelectedId(null)
    try {
      const result = await api.readUnitFields()
      setData(result); setChanged(new Set()); setCategory('')
    } catch (err) {
      setData(null)
      setFeedback({ text: `${t('读取失败：')}${err instanceof Error ? err.message : String(err)}`, error: true })
      throw err
    }
  })

  const write = (row: FieldRow, value: string, rect: DOMRect | null) => run('write', async () => {
    try {
      const result = await api.writeUnitFieldValue(row.id, value)
      setData(prev => prev ? { ...prev, rows: prev.rows.map(r => r.key === result.key ? { ...r, value: result.value } : r) } : prev)
      setChanged(prev => new Set(prev).add(row.id))
      floatChange(rect, row.value, textValue(result.value), t('已写入'))
      setFeedback({ text: `${t('已写入')} ${row.name}：${textValue(result.value)}` })
    } catch (err) {
      setFeedback({ text: `${t('写入失败：')}${err instanceof Error ? err.message : String(err)}`, error: true })
      throw err
    }
  })

  const all = data?.rows ?? []
  const categories = [...new Set(all.map(r => r.category))]
  const q = query.trim().toLowerCase()
  const visible = all.filter(r => (!category || r.category === category) && (!writableOnly || r.writable)
    && (!q || [r.label, r.labelEn, r.code, r.constant, r.category, r.note, textValue(r.value)].join(' ').toLowerCase().includes(q)))
  const rows: FieldRow[] = visible.map(r => ({
    id: r.key, group: r.category,
    name: english ? `${r.labelEn || r.constant}${r.weapon ? ` (${r.weapon})` : ''}` : r.label,
    sub: `${r.code} · ${r.constant}`, value: textValue(r.value), type: r.kind,
    note: t(r.note), readOnly: busy || !r.writable || r.value === null,
    status: changed.has(r.key) ? '已写入' : r.writable && r.value !== null ? '可修改' : '只读',
  }))
  const selected = all.find(r => r.key === selectedId)

  useCommandCard([
    { key: 'Q', icon: 'read', title: t('读取单位字段'), description: t('读取当前选中单位的编辑器字段，包括状态、外观和两组攻击。'), pending: pending.read, estimateMs: 1500, disabled: !connected || busy, onPress: () => void read() },
    { key: 'W', icon: 'write', title: t('修改字段'), description: t('编辑字段表里选中的那一行，回车写入游戏。'), pending: pending.write, estimateMs: 500, disabled: !connected || busy || !selected?.writable || selected.value === null,
      onPress: () => selectedId ? setEditingId(selectedId) : announce(t('先在字段表里选一行。')) },
    { key: 'A', icon: 'catalog', title: t('只看可修改字段'), description: t('隐藏当前没有写入接口的字段。'), active: writableOnly, onPress: () => setWritableOnly(v => !v) },
  ])

  return (
    <div className={s.page}>
      <div className={s.subject}>
        <span className={s.socket} aria-hidden="true"><Icon name="unit-melee" /></span>
        <div className={s.identity}>
          <p className={s.name}>{name || data?.unitCode || t('未读取单位')}</p>
          {data && <span>{data.unitCode}</span>}
        </div>
        <span className={s.spacer} />
        <Button variant="cast" icon="read" disabled={!connected || busy} onClick={() => void read()}>{t('读取单位字段')}</Button>
      </div>
      <div className={s.filters}>
        <TextField variant="search" className={s.search} aria-label={t('搜索单位字段')} placeholder={t('搜索名称、字段代码或说明')} value={query} onChange={e => setQuery(e.target.value)} />
        <Select aria-label={t('按分类筛选')} value={category} onChange={e => setCategory(e.target.value)} options={[
          { value: '', label: t('全部分类') }, ...categories.map(c => ({ value: c, label: t(c) })),
        ]} />
        <Checkbox label={t('只看可修改字段')} checked={writableOnly} onChange={e => setWritableOnly(e.target.checked)} />
        <span className={s.summary}>{visible.length} / {all.length}</span>
      </div>
      <p className={s.detail}>{t('选中单位后读取，点数值修改并回车写入。游戏拒绝的字段会提示具体原因；文本及攻击 2 射程暂为只读。')}</p>
      {feedback && <div className={s.feedback}><Status tone={feedback.error ? 'error' : 'info'}>{feedback.text}</Status></div>}
      <FieldTable label={t('单位字段')} rows={rows} grouped={!category && !q}
        selectedId={selectedId} onSelect={setSelectedId} editingId={editingId} onEditingChange={setEditingId}
        onCommit={(row, value, rect) => void write(row, value, rect)}
        empty={pending.read ? t('正在读取单位字段…') : all.length ? t('没有匹配的字段。') : t('在游戏里选中一个单位，再点“读取单位字段”。')}
        keys={[{ key: 'W', label: t('修改') }]} />
    </div>
  )
}
