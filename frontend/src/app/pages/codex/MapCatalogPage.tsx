import { useEffect, useRef, useState } from 'react'
import { Button, PillGroup, ProgressBar, Select, TextArea, TextField } from '../../../ds'
import { api, type MapCatalogChange, type MapCatalogProgress, type MapCatalogRow } from '../../../lib/api'
import { useCommandCard } from '../../state/commands'
import { useMapIssues } from '../../state/mapIssues'
import { fill, useT } from '../../i18n'
import { DataTable } from '../common/DataTable'
import { copyText, isRunning, usePolledJob } from '../common/Jobs'
import { CodexLayout, Fact, SheetActions, SheetHead, SheetText, copyCode, useDebounced } from './Codex'
import s from './MapCatalogPage.module.css'

const KINDS = [['item', '物品'], ['ability', '技能'], ['unit', '单位'], ['upgrade', '科技']] as const
const PHASES: Record<string, string> = {
  queued: '准备读取', hash: '核对输入文件', chapter: '读取章节', objects: '读取物编对象', tables: '检查数据表',
  chapter_complete: '章节读取完成', verify: '复核原文件', complete: '读取完成',
}
const STATUSES: Record<string, string> = { succeeded: '读取完成', partial: '部分内容未能读取', failed: '读取失败', cancelled: '读取已停止' }
const PAGE = 100

const valueText = (v: unknown) => (v === null || v === undefined ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v))

/**
 * Objects a campaign or map adds or changes, read from its files without the game.
 * Reading runs as a backend job; searching, paging and export work on its result.
 */
