// Screenshots of the built style guide in the system Edge, for design review.
// Usage: node scripts/shoot-styleguide.mjs [out dir]   (after `npm run build:styleguide`)
import { chromium } from 'playwright-core'
import { mkdirSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = resolve(fileURLToPath(new URL('..', import.meta.url)))
const outDir = resolve(process.argv[2] ?? resolve(root, '截图'))
const url = pathToFileURL(resolve(root, 'dist-styleguide/styleguide.html')).href
rmSync(outDir, { recursive: true, force: true })
mkdirSync(outDir, { recursive: true })

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
const errors = []
page.on('pageerror', e => errors.push(String(e)))
page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') errors.push(`${m.type()}: ${m.text()}`) })
await page.goto(url)
await page.evaluate(() => document.fonts.ready)
await page.waitForTimeout(500)

const shot = (name, opts = {}) => page.screenshot({ path: resolve(outDir, `${name}.png`), ...opts })
const section = async (id, name) => {
  const el = page.locator(`#${id}`)
  await el.scrollIntoViewIfNeeded()
  await page.waitForTimeout(150)
  await el.screenshot({ path: resolve(outDir, `${name}.png`) })
}

await shot('00-整页', { fullPage: true })
await section('palette', '01-色板')
await section('type', '02-字体')
await section('frames', '03-边框')
await section('icons', '04-图标')
await section('controls', '05-控件')

// Values: lock a row, edit another and catch the bounty text, damage the life bar.
await page.locator('#values').scrollIntoViewIfNeeded()
await page.click('button[aria-label="锁定力量"]')
await page.click('button[aria-label^="当前生命"]')
await page.fill('#values input', '980')
await page.keyboard.press('Enter')
await page.getByRole('button', { name: '受到伤害' }).click()
await page.waitForTimeout(260)
await section('values', '06-数值-锁定飘字掉血')

// Command card: hover for the tooltip, start a long call (S) and a toggle (D).
await page.locator('#commands').scrollIntoViewIfNeeded()
await page.click('[data-testid="cmd-D"]')
await page.click('[data-testid="cmd-S"]')
await page.hover('[data-testid="cmd-Q"]')
await page.waitForTimeout(900)
await section('commands', '07-命令卡-提示框与转圈')
const card = page.locator('[aria-label="命令卡"]')
await page.waitForTimeout(400)
await card.screenshot({ path: resolve(outDir, '08-命令卡-S停在九成等结果.png') })

// Motion: select an enemy, hold to confirm halfway, reveal the fog midway.
await page.locator('#motion').scrollIntoViewIfNeeded()
await page.getByRole('radio', { name: '敌方' }).click()
await page.click('button[title="狮鹫骑士"]')
await page.mouse.move(0, 0)
const hold = page.getByRole('button', { name: /强制结束对局/ })
const hb = await hold.boundingBox()
await page.mouse.move(hb.x + hb.width / 2, hb.y + hb.height / 2)
await page.mouse.down()
await page.waitForTimeout(330)
await section('motion', '09-动效-选择圈与长按确认')
await page.mouse.up()
await page.waitForTimeout(300)

await page.locator('#motion').getByRole('button', { name: '连接游戏' }).click()
await page.waitForTimeout(700 + 520)
await page.locator('#motion [class*="fogBox"]').screenshot({ path: resolve(outDir, '10-动效-迷雾散开中.png') }).catch(() => {})
await page.waitForTimeout(1200)

// Dialog.
await page.locator('#dialogs').scrollIntoViewIfNeeded()
await page.getByRole('button', { name: '打开对话框' }).click()
await page.waitForTimeout(400)
await shot('11-对话框')
await page.keyboard.press('Escape')

// Narrow window.
await page.setViewportSize({ width: 820, height: 900 })
await page.goto(url)
await page.evaluate(() => document.fonts.ready)
await page.waitForTimeout(400)
await shot('12-窄窗口820')

await browser.close()
console.log(errors.length ? `console:\n${errors.join('\n')}` : 'no page errors or warnings')
