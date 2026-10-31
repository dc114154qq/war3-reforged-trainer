import { useState } from 'react'
import { Button, EditableNumber, Frost, Icon, RollingNumber, StatBar, XpBar, announce, bounty, cx } from '../ds'
import { Demo, Section } from './Section'
import s from './sg.module.css'

interface Row { key: string; name: string; en: string; value: number; locked: boolean; pulse: number }

const fmt = (n: number) => String(Number(n.toFixed(2)))
const delta = (n: number) => `${n < 0 ? '−' : '+'}${fmt(Math.abs(n))}`

function Ledger() {
  const [rows, setRows] = useState<Row[]>([
    { key: 'str', name: '力量', en: 'Strength', value: 48, locked: false, pulse: 0 },
    { key: 'speed', name: '移动速度', en: 'Move Speed', value: 320, locked: true, pulse: 0 },
    { key: 'hp', name: '当前生命', en: 'Life', value: 1250, locked: false, pulse: 0 },
  ])
  const update = (key: string, fn: (r: Row) => Row) => setRows(rs => rs.map(r => (r.key === key ? fn(r) : r)))

  // What polling would show: the game moves unlocked values; locked ones get pulled back and flash.
  const gameTick = () => setRows(rs => rs.map(r => {
    if (r.locked) return { ...r, pulse: r.pulse + 1 }
    return { ...r, value: Math.max(1, Math.round(r.value + (Math.random() * 2 - 1) * r.value * 0.2)) }
  }))

  return (
    <>
      <div className={s.ledger} role="table" aria-label="字段示例">
        {rows.map(r => (
          <div key={r.key} role="row" className={cx(s.ledgerRow, r.locked && s.locked)}>
            <span role="cell" className={s.ledgerName}>{r.name}<span className={s.dim}>{r.en}</span></span>
            <span role="cell" className={s.ledgerValue}>
              <EditableNumber
                className={s.fill}
                text={fmt(r.value)}
                label={r.name}
                onInvalid={() => announce('写入失败：请输入数字。')}
                onCommit={(v, rect) => {
                  if (v !== r.value) bounty({ anchor: rect, text: delta(v - r.value) })
                  update(r.key, x => ({ ...x, value: v }))
                }}
              >
                <Frost locked={r.locked} pulse={r.pulse} />
              </EditableNumber>
            </span>
            <span role="cell">
              <button
                type="button"
                className={s.lock}
                aria-pressed={r.locked}
                aria-label={r.locked ? `解锁${r.name}` : `锁定${r.name}`}
                onClick={() => update(r.key, x => ({ ...x, locked: !x.locked }))}
              >
                <Icon name="lock" tone={r.locked ? 'frost' : 'muted'} />
              </button>
            </span>
          </div>
        ))}
      </div>
      <div className={s.row}>
        <Button size="sm" icon="refresh" onClick={gameTick}>模拟游戏改值</Button>
        <span className={s.dim}>点数值修改，回车写入；点雪花锁定或解锁。</span>
      </div>
    </>
  )
}

export function Values() {
  const [roll, setRoll] = useState(18500)
  const [life, setLife] = useState(1250)
  const [mana, setMana] = useState(420)
  const [frozen, setFrozen] = useState(false)

  return (
    <Section id="values" title="数值与状态条" lead="数字会滚动，写入成功飘字，锁定就冻住。血条掉血时先留一段浅色残影再追上。">
      <div className={s.demoGrid}>
        <Demo title="滚动数字" note="每一位单独滚到新值，右边的先动。">
          <div className={s.row}>
            <span className={s.bigNumber}><RollingNumber text={String(roll)} /></span>
            <Button size="sm" onClick={() => setRoll(Math.round(Math.random() * 99999))}>换一个数</Button>
          </div>
        </Demo>
        <Demo title="字段：修改、飘字、冰封" wide>
          <Ledger />
        </Demo>
        <Demo title="生命与魔法" wide>
          <div className={s.bars}>
            <StatBar kind="life" value={life} max={1250} frozen={frozen} />
            <StatBar kind="mana" value={mana} max={600} />
            <XpBar xp={4120} floor={3500} next={4400} />
          </div>
          <div className={s.row}>
            <Button size="sm" onClick={() => !frozen && setLife(v => Math.max(1, v - 180 - Math.round(Math.random() * 120)))}>受到伤害</Button>
            <Button size="sm" onClick={() => setLife(v => Math.min(1250, v + 260))}>治疗</Button>
            <Button size="sm" onClick={() => setMana(v => (v >= 600 ? 120 : Math.min(600, v + 160)))}>回魔</Button>
            <Button size="sm" icon="lock" onClick={() => setFrozen(f => !f)}>{frozen ? '解锁生命' : '锁定生命'}</Button>
          </div>
        </Demo>
      </div>
    </Section>
  )
}
