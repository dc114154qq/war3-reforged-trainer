// A fake window.pywebview for developing and screenshotting the app without the game.
// Loaded only when the page is opened with ?mock and no real bridge exists (see main.tsx);
// it ships as a separate chunk that the desktop app never requests.
// Data shapes follow src/lib/types.ts; values are illustrative.
import type {
  AbilityFieldRow, BagItemRow, CandidateUnit, EquipmentItemRow, ExtensionsSnapshot, GoldMineData, HotkeyItem, ItemFieldRow, LockItem, ResourceGroup,
  ResourceSnapshot, SelectedUnitData, SystemStatus, TalentRow, UnitFieldRow,
} from '../../lib/types'
import type { DefinitionProgress, MapCatalogChange, MapCatalogProgress, MapCatalogRow, MapScriptOptions, MapScriptProgress } from '../../lib/api'

const params = new URLSearchParams(location.search)
/** ?mock=connected starts already connected. */
let connected = params.get('mock') === 'connected'
let hotkeysOn = true
/** ?lang=en starts in English. */
let language: 'zh' | 'en' = params.get('lang') === 'en' ? 'en' : 'zh'
const wait = (ms: number) => new Promise(r => setTimeout(r, ms))
const hex = (n: number) => `0x${n.toString(16).toUpperCase()}`

/* ---- System ---------------------------------------------------------------------- */

const status = (): SystemStatus => ({
  appVersion: '2.2.0',
  edition: '普通读取版',
  connected,
  pid: connected ? 14328 : null,
  gameVersion: connected ? '3.0.1.24371' : null,
  adapterProfile: connected ? 'reforged-3.0.1.24371' : null,
  bridgeProfile: 3,
  hotkeysEnabled: hotkeysOn,
  statusMessage: connected ? '已连接 Warcraft III 3.0.1.24371，已读取选中单位' : '没有找到 Warcraft III 正式服或测试服的可见窗口',
  language,
})

/* ---- Resources and locks --------------------------------------------------------- */

// Row shapes follow war3_application.resource_row_values: "<n> (Player <id>)" for the game's
// own player state, "<n> (h<header>/p<player>)" for groups found in memory; iids are the
// backend's resource_iid. Values are strings, as VirtualTree rows carry them.
interface MockGroup { iid: string; label: string; gold: number; lumber: number; used: number; cap: number; addr?: [number, number]; source: string }
const groupData: MockGroup[] = [
  { iid: 'native-player:0', label: '1 (Player 0)', gold: 18500, lumber: 9200, used: 42, cap: 100, source: 'persistent native player state' },
  { iid: '24a10280:24a10298', label: '2 (h5/p1)', gold: 6400, lumber: 3100, used: 36, cap: 100, addr: [0x24a10280, 0x24a10298], source: 'player resource scan' },
  { iid: '24a10880:24a10898', label: '3 (h5/p4)', gold: 2210, lumber: 940, used: 58, cap: 80, addr: [0x24a10880, 0x24a10898], source: 'heuristic resource scan' },
]
let selectedGroup = groupData[0].iid
let delta = '10000'
const locks = new Map<string, LockItem>()
const cur = () => groupData.find(g => g.iid === selectedGroup) ?? groupData[0]
const groups = (): ResourceGroup[] => groupData.map(g => ({
  _iid: g.iid, group: g.label, gold: String(g.gold), lumber: String(g.lumber), food: `${g.used}/${g.cap}`,
  gold_address: g.addr ? `0x${g.addr[0].toString(16)}` : '—', lumber_address: g.addr ? `0x${g.addr[1].toString(16)}` : '—', source: g.source,
}) as unknown as ResourceGroup)
const snapshot = (): ResourceSnapshot => {
  const g = cur()
  return {
    current: connected ? { gold: String(g.gold), lumber: String(g.lumber), food: String(g.used), foodCap: String(g.cap) } : { gold: '', lumber: '', food: '', foodCap: '' },
    targets: { gold: String(g.gold), lumber: String(g.lumber), foodUsed: String(g.used), foodCap: String(g.cap) },
    delta,
    groups: connected ? groups() : [],
  }
}
const lockList = () => [...locks.values()]
const LOCK_LABEL: Record<string, string> = { gold: '金币', lumber: '木材', food_used: '当前人口', food_cap: '最大人口' }

const mines = (): GoldMineData['rows'] => [
  { handle: '0x100A1', rawcode: 'ngol', kind: '普通金矿', owner: 15, before: 12500, after: 12500, status: '已读取', error: 0, x: -2944, y: 1216 },
  { handle: '0x100B7', rawcode: 'ngol', kind: '普通金矿', owner: 15, before: 8300, after: 8300, status: '已读取', error: 0, x: 2112, y: -704 },
  { handle: '0x100C2', rawcode: 'egol', kind: '缠绕金矿', owner: 0, before: 4120, after: 4120, status: '已读取', error: 0, x: -1536, y: 960 },
]

/* ---- Selected unit ------------------------------------------------------------- */

const base = 0x24a8f100
const field = (iid: string, category: string, label: string, value: string, type: string, offset: number, note: string): UnitFieldRow =>
  ({ _iid: iid, category, label, value, type, address: hex(base + offset), note })
const fields: UnitFieldRow[] = [
  field('hp', '基础', '当前生命', '1250', 'f32', 0x20, '单位现在的生命值。超过生命上限的部分会被游戏截掉。'),
  field('hp_max', '基础', '生命上限', '1250', 'i32', 0x24, '生命值的最大值。'),
  field('mp', '基础', '当前魔法', '600', 'f32', 0x30, '单位现在的魔法值。'),
  field('mp_max', '基础', '魔法上限', '600', 'i32', 0x34, '魔法值的最大值。'),
  field('str', '英雄', '基础力量', '48', 'i32', 0x120, '英雄的基础力量，不含装备加成。'),
  field('agi', '英雄', '基础敏捷', '32', 'i32', 0x124, '英雄的基础敏捷，不含装备加成。'),
  field('int', '英雄', '基础智力', '42', 'i32', 0x128, '英雄的基础智力，不含装备加成。'),
  field('level', '英雄', '英雄等级', '8', 'i32', 0x130, '只改等级不会补发技能点。'),
  field('armor', '战斗', '护甲', '5', 'f32', 0xa0, '每点护甲大约减少 6% 受到的物理伤害。'),
  field('cooldown', '战斗', '攻击间隔', '2.2', 'f32', 0xa8, '两次攻击之间的秒数，越小越快。'),
  field('speed', '战斗', '移动速度', '320', 'f32', 0x190, '地面移动速度，游戏上限是 522。'),
  field('resolve', '3.0 属性', '斗志', '18.5', 'f32', 0x240, '3.0 新增的战斗韧性属性。'),
]
const pos = { x: '-1240.0', y: '860.5' }
const regen = { hp: '6.5', mp: '3.2' }
const value = (iid: string) => fields.find(f => f._iid === iid)!.value

