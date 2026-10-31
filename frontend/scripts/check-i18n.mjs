// Fails when a literal passed to t('…') in src/app has no English translation, in either
// src/app/i18n/en/*.ts (new text) or src/lib/ui_text.ts (text carried over from 2.1.22).
// Node 24 strips the TypeScript annotations of those files on import. Also fails when two
// files in i18n/en translate the same key differently.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = resolve(fileURLToPath(new URL('..', import.meta.url)))
const EN = {}
const from = {}
const conflicts = []
const enDir = resolve(root, 'src/app/i18n/en')
for (const name of readdirSync(enDir).filter(n => n.endsWith('.ts'))) {
  const table = (await import(pathToFileURL(join(enDir, name)).href)).default
  // The tables merge into one, so a key translated differently in two files would silently
  // take whichever file loads last.
  for (const [key, value] of Object.entries(table)) {
    if (key in EN && EN[key] !== value) conflicts.push(`${key}: ${from[key]} “${EN[key]}” vs ${name} “${value}”`)
    EN[key] = value
    from[key] = name
  }
}
const { UI_EN } = await import(new URL('../src/lib/ui_text.ts', import.meta.url))

function* files(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name)
    if (statSync(path).isDirectory()) yield* files(path)
    else if (/\.tsx?$/.test(name)) yield path
  }
}

// t('…'), tr('…') and t("…") with a plain literal; dynamic arguments are not checked.
const CALL = /\b(?:t|tr)\(\s*(['"])((?:(?!\1)[^\\]|\\.)*)\1\s*\)/g
const missing = []
let count = 0
for (const path of files(resolve(root, 'src/app'))) {
  if (path.includes(join('i18n', 'en'))) continue
  const text = readFileSync(path, 'utf8')
  for (const m of text.matchAll(CALL)) {
    count++
    const key = m[2].trim()
    if (!(key in EN) && !(key in UI_EN)) {
      const line = text.slice(0, m.index).split('\n').length
      missing.push(`${relative(root, path)}:${line}  ${key}`)
    }
  }
}

if (conflicts.length) {
  console.error(`${conflicts.length} key(s) translated differently in two files:\n${conflicts.join('\n')}`)
  process.exit(1)
}
if (missing.length) {
  console.error(`${missing.length} string(s) without English:\n${missing.join('\n')}`)
  process.exit(1)
}
console.log(`i18n ok (${count} literal strings)`)
