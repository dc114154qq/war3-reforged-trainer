import { useRef, useState, type MouseEvent } from 'react'
import { Button, Checkbox, Icon, RawcodePlate, Select, SelectionRing, TextField, announce } from '../../../ds'
import { api } from '../../../lib/api'
import { useCommandCard } from '../../state/commands'
import { useSystem } from '../../state/system'
import { useT } from '../../i18n'
import { DataTable } from '../common/DataTable'
import { Hint, PageBody, Row, Section, Status, usePending } from '../common/Layout'
import s from './BatchPage.module.css'

/** One unit from batch_read_units: instance is the backend identity joined with ':', error a read problem. */
interface BatchUnit { checked: boolean; rawcode: string; instance: string; hp: string; mp: string; error?: string | null }
interface FieldDef { key: string; label: string; category?: string; type?: string; supported?: number }
interface Report { unit: string; field: string; target: string; status: string; reason: string; actual?: string }

/** Hero type ids start with a capital letter in Warcraft III. */
const isHero = (code: string) => /^[A-Z]/.test(code)

export default function BatchPage() {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const { pending, run } = usePending()
  const [units, setUnits] = useState<BatchUnit[]>([])
  const [fields, setFields] = useState<FieldDef[]>([])
  const [targets, setTargets] = useState<Record<string, string>>({})
  const [reports, setReports] = useState<Report[]>([])
  const [message, setMessage] = useState('')
  const [hover, setHover] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [filledOnly, setFilledOnly] = useState(false)
  const [showUnits, setShowUnits] = useState(false)
  const anchor = useRef<number | null>(null)

  // api.ts throws on success: false and shows the reason; the status line repeats it here.
  const failed = (err: unknown) => { setMessage(err instanceof Error ? err.message : String(err)); throw err }

  const read = () => run('read', async () => {
    try {
      const res = await api.batchReadUnits()
      const list = (res?.units ?? []) as BatchUnit[]
      setUnits(list)
      const defs = (res?.fields ?? []) as FieldDef[]
      setFields(defs)
      setCategory('')
      setTargets(prev => Object.fromEntries(defs.map(f => [f.key, prev[f.key] ?? ''])))
      setReports([])
      setMessage(list.length ? `已成功解析 ${list.length} 个选中单位实例` : '未读取到选中单位')
    } catch (err) {
      failed(err)
    }
  })

  const setAll = (checked: boolean) => setUnits(us => us.map(u => ({ ...u, checked })))

  /** Click toggles; Shift-click extends from the last clicked unit, as in a list. */
  const toggle = (index: number, e: MouseEvent) => {
    setUnits(us => {
      const next = [...us]
      if (e.shiftKey && anchor.current !== null) {
        const [from, to] = [Math.min(anchor.current, index), Math.max(anchor.current, index)]
        const value = !us[index].checked
        for (let i = from; i <= to; i++) next[i] = { ...next[i], checked: value }
      } else {
        next[index] = { ...next[index], checked: !next[index].checked }
      }
      return next
    })
    anchor.current = index
  }

  const write = () => run('write', async () => {
    const instances = units.filter(u => u.checked).map(u => u.instance)
    if (!instances.length) return announce(t('请先勾选需要批量修改的单位'))
    const active = Object.fromEntries(Object.entries(targets).map(([k, v]) => [k, v.trim()]).filter(([, v]) => v))
    if (!Object.keys(active).length) return announce(t('请至少填写一个目标修改值'))
    try {
      const res = await api.batchWriteUnits(instances, active)
      setMessage(res?.message || '批量修改已下发执行')
      setReports((res?.reports ?? []) as Report[])
    } catch (err) {
      failed(err)
    }
  })

  const clear = () => setTargets(prev => Object.fromEntries(Object.keys(prev).map(k => [k, ''])))
  const checked = units.filter(u => u.checked).length
  const busy = pending.read || pending.write
  const filled = fields.filter(f => targets[f.key]?.trim()).length
  const q = query.trim().toLowerCase()
  const visible = fields.filter(f => (!category || f.category === category)
    && (!filledOnly || targets[f.key]?.trim())
    && (!q || [f.key, f.label, t(f.label), f.category ?? ''].some(v => v.toLowerCase().includes(q))))
  const categories = [...new Set(fields.map(f => f.category).filter((v): v is string => !!v))]

  useCommandCard([
    { key: 'Q', icon: 'candidates', title: t('读取所有选中单位'), description: t('读取游戏里框选的全部单位，放进头像网格。'), pending: pending.read, estimateMs: 1100, disabled: !connected || busy, onPress: () => void read() },
    { key: 'W', icon: 'unit-melee', title: t('全选'), description: t('勾选网格里的全部单位。'), disabled: !units.length, onPress: () => setAll(true) },
    { key: 'E', icon: 'cancel', title: t('全不选'), description: t('取消勾选全部单位。'), disabled: !units.length, onPress: () => setAll(false) },
    { key: 'R', icon: 'write', title: t('批量修改'), description: t('把填写的目标值写进所有勾选的单位；留空的属性保持原值。'), pending: pending.write, estimateMs: 1500, disabled: !connected || busy, onPress: () => void write() },
    { key: 'A', icon: 'remove', title: t('清空目标值'), description: t('清空全部目标值输入框。'), onPress: clear },
  ])

  return (
    <PageBody fill className={s.page}>
      <Section
        className={s.selection}
        title={`${t('选中的单位')}（${checked}/${units.length}）`}
        actions={<>
          <Button size="sm" icon="read" disabled={!connected || busy} onClick={() => void read()}>{t('读取所有选中单位')}</Button>
          <Button size="sm" disabled={!units.length} onClick={() => setAll(true)}>{t('全选')}</Button>
          <Button size="sm" disabled={!units.length} onClick={() => setAll(false)}>{t('全不选')}</Button>
          {!!units.length && <Button size="sm" onClick={() => setShowUnits(v => !v)}>{showUnits ? t('收起单位') : t('展开单位')}</Button>}
        </>}
      >
        {units.length === 0 ? (
          <p className={s.empty}>{t('暂无单位，请在游戏里拉框选中后读取。')}</p>
        ) : showUnits ? (
          <ul className={s.grid} role="listbox" aria-multiselectable="true" aria-label={t('选中的单位')}>
            {units.map((u, i) => (
              <li key={u.instance}>
                <button
                  type="button"
                  role="option"
                  aria-selected={u.checked}
                  className={s.unit}
                  title={`${u.rawcode}　${u.instance}\n${t('生命')} ${u.hp}　${t('魔法')} ${u.mp}${u.error ? `\n${t(u.error)}` : ''}`}
                  onClick={e => toggle(i, e)}
                  onPointerEnter={() => setHover(u.instance)}
                  onPointerLeave={() => setHover(null)}
                >
                  <SelectionRing className={s.ring} state={u.checked ? 'selected' : hover === u.instance ? 'hover' : 'none'} />
                  <span className={s.portrait}><Icon name={isHero(u.rawcode) ? 'unit-hero' : 'unit-melee'} /></span>
                  <span className={s.plate}><RawcodePlate code={u.rawcode} /></span>
                  <span className={s.vitals}><span className={s.hp}>{u.hp}</span><span className={s.mp}>{u.mp}</span></span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        {message && <Status>{t(message)}</Status>}
      </Section>

      <Section
        className={s.fieldSection}
        title={t('目标值')}
        actions={<>
          <Button size="sm" onClick={clear}>{t('清空目标值')}</Button>
          <Button variant="cast" size="sm" disabled={!connected || busy} onClick={() => void write()}>{t('批量修改')}</Button>
        </>}
      >
        {fields.length === 0 ? (
          <p className={s.empty}>{t('读取单位后会列出可以批量修改的属性。')}</p>
        ) : (<>
          <Hint>{t('留空的属性将保持单位原有数值不变')}</Hint>
          <Row className={s.filters}>
            <TextField variant="search" aria-label={t('搜索批量字段')} placeholder={t('搜索字段名或标识')} value={query} onChange={e => setQuery(e.target.value)} />
            <Select aria-label={t('按分类筛选')} value={category} onChange={e => setCategory(e.target.value)} options={[
              { value: '', label: t('全部分类') }, ...categories.map(c => ({ value: c, label: t(c) })),
            ]} />
            <Checkbox label={t('只看已填写')} checked={filledOnly} onChange={e => setFilledOnly(e.target.checked)} />
            <span className={s.count}>{t('已填写')} {filled} / {fields.length} · {t('显示')} {visible.length}</span>
          </Row>
          <div className={s.targets} data-testid="batch-targets">
            {visible.map(f => (
              <TextField
                key={f.key}
                id={`batch-${f.key}`}
                label={t(f.label)}
                title={`${t(f.category ?? '')} · ${f.key}${f.supported !== undefined ? ` · ${f.supported}/${units.length}` : ''}`}
                placeholder={t('保持原值')}
                inputMode="decimal"
                disabled={busy}
                value={targets[f.key] ?? ''}
                onChange={e => setTargets(prev => ({ ...prev, [f.key]: e.target.value }))}
                className={s.target}
              />
            ))}
          </div>
          {!visible.length && <p className={s.empty}>{t('没有匹配的字段。')}</p>}
          <Hint>{t('筛选只影响显示；隐藏字段中已填写的值也会提交。')}</Hint>
        </>)}
      </Section>

      <details className={s.results}>
        <summary>{t('执行结果')}（{reports.length}）</summary>
        <DataTable<Report>
          label={t('执行结果')}
          rows={reports}
          rowKey={r => `${r.unit}-${r.field}`}
          empty={t('尚未执行批量修改')}
          maxHeight={160}
          columns={[
            { key: 'unit', label: t('单位实例'), width: '140px', mono: true },
            { key: 'field', label: t('字段'), width: '150px', render: r => t(fields.find(f => f.key === r.field)?.label ?? r.field) },
            { key: 'target', label: t('目标值'), width: '100px' },
            { key: 'status', label: t('结果'), width: '80px', render: r => t(r.status) },
            { key: 'reason', label: t('读回或跳过原因'), render: r => t(r.reason || r.actual || '') },
          ]}
        />
      </details>
    </PageBody>
  )
}
