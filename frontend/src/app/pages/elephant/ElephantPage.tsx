import { useEffect, useState, type ReactNode } from 'react'
import { HoldToConfirm, Icon, TextField, announce, cx, type IconName } from '../../../ds'
import { api } from '../../../lib/api'
import { useCatalogName } from '../../state/catalog'
import { useCommandCard } from '../../state/commands'
import { useParams } from '../../state/params'
import { useSystem } from '../../state/system'
import { fill, useT } from '../../i18n'
import { PageBody, usePending } from '../common/Layout'
import s from './ElephantPage.module.css'

/** Values shown until the backend reports its own (2.1.22 defaults). */
const DEFAULTS: Record<string, string> = {
  hero_level: '1', unit_scale: '1.0', unit_rawcode: '', item_rawcode: 'ckng', ability_rawcode: 'AOsh', ability_level: '1',
  tech_rawcode: '', tech_level: '1', xp_rate: '1.0',
}

type Run = (action: string, label: string, params?: Record<string, unknown>) => void

export default function ElephantPage() {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const values = useParams(st => st.values)
  const { pending, run } = usePending()
  const p = (key: string) => values[key] ?? DEFAULTS[key]

  useEffect(() => { void useParams.getState().reload() }, [])

  // A failed action is reported by api.ts (notice dialog or the yellow line), so only
  // success needs saying here. The result carries the parameters the action changed.
  const act: Run = (action, label, params = {}) => void run(action, async () => {
    const result = await api.executeElephantAction(action, params)
    if (result?.success) announce(fill(t('{action}：已完成'), { action: t(label) }))
  })

  /** prewarm_elephant is its own bridge method, not one of the Elephant actions. */
  const prewarm = () => void run('prewarm', async () => {
    const result = await api.prewarmElephant()
    if (result?.success) announce(t(result.message || '大象功能初始化就绪'))
  })

  const tile = (action: string, label: string, icon: IconName, params?: Record<string, unknown>) => (
    <Tile key={`${action}-${label}`} icon={icon} label={t(label)} pending={!!pending[action]} disabled={!connected} onPress={() => act(action, label, params)} />
  )

  useCommandCard([
    { key: 'Q', icon: 'reveal-map', title: t('全开视野'), description: t('去掉地图迷雾和黑色遮罩。'), pending: pending.reveal_map, disabled: !connected, onPress: () => act('reveal_map', '全开视野') },
    { key: 'W', icon: 'invulnerable', title: t('无敌'), description: t('选中单位不再受到伤害。'), pending: pending.invulnerable, disabled: !connected, onPress: () => act('invulnerable', '无敌') },
    { key: 'E', icon: 'reset-cooldown', title: t('重置技能冷却'), description: t('立刻重置选中单位所有技能的冷却。'), pending: pending.reset_cooldown, disabled: !connected, onPress: () => act('reset_cooldown', '重置技能冷却') },
    { key: 'R', icon: 'take-control', title: t('获取控制权'), description: t('把选中的目标单位变成你的。'), pending: pending.take_control, disabled: !connected, onPress: () => act('take_control', '获取控制权') },
    { key: 'A', icon: 'level-up', title: t('设置英雄等级'), description: t('把选中英雄的等级改成填写的等级。'), pending: pending.hero_level_set, disabled: !connected, onPress: () => act('hero_level_set', '设置英雄等级', { level: p('hero_level') }) },
    { key: 'S', icon: 'add-item', title: t('添加物品'), description: t('给选中单位添加填写的物品。'), pending: pending.add_item, disabled: !connected, onPress: () => act('add_item', '添加物品', { rawcode: p('item_rawcode') }) },
    { key: 'D', icon: 'add-ability', title: t('添加技能'), description: t('给选中单位添加填写的技能和等级。'), pending: pending.add_ability, disabled: !connected, onPress: () => act('add_ability', '添加技能', { rawcode: p('ability_rawcode'), level: p('ability_level') }) },
    { key: 'F', icon: 'summon', title: t('生成单位'), description: t('在选中单位旁生成填写的单位。'), pending: pending.create_unit, disabled: !connected, onPress: () => act('create_unit', '生成单位', { rawcode: p('unit_rawcode'), to_self: false }) },
    { key: 'Z', icon: 'pause', title: t('暂停游戏'), description: t('暂停整局游戏。'), pending: pending.pause_game, disabled: !connected, onPress: () => act('pause_game', '暂停游戏') },
    { key: 'X', icon: 'resume', title: t('恢复游戏'), description: t('让暂停的游戏继续。'), pending: pending.resume_game, disabled: !connected, onPress: () => act('resume_game', '恢复游戏') },
    { key: 'C', icon: 'settings', title: t('初始化大象功能'), description: t('提前准备大象功能，第一次使用时更快响应。'), pending: pending.prewarm, estimateMs: 1500, disabled: !connected, onPress: prewarm },
  ])

  return (
    <PageBody>
      <div className={s.top}>
        <p className={s.lead}>{t('这些功能作用于游戏里当前选中的单位或整局游戏。输入框里的数值会记住，全局快捷键也用同一组数值。')}</p>
        <button type="button" className={s.prewarm} disabled={!connected || pending.prewarm} onClick={prewarm}>
          <Icon name="settings" />{t('初始化大象功能')}
        </button>
      </div>

      <div className={s.groups}>
        <Group title={t('地图与战局')}>
          <div className={s.tiles}>
            {tile('reveal_map', '全开视野', 'reveal-map')}
            {tile('hide_map', '恢复迷雾', 'hide-map')}
            {tile('pause_game', '暂停游戏', 'pause')}
            {tile('resume_game', '恢复游戏', 'resume')}
            {tile('peace_on', '开启和平模式', 'peace')}
            {tile('peace_off', '关闭和平模式', 'peace')}
          </div>
          <div className={s.danger}>
            <HoldToConfirm icon="end-game" size="sm" disabled={!connected} onConfirm={() => act('end_game', '结束当前游戏')}>{t('按住结束当前游戏')}</HoldToConfirm>
          </div>
        </Group>

        <Group title={t('英雄与单位状态')}>
          <div className={s.params}>
            <Param name="hero_level" label={t('英雄等级')} value={p('hero_level')} narrow />
            <Tile compact icon="read" label={t('读取')} pending={!!pending.hero_level_read} disabled={!connected} onPress={() => act('hero_level_read', '读取英雄等级')} />
            <Tile compact icon="level-up" label={t('设置')} pending={!!pending.hero_level_set} disabled={!connected} onPress={() => act('hero_level_set', '设置英雄等级', { level: p('hero_level') })} />
            <Param name="unit_scale" label={t('模型缩放')} value={p('unit_scale')} narrow />
            <Tile compact icon="scale" label={t('设置缩放')} pending={!!pending.set_scale} disabled={!connected} onPress={() => act('set_scale', '设置缩放', { scale: p('unit_scale') })} />
          </div>
          <div className={s.tiles}>
            {tile('invulnerable', '无敌', 'invulnerable')}
            {tile('vulnerable', '取消无敌', 'invulnerable')}
            {tile('collision_off', '关闭碰撞体积', 'collision-off')}
            {tile('collision_on', '开启碰撞体积', 'collision-off')}
            {tile('pause_unit', '暂停单位', 'pause')}
            {tile('resume_unit', '恢复单位', 'resume')}
            {tile('reset_cooldown', '重置技能冷却', 'reset-cooldown')}
          </div>
        </Group>

        <Group title={t('目标单位与阵营')}>
          <div className={s.tiles}>
            {tile('take_control', '获取控制权', 'take-control')}
            {tile('kill_unit', '秒杀目标', 'kill')}
            {tile('explode_unit', '瞬间爆炸', 'explode')}
            {tile('remove_unit', '删除单位', 'remove')}
          </div>
          <div className={s.danger}>
            <HoldToConfirm icon="kill" size="sm" disabled={!connected} onConfirm={() => act('kill_owner_units', '秒杀该玩家全部单位')}>{t('按住秒杀该玩家全部单位')}</HoldToConfirm>
          </div>
        </Group>

        <Group title={t('召唤与物品')}>
          <div className={s.params}>
            <Param name="unit_rawcode" label={t('单位 ID')} value={p('unit_rawcode')} kind="unit" placeholder="hfoo" />
            <Tile compact icon="summon" label={t('生成单位')} pending={!!pending.create_unit} disabled={!connected} onPress={() => act('create_unit', '生成单位', { rawcode: p('unit_rawcode'), to_self: false })} />
            <Tile compact icon="take-control" label={t('复制给自己')} pending={!!pending.create_unit} disabled={!connected} onPress={() => act('create_unit', '复制选中单位归属给自己', { rawcode: p('unit_rawcode'), to_self: true })} />
          </div>
          <div className={s.params}>
            <Param name="item_rawcode" label={t('物品 ID')} value={p('item_rawcode')} kind="item" placeholder="ckng" />
            <Tile compact icon="add-item" label={t('添加物品')} pending={!!pending.add_item} disabled={!connected} onPress={() => act('add_item', '添加物品', { rawcode: p('item_rawcode') })} />
          </div>
          <div className={s.danger}>
            <HoldToConfirm icon="remove" size="sm" disabled={!connected} onConfirm={() => act('clear_inventory', '清空物品栏')}>{t('按住清空物品栏')}</HoldToConfirm>
          </div>
        </Group>

        <Group title={t('技能')}>
          <div className={s.params}>
            <Param name="ability_rawcode" label={t('技能 ID')} value={p('ability_rawcode')} kind="ability" placeholder="AOsh" />
            <Param name="ability_level" label={t('等级')} value={p('ability_level')} narrow />
          </div>
          <div className={s.tiles}>
            {tile('add_ability', '添加技能', 'add-ability', { rawcode: p('ability_rawcode'), level: p('ability_level') })}
            {tile('remove_ability', '删除技能', 'remove', { rawcode: p('ability_rawcode') })}
            {tile('set_ability_level', '设定技能等级', 'level-up', { rawcode: p('ability_rawcode'), level: p('ability_level') })}
          </div>
        </Group>

        <Group title={t('科技与经验')}>
          <div className={s.params}>
            <Param name="tech_rawcode" label={t('科技 ID')} value={p('tech_rawcode')} kind="upgrade" placeholder="Rhme" />
            <Param name="tech_level" label={t('等级')} value={p('tech_level')} narrow />
            <Tile compact icon="tech" label={t('设定科技等级')} pending={!!pending.set_tech} disabled={!connected} onPress={() => act('set_tech', '设定玩家科技等级', { rawcode: p('tech_rawcode'), level: p('tech_level') })} />
          </div>
          <div className={s.params}>
            <Param name="xp_rate" label={t('经验倍率')} value={p('xp_rate')} narrow />
            <Tile compact icon="xp-rate" label={t('设定经验倍率')} pending={!!pending.set_xp_rate} disabled={!connected} onPress={() => act('set_xp_rate', '设定经验倍率', { rate: p('xp_rate') })} />
          </div>
        </Group>
      </div>
    </PageBody>
  )
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={s.group} aria-label={title}>
      <h2 className={s.groupTitle}>{title}</h2>
      {children}
    </section>
  )
}

