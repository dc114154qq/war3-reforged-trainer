import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { Button, Frost, Icon, announce } from '../../../ds'
import type { LockItem } from '../../../lib/types'
import { useCommandCard } from '../../state/commands'
import { useLocks } from '../../state/locks'
import { useSystem } from '../../state/system'
import { useT } from '../../i18n'
import { Hint, PageBody, Section, usePending } from '../common/Layout'
import s from './LocksPage.module.css'

const REFRESH_MS = 2500

/** The frozen roll: every value the backend keeps re-applying, each ready to thaw. */
export default function LocksPage() {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const items = useLocks(st => st.items)
  const { pending, run } = usePending()
  // Ids being thawed: the frost cracks first, then the row leaves.
  const [thawing, setThawing] = useState<Set<string>>(new Set())

  // Locks are added from other pages and from hotkeys; keep the roll current while it is open.
  useEffect(() => {
    void useLocks.getState().reload()
    const timer = window.setInterval(() => void useLocks.getState().reload(), REFRESH_MS)
    return () => window.clearInterval(timer)
  }, [])

  const thaw = (lock: LockItem) => {
    if (thawing.has(lock._iid)) return
    setThawing(prev => new Set(prev).add(lock._iid))
    window.setTimeout(async () => {
      if (await useLocks.getState().remove(lock._iid)) announce(t('已解除锁定'))
      setThawing(prev => { const next = new Set(prev); next.delete(lock._iid); return next })
    }, 420)
  }

  const applyOnce = () => run('apply', async () => {
    const message = await useLocks.getState().applyOnce()
    if (message !== null) announce(t(message || '锁定项已执行一次'))
  })

  useCommandCard([
    { key: 'Q', icon: 'refresh', title: t('刷新'), description: t('重新读取锁定列表。'), pending: pending.refresh, estimateMs: 300, onPress: () => void run('refresh', () => useLocks.getState().reload()) },
    { key: 'W', icon: 'write', title: t('全部单次写入'), description: t('立刻把所有锁定值写进游戏一次，不等定时写入。'), pending: pending.apply, estimateMs: 600, disabled: !connected || !items.length, onPress: () => void applyOnce() },
  ])

  return (
    <PageBody>
      <Section
        title={`${t('冰封名录')}（${items.length}）`}
        actions={<>
          <Button size="sm" icon="refresh" disabled={pending.refresh} onClick={() => void run('refresh', () => useLocks.getState().reload())}>{t('刷新')}</Button>
          <Button variant="cast" size="sm" disabled={!connected || !items.length || pending.apply} onClick={() => void applyOnce()}>{t('全部单次写入')}</Button>
        </>}
      >
        <Hint>{t('修改器会定时把这些值写回游戏。解冻后不再守护，游戏里的数值会照常变化。')}</Hint>
        {items.length === 0 ? (
          <p className={s.empty}>{t('还没有锁定任何值。在“选中单位”或“玩家资源”里点锁定按钮添加。')}</p>
        ) : (
          <ul className={s.roll} aria-label={t('锁定列表')}>
            <AnimatePresence initial={false}>
              {items.map(lock => (
                <motion.li
                  key={lock._iid}
                  className={s.item}
                  layout
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, height: 0, transition: { duration: 0.2 } }}
                >
                  <span className={s.scope}>{t(lock.scope)}</span>
                  <span className={s.label}>{t(lock.label)}</span>
                  <span className={s.value}>
                    <span className={s.valueText}>{lock.value}</span>
                    <Frost locked={!thawing.has(lock._iid)} />
                  </span>
                  <Button size="sm" disabled={thawing.has(lock._iid)} onClick={() => thaw(lock)}>
                    <Icon name="lock" tone="frost" /> {t('解冻')}
                  </Button>
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        )}
      </Section>
    </PageBody>
  )
}
