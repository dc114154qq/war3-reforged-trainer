import { useLayoutEffect, useRef, useState } from 'react'
import { Frame, PLAYER_COLORS, PLAYER_NAMES, QUALITY_LABEL, RollingNumber, type Quality } from '../ds'
import { Demo, Section } from './Section'
import s from './sg.module.css'

const CORE = [
  { name: '夜幕', token: '--nightfall', hex: '#121A2B', use: '舞台底色，取自游戏提示框的深海军蓝' },
  { name: '黑铁', token: '--iron', hex: '#26221E', use: '顶带、操作台、按钮底座' },
  { name: '青铜', token: '--bronze', hex: '#B08A4E', use: '框线、分隔、焦点、选中标记' },
  { name: '金币', token: '--gold', hex: '#FFDC00', use: '只用于数字：资源、改动的值、热键字母' },
  { name: '羊皮纸', token: '--vellum', hex: '#E4D3AA', use: '对话框正文、详情抽屉' },
  { name: '白骨', token: '--bone', hex: '#EAE3D2', use: '深色上的正文' },
]

const GAME = [
  { name: '木材', token: '--lumber', use: '木材飘字、成功' },
  { name: '法力', token: '--mana', use: '魔法条' },
  { name: '冰封', token: '--frost', use: '锁定的值' },
  { name: '鲜血', token: '--blood', use: '危险操作' },
  { name: '经验', token: '--xp', use: '英雄经验条' },
  { name: '加成', token: '--bonus', use: '装备加成 +12' },
  { name: '友方', token: '--select-ally', use: '选择圈' },
  { name: '中立', token: '--select-neutral', use: '选择圈、悬停' },
  { name: '敌方', token: '--select-enemy', use: '选择圈' },
]

const TEXT_ROLES = [
  { token: '--text-primary', sample: '正文、字段名' },
  { token: '--text-secondary', sample: '说明文字' },
  { token: '--text-tertiary', sample: '表头、单位、次要标注' },
  { token: '--text-label', sample: '分组标题' },
  { token: '--text-value', sample: '18500' },
]

/* WCAG contrast of a rendered text colour over the stage colour, blending alpha first. */
function contrastOnStage(color: string): number {
  const m = color.match(/rgba?\(([^)]+)\)/)
  if (!m) return 0
  const [r, g, b, a = 1] = m[1].split(/[ ,/]+/).filter(Boolean).map(Number)
  const stage = [0x12, 0x1a, 0x2b]
  const mix = [r, g, b].map((c, i) => c * a + stage[i] * (1 - a))
  const lum = (rgb: number[]) => {
    const [x, y, z] = rgb.map(c => { const v = c / 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4 })
    return 0.2126 * x + 0.7152 * y + 0.0722 * z
  }
  const l1 = lum(mix), l2 = lum(stage)
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)
}

function TextRoles() {
  const refs = useRef<Array<HTMLSpanElement | null>>([])
  const [ratios, setRatios] = useState<number[]>([])
  useLayoutEffect(() => {
    setRatios(refs.current.map(el => (el ? contrastOnStage(getComputedStyle(el).color) : 0)))
  }, [])
  return (
    <ul className={s.roles}>
      {TEXT_ROLES.map((r, i) => (
        <li key={r.token}>
          <span ref={el => { refs.current[i] = el }} style={{ color: `var(${r.token})` }} className={s.roleSample}>{r.sample}</span>
          <code className={s.token}>{r.token}</code>
          <span className={s.ratio}>{ratios[i] ? `${ratios[i].toFixed(1)}:1` : ''}</span>
        </li>
      ))}
    </ul>
  )
}

