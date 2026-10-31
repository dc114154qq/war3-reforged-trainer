import { useState } from 'react'
import { Button, TextField, announce } from '../../../ds'
import { api } from '../../../lib/api'
import type { Equipment3Row } from '../../../lib/types'
import { useCommandCard } from '../../state/commands'
import { useSystem } from '../../state/system'
import { fill, useT } from '../../i18n'
import { DataTable } from '../common/DataTable'
import { CodexLayout, Count, GiveButton, SheetActions, SheetHead, SheetText, copyCode, useDebounced, useSearch } from './Codex'
import s from './CatalogPage.module.css'

/** The 3.0 campaign and Reforged equipment, from the official Chinese item data. */
export default function Equipment3Page() {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<string | null>(null)
  const settled = useDebounced(query)
  const { data, loading } = useSearch(() => api.search3Equipment(settled), [settled])
  const rows = data?.rows ?? []
  const entry = rows.find(r => r.code === selected) ?? null

  const create = async (row: Equipment3Row) => {
    const result = await api.executeElephantAction('add_item', { rawcode: row.code })
    if (result?.success) announce(fill(t('已创建 {name}，在选中英雄身上或脚下'), { name: row.name }))
    else window.dispatchEvent(new CustomEvent('war3-error', { detail: result?.error || '操作未完成' }))
  }

  useCommandCard([
    { key: 'Q', icon: 'copy', title: t('复制代码'), description: t('复制选中装备的四字符代码。'), disabled: !entry, onPress: () => entry && void copyCode(entry.code) },
    { key: 'W', icon: 'add-item', title: t('创建装备'), description: t('给选中英雄创建这件装备；物品栏满时放在脚下。'), disabled: !entry || !connected, onPress: () => entry && void create(entry) },
  ])

  return (
    <CodexLayout
      toolbar={<>
        <TextField
          variant="search"
          className={s.search}
          aria-label={t('搜索装备')}
          placeholder={t('装备名称、代码或效果，例如“霜之哀伤”')}
          value={query}
          onChange={e => setQuery(e.target.value)}
        />
        <Count match={data?.matchCount ?? 0} total={data?.totalCount ?? 0} shown={rows.length} loading={loading} />
      </>}
      list={
        <DataTable<Equipment3Row>
          label={t('3.0 装备')}
          fill
          rows={rows}
          rowKey={r => r.code}
          selected={selected}
          onSelect={r => setSelected(r.code)}
          empty={loading ? t('正在检索…') : t('没有匹配的 3.0 装备。清空搜索可以看到全部装备。')}
          columns={[
            { key: 'code', label: t('代码'), width: '72px', mono: true },
            { key: 'name', label: t('装备名称'), width: 'minmax(150px, 1fr)', render: r => <span className={s.name}>{r.name}</span> },
            { key: 'description', label: t('属性与效果'), width: 'minmax(0, 2.2fr)', render: r => <span className={s.desc}>{r.description}</span> },
          ]}
        />
      }
      footer={t('来源：Warcraft III 3.0.1.24360 官方中文装备资料。地图可能改动同一代码的效果；创建装备需要当前地图里有这个物品的定义。')}
      sheet={entry && {
        key: entry.code,
        content: <>
          <SheetHead code={entry.code} name={entry.name} />
          <SheetText><p>{entry.description || t('没有特殊被动描述。')}</p></SheetText>
          <SheetActions>
            <Button size="sm" onClick={() => setSelected(null)}>{t('关闭')}</Button>
            <Button size="sm" icon="copy" onClick={() => void copyCode(entry.code)}>{t('复制代码')}</Button>
            <GiveButton action="add_item" params={{ rawcode: entry.code }} label={t('创建装备')} done={fill(t('已创建 {name}，在选中英雄身上或脚下'), { name: entry.name })} />
          </SheetActions>
        </>,
      }}
    />
  )
}
