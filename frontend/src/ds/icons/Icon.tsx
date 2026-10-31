import { ICON_BODIES, type IconName } from './generated'
import { cx } from '../util'
import s from './Icon.module.css'

/** bone/gold/frost/lumber/wheat are engraved-metal gradients; muted and current are flat. */
export type IconTone = 'bone' | 'gold' | 'frost' | 'lumber' | 'wheat' | 'muted' | 'current'

interface IconProps {
  name: IconName
  tone?: IconTone
  size?: number
  /** Give a title only when the icon stands alone and carries meaning. */
  title?: string
  className?: string
}

const escapeText = (t: string) => t.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]!)

export function Icon({ name, tone = 'bone', size, title, className }: IconProps) {
  return (
    <svg
      className={cx(s.icon, s[tone], className)}
      viewBox="0 0 512 512"
      width={size}
      height={size}
      role={title ? 'img' : undefined}
      aria-hidden={title ? undefined : true}
      dangerouslySetInnerHTML={{ __html: (title ? `<title>${escapeText(title)}</title>` : '') + ICON_BODIES[name] }}
    />
  )
}

/** Gradients the tones refer to. Rendered once by <DsProvider>. */
export function IconDefs() {
  return (
    <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true">
      <defs>
        <linearGradient id="ds-ig-bone" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f7efdc" />
          <stop offset="0.55" stopColor="#d6c6a0" />
          <stop offset="1" stopColor="#957d50" />
        </linearGradient>
        <linearGradient id="ds-ig-gold" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffeb94" />
          <stop offset="0.5" stopColor="#e7b231" />
          <stop offset="1" stopColor="#8e5e14" />
        </linearGradient>
        <linearGradient id="ds-ig-lumber" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#d9b98a" />
          <stop offset="1" stopColor="#7a5530" />
        </linearGradient>
        <linearGradient id="ds-ig-wheat" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#f3dfa0" />
          <stop offset="1" stopColor="#a8823c" />
        </linearGradient>
        <linearGradient id="ds-ig-frost" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#effaff" />
          <stop offset="0.5" stopColor="#9ad8f5" />
          <stop offset="1" stopColor="#4a86ad" />
        </linearGradient>
      </defs>
    </svg>
  )
}
