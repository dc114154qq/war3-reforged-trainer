import { useEffect, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { Button, Keycap, ProgressBar, TextField } from '../../../ds'
import { api, type MapScriptOptions, type MapScriptProgress } from '../../../lib/api'
import { useCatalogName } from '../../state/catalog'
import { useCommandCard } from '../../state/commands'
import { fill, useT } from '../../i18n'
import { FileResults, PathFields, copyText, splitPaths, usePolledJob } from '../common/Jobs'
import { PageBody, Section } from '../common/Layout'
import s from './MapScriptsPage.module.css'

const MENUS: [string, string][] = [
  ['原版菜单与按键', '保留资源、自动化、单位属性、个人设置、玩家管理和帮助'],
  ['原主菜单翻页', '直接在火龙原主菜单增加功能，每页最多 6 项；没有另一个增强主菜单'],
  ['地图目录', '物品、技能、单位召唤与科技，包含当前章节的自定义内容'],
  ['物品与英雄', '六神器方案、具体物品槽操作、英雄成长与批量修改'],
  ['传送与资源', '位置标记、返回上次位置、部队集合、资源最低值与金矿金额'],
  ['自动项与结果', '绑定启用时的选择，血魔阈值、停止开关、收藏与执行结果'],
]
const STAGES: Record<string, string> = {
  queued: '准备处理', source_hash_begin: '核对输入文件', start: '复制并保留原文件', definitions_begin: '补齐 3.0 背包定义',
  definitions_complete: '背包定义补齐完成', catalogue_begin: '读取当前地图定义', script_baseline_check: '检查原始脚本',
  script_compile: '检查加入后的脚本', script_write: '写入功能脚本', chapter_begin: '处理章节', chapter_verified: '章节校验完成',
  archive_verify: '独立读回归档', verify_member: '核对原有文件', replace_chapter: '保存战役章节', verified: '完成最终校验', complete: '处理结束',
}
const STATES: Record<string, string> = {
  succeeded: '处理完成', failed: '处理失败', partial: '部分文件处理失败', cancelled: '处理已停止，成功的副本已保留',
}
const DEFAULT_OPTIONS: MapScriptOptions = {
  prefix: '-mx', features: ['resources', 'hero', 'units', 'abilities', 'items', 'automatic', 'world'],
  artifact_codes: ['klmm', 'srtl', 'shdt', 'crdt', 'frhg', 'nspi'], resource_amount: 10000,
}

const fileName = (path: string) => path.split(/[\\/]/).pop()?.replace(/\.\w+$/, '') ?? path

/**
 * Write the classic HKE 1.25B functions into a copy of a map or campaign. While the job runs
 * the page shows a loading screen: the map's name, a long bar and the current step underneath.
 */
export default function MapScriptsPage() {
  const t = useT()
  const reduce = useReducedMotion()
  const { progress, setProgress, poll, busy } = usePolledJob<MapScriptProgress>(id => api.getMapScriptProgress(id), { jobId: '', status: 'idle', elapsed: 0 }, 300)
  const [paths, setPaths] = useState('')
  const [folder, setFolder] = useState('')
  const [options, setOptions] = useState<MapScriptOptions>(DEFAULT_OPTIONS)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [starting, setStarting] = useState(false)
  const selected = splitPaths(paths)
  const working = starting || busy

  useEffect(() => {
    let live = true
    api.getMapScriptOptions().then(r => { if (live && r?.success) setOptions(r.options) }).catch(() => {})
    return () => { live = false }
  }, [])

  const start = async (combined: boolean) => {
    setStarting(true)
    try {
      const r = await api.startMapScripts(selected, folder, options, combined)
      if (r?.success) await poll(r.jobId)
    } catch { /* reported by callApi */ } finally {
      setStarting(false)
    }
  }
  const stop = async () => {
    try {
      const r = await api.cancelMapScripts(progress.jobId)
      if (r?.success) setProgress(p => ({ ...p, status: 'cancelling' }))
    } catch { /* reported by callApi */ }
  }
  const savePlan = async () => {
    setSaving(true)
    setSaved(false)
    try {
      const r = await api.saveMapScriptOptions(options)
      if (r?.success) { setOptions(r.options); setSaved(true) }
    } catch { /* reported by callApi */ } finally {
      setSaving(false)
    }
  }
  const setCode = (i: number, code: string) => {
    setSaved(false)
    setOptions(o => ({ ...o, artifact_codes: o.artifact_codes.map((c, j) => (j === i ? code : c)) }))
  }

  const step = progress.stage?.startsWith('definitions_') ? '补齐 3.0 背包定义'
    : progress.stage?.startsWith('catalogue_') ? '读取当前地图定义'
    : STAGES[progress.stage ?? ''] ?? '正在检查文件'
  const headline = progress.status === 'cancelling' ? '正在停止，请稍候…' : busy ? step : STATES[progress.status] ?? ''
  const files = (progress.files ?? []).map(f => ({ ...f, error: f.error ? progress.failures?.find(x => x.source === f.source)?.reason || f.error : '' }))

  useCommandCard([
    { key: 'Q', icon: 'scripts', title: t('注入火龙功能脚本'), description: t('把火龙功能写进选中地图或战役的副本，原文件保留。'), pending: working, estimateMs: 12000, disabled: !selected.length, onPress: () => void start(false) },
    { key: 'W', icon: 'map-data', title: t('补齐 3.0 背包定义并注入火龙'), description: t('生成用于 3.0 的副本：先补齐背包定义，再注入火龙功能。'), pending: working, estimateMs: 16000, disabled: !selected.length, onPress: () => void start(true) },
    { key: 'E', icon: 'save', title: t('保存六神器方案'), description: t('保存六个神器代码，下次打开仍保留。'), pending: saving, onPress: () => void savePlan() },
    { key: 'R', icon: 'cancel', title: t('停止处理'), description: t('停止正在进行的处理；已完成的副本会保留。'), disabled: !busy || progress.status === 'cancelling', onPress: () => void stop() },
  ])

  return (
    <PageBody>
      <div className={s.intro}>
        <p className={s.lead}>{t('把经典版火龙修改器（HKE 1.25B）的功能写进地图或战役副本。处理完可以关掉修改器，在游戏里用菜单或命令独立操作。原文件保留，不需要启动游戏。')}</p>
        <p className={s.note}>{t('支持本地单人 JASS 地图和战役，暂不支持 Lua。3.0 背包继续用本修改器的专用功能，脚本不接管背包和扩展装备。')}</p>
      </div>

      <section className={s.activation} aria-label={t('游戏内激活方法')}>
        <div className={s.combo}>
          <span className={s.comboLabel}>{t('进入副本后依次按')}</span>
          <Keycap>↑</Keycap><Keycap>↑</Keycap><Keycap>←</Keycap><Keycap>↓</Keycap>
          <span className={s.comboLabel}>{t('激活')}</span>
        </div>
        <p>{t('激活后先按 ↑ 再在 1 秒内按 Esc 呼出主菜单；先按 ↑ 再双击单位呼出单位菜单。')}</p>
        <ul className={s.commands}>
          <li><code>-h</code>{t('键盘帮助')}</li>
          <li><code>-c</code>{t('命令帮助')}</li>
          <li><code>-u</code>{t('单位命令')}</li>
        </ul>
      </section>

      <AnimatePresence initial={false}>
        {progress.status !== 'idle' && (
          <motion.section
            key="loading"
            className={s.loading}
            data-state={busy ? 'running' : progress.status}
            aria-live="polite"
            initial={reduce ? { opacity: 0 } : { opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <p className={s.mapName}>{fileName(progress.currentFile || selected[0] || '')}</p>
            <ProgressBar
              className={s.bar}
              label={t('脚本文件处理进度')}
              value={(progress.fileCompleted ?? 0) + (busy && progress.total ? (progress.completed ?? 0) / progress.total : 0)}
              max={progress.fileTotal || 1}
            />
            <div className={s.tipLine}>
              <span className={s.tip}>{t(headline)}{busy && progress.chapter ? `　${progress.chapter}` : ''}</span>
              <span>{fill(t('文件 {done} / {total}　已用 {n} 秒'), { done: progress.fileCompleted ?? 0, total: progress.fileTotal ?? 0, n: progress.elapsed.toFixed(1) })}</span>
            </div>
            {progress.logPath && <p className={s.path}>{t('处理日志：')}{progress.logPath}</p>}
            {busy && <Button variant="danger" size="sm" className={s.stop} disabled={progress.status === 'cancelling'} onClick={() => void stop()}>{t('停止处理')}</Button>}
          </motion.section>
        )}
      </AnimatePresence>

      {files.length > 0 && (
        <FileResults
          files={files}
          extra={f => f.destination && (
            <>
              <span className={s.resultNote}>{t('功能脚本已写入副本，进入游戏后可以独立使用。')}</span>
              {'usagePath' in f && f.usagePath && (
                <span className={s.usage}>
                  <span className={s.path}>{t('游戏内命令说明：')}{f.usagePath}</span>
                  <Button size="sm" icon="copy" onClick={() => void copyText(f.usagePath!, t('已复制完整路径'))}>{t('复制说明路径')}</Button>
                </span>
              )}
            </>
          )}
        />
      )}

      <Section title={t('地图与输出')}>
        <fieldset className={s.fieldset} disabled={working}>
          <PathFields
            paths={paths}
            onPaths={setPaths}
            folder={folder}
            onFolder={setFolder}
            disabled={working}
            filesLabel={t('地图或战役文件（每行一个）')}
            placeholder={t('支持 .w3n / .w3x / .w3m，每行一个完整路径')}
            folderLabel={t('输出文件夹（留空则放在原文件旁边）')}
          />
        </fieldset>
        <div className={s.actions}>
          <Button variant="cast" icon="scripts" disabled={working || !selected.length} onClick={() => void start(false)}>{t('注入火龙功能脚本')}</Button>
          <Button icon="map-data" disabled={working || !selected.length} onClick={() => void start(true)}>{t('补齐 3.0 背包定义并注入火龙')}</Button>
        </div>
        <p className={s.note}>{t('组合按钮生成用于 3.0 的副本，已有背包定义会保留；单独注入火龙不需要 3.0。功能来自 HkeW3mModifier 2.06 附带的原版 HKE 1.25B，原作者为火龙 / WuHansen。')}</p>
      </Section>

      <Section title={t('火龙主菜单里的六神器方案')}>
        <p className={s.note}>{t('填 6 个普通物品代码，注入时一起写进地图。游戏里点“领取六神器方案”即可；物品栏满时不会删除原物品。保存后下次打开仍保留。')}</p>
        <fieldset className={s.fieldset} disabled={working}>
          <div className={s.artifacts}>
            {options.artifact_codes.map((code, i) => <ArtifactCode key={i} index={i} code={code} onChange={v => setCode(i, v)} />)}
          </div>
          <Button size="sm" icon="save" disabled={saving} onClick={() => void savePlan()}>{saving ? t('正在保存…') : saved ? t('方案已保存') : t('保存六神器方案')}</Button>
        </fieldset>
      </Section>

      <Section title={t('写进地图的菜单')}>
        <dl className={s.menus}>
          {MENUS.map(([name, detail]) => (
            <div key={name} className={s.menu}>
              <dt>{t(name)}</dt>
              <dd>{t(detail)}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <details className={s.details}>
        <summary>{t('使用与兼容说明')}</summary>
        <p>{t('功能和参数随地图保存，游戏内操作不会请求修改器。旧存档不会自动得到新脚本，请从新副本的章节入口进入。')}</p>
        <p>{t('新增功能直接位于火龙原主菜单，用上一页／下一页切换。目录中可以搜索名称或代码，精确数值按游戏内提示输入；位置、收藏和最近记录限当前章节。不增加镜头设置、操作目标管理或单位信息页。')}</p>
        <p>{t('方向键、命令与原版正常功能保留。地图本身未定义的单位、技能或物品不能凭空补出；地图自身的触发器仍可能覆盖修改。目录在进入章节后分批准备。')}</p>
        <p>{t('已有 3.0 背包的单位会跳过火龙额外背包切换；3.0 背包控制能力与载体受到保护。其他功能也不复制 3.0 扩展槽、天赋及剧情私有状态。')}</p>
        <p>{t('兼容处理保留地图用于识别单位的数据，隔离脚本名称，并移除了旧脚本的隐藏接管命令和标题校验递归计时器。')}</p>
      </details>
    </PageBody>
  )
}

function ArtifactCode({ index, code, onChange }: { index: number; code: string; onChange(code: string): void }) {
  const t = useT()
  const name = useCatalogName('item', code.trim())
  return (
    <label className={s.artifact}>
      <span className={s.artifactLabel}>{fill(t('第 {n} 件'), { n: index + 1 })}</span>
      <TextField aria-label={fill(t('火龙神器代码 {n}'), { n: index + 1 })} className={s.artifactCode} maxLength={4} spellCheck={false} value={code} onChange={e => onChange(e.target.value)} />
      <span className={s.artifactName}>{name ?? ''}</span>
    </label>
  )
}
