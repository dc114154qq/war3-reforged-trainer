import { useEffect, useRef, useState, type ReactNode, type RefObject } from 'react'
import { Button, EditableNumber, Icon, PlayerSwatch, TextField, announce, bounty, type BountyTone, type IconName, type IconTone } from '../../../ds'
import { api } from '../../../lib/api'
import type { GoldMineData, ResourceGroup, ResourceSnapshot } from '../../../lib/types'
import { useCommandCard } from '../../state/commands'
import { resourceLockId, useLocks } from '../../state/locks'
import { num, useResources, type AddKind, type SetKind } from '../../state/resources'
import { useSystem } from '../../state/system'
import { useT } from '../../i18n'
import { DataTable } from '../common/DataTable'
import { Hint, PageBody, Row, Section, Status, usePending } from '../common/Layout'
import s from './ResourcesPage.module.css'

const CURRENT: Record<SetKind, keyof ResourceSnapshot['current']> = { gold: 'gold', lumber: 'lumber', food_used: 'food', food_cap: 'foodCap' }
const TONE: Record<SetKind, BountyTone> = { gold: 'gold', lumber: 'lumber', food_used: 'plain', food_cap: 'plain' }

/**
 * The player colour of a resource group, when the backend's label names the player:
 * "2 (Player 1)" for the game's own player state, "3 (h5/p1)" for a group found in memory.
 * Player numbers are 0-based as in JASS; anything outside the twelve colours gets none.
 */
const slotOf = (group: string) => {
  const m = /\(Player (\d+)\)|\/p(\d+)\)/.exec(group)
  if (!m) return null
  const slot = Number(m[1] ?? m[2])
  return slot >= 0 && slot < 12 ? slot : null
}

const signed = (n: number) => `${n > 0 ? '+' : '−'}${Math.abs(n)}`

