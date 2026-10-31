import { useEffect, useMemo, useState } from 'react'
import { Button, EditableNumber, Icon, PillGroup, RawcodePlate, StatBar, TextField, announce, bounty } from '../../../ds'
import { api } from '../../../lib/api'
import type { CandidateUnit, SelectedUnitData, UnitFieldRow } from '../../../lib/types'
import { useCommandCard } from '../../state/commands'
import { unitLockId, useLocks } from '../../state/locks'
import { num } from '../../state/resources'
import { useSystem } from '../../state/system'
import { rawcodeOf, useUnit } from '../../state/unit'
import { useT } from '../../i18n'
import { FieldTable, type FieldRow } from '../common/FieldTable'
import { Status, usePending } from '../common/Layout'
import s from './UnitPage.module.css'

/** The six core targets write_selected_unit understands; empty means "leave as is". */
type CoreKey = 'hpTarget' | 'hpRegenTarget' | 'mpTarget' | 'mpRegenTarget' | 'xTarget' | 'yTarget'
const EMPTY_TARGETS: Record<CoreKey, string> = { hpTarget: '', hpRegenTarget: '', mpTarget: '', mpRegenTarget: '', xTarget: '', yTarget: '' }

const fmt = (n: number) => String(Number(n.toFixed(2)))
const signed = (n: number) => `${n > 0 ? '+' : '−'}${fmt(Math.abs(n))}`

