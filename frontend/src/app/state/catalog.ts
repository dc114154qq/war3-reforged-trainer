import { useEffect } from 'react'
import { create } from 'zustand'
import { api } from '../../lib/api'
import { useSystem } from './system'

type Kind = 'item' | 'ability' | 'unit' | 'upgrade'
interface Name { zh: string; en: string }

interface CatalogNames {
  /** Keyed "kind:code"; null while looking up or when the catalogue has no entry. */
  names: Record<string, Name | null>
  lookup(kind: Kind, code: string): void
}

/** Display names from the bundled ID catalogue, looked up once per rawcode. */
export const useCatalogNames = create<CatalogNames>()((set, get) => ({
  names: {},
  lookup(kind, code) {
    const key = `${kind}:${code}`
    if (key in get().names) return
    set(st => ({ names: { ...st.names, [key]: null } }))
    void api.searchIdCatalog(kind, code).then(data => {
      const row = data?.rows?.find(r => r.rawcode === code)
      if (row) set(st => ({ names: { ...st.names, [key]: { zh: row.name_zh, en: row.name_en } } }))
    }).catch(() => {})
  },
}))

const isCode = (code: string | null | undefined): code is string => !!code && /^[A-Za-z0-9]{4}$/.test(code)

/** The catalogue name of a rawcode in the current language, or null if unknown. */
export function useCatalogName(kind: Kind, code: string | null | undefined): string | null {
  const name = useCatalogNames(st => (isCode(code) ? st.names[`${kind}:${code}`] : null))
  const language = useSystem(st => st.status.language)
  useEffect(() => { if (isCode(code)) useCatalogNames.getState().lookup(kind, code) }, [kind, code])
  return (language === 'en' ? name?.en : name?.zh) || name?.zh || null
}

/** Names for many rawcodes at once (inventory grids); unknown codes map to undefined. */
export function useCatalogNameMap(kind: Kind, codes: string[]): Record<string, string | undefined> {
  const names = useCatalogNames(st => st.names)
  const language = useSystem(st => st.status.language)
  const list = codes.filter(isCode).join(',')
  useEffect(() => {
    for (const code of list.split(',')) if (code) useCatalogNames.getState().lookup(kind, code)
  }, [kind, list])
  const out: Record<string, string | undefined> = {}
  for (const code of codes) {
    const name = names[`${kind}:${code}`]
    out[code] = (language === 'en' ? name?.en : name?.zh) || name?.zh || undefined
  }
  return out
}
