import { useState } from 'react'
import { Button, Dialog } from '../../ds'
import { useMapIssues } from '../state/mapIssues'
import { useNav } from '../state/nav'
import { useNotices } from '../state/notices'
import { useT } from '../i18n'
import s from './NoticeDialog.module.css'

/**
 * Failures that need explaining: title, reason, per-file details and the diagnostic log.
 * One at a time, in arrival order.
 */
export function NoticeDialog() {
  const t = useT()
  const notice = useNotices(st => st.queue[0])
  const dismiss = useNotices(st => st.dismiss)
  const setPage = useNav(st => st.setPage)
  const [copied, setCopied] = useState(false)
  const [copyFailed, setCopyFailed] = useState(false)

  const close = () => { setCopied(false); setCopyFailed(false); dismiss() }

  const copy = async () => {
    if (!notice) return
    const details = (notice.details ?? []).map(d => `${d.scope} / ${d.file}\n${d.message}${d.impact ? `\n${d.impact}` : ''}`).join('\n\n')
    try {
      const log = notice.logPath && !notice.message.includes(notice.logPath) ? notice.logPath : ''
      await navigator.clipboard.writeText([t(notice.title || '操作未完成'), notice.message, details, log].filter(Boolean).join('\n\n'))
      setCopied(true)
      setCopyFailed(false)
    } catch {
      setCopied(false)
      setCopyFailed(true)
    }
  }

  const showPageDetails = () => {
    close()
    useMapIssues.getState().request()
    setPage('map_catalog')
  }

  return (
    <Dialog
      open={!!notice}
      onOpenChange={open => { if (!open) close() }}
      title={t(notice?.title || '操作未完成')}
      actions={notice && (
        <>
          <Button onClick={() => void copy()}>{copied ? t('已复制') : t('复制完整原因')}</Button>
          {notice.context === 'map_catalog' && <Button onClick={showPageDetails}>{t('查看页面详情')}</Button>}
          <Button variant="cast" onClick={close} data-testid="notice-ok">{t('知道了')}</Button>
        </>
      )}
    >
      {notice && (
        <div className={s.body} data-testid="notice">
          <p className={s.reason}>{t(notice.diagnosis?.reason || notice.message)}</p>
          {!!notice.diagnosis?.recovery && <p className={s.reason}>{t(notice.diagnosis.recovery)}</p>}
          {!!notice.details?.length && (
            <section aria-label={t('具体原因')}>
              <h3 className={s.heading}>{t('具体原因')}</h3>
              {notice.details.map((d, i) => (
                <article key={i} className={s.detail}>
                  <strong>{d.scope} / {d.file}</strong>
                  <p>{d.message}</p>
                  {d.impact && <p>{d.impact}</p>}
                </article>
              ))}
            </section>
          )}
          {notice.logPath && (notice.diagnosis || !notice.message.includes(notice.logPath)) && (
            <p className={s.log}>{t('诊断日志')}：<span className={s.path}>{notice.logPath}</span></p>
          )}
          {notice.diagnosis?.logSaveFailed && <p className={s.reason}>{t('诊断日志未能保存，请检查日志目录。')}</p>}
          {copyFailed && <p role="alert" className={s.reason}>{t('无法写入剪贴板。可选中文字后按 Ctrl+C。')}</p>}
        </div>
      )}
    </Dialog>
  )
}
