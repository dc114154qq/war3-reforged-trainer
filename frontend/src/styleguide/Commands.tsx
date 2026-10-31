import { useRef, useState } from 'react'
import { CommandCard, StatBar, Icon, announce, type CommandSpec, type GridKey, type IconName } from '../ds'
import { Section } from './Section'
import s from './sg.module.css'

interface Def { key: GridKey; icon: IconName; title: string; description: string; estimateMs?: number; toggle?: boolean; done?: string }

const DEFS: Def[] = [
  { key: 'Q', icon: 'read', title: '读取选中单位', description: '从游戏里重新读取当前选中的单位。', estimateMs: 900 },
  { key: 'W', icon: 'write', title: '写入字段', description: '把选中字段的新值写回游戏。', estimateMs: 500 },
  { key: 'E', icon: 'refresh', title: '刷新字段表', description: '重新读取全部字段，不切换单位。', estimateMs: 800 },
  { key: 'R', icon: 'lock', title: '锁定字段', description: '冻住选中字段的值。', estimateMs: 300 },
  { key: 'A', icon: 'candidates', title: '读取候选单位', description: '读取同时选中的所有单位。', estimateMs: 1100 },
  { key: 'S', icon: 'locate', title: 'Native 定位', description: '用游戏内部函数重新定位单位地址。这次故意比预估慢，看转圈停在九成处等结果。', estimateMs: 700 },
  { key: 'D', icon: 'invulnerable', title: '无敌', description: '选中单位不再受到伤害。再按一次关闭。', estimateMs: 500, toggle: true },
  { key: 'F', icon: 'reset-cooldown', title: '重置冷却', description: '立刻重置所有技能冷却。', estimateMs: 600, done: '技能冷却已重置' },
  { key: 'Z', icon: 'copy', title: '复制地址', description: '把选中字段的地址复制到剪贴板。', estimateMs: 200, done: '已复制地址 0x24A8F120' },
  { key: 'X', icon: 'cancel', title: '取消定位', description: '放开当前定位的单位。', estimateMs: 400, done: '已取消定位' },
]

// Simulated backend: most calls land near the estimate; S deliberately runs long.
const actualDuration = (d: Def) => (d.key === 'S' ? 2600 : (d.estimateMs ?? 800) * (0.7 + Math.random() * 0.5))

export function Commands() {
  const [pending, setPending] = useState<Partial<Record<GridKey, boolean>>>({})
  const [active, setActive] = useState(false)
  const activeRef = useRef(false)
  const timers = useRef<number[]>([])

  const commands: CommandSpec[] = DEFS.map(d => ({
    key: d.key,
    icon: d.icon,
    title: d.title,
    description: d.description,
    estimateMs: d.estimateMs,
    pending: pending[d.key],
    active: d.toggle ? active : undefined,
    onPress: () => {
      setPending(p => ({ ...p, [d.key]: true }))
      timers.current.push(window.setTimeout(() => {
        setPending(p => ({ ...p, [d.key]: false }))
        if (d.toggle) {
          activeRef.current = !activeRef.current
          setActive(activeRef.current)
          announce(activeRef.current ? '阿尔萨斯王子已无敌' : '已取消无敌')
        } else if (d.done) announce(d.done)
      }, actualDuration(d)))
    },
  }))

  return (
    <Section
      id="commands"
      title="命令卡"
      lead="4×3 网格，热键 Q W E R / A S D F / Z X C V。调用进行中显示冷却转圈：按预估时间转到九成，等结果回来再补完一圈并闪一下边。"
    >
      <div className={`ds-metal ds-rim-top ${s.consoleDemo}`}>
        <div className={s.consoleInfo}>
          <span className={s.consoleName}><Icon name="unit-hero" /> 阿尔萨斯王子</span>
          <StatBar kind="life" value={1250} max={1250} />
          <StatBar kind="mana" value={600} max={600} />
          <p className={s.dim}>在页面空白处直接按热键，或者点按钮。鼠标停在按钮上看提示框。</p>
        </div>
        <CommandCard commands={commands} />
      </div>
    </Section>
  )
}
