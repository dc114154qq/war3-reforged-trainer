// Screenshot every page of the built app against the mock bridge (?mock=connected).
// Usage: node scripts/shoot-pages.mjs <out dir> [page id ...]   (after `npm run build`)
// SHOT_SIZE=800x480 sets the viewport, SHOT_QUERY=&lang=en adds to the URL, SHOT_NO_ACT=1 skips interactions.
import { chromium } from 'playwright-core'
import { spawn } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(fileURLToPath(new URL('..', import.meta.url)))
const [, , outArg, ...only] = process.argv
const outDir = resolve(outArg ?? resolve(root, 'shots'))
const PORT = 4318
const SIZE = (process.env.SHOT_SIZE ?? '1280x820').split('x').map(Number)

/** Per-page interactions shot as a second "-b" image, to show the page with data in it. */
const ACTIONS = {
  resources: async p => { await p.getByRole('button', { name: '锁定', exact: true }).first().click(); await p.getByRole('button', { name: '读取全图金矿' }).click(); await p.waitForTimeout(1500); await p.mouse.wheel(0, 600) },
  unit: async p => { await p.getByText('护甲', { exact: true }).click(); await p.mouse.wheel(0, 400) },
  batch: async p => { await p.getByRole('button', { name: '读取所有选中单位' }).first().click(); await p.waitForTimeout(1000); await p.getByRole('textbox').first().fill('2000'); await p.getByRole('button', { name: '批量修改' }).last().click(); await p.waitForTimeout(1200) },
  ability_fields: async p => { await p.getByRole('button', { name: '读取技能字段', exact: true }).first().click(); await p.waitForTimeout(900); await p.locator('[data-row="ab6"]').click() },
  item_fields: async p => { await p.getByRole('radio', { name: '装备加成 / 附带技能' }).click(); await p.getByRole('radio', { name: '3.0 装备栏' }).click(); await p.getByRole('button', { name: '主手' }).click(); await p.waitForTimeout(900) },
  extensions: async p => { await p.getByRole('button', { name: '补齐背包定义…' }).click(); await p.getByRole('button', { name: '选择文件（可多选）…' }).click(); await p.getByRole('button', { name: '立即补齐定义' }).click(); await p.waitForTimeout(1800) },
  elephant: async p => { await p.getByRole('button', { name: '全开视野' }).first().click(); await p.waitForTimeout(250) },
  hotkeys: async p => { await p.getByRole('radio', { name: /属性增强/ }).click(); await p.waitForTimeout(300) },
  catalogs: async p => { await p.locator('[role="row"][tabindex]').nth(1).click(); await p.waitForTimeout(400) },
  map_catalog: async p => { await p.getByRole('button', { name: '选择战役／地图…' }).first().click(); await p.getByRole('button', { name: '读取自定义目录' }).first().click(); await p.waitForTimeout(3600); await p.locator('[role="row"][tabindex]').first().click(); await p.waitForTimeout(500) },
  equipment3: async p => { await p.locator('[role="row"][tabindex]').first().click(); await p.waitForTimeout(400) },
  hero_skills: async p => { await p.locator('[role="row"][tabindex]').nth(2).click(); await p.waitForTimeout(400) },
  map_scripts: async p => { await p.getByRole('button', { name: '选择文件（可多选）…' }).click(); await p.getByRole('button', { name: '注入火龙功能脚本' }).last().click(); await p.waitForTimeout(1400) },
  archive: async p => { await p.getByRole('radio', { name: 'RPG 载入码' }).click(); await p.getByRole('button', { name: '从游戏内存扫描' }).last().click(); await p.waitForTimeout(2000) },
  locks: async p => { await p.getByRole('button', { name: '刷新' }).first().click(); await p.waitForTimeout(600) },
}
mkdirSync(outDir, { recursive: true })

const server = spawn(process.execPath, [resolve(root, 'node_modules/vite/bin/vite.js'), 'preview', '--port', String(PORT), '--strictPort'], { cwd: root })
await new Promise((ok, fail) => {
  const timer = setTimeout(() => fail(new Error('vite preview did not start')), 20000)
  server.stdout.on('data', d => { if (String(d).includes(String(PORT))) { clearTimeout(timer); ok() } })
  server.on('exit', code => fail(new Error(`vite preview exited ${code}`)))
})

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const errors = []
const page = await browser.newPage({ viewport: { width: SIZE[0], height: SIZE[1] } })
page.on('pageerror', e => errors.push(String(e)))
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })

try {
  await page.goto(`http://localhost:${PORT}/?mock=connected${process.env.SHOT_QUERY ?? ''}`)
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(800)
  const chapters = await page.locator('[data-testid^="chapter-"]').count()
  let n = 0
  for (let c = 0; c < chapters; c++) {
    // Narrow windows fold the chapters into a menu; click through the DOM as --ui-check does.
    await page.locator('[data-testid^="chapter-"]').nth(c).evaluate(el => el.click())
    await page.waitForTimeout(250)
    const tabs = await page.locator('[data-testid^="page-"]').count()
    for (let i = 0; i < Math.max(tabs, 1); i++) {
      if (tabs) await page.locator('[data-testid^="page-"]').nth(i).evaluate(el => el.click())
      await page.waitForTimeout(1100)
      const id = await page.locator('[data-testid="stage"]').getAttribute('data-page')
      n++
      if (only.length && !only.includes(id)) continue
      const name = `${String(n).padStart(2, '0')}-${id}`
      await page.screenshot({ path: resolve(outDir, `${name}.png`) })
      if (ACTIONS[id] && !process.env.SHOT_NO_ACT) {
        try { await ACTIONS[id](page); await page.waitForTimeout(500); await page.screenshot({ path: resolve(outDir, `${name}-b.png`) }) }
        catch (e) { errors.push(`${id} action: ${e.message.split('\n')[0]}`) }
        // Close whatever the action opened (dialogs, editors) before moving on.
        await page.keyboard.press('Escape')
        await page.waitForTimeout(300)
      }
    }
  }
} finally {
  await browser.close()
  server.kill()
}
console.log(errors.length ? `page errors:\n${errors.join('\n')}` : 'no page errors')