export default function ResourcesPage() {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const snapshot = useResources(st => st.snapshot)
  const locks = useLocks(st => st.items)
  const { pending, run } = usePending()
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null)
  const [delta, setDelta] = useState('')
  const goldRef = useRef<HTMLSpanElement>(null)
  const lumberRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    void useResources.getState().poll()
    void useLocks.getState().reload()
  }, [])
  useEffect(() => { if (snapshot && !delta) setDelta(snapshot.delta || '10000') }, [snapshot, delta])
  // The backend writes and locks the group selected on its side, which the snapshot does not
  // report; select ours explicitly whenever it is missing or no longer listed.
  const groupIds = snapshot?.groups.map(g => g._iid).join('|') ?? ''
  useEffect(() => {
    const ids = groupIds ? groupIds.split('|') : []
    if (!ids.length || (selectedGroup && ids.includes(selectedGroup))) return
    void syncGroup(ids[0])
  }, [groupIds]) // eslint-disable-line react-hooks/exhaustive-deps

  const value = (kind: SetKind) => num(snapshot?.current[CURRENT[kind]])
  const isLocked = (kind: SetKind) => locks.some(l =>
    selectedGroup ? l._iid === resourceLockId(selectedGroup, kind) : l._iid.startsWith('resource:') && l._iid.endsWith(`:${kind}`))
  const lockOf = (kind: SetKind) => locks.find(l => l._iid.startsWith('resource:') && l._iid.endsWith(`:${kind}`)
    && (!selectedGroup || l._iid === resourceLockId(selectedGroup, kind)))

  const setValue = (kind: SetKind, next: number, rect: DOMRect | null) => run(`set-${kind}`, async () => {
    const before = value(kind)
    const after = await useResources.getState().set(kind, String(Math.round(next)))
    const now = num(after?.current[CURRENT[kind]])
    if (before !== null && now !== null && now !== before) bounty({ anchor: rect, text: signed(now - before), tone: TONE[kind] })
  })

  /** Lock at the value shown: write it as the target first, since the backend locks its target. */
  const toggleLock = (kind: SetKind) => run(`lock-${kind}`, async () => {
    const existing = lockOf(kind)
    if (existing) {
      if (await useLocks.getState().remove(existing._iid)) announce(t('已解除锁定'))
      return
    }
    const current = value(kind)
    if (current === null) return announce(t('先读取资源组，再锁定。'))
    if (!(await useResources.getState().set(kind, String(current)))) return
    const result = await api.addResourceLock(kind)
    if (result?.success) {
      useLocks.getState().set(result.locks)
      announce(t('已锁定'))
    }
  })

  const add = (kind: AddKind) => run(`add-${kind}`, async () => {
    const before = { gold: value('gold'), lumber: value('lumber') }
    const after = await useResources.getState().add(kind, delta.trim() || '0')
    if (!after) return
    for (const [key, ref] of [['gold', goldRef], ['lumber', lumberRef]] as const) {
      const was = before[key], now = num(after.current[key])
      if (was !== null && now !== null && now !== was) bounty({ anchor: ref.current, text: signed(now - was), tone: key })
    }
  })

  /** Select a group on both sides; the backend resets its targets to that group's values. */
  const syncGroup = (iid: string) => run('select', async () => {
    setSelectedGroup(iid)
    const next = await api.selectResourceGroup(iid)
    if (next) useResources.setState({ snapshot: next })
  })

  const readGroups = () => run('groups', async () => {
    const result = await api.refreshResources()
    if (!result?.data) return
    useResources.setState({ snapshot: result.data })
    // Keep the group the user picked when it is still there.
    const ids = result.data.groups.map(g => g._iid)
    if (ids.length) await syncGroup(selectedGroup && ids.includes(selectedGroup) ? selectedGroup : ids[0])
  })

  const selectGroup = (group: ResourceGroup) => syncGroup(group._iid)

  useCommandCard([
    { key: 'Q', icon: 'read', title: t('读取全部资源组'), description: t('从游戏内存重新查找所有玩家的资源组，刷新金币、木材和人口。'), pending: pending.groups, estimateMs: 900, disabled: !connected, onPress: () => void readGroups() },
    { key: 'W', icon: 'gold', title: t('金币 ±'), description: t('金币加上“单次增量”；增量写负数就是减少。'), pending: pending['add-gold'], estimateMs: 500, disabled: !connected, onPress: () => void add('gold') },
    { key: 'E', icon: 'lumber', title: t('木材 ±'), description: t('木材加上“单次增量”；增量写负数就是减少。'), pending: pending['add-lumber'], estimateMs: 500, disabled: !connected, onPress: () => void add('lumber') },
    { key: 'R', icon: 'gold-mine', title: t('金木一起 ±'), description: t('金币和木材同时加上“单次增量”。'), pending: pending['add-both'], estimateMs: 500, disabled: !connected, onPress: () => void add('both') },
    { key: 'A', icon: 'lock', title: t('锁定金币'), description: t('把金币冻在当前数值，游戏改动后会被改回来。再按一次解锁。'), pending: pending['lock-gold'], active: isLocked('gold'), disabled: !connected, onPress: () => void toggleLock('gold') },
    { key: 'S', icon: 'lock', title: t('锁定木材'), description: t('把木材冻在当前数值。再按一次解锁。'), pending: pending['lock-lumber'], active: isLocked('lumber'), disabled: !connected, onPress: () => void toggleLock('lumber') },
  ])

  return (
    <PageBody>
      <div className={s.treasury}>
        <Treasure icon="gold" tone="gold" label={t('金币')} valueRef={goldRef}
          value={value('gold')} locked={isLocked('gold')} disabled={!connected}
          onCommit={(n, rect) => void setValue('gold', n, rect)} onLock={() => void toggleLock('gold')} />
        <Treasure icon="lumber" tone="lumber" label={t('木材')} valueRef={lumberRef}
          value={value('lumber')} locked={isLocked('lumber')} disabled={!connected}
          onCommit={(n, rect) => void setValue('lumber', n, rect)} onLock={() => void toggleLock('lumber')} />
        <div className={s.treasure}>
          <span className={s.caption}><Icon name="food" tone="wheat" /> {t('人口')}</span>
          <span className={s.big}>
            <Amount value={value('food_used')} label={t('已用人口')} disabled={!connected} onCommit={(n, rect) => void setValue('food_used', n, rect)} locked={isLocked('food_used')} />
            <span className={s.slash}>/</span>
            <Amount value={value('food_cap')} label={t('人口上限')} disabled={!connected} onCommit={(n, rect) => void setValue('food_cap', n, rect)} locked={isLocked('food_cap')} />
          </span>
          <span className={s.locks}>
            <LockButton locked={isLocked('food_used')} disabled={!connected} onClick={() => void toggleLock('food_used')}>{t('锁已用')}</LockButton>
            <LockButton locked={isLocked('food_cap')} disabled={!connected} onClick={() => void toggleLock('food_cap')}>{t('锁上限')}</LockButton>
          </span>
        </div>
      </div>

      <Row className={s.delta}>
        <TextField label={t('单次增量')} value={delta} onChange={e => setDelta(e.target.value)} inputMode="numeric" className={s.deltaField} />
        <Button disabled={!connected} onClick={() => void add('gold')}>{t('金币 ±')}</Button>
        <Button disabled={!connected} onClick={() => void add('lumber')}>{t('木材 ±')}</Button>
        <Button disabled={!connected} onClick={() => void add('both')}>{t('金木一起 ±')}</Button>
        <span className={s.deltaHint}>{t('增量写负数就是减少。')}</span>
      </Row>

      <Section title={`${t('资源组')}（${snapshot?.groups.length ?? 0}）`} actions={
        <Button size="sm" icon="refresh" disabled={!connected || pending.groups} onClick={() => void readGroups()}>{t('读取全部资源组')}</Button>
      }>
        <DataTable<ResourceGroup>
          label={t('资源组')}
          rows={snapshot?.groups ?? []}
          rowKey={g => g._iid}
          selected={selectedGroup}
          onSelect={g => void selectGroup(g)}
          empty={t('还没有资源组。连接游戏、进入地图后点“读取全部资源组”。')}
          columns={[
            { key: 'group', label: t('资源组'), width: 'minmax(170px, 1.6fr)', render: g => {
              const slot = slotOf(g.group)
              return <span className={s.group}>{slot !== null && <PlayerSwatch slot={slot} />}{t(g.group)}</span>
            } },
            { key: 'gold', label: t('金币'), width: '90px', render: g => <span className={s.goldText}>{g.gold}</span> },
            { key: 'lumber', label: t('木材'), width: '90px', render: g => <span className={s.lumberText}>{g.lumber}</span> },
            { key: 'food', label: t('人口'), width: '80px' },
            { key: 'gold_address', label: t('金币地址'), width: '112px', mono: true },
            { key: 'lumber_address', label: t('木材地址'), width: '112px', mono: true },
            { key: 'source', label: t('来源'), width: 'minmax(120px, 1.2fr)', render: g => <span className={s.dim}>{g.source}</span> },
          ]}
        />
      </Section>

      <GoldMines connected={connected} />
    </PageBody>
  )
}