const unit = (): SelectedUnitData => connected ? {
  hasSelection: true,
  unitTypeId: 'Hart',
  identity: '(0x100027, 0x24A8F100, 3)',
  hp: { current: value('hp'), max: value('hp_max'), regen: regen.hp, target: '', regenTarget: '' },
  mp: { current: value('mp'), max: value('mp_max'), regen: regen.mp, target: '', regenTarget: '' },
  position: { xCurrent: pos.x, yCurrent: pos.y, xTarget: '', yTarget: '' },
  fields,
} : {
  hasSelection: false, unitTypeId: '', identity: null,
  hp: { current: '', max: '', regen: '', target: '', regenTarget: '' },
  mp: { current: '', max: '', regen: '', target: '', regenTarget: '' },
  position: { xCurrent: '', yCurrent: '', xTarget: '', yTarget: '' },
  fields: [],
}

const candidateRows: CandidateUnit[] = [
  { _iid: 'c1', index: '1', confidence: '0.99', hp: '1250/1250', mp: '600/600', position: '(-1240.0, 860.5)', evidence: '12/12', components: 'hero,inventory', inventory: '6', handle: '0x100027', owner: '0', unit: 'Hart' },
  { _iid: 'c2', index: '2', confidence: '0.61', hp: '420/420', mp: '0/0', position: '(-1080.0, 720.0)', evidence: '7/12', components: 'unit', inventory: '0', handle: '0x10002B', owner: '0', unit: 'hfoo' },
]


/* ---- Catalogue ------------------------------------------------------------------- */

const CATALOG: Record<string, [string, string, string, string?, string?]> = {
  Hart: ['unit', '阿尔萨斯王子', 'Prince Arthas', '英雄', '洛丹伦的王子，圣骑士。擅长治疗友军并保护部队。'],
  Hpal: ['unit', '圣骑士', 'Paladin', '英雄', '勇猛的战士，可以治疗友军、为盟友提供神圣护甲。'],
  hfoo: ['unit', '步兵', 'Footman', '人类', '基础步兵单位，可以学习防御姿态。'],
  hkni: ['unit', '骑士', 'Knight', '人类', '强大的骑乘单位，可以学习动物作战训练。'],
  hgry: ['unit', '狮鹫骑士', 'Gryphon Rider', '人类', '骑着狮鹫的矮人，能攻击地面与空中单位。'],
  AHhb: ['ability', '神圣之光', 'Holy Light', '英雄技能', '一道神圣的光芒，可以治疗友军单位，或者对亡灵单位造成伤害。'],
  AHbz: ['ability', '暴风雪', 'Blizzard', '英雄技能', '召唤数波冰片对目标区域内的单位造成伤害。'],
  AHab: ['ability', '辉煌光环', 'Brilliance Aura', '英雄技能', '增加周围友军单位的魔法恢复速度。'],
  AOsh: ['ability', '震荡波', 'Shockwave', '英雄技能', '发出一道冲击波，对一条直线上的敌方地面单位造成伤害。'],
  ratc: ['item', '攻击之爪 +12', 'Claws of Attack +12', '永久', '持有者的攻击力提高 12 点。'],
  rde3: ['item', '守护指环 +4', 'Ring of Protection +4', '永久', '持有者的护甲提高 4 点。'],
  pghe: ['item', '大生命药水', 'Potion of Greater Healing', '可充能', '立刻恢复 500 点生命值。'],
  bspd: ['item', '速度之靴', 'Boots of Speed', '永久', '持有者的移动速度提高 60 点。'],
  hlst: ['item', '巨力头盔', 'Helm of Valor', '永久', '力量和敏捷各提高 4 点。'],
  cnob: ['item', '贵族圆环', 'Circlet of Nobility', '永久', '全部属性提高 2 点。'],
  ckng: ['item', '国王之冠 +5', 'Crown of Kings +5', '永久', '全部属性提高 5 点。'],
  Rhme: ['upgrade', '铁剑', 'Iron Forged Swords', '人类', '提高步兵、骑士、狮鹫骑士等近战单位的攻击力。'],
  Rhar: ['upgrade', '铁甲', 'Iron Plating', '人类', '提高步兵、骑士等单位的护甲。'],
  Rhla: ['upgrade', '皮甲', 'Studded Leather Armor', '人类', '提高火枪手、迫击炮小队等远程单位的护甲。'],
}

/* ---- Ability and item fields ------------------------------------------------------ */

const abilityRows: AbilityFieldRow[] = [
  ['aare', '作用范围', 'real', 'level', '0'], ['ahdu', '持续时间（英雄）', 'real', 'level', '0'], ['adur', '持续时间（普通）', 'real', 'level', '0'],
  ['acdn', '冷却时间', 'real', 'level', '5'], ['amcs', '魔法消耗', 'int', 'level', '65'], ['aran', '施法距离', 'real', 'level', '800'],
  ['Hhb1', '治疗量', 'real', 'level', '200'], ['atar', '目标允许', 'int', 'level', '12', '只读'], ['abuf', '魔法效果', 'string', 'level', 'BHhb', '未开放'],
  ['aher', '英雄技能', 'bool', 'global', '1'], ['alev', '等级数', 'int', 'global', '3', '只读'],
].map(([field, name, type, scope, value, status], i) => ({ _iid: `ab${i}`, field, name, type, scope, value, status: status ?? '可写', searchText: '' }))
const abilityData = (code = 'AHhb') => ({
  summary: `${code} 第 1 级：${abilityRows.length} 个字段`, detail: '字段来自选中单位身上这个技能的实例；只修改当前实例，不影响其他单位。', rows: abilityRows,
})

const itemRows: ItemFieldRow[] = [
  ['iclr', '物品颜色', 'int', '0'], ['ilev', '物品等级', 'int', '6'], ['iuse', '主动使用', 'bool', '0'], ['iper', '永久', 'bool', '1'],
  ['iprn', '可被抵押', 'bool', '1'], ['icid', '冷却组', 'string', 'AIat', '只读'], ['ista', '最大堆叠', 'int', '0', '未开放'], ['icha', '使用次数', 'int', '0'],
].map(([field, name, type, value, status], i) => ({ _iid: `it${i}`, field, name, type, value, status: status ?? '可写', editable: status !== '只读', searchText: '' }))
const itemData = () => ({ summary: `ratc 攻击之爪 +12：${itemRows.length} 个字段`, detail: '物品 0x100512，持有者 阿尔萨斯王子', rows: itemRows })

