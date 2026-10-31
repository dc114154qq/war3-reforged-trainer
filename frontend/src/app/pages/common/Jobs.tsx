import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { Button, ProgressBar, TextArea, announce } from '../../../ds'
import { api, type DefinitionFileResult, type DefinitionProgress } from '../../../lib/api'
import { fill, useT } from '../../i18n'
import s from './Jobs.module.css'

/** One path per line; surrounding quotes from Explorer's "Copy as path" are dropped. */
export const splitPaths = (text: string) =>
  [...new Set(text.split(/\r?\n/).map(p => p.trim().replace(/^"(.*)"$/, '$1')).filter(Boolean))]

export const isRunning = (status: string) => status === 'running' || status === 'cancelling'

export async function copyText(text: string, done = '已复制') {
  try {
    await navigator.clipboard.writeText(text)
    announce(done)
  } catch {
    window.dispatchEvent(new CustomEvent('war3-error', { detail: '复制失败，请选中完整路径后复制。' }))
  }
}

/**
 * Poll a background job on the backend until it stops running. The first poll (no id)
 * picks up a job that is still running from before the page was opened.
 */
export function usePolledJob<P extends { jobId: string; status: string }>(fetch: (id: string) => Promise<P>, initial: P, intervalMs = 250) {
  const [progress, setProgress] = useState<P>(initial)
  const timer = useRef<number | undefined>(undefined)
  const disposed = useRef(false)
  const fetchRef = useRef(fetch)
  fetchRef.current = fetch

  const poll = useCallback(async (id = '') => {
    window.clearTimeout(timer.current)
    let next: P | null = null
    try {
      next = await fetchRef.current(id)
      if (!disposed.current && next) setProgress(next)
    } catch {
      // callApi already reported the failure.
    } finally {
      if (!disposed.current && next && isRunning(next.status)) timer.current = window.setTimeout(() => void poll(next!.jobId), intervalMs)
    }
  }, [intervalMs])

  useEffect(() => {
    disposed.current = false
    void poll()
    return () => { disposed.current = true; window.clearTimeout(timer.current) }
  }, [poll])

  return { progress, setProgress, poll, busy: isRunning(progress.status) }
}

/** Input files (one per line, with a picker) and an optional output folder. */
export function PathFields({ paths, onPaths, folder, onFolder, disabled, filesLabel, filesHelp, folderLabel, placeholder }: {
  paths: string
  onPaths(value: string): void
  folder: string
  onFolder(value: string): void
  disabled?: boolean
  filesLabel: string
  filesHelp?: ReactNode
  folderLabel: string
  placeholder?: string
}) {
  const t = useT()
  const [choosing, setChoosing] = useState(false)
  const choose = async (kind: 'files' | 'folder') => {
    setChoosing(true)
    try {
      if (kind === 'folder') {
        const r = await api.chooseDefinitionFolder()
        if (r?.path) onFolder(r.path)
      } else {
        const r = await api.chooseDefinitionFiles()
        if (r?.paths?.length) onPaths(r.paths.join('\n'))
      }
    } catch {
      // reported by callApi
    } finally {
      setChoosing(false)
    }
  }
  return (
    <div className={s.paths}>
      <div className={s.pathHead}>
        <span className={s.pathLabel}>{filesLabel}</span>
        <Button size="sm" icon="open-file" disabled={disabled || choosing} onClick={() => void choose('files')}>{t('选择文件（可多选）…')}</Button>
      </div>
      <TextArea aria-label={filesLabel} rows={4} spellCheck={false} value={paths} disabled={disabled} placeholder={placeholder} onChange={e => onPaths(e.target.value)} />
      {filesHelp && <p className={s.help}>{filesHelp}</p>}
      <div className={s.pathHead}>
        <span className={s.pathLabel}>{folderLabel}</span>
        <Button size="sm" icon="open-file" disabled={disabled || choosing} onClick={() => void choose('folder')}>{t('选择文件夹…')}</Button>
      </div>
      <TextArea aria-label={folderLabel} rows={2} spellCheck={false} value={folder} disabled={disabled} onChange={e => onFolder(e.target.value)} />
    </div>
  )
}

