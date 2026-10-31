import { useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { EditableNumber, Icon, SPRING, Tooltip, bounty, type BountyTone, type IconName, type IconTone } from '../../ds'
import { CHAPTERS, chapterOf } from '../routes'
import { useNav } from '../state/nav'
import { num, useResources, type SetKind } from '../state/resources'
import { useSystem } from '../state/system'
import { useUnit } from '../state/unit'
import { useT } from '../i18n'
import { DayNightClock } from './DayNightClock'
import { SystemMenu } from './SystemMenu'
import s from './TopBand.module.css'

export function TopBand() {
  const t = useT()
  const page = useNav(st => st.page)
  const setChapter = useNav(st => st.setChapter)
  const current = chapterOf(page)
  const [menu, setMenu] = useState(false)

  return (
    <header className={`ds-metal ${s.band}`} data-testid="top-band">
      <nav className={s.chapters} aria-label={t('章节')}>
        {CHAPTERS.map((c, i) => (
          <button
            key={c.id}
            type="button"
            className={s.chapter}
            data-active={c.id === current.id || undefined}
            aria-current={c.id === current.id ? 'page' : undefined}
            data-testid={`chapter-${c.id}`}
            title={`Alt+${i + 1}`}
            onClick={() => setChapter(c.id)}
          >
            {t(c.label)}
            {c.id === current.id && <motion.span layoutId="chapter-mark" className={s.mark} transition={SPRING.layout} />}
          </button>
        ))}
      </nav>

      <div className={s.compact}>
        <button type="button" className={s.chapter} data-active aria-expanded={menu} onClick={() => setMenu(m => !m)}>
          {t(current.label)}
          <svg className={s.caret} viewBox="0 0 10 6" aria-hidden="true"><path d="M1 1l4 4 4-4" /></svg>
        </button>
        <AnimatePresence>
          {menu && (
            <motion.ul
              className={`ds-frame-ornate ${s.menu}`}
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -4 }}
              transition={{ duration: 0.14 }}
            >
              {CHAPTERS.map(c => (
                <li key={c.id}>
                  <button type="button" data-active={c.id === current.id || undefined} onClick={() => { setChapter(c.id); setMenu(false) }}>
                    {t(c.label)}
                  </button>
                </li>
              ))}
            </motion.ul>
          )}
        </AnimatePresence>
      </div>

      <DayNightClock />

      <div className={s.right}>
        <Resources />
        <HotkeySwitch />
        <ReadAllButton />
        <SystemMenu />
      </div>
    </header>
  )
}

function upkeep(food: number) {
  if (food <= 50) return { text: '无维护费', className: s.upkeepNone }
  if (food <= 80) return { text: '低维护费', className: s.upkeepLow }
  return { text: '高维护费', className: s.upkeepHigh }
}

const TONE: Record<SetKind, BountyTone> = { gold: 'gold', lumber: 'lumber', food_used: 'plain', food_cap: 'plain' }

/** Gold, lumber and food, where the game shows them. Click a number to set it. */
function Resources() {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const current = useResources(st => st.snapshot?.current)
  const setResource = useResources(st => st.set)
  const values: Record<SetKind, number | null> = {
    gold: num(current?.gold),
    lumber: num(current?.lumber),
    food_used: num(current?.food),
    food_cap: num(current?.foodCap),
  }

  const commit = async (kind: SetKind, value: number, rect: DOMRect | null) => {
    const before = values[kind]
    const after = await setResource(kind, String(Math.round(value)))
    if (!after || before === null) return
    const now = num(kind === 'gold' ? after.current.gold : kind === 'lumber' ? after.current.lumber : kind === 'food_used' ? after.current.food : after.current.foodCap)
    if (now === null || now === before) return
    bounty({ anchor: rect, text: `${now > before ? '+' : '−'}${Math.abs(now - before)}`, tone: TONE[kind], from: 'below' })
  }

  const value = (kind: SetKind, label: string) => {
    const v = values[kind]
    if (!connected || v === null) return <span className={s.none} aria-label={`${t(label)} —`}>—</span>
    return (
      <span data-res={kind}>
        <EditableNumber text={String(v)} label={t(label)} onCommit={(n, rect) => void commit(kind, n, rect)} />
      </span>
    )
  }

  const fee = values.food_used === null ? null : upkeep(values.food_used)

  return (
    <div className={s.resources}>
      <Counter icon="gold" tone="gold" label={t('金币')}>{value('gold', '金币')}</Counter>
      <Counter icon="lumber" tone="lumber" label={t('木材')}>{value('lumber', '木材')}</Counter>
      <Counter icon="food" tone="wheat" label={t('人口')}>
        {value('food_used', '已用人口')}
        <span className={s.slash}>/</span>
        {value('food_cap', '人口上限')}
        {connected && fee && <span className={`${s.upkeep} ${fee.className}`}>{t(fee.text)}</span>}
      </Counter>
    </div>
  )
}

function Counter({ icon, tone, label, children }: { icon: IconName; tone: IconTone; label: string; children: ReactNode }) {
  return (
    <div className={s.counter} role="group" aria-label={label}>
      <Icon name={icon} tone={tone} className={s.resIcon} />
      <span className={s.amount}>{children}</span>
    </div>
  )
}

/** The global hotkey switch stays in sight: it decides whether keys work inside the game. */
function HotkeySwitch() {
  const t = useT()
  const enabled = useSystem(st => st.status.hotkeysEnabled)
  const bridgeReady = useSystem(st => st.bridgeReady)
  const setEnabled = useSystem(st => st.setHotkeysEnabled)
  return (
    <Tooltip title={enabled ? t('全局快捷键：已开启') : t('全局快捷键：已关闭')}>
      {/* A labelled lamp rather than an icon: at band size no glyph reads as "hotkeys". */}
      <button
        type="button"
        className={s.hotkeys}
        aria-pressed={enabled}
        aria-label={enabled ? t('全局快捷键：已开启') : t('全局快捷键：已关闭')}
        disabled={!bridgeReady}
        data-testid="hotkeys-switch"
        onClick={() => void setEnabled(!enabled)}
      >
        <span className={s.lamp} aria-hidden="true" />
        <span className={s.hotkeyText}><span>{t('全局快捷键')}</span><strong>{enabled ? t('已开启') : t('已关闭')}</strong></span>
      </button>
    </Tooltip>
  )
}

function ReadAllButton() {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const reading = useUnit(st => st.reading)
  const readAll = useUnit(st => st.readAll)
  return (
    <Tooltip title={t('读取游戏里当前选中的全部单位，刷新操作台和候选列表。游戏内快捷键是 Ctrl+F11。')}>
      <button type="button" className={s.readAll} data-testid="global-read-units" disabled={!connected || reading}
        aria-busy={reading} onClick={() => void readAll()}>
        <Icon name="read" />
        <span>{reading ? t('正在读取…') : t('读取全部单位')}</span>
      </button>
    </Tooltip>
  )
}