export default function UnitPage() {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const unit = useUnit(st => st.unit)
  const locks = useLocks(st => st.items)
  const { pending, run } = usePending()
  const [category, setCategory] = useState('全部')
  const [query, setQuery] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [candidate, setCandidate] = useState<string | null>(null)

  useEffect(() => { void useLocks.getState().reload() }, [])

  const received = (data: SelectedUnitData | undefined | null) => { if (data) useUnit.getState().received(data) }
  const fields = useMemo(() => unit?.fields ?? [], [unit])
  const categories = useMemo(() => ['全部', ...new Set(fields.map(f => f.category))], [fields])
  useEffect(() => { if (!categories.includes(category)) setCategory('全部') }, [categories, category])

  const q = query.trim().toLowerCase()
  const visible = fields.filter(f =>
    (category === '全部' || f.category === category)
    && (!q || [f.label, f.value, f.address, f.note].some(x => x.toLowerCase().includes(q))))
  const rows: FieldRow[] = visible.map(f => ({
    id: f._iid, group: f.category, name: f.label, value: f.value, type: f.type, address: f.address, note: f.note,
    locked: locks.some(l => l._iid === unitLockId(f._iid)),
  }))
  const selected = fields.find(f => f._iid === selectedId) ?? null

  const writeCore = (key: CoreKey, value: number, before: number | null, rect: DOMRect | null) => run(`core-${key}`, async () => {
    const result = await api.writeSelectedUnit({ ...EMPTY_TARGETS, [key]: fmt(value) })
    if (!result?.success || !result.data) return
    received(result.data)
    if (before !== null && value !== before && rect) bounty({ anchor: rect, text: signed(value - before) })
  })

  const writeField = (row: FieldRow, value: string, rect: DOMRect | null) => run(`field-${row.id}`, async () => {
    const result = await api.writeUnitField(row.id, value)
    if (!result?.success || !result.data) return
    received(result.data)
    const before = num(row.value), after = num(result.data.fields.find(f => f._iid === row.id)?.value)
    if (before !== null && after !== null && after !== before) bounty({ anchor: rect, text: signed(after - before) })
  })

  const toggleLock = (field: UnitFieldRow | null) => run('lock', async () => {
    if (!field) return announce(t('请先选择需要操作的单位字段。'))
    const id = unitLockId(field._iid)
    if (useLocks.getState().items.some(l => l._iid === id)) {
      if (await useLocks.getState().remove(id)) announce(t('已解除锁定'))
      return
    }
    const result = await api.addUnitFieldLock(field._iid, field.value)
    if (result?.success) {
      useLocks.getState().set(result.locks)
      announce(`${t('已锁定')} ${field.label}=${field.value}`)
    }
  })

  const refreshFields = () => run('refresh', async () => received(await api.readSelectedUnit()))
  const native = () => run('native', async () => {
    const result = await api.readNativeSelection()
    if (result?.success) received(result.unit)
  })

  const listCandidates = () => run('list', async () => {
    const rows = await api.refreshUnitCandidates()
    if (rows) useUnit.setState({ candidates: rows })
  })
  const readCandidate = (iid: string | null) => run('read', async () => {
    if (!iid) return announce(t('先在候选单位列表里选一个。'))
    setCandidate(iid)
    const result = await api.readSelectionCandidate(iid)
    if (result?.success) received(result.unit)
  })

  const copyAddress = () => {
    if (!selected) return announce(t('请先选择需要操作的单位字段。'))
    navigator.clipboard?.writeText(selected.address).then(() => announce(`${t('已复制地址')} ${selected.address}`), () => {})
  }

  useCommandCard([
    { key: 'W', icon: 'write', title: t('修改字段'), description: t('编辑字段表里选中的那一行，回车写入游戏。'), pending: selectedId ? pending[`field-${selectedId}`] : false, estimateMs: 500, disabled: !connected,
      onPress: () => selectedId ? setEditingId(selectedId) : announce(t('请先选择需要操作的单位字段。')) },
    { key: 'E', icon: 'refresh', title: t('刷新字段表'), description: t('重新读取当前单位的全部字段，不切换单位。'), pending: pending.refresh, estimateMs: 800, disabled: !connected, onPress: () => void refreshFields() },
    { key: 'R', icon: 'lock', title: t('锁定字段'), description: t('把选中字段冻在当前数值，游戏改动后会被改回来。再按一次解锁。'), pending: pending.lock, disabled: !connected, onPress: () => void toggleLock(selected),
      active: selectedId ? locks.some(l => l._iid === unitLockId(selectedId)) : undefined },
    { key: 'A', icon: 'candidates', title: t('列出候选单位'), description: t('检索游戏内存里可能是当前选中单位的候选，放进左侧列表。'), pending: pending.list, estimateMs: 1100, disabled: !connected, onPress: () => void listCandidates() },
    { key: 'D', icon: 'unit-hero', title: t('读取所选候选'), description: t('把左侧列表里选中的候选当作当前单位读取。'), pending: pending.read, estimateMs: 900, disabled: !connected || !candidate, onPress: () => void readCandidate(candidate) },
    { key: 'S', icon: 'locate', title: t('Native 定位'), description: t('用游戏内部函数重新定位选中单位。读出来的数不对时再用。'), pending: pending.native, estimateMs: 1400, disabled: !connected, onPress: () => void native() },
    { key: 'Z', icon: 'copy', title: t('复制地址'), description: t('把选中字段的内存地址复制到剪贴板。'), disabled: !selected, onPress: copyAddress },
  ])

  return (
    <div className={s.page}>
      <aside className={s.dossier} aria-label={t('单位卷宗')}>
        <Dossier unit={unit} connected={connected} pending={pending} writeCore={writeCore} />
        <Candidates
          connected={connected}
          selected={candidate}
          onSelect={setCandidate}
          onList={() => void listCandidates()}
          onRead={iid => void readCandidate(iid)}
          listing={!!pending.list}
          reading={!!pending.read}
        />
      </aside>

      <section className={s.ledger} aria-label={t('单位动态字段表')}>
        <div className={s.toolbar}>
          <PillGroup<string>
            label={t('按分类筛选')}
            value={category}
            onChange={setCategory}
            className={s.pills}
            options={categories.map(c => ({ value: c, label: t(c), count: c === '全部' ? fields.length : fields.filter(f => f.category === c).length }))}
          />
          <TextField variant="search" aria-label={t('搜索字段')} placeholder={t('搜字段名、数值、地址或说明')} value={query} onChange={e => setQuery(e.target.value)} className={s.search} />
        </div>
        <FieldTable
          label={t('单位动态字段表')}
          rows={rows}
          grouped={category === '全部' && !q}
          selectedId={selectedId}
          onSelect={setSelectedId}
          editingId={editingId}
          onEditingChange={setEditingId}
          onCommit={(row, value, rect) => void writeField(row, value, rect)}
          onToggleLock={row => void toggleLock(fields.find(f => f._iid === row.id) ?? null)}
          empty={unit?.hasSelection ? t('没有匹配的字段。') : t('还没有读取单位。在游戏里选中单位后按 Q。')}
          keys={[{ key: 'W', label: t('修改') }, { key: 'R', label: t('锁定') }, { key: 'Z', label: t('复制地址') }]}
        />
      </section>
    </div>
  )
}

