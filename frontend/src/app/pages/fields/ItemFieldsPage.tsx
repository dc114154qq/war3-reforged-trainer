import { useState, type CSSProperties } from 'react'
import { Button, PillGroup, TextField, announce, cx } from '../../../ds'
import { api } from '../../../lib/api'
import type { ItemFieldRow, ItemFieldsData } from '../../../lib/types'
import { useCommandCard } from '../../state/commands'
import { useSystem } from '../../state/system'
import { useT } from '../../i18n'
import { FieldTable, type FieldRow } from '../common/FieldTable'
import { Status, usePending } from '../common/Layout'
import { FieldFilters, filterFields, floatChange, type FieldFilter } from './shared'
import s from './Fields.module.css'

type Mode = 'basic' | 'effects'
type Area = 'classic' | 'bag' | 'equipment'

const EQUIPMENT_SLOTS = ['头部', '胸部', '手套', '靴子', '戒指 1', '戒指 2', '主手', '副手', '饰品']
const EMPTY: ItemFieldsData = { summary: '', detail: '', rows: [] }

/** Slot grids as the game lays them out: 2 × 3 inventory, 10 × 3 bag, 3 × 3 equipment. */
function slotsOf(mode: Mode, area: Area): { labels: string[]; cols: number; wide?: boolean } {
  if (mode === 'effects' && area === 'bag') return { labels: Array.from({ length: 30 }, (_, i) => String(i + 1)), cols: 10 }
  if (mode === 'effects' && area === 'equipment') return { labels: EQUIPMENT_SLOTS, cols: 3, wide: true }
  return { labels: ['1', '2', '3', '4', '5', '6'], cols: 2 }
}