const effectRows: ItemFieldRow[] = [
  { _iid: 'fx:0', field: 'Iatt', name: '攻击力加成', type: 'int', value: '12', status: '可写', ability: 'AIat', effectClass: 'damage', scope: 'level', note: '直接改变英雄面板攻击力' },
  { _iid: 'fx:1', field: 'aare', name: '作用范围', type: 'real', value: '0', status: '可写', ability: 'AIat', effectClass: 'common', scope: 'level' },
  { _iid: 'fx:2', field: 'acdn', name: '冷却时间', type: 'real', value: '0', status: '只读', ability: 'AIat', effectClass: 'common', scope: 'level', editable: false },
]
const effectData = (level = '1') => ({ summary: `1 个附带技能，${effectRows.length} 个字段`, detail: `第 ${level} 级`, rows: effectRows })

/* ---- 3.0 extensions -------------------------------------------------------------- */

const bag = Array.from({ length: 30 }, (_, i) => ({ _iid: `bag:${i}`, slot: i + 1, rawcode: '', charges: '' as number | '', handle: '' })) as unknown as BagItemRow[]
const putBag = (i: number, rawcode: string, charges: string) => Object.assign(bag[i], { rawcode, charges: Number(charges), handle: `0x${(0x100400 + i * 7).toString(16)}` })
putBag(0, 'pghe', '3'); putBag(1, 'rde3', '1'); putBag(2, 'bspd', '1'); putBag(5, 'cnob', '1'); putBag(11, 'pghe', '2')
const SLOT_NAMES = ['头部', '胸部', '手套', '靴子', '戒指', '戒指 2', '主手', '副手', '饰品']
const SLOT_TYPES = ['头部', '胸部', '手套', '靴子', '戒指', '戒指', '主手', '副手', '饰品']
const equipment: EquipmentItemRow[] = SLOT_NAMES.map((slot, i) => ({ _iid: `equipment:${i}`, slot, rawcode: '', type: '', charges: '', handle: '' }))
const putEquip = (i: number, rawcode: string) => Object.assign(equipment[i], { rawcode, type: SLOT_TYPES[i], charges: 1, handle: `0x${(0x100600 + i * 5).toString(16)}` })
putEquip(0, 'hlst'); putEquip(4, 'rde3'); putEquip(6, 'ratc')
const talents: TalentRow[] = [
  { _iid: 'talent:AThg:0', hero: '人类加雷克', tier: 1 as unknown as string, choices: '[原生已选] ATa1 坚韧 / ATa2 迅捷', choiceCodes: ['ATa1', 'ATa2'], selected: '原生选择：ATa1；能力：无' },
  { _iid: 'talent:AThg:1', hero: '人类加雷克', tier: 2 as unknown as string, choices: 'ATb1 盾墙 / ATb2 猛击', choiceCodes: ['ATb1', 'ATb2'], selected: '' },
  { _iid: 'talent:AThg:2', hero: '人类加雷克', tier: 3 as unknown as string, choices: 'ATc1 统帅 / ATc2 狂怒', choiceCodes: ['ATc1', 'ATc2'], selected: '' },
]
let talentPoints = 1
const loadouts = ['套装1', '首领战']
const extensions = (): ExtensionsSnapshot => ({
  status: connected ? `扩展背包 30 格、装备 9 槽；人类加雷克 AThg/3；点数 ${talentPoints}/3` : '尚未读取 3.0 扩展状态',
  bag: connected ? bag : [], equipment: connected ? equipment : [], talents: connected ? talents : [],
  officialBackpacks: ['人类加雷克 (ebhg)', '人类兰登 (ebhl)', '人类伊拉斯塔 (ebhi)', '亡灵加雷克 (ebug)', '亡灵安雅 (ebua)', '亡灵列奥尼德 (ebul)'],
  currentBackpackChoice: '人类加雷克 (ebhg)', loadoutName: '套装1', loadoutNames: loadouts, selectedTalentIid: 'talent:AThg:1',
})

/* ---- File jobs (backpack definitions) -------------------------------------------- */

let defJob: DefinitionProgress = { jobId: '', status: 'idle', elapsed: 0 }
let defStarted = 0
function definitionProgress(): DefinitionProgress {
  if (defJob.status !== 'running') return defJob
  const elapsed = (Date.now() - defStarted) / 1000
  const total = 4
  const completed = Math.min(total, Math.floor(elapsed / 0.9))
  if (completed >= total) {
    const destination = (defJob.currentFile ?? '').replace(/(\.\w+)$/, ' (背包定义)$1')
    defJob = { ...defJob, status: 'succeeded', stage: 'complete', elapsed, completed: total, total,
      result: { success: true, message: '已补齐 4 个章节的背包定义并完成校验', destination, report: { report_path: destination + '.report.json', log_path: destination + '.log' } } }
    return defJob
  }
  return { ...defJob, elapsed, total, completed, index: completed + 1, stage: 'write_table', chapter: `第 ${completed + 1} 章` }
}


/* ---- Elephant ---------------------------------------------------------------------- */