function Dossier({ unit, connected, pending, writeCore }: {
  unit: SelectedUnitData | null
  connected: boolean
  pending: Record<string, boolean>
  writeCore(key: CoreKey, value: number, before: number | null, rect: DOMRect | null): void
}) {
  const t = useT()
  const names = useUnit(st => st.names)
  const language = useSystem(st => st.status.language)
  const code = rawcodeOf(unit?.unitTypeId)
  const name = code ? names[code] : null
  const has = !!unit?.hasSelection && !!code

  const editable = (key: CoreKey, label: string, raw: string | undefined, suffix = '') => {
    const value = num(raw)
    if (!has || !connected || value === null) return <span className={s.none}>—</span>
    return (
      <span className={s.coreValue} data-busy={pending[`core-${key}`] || undefined}>
        <EditableNumber text={fmt(value)} label={label} onCommit={(n, rect) => writeCore(key, n, value, rect)} />
        {suffix && <span className={s.suffix}>{suffix}</span>}
      </span>
    )
  }

  return (
    <div className={s.identity}>
      <h2 className={s.name}>{has ? ((language === 'en' ? name?.en : name?.zh) || name?.zh || code) : t('未读取单位')}</h2>
      <div className={s.meta}>
        {code && <RawcodePlate code={code} />}
        {unit?.identity && <span className={s.identityText} title={unit.identity}>{unit.identity}</span>}
      </div>

      <div className={s.core}>
        <StatBar kind="life" label={t('生命')} value={num(unit?.hp.current) ?? 0} max={num(unit?.hp.max) ?? 0} />
        <div className={s.coreRow}>
          <span className={s.coreLabel}>{t('当前')}</span>{editable('hpTarget', t('当前生命'), unit?.hp.current)}
          <span className={s.coreLabel}>{t('回复')}</span>{editable('hpRegenTarget', t('生命回复'), unit?.hp.regen, '/s')}
        </div>
        <StatBar kind="mana" label={t('魔法')} value={num(unit?.mp.current) ?? 0} max={num(unit?.mp.max) ?? 0} />
        <div className={s.coreRow}>
          <span className={s.coreLabel}>{t('当前')}</span>{editable('mpTarget', t('当前魔法'), unit?.mp.current)}
          <span className={s.coreLabel}>{t('回复')}</span>{editable('mpRegenTarget', t('魔法回复'), unit?.mp.regen, '/s')}
        </div>
        <div className={s.coreRow}>
          <span className={s.coreLabel}><Icon name="locate" tone="muted" /> X</span>{editable('xTarget', t('X 坐标'), unit?.position.xCurrent)}
          <span className={s.coreLabel}>Y</span>{editable('yTarget', t('Y 坐标'), unit?.position.yCurrent)}
        </div>
      </div>
    </div>
  )
}

function Candidates({ connected, selected, onSelect, onList, onRead, listing, reading }: {
  connected: boolean
  selected: string | null
  onSelect(iid: string): void
  onList(): void
  onRead(iid: string | null): void
  listing: boolean
  reading: boolean
}) {
  const t = useT()
  const candidates = useUnit(st => st.candidates)

  const describe = (c: CandidateUnit) => [
    `${t('可信度')} ${c.confidence}`, `${t('生命')} ${c.hp}`, `${t('魔法')} ${c.mp}`, `${t('坐标')} ${c.position}`,
    `refs/known ${c.evidence}`, `${t('组件')} ${c.components}`, `${t('物品槽')} ${c.inventory}`, `handle ${c.handle}`, `owner ${c.owner}`, `unit ${c.unit}`,
  ].join('\n')

  return (
    <section className={s.candidates}>
      <header className={s.candHead}>
        <h3 className={s.subhead}>{t('候选单位')}（{candidates.length}）</h3>
        <Button size="sm" disabled={!connected || listing} onClick={onList}>{t('列出候选单位')}</Button>
        <Button size="sm" disabled={!connected || !selected || reading} onClick={() => onRead(selected)}>{t('读取所选')}</Button>
      </header>
      {candidates.length === 0 ? (
        <p className={s.empty}>{t('暂无候选单位。点“列出候选单位”检索。')}</p>
      ) : (
        <ul className={s.candList} role="listbox" aria-label={t('候选单位')}>
          {candidates.map(c => (
            <li
              key={c._iid}
              role="option"
              aria-selected={selected === c._iid}
              tabIndex={0}
              className={s.cand}
              title={describe(c)}
              onClick={() => onSelect(c._iid)}
              onDoubleClick={() => onRead(c._iid)}
              onKeyDown={e => {
                if (e.key === 'Enter') onRead(c._iid)
                if (e.key === ' ') { e.preventDefault(); onSelect(c._iid) }
              }}
            >
              <span className={s.candIndex}>{c.index}</span>
              <span className={s.candMain}>
                <span>{t('生命')} {c.hp}　{t('魔法')} {c.mp}</span>
                <span className={s.candSub}>{c.position}　{t('可信度')} {c.confidence}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
      {reading && <Status tone="busy">{t('正在读取候选单位…')}</Status>}
      <p className={s.candHint}>{t('双击或回车读取该候选单位；鼠标停留可看全部证据。')}</p>
    </section>
  )
}
