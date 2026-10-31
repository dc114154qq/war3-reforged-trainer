import { useEffect, useRef, useState } from 'react'
import { Button, HoldToConfirm, PillGroup, Select, TextField, Tooltip } from '../../../ds'
import { api } from '../../../lib/api'
import type { BagItemRow, EquipmentItemRow, ExtensionsSnapshot, TalentRow } from '../../../lib/types'
import { useCatalogNameMap } from '../../state/catalog'
import { useCommandCard } from '../../state/commands'
import { useSystem } from '../../state/system'
import { fill, useT } from '../../i18n'
import { DataTable } from '../common/DataTable'
import { DefinitionDialog } from '../common/DefinitionDialog'
import { Hint, PageBody, Row, Section, Status, usePending } from '../common/Layout'
import s from './ExtensionsPage.module.css'

const EMPTY: ExtensionsSnapshot = {
  status: '尚未读取 3.0 扩展状态', bag: [], equipment: [], talents: [], officialBackpacks: [], currentBackpackChoice: '', loadoutName: '套装1',
}

type Result = { success: boolean; data?: ExtensionsSnapshot; message?: string; error?: string } | undefined

export default function ExtensionsPage() {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const { pending, run } = usePending()
  const [snap, setSnap] = useState<ExtensionsSnapshot>(EMPTY)
  const [bagId, setBagId] = useState('')
  const [equipId, setEquipId] = useState('')
  const [talentId, setTalentId] = useState('')
  const [talentChoice, setTalentChoice] = useState('')
  const [rawcode, setRawcode] = useState('')
  const [charges, setCharges] = useState('1')
  const [backpack, setBackpack] = useState('')
  const [loadoutName, setLoadoutName] = useState('套装1')
  const [savedLoadout, setSavedLoadout] = useState('')
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null)
  const [elapsed, setElapsed] = useState(0)
  const [definitions, setDefinitions] = useState(false)
  const clearTimer = useRef<number | undefined>(undefined)

  const talent = snap.talents.find(r => r._iid === talentId)
  const choices = talent?.choiceCodes ?? []
  const names = useCatalogNameMap('item', [...snap.bag, ...snap.equipment].map(r => r.rawcode).filter(Boolean))
  const equipBusy = Object.entries(pending).some(([k, v]) => v && k.startsWith('equip-'))
  const talentBusy = Object.entries(pending).some(([k, v]) => v && k.startsWith('talent-'))

  /** Keep the talent selection and choice valid against a fresh snapshot, as 2.1.22 did. */
  const accept = (next: ExtensionsSnapshot) => {
    setSnap(next)
    const tier = next.talents.some(r => r._iid === talentId) ? talentId : next.selectedTalentIid || next.talents[0]?._iid || ''
    setTalentId(tier)
    const options = next.talents.find(r => r._iid === tier)?.choiceCodes ?? []
    setTalentChoice(c => (options.includes(c) ? c : options[0] ?? ''))
    setBackpack(b => b || next.currentBackpackChoice || next.officialBackpacks[0] || '')
  }

  const say = (text: string, error = false) => {
    window.clearTimeout(clearTimer.current)
    setMessage({ text, error })
    if (!error) clearTimer.current = window.setTimeout(() => setMessage(null), 5000)
  }
  useEffect(() => () => window.clearTimeout(clearTimer.current), [])

  const load = () => run('load', async () => accept(await api.refreshExtensionStatus()))
  useEffect(() => { void load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * Run an extension action and take the snapshot it returns. api.ts throws on success: false
   * (and shows the reason as a notice), so a failure only has to replace the progress line.
   */
  const perform = async (call: () => Promise<Result>, done: string) => {
    try {
      const result = await call()
      if (result?.data) accept(result.data)
      say(result?.message || done)
    } catch (err) {
      say(err instanceof Error ? err.message : String(err), true)
      throw err
    }
  }

  const bag = (action: string, params: Record<string, unknown> = {}) => run(`bag-${action}`, () =>
    perform(() => api.extensionBagAction(action, { row_iid: bagId, ...params }), `${t('背包操作完成')}：${t(BAG_ACTIONS[action] ?? action)}`))

  const equip = (action: string, params: Record<string, unknown> = {}) => run(`equip-${action}`, async () => {
    setElapsed(0)
    const started = Date.now()
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000)
    say(action.includes('restore') ? t('正在恢复套装并按部位装备，请稍候…') : t('正在处理装备，请稍候…'))
    try {
      await perform(() => api.extensionEquipmentAction(action, { row_iid: equipId, bag_row_iid: bagId, ...params }), `${t('装备操作完成')}：${t(EQUIP_ACTIONS[action] ?? action)}`)
    } finally {
      window.clearInterval(timer)
    }
  })

  const talentAction = (action: string, params: Record<string, unknown> = {}) => run(`talent-${action}`, () =>
    perform(() => api.extensionTalentAction(action, { row_iid: talentId, ...params }), `${t('天赋操作完成')}：${t(TALENT_ACTIONS[action] ?? action)}`))

  const selectTalent = (row: TalentRow) => {
    if (talentBusy) return
    setTalentId(row._iid)
    const options = row.choiceCodes ?? []
    setTalentChoice(c => (options.includes(c) ? c : options[0] ?? ''))
  }

  /** Restore uses the picked saved plan, or the typed name when it names a saved plan. */
  const restoreName = () => savedLoadout || ((snap.loadoutNames ?? []).includes(loadoutName) ? loadoutName : '')

  useCommandCard([
    { key: 'Q', icon: 'refresh', title: t('读取扩展状态'), description: t('重新读取选中英雄的扩展背包、装备栏和天赋树。'), pending: pending.load, estimateMs: 900, disabled: !connected, onPress: () => void load() },
    { key: 'W', icon: 'add-item', title: t('添加物品'), description: t('把填写的物品 ID 和数量放进扩展背包。'), pending: pending['bag-add_item'], estimateMs: 700, disabled: !connected || !rawcode.trim(),
      onPress: () => void bag('add_item', { rawcode: rawcode.trim(), charges }) },
    { key: 'E', icon: 'copy', title: t('复制物品'), description: t('在背包里复制一件选中的物品。'), pending: pending['bag-duplicate'], estimateMs: 700, disabled: !connected || !bagId, onPress: () => void bag('duplicate') },
    { key: 'R', icon: 'write', title: t('改数量'), description: t('把选中背包物品的数量改成填写的数量。'), pending: pending['bag-set_charges'], estimateMs: 600, disabled: !connected || !bagId, onPress: () => void bag('set_charges', { charges }) },
    { key: 'A', icon: 'equipment', title: t('放入所选装备槽'), description: t('把选中的背包物品装进选中的装备槽。'), pending: pending['equip-equip_bag_to_slot'], estimateMs: 2500, disabled: !connected || equipBusy, onPress: () => void equip('equip_bag_to_slot') },
    { key: 'S', icon: 'cancel', title: t('卸下所选'), description: t('卸下选中装备槽里的装备，效果一并撤销。'), pending: pending['equip-unequip'], estimateMs: 2000, disabled: !connected || equipBusy, onPress: () => void equip('unequip') },
    { key: 'D', icon: 'save', title: t('保存套装'), description: t('把当前九个部位的装备存成一套方案。'), pending: pending['equip-save_loadout'], estimateMs: 1500, disabled: !connected || equipBusy, onPress: () => void equip('save_loadout', { name: loadoutName }) },
    { key: 'F', icon: 'open-file', title: t('恢复套装'), description: t('按保存的方案把装备逐个部位装回去。'), pending: pending['equip-restore_loadout'], estimateMs: 6000, disabled: !connected || equipBusy, onPress: () => void equip('restore_loadout', { name: restoreName() }) },
    { key: 'Z', icon: 'level-up', title: t('+1 天赋点'), description: t('给选中英雄加一个天赋点。'), pending: pending['talent-grant_point'], estimateMs: 600, disabled: !connected || talentBusy, onPress: () => void talentAction('grant_point') },
    { key: 'X', icon: 'hero-skill', title: t('添加所选天赋'), description: t('把下方选中天赋层里选好的天赋加给英雄。'), pending: pending['talent-add_choice'], estimateMs: 700, disabled: !connected || talentBusy || !choices.includes(talentChoice),
      onPress: () => void talentAction('add_choice', { choice: talentChoice }) },
    { key: 'C', icon: 'map-data', title: t('补齐背包定义'), description: t('为战役或地图生成补齐 3.0 背包定义的新副本。'), onPress: () => setDefinitions(true) },
  ])

  const bagRow = snap.bag.find(r => r._iid === bagId)
  const equipRow = snap.equipment.find(r => r._iid === equipId)

  return (
    <PageBody>
      <header className={s.status}>
        <span className={s.statusText}>{t(snap.status)}</span>
        <Button size="sm" icon="map-data" onClick={() => setDefinitions(true)}>{t('补齐背包定义…')}</Button>
        <Button size="sm" icon="refresh" disabled={!connected || pending.load} onClick={() => void load()}>{t('读取扩展状态')}</Button>
      </header>
      <Hint>{t('添加背包时提示“背包装备未定义”，先用“补齐背包定义”为战役或地图生成新副本。')}</Hint>
      {message && <Status tone={message.error ? 'error' : 'info'}>{message.text}</Status>}

      <div className={s.upper}>
        <Section title={`${t('扩展背包')}（${snap.bag.filter(r => r.rawcode).length}/${snap.bag.length}）`} className={s.block}>
          {snap.bag.length === 0 ? <p className={s.empty}>{t('背包为空，或者还没有读到 3.0 扩展背包。')}</p> : (
            <div className={s.bag} role="listbox" aria-label={t('扩展背包')}>
              {snap.bag.map(r => <ItemSocket key={r._iid} row={r} name={names[r.rawcode]} selected={r._iid === bagId} onSelect={() => setBagId(r._iid)} label={fill(t('第 {n} 格'), { n: r.slot })} />)}
            </div>
          )}
          {snap.bag.length > 0 && <p className={s.picked}>{bagRow ? describe(t, fill(t('第 {n} 格'), { n: bagRow.slot }), bagRow, names[bagRow.rawcode]) : t('点一格选中背包物品。')}</p>}
          <Row className={s.controls}>
            <TextField className={s.code} label={t('物品 ID')} maxLength={4} spellCheck={false} value={rawcode} onChange={e => setRawcode(e.target.value)} />
            <TextField className={s.count} label={t('数量')} inputMode="numeric" value={charges} onChange={e => setCharges(e.target.value)} />
            <Button disabled={!connected || !rawcode.trim()} onClick={() => void bag('add_item', { rawcode: rawcode.trim(), charges })}>{t('添加物品')}</Button>
            <Button disabled={!connected || !bagId} onClick={() => void bag('set_charges', { charges })}>{t('改数量')}</Button>
            <Button disabled={!connected || !bagId} onClick={() => void bag('duplicate')}>{t('复制')}</Button>
            <HoldToConfirm icon="remove" disabled={!connected || !bagId} onConfirm={() => void bag('destroy')}>{t('按住销毁')}</HoldToConfirm>
          </Row>
          <Row className={s.controls}>
            <Select
              className={s.backpack}
              label={t('官方背包装备')}
              value={backpack}
              onChange={e => setBackpack(e.target.value)}
              options={snap.officialBackpacks.map(b => ({ value: b, label: b }))}
              disabled={!snap.officialBackpacks.length}
            />
            <Button disabled={!connected || !backpack} onClick={() => void bag('add_official_backpack', { choice: backpack })}>{t('添加官方背包装备')}</Button>
            <Button disabled={!connected || !bagId} onClick={() => void bag('repair_item')}>{t('修复状态')}</Button>
          </Row>
        </Section>

        <Section title={`${t('装备栏')}（${snap.equipment.filter(r => r.rawcode).length}/${snap.equipment.length || 9}）`} className={s.block}>
          {snap.equipment.length === 0 ? <p className={s.empty}>{t('当前单位没有穿戴装备，或者还没有读取。')}</p> : (
            <div className={s.doll} role="listbox" aria-label={t('装备栏')}>
              {snap.equipment.map(r => <ItemSocket key={r._iid} row={r} name={names[r.rawcode]} selected={r._iid === equipId} onSelect={() => setEquipId(r._iid)} label={t(r.slot)} slotName={t(r.slot)} />)}
            </div>
          )}
          {snap.equipment.length > 0 && <p className={s.picked}>{equipRow ? describe(t, t(equipRow.slot), equipRow, names[equipRow.rawcode]) : t('点一个部位选中装备槽。')}</p>}
          <fieldset className={s.fieldset} disabled={equipBusy}>
            <Row className={s.controls}>
              <Button disabled={!connected} onClick={() => void equip('equip_bag_to_slot')}>{t('放入所选装备槽')}</Button>
              <Button disabled={!connected} onClick={() => void equip('unequip')}>{t('卸下所选')}</Button>
              <Button disabled={!connected} onClick={() => void equip('audit')}>{t('审计装备')}</Button>
              <Button disabled={!connected} onClick={() => void equip('repair_misplaced')}>{t('修复错槽')}</Button>
              <Button disabled={!connected} onClick={() => void equip('enable_any_slot')}>{t('开启任意槽')}</Button>
              <HoldToConfirm icon="remove" disabled={!connected || equipBusy || !equipId} onConfirm={() => void equip('destroy')}>{t('按住销毁')}</HoldToConfirm>
            </Row>
            <Row className={s.controls}>
              <Select
                className={s.loadout}
                label={t('已保存方案')}
                value={savedLoadout}
                onChange={e => { setSavedLoadout(e.target.value); if (e.target.value) setLoadoutName(e.target.value) }}
                options={[{ value: '', label: t('自动匹配已保存方案') }, ...(snap.loadoutNames ?? []).map(n => ({ value: n, label: n }))]}
              />
              <TextField className={s.loadoutName} label={t('套装名称')} value={loadoutName} onChange={e => setLoadoutName(e.target.value)} />
              <Button variant="cast" disabled={!connected} onClick={() => void equip('save_loadout', { name: loadoutName })}>{t('保存套装')}</Button>
              <Button disabled={!connected} onClick={() => void equip('restore_loadout', { name: restoreName() })}>{t('恢复套装')}</Button>
            </Row>
            <Row className={s.controls}>
              <Button size="sm" disabled={!connected} onClick={() => void equip('save_all_loadouts', { name: loadoutName })}>{t('一键保存全英雄')}</Button>
              <Button size="sm" disabled={!connected} onClick={() => void equip('restore_all_loadouts', { name: restoreName() })}>{t('一键恢复全英雄')}</Button>
              <Button size="sm" icon="export" onClick={() => void equip('export_loadouts')}>{t('导出方案')}</Button>
              <Button size="sm" icon="open-file" onClick={() => void equip('import_loadouts')}>{t('导入方案')}</Button>
            </Row>
          </fieldset>
          {equipBusy && <Status tone="busy">{fill(t('正在处理装备，已用时 {n} 秒；完成后会核对九个部位。'), { n: elapsed })}</Status>}
        </Section>
      </div>

      <Section
        title={fill(t('天赋树（{n} 层）'), { n: snap.talents.length })}
        actions={<>
          <Button size="sm" disabled={!connected || talentBusy} onClick={() => void talentAction('grant_point')}>{t('+1 天赋点')}</Button>
          <HoldToConfirm size="sm" icon="reset-cooldown" disabled={!connected || talentBusy} onConfirm={() => void talentAction('reset_talents')}>{t('按住重置天赋')}</HoldToConfirm>
        </>}
      >
        <DataTable<TalentRow>
          label={t('天赋树')}
          rows={snap.talents}
          rowKey={r => r._iid}
          selected={talentId}
          onSelect={selectTalent}
          empty={t('没有检测到英雄天赋树。')}
          maxHeight={260}
          columns={[
            { key: 'hero', label: t('天赋树归属'), width: '140px', render: r => <strong>{r.hero}</strong> },
            { key: 'tier', label: t('层级'), width: '60px', render: r => `T${r.tier}` },
            { key: 'choices', label: t('候选天赋'), mono: true },
            { key: 'selected', label: t('已选择'), width: '240px', render: r => r.selected || t('（未点）') },
          ]}
        />
        <Row className={s.talentPick}>
          <span className={s.tierLabel}>{talent ? `${talent.hero}　T${talent.tier}` : t('先读取扩展状态，再在上面选一层天赋。')}</span>
          {choices.length > 0 && (
            <PillGroup<string> label={t('选择天赋')} value={talentChoice} onChange={setTalentChoice} options={choices.map(c => ({ value: c, label: c }))} />
          )}
          <Button variant="cast" disabled={!connected || talentBusy || !choices.includes(talentChoice)} onClick={() => void talentAction('add_choice', { choice: talentChoice })}>{t('添加所选天赋')}</Button>
        </Row>
      </Section>

      <DefinitionDialog open={definitions} onOpenChange={setDefinitions} />
    </PageBody>
  )
}