const elephantParams: Record<string, string> = {
  hero_level: '10', unit_scale: '1.0', unit_rawcode: 'hfoo', item_rawcode: 'ckng', ability_rawcode: 'AOsh', ability_level: '3',
  tech_rawcode: 'Rhme', tech_level: '1', xp_rate: '1.0',
}
// The 68 global hotkeys of war3_backend.py, as get_all_hotkeys reports them.
const HOTKEY_SPECS: [string, string][] = [
  ['read_unit', 'Ctrl+F11  读取所有选中单位'],
  ['hero_level', 'Ctrl+Q  英雄等级'],
  ['instant_move', 'Ctrl+X  瞬间移动'],
  ['explode_unit', 'Ctrl+W  瞬间爆炸目标单位'],
  ['reveal_map', 'Home  开图'],
  ['hide_map', 'End  关图'],
  ['invulnerable', 'Ctrl+E  无敌'],
  ['vulnerable', 'Ctrl+R  取消无敌'],
  ['reset_cooldown', 'Ctrl+Z  重置冷却'],
  ['clone_to_self', 'Ctrl+A  复制单位给自己'],
  ['duplicate_inventory', 'Ctrl+D  复制背包物品'],
  ['unit_scale', 'Ctrl+P  设置大小'],
  ['item_charges', 'Ctrl+F  物品数量'],
  ['drop_inventory', 'Ctrl+T  丢弃背包所有物品'],
  ['add_ability', 'Ctrl+G  添加技能'],
  ['clone_unit', 'Ctrl+B  复制单位'],
  ['take_control', 'Ctrl+I  获取对方控制权'],
  ['add_resources', 'Ctrl+L  增加金币木材'],
  ['mass_clone', 'Ctrl+N  大量复制'],
  ['ability_level', 'Ctrl+H  设置技能等级'],
  ['remove_ability', 'Ctrl+J  删除技能'],
  ['all_auras', 'Ctrl+Num1  全光环'],
  ['all_passives', 'Ctrl+Num2  全被动'],
  ['six_artifacts', 'Ctrl+Num3  得到6个神器'],
  ['reinforcements', 'Ctrl+K  呼叫增援'],
  ['preset_item', 'Ctrl+M  得到物品'],
  ['preset_tech', 'Ctrl+O  得到科技'],
  ['create_all_items', 'Ctrl+S  创建所有物品'],
  ['ignore_collision', 'Alt+L  无视碰撞体积'],
  ['hero_attributes', 'Alt+Q  设置属性'],
  ['skill_points', 'Alt+W  增加技能点数'],
  ['kill_owner_units', 'Alt+E  秒杀玩家的所有单位'],
  ['xp_rate', 'Alt+R  增加经验获取率'],
  ['reset_ability', 'Alt+T  重置技能'],
  ['all_debuffs', 'Alt+Y  获得 debuff'],
  ['all_buffs', 'Alt+U  获得 buff'],
  ['fullscreen_swarm', 'Alt+I  全屏腐臭蜂群'],
  ['fullscreen_clap', 'Alt+O  全屏雷霆一击'],
  ['fullscreen_monsoon', 'Alt+P  全屏季风'],
  ['fullscreen_starfall', 'Alt+A  全屏群星陨落'],
  ['fullscreen_forked', 'Alt+S  全屏叉状闪电'],
  ['fullscreen_auto', 'Alt+D  全屏自动特效攻击'],
  ['toggle_unit_pause', 'Alt+F  暂停/恢复单位'],
  ['toggle_game_pause', 'Alt+G  暂停/恢复游戏'],
  ['end_game', 'Alt+H  结束游戏'],
  ['remove_all_abilities', 'Alt+J  技能全删'],
  ['ally_health_lock', 'Alt+K  我方锁血'],
  ['allied_cooldowns', 'Alt+C  重置我方全部技能冷却'],
  ['rapid_build', 'Alt+V  持续快速建造/升级'],
  ['instant_victory', 'Alt+B  直接胜利'],
  ['game_speed', 'Alt+N  加速/恢复游戏'],
  ['stat_hp_regen', 'Ctrl+Alt+F1  生命值恢复'],
  ['stat_mp_regen', 'Ctrl+Alt+F2  法力恢复'],
  ['stat_attack_speed', 'Ctrl+Alt+F3  实际攻速'],
  ['stat_critical_chance', 'Ctrl+Alt+F4  致命一击几率%'],
  ['stat_critical_damage', 'Ctrl+Alt+F5  暴击伤害%'],
  ['stat_spell_critical_chance', 'Ctrl+Alt+F6  法术暴击几率%'],
  ['stat_spell_critical_damage', 'Ctrl+Alt+F7  法术暴击伤害%'],
  ['stat_ability_speed_flat', 'Ctrl+Alt+F8  技能速度'],
  ['stat_ability_speed_percent', 'Ctrl+Alt+F9  技能速度%'],
  ['stat_ability_amp_flat', 'Ctrl+Alt+F10  技能增强'],
  ['stat_ability_amp_percent', 'Ctrl+Alt+F11  技能增强%'],
  ['stat_lifesteal_percent', 'Ctrl+Alt+F12  生命窃取%'],
  ['stat_ability_vamp_flat', 'Ctrl+Alt+1  技能汲取'],
  ['stat_ability_vamp_percent', 'Ctrl+Alt+2  技能汲取%'],
  ['stat_resolve_flat', 'Ctrl+Alt+3  斗志'],
  ['stat_resolve_percent', 'Ctrl+Alt+4  斗志%'],
  ['stat_magic_resistance_percent', 'Ctrl+Alt+5  魔法抗性%']
]
const PARAMS: Record<string, [string, string]> = {
  hero_level: ['等级', '10'], unit_scale: ['缩放', '1.0'], item_charges: ['数量', '99'], add_ability: ['技能ID', 'AOsh'], add_resources: ['增量', '10000'],
  mass_clone: ['数量', '5'], ability_level: ['等级', '3'], remove_ability: ['技能ID', 'AOsh'], reinforcements: ['单位ID', 'hfoo'], preset_item: ['物品ID', 'ckng'],
  preset_tech: ['科技ID', 'Rhme'], hero_attributes: ['属性值', '100'], skill_points: ['点数', '5'], xp_rate: ['倍率', '2.0'], reset_ability: ['技能ID', 'AHbz'],
  fullscreen_auto: ['特效数', '8'], game_speed: ['倍速', '2'],
}
const DANGEROUS = new Set(['explode_unit', 'drop_inventory', 'kill_owner_units', 'end_game', 'remove_all_abilities', 'instant_victory'])
const COMBAT = new Set(['instant_move', 'explode_unit', 'clone_unit', 'clone_to_self', 'take_control', 'mass_clone', 'kill_owner_units'])
const WORLD = new Set(['reveal_map', 'hide_map', 'toggle_game_pause', 'end_game', 'rapid_build', 'instant_victory', 'game_speed', 'add_resources'])
const hotkeys: HotkeyItem[] = HOTKEY_SPECS.map(([name, spec], i) => {
  const [key, ...rest] = spec.split(/\s+/)
  const param = name.startsWith('stat_') ? ['参数值', String(10 + i)] : PARAMS[name]
  return {
    name, key, label: rest.join(' '), enabled: i % 3 !== 2,
    paramKey: param ? name : null, paramLabel: param?.[0] ?? null, paramValue: param?.[1] ?? null,
    isDangerous: DANGEROUS.has(name),
    category: name.startsWith('stat_') ? 'stats' : name.startsWith('fullscreen_') ? 'fullscreen' : COMBAT.has(name) ? 'combat' : WORLD.has(name) ? 'world' : 'general',
  }
})
const DEFAULT_ARTIFACTS = ['klmm', 'srtl', 'shdt', 'crdt', 'frhg', 'nspi']
let artifacts = [...DEFAULT_ARTIFACTS]


/* ---- Codex: 3.0 equipment, hero abilities, map data -------------------------------- */