export default function ItemFieldsPage() {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const { pending, run } = usePending()
  const [mode, setMode] = useState<Mode>('basic')
  const [area, setArea] = useState<Area>('classic')
  const [level, setLevel] = useState('1')
  const [slot, setSlot] = useState('0')
  const [filter, setFilter] = useState<FieldFilter>({ query: '', showZero: true, showUnsupported: true })
  const [data, setData] = useState<ItemFieldsData>(EMPTY)
  const [feedback, setFeedback] = useState<{ text: string; error?: boolean } | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const busy = !!pending.read || Object.entries(pending).some(([k, v]) => v && k.startsWith('write-'))

  /** Changing what is inspected invalidates the rows: their ids belong to the old read. */
  const reset = () => { setData(EMPTY); setFeedback(null); setEditingId(null) }

  const read = (target = slot) => run('read', async () => {
    setSlot(target)
    reset()
    try {
      const result = mode === 'effects'
        ? await api.readItemEffectFields(area, target, level.trim() || '1')
        : await api.readItemFields(target, filter.query.trim(), filter.showZero, filter.showUnsupported)
      setData({ summary: result.summary, detail: result.detail, rows: result.rows ?? [] })
      if (!result.rows?.length) setFeedback({ text: t('这个槽位是空的，或者没有读到物品字段。') })
    } catch (err) {
      setFeedback({ text: `${t('读取失败：')}${err instanceof Error ? err.message : String(err)}`, error: true })
      throw err
    }
  })

  const write = (row: FieldRow, value: string, rect: DOMRect | null) => run(`write-${row.id}`, async () => {
    try {
      const result = mode === 'effects' ? await api.writeItemEffectField(row.id, value) : await api.writeItemField(row.id, value)
      if (result?.data) setData(result.data)
      floatChange(rect, row.value, value, t('已写入'))
      setFeedback({ text: `${t('已写入')} ${row.name}：${value}` })
    } catch (err) {
      // api.ts throws on success: false. As in 2.1.22 the table is cleared: the backend drops
      // the item snapshot after a failed write, so the row ids are stale.
      reset()
      setFeedback({ text: `${t('写入失败：')}${err instanceof Error ? err.message : String(err)}`, error: true })
      throw err
    }
  })

  const visible = filterFields<ItemFieldRow>(data.rows, filter)
  const rows: FieldRow[] = visible.map(r => {
    const source = r.ability ? `${r.ability} / ${r.effectClass}　${r.scope === 'level' ? `${t('等级')} ${level || 1}` : t('通用')}` : ''
    return {
      id: r._iid, name: r.name || r.field, sub: source || (r.name ? r.field : undefined), value: r.value, type: r.type, status: r.status,
      note: [r.note, source || r.field].filter(Boolean).join('　'), readOnly: r.editable === false,
    }
  })

  const grid = slotsOf(mode, area)
  const switchMode = (next: Mode) => { setMode(next); setSlot('0'); reset() }
  const switchArea = (next: Area) => { setArea(next); setSlot('0'); reset() }

  useCommandCard([
    { key: 'Q', icon: 'read', title: t('读取选定槽位'), description: t('读取选中单位这个槽位上物品的字段。'), pending: pending.read, estimateMs: 900, disabled: !connected, onPress: () => void read() },
    { key: 'W', icon: 'write', title: t('修改字段'), description: t('编辑字段表里选中的那一行，回车写入游戏。'), pending: selectedId ? pending[`write-${selectedId}`] : false, estimateMs: 500, disabled: !connected,
      onPress: () => selectedId ? setEditingId(selectedId) : announce(t('先在字段表里选一行。')) },
    { key: 'E', icon: 'add-item', title: t('物品基础字段'), description: t('查看和修改物品自身的字段。'), active: mode === 'basic', disabled: busy, onPress: () => switchMode('basic') },
    { key: 'R', icon: 'add-ability', title: t('装备加成 / 附带技能'), description: t('查看和修改物品附带技能提供的加成。'), active: mode === 'effects', disabled: busy, onPress: () => switchMode('effects') },
    { key: 'A', icon: 'search', title: t('显示数值为 0 的项'), description: t('切换是否列出数值为 0 的字段。'), active: filter.showZero, onPress: () => setFilter(f => ({ ...f, showZero: !f.showZero })) },
    { key: 'S', icon: 'catalog', title: t('显示未支持字段'), description: t('切换是否列出尚未开放或未确认的字段。'), active: filter.showUnsupported, onPress: () => setFilter(f => ({ ...f, showUnsupported: !f.showUnsupported })) },
  ])

  return (
    <div className={s.page}>
      <div className={s.subject}>
        <div
          className={cx(s.slots, grid.wide && s.slotsWide)}
          style={{ '--cols': grid.cols } as CSSProperties}
          role="group"
          aria-label={t('物品槽位')}
        >
          {grid.labels.map((label, i) => (
            <button
              key={label}
              type="button"
              className={s.slot}
              data-wide={grid.wide || undefined}
              aria-pressed={slot === String(i)}
              aria-label={grid.wide ? t(label) : `${t('槽位')} ${label}`}
              disabled={busy}
              onClick={() => void read(String(i))}
            >
              {grid.wide ? t(label) : label}
            </button>
          ))}
        </div>
        <div className={s.identity}>
          <PillGroup<Mode>
            label={t('编辑内容')}
            value={mode}
            onChange={switchMode}
            options={[{ value: 'basic', label: t('物品基础字段') }, { value: 'effects', label: t('装备加成 / 附带技能') }]}
          />
          {mode === 'effects' && (
            <div className={s.modes}>
              <PillGroup<Area>
                label={t('物品位置')}
                value={area}
                onChange={switchArea}
                options={[{ value: 'classic', label: t('普通物品栏') }, { value: 'bag', label: t('3.0 扩展背包') }, { value: 'equipment', label: t('3.0 装备栏') }]}
              />
              <TextField
                className={s.level}
                aria-label={t('物品技能字段等级')}
                suffix={t('级')}
                inputMode="numeric"
                value={level}
                disabled={busy}
                onChange={e => { setLevel(e.target.value); reset() }}
              />
            </div>
          )}
        </div>
        <span className={s.spacer} />
        <Button variant="cast" icon="read" disabled={!connected || busy} onClick={() => void read()}>{t('读取选定槽位')}</Button>
      </div>

      <FieldFilters filter={filter} onChange={setFilter} summary={data.summary} shown={visible.length} total={data.rows.length} />
      {data.detail && <p className={s.detail}>{t(data.detail)}</p>}
      {feedback && <div className={s.feedback}><Status tone={feedback.error ? 'error' : 'info'}>{feedback.text}</Status></div>}

      <FieldTable
        label={t('物品字段')}
        rows={rows}
        grouped={false}
        selectedId={selectedId}
        onSelect={setSelectedId}
        editingId={editingId}
        onEditingChange={setEditingId}
        onCommit={(row, value, rect) => void write(row, value, rect)}
        empty={pending.read ? t('正在读取物品字段…') : data.rows.length
          ? t('没有匹配的字段。')
          : t('在游戏里选中带物品的英雄或单位，点一个槽位读取。基础字段和附带技能分开读取；地图脚本算出的效果以游戏内为准。')}
        keys={[{ key: 'W', label: t('修改') }]}
      />
    </div>
  )
}
