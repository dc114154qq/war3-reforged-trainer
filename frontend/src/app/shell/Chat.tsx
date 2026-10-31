import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { create } from 'zustand'
import { PLAYER_COLORS, announce, bounty } from '../../ds'
import { api } from '../../lib/api'
import { PAGES } from '../routes'
import { useNav } from '../state/nav'
import { num, useResources, type AddKind } from '../state/resources'
import { useSystem } from '../state/system'
import { useUnit } from '../state/unit'
import { t as tr, useT } from '../i18n'
import s from './Chat.module.css'

interface Line { id: number; text: string }
let seq = 1

export const useChat = create<{ open: boolean; log: Line[] }>(() => ({ open: false, log: [] }))
export const openChat = () => useChat.setState({ open: true })
const closeChat = () => useChat.setState({ open: false })

/**
 * A typed command. Names describe what the trainer itself does (it writes game memory);
 * they deliberately avoid the game's own cheat codes, which work differently.
 */
interface Command {
  name: string
  /** Takes a number after the name, e.g. "加金币 5000". */
  takesAmount?: boolean
  desc: string
  run(amount: number | null): Promise<void> | void
}

/** Add to gold, lumber or both and float each change into its counter. */
async function addResources(kind: AddKind, amount: number | null, done: string) {
  // Without a number, use the step set on the resources page, as its +/- buttons do.
  const delta = amount === null ? useResources.getState().snapshot?.delta || '1000' : String(Math.round(amount))
  const before = useResources.getState().snapshot?.current
  const after = await useResources.getState().add(kind, delta)
  if (!after) return
  for (const key of ['gold', 'lumber'] as const) {
    const was = num(before?.[key]), now = num(after.current[key])
    if (was === null || now === null || was === now) continue
    bounty({ anchor: document.querySelector(`[data-res="${key}"]`), text: `${now > was ? '+' : '−'}${Math.abs(now - was)}`, tone: key, from: 'below' })
  }
  announce(tr(done))
}

async function elephant(action: string, done: string) {
  try {
    const result = await api.executeElephantAction(action)
    if (result?.success) announce(tr(done))
  } catch { /* reported by callApi */ }
}

const COMMANDS: Command[] = [
  { name: '加金币', takesAmount: true, desc: '金币加上这个数；不写数时用玩家资源页的增量', run: n => addResources('gold', n, '金币已修改') },
  { name: '加木材', takesAmount: true, desc: '木材加上这个数；不写数时用玩家资源页的增量', run: n => addResources('lumber', n, '木材已修改') },
  { name: '加金木', takesAmount: true, desc: '金币和木材各加这个数', run: n => addResources('both', n, '金币和木材已修改') },
  {
    name: '人口上限', takesAmount: true, desc: '把人口上限改成这个数',
    run: async n => {
      if (n === null) return announce(tr('请在后面写上数值，例如：人口上限 300'))
      if (await useResources.getState().set('food_cap', String(Math.round(n)))) announce(tr('人口上限已修改'))
    },
  },
  { name: '显示全图', desc: '去掉地图迷雾和黑色遮罩', run: () => elephant('reveal_map', '已显示全图') },
  { name: '无敌', desc: '选中单位不再受到伤害', run: () => elephant('invulnerable', '选中单位已无敌') },
  { name: '重置冷却', desc: '立刻重置选中单位所有技能的冷却', run: () => elephant('reset_cooldown', '技能冷却已重置') },
  { name: '读取所有选中单位', desc: '命令卡 Q', run: () => useUnit.getState().readAll() },
]

/** Longest name first, so "加金木" is not read as a prefix of something shorter. */
const BY_LENGTH = [...COMMANDS].sort((a, b) => b.name.length - a.name.length)

function parseCommand(text: string): { command: Command; amount: number | null; badAmount: boolean } | null {
  const lower = text.toLowerCase()
  for (const command of BY_LENGTH) {
    for (const name of [command.name, tr(command.name)]) {
      if (!lower.startsWith(name.toLowerCase())) continue
      const rest = text.slice(name.length).trim()
      if (!rest) return { command, amount: null, badAmount: false }
      if (!command.takesAmount) continue
      const n = Number(rest.replace(/[−–]/g, '-').replace(/,/g, ''))
      return { command, amount: Number.isFinite(n) ? n : null, badAmount: !Number.isFinite(n) }
    }
  }
  return null
}

interface Suggestion { kind: '跳转' | '动作'; label: string; desc: string; takesAmount?: boolean }

const ALL: Suggestion[] = [
  ...COMMANDS.map(c => ({ kind: '动作' as const, label: c.name, desc: c.desc, takesAmount: c.takesAmount })),
  ...PAGES.map(p => ({ kind: '跳转' as const, label: p.label, desc: '' })),
]

