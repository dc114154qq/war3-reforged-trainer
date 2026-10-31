// Page ids regrouped into six chapters; shared with --ui-check and persisted navigation.
// Ids are a contract: the Python --ui-check and saved navigation state refer to them.

export type PageId =
  | 'resources' | 'unit' | 'batch' | 'locks'
  | 'unit_fields' | 'ability_fields' | 'item_fields' | 'extensions'
  | 'elephant' | 'hotkeys'
  | 'catalogs' | 'upgrade_catalog' | 'map_catalog' | 'equipment3' | 'hero_skills'
  | 'map_scripts' | 'archive'

export type ChapterId = 'battle' | 'fields' | 'elephant' | 'codex' | 'huolong' | 'archive'

export interface PageMeta {
  id: PageId
  label: string
}

export interface Chapter {
  id: ChapterId
  label: string
  pages: PageMeta[]
}

export const CHAPTERS: Chapter[] = [
  {
    id: 'battle', label: '战况', pages: [
      { id: 'resources', label: '玩家资源' },
      { id: 'unit', label: '选中单位' },
      { id: 'batch', label: '批量修改' },
      { id: 'locks', label: '锁定列表' },
    ],
  },
  {
    id: 'fields', label: '字段', pages: [
      { id: 'unit_fields', label: '单位字段' },
      { id: 'ability_fields', label: '技能字段' },
      { id: 'item_fields', label: '物品字段' },
      { id: 'extensions', label: '3.0 扩展' },
    ],
  },
  {
    id: 'elephant', label: '大象', pages: [
      { id: 'elephant', label: '经典功能' },
      { id: 'hotkeys', label: '全局快捷键' },
    ],
  },
  {
    id: 'codex', label: '典籍', pages: [
      { id: 'catalogs', label: 'ID 检索' },
      { id: 'upgrade_catalog', label: '科技目录' },
      { id: 'map_catalog', label: '自定义地图数据' },
      { id: 'equipment3', label: '3.0 装备' },
      { id: 'hero_skills', label: '3.0 英雄技能' },
    ],
  },
  {
    id: 'huolong', label: '火龙', pages: [
      { id: 'map_scripts', label: '脚本注入' },
    ],
  },
  {
    id: 'archive', label: '存档', pages: [
      { id: 'archive', label: '代码提取' },
    ],
  },
]

export const PAGES: PageMeta[] = CHAPTERS.flatMap(c => c.pages)
export const chapterOf = (page: PageId) => CHAPTERS.find(c => c.pages.some(p => p.id === page))!
export const pageMeta = (page: PageId) => PAGES.find(p => p.id === page)!
export const isPageId = (value: unknown): value is PageId => PAGES.some(p => p.id === value)
