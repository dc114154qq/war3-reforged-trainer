import { useState } from 'react'
import { Button, Icon, TextField, announce } from '../../../ds'
import { api } from '../../../lib/api'
import type { AbilityFieldRow, AbilityFieldsData } from '../../../lib/types'
import { useCatalogName } from '../../state/catalog'
import { useCommandCard } from '../../state/commands'
import { useSystem } from '../../state/system'
import { useT } from '../../i18n'
import { FieldTable, type FieldRow } from '../common/FieldTable'
import { Status, usePending } from '../common/Layout'
import { FieldFilters, filterFields, floatChange, type FieldFilter } from './shared'
import s from './Fields.module.css'

export default function AbilityFieldsPage() {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const { pending, run } = usePending()
  const [rawcode, setRawcode] = useState('AHhb')
  const [level, setLevel] = useState('1')
  const [filter, setFilter] = useState<FieldFilter>({ query: '', showZero: true, showUnsupported: true })
  const [data, setData] = useState<AbilityFieldsData>({ summary: '', detail: '', rows: [] })
  const [feedback, setFeedback] = useState<{ text: string; error?: boolean } | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const code = rawcode.trim()
  const name = useCatalogName('ability', code)

  const read = () => run('read', async () => {
    if (!code) {
      setFeedback({ text: t('请输入技能 ID，例如 AHbz。'), error: true })
      return
    }
    setFeedback(null)
    setEditingId(null)
    try {
      const result = await api.readAbilityFields(code, level.trim() || '1', filter.query.trim(), filter.showZero, filter.showUnsupported)
      setData({ summary: result.summary, detail: result.detail, rows: result.rows ?? [] })
      if (!result.rows?.length) setFeedback({ text: t('没有找到这个技能的字段。确认游戏在运行，并选中了拥有这个技能的单位。') })
    } catch (err) {
      setData({ summary: '', detail: '', rows: [] })
      setFeedback({ text: `${t('读取失败：')}${err instanceof Error ? err.message : String(err)}`, error: true })
      throw err
    }
  })

  const write = (row: FieldRow, value: string, rect: DOMRect | null) => run(`write-${row.id}`, async () => {
    try {
      const result = await api.writeAbilityField(row.id, value)
      if (result?.data) setData(result.data)
      floatChange(rect, row.value, value, t('已写入'))
      setFeedback({ text: `${t('已写入')} ${row.name}：${value}` })
    } catch (err) {
      // api.ts throws on success: false; the reason is also shown as a notice.
      setFeedback({ text: `${t('写入失败：')}${err instanceof Error ? err.message : String(err)}`, error: true })
      throw err
    }
  })

  const visible = filterFields<AbilityFieldRow>(data.rows, filter)
  const rows: FieldRow[] = visible.map(r => ({
    id: r._iid, name: r.name || r.field, sub: r.name ? r.field : undefined, value: r.value, type: r.type, status: r.status,
    note: [r.scope && `${t('作用域')} ${r.scope}`, r.field].filter(Boolean).join('　'),
  }))

  useCommandCard([
    { key: 'Q', icon: 'read', title: t('读取技能字段'), description: t('按技能 ID 和等级读取选中单位身上这个技能的全部字段。'), pending: pending.read, estimateMs: 900, disabled: !connected, onPress: () => void read() },
    { key: 'W', icon: 'write', title: t('修改字段'), description: t('编辑字段表里选中的那一行，回车写入游戏。'), pending: selectedId ? pending[`write-${selectedId}`] : false, estimateMs: 500, disabled: !connected,
      onPress: () => selectedId ? setEditingId(selectedId) : announce(t('先在字段表里选一行。')) },
    { key: 'A', icon: 'search', title: t('显示数值为 0 的项'), description: t('切换是否列出数值为 0 的字段。'), active: filter.showZero, onPress: () => setFilter(f => ({ ...f, showZero: !f.showZero })) },
    { key: 'S', icon: 'catalog', title: t('显示未支持字段'), description: t('切换是否列出尚未开放或未确认的字段。'), active: filter.showUnsupported, onPress: () => setFilter(f => ({ ...f, showUnsupported: !f.showUnsupported })) },
  ])

  return (
    <div className={s.page}>
      <div className={s.subject}>
        <span className={s.socket} aria-hidden="true"><Icon name="add-ability" /></span>
        <div className={s.identity}>
          <p className={s.name} data-empty={!name || undefined}>{name ?? (code ? code : t('输入技能 ID'))}</p>
          <TextField
            className={s.code}
            aria-label={t('技能 ID')}
            placeholder="AHbz"
            maxLength={4}
            spellCheck={false}
            value={rawcode}
            onChange={e => setRawcode(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') void read() }}
          />
        </div>
        <TextField
          className={s.level}
          label={t('技能等级')}
          inputMode="numeric"
          value={level}
          onChange={e => setLevel(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') void read() }}
        />
        <span className={s.spacer} />
        <Button variant="cast" icon="read" disabled={!connected || pending.read} onClick={() => void read()}>{t('读取技能字段')}</Button>
      </div>

      <FieldFilters filter={filter} onChange={setFilter} summary={data.summary} shown={visible.length} total={data.rows.length} />
      {data.detail && <p className={s.detail}>{t(data.detail)}</p>}
      {feedback && <div className={s.feedback}><Status tone={feedback.error ? 'error' : 'info'}>{feedback.text}</Status></div>}

      <FieldTable
        label={t('技能字段')}
        rows={rows}
        grouped={false}
        selectedId={selectedId}
        onSelect={setSelectedId}
        editingId={editingId}
        onEditingChange={setEditingId}
        onCommit={(row, value, rect) => void write(row, value, rect)}
        empty={pending.read ? t('正在读取技能字段…') : data.rows.length
          ? t('没有匹配的字段。')
          : t('输入技能 ID（例如 AHbz 暴风雪、AHfs 烈焰风暴、AHab 辉煌光环），在游戏里选中拥有这个技能的单位，再读取。')}
        keys={[{ key: 'W', label: t('修改') }]}
      />
    </div>
  )
}