function suggest(text: string): Suggestion[] {
  const q = text.trim().toLowerCase().split(/\s+/)[0]
  if (!q) return ALL.filter(x => x.kind === '动作').slice(0, 8)
  return ALL.filter(x => x.label.toLowerCase().includes(q) || tr(x.label).toLowerCase().includes(q)).slice(0, 8)
}

/** Execute a line typed in the chat box. */
async function execute(input: string) {
  const text = input.trim()
  closeChat()
  if (!text) return
  useChat.setState(st => ({ log: [...st.log.slice(-3), { id: seq++, text }] }))

  const parsed = parseCommand(text)
  if (parsed) {
    if (parsed.badAmount) return announce(tr('数值要写成数字，例如：加金币 5000'))
    if (!useSystem.getState().status.connected) return announce(tr('还没有连接游戏。先点上方的昼夜钟连接。'))
    return parsed.command.run(parsed.amount)
  }
  const page = PAGES.find(p => p.label === text || tr(p.label).toLowerCase() === text.toLowerCase())
    ?? PAGES.find(p => p.label.includes(text))
  if (page) return useNav.getState().setPage(page.id)
  announce(tr('没有认出这条输入。可以输入页面名或修改器指令，例如：加金币 5000'))
}

/** Enter opens it, as typing in game. Takes page names and the trainer's own commands. */
export function Chat() {
  const open = useChat(st => st.open)
  const log = useChat(st => st.log)
  return (
    <div className={s.chat}>
      <div className={s.log} aria-live="polite">
        <AnimatePresence initial={false}>
          {log.map(line => <LogLine key={line.id} line={line} />)}
        </AnimatePresence>
      </div>
      <AnimatePresence>{open && <ChatInput />}</AnimatePresence>
    </div>
  )
}

function LogLine({ line }: { line: Line }) {
  const t = useT()
  useEffect(() => {
    const timer = window.setTimeout(() => useChat.setState(st => ({ log: st.log.filter(l => l.id !== line.id) })), 7000)
    return () => window.clearTimeout(timer)
  }, [line.id])
  return (
    <motion.p className={s.line} layout initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, transition: { duration: 0.5 } }}>
      <span className={s.to}>{t('[所有人]')}</span>
      <span className={s.who} style={{ color: PLAYER_COLORS[0] }}>{t('你')}</span>：{line.text}
    </motion.p>
  )
}

function ChatInput() {
  const t = useT()
  const [text, setText] = useState('')
  const [index, setIndex] = useState(-1)
  const list = useMemo(() => suggest(text), [text])

  const choose = (item: Suggestion) => {
    // Commands that take a number wait for one: fill in the name and let the user type it.
    if (item.takesAmount && !parseCommand(text)?.amount) {
      setText(`${t(item.label)} `)
      setIndex(-1)
      return
    }
    void execute(item.takesAmount ? text : t(item.label))
  }

  const kindLabel = { 跳转: t('跳转'), 动作: t('动作') }

  return (
    <motion.div
      className={s.panel}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 4, transition: { duration: 0.1 } }}
      transition={{ duration: 0.14 }}
    >
      {list.length > 0 && (
        <ul className={s.suggest} role="listbox" aria-label={t('可以输入的内容')}>
          {list.map((item, i) => (
            <li
              key={`${item.kind}-${item.label}`}
              role="option"
              aria-selected={i === index}
              className={s.option}
              data-active={i === index || undefined}
              onMouseDown={e => { e.preventDefault(); choose(item) }}
              onMouseEnter={() => setIndex(i)}
            >
              <span className={s.kind}>{kindLabel[item.kind]}</span>
              <span className={s.label}>
                {t(item.label)}
                {item.takesAmount && <span className={s.arg}> {t('数值')}</span>}
              </span>
              <span className={s.desc}>{item.desc && t(item.desc)}</span>
            </li>
          ))}
        </ul>
      )}
      <label className={s.prompt}>
        <span className={s.to}>{t('[所有人]：')}</span>
        <input
          className={s.input}
          autoFocus
          value={text}
          spellCheck={false}
          aria-label={t('聊天框，输入页面名或修改器指令')}
          data-testid="chat-input"
          onChange={e => { setText(e.target.value); setIndex(-1) }}
          onBlur={closeChat}
          onKeyDown={e => {
            if (e.key === 'ArrowDown') { e.preventDefault(); setIndex(i => Math.min(list.length - 1, i + 1)) }
            else if (e.key === 'ArrowUp') { e.preventDefault(); setIndex(i => Math.max(-1, i - 1)) }
            else if (e.key === 'Tab' && list.length) {
              e.preventDefault()
              const item = list[Math.max(0, index)]
              setText(item.takesAmount ? `${t(item.label)} ` : t(item.label))
              setIndex(-1)
            } else if (e.key === 'Enter') {
              e.preventDefault()
              if (index >= 0 && list[index]) choose(list[index])
              else void execute(text)
            } else if (e.key === 'Escape') {
              e.preventDefault()
              closeChat()
            }
          }}
        />
      </label>
    </motion.div>
  )
}