const EQUIPMENT3: { code: string; name: string; description: string }[] = [
  { code: 'I0FM', name: '霜之哀伤', description: '攻击力 +45，力量 +12。攻击时有几率冰冻目标 2 秒，并吸取目标的生命。' },
  { code: 'I0HD', name: '统御之盔', description: '全部属性 +10，护甲 +6。周围友军的生命恢复速度提高。' },
  { code: 'I0AS', name: '埃辛诺斯战刃', description: '攻击力 +38，敏捷 +15。攻击附带火焰伤害。' },
  { code: 'I0LR', name: '光明使者', description: '攻击力 +30，智力 +8。对亡灵单位造成额外神圣伤害。' },
  { code: 'I0DR', name: '龙鳞胸甲', description: '护甲 +12，魔法抗性 +20%。' },
  { code: 'I0WB', name: '疾风之靴', description: '移动速度 +80，敏捷 +6。' },
]
const HERO_SKILLS: { hero: string; name: string; code: string; levels: string; description: string }[] = [
  { hero: '加雷克', name: '盾牌猛击', code: 'AGsb', levels: '3', description: '用盾牌猛击目标，造成伤害并眩晕 2 秒。' },
  { hero: '加雷克', name: '战吼', code: 'AGwc', levels: '3', description: '激励周围友军，提高攻击力和移动速度。' },
  { hero: '兰登', name: '暗影步', code: 'ALss', levels: '3', description: '瞬间移动到目标身后，下次攻击造成额外伤害。' },
  { hero: '伊拉斯塔', name: '奥术飞弹', code: 'AIam', levels: '3', description: '发射数枚奥术飞弹，对目标造成魔法伤害。' },
  { hero: '安雅', name: '灵魂收割', code: 'AAsh', levels: '3', description: '吸取周围敌人的灵魂，为自己恢复生命和魔法。' },
  { hero: '列奥尼德', name: '复活', code: 'ALrv', levels: '1', description: '复活附近死去的友方单位。' },
]
const change = (field: string, label: string, before: unknown, after: unknown, file = 'war3map.w3u'): MapCatalogChange =>
  ({ field, label, level: 0, index: 0, value: after, rawValue: after, baseValue: before, baseKnown: before !== null, file, storage: 'int' })
const MAP_ROWS: MapCatalogRow[] = [
  { id: '0', kind: 'unit', rawcode: 'H000', base: 'Hpal', name: '乌瑟尔', isHero: true, heroNames: ['乌瑟尔·光明使者'], description: '白银之手骑士团的首领。', scope: '第 1 章', changeType: 'added', changeCount: 3, files: ['war3map.w3u'],
    changes: [change('unam', '名称', '圣骑士', '乌瑟尔'), change('ustr', '基础力量', 22, 26), change('uhpm', '生命上限', 650, 800)] },
  { id: '1', kind: 'unit', rawcode: 'hfoo', base: 'hfoo', name: '步兵', description: '基础步兵单位。', scope: '战役共用', changeType: 'modified', changeCount: 1, files: ['war3campaign.w3u'],
    changes: [change('uhpm', '生命上限', 420, 480, 'war3campaign.w3u')] },
  { id: '2', kind: 'item', rawcode: 'I000', base: 'ratc', name: '白银之手战锤', description: '攻击力 +15。', scope: '第 1 章', changeType: 'added', changeCount: 2, files: ['war3map.w3t'],
    changes: [change('unam', '名称', '攻击之爪 +12', '白银之手战锤', 'war3map.w3t'), change('Iatt', '攻击力加成', 12, 15, 'war3map.w3t')] },
  { id: '3', kind: 'ability', rawcode: 'A000', base: 'AHhb', name: '圣光术（战役）', description: '治疗量提高的神圣之光。', scope: '第 2 章', changeType: 'added', changeCount: 1, files: ['war3map.w3a'],
    changes: [change('Hhb1', '治疗量', 200, 260, 'war3map.w3a')] },
  { id: '4', kind: 'upgrade', rawcode: 'Rhme', base: 'Rhme', name: '铁剑', description: '', scope: '战役共用', changeType: 'modified', changeCount: 0, files: ['war3campaign.w3q'], changes: [] },
]
let mapJob: MapCatalogProgress = { jobId: '', status: 'idle', elapsed: 0 }
let mapStarted = 0
function mapProgress(): MapCatalogProgress {
  if (mapJob.status !== 'running') return mapJob
  const elapsed = (Date.now() - mapStarted) / 1000
  const total = 5
  const index = Math.min(total + 1, 1 + Math.floor(elapsed / 0.5))
  if (index > total) {
    mapJob = { ...mapJob, status: 'partial', stage: 'complete', elapsed, rowCount: MAP_ROWS.length,
      counts: { item: 1, ability: 1, unit: 2, upgrade: 1 }, scopes: ['战役共用', '第 1 章', '第 2 章'],
      diagnostics: [{ scope: '第 2 章', file: 'war3map.wts', message: '字符串 TRIGSTR_118 没有找到，相关名称显示为原始代码。', impact: '只影响显示，不影响读取其他字段。' }] }
    return mapJob
  }
  return { ...mapJob, elapsed, index, total, scope: `第 ${index} 章`, file: `Chapter${index}.w3x\\war3map.w3u` }
}


/* ---- Map scripts and archive ------------------------------------------------------- */

let scriptOptions: MapScriptOptions = { prefix: '-mx', features: ['resources', 'hero', 'units', 'abilities', 'items', 'automatic', 'world'],
  artifact_codes: ['klmm', 'srtl', 'shdt', 'crdt', 'frhg', 'nspi'], resource_amount: 10000 }
let scriptJob: MapScriptProgress = { jobId: '', status: 'idle', elapsed: 0 }
let scriptStarted = 0
let scriptPaths: string[] = []
function scriptProgress(): MapScriptProgress {
  if (scriptJob.status !== 'running') return scriptJob
  const elapsed = (Date.now() - scriptStarted) / 1000
  const total = 6
  const steps = Math.floor(elapsed / 0.6)
  const fileIndex = Math.min(scriptPaths.length, Math.floor(steps / total) + 1)
  if (steps >= total * scriptPaths.length) {
    const files = scriptPaths.map(source => ({ source, status: 'succeeded', destination: source.replace(/(\.\w+)$/, ' (火龙)$1'), message: '', error: '', logPath: '', reportPath: '',
      usagePath: source.replace(/(\.\w+)$/, ' (火龙) 命令说明.txt') }))
    scriptJob = { ...scriptJob, status: 'succeeded', stage: 'complete', elapsed, fileCompleted: files.length, fileSucceeded: files.length, files }
    return scriptJob
  }
  const stages = ['source_hash_begin', 'start', 'catalogue_begin', 'script_compile', 'script_write', 'archive_verify']
  return { ...scriptJob, elapsed, fileIndex, fileCompleted: fileIndex - 1, total, completed: steps % total, stage: stages[steps % total],
    chapter: `第 ${(steps % total) + 1} 步`, currentFile: scriptPaths[fileIndex - 1] }
}
const SAVES = [
  { path: 'C:\\Users\\player\\Documents\\Warcraft III\\Campaigns\\HumanCampaign03.w3z', name: 'HumanCampaign03.w3z', date: '1761580800.5' },
  { path: 'C:\\Users\\player\\Documents\\Warcraft III\\Campaigns\\HumanCampaign04.w3z', name: 'HumanCampaign04.w3z', date: '1761667200.25' },
]
const ARCHIVE_ROWS = [
  { scope: '阿尔萨斯', key: '英雄等级', type: 'integer', value: '8' },
  { scope: '阿尔萨斯', key: '经验值', type: 'integer', value: '3150' },
  { scope: '阿尔萨斯', key: '技能 AHhb', type: 'integer', value: '3' },
  { scope: '阿尔萨斯', key: '技能 AHad', type: 'integer', value: '2' },
  { scope: '阿尔萨斯', key: '物品栏 1', type: 'item', value: 'ratc (攻击之爪 +12)' },
  { scope: '阿尔萨斯', key: '物品栏 2', type: 'item', value: 'pghe ×2' },
  { scope: '吉安娜', key: '英雄等级', type: 'integer', value: '6' },
  { scope: '全局', key: '金币', type: 'integer', value: '1500' },
]
const RPG_CODES = [
  { kind: '游戏内存扫描', code: '-load 9Fk2-QpLx-77Ra-MmZ3-0vTe-4HcY', source: '内存匹配 (chat history)' },
  { kind: '游戏内存扫描', code: '-load H7cQ-21aX-pL0k-Yy3N-8sDd', source: '内存匹配 (string table)' },
]

