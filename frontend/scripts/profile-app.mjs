// Measure interaction latency in the real desktop window (WebView2 + Python bridge, no game).
// Usage: node scripts/profile-app.mjs [out.json] [--cpu]   (from frontend/, after `npm run build`)
// WebView2 is started with a DevTools port; Playwright attaches over CDP and times each step
// from the click to the moment its result is on screen (next frame after the DOM settles).
import { chromium } from 'playwright-core'
import { spawn } from 'node:child_process'
import { writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)))
const out = process.argv.find(a => a.endsWith('.json'))
const cpu = process.argv.includes('--cpu')
const PORT = 9333

const app = spawn('python', process.env.TRACE_LOCK ? ['tools/trace_dispatch_lock.py'] : ['war3_web_gui.py'], {
  cwd: root,
  env: { ...process.env, WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS: `--remote-debugging-port=${PORT}` },
  stdio: 'ignore',
})

async function attach() {
  for (let i = 0; i < 80; i++) {
    try { return await chromium.connectOverCDP(`http://127.0.0.1:${PORT}`) } catch { await new Promise(r => setTimeout(r, 250)) }
  }
  throw new Error('WebView2 DevTools port did not open')
}

const results = []
let browser
try {
  browser = await attach()
  const page = browser.contexts()[0].pages().find(p => p.url().includes('index.html')) ?? browser.contexts()[0].pages()[0]
  await page.waitForSelector('[data-testid="stage"]')
  await page.waitForTimeout(2500)
  await page.evaluate(() => {
    window.__long = []
    new PerformanceObserver(l => { for (const e of l.getEntries()) window.__long.push({ start: e.startTime, ms: e.duration }) }).observe({ type: 'longtask', buffered: true })
  })
  // Time every bridge call from the page's side: start, end and which call it was.
  await page.evaluate(() => {
    window.__calls = []
    const api = window.pywebview.api
    for (const name of Object.keys(api)) {
      const fn = api[name]
      if (typeof fn !== 'function') continue
      api[name] = (...args) => {
        const start = performance.now()
        const p = fn(...args)
        Promise.resolve(p).finally(() => window.__calls.push({ name, start, ms: performance.now() - start }))
        return p
      }
    }
  })
  const session = cpu ? await page.context().newCDPSession(page) : null
  if (session) { await session.send('Profiler.enable'); await session.send('Profiler.setSamplingInterval', { interval: 200 }) }

  /** Click, then wait until `done` holds and one more frame has painted. */
  async function step(label, selector, done, { profile = false } = {}) {
    await page.waitForTimeout(400)
    await page.evaluate(() => { window.__long = []; window.__calls = [] })
    if (profile && session) await session.send('Profiler.start')
    const t0 = await page.evaluate(() => performance.now())
    await page.locator(selector).first().evaluate(el => el.click())
    const t1 = await page.evaluate(async src => {
      const check = new Function(`return (${src})()`)
      const deadline = performance.now() + 8000
      while (!check() && performance.now() < deadline) await new Promise(r => setTimeout(r, 4))
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))
      return performance.now()
    }, done.toString())
    let hot
    if (profile && session) {
      const { profile: p } = await session.send('Profiler.stop')
      hot = topFunctions(p)
    }
    const long = await page.evaluate(() => window.__long)
    const calls = (await page.evaluate(() => window.__calls)).map(c => `${c.name} ${Math.round(c.ms)}`)
    const row = { label, ms: Math.round(t1 - t0), longTasks: long.map(l => Math.round(l.ms)), calls, hot }
    results.push(row)
    console.log(`${label.padEnd(34)} ${String(row.ms).padStart(6)} ms   long tasks ${JSON.stringify(row.longTasks)}`)
    console.log(`      calls: ${calls.join(', ')}`)
    if (hot) for (const h of hot.slice(0, 12)) console.log(`      ${String(h.ms).padStart(6)} ms  ${h.name}  ${h.url}`)
  }

  // Idle cost: what the page spends per second when nobody touches it (polling, animations).
  const metrics = await page.context().newCDPSession(page)
  await metrics.send('Performance.enable')
  const sample = async () => Object.fromEntries((await metrics.send('Performance.getMetrics')).metrics.map(m => [m.name, m.value]))
  async function idle(label, seconds = 6) {
    const a = await sample()
    await page.waitForTimeout(seconds * 1000)
    const b = await sample()
    const per = k => (b[k] - a[k]) / seconds
    const row = { label, taskMsPerSec: Math.round(per('TaskDuration') * 1000), scriptMsPerSec: Math.round(per('ScriptDuration') * 1000),
      layoutsPerSec: +per('LayoutCount').toFixed(1), styleRecalcsPerSec: +per('RecalcStyleCount').toFixed(1) }
    results.push(row)
    console.log(`idle ${label.padEnd(29)} task ${row.taskMsPerSec} ms/s  script ${row.scriptMsPerSec} ms/s  layouts ${row.layoutsPerSec}/s  style ${row.styleRecalcsPerSec}/s`)
  }
  await idle('resources page')

  const stagePage = id => `() => document.querySelector('[data-testid="stage"]')?.dataset.page === '${id}' && document.querySelector('[data-testid="stage"] button')`
  await step('hotkeys switch on', '[data-testid="hotkeys-switch"]', () => document.querySelector('[data-testid="hotkeys-switch"]').getAttribute('aria-pressed') === 'true')
  await step('hotkeys switch off', '[data-testid="hotkeys-switch"]', () => document.querySelector('[data-testid="hotkeys-switch"]').getAttribute('aria-pressed') === 'false')
  for (const [chapter, first] of [['battle', 'resources'], ['fields', 'ability_fields'], ['elephant', 'elephant'], ['codex', 'catalogs'], ['huolong', 'map_scripts'], ['archive', 'archive']]) {
    await step(`chapter ${chapter}`, `[data-testid="chapter-${chapter}"]`, new Function(`return ${stagePage(first)}`)(), { profile: chapter === 'codex' })
  }
  await page.locator('[data-testid="chapter-codex"]').evaluate(el => el.click())
  await page.waitForTimeout(800)
  const firstCode = () => document.querySelector('[data-testid="stage"] [role="row"][tabindex] span')?.textContent
  for (const kind of ['单位', '技能', '科技', '物品']) {
    const before = await page.evaluate(firstCode)
    await step(`catalog ${kind}`, `[role="radio"]:text-is("${kind}")`,
      new Function(`return () => { const v = document.querySelector('[data-testid="stage"] [role="row"][tabindex] span')?.textContent; return v && v !== ${JSON.stringify(before)} }`)(),
      { profile: kind === '单位' })
  }
  for (const id of ['upgrade_catalog', 'map_catalog', 'equipment3', 'hero_skills']) {
    await step(`page ${id}`, `[data-testid="page-${id}"]`, new Function(`return ${stagePage(id)}`)())
  }
  await page.locator('[data-testid="chapter-elephant"]').evaluate(el => el.click())
  await page.waitForTimeout(600)
  await step('page hotkeys', '[data-testid="page-hotkeys"]', new Function(`return ${stagePage('hotkeys')}`)(), { profile: true })
  await step('page elephant', '[data-testid="page-elephant"]', new Function(`return ${stagePage('elephant')}`)())
  await idle('elephant page')
  await page.locator('[data-testid="chapter-codex"]').evaluate(el => el.click())
  await idle('codex page')
} finally {
  if (out) writeFileSync(out, JSON.stringify(results, null, 2))
  await browser?.close().catch(() => {})
  app.kill()
  spawn('taskkill', ['/pid', String(app.pid), '/t', '/f'], { stdio: 'ignore' })
}

/** Self time per function from a CDP CPU profile, largest first. */
function topFunctions(profile) {
  const byId = new Map(profile.nodes.map(n => [n.id, n]))
  const self = new Map()
  const dt = profile.timeDeltas
  profile.samples.forEach((id, i) => {
    const n = byId.get(id)
    const key = `${n.callFrame.functionName || '(anonymous)'}|${n.callFrame.url.split('/').pop()}:${n.callFrame.lineNumber}`
    self.set(key, (self.get(key) ?? 0) + (dt[i] ?? 0) / 1000)
  })
  return [...self.entries()].map(([k, ms]) => ({ name: k.split('|')[0], url: k.split('|')[1], ms: Math.round(ms) }))
    .filter(x => !['(idle)', '(program)', '(garbage collector)'].includes(x.name) || x.ms > 5)
    .sort((a, b) => b.ms - a.ms)
}
