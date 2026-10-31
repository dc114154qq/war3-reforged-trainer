import { useState } from 'react'
import { Button, Dialog, DialogClose, RawcodePlate, announce } from '../ds'
import { Demo, Section } from './Section'
import s from './sg.module.css'

export function Dialogs() {
  const [open, setOpen] = useState(false)
  return (
    <Section id="dialogs" title="对话框" lead="游戏菜单样式：黑铁标题栏、双线角花、羊皮纸正文。Esc 或点遮罩关闭，焦点锁在框内。">
      <div className={s.demoGrid}>
        <Demo title="错误详情">
          <Button onClick={() => setOpen(true)}>打开对话框</Button>
          <Dialog
            open={open}
            onOpenChange={setOpen}
            title="写入失败"
            description="游戏拒绝了这次写入，字段没有改动。"
            actions={(
              <>
                <DialogClose asChild><Button>关闭</Button></DialogClose>
                <Button variant="cast" onClick={() => { setOpen(false); announce('已重新读取单位') }}>重新读取单位</Button>
              </>
            )}
          >
            <p className={s.docText}>
              字段 <RawcodePlate code="Hpal" /> 的地址在读取之后发生了变化，通常是单位刚刚死亡或被替换。重新读取单位后再写一次。
            </p>
          </Dialog>
        </Demo>
      </div>
    </Section>
  )
}

const RULES = [
  ['金色只给数字', '资源、刚改过的值、热键字母。边框、标题和选中状态用青铜。'],
  ['装饰只在框角', '内容区保持平整；不在输入框和表格上加花边。'],
  ['动画回应操作', '每个动画都要说明刚刚发生了什么。没有呼吸灯、飘浮粒子和逐块淡入。'],
  ['失焦就停', '窗口失去焦点时 CSS 动画暂停，轮询驱动的动画和模拟也要停（useWindowFocused）。'],
  ['游戏文字用 600', '从游戏读出的名字只用半粗：只有 600 带名字字库，900 只用于固定文案和数字。'],
  ['页面切换别吞动画', '包住整页的 AnimatePresence 不要写 initial={false}，它会顺着上下文关掉页内所有元素的进场动画。'],
  ['文案说清楚', '按钮写会发生什么；成功提示和按钮用同一个词；错误说哪里错、怎么办。'],
]

export function Rules() {
  return (
    <Section id="rules" title="使用规则" lead="写页面时对照。界面上任何一个元素都要能回答：它在魔兽里对应什么，或者它解决了什么使用问题。">
      <dl className={s.rules}>
        {RULES.map(([t, d]) => (
          <div key={t}>
            <dt>{t}</dt>
            <dd>{d}</dd>
          </div>
        ))}
      </dl>
    </Section>
  )
}
