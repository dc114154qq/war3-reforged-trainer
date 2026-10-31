import { Commands } from './Commands'
import { Controls } from './Controls'
import { Frames, Palette, Type } from './Foundations'
import { Icons } from './Icons'
import { Dialogs, Rules } from './Misc'
import { Motion } from './Motion'
import { Values } from './Values'
import s from './sg.module.css'

const NAV = [
  ['palette', '色板'], ['type', '字体'], ['frames', '边框'], ['icons', '图标'], ['controls', '控件'],
  ['values', '数值'], ['commands', '命令卡'], ['motion', '动效'], ['dialogs', '对话框'], ['rules', '规则'],
]

export function StyleGuide() {
  return (
    <div className={`ds-stage ${s.page}`}>
      <header className={`ds-metal ${s.top}`}>
        <span className={s.brand}>设计系统</span>
        <nav className={s.nav} aria-label="章节">
          {NAV.map(([id, label]) => <a key={id} href={`#${id}`}>{label}</a>)}
        </nav>
      </header>
      <main className={s.main}>
        <div className={s.intro}>
          <h1 className={s.title}>魔兽争霸 III 修改器 设计系统</h1>
          <p className={s.lead}>
            阶段 1 的全部组件都在这一页，每个都能直接操作。页面代码只从 src/ds 引入这些组件和变量。
          </p>
        </div>
        <Palette />
        <Type />
        <Frames />
        <Icons />
        <Controls />
        <Values />
        <Commands />
        <Motion />
        <Dialogs />
        <Rules />
      </main>
    </div>
  )
}
