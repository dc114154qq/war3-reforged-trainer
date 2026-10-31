import { AnimatePresence, motion } from 'motion/react'
import { Button, CommandCard, FogReveal, Icon, RawcodePlate, StatBar, type CommandSpec } from '../../ds'
import { useCommands } from '../state/commands'
import { num } from '../state/resources'
import { useSystem } from '../state/system'
import { rawcodeOf, useUnit } from '../state/unit'
import { useT } from '../i18n'
import s from './Console.module.css'

/** Hero type ids start with a capital letter in Warcraft III (Hpal, Obla, Ulic, Edem). */
const isHeroCode = (code: string) => /^[A-Z]/.test(code)

/**
 * The bottom console, present on every page: portrait, life and mana, the command card.
 * The unit area is under fog until the game connects (the fog clearing is the app's one
 * orchestrated moment); the command card stays usable, since several pages work offline.
 */
export function Console() {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const connectedAt = useSystem(st => st.connectedAt)
  const reading = useUnit(st => st.reading)
  const readAll = useUnit(st => st.readAll)
  const pageCommands = useCommands(st => st.page)
  // Right after connecting, the console fills in as the fog clears; later renders are instant.
  const fresh = performance.now() - connectedAt < 1500

  const defaults: CommandSpec[] = [{
    key: 'Q',
    icon: 'read',
    title: t('读取所有选中单位'),
    description: t('读取游戏里当前选中的全部单位，刷新操作台和候选列表。游戏内快捷键是 Ctrl+F11。'),
    pending: reading,
    estimateMs: 900,
    disabled: !connected,
    onPress: () => void readAll(),
  }]
  const taken = new Set(pageCommands.map(c => c.key))
  const commands = [...pageCommands, ...defaults.filter(c => !taken.has(c.key))]

  return (
    <footer className={`ds-metal ds-rim-top ${s.console}`} data-testid="console">
      <div className={s.unitArea}>
        <Portrait fresh={fresh} />
        <section className={s.info} aria-label={t('单位信息')}>
          <UnitInfo fresh={fresh} />
        </section>
        <FogReveal revealed={connected} origin={{ x: 0.62, y: 0 }}>
          <Waiting />
        </FogReveal>
      </div>
      <div className={s.card}>
        <CommandCard commands={commands} entrance={fresh} label={t('命令卡')} />
      </div>
    </footer>
  )
}

function Portrait({ fresh }: { fresh: boolean }) {
  const unit = useUnit(st => st.unit)
  const code = rawcodeOf(unit?.unitTypeId)
  return (
    <section className={s.portraitArea}>
      <div className={`ds-frame-ornate ${s.frame}`}>
        {unit?.hasSelection && code && (
          <motion.div
            className={s.stage}
            initial={fresh ? { opacity: 0 } : false}
            animate={{ opacity: 1 }}
            transition={{ delay: fresh ? 0.38 : 0, duration: 0.35 }}
          >
            <AnimatePresence initial={false} mode="popLayout">
              <motion.div
                key={code}
                className={s.portrait}
                initial={{ opacity: 0, scale: 0.86 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 1.08 }}
                transition={{ duration: 0.2 }}
              >
                <Icon name={isHeroCode(code) ? 'unit-hero' : 'unit-melee'} className={s.portraitIcon} />
              </motion.div>
            </AnimatePresence>
          </motion.div>
        )}
      </div>
    </section>
  )
}

function UnitInfo({ fresh }: { fresh: boolean }) {
  const t = useT()
  const unit = useUnit(st => st.unit)
  const names = useUnit(st => st.names)
  const language = useSystem(st => st.status.language)
  const statusMessage = useSystem(st => st.status.statusMessage)
  const code = rawcodeOf(unit?.unitTypeId)

  if (!unit?.hasSelection || !code) {
    return (
      <div className={s.infoInner}>
        <p className={s.empty}>{t('还没有读取单位。在游戏里选中单位后按 Q。')}</p>
        <p className={s.status}>{t(statusMessage)}</p>
      </div>
    )
  }

  const name = names[code]
  const display = (language === 'en' ? name?.en : name?.zh) || name?.zh || code
  const hp = num(unit.hp.current) ?? 0
  const hpMax = num(unit.hp.max) ?? 0
  const mp = num(unit.mp.current) ?? 0
  const mpMax = num(unit.mp.max) ?? 0
  const x = num(unit.position.xCurrent)
  const y = num(unit.position.yCurrent)

  return (
    <motion.div
      className={s.infoInner}
      initial={fresh ? { opacity: 0, y: 6 } : false}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: fresh ? 0.44 : 0, duration: 0.35 }}
    >
      <div className={s.nameRow}>
        <span className={s.unitName}>{display}</span>
        <RawcodePlate code={code} />
      </div>
      <StatBar kind="life" value={hp} max={hpMax} label={t('生命')} />
      {mpMax > 0 && <StatBar kind="mana" value={mp} max={mpMax} label={t('魔法')} />}
      <p className={s.position}>
        {x !== null && y !== null && <>{t('坐标')} <span className={s.coord}>{x.toFixed(1)}, {y.toFixed(1)}</span></>}
        <span className={s.status}>{t(statusMessage)}</span>
      </p>
    </motion.div>
  )
}

function Waiting() {
  const t = useT()
  const statusMessage = useSystem(st => st.status.statusMessage)
  const bridgeReady = useSystem(st => st.bridgeReady)
  const connecting = useSystem(st => st.connecting)
  const connect = useSystem(st => st.connect)
  return (
    <div className={s.waiting}>
      <div className={s.waitingText}>
        <p className={s.waitingTitle}>{t('等待魔兽争霸 III')}</p>
        <p className={s.waitingStatus}>{t(statusMessage) || t('进入地图、选中一个单位后连接。')}</p>
      </div>
      <Button variant="cast" disabled={!bridgeReady || connecting} onClick={() => void connect()} data-testid="connect">
        {connecting ? t('正在连接') : t('连接游戏')}
      </Button>
      <p className={s.credits}>{t('大象功能灵感来源于经典版大象修改器，本软件完全免费，谨防倒卖')}</p>
    </div>
  )
}