const BAG_ACTIONS: Record<string, string> = {
  add_item: '添加物品', set_charges: '改数量', duplicate: '复制', destroy: '销毁', repair_item: '修复状态', add_official_backpack: '添加官方背包装备',
}
const EQUIP_ACTIONS: Record<string, string> = {
  equip_bag_to_slot: '放入所选装备槽', unequip: '卸下所选', audit: '审计装备', repair_misplaced: '修复错槽', enable_any_slot: '开启任意槽', destroy: '销毁',
  save_loadout: '保存套装', restore_loadout: '恢复套装', save_all_loadouts: '一键保存全英雄', restore_all_loadouts: '一键恢复全英雄',
  export_loadouts: '导出方案', import_loadouts: '导入方案',
}
const TALENT_ACTIONS: Record<string, string> = { grant_point: '+1 天赋点', reset_talents: '重置天赋', add_choice: '添加所选天赋' }

function describe(t: (s: string) => string, where: string, row: BagItemRow | EquipmentItemRow, name: string | undefined) {
  if (!row.rawcode) return `${where}：${t('空')}`
  const type = 'type' in row && row.type ? `　${t(row.type)}` : ''
  return `${where}：${name ?? row.rawcode}（${row.rawcode}）×${row.charges}${type}　${row.handle}`
}

/** One inventory cell: rawcode in the socket, charges in the corner as in the game. */
function ItemSocket({ row, name, selected, onSelect, label, slotName }: {
  row: BagItemRow | EquipmentItemRow
  name: string | undefined
  selected: boolean
  onSelect(): void
  label: string
  slotName?: string
}) {
  const t = useT()
  const empty = !row.rawcode
  const cell = (
    <button
      type="button"
      role="option"
      aria-selected={selected}
      aria-label={empty ? `${label}（${t('空')}）` : `${label}：${name ?? row.rawcode}`}
      className={s.socket}
      data-empty={empty || undefined}
      onClick={onSelect}
    >
      {slotName && <span className={s.slotName}>{slotName}</span>}
      {!empty && <span className={s.socketCode}>{row.rawcode}</span>}
      {!empty && Number(row.charges) > 0 && <span className={s.charges}>{row.charges}</span>}
    </button>
  )
  if (empty) return cell
  return (
    <Tooltip title={name ?? row.rawcode} body={<span className={s.tip}>{row.rawcode}　×{row.charges}{'type' in row && row.type ? `　${t(row.type)}` : ''}<br />{row.handle}</span>}>
      {cell}
    </Tooltip>
  )
}
