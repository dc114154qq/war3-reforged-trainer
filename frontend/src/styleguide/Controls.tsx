import { useState } from 'react'
import { Button, Checkbox, GroupHeader, Keycap, PillGroup, PlayerSwatch, RawcodePlate, TextField, Tooltip } from '../ds'
import { Demo, Section } from './Section'
import s from './sg.module.css'

type Filter = 'all' | 'base' | 'hero' | 'combat' | 'locked'

export function Controls() {
  const [filter, setFilter] = useState<Filter>('all')
  const [query, setQuery] = useState('')
  const [checks, setChecks] = useState({ hotkeys: true, sound: false })

  return (
    <Section id="controls" title="按钮与输入" lead="铸铜按钮是唯一的实心按钮，每个视图最多一个；其余用黑铁。危险操作用血色，并配合长按确认。">
      <div className={s.demoGrid}>
        <Demo title="按钮" wide>
          <div className={s.row}>
            <Button variant="cast" size="lg">连接游戏</Button>
            <Button variant="cast">写入选中单位</Button>
            <Button icon="refresh">刷新字段表</Button>
            <Button icon="copy" size="sm">复制地址</Button>
            <Button variant="danger" icon="kill">杀死单位</Button>
            <Button disabled>不可用</Button>
          </div>
        </Demo>
        <Demo title="筛选药丸" note="方向键切换，取自炉石卡牌库的筛选条。" wide>
          <PillGroup<Filter>
            label="按分类筛选"
            value={filter}
            onChange={setFilter}
            options={[
              { value: 'all', label: '全部', count: 21 },
              { value: 'base', label: '基础', count: 6 },
              { value: 'hero', label: '英雄', count: 5 },
              { value: 'combat', label: '战斗', count: 8 },
              { value: 'locked', label: '已锁定', count: 2 },
            ]}
          />
        </Demo>
        <Demo title="输入框">
          <div className={s.row}>
            <TextField variant="search" aria-label="搜索字段" placeholder="搜字段名、地址或说明" value={query} onChange={e => setQuery(e.target.value)} />
            <TextField label="英雄等级" defaultValue="10" suffix="级" inputMode="numeric" className={s.narrow} />
          </div>
        </Demo>
        <Demo title="勾选框">
          <div className={s.column}>
            <Checkbox label="启用全局快捷键" checked={checks.hotkeys} onChange={e => setChecks(c => ({ ...c, hotkeys: e.target.checked }))} />
            <Checkbox label="操作音效" checked={checks.sound} onChange={e => setChecks(c => ({ ...c, sound: e.target.checked }))} />
            <Checkbox label="需要连接游戏" disabled />
          </div>
        </Demo>
        <Demo title="小部件">
          <div className={s.column}>
            <span className={s.row}><Keycap>W</Keycap>修改<Keycap>R</Keycap>锁定<Keycap>Z</Keycap>复制地址</span>
            <span className={s.row}><RawcodePlate code="Hart" /><RawcodePlate code="AHbz" /><PlayerSwatch slot={0} withLabel /><PlayerSwatch slot={1} withLabel /></span>
          </div>
        </Demo>
        <Demo title="分组标题">
          <GroupHeader>基础</GroupHeader>
          <GroupHeader>3.0 属性</GroupHeader>
        </Demo>
        <Demo title="悬停提示" note="任意元素都能挂；命令卡用固定位置的提示。">
          <div className={s.row}>
            <Tooltip title="Native 定位" hotkey="S" body="用游戏内部函数重新定位单位地址。读出来的数不对时再用。">
              <Button icon="locate">把鼠标放上来</Button>
            </Tooltip>
          </div>
        </Demo>
      </div>
    </Section>
  )
}
