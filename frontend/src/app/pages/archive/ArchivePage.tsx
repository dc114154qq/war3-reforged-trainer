import { useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { Button, PillGroup, ProgressBar, Select, TextArea, TextField, announce } from '../../../ds'
import { api } from '../../../lib/api'
import type { ArchiveRow, RpgCodeRow } from '../../../lib/types'
import { useCommandCard } from '../../state/commands'
import { useSystem } from '../../state/system'
import { fill, useT } from '../../i18n'
import { DataTable } from '../common/DataTable'
import { Status, usePending } from '../common/Layout'
import s from './ArchivePage.module.css'

type Tab = 'campaign' | 'rpg'
/** A save from scan_archive_directory; date is the file's modification time in epoch seconds. */
interface SaveFile { path: string; name: string; date?: string }

const fileDate = (date: string | undefined) => {
  const ms = Number(date) * 1000
  return Number.isFinite(ms) && ms > 0 ? new Date(ms).toLocaleString() : ''
}
type Feedback = { text: string; error?: boolean } | null

export default function ArchivePage() {
  const t = useT()
  const connected = useSystem(st => st.status.connected)
  const { pending, run } = usePending()
  const [tab, setTab] = useState<Tab>('campaign')
  const [feedback, setFeedback] = useState<Feedback>(null)

  // Campaign saves
  const [directory, setDirectory] = useState('')
  const [files, setFiles] = useState<SaveFile[]>([])
  const [file, setFile] = useState('')
  const [rows, setRows] = useState<ArchiveRow[]>([])
  const [filter, setFilter] = useState('')

  // RPG load codes
  const [prefix, setPrefix] = useState('-load')
  const [text, setText] = useState('')
  const [codes, setCodes] = useState<RpgCodeRow[]>([])

  const fail = (message: string) => setFeedback({ text: message, error: true })

  /**
   * Show progress, then the outcome. api.ts throws on success: false (and shows the reason
   * as a notice), so failures land in the catch and replace the progress line.
   */
  const attempt = async <T,>(busyText: string, failText: string, call: () => Promise<T>, done: (result: T) => void) => {
    setFeedback({ text: busyText })
    try {
      done(await call())
    } catch (err) {
      fail(`${failText}${t(err instanceof Error ? err.message : String(err))}`)
      throw err
    }
  }

  const scanDirectory = () => run('scan', () => attempt(t('正在扫描存档目录…'), t('扫描失败：'),
    () => api.scanArchiveDirectory(directory.trim()),
    r => {
      const found = (r?.files ?? []) as SaveFile[]
      setFiles(found)
      if (r?.directory && !directory.trim()) setDirectory(r.directory)
      setFile(found[0]?.path ?? '')
      setFeedback({ text: found.length ? fill(t('找到 {n} 个战役存档'), { n: found.length }) : t('这个目录里没有 .w3v 或 .w3z 存档。') })
    }))

  const readFile = () => run('read', async () => {
    if (!file) return fail(t('先选择要解析的存档文件。'))
    await attempt(t('正在解析战役存档…'), t('解析失败：'), () => api.readArchiveFile(file), r => {
      setRows(r?.rows ?? [])
      setFeedback({ text: fill(t('解析完成，共 {n} 条英雄数据'), { n: r?.rows?.length ?? 0 }) })
    })
  })

  const readLive = () => run('live', () => attempt(t('正在从游戏内存读取战役英雄缓存…'), t('读取失败：'), () => api.readLiveHeroes(), r => {
    setRows(r?.rows ?? [])
    setFeedback({ text: fill(t('内存读取完成，共 {n} 条英雄数据'), { n: r?.rows?.length ?? 0 }) })
  }))

  const scanMemory = () => run('memory', () => attempt(fill(t('正在扫描游戏内存里的 {prefix} 载入码…'), { prefix }), t('扫描失败：'),
    () => api.scanRpgCodesMemory(prefix),
    r => {
      setCodes(r?.rows ?? [])
      setFeedback({ text: fill(t('扫描完成，找到 {n} 条载入码'), { n: r?.rows?.length ?? 0 }) })
    }))

  const parseText = () => run('parse', async () => {
    if (!text.trim()) return fail(t('先在文本框里粘贴含有载入码的文字。'))
    await attempt(t('正在提取载入码…'), t('提取失败：'), () => api.parseRpgCodesText(text, prefix), r => {
      setCodes(r?.rows ?? [])
      setFeedback({ text: fill(t('提取完成，共 {n} 条载入码'), { n: r?.rows?.length ?? 0 }) })
    })
  })

  const q = filter.trim().toLowerCase()
  const visible = rows.filter(r => !q || [r.scope, r.key, r.value].some(x => x.toLowerCase().includes(q)))
  const busy = Object.values(pending).some(Boolean)

  useCommandCard(tab === 'campaign' ? [
    { key: 'Q', icon: 'open-file', title: t('扫描目录'), description: t('在存档目录里找战役存档；留空时自动找魔兽争霸的存档目录。'), pending: pending.scan, estimateMs: 1200, onPress: () => void scanDirectory() },
    { key: 'W', icon: 'archive', title: t('解析此存档'), description: t('读出存档里英雄跨关卡保存的属性、技能和物品。'), pending: pending.read, estimateMs: 1500, disabled: !file, onPress: () => void readFile() },
    { key: 'E', icon: 'unit-hero', title: t('读当前内存英雄'), description: t('战役进行中，直接从游戏内存读取英雄缓存。'), pending: pending.live, estimateMs: 1500, disabled: !connected, onPress: () => void readLive() },
    { key: 'A', icon: 'chat', title: t('RPG 载入码'), description: t('切换到 RPG 载入码提取。'), onPress: () => setTab('rpg') },
  ] : [
    { key: 'Q', icon: 'search', title: t('从游戏内存扫描'), description: t('从游戏内存里找最近收到的载入码。'), pending: pending.memory, estimateMs: 2500, disabled: !connected, onPress: () => void scanMemory() },
    { key: 'W', icon: 'read', title: t('从文本提取'), description: t('从粘贴的聊天记录或文档里提取载入码。'), pending: pending.parse, onPress: () => void parseText() },
    { key: 'A', icon: 'archive', title: t('战役存档'), description: t('切换到战役存档提取。'), onPress: () => setTab('campaign') },
  ])

  return (
    <div className={s.page}>
      <div className={s.tabs}>
        <PillGroup<Tab>
          label={t('提取方式')}
          value={tab}
          onChange={v => { setTab(v); setFeedback(null) }}
          options={[{ value: 'campaign', label: t('战役存档（.w3v / .w3z）') }, { value: 'rpg', label: t('RPG 载入码') }]}
        />
      </div>

      {tab === 'campaign' ? (
        <>
          <div className={s.controls}>
            <TextField
              className={s.grow}
              label={t('存档目录（留空自动找魔兽争霸的存档目录）')}
              placeholder="C:\Users\…\Documents\Warcraft III\Save"
              spellCheck={false}
              value={directory}
              onChange={e => setDirectory(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') void scanDirectory() }}
            />
            <Button icon="open-file" disabled={pending.scan} onClick={() => void scanDirectory()}>{t('扫描目录')}</Button>
          </div>
          <div className={s.controls}>
            {files.length > 0 && (
              <Select
                className={s.grow}
                label={t('存档文件')}
                value={file}
                onChange={e => setFile(e.target.value)}
                options={files.map(f => ({ value: f.path, label: fileDate(f.date) ? `${f.name}（${fileDate(f.date)}）` : f.name }))}
              />
            )}
            {files.length > 0 && <Button variant="cast" icon="archive" disabled={pending.read} onClick={() => void readFile()}>{t('解析此存档')}</Button>}
            <Button icon="unit-hero" disabled={!connected || pending.live} onClick={() => void readLive()}>{t('读当前内存英雄')}</Button>
          </div>
          <Scanning active={busy} />
          {feedback && <Status tone={feedback.error ? 'error' : 'info'}>{feedback.text}</Status>}
          {rows.length > 0 && (
            <div className={s.filter}>
              <TextField variant="search" className={s.search} aria-label={t('筛选英雄数据')} placeholder={t('筛选英雄属性、技能或物品')} value={filter} onChange={e => setFilter(e.target.value)} />
              <span>{fill(t('{shown} / {total} 项'), { shown: visible.length, total: rows.length })}</span>
            </div>
          )}
          <DataTable<ArchiveRow>
            label={t('英雄数据')}
            fill
            rows={visible}
            rowKey={r => `${r.scope}:${r.key}`}
            empty={t('还没有战役数据。点“扫描目录”找本地单人战役存档，或在战役进行中点“读当前内存英雄”。')}
            columns={[
              { key: 'scope', label: t('作用域或英雄'), width: '150px' },
              { key: 'key', label: t('键名'), width: 'minmax(160px, 1fr)' },
              { key: 'type', label: t('类型'), width: '90px' },
              { key: 'value', label: t('内容'), width: 'minmax(0, 2fr)', mono: true },
            ]}
          />
        </>
      ) : (
        <>
          <div className={s.controls}>
            <TextField className={s.prefix} label={t('命令前缀')} spellCheck={false} value={prefix} onChange={e => setPrefix(e.target.value)} />
            <Button variant="cast" icon="search" disabled={!connected || pending.memory} onClick={() => void scanMemory()}>{t('从游戏内存扫描')}</Button>
          </div>
          <div className={s.controls}>
            <TextArea
              className={s.grow}
              label={t('或者粘贴聊天记录、文档或识别出的文字')}
              rows={3}
              spellCheck={false}
              placeholder={t('粘贴含有 -load 载入码的文字')}
              value={text}
              onChange={e => setText(e.target.value)}
            />
            <Button disabled={pending.parse} onClick={() => void parseText()}>{t('从文本提取')}</Button>
          </div>
          <Scanning active={busy} />
          {feedback && <Status tone={feedback.error ? 'error' : 'info'}>{feedback.text}</Status>}
          <Codes codes={codes} />
        </>
      )}
    </div>
  )
}

/** The loading-screen bar while a scan runs. */
function Scanning({ active }: { active: boolean }) {
  const t = useT()
  return active ? <ProgressBar className={s.scanning} label={t('正在扫描')} /> : null
}

/** Each code on its own strip of vellum, ready to copy, as a player would write it down. */
function Codes({ codes }: { codes: RpgCodeRow[] }) {
  const t = useT()
  const reduce = useReducedMotion()
  const [copied, setCopied] = useState<string | null>(null)
  const copy = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(code)
      announce(t('已复制载入码'))
    } catch {
      window.dispatchEvent(new CustomEvent('war3-error', { detail: '复制失败，请选中完整文字后复制。' }))
    }
  }
  if (!codes.length) {
    return <p className={s.empty}>{t('还没有载入码。在联机 RPG 地图里点“从游戏内存扫描”提取最近收到的存档代码，也可以在上面粘贴文字后提取。')}</p>
  }
  return (
    <ol className={s.codes} aria-label={t('载入码')}>
      <AnimatePresence initial={false}>
        {codes.map((c, i) => (
          <motion.li
            key={`${c.code}-${i}`}
            className={s.strip}
            initial={reduce ? { opacity: 0 } : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: reduce ? 0 : Math.min(i, 8) * 0.04 }}
          >
            <div className={s.stripHead}>
              <span className={s.kind}>{t(c.kind)}</span>
              <span className={s.source}>{t(c.source)}</span>
              <Button size="sm" icon="copy" onClick={() => void copy(c.code)}>{copied === c.code ? t('已复制') : t('复制')}</Button>
            </div>
            <p className={s.code}>{c.code}</p>
          </motion.li>
        ))}
      </AnimatePresence>
    </ol>
  )
}
