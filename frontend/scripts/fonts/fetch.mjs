// Downloads the full Source Han Serif CN weights the subsetter needs, verifying SHA256.
// Files land in assets-src/fonts/source/ (git-ignored). Already-present files with the
// right hash are kept.
import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(fileURLToPath(new URL('../..', import.meta.url)))
const dir = resolve(root, 'assets-src/fonts/source')
const BASE = 'https://cdn.jsdelivr.net/gh/adobe-fonts/source-han-serif@release/SubsetOTF/CN/'

// Source Han Serif 2.003, SIL Open Font License 1.1.
const FONTS = {
  'SourceHanSerifCN-SemiBold.otf': '50D3F12201CE2DD840650B6BFA47EBB8572ECF767EEC0E5CCB20A247B5BFA805',
  'SourceHanSerifCN-Heavy.otf': '053E911FDB1A55D4D8512A1F11203F1FB9A7291E34BC260474B8C80358C69FA6',
}

const sha256 = buf => createHash('sha256').update(buf).digest('hex').toUpperCase()

mkdirSync(dir, { recursive: true })
for (const [name, expected] of Object.entries(FONTS)) {
  const path = resolve(dir, name)
  if (existsSync(path) && sha256(readFileSync(path)) === expected) {
    console.log(`${name}: present`)
    continue
  }
  const res = await fetch(BASE + name)
  if (!res.ok) throw new Error(`${name}: HTTP ${res.status}`)
  const buf = Buffer.from(await res.arrayBuffer())
  const got = sha256(buf)
  if (got !== expected) throw new Error(`${name}: SHA256 ${got}, expected ${expected}`)
  writeFileSync(path, buf)
  console.log(`${name}: downloaded ${(buf.length / 1048576).toFixed(1)} MB`)
}