function Treasure({ icon, tone, label, value, locked, disabled, onCommit, onLock, valueRef }: {
  icon: IconName
  tone: IconTone
  label: string
  value: number | null
  locked: boolean
  disabled: boolean
  onCommit(n: number, rect: DOMRect | null): void
  onLock(): void
  valueRef: RefObject<HTMLSpanElement | null>
}) {
  const t = useT()
  return (
    <div className={s.treasure}>
      <span className={s.caption}><Icon name={icon} tone={tone} /> {label}</span>
      <span className={s.big} ref={valueRef}>
        <Amount value={value} label={label} disabled={disabled} onCommit={onCommit} locked={locked} />
      </span>
      <span className={s.locks}>
        <LockButton locked={locked} disabled={disabled} onClick={onLock}>{locked ? t('解锁') : t('锁定')}</LockButton>
      </span>
    </div>
  )
}

function Amount({ value, label, disabled, locked, onCommit }: {
  value: number | null
  label: string
  disabled: boolean
  locked: boolean
  onCommit(n: number, rect: DOMRect | null): void
}) {
  if (value === null || disabled) return <span className={s.unknown} aria-label={`${label} —`}>—</span>
  return (
    <span className={s.amount} data-locked={locked || undefined}>
      <EditableNumber text={String(value)} label={label} onCommit={onCommit} />
    </span>
  )
}

