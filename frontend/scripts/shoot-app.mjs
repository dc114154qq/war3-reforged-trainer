// Screenshots of the built app shell against the mock bridge (?mock), in the system Edge.
// Usage: node scripts/shoot-app.mjs <out dir>     (after `npm run build`)
import { chromium } from 'playwright-core'
import { spawn } from 'node:child_process'
import { mkdirSync, rmSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(fileURLToPath(new URL('..', import.meta.url)))
const outDir = resolve(process.argv[2] ?? resolve(root, 'shots'))
const PORT = 4317
rmSync(outDir, { recursive: true, force: true })
mkdirSync(outDir, { recursive: true })

// The multi-file build needs http (module scripts do not load from file://), as in pywebview.
const server = spawn(process.execPath, [resolve(root, 'node_modules/vite/bin/vite.js'), 'preview', '--port', String(PORT), '--strictPort'], { cwd: root })
await new Promise((ok, fail) => {
  const timer = setTimeout(() => fail(new Error('vite preview did not start')), 20000)
  server.stdout.on('data', d => { if (String(d).includes(String(PORT))) { clearTimeout(timer); ok() } })
  server.on('exit', code => fail(new Error(`vite preview exited ${code}`)))
})

const base = `http://localhost:${PORT}/`
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const errors = []

async function open(width, height, query) {
  const page = await browser.newPage({ viewport: { width, height } })
  page.on('pageerror', e => errors.push(String(e)))
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
  await page.goto(base + query)
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(900)
  return page
}
const shot = (page, name) => page.screenshot({ path: resolve(outDir, `${name}.png`) })
const sel = id => `[data-testid="${id}"]`

try {
  // Waiting, then the connect reveal caught midway.
  let page = await open(1280, 820, '?mock')
  await shot(page, '01-未连接')
  await page.click(sel('connect'))
  await page.waitForTimeout(900 + 500)
  await shot(page, '02-连接时迷雾散开')
  await page.waitForTimeout(1500)
  await shot(page, '03-已连接')

  // Chat: suggestions, then a command and its result.
  await page.mouse.move(640, 400)
  await page.keyboard.press('Enter')
  await page.keyboard.type('加', { delay: 30 })
  await page.waitForTimeout(250)
  await shot(page, '04-聊天框指令提示')
  await page.keyboard.type('金木 5000', { delay: 30 })
  await page.keyboard.press('Enter')
  await page.waitForTimeout(650)
  await shot(page, '05-加金木后飘字')
  await page.waitForTimeout(2600)

  // Q on the command card: read all selected units.
  await page.hover(sel('cmd-Q'))
  await page.keyboard.press('q')
  await page.waitForTimeout(350)
  await shot(page, '06-命令卡读取中')
  await page.waitForTimeout(900)

  // System menu.
  await page.click(sel('system-menu'))
  await page.waitForTimeout(300)
  await shot(page, '07-系统菜单')
  await page.keyboard.press('Escape')

  // A failure with a log path, as the backend reports it.
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('war3-error', { detail: {
    title: '写入失败',
    message: '游戏拒绝了这次写入，字段没有改动。通常是单位刚刚死亡或被替换，重新读取单位后再写一次。',
    logPath: 'C:\\Users\\player\\AppData\\Local\\War3ReforgedTrainer\\logs\\write_unit_field-20261028.log',
  } })))
  await page.waitForTimeout(400)
  await shot(page, '08-错误对话框')
  await page.click(sel('notice-ok'))
  await page.waitForTimeout(300)

  // English.
  await page.click(sel('system-menu'))
  await page.getByRole('radio', { name: 'English' }).click()
  await page.keyboard.press('Escape')
  await page.waitForTimeout(500)
  await page.click(sel('chapter-codex'))
  await page.waitForTimeout(400)
  await shot(page, '09-英文')
  await page.close()

  // Smallest window.
  page = await open(800, 480, '?mock=connected')
  await shot(page, '10-最小窗口800x480')
  await page.close()
} finally {
  await browser.close()
  server.kill()
}
console.log(errors.length ? `page errors:\n${errors.join('\n')}` : 'no page errors')
