// Checks WCAG contrast for the text and line colours in src/ds/tokens.css against the
// surfaces they are used on. Alpha colours are blended over the surface first.
// Exits non-zero when any pair falls below its threshold.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(fileURLToPath(new URL('..', import.meta.url)))
const css = readFileSync(resolve(root, 'src/ds/tokens.css'), 'utf8')

// Only the first :root block; media-query overrides do not touch colours.
const block = css.slice(css.indexOf(':root'), css.indexOf('@media'))
const vars = new Map()
for (const m of block.matchAll(/--([\w-]+):\s*([^;]+);/g)) vars.set(m[1], m[2].trim())

function resolveVar(value, depth = 0) {
  const ref = value.match(/^var\(--([\w-]+)\)$/)
  if (!ref) return value
  if (depth > 8 || !vars.has(ref[1])) throw new Error(`cannot resolve ${value}`)
  return resolveVar(vars.get(ref[1]), depth + 1)
}

function parse(value) {
  const v = resolveVar(value)
  let m = v.match(/^#([0-9a-f]{6})$/i)
  if (m) return [0, 2, 4].map(i => parseInt(m[1].slice(i, i + 2), 16)).concat(1)
  m = v.match(/^rgba?\(([^)]+)\)$/)
  if (m) {
    const [r, g, b, a = '1'] = m[1].split(',').map(s => s.trim())
    return [Number(r), Number(g), Number(b), Number(a)]
  }
  throw new Error(`unsupported colour ${value}`)
}

const blend = ([r, g, b, a], [br, bg, bb]) => [r * a + br * (1 - a), g * a + bg * (1 - a), b * a + bb * (1 - a)]

function luminance(rgb) {
  const [r, g, b] = rgb.map(c => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function ratio(fg, bg) {
  const base = parse(bg)
  const a = luminance(blend(parse(fg), base))
  const b = luminance(base)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

// Surfaces as actually painted; gradients are checked at their darkest/lightest point of use.
const SURFACES = {
  stage: 'var(--surface-stage)',
  'stage, lit top': '#1d2a45',
  raised: 'var(--surface-raised)',
  sunken: 'var(--surface-sunken)',
  console: '#221e19',
  'console, top': '#302a24',
  document: 'var(--surface-document)',
  'bronze pill': '#b58f50',
}

const TEXT = 4.5
const NON_TEXT = 3
const PAIRS = [
  ...['--text-primary', '--text-secondary', '--text-tertiary', '--text-label', '--text-value'].flatMap(fg =>
    ['stage', 'stage, lit top', 'raised', 'console', 'console, top'].map(bg => [fg, bg, TEXT])),
  ['--text-primary', 'sunken', TEXT],
  ['--text-tertiary', 'sunken', TEXT],
  ['--text-danger', 'stage', TEXT],
  ['--frost', 'stage', TEXT],
  ['--lumber', 'stage', TEXT],
  ['--text-on-document', 'document', TEXT],
  ['--text-on-bronze', 'bronze pill', TEXT],
  ['--focus', 'stage', NON_TEXT],
  ['--focus', 'console', NON_TEXT],
  ['--line-strong', 'stage', NON_TEXT],
]

let failed = 0
for (const [fg, bg, min] of PAIRS) {
  const r = ratio(`var(${fg})`, SURFACES[bg])
  const ok = r >= min
  if (!ok) failed++
  console.log(`${ok ? 'ok  ' : 'FAIL'} ${r.toFixed(2).padStart(5)}:1  ${fg} on ${bg} (needs ${min})`)
}
if (failed) {
  console.error(`${failed} contrast pair(s) below threshold`)
  process.exit(1)
}
console.log('contrast ok')