function LockButton({ locked, disabled, onClick, children }: { locked: boolean; disabled: boolean; onClick(): void; children: ReactNode }) {
  return (
    <button type="button" className={s.lockButton} aria-pressed={locked} disabled={disabled} onClick={onClick}>
      <Icon name="lock" tone={locked ? 'frost' : 'muted'} />
      {children}
    </button>
  )
}

/** Remaining gold in each mine: read or set for the selection or the whole map. */
function GoldMines({ connected }: { connected: boolean }) {
  const t = useT()
  const [amount, setAmount] = useState('1000000')
  const [busy, setBusy] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [result, setResult] = useState<GoldMineData | null>(null)
  const [error, setError] = useState('')

  const go = async (scope: 'selected' | 'world', write: boolean) => {
    if (busy) return
    setBusy(true)
    setError('')
    setResult(null)
    setSeconds(0)
    const started = Date.now()
    const timer = window.setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 250)
    try {
      const res = await api.goldMines(scope, write ? amount : undefined)
      setResult(res?.data ?? null)
      setError(res?.success ? '' : (res?.error ?? t('操作未完成')))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      window.clearInterval(timer)
      setBusy(false)
    }
  }

  type MineRow = GoldMineData['rows'][number]
  const max = Math.max(1, ...(result?.rows ?? []).flatMap(r => [r.before, r.after]))

  return (
    <Section title={t('金矿剩余金币')}>
      <Hint>{t('设置的是每座金矿剩余可采的金币。全图操作包含其他玩家和中立金矿；非金矿、已移除的矿点会跳过。支持普通、缠绕和闹鬼金矿，数值范围 0–100000000，设为 0 会耗尽金矿。')}</Hint>
      <Row>
        <TextField label={t('每座金矿的目标剩余金币')} value={amount} onChange={e => setAmount(e.target.value)} inputMode="numeric" disabled={busy} className={s.mineField} />
        <Button disabled={!connected || busy} onClick={() => void go('selected', false)}>{t('读取选中金矿')}</Button>
        <Button disabled={!connected || busy} onClick={() => void go('selected', true)}>{t('修改选中金矿')}</Button>
        <Button disabled={!connected || busy} onClick={() => void go('world', false)}>{t('读取全图金矿')}</Button>
        <Button disabled={!connected || busy} onClick={() => void go('world', true)}>{t('批量修改全图金矿')}</Button>
      </Row>
      {busy && <Status tone="busy">{`${t('正在处理金矿…')} ${seconds} s`}</Status>}
      {!busy && result && (
        <Status>
          {`${t('金矿数量：')}${result.count}`}
          {result.action ? `　${t('已修改：')}${result.changed}　${t('已符合目标：')}${result.unchanged}　${t('跳过或失败：')}${result.failed}` : ''}
          {`　${result.scope === 'world' ? t('全图金矿') : t('当前选中金矿')}`}
        </Status>
      )}
      {error && <Status tone="error">{t(error)}</Status>}
      {result && (
        <DataTable<MineRow>
          className={s.mineTable}
          label={t('金矿剩余金币')}
          rows={result.rows}
          rowKey={r => r.handle}
          maxHeight={300}
          empty={t('当前范围未读取到金矿。')}
          columns={[
            { key: 'rawcode', label: t('金矿代码'), width: '76px', mono: true },
            { key: 'kind', label: t('金矿类型'), width: '92px', render: r => t(r.kind) },
            { key: 'owner', label: t('玩家槽位'), width: '70px' },
            { key: 'pos', label: t('坐标'), width: '130px', mono: true, render: r => `${r.x.toFixed(1)}, ${r.y.toFixed(1)}` },
            { key: 'before', label: t('读取时金币'), width: '96px', align: 'right' },
            { key: 'after', label: t('操作后金币'), width: 'minmax(150px, 1fr)', render: r => (
              <span className={s.remaining}>
                <span className={s.remainingBar}><i style={{ width: `${(Math.max(0, r.after < 0 ? r.before : r.after) / max) * 100}%` }} /></span>
                <span>{r.after < 0 ? t('待确认') : r.after}</span>
              </span>
            ) },
            { key: 'status', label: t('结果'), width: 'minmax(110px, 1fr)', render: r => `${t(r.status)}${r.error ? ` (${r.error})` : ''}` },
          ]}
        />
      )}
    </Section>
  )
}
