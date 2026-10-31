import { useRef, useState } from 'react'
import {
  Button, FogReveal, HoldToConfirm, Icon, PillGroup, RollingNumber, SelectionRing, announce, bounty,
  type IconName, type Relation,
} from '../ds'
import { Demo, Section } from './Section'
import s from './sg.module.css'

const UNITS: { id: string; icon: IconName; name: string }[] = [
  { id: 'hero', icon: 'unit-hero', name: '阿尔萨斯王子' },
  { id: 'melee', icon: 'unit-melee', name: '步兵' },
  { id: 'air', icon: 'unit-air', name: '狮鹫骑士' },
]

function Selection() {
  const [selected, setSelected] = useState('hero')
  const [hover, setHover] = useState<string | null>(null)
  const [relation, setRelation] = useState<Relation>('ally')
  return (
    <>
      <div className={s.cands}>
        {UNITS.map(u => (
          <button
            key={u.id}
            type="button"
            className={s.cand}
            aria-pressed={u.id === selected}
            title={u.name}
            onClick={() => setSelected(u.id)}
            onPointerEnter={() => setHover(u.id)}
            onPointerLeave={() => setHover(null)}
          >
            <SelectionRing className={s.ring} relation={relation} state={u.id === selected ? 'selected' : u.id === hover ? 'hover' : 'none'} />
            <span className={s.portrait}><Icon name={u.icon} /></span>
          </button>
        ))}
      </div>
      <PillGroup<Relation>
        label="阵营"
        value={relation}
        onChange={setRelation}
        options={[{ value: 'ally', label: '友方' }, { value: 'neutral', label: '中立' }, { value: 'enemy', label: '敌方' }]}
      />
    </>
  )
}

function Treasury() {
  const [gold, setGold] = useState(18500)
  const [lumber, setLumber] = useState(9200)
  const goldRef = useRef<HTMLSpanElement>(null)
  const lumberRef = useRef<HTMLSpanElement>(null)
  return (
    <>
      <div className={`ds-metal ${s.treasury}`}>
        <span className={s.counter}><Icon name="gold" tone="gold" /><span ref={goldRef} className={s.counterValue}><RollingNumber text={String(gold)} /></span></span>
        <span className={s.counter}><Icon name="lumber" tone="lumber" /><span ref={lumberRef} className={s.counterValue}><RollingNumber text={String(lumber)} /></span></span>
      </div>
      <div className={s.row}>
        <Button size="sm" onClick={() => { setGold(g => g + 500); bounty({ anchor: goldRef.current, text: '+500', tone: 'gold', from: 'below' }) }}>金币 +500</Button>
        <Button size="sm" onClick={() => { setLumber(l => l + 200); bounty({ anchor: lumberRef.current, text: '+200', tone: 'lumber', from: 'below' }) }}>木材 +200</Button>
      </div>
    </>
  )
}

function Fog() {
  const [revealed, setRevealed] = useState(false)
  const [busy, setBusy] = useState(false)
  return (
    <div className={s.fogBox}>
      <div className={s.fogContent}>
        <span className={s.fogTitle}>选中单位</span>
        <span className={s.dim}>迷雾后面是已连接时的界面。</span>
      </div>
      <FogReveal revealed={revealed} onRevealed={() => setBusy(false)}>
        <div className={s.fogCard}>
          <span className={s.fogTitle}>等待魔兽争霸 III</span>
          <Button
            variant="cast"
            disabled={busy}
            onClick={() => { setBusy(true); window.setTimeout(() => setRevealed(true), 700) }}
          >
            {busy ? '正在连接' : '连接游戏'}
          </Button>
        </div>
      </FogReveal>
      {revealed && (
        <Button size="sm" className={s.fogReset} onClick={() => setRevealed(false)}>断开</Button>
      )}
    </div>
  )
}

export function Motion() {
  return (
    <Section id="motion" title="动效" lead="动画只回应操作，并说明刚刚发生了什么。唯一不由点击直接触发的是连接时的迷雾散开，每次连接只播一次。">
      <div className={s.demoGrid}>
        <Demo title="选择圈" note="选中时绿色分段圈弹出，悬停是细黄圈；阵营决定颜色。">
          <Selection />
        </Demo>
        <Demo title="资源飘字" note="顶带的计数器：飘字从下方升进计数器。">
          <Treasury />
        </Demo>
        <Demo title="黄字提示" note="简短结果和失败原因；要解释或要决定的事用对话框。">
          <div className={s.row}>
            <Button size="sm" onClick={() => announce('写入失败：没有选中单位。先在游戏里点选一个单位。')}>显示一条</Button>
          </div>
        </Demo>
        <Demo title="长按确认" note="危险操作不弹窗，按住 0.6 秒外圈填满才执行；松手太早会提示。">
          <div className={s.row}>
            <HoldToConfirm icon="end-game" onConfirm={() => announce('已强制结束对局')}>强制结束对局</HoldToConfirm>
          </div>
        </Demo>
        <Demo title="迷雾散开" note="连接游戏时，迷雾从昼夜钟的位置向外散开。" wide>
          <Fog />
        </Demo>
      </div>
    </Section>
  )
}
