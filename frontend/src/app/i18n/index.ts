import { UI_EN, translateDynamic } from '../../lib/ui_text'
import { useSystem } from '../state/system'

type Lang = 'zh' | 'en'

// English tables, one file per area in ./en (shell.ts, battle.ts, …), merged at build time.
// Strings the 2.1.22 panels already had stay in src/lib/ui_text.ts (UI_EN); backend messages
// come from set_ui_language. scripts/check-i18n.mjs checks every literal passed to t().
const modules = import.meta.glob<{ default: Record<string, string> }>('./en/*.ts', { eager: true })
export const EN: Record<string, string> = Object.assign({}, ...Object.values(modules).map(m => m.default))

/**
 * Translate a Chinese source string. Chinese is the key, as in 2.1.22, so backend messages
 * (status text, errors) translate through the same lookup as shell labels.
 * Falls back to the Chinese text when no translation exists.
 */
export function translate(text: string, lang: Lang, backend: Record<string, string>): string {
  if (lang !== 'en' || !text) return text
  const key = text.trim()
  const hit = EN[key] ?? UI_EN[key] ?? backend[key] ?? translateDynamic(key)
  return hit === undefined ? text : text.replace(key, hit)
}

/** Translation function bound to the current language; re-renders when the language changes. */
export function useT() {
  const lang = useSystem(st => st.status.language)
  const backend = useSystem(st => st.translations)
  return (text: string) => translate(text, lang, backend)
}

/** For non-React code (store actions, announcements). */
export function t(text: string): string {
  const { status, translations } = useSystem.getState()
  return translate(text, status.language, translations)
}

/** Put values into a translated template, e.g. fill(t(template), { n: 3 }); each language keeps its own word order. */
export function fill(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m))
}
