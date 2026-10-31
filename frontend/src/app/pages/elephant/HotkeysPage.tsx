import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { Button, Checkbox, Keycap, PillGroup, TextField, announce } from '../../../ds'
import { api } from '../../../lib/api'
import type { HotkeyItem } from '../../../lib/types'
import { useCommandCard } from '../../state/commands'
import { useSystem } from '../../state/system'
import { fill, useT } from '../../i18n'
import { usePending } from '../common/Layout'
import s from './HotkeysPage.module.css'

type Category = 'all' | HotkeyItem['category']
const CATEGORIES: { value: Category; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'stats', label: '属性增强' },
  { value: 'combat', label: '单位与战斗' },
  { value: 'fullscreen', label: '全屏特效' },
  { value: 'world', label: '地图与世界' },
  { value: 'general', label: '技能与物品' },
]

export default function HotkeysPage() {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const hotkeysOn = useSystem(st => st.status.hotkeysEnabled)
  const { pending, run } = usePending()
  const [hotkeys, setHotkeys] = useState<HotkeyItem[]>([])
  const [category, setCategory] = useState<Category>('all')
  const [query, setQuery] = useState('')
  const [artifacts, setArtifacts] = useState<string[]>([])

  const load = useCallback(async () => {
    try {
      setHotkeys(await api.getAllHotkeys())
      setArtifacts((await api.getArtifactPlan()).codes)
    } catch {
      // reported by callApi
    }
  }, [])

  useEffect(() => {
    void load()
    // Parameters changed elsewhere (the Elephant page, a hotkey in game) show up here too.
    const refresh = () => { void api.getAllHotkeys().then(setHotkeys).catch(() => {}) }
    window.addEventListener('war3-elephant-parameters', refresh)
    return () => window.removeEventListener('war3-elephant-parameters', refresh)
  }, [load])

  const toggle = async (h: HotkeyItem) => {
    const next = !h.enabled
    setHotkeys(list => list.map(x => (x.name === h.name ? { ...x, enabled: next } : x)))
    try {
      const result = await api.setHotkeyCheck(h.name, next)
      if (!result?.success) throw new Error(result?.error)
    } catch {
      setHotkeys(list => list.map(x => (x.name === h.name ? { ...x, enabled: !next } : x)))
    }
  }

  const setAll = (enabled: boolean) => run(enabled ? 'all-on' : 'all-off', async () => {
    const result = await api.setAllHotkeysChecks(enabled)
    if (result?.success) setHotkeys(result.hotkeys)
  })

  const setParam = async (h: HotkeyItem, value: string) => {
    if (!h.paramKey || value === (h.paramValue ?? '')) return
    setHotkeys(list => list.map(x => (x.paramKey === h.paramKey ? { ...x, paramValue: value } : x)))
    try { await api.setHotkeyParameter(h.paramKey, value) } catch { /* reported by callApi */ }
  }

  // Failures are thrown and shown by api.ts; only success needs saying here.
  const trigger = (h: HotkeyItem) => run(`fire-${h.name}`, async () => {
    const result = h.name === 'six_artifacts' ? await api.applyArtifactPlan([...artifacts]) : await api.triggerHotkey(h.name)
    if (result?.success) announce(t(result.message || fill(t('{action}：已完成'), { action: t(h.label) })))
  })

  const saveArtifacts = async (codes: string[]) => {
    try {
      const result = await api.saveArtifactPlan(codes)
      if (result?.success) announce(t('神器方案已保存'))
    } catch { /* reported by callApi */ }
  }
  const restoreArtifacts = () => run('artifacts', async () => {
    const result = await api.restoreDefaultArtifactPlan()
    if (result?.success && result.plan) {
      setArtifacts(result.plan.codes)
      announce(t('默认神器方案已恢复并保存'))
    }
  })

  const q = query.trim().toLowerCase()
  const visible = hotkeys.filter(h =>
    (category === 'all' || h.category === category)
    && (!q || [h.name, h.label, h.key].some(x => x.toLowerCase().includes(q))))
  const enabledCount = hotkeys.filter(h => h.enabled).length
  // Plain hotkeys pack several to a row; the ones with a value to fill in get a wider card.
  const hasValue = (h: HotkeyItem) => !!h.paramKey || h.name === 'six_artifacts'
  const plain = visible.filter(h => !hasValue(h))
  const valued = visible.filter(hasValue)

  /**
   * One hotkey: name and run button on top, the keys (and the value, if any) underneath.
   * A render function, not a component: a component defined here would be a new type on
   * every render and remount the inputs inside it while typing.
   */
  const card = (h: HotkeyItem, children?: ReactNode, wide = false) => (
    <li key={h.name} className={s.card} data-enabled={h.enabled || undefined} data-danger={h.isDangerous || undefined} data-wide={wide || undefined}>
      <div className={s.cardTop}>
        <Checkbox label="" aria-label={fill(t('启用 {name}'), { name: t(h.label) })} checked={h.enabled} onChange={() => void toggle(h)} className={s.check} />
        <span className={s.labelText} title={t(h.label)}>{t(h.label)}</span>
        {h.isDangerous && <span className={s.dangerTag}>{t('慎用')}</span>}
        <Button size="sm" className={s.fire} disabled={!connected || pending[`fire-${h.name}`]} onClick={() => void trigger(h)}>{t('触发')}</Button>
      </div>
      <div className={s.cardBottom}>
        <span className={s.keys} aria-label={h.key}>
          {h.key.split('+').map((k, i) => <Keycap key={i}>{k}</Keycap>)}
        </span>
        {children}
      </div>
    </li>
  )

  useCommandCard([
    { key: 'Q', icon: 'hotkey', title: t('全选可用'), description: t('勾选全部快捷键，游戏里按键即可触发。'), pending: pending['all-on'], onPress: () => void setAll(true) },
    { key: 'W', icon: 'cancel', title: t('清空勾选'), description: t('取消勾选全部快捷键。'), pending: pending['all-off'], onPress: () => void setAll(false) },
    { key: 'E', icon: 'refresh', title: t('刷新列表'), description: t('重新读取快捷键和参数。'), onPress: () => void load() },
  ])

  return (
    <div className={s.page}>
      <div className={s.toolbar}>
        <PillGroup<Category>
          label={t('按分类筛选')}
          value={category}
          onChange={setCategory}
          className={s.pills}
          options={CATEGORIES.map(c => ({ value: c.value, label: t(c.label), count: c.value === 'all' ? hotkeys.length : hotkeys.filter(h => h.category === c.value).length }))}
        />
        <TextField variant="search" className={s.search} aria-label={t('搜索快捷键')} placeholder={t('搜索功能名称或按键')} value={query} onChange={e => setQuery(e.target.value)} />
      </div>
      <div className={s.summary}>
        <span>{fill(t('已勾选 {n} / {total} 项'), { n: enabledCount, total: hotkeys.length })}</span>
        {!hotkeysOn && <span className={s.off}>{t('全局快捷键总开关已关闭，勾选的按键暂时不会响应。')}</span>}
        <span className={s.spacer} />
        <Button size="sm" disabled={pending['all-on']} onClick={() => void setAll(true)}>{t('全选可用')}</Button>
        <Button size="sm" disabled={pending['all-off']} onClick={() => void setAll(false)}>{t('清空勾选')}</Button>
      </div>

      <div className={s.list} aria-label={t('全局快捷键')}>
        {visible.length === 0 && <p className={s.empty}>{hotkeys.length ? t('没有匹配的快捷键。') : t('正在读取快捷键…')}</p>}
        {plain.length > 0 && (
          <ol className={s.grid}>
            {plain.map(h => card(h))}
          </ol>
        )}
        {valued.length > 0 && (
          <>
            {plain.length > 0 && <h3 className={s.groupTitle}>{t('需要填写数值的快捷键')}</h3>}
            <ol className={`${s.grid} ${s.wideGrid}`}>
              {valued.map(h => card(h,
                  h.name === 'six_artifacts' ? (
                    <span className={s.artifacts}>
                      {artifacts.map((code, i) => (
                        <TextField
                          key={i}
                          className={s.artifact}
                          aria-label={fill(t('神器槽 {n}'), { n: i + 1 })}
                          maxLength={4}
                          spellCheck={false}
                          value={code}
                          onChange={e => setArtifacts(list => list.map((c, j) => (j === i ? e.target.value : c)))}
                          onBlur={() => void saveArtifacts(artifacts)}
                        />
                      ))}
                      <Button size="sm" disabled={pending.artifacts} onClick={() => void restoreArtifacts()}>{t('恢复默认方案')}</Button>
                    </span>
                  ) : (
                    <ParamInput label={t(h.paramLabel || '参数')} value={h.paramValue ?? ''} onCommit={v => void setParam(h, v)} />
                  ),
                  h.name === 'six_artifacts'))}
            </ol>
          </>
        )}
      </div>
    </div>
  )
}

function ParamInput({ label, value, onCommit }: { label: string; value: string; onCommit(value: string): void }) {
  const [draft, setDraft] = useState(value)
  useEffect(() => setDraft(value), [value])
  return (
    <TextField
      className={s.paramField}
      aria-label={label}
      suffix={label}
      value={draft}
      spellCheck={false}
      onChange={e => setDraft(e.target.value)}
      onBlur={() => onCommit(draft.trim())}
      onKeyDown={e => { if (e.key === 'Enter') onCommit(draft.trim()) }}
    />
  )
}
