import { useState } from 'react'
import { Button, PillGroup, TextField } from '../../../ds'
import { api } from '../../../lib/api'
import type { CatalogItemRow } from '../../../lib/types'
import { useCommandCard } from '../../state/commands'
import { fill, useT } from '../../i18n'
import { DataTable } from '../common/DataTable'
import { CodexLayout, Count, Fact, GiveButton, SheetActions, SheetHead, SheetText, copyCode, useDebounced, useSearch } from './Codex'
import s from './CatalogPage.module.css'

export type CatalogKind = 'item' | 'ability' | 'unit' | 'upgrade'

const KINDS: { value: CatalogKind; label: string }[] = [
  { value: 'item', label: '物品' }, { value: 'ability', label: '技能' }, { value: 'unit', label: '单位' }, { value: 'upgrade', label: '科技' },
]

/** ID lookup in the bundled catalogue of stock objects; the tech page opens on upgrades. */
export function CatalogSearch({ initialKind }: { initialKind: CatalogKind }) {
  const t = useT()
  const [kind, setKind] = useState<CatalogKind>(initialKind)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const settled = useDebounced(query)
  const { data, loading } = useSearch(() => api.searchIdCatalog(kind, settled), [kind, settled])
  const rows = data?.rows ?? []
  const entry = rows.find(r => r.rawcode === selected) ?? null

  useCommandCard([
    { key: 'Q', icon: 'catalog', title: t('物品'), description: t('切换到物品目录。'), active: kind === 'item', onPress: () => setKind('item') },
    { key: 'W', icon: 'hero-skill', title: t('技能'), description: t('切换到技能目录。'), active: kind === 'ability', onPress: () => setKind('ability') },
    { key: 'E', icon: 'unit-hero', title: t('单位'), description: t('切换到单位目录。'), active: kind === 'unit', onPress: () => setKind('unit') },
    { key: 'R', icon: 'upgrade-catalog', title: t('科技'), description: t('切换到科技目录。'), active: kind === 'upgrade', onPress: () => setKind('upgrade') },
    { key: 'A', icon: 'copy', title: t('复制代码'), description: t('复制选中条目的四字符代码。'), disabled: !entry, onPress: () => entry && void copyCode(entry.rawcode) },
  ])

  return (
    <CodexLayout
      toolbar={<>
        <PillGroup<CatalogKind> label={t('目录')} value={kind} onChange={k => { setKind(k); setSelected(null) }} options={KINDS.map(k => ({ value: k.value, label: t(k.label) }))} />
        <TextField
          variant="search"
          className={s.search}
          aria-label={t('搜索目录')}
          placeholder={t('代码、中文名、英文名、分类或效果')}
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
        <Count match={data?.matchCount ?? 0} total={data?.totalCount ?? 0} shown={rows.length} loading={loading} />
      </>}
      list={
        <DataTable<CatalogItemRow>
          label={t('目录条目')}
          fill
          rows={rows}
          rowKey={r => r.rawcode}
          selected={selected}
          onSelect={r => setSelected(r.rawcode)}
          empty={loading ? t('正在检索…') : t('没有匹配的条目。换个更通用的词试试，例如“骑士”“光环”“Paladin”或四字符代码。')}
          columns={[
            { key: 'rawcode', label: t('代码'), width: '72px', mono: true },
            { key: 'name', label: t('名称'), width: 'minmax(160px, 1.1fr)', render: r => <span className={s.name}>{r.name_zh || r.name_en || '—'}<small>{r.name_en}</small></span> },
            { key: 'description', label: kind === 'unit' ? t('单位介绍') : t('描述或效果'), width: 'minmax(0, 2fr)', render: r => <span className={s.desc}>{r.description}</span> },
            { key: 'category', label: t('分类'), width: '110px', render: r => r.category || t('未分类') },
          ]}
        />
      }
      footer={t('不区分大小写；说明来自游戏基础资料，地图自定义的内容可能不同。')}
      sheet={entry && {
        key: `${kind}:${entry.rawcode}`,
        content: <>
          <SheetHead
            code={entry.rawcode}
            name={entry.name_zh || entry.name_en}
            sub={entry.name_zh ? entry.name_en : undefined}
            facts={<Fact label={t('分类')}>{entry.category || t('未分类')}</Fact>}
          />
          <SheetText>
            <p>{entry.description || t('游戏基础资料没有这个对象的介绍。')}</p>
            {entry.descriptionSource && <small>{entry.descriptionSource}</small>}
            {entry.descriptionPartial && <small>{t('部分变量以游戏内数值为准。')}</small>}
          </SheetText>
          <SheetActions>
            <Button size="sm" onClick={() => setSelected(null)}>{t('关闭')}</Button>
            <Button size="sm" icon="copy" onClick={() => void copyCode(entry.rawcode)}>{t('复制代码')}</Button>
            {kind === 'item' && <GiveButton action="add_item" params={{ rawcode: entry.rawcode }} label={t('给选中单位')} done={fill(t('已添加物品 {name}'), { name: entry.name_zh || entry.rawcode })} />}
            {kind === 'ability' && <GiveButton action="add_ability" params={{ rawcode: entry.rawcode, level: '1' }} label={t('给选中单位')} done={fill(t('已添加技能 {name}'), { name: entry.name_zh || entry.rawcode })} />}
          </SheetActions>
        </>,
      }}
    />
  )
}

export default function CatalogPage() {
  return <CatalogSearch initialKind="item" />
}