const FILE_STATES: Record<string, string> = {
  queued: '等待处理', running: '正在处理', succeeded: '处理成功', failed: '处理失败', cancelled: '已停止', skipped: '尚未处理',
}

/** Progress of a file job: headline, elapsed time, file and chapter bars, current work, log. */
export function JobProgress({ progress, headline }: { progress: DefinitionProgress; headline: string }) {
  const t = useT()
  const busy = isRunning(progress.status)
  return (
    <div className={s.progress} role="status" aria-live="polite">
      <p className={s.headline}>{t(headline)}</p>
      <p className={s.line}>{fill(t('已用时间：{n} 秒'), { n: progress.elapsed.toFixed(1) })}</p>
      {progress.batchMode && (
        <>
          <p className={s.line}>
            {fill(t('文件进度：{done} / {total}；成功 {ok}，失败 {failed}'), {
              done: progress.fileCompleted ?? 0, total: progress.fileTotal ?? 0, ok: progress.fileSucceeded ?? 0, failed: progress.fileFailed ?? 0,
            })}
            {busy && `；${fill(t('当前第 {n} 个文件'), { n: progress.fileIndex ?? 1 })}`}
          </p>
          <ProgressBar label={t('批量文件处理进度')} value={progress.fileCompleted ?? 0} max={progress.fileTotal || 1} />
        </>
      )}
      {progress.total ? (
        <>
          <p className={s.line}>{fill(t('章节进度：{done} / {total}；当前第 {index} 章'), { done: progress.completed ?? 0, total: progress.total, index: progress.index ?? 1 })}</p>
          <ProgressBar label={t('章节处理进度')} value={progress.completed ?? 0} max={progress.total} />
        </>
      ) : busy && <ProgressBar label={t('正在检查文件')} />}
      {progress.chapter && <p className={s.path}>{t('当前章节：')}{progress.chapter}</p>}
      {progress.currentFile && <p className={s.path}>{t('当前文件：')}{progress.currentFile}</p>}
      {progress.logPath && <p className={s.path}>{t('处理日志：')}{progress.logPath}</p>}
    </div>
  )
}

/** Per-file outcome of a batch job, with the output path ready to copy. */
export function FileResults({ files, extra }: { files: (DefinitionFileResult & { usagePath?: string })[]; extra?: (file: DefinitionFileResult & { usagePath?: string }) => ReactNode }) {
  const t = useT()
  const outputs = files.filter(f => f.status === 'succeeded' && f.destination).map(f => f.destination)
  return (
    <section className={s.files} aria-label={t('逐个文件的处理结果')}>
      <div className={s.pathHead}>
        <span className={s.pathLabel}>{t('逐个文件的处理结果')}</span>
        <Button size="sm" icon="copy" disabled={!outputs.length} onClick={() => void copyText(outputs.join('\n'), t('已复制全部输出路径'))}>{t('复制全部输出路径')}</Button>
      </div>
      <ol className={s.fileList}>
        {files.map(file => (
          <li key={file.source} className={s.file} data-status={file.status}>
            <span className={s.fileState}>{t(FILE_STATES[file.status] ?? file.status)}</span>
            <span className={s.path}>{file.source}</span>
            {file.destination && (
              <span className={s.output}>
                <span className={s.path}>→ {file.destination}</span>
                <Button size="sm" icon="copy" onClick={() => void copyText(file.destination, t('已复制完整路径'))}>{t('复制完整路径')}</Button>
              </span>
            )}
            {file.error && <span className={s.error}>{t(file.error)}</span>}
            {file.logPath && <span className={s.path}>{t('处理日志：')}{file.logPath}</span>}
            {file.reportPath && <span className={s.path}>{t('处理报告：')}{file.reportPath}</span>}
            {extra?.(file)}
          </li>
        ))}
      </ol>
    </section>
  )
}
