import { useState } from 'react'
import { Button, Select, TextField, announce } from '../../../ds'
import { api } from '../../../lib/api'
import type { HeroSkillRow } from '../../../lib/types'
import { useCommandCard } from '../../state/commands'
import { useSystem } from '../../state/system'
import { fill, useT } from '../../i18n'
import { DataTable } from '../common/DataTable'
import { CodexLayout, Count, Fact, GiveButton, SheetActions, SheetHead, SheetText, copyCode, useDebounced, useSearch } from './Codex'
import s from './CatalogPage.module.css'

const ALL_HEROES = '全部角色'

/** Abilities of the new 3.0 campaign heroes, filterable by hero. */
export default function HeroSkillsPage() {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const [hero, setHero] = useState('')
  const [heroes, setHeroes] = useState<string[]>([])
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const settled = useDebounced(query)
  const { data, loading } = useSearch(async () => {
    const result = await api.search3HeroSkills(hero, settled)
    // The backend's list starts with its own "all heroes" entry (全部角色); the empty option covers it.
    if (result?.heroes?.length) setHeroes(h => (h.length ? h : result.heroes.filter(name => name !== ALL_HEROES)))
    return result
  }, [hero, settled])
  const rows = data?.rows ?? []
  const keyOf = (r: HeroSkillRow) => `${r.hero}:${r.code}`
  const entry = rows.find(r => keyOf(r) === selected) ?? null

  const add = async (row: HeroSkillRow) => {
    const result = await api.executeElephantAction('add_ability', { rawcode: row.code, level: '1' })
    if (result?.success) announce(fill(t('已添加技能 {name}'), { name: row.name }))
    else window.dispatchEvent(new CustomEvent('war3-error', { detail: result?.error || '操作未完成' }))
  }

  useCommandCard([
    { key: 'Q', icon: 'copy', title: t('复制代码'), description: t('复制选中技能的四字符代码。'), disabled: !entry, onPress: () => entry && void copyCode(entry.code) },
    { key: 'W', icon: 'add-ability', title: t('添加技能'), description: t('把选中技能加给游戏里选中的单位。'), disabled: !entry || !connected, onPress: () => entry && void add(entry) },
  ])

  return (
    <CodexLayout
      toolbar={<>
        <Select
          aria-label={t('所属英雄')}
          className={s.hero}
          value={hero}
          onChange={e => { setHero(e.target.value); setSelected(null) }}
          options={[{ value: '', label: t('全部英雄') }, ...heroes.map(h => ({ value: h, label: h }))]}
        />
        <TextField
          variant="search"
          className={s.search}
          aria-label={t('搜索技能')}
          placeholder={t('技能名称、代码或效果，例如“暴风雪”')}
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
        <Count match={data?.matchCount ?? 0} total={data?.totalCount ?? 0} shown={rows.length} loading={loading} />
      </>}
      list={
        <DataTable<HeroSkillRow>
          label={t('3.0 英雄技能')}
          fill
          rows={rows}
          rowKey={keyOf}
          selected={selected}
          onSelect={r => setSelected(keyOf(r))}
          empty={loading ? t('正在检索…') : t('没有匹配的技能。选“全部英雄”或换个词，例如“治疗”“复活”。')}
          columns={[
            { key: 'code', label: t('代码'), width: '72px', mono: true },
            { key: 'hero', label: t('所属英雄'), width: '120px' },
            { key: 'name', label: t('技能名称'), width: 'minmax(130px, 1fr)', render: r => <span className={s.name}>{r.name}</span> },
            { key: 'levels', label: t('等级'), width: '56px', render: r => r.levels || '1' },
            { key: 'description', label: t('效果'), width: 'minmax(0, 2fr)', render: r => <span className={s.desc}>{r.description}</span> },
          ]}
        />
      }
      footer={t('技能取自官方 3.0 战役英雄。地图可能改动同一代码的效果；添加技能需要当前地图里有这个技能的定义。')}
      sheet={entry && {
        key: keyOf(entry),
        content: <>
          <SheetHead
            code={entry.code}
            name={entry.name}
            facts={<><Fact label={t('所属英雄')}>{entry.hero}</Fact><Fact label={t('等级')}>{entry.levels || '1'}</Fact></>}
          />
          <SheetText><p>{entry.description || '—'}</p></SheetText>
          <SheetActions>
            <Button size="sm" onClick={() => setSelected(null)}>{t('关闭')}</Button>
            <Button size="sm" icon="copy" onClick={() => void copyCode(entry.code)}>{t('复制代码')}</Button>
            <GiveButton action="add_ability" params={{ rawcode: entry.code, level: '1' }} label={t('添加技能')} done={fill(t('已添加技能 {name}'), { name: entry.name })} />
          </SheetActions>
        </>,
      }}
    />
  )
}