/** A command button in the shape of the game's: icon on an iron plate, name underneath. */
function Tile({ icon, label, onPress, pending, disabled, compact }: {
  icon: IconName
  label: string
  onPress(): void
  pending?: boolean
  disabled?: boolean
  compact?: boolean
}) {
  return (
    <button
      type="button"
      className={cx(s.tile, compact && s.compact)}
      data-pending={pending || undefined}
      aria-busy={pending || undefined}
      disabled={disabled}
      onClick={() => { if (!pending) onPress() }}
    >
      <span className={s.tileIcon}><Icon name={icon} /></span>
      <span className={s.tileLabel}>{label}</span>
    </button>
  )
}

/**
 * A remembered parameter: edits are sent to the backend on Enter or when the field loses
 * focus, so global hotkeys use the same value. Rawcodes show their catalogue name.
 */
function Param({ name, label, value, kind, placeholder, narrow }: {
  name: string
  label: string
  value: string
  kind?: 'unit' | 'item' | 'ability' | 'upgrade'
  placeholder?: string
  narrow?: boolean
}) {
  const [draft, setDraft] = useState(value)
  useEffect(() => setDraft(value), [value])
  const known = useCatalogName(kind ?? 'unit', kind ? draft.trim() : null)

  const commit = async () => {
    const next = draft.trim()
    if (next === value) return
    useParams.getState().merge({ [name]: next })
    try {
      const result = await api.setElephantParameter(name, next)
      if (result?.success) useParams.getState().merge(result.changedParameters)
    } catch {
      // reported by callApi
    }
  }

  return (
    <span className={s.param}>
      <TextField
        className={cx(narrow ? s.narrow : s.code)}
        label={label}
        value={draft}
        placeholder={placeholder}
        spellCheck={false}
        maxLength={kind ? 4 : undefined}
        onChange={e => setDraft(e.target.value)}
        onBlur={() => void commit()}
        onKeyDown={e => { if (e.key === 'Enter') void commit() }}
      />
      {kind && <span className={s.known}>{known ?? ''}</span>}
    </span>
  )
}