/* ---- Handlers ------------------------------------------------------------------------ */

const handlers: Record<string, (...args: any[]) => unknown> = {
  get_system_status: status,
  get_ui_notifications: () => [],
  async connect_process() { await wait(900); connected = true; return { success: true, status: status() } },
  cancel_discovery: () => ({ success: true }),
  set_hotkeys_enabled: (on: boolean) => { hotkeysOn = on; return { success: true, enabled: on, status: '' } },
  set_ui_language: (lang: 'zh' | 'en') => { language = lang; return { success: true, language: lang, translations: {} } },

  get_resource_snapshot: snapshot,
  async refresh_resources() { await wait(600); return { success: true, data: snapshot() } },
  select_resource_group(iid: string) {
    if (!groupData.some(g => g.iid === iid)) throw new Error('资源组已变化，请重新读取')
    selectedGroup = iid
    return snapshot()
  },
  set_resource(kind: string, v: string) {
    const n = Number(v)
    const g = cur()
    if (kind === 'gold') g.gold = n
    else if (kind === 'lumber') g.lumber = n
    else if (kind === 'food_used') g.used = n
    else if (kind === 'food_cap') g.cap = n
    else return { success: false, error: `Unknown resource kind: ${kind}` }
    return { success: true, data: snapshot() }
  },
  add_resource(kind: string, d?: string) {
    if (d !== undefined) delta = d
    const n = Number(delta)
    const g = cur()
    if (kind !== 'lumber') g.gold += n
    if (kind !== 'gold') g.lumber += n
    return { success: true, data: snapshot() }
  },
  add_resource_lock(kind: string) {
    const g = cur()
    const v = kind === 'gold' ? g.gold : kind === 'lumber' ? g.lumber : kind === 'food_used' ? g.used : g.cap
    const local = g === groupData[0]
    locks.set(`resource:${g.iid}:${kind}`, { _iid: `resource:${g.iid}:${kind}`, scope: local ? '本地玩家资源' : `资源组 ${g.label.split(' ')[0]}`, label: LOCK_LABEL[kind], value: String(v) })
    return { success: true, locks: lockList() }
  },
  async gold_mines(scope: string, amount: string | null) {
    await wait(1200)
    const rows = mines().map(r => amount === null ? r : { ...r, after: Number(amount), status: '已修改' })
    const data: GoldMineData = { scope: scope as GoldMineData['scope'], action: amount === null ? 0 : 1, count: rows.length, visited: rows.length, ignored: 0,
      changed: amount === null ? 0 : rows.length, unchanged: 0, failed: 0, uncertain: 0, rows }
    return { success: true, data }
  },

  get_locks: lockList,
  remove_lock(iid: string) { locks.delete(iid); return { success: true, locks: lockList() } },
  async apply_locks_once() { await wait(400); return { success: true, message: '锁定项已执行一次' } },

  get_selected_unit_snapshot: unit,
  get_unit_candidates_snapshot: () => (connected ? candidateRows : []),
  async read_all_selected_units() { await wait(700); return { unit: unit(), candidates: candidateRows } },
  async read_selected_unit() { await wait(500); return unit() },
  async write_selected_unit(targets: Record<string, string>) {
    await wait(400)
    if (targets.hpTarget) fields.find(f => f._iid === 'hp')!.value = targets.hpTarget
    if (targets.mpTarget) fields.find(f => f._iid === 'mp')!.value = targets.mpTarget
    if (targets.hpRegenTarget) regen.hp = targets.hpRegenTarget
    if (targets.mpRegenTarget) regen.mp = targets.mpRegenTarget
    if (targets.xTarget) pos.x = Number(targets.xTarget).toFixed(1)
    if (targets.yTarget) pos.y = Number(targets.yTarget).toFixed(1)
    return { success: true, data: unit() }
  },
  async write_unit_field(iid: string, v: string) {
    await wait(400)
    fields.find(f => f._iid === iid)!.value = v
    return { success: true, data: unit() }
  },
  add_unit_field_lock(iid: string, v: string) {
    const f = fields.find(x => x._iid === iid)!
    locks.set(`unit:${iid}`, { _iid: `unit:${iid}`, scope: '选中单位', label: f.label, value: v })
    return { success: true, locks: lockList() }
  },
  async refresh_unit_candidates() { await wait(800); return candidateRows },
  async read_selection_candidate() { await wait(500); return { success: true, unit: unit() } },
  async read_native_selection() { await wait(1000); return { success: true, unit: unit() } },

  async batch_read_units() {
    await wait(700)
    return {
      success: true,
      units: [
        { checked: true, rawcode: 'Hart', instance: '1048615:615051520:3', hp: '1250', mp: '600', error: null },
        { checked: true, rawcode: 'hfoo', instance: '1048619:615125760:3', hp: '420', mp: '0' },
        { checked: true, rawcode: 'hfoo', instance: '1048620:615126912:3', hp: '318', mp: '0' },
        { checked: false, rawcode: 'hrif', instance: '1048622:615131712:3', hp: '535', mp: '0' },
        { checked: true, rawcode: 'hgry', instance: '1048630:615136528:3', hp: '875', mp: '0' },
        { checked: false, rawcode: 'hmpr', instance: '1048633:615141264:3', hp: '290', mp: '200' },
      ],
      fields: [
        ...[['hp_current', '当前生命'], ['hp_max', '生命上限'], ['mp_current', '当前魔法'], ['mp_max', '魔法上限'], ['move_speed', '移动速度'], ['attack_speed', '攻击速度'], ['attack1_range', '攻击1范围']]
          .map(([key, label]) => ({ key, label, category: '基础', type: 'f32', supported: true })),
      ],
    }
  },
  async batch_write_units(instances: string[], targets: Record<string, string>) {
    await wait(900)
    const reports = instances.flatMap(u => Object.entries(targets).map(([k, v]) => ({ unit: u, field: k, target: v, status: '已写入', reason: `读回 ${v}`, actual: v })))
    return { success: true, message: `批量处理完成，共 ${reports.length} 项字段结果`, reports, stopped: false, logPath: '' }
  },


  async read_ability_fields(rawcode: string) { await wait(600); return abilityData(rawcode) },
  async read_unit_fields() {
    await wait(500)
    return { success: true, rawcode: 0x48617274, unitCode: 'Hart', identity: 'mock-only', rows: [
      { key: 'ua1r:1', code: 'ua1r', constant: 'UNIT_WEAPON_RF_ATTACK_RANGE', kind: 'real', weapon: 1, label: '攻击 1 - 攻击范围', labelEn: 'Attack Range', category: '攻击 1', writable: true, value: 600, note: '原生字段；写入以游戏接受且读回一致为准' },
      { key: 'ua1r:2', code: 'ua1r', constant: 'UNIT_WEAPON_RF_ATTACK_RANGE', kind: 'real', weapon: 2, label: '攻击 2 - 攻击范围', labelEn: 'Attack Range', category: '攻击 2', writable: false, value: 500, note: '第二武器射程可读取；游戏现有原生接口无法可靠写入' },
    ] }
  },
  async write_unit_field_value(key: string, value: string) { await wait(300); return { success: true, key, value: Number(value) } },
  async write_ability_field(iid: string, v: string) {
    await wait(400)
    const row = abilityRows.find(r => r._iid === iid)!
    if (row.status === '只读') return { success: false, error: '这个字段只读' }
    row.value = v; row.status = '已修改'
    return { success: true, data: abilityData() }
  },
  async read_item_fields(slot: string) {
    await wait(500)
    return slot === '3' ? { summary: '槽位 4 为空', detail: '', rows: [] } : itemData()
  },
  async write_item_field(iid: string, v: string) {
    await wait(400)
    Object.assign(itemRows.find(r => r._iid === iid)!, { value: v, status: '已修改' })
    return { success: true, data: itemData() }
  },
  async read_item_effect_fields(_area: string, _slot: string, level: string) { await wait(600); return effectData(level) },
  async write_item_effect_field(iid: string, v: string) {
    await wait(400)
    Object.assign(effectRows.find(r => r._iid === iid)!, { value: v, status: '已修改' })
    return { success: true, data: effectData() }
  },

  async refresh_extension_status() { await wait(500); return extensions() },
  async extension_bag_action(action: string, p: Record<string, any>) {
    await wait(500)
    const i = bag.findIndex(r => r._iid === p.row_iid)
    if (action === 'add_item') {
      if (!p.rawcode) return { success: false, error: '请先填写物品 ID' }
      putBag(bag.findIndex(r => !r.rawcode), p.rawcode, String(p.charges || 1))
    } else if (action === 'set_charges' && i >= 0) bag[i].charges = String(p.charges)
    else if (action === 'duplicate' && i >= 0) putBag(bag.findIndex(r => !r.rawcode), bag[i].rawcode, bag[i].charges)
    else if (action === 'destroy' && i >= 0) Object.assign(bag[i], { rawcode: '', charges: '', handle: '' })
    return { success: true, data: extensions() }
  },
  async extension_equipment_action(action: string, p: Record<string, any>) {
    await wait(action.includes('restore') ? 2600 : 900)
    const i = equipment.findIndex(r => r._iid === p.row_iid)
    if (action === 'unequip' && i >= 0) Object.assign(equipment[i], { rawcode: '', type: '', charges: '', handle: '' })
    if (action === 'save_loadout' && p.name && !loadouts.includes(p.name)) loadouts.push(p.name)
    const messages: Record<string, string> = { save_loadout: `已保存套装 ${p.name}`, restore_loadout: '已恢复套装并核对九个部位', audit: '九个部位均已核对' }
    return { success: true, message: messages[action] ?? '', data: extensions() }
  },
  async extension_talent_action(action: string, p: Record<string, any>) {
    await wait(500)
    if (action === 'grant_point') talentPoints++
    if (action === 'reset_talents') { talentPoints = 3; talents.forEach(r => { r.selected = '' }) }
    if (action === 'add_choice') { const r = talents.find(x => x._iid === p.row_iid); if (r) r.selected = p.choice }
    return { success: true, data: extensions() }
  },

  get_backpack_definition_progress: () => definitionProgress(),
  start_backpack_definitions(path: string, folder: string) {
    defStarted = Date.now()
    defJob = { jobId: 'def1', status: 'running', stage: 'queued', elapsed: 0, currentFile: path, logPath: `${folder || 'D:\\Maps'}\\definitions.log` }
    return { success: true, jobId: 'def1' }
  },
  start_backpack_definitions_batch(paths: string[], folder: string) { return handlers.start_backpack_definitions(paths[0], folder) },
  cancel_backpack_definitions() { defJob = { ...defJob, status: 'cancelled', result: { success: false, cancelled: true, error: '处理已停止，原文件已保留。' } }; return { success: true } },
  choose_definition_files: () => ({ success: true, cancelled: false, paths: ['D:\\Warcraft III\\Maps\\Campaign\\HumanCampaign.w3n'] }),
  choose_definition_folder: () => ({ success: true, cancelled: false, path: 'D:\\Warcraft III\\Maps\\Output' }),


  get_map_script_options: () => ({ success: true, options: scriptOptions, features: {} }),
  save_map_script_options(options: MapScriptOptions) { scriptOptions = options; return { success: true, options } },
  start_map_scripts(paths: string[], folder: string) {
    scriptPaths = paths; scriptStarted = Date.now()
    scriptJob = { jobId: 'hke1', status: 'running', elapsed: 0, batchMode: true, fileTotal: paths.length, fileCompleted: 0, outputFolder: folder, logPath: 'D:\\Warcraft III\\Maps\\火龙注入.log' }
    return { success: true, jobId: 'hke1' }
  },
  get_map_script_progress: () => scriptProgress(),
  cancel_map_scripts() { scriptJob = { ...scriptJob, status: 'cancelled' }; return { success: true } },

  async scan_archive_directory(dir: string) { await wait(700); return { success: true, directory: dir || 'C:\\Users\\player\\Documents\\Warcraft III', files: SAVES } },
  async read_archive_file() { await wait(900); return { success: true, rows: ARCHIVE_ROWS } },
  async read_live_heroes() { await wait(900); return connected ? { success: true, rows: ARCHIVE_ROWS.slice(0, 6) } : { success: false, error: '没有连接游戏' } },
  async scan_rpg_codes_memory() { await wait(1500); return { success: true, rows: RPG_CODES } },
  async parse_rpg_codes_text(text: string, prefix: string) {
    await wait(300)
    const rows = text.split(/\r?\n/).filter(l => l.includes(prefix)).map(l => ({ kind: '剪贴板/文本提取', code: l.slice(l.indexOf(prefix)).trim(), source: '文本分析' }))
    return { success: true, rows }
  },
  search_id_catalog: (kind: string, query: string) => {
    const q = query.trim().toLowerCase()
    const all = Object.entries(CATALOG).filter(([, v]) => v[0] === kind)
    const rows = all
      .filter(([code, v]) => !q || [code, v[1], v[2], v[3] ?? '', v[4] ?? ''].some(x => x.toLowerCase().includes(q)))
      .map(([code, v]) => ({ rawcode: code, name_zh: v[1], name_en: v[2], category: v[3] ?? '', description: v[4] ?? '', descriptionSource: '游戏基础资料', descriptionPartial: false }))
    return { kind, totalCount: all.length, matchCount: rows.length, rows }
  },
  search_3_equipment(query: string) {
    const q = query.trim()
    const rows = EQUIPMENT3.filter(r => !q || [r.code, r.name, r.description].some(x => x.includes(q)))
    return { totalCount: EQUIPMENT3.length, matchCount: rows.length, rows }
  },
  search_3_hero_skills(hero: string, query: string) {
    const q = query.trim()
    const rows = HERO_SKILLS.filter(r => (!hero || hero === '全部角色' || r.hero === hero) && (!q || [r.code, r.name, r.description].some(x => x.includes(q))))
    return { heroes: ['全部角色', ...new Set(HERO_SKILLS.map(r => r.hero))], totalCount: HERO_SKILLS.length, matchCount: rows.length, rows }
  },

  choose_definition_file: () => ({ success: true, cancelled: false, path: 'D:\\Warcraft III\\Maps\\Campaign\\HumanCampaign.w3n' }),
  start_map_catalog(path: string) { mapStarted = Date.now(); mapJob = { jobId: 'map1', status: 'running', elapsed: 0, stage: 'chapter', source: path }; return { success: true, jobId: 'map1' } },
  get_map_catalog_progress: () => mapProgress(),
  cancel_map_catalog() { mapJob = { ...mapJob, status: 'cancelled' }; return { success: true } },
  search_map_catalog(_id: string, kind: string, query: string, scope: string, changeType: string, offset: number) {
    const rows = MAP_ROWS.filter(r => (!kind || r.kind === kind) && (!scope || r.scope === scope) && (!changeType || r.changeType === changeType)
      && (!query || [r.rawcode, r.name, r.description].some(x => x.includes(query))))
    return { success: true, rows: rows.slice(offset, offset + 100).map(({ changes: _c, ...r }) => r), matchCount: rows.length, totalCount: MAP_ROWS.length }
  },
  get_map_catalog_entry: (_id: string, row: string) => MAP_ROWS.find(r => r.id === row),
  async export_map_catalog(_id: string, format: string) { await wait(700); return { success: true, path: `D:\\Warcraft III\\Maps\\Campaign\\HumanCampaign 自定义目录.${format}`, count: MAP_ROWS.length } },
  get_elephant_parameters: () => ({ ...elephantParams }),
  set_elephant_parameter(key: string, value: string) { elephantParams[key] = value; return { success: true, changedParameters: { [key]: value } } },
  async prewarm_elephant() { await wait(1200); return { success: true, message: '大象功能初始化就绪' } },
  async execute_elephant_action(action: string, params: Record<string, unknown> = {}) {
    await wait(450)
    if (!connected) return { success: false, error: '没有选中单位', action }
    if (action === 'remove_ability') return { success: false, error: '选中单位没有这个技能', action }
    if (action === 'hero_level_read') elephantParams.hero_level = '10'
    // Which remembered parameter each action stores, as execute_elephant_action does.
    const stores: Record<string, [string, string][]> = {
      hero_level_set: [['hero_level', 'level']], set_scale: [['unit_scale', 'scale']], set_xp_rate: [['xp_rate', 'rate']],
      create_unit: [['unit_rawcode', 'rawcode']], add_item: [['item_rawcode', 'rawcode']], remove_ability: [['ability_rawcode', 'rawcode']],
      add_ability: [['ability_rawcode', 'rawcode'], ['ability_level', 'level']], set_ability_level: [['ability_rawcode', 'rawcode'], ['ability_level', 'level']],
      set_tech: [['tech_rawcode', 'rawcode'], ['tech_level', 'level']],
    }
    for (const [key, param] of stores[action] ?? []) if (params[param]) elephantParams[key] = String(params[param])
    return { success: true, action, parameters: { ...elephantParams } }
  },

  get_all_hotkeys: () => hotkeys.map(h => ({ ...h })),
  set_hotkey_check(name: string, enabled: boolean) { hotkeys.find(h => h.name === name)!.enabled = enabled; return { success: true, name, enabled } },
  set_all_hotkeys_checks(enabled: boolean) { hotkeys.forEach(h => { h.enabled = enabled }); return { success: true, enabled, hotkeys: hotkeys.map(h => ({ ...h })) } },
  set_hotkey_parameter(paramKey: string, value: string) {
    hotkeys.filter(h => h.paramKey === paramKey).forEach(h => { h.paramValue = value })
    return { success: true, paramKey, value }
  },
  async trigger_hotkey(name: string) {
    await wait(400)
    const h = hotkeys.find(x => x.name === name)!
    return connected ? { success: true, name, message: `${h.label}：已执行` } : { success: false, error: '没有连接游戏' }
  },
  get_artifact_plan: () => ({ codes: [...artifacts], isDefault: artifacts.join() === DEFAULT_ARTIFACTS.join(), defaultCodes: DEFAULT_ARTIFACTS }),
  save_artifact_plan(codes: string[]) { artifacts = [...codes]; return { success: true, plan: handlers.get_artifact_plan() } },
  restore_default_artifact_plan() { artifacts = [...DEFAULT_ARTIFACTS]; return { success: true, plan: handlers.get_artifact_plan() } },
  async apply_artifact_plan() { await wait(800); return { success: true, message: '已给选中英雄 6 件神器' } },
}

const api = new Proxy({} as Record<string, (...args: any[]) => Promise<any>>, {
  get: (_t, name: string) => async (...args: any[]) => {
    const fn = handlers[name]
    if (!fn) return { success: false, error: `mock bridge: ${name} not implemented` }
    return fn(...args)
  },
})

window.pywebview = { api }
window.dispatchEvent(new Event('pywebviewready'))