export function Palette() {
  return (
    <Section id="palette" title="色板" lead="六个核心色，加上直接取自游戏的语义色。组件只用语义变量，不直接写色值。">
      <div className={s.coreGrid}>
        {CORE.map(c => (
          <figure key={c.token} className={s.core}>
            <span className={s.chip} style={{ background: `var(${c.token})` }} />
            <figcaption>
              <span className={s.coreName}>{c.name}</span>
              <code className={s.token}>{c.hex}</code>
              <span className={s.coreUse}>{c.use}</span>
            </figcaption>
          </figure>
        ))}
      </div>

      <div className={s.demoGrid}>
        <Demo title="游戏语义色">
          <ul className={s.swatchList}>
            {GAME.map(g => (
              <li key={g.token}>
                <i style={{ background: `var(${g.token})` }} />
                <span>{g.name}</span>
                <span className={s.dim}>{g.use}</span>
              </li>
            ))}
          </ul>
        </Demo>
        <Demo title="文字层级" note="比值是在舞台底色上实测的对比度，正文要求 4.5:1 以上。">
          <TextRoles />
        </Demo>
        <Demo title="物品品质" note="用于装备目录的名称着色。">
          <ul className={s.qualityList}>
            {(Object.keys(QUALITY_LABEL) as Quality[]).map(q => (
              <li key={q} style={{ color: `var(--quality-${q})` }}>{QUALITY_LABEL[q]}之刃</li>
            ))}
          </ul>
        </Demo>
        <Demo title="玩家颜色" note="资源组和小地图按玩家槽位着色。">
          <ul className={s.players}>
            {PLAYER_COLORS.map((c, i) => (
              <li key={c}><i style={{ background: c }} />{i + 1} {PLAYER_NAMES[i]}</li>
            ))}
          </ul>
        </Demo>
      </div>
    </Section>
  )
}

// Built from code points so most of these characters stay out of the source text, and
// therefore out of the UI subset: they render through the lazily loaded names subset.
const GAME_NAME = String.fromCodePoint(0x725b, 0x5934, 0x4eba, 0x914b, 0x957f, 0x0020, 0x51ef, 0x6069, 0x00b7, 0x8840, 0x8e44)

export function Type() {
  return (
    <Section id="type" title="字体" lead="两种字体：思源宋体负责标题、章节名和大数字，微软雅黑负责正文和数据。Consolas 只用于地址和四字符 ID。">
      <div className={s.typeGrid}>
        <div className={s.specimen}>
          <span className={s.specLabel}>思源宋体 特粗 900，页名</span>
          <span className={s.spec900}>选中单位</span>
        </div>
        <div className={s.specimen}>
          <span className={s.specLabel}>思源宋体 半粗 600，章节、按钮、数值</span>
          <span className={s.spec600}>战况 字段 大象 典籍 火龙 存档</span>
        </div>
        <div className={s.specimen}>
          <span className={s.specLabel}>大数字 72px，金币色</span>
          <span className={s.specBig}><RollingNumber text="18500" /></span>
        </div>
        <div className={s.specimen}>
          <span className={s.specLabel}>微软雅黑 14px，正文</span>
          <span className={s.specSans}>只改等级不会补发技能点，技能点要另外修改。</span>
        </div>
        <div className={s.specimen}>
          <span className={s.specLabel}>Consolas，只用于数据</span>
          <span className={s.specMono}>0x24A8F120　Hpal　AHbz</span>
        </div>
        <div className={s.specimen}>
          <span className={s.specLabel}>游戏里读出的名字，半粗 600，按需加载的名字字库</span>
          <span className={s.spec600}>{GAME_NAME}</span>
        </div>
      </div>
      <ol className={s.scale}>
        {[['12', '表头、次要标注'], ['13', '说明、药丸'], ['14', '正文基准'], ['15', '衬线标签'], ['16', '字段值'], ['21', '对话框标题'], ['28', '页名'], ['48', '统计数字'], ['72', '资源大数字']].map(([px, use]) => (
          <li key={px}><span className={s.scalePx}>{px}</span><span className={s.dim}>{use}</span></li>
        ))}
      </ol>
    </Section>
  )
}

export function Frames() {
  return (
    <Section id="frames" title="边框与材质" lead="装饰只出现在框角。九宫格 SVG 边框画在覆盖层上，宿主自己的背景不会遮住角饰。">
      <div className={s.demoGrid}>
        <Demo title="ornate 角饰框" note="提示框、小地图、头像、详情。">
          <Frame className={s.frameSample}>
            <p className={s.frameText}>阿尔萨斯王子</p>
            <p className={s.dim}>边线是发丝线，四角是青铜卡角。</p>
          </Frame>
        </Demo>
        <Demo title="grand 双线框" note="只用于对话框。">
          <Frame variant="grand" className={s.frameSample}>
            <p className={s.frameText}>强制结束对局</p>
            <p className={s.dim}>双线加铸造角花。</p>
          </Frame>
        </Demo>
        <Demo title="凹槽" note="命令卡底座、输入框、状态条轨道。">
          <div className={`ds-well ${s.wellSample}`} />
        </Demo>
        <Demo title="黑铁与铜沿" note="顶带和操作台。">
          <div className={`ds-metal ds-rim-top ${s.metalSample}`} />
        </Demo>
      </div>
    </Section>
  )
}