export default function MapCatalogPage() {
  const t = useT()
  const { progress, setProgress, poll, busy } = usePolledJob<MapCatalogProgress>(id => api.getMapCatalogProgress(id), { jobId: '', status: 'idle', elapsed: 0 }, 400)
  const ready = progress.status === 'succeeded' || progress.status === 'partial'
  const [path, setPath] = useState('')
  const [starting, setStarting] = useState(false)
  const [kind, setKind] = useState<string>('item')
  const [query, setQuery] = useState('')
  const [scope, setScope] = useState('')
  const [changeType, setChangeType] = useState('')
  const [rows, setRows] = useState<MapCatalogRow[]>([])
  const [matches, setMatches] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [entry, setEntry] = useState<MapCatalogRow | null>(null)
  const [format, setFormat] = useState('csv')
  const [exporting, setExporting] = useState(false)
  const [exported, setExported] = useState<{ path: string; count: number } | null>(null)
  const [issuesOpen, setIssuesOpen] = useState(false)
  const [sourceOpen, setSourceOpen] = useState(true)
  const issuesRef = useRef<HTMLElement>(null)
  const searchRev = useRef(0)
  const detailRev = useRef(0)
  const settled = useDebounced(query, 200)
  const working = starting || busy
  const diagnostics: { scope: string; file: string; message: string; impact?: string }[] = progress.diagnostics ?? progress.warnings ?? []

  const search = async (page: number) => {
    if (!ready) return
    const mine = ++searchRev.current
    detailRev.current++
    setEntry(null)
    setLoading(true)
    setOffset(page)
    try {
      const result = await api.searchMapCatalog(progress.jobId, kind, settled, scope, changeType, page)
      if (mine !== searchRev.current) return
      setRows(result.rows)
      setMatches(result.matchCount)
    } catch {
      if (mine === searchRev.current) { setRows([]); setMatches(0) }
    } finally {
      if (mine === searchRev.current) setLoading(false)
    }
  }

  // A finished read (or a different job) brings the first page; later filters re-search.
  useEffect(() => {
    if (!ready) return
    setSourceOpen(false)
    if (progress.status === 'partial') setIssuesOpen(true)
  }, [ready, progress.jobId, progress.status])
  useEffect(() => { void search(0) }, [ready, progress.jobId, kind, settled, scope, changeType]) // eslint-disable-line react-hooks/exhaustive-deps

  // "Show the details on the page" from a failure notice.
  const issuesRequested = useMapIssues(st => st.pending)
  useEffect(() => {
    if (!issuesRequested) return
    useMapIssues.getState().handled()
    setIssuesOpen(true)
    window.setTimeout(() => issuesRef.current?.scrollIntoView({ block: 'nearest' }), 50)
  }, [issuesRequested])

  const choose = async () => {
    try {
      const r = await api.chooseDefinitionFile()
      if (r?.path) setPath(r.path)
    } catch { /* reported by callApi */ }
  }
  const start = async () => {
    setStarting(true)
    searchRev.current++
    detailRev.current++
    setRows([]); setEntry(null); setMatches(0); setOffset(0); setScope(''); setExported(null); setIssuesOpen(false)
    try {
      const r = await api.startMapCatalog(path.trim())
      if (r?.success) await poll(r.jobId)
    } catch { /* reported by callApi */ } finally {
      setStarting(false)
    }
  }
  const stop = async () => {
    try {
      await api.cancelMapCatalog(progress.jobId)
      setProgress(p => ({ ...p, status: 'cancelling' }))
    } catch { /* reported by callApi */ }
  }

  const open = async (row: MapCatalogRow) => {
    const mine = ++detailRev.current
    try {
      const detail = await api.getMapCatalogEntry(progress.jobId, row.id)
      if (mine === detailRev.current) setEntry(detail)
    } catch { /* reported by callApi */ }
  }

  const exportData = async (all: boolean) => {
    setExporting(true)
    try {
      const r = await api.exportMapCatalog(progress.jobId, format, all ? '' : kind, all ? '' : settled, all ? '' : scope, all ? '' : changeType)
      if (r?.success && r.path) setExported({ path: r.path, count: r.count ?? 0 })
    } catch { /* reported by callApi */ } finally {
      setExporting(false)
    }
  }

  const copyIssues = () => copyText(diagnostics.map(d => `${d.scope} / ${d.file}\n${d.message}${'impact' in d && d.impact ? `\n${d.impact}` : ''}`).join('\n\n'), t('已复制完整原因'))
  const copyEntry = (e: MapCatalogRow) => copyText([
    e.rawcode, e.name, (e.heroNames ?? []).join('、'), e.scope,
    (e.changes ?? []).map(c => `${c.label} [${c.field}] ${c.level}/${c.index}\n${c.baseKnown ? valueText(c.baseValue) : t('未收录原值')} → ${valueText(c.value)}\n${c.file}`).join('\n\n'),
  ].filter(Boolean).join('\n'), t('已复制全部字段'))

  const headline = progress.status === 'cancelling' ? '正在停止，请稍候…' : STATUSES[progress.status] ?? PHASES[progress.stage ?? ''] ?? '正在读取'

  useCommandCard([
    { key: 'Q', icon: 'open-file', title: t('选择战役／地图…'), description: t('选择要读取的战役或地图文件。'), disabled: working, onPress: () => void choose() },
    { key: 'W', icon: 'map-data', title: t('读取自定义目录'), description: t('读取这张地图新增或修改的物品、技能、单位和科技。不需要启动游戏。'), pending: working, estimateMs: 8000, disabled: !path.trim(), onPress: () => void start() },
    { key: 'E', icon: 'export', title: t('导出当前筛选'), description: t('把当前筛选出的对象导出为文件。'), pending: exporting, disabled: !ready, onPress: () => void exportData(false) },
    { key: 'R', icon: 'copy', title: t('复制代码'), description: t('复制选中对象的四字符代码。'), disabled: !entry, onPress: () => entry && void copyCode(entry.rawcode) },
  ])

  return (
    <CodexLayout
      toolbar={
        <div className={s.top}>
          <details className={s.source} open={sourceOpen} onToggle={e => setSourceOpen((e.target as HTMLDetailsElement).open)}>
            <summary>{ready ? `${t('已读取：')}${progress.source ?? ''}` : t('选择战役／地图')}</summary>
            <p className={s.help}>{t('选择一张战役或地图，列出它新增或修改的物品、技能、单位和科技。原生且未修改的对象不列入目录，原文件不会被修改。不需要启动游戏。')}</p>
            <div className={s.sourceRow}>
              <TextArea aria-label={t('战役／地图完整路径')} className={s.path} rows={2} spellCheck={false} value={path} disabled={working || exporting} placeholder={t('支持 .w3n / .w3x / .w3m')} onChange={e => setPath(e.target.value)} />
              <div className={s.sourceActions}>
                <Button icon="open-file" disabled={working || exporting} onClick={() => void choose()}>{t('选择战役／地图…')}</Button>
                {working
                  ? <Button variant="danger" disabled={starting || progress.status === 'cancelling'} onClick={() => void stop()}>{t('停止读取')}</Button>
                  : <Button variant="cast" icon="map-data" disabled={!path.trim() || exporting} onClick={() => void start()}>{t('读取自定义目录')}</Button>}
              </div>
            </div>
          </details>

          {progress.status !== 'idle' && !ready && (
            <div className={s.scan} role="status" aria-live="polite">
              <strong>{t(headline)}</strong>
              <span>{fill(t('已用时间：{n} 秒'), { n: progress.elapsed.toFixed(1) })}</span>
              {isRunning(progress.status) && <ProgressBar label={t('地图目录读取进度')} value={Math.max(0, (progress.index ?? 1) - 1)} max={progress.total || undefined} />}
              {isRunning(progress.status) && progress.scope && <span className={s.mono}>{progress.index ?? 0} / {progress.total ?? 0}　{progress.scope}</span>}
              {isRunning(progress.status) && progress.file && <span className={s.mono}>{progress.file}</span>}
              {progress.error && <span className={s.error}>{t(progress.error)}</span>}
            </div>
          )}

          {ready && diagnostics.length > 0 && (
            <section ref={issuesRef} className={s.issues} data-warning={progress.status === 'partial' || undefined} aria-label={t('目录读取详情')}>
              <div className={s.issuesHead}>
                <strong>{progress.status === 'partial' ? t('部分字段需要注意') : t('目录读取完成，有附加文字提示')}</strong>
                <Button size="sm" onClick={() => setIssuesOpen(o => !o)}>{issuesOpen ? t('收起原因') : t('查看具体原因')}</Button>
                <Button size="sm" icon="copy" onClick={() => void copyIssues()}>{t('复制完整原因')}</Button>
              </div>
              {issuesOpen && (
                <div className={s.issueList} role="region" aria-label={t('具体原因列表')}>
                  {diagnostics.map((d, i) => (
                    <article key={i}>
                      <strong className={s.mono}>{d.scope} / {d.file}</strong>
                      <p>{t(d.message)}</p>
                      {d.impact && <p>{t(d.impact)}</p>}
                    </article>
                  ))}
                </div>
              )}
            </section>
          )}

          <div className={s.filters}>
            <PillGroup<string>
              label={t('对象类型')}
              value={kind}
              onChange={setKind}
              options={KINDS.map(([id, label]) => ({ value: id, label: t(label), count: progress.counts?.[id] ?? 0 }))}
            />
            <Select aria-label={t('来源章节')} className={s.select} value={scope} disabled={!ready || exporting} onChange={e => setScope(e.target.value)}
              options={[{ value: '', label: t('全部来源') }, ...(progress.scopes ?? []).map(x => ({ value: x, label: x }))]} />
            <Select aria-label={t('改动类型')} className={s.select} value={changeType} disabled={!ready || exporting} onChange={e => setChangeType(e.target.value)}
              options={[{ value: '', label: t('新增与修改') }, { value: 'added', label: t('新增对象') }, { value: 'modified', label: t('修改原生对象') }]} />
            <TextField variant="search" className={s.query} aria-label={t('搜索自定义目录')} placeholder={t('代码、名称、说明、字段或数值')} value={query} disabled={!ready || exporting} onChange={e => setQuery(e.target.value)} />
          </div>
          <div className={s.exports}>
            <span>{fill(t('匹配 {match} / 共 {total}'), { match: matches, total: progress.rowCount ?? 0 })}</span>
            <span className={s.spacer} />
            <Select aria-label={t('导出格式')} className={s.select} value={format} disabled={exporting} onChange={e => setFormat(e.target.value)}
              options={[{ value: 'csv', label: t('CSV（Excel 可打开）') }, { value: 'json', label: t('JSON（含完整字段）') }]} />
            <Button size="sm" icon="export" disabled={!ready || exporting || loading} onClick={() => void exportData(false)}>{t('导出当前筛选')}</Button>
            <Button size="sm" icon="export" disabled={!ready || exporting} onClick={() => void exportData(true)}>{t('导出全部四类数据')}</Button>
          </div>
          {exporting && <p className={s.help}>{t('正在导出…')}</p>}
          {exported && (
            <div className={s.exported}>
              <span>{fill(t('导出完成：{n} 条'), { n: exported.count })}</span>
              <span className={s.mono}>{exported.path}</span>
              <Button size="sm" icon="copy" onClick={() => void copyText(exported.path, t('已复制完整路径'))}>{t('复制完整路径')}</Button>
            </div>
          )}
        </div>
      }
      list={<>
        <DataTable<MapCatalogRow>
          label={t('自定义对象')}
          fill
          rows={rows}
          rowKey={r => r.id}
          selected={entry?.id ?? null}
          onSelect={r => void open(r)}
          empty={loading ? t('正在检索…') : ready ? t('当前筛选没有新增或修改的对象。') : t('先选择战役或地图并读取目录。')}
          columns={[
            { key: 'rawcode', label: t('代码'), width: '64px', mono: true },
            { key: 'name', label: t('名称'), width: 'minmax(140px, 1fr)', render: r => (
              <span className={s.name}>{r.name}{r.isHero && <small>{r.heroNames?.length ? r.heroNames.join('、') : t('物编未提供固定本名')}</small>}</span>
            ) },
            { key: 'description', label: t('描述或效果'), width: 'minmax(0, 1.6fr)', render: r => <span className={s.desc}>{r.description || t('没有说明，可查看具体修改字段。')}</span> },
            { key: 'change', label: t('改动'), width: '96px', render: r => <span className={s.change} data-type={r.changeType}>{fill(r.changeType === 'added' ? t('新增 {n}') : t('修改 {n}'), { n: r.changeCount })}</span> },
            { key: 'scope', label: t('来源章节'), width: '110px' },
            { key: 'base', label: t('原型'), width: '58px', mono: true },
          ]}
        />
        <div className={s.pages}>
          <Button size="sm" disabled={!ready || loading || offset === 0} onClick={() => void search(Math.max(0, offset - PAGE))}>{t('上一页')}</Button>
          <span>{matches ? offset + 1 : 0}–{Math.min(offset + PAGE, matches)} / {matches}</span>
          <Button size="sm" disabled={!ready || loading || offset + PAGE >= matches} onClick={() => void search(offset + PAGE)}>{t('下一页')}</Button>
        </div>
      </>}
      footer={t('战役共用数据只列一次；章节记录是该章节自己的修改。目录读取静态物编和数据表，脚本运行后临时修改的内容不在目录中。')}
      sheet={entry && {
        key: entry.id,
        content: <>
          <SheetHead
            code={entry.rawcode}
            name={entry.name}
            sub={entry.heroNames?.length ? `${t('英雄本名：')}${entry.heroNames.join('、')}` : undefined}
            facts={<>
              <Fact label={t('来源章节')}>{entry.scope}</Fact>
              <Fact label={t('原型')}>{entry.base}</Fact>
              <Fact label={t('改动')}>{entry.changeType === 'added' ? t('新增对象') : t('修改原生对象')}</Fact>
            </>}
          />
          <SheetText>
            {entry.description && <p>{entry.description}</p>}
            {entry.isHero && <small>{t('本名来自物编；多个名称表示候选名字。')}</small>}
            <Changes changes={entry.changes ?? []} />
          </SheetText>
          <SheetActions>
            <Button size="sm" onClick={() => setEntry(null)}>{t('关闭')}</Button>
            <Button size="sm" icon="copy" onClick={() => void copyCode(entry.rawcode)}>{t('复制代码')}</Button>
            <Button size="sm" icon="copy" onClick={() => void copyEntry(entry)}>{t('复制全部字段')}</Button>
          </SheetActions>
        </>,
      }}
    />
  )
}

/** Every changed field: name and id, level and column, the stock value and the map's value. */
function Changes({ changes }: { changes: MapCatalogChange[] }) {
  const t = useT()
  if (!changes.length) return <small>{t('这是以原生对象为原型新增的对象，没有额外修改字段。')}</small>
  return (
    <ol className={s.changes} aria-label={t('完整字段改动表')}>
      <li className={s.changeCount}>{fill(t('共 {n} 个改动字段'), { n: changes.length })}</li>
      {changes.map((c, i) => (
        <li key={i} className={s.changeItem}>
          <span className={s.changeLabel}>{c.label}<code>{c.field}</code><span>{c.level} / {c.index}</span></span>
          <span className={s.changeValues}>
            <span className={s.before}>{c.baseKnown ? valueText(c.baseValue) : t('未收录原值')}</span>
            <span aria-hidden="true">→</span>
            <span className={s.after}>{valueText(c.value)}</span>
          </span>
          {valueText(c.rawValue) !== valueText(c.value) && <small>{valueText(c.rawValue)}</small>}
          <small>{c.file}</small>
        </li>
      ))}
    </ol>
  )
}
