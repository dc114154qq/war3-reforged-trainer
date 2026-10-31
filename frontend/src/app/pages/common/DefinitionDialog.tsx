import { useState } from 'react'
import { Button, Dialog, DialogClose } from '../../../ds'
import { api, type DefinitionProgress, type DefinitionResult } from '../../../lib/api'
import { fill, useT } from '../../i18n'
import { FileResults, JobProgress, PathFields, copyText, splitPaths, usePolledJob } from './Jobs'
import s from './DefinitionDialog.module.css'

const JOB_STATES: Record<string, string> = {
  succeeded: '处理完成', partial: '部分文件处理失败', failed: '处理失败', cancelled: '处理已停止，原文件已保留。',
}
const STAGES: Record<string, string> = {
  queued: '准备处理', custom_object_begin: '检查地图对象', custom_object_verified: '对象检查完成', custom_object_failed: '发现对象结构异常',
  source_hash_begin: '核对输入文件', start: '读取定义资料', copy_begin: '复制原文件', source_copied: '复制校验完成', scan_archive: '检查归档文件',
  chapter_begin: '处理章节', table_layout_verified: '检查数据表格式', write_table: '写入背包定义', archive_verify: '复查归档',
  verify_member: '核对原有文件', chapter_verified: '章节校验完成', replace_chapter: '保存战役章节', output_verify: '核对最终输出',
  verified: '准备完成输出', complete: '处理完成', script_function_order_verified: '章节脚本顺序检查完成', script_validation_failed: '发现章节脚本错误',
  archive_compaction_begin: '整理归档中的旧数据', archive_compaction_complete: '归档整理完成', archive_compaction_skipped: '归档无需整理',
  archive_compaction_failed: '归档整理出错',
}

/**
 * Add the 3.0 backpack definitions to a campaign or map, writing a new copy.
 * The job keeps running on the backend when the dialog closes; reopening picks it up.
 */
export function DefinitionDialog({ open, onOpenChange }: { open: boolean; onOpenChange(open: boolean): void }) {
  const t = useT()
  // Paths survive closing the dialog, as the bound values did in 2.1.22.
  const [paths, setPaths] = useState('')
  const [folder, setFolder] = useState('')
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      size="lg"
      surface="iron"
      title={t('补齐战役／地图背包定义')}
      description={t('添加背包时提示“背包装备未定义”，就用这里为战役或地图补齐定义。原文件会保留，生成的是新副本；完成后用新副本重新进入地图。已有存档仍是保存时的数据。')}
    >
      {open && <DefinitionJob paths={paths} onPaths={setPaths} folder={folder} onFolder={setFolder} />}
    </Dialog>
  )
}

function DefinitionJob({ paths, onPaths, folder, onFolder }: { paths: string; onPaths(v: string): void; folder: string; onFolder(v: string): void }) {
  const t = useT()
  const { progress, setProgress, poll, busy } = usePolledJob<DefinitionProgress>(id => api.getBackpackDefinitionProgress(id), { jobId: '', status: 'idle', elapsed: 0 })
  const [starting, setStarting] = useState(false)
  const selected = splitPaths(paths)
  const working = starting || busy

  const result: DefinitionResult | null = progress.result
    ?? (progress.status === 'failed' ? { success: false, error: progress.error, logPath: progress.logPath } : null)

  const start = async () => {
    setStarting(true)
    try {
      const job = selected.length > 1
        ? await api.startBackpackDefinitionsBatch(selected, folder)
        : await api.startBackpackDefinitions(selected[0] ?? '', folder)
      if (job?.success) await poll(job.jobId)
    } catch {
      // reported by callApi
    } finally {
      setStarting(false)
    }
  }
  const stop = async () => {
    await api.cancelBackpackDefinitions(progress.jobId)
    setProgress(p => ({ ...p, status: 'cancelling' }))
  }

  const headline = progress.status === 'cancelling' ? '正在停止，请稍候…'
    : JOB_STATES[progress.status] ?? STAGES[progress.stage ?? ''] ?? '正在处理'

  return (
    <>
      <PathFields
        paths={paths}
        onPaths={onPaths}
        folder={folder}
        onFolder={onFolder}
        disabled={working}
        filesLabel={t('地图或战役文件')}
        placeholder={t('支持 .w3n / .w3x / .w3m，每行一个完整路径')}
        filesHelp={fill(t('可一次选择多个文件，也可以每行粘贴一个完整路径；相同路径会自动去重。已填入 {n} 个文件。'), { n: selected.length })}
        folderLabel={t('输出文件夹（留空则放在原文件旁边）')}
      />
      {progress.status !== 'idle' && <JobProgress progress={progress} headline={headline} />}
      {result && (
        <div className={s.result} data-ok={result.success && !progress.fileFailed ? '' : undefined}>
          {result.error ? (
            <>
              <p>{t(result.error)}</p>
              {result.logPath && <p className={s.path}>{t('处理日志：')}{result.logPath}</p>}
            </>
          ) : result.batch ? <p>{t(result.message ?? '')}</p> : (
            <>
              <p>{t(result.message ?? '')}</p>
              {result.destination && (
                <div className={s.output}>
                  <span className={s.path}>{result.destination}</span>
                  <Button size="sm" icon="copy" onClick={() => void copyText(result.destination!, t('已复制完整路径'))}>{t('复制完整路径')}</Button>
                </div>
              )}
              {result.report && <p className={s.path}>{t('处理报告：')}{result.report.report_path}<br />{t('处理日志：')}{result.report.log_path}</p>}
            </>
          )}
        </div>
      )}
      {progress.batchMode && !!progress.files?.length && <FileResults files={progress.files} />}
      <footer className={s.footer}>
        {working ? (
          <>
            <span className={s.note}>{t('关闭窗口后仍会继续处理，可重新打开查看。')}</span>
            <Button variant="danger" disabled={starting || progress.status === 'cancelling'} onClick={() => void stop()}>{t('停止处理')}</Button>
          </>
        ) : (
          <>
            <DialogClose asChild><Button>{t('关闭')}</Button></DialogClose>
            <Button variant="cast" icon="write" disabled={!selected.length} onClick={() => void start()}>
              {selected.length > 1 ? fill(t('批量补齐定义（{n} 个文件）'), { n: selected.length }) : t('立即补齐定义')}
            </Button>
          </>
        )}
      </footer>
    </>
  )
}
