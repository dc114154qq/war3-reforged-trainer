import { ICON_ATTRIBUTION, ICON_GROUPS, ICON_SOURCES, Icon, type IconTone } from '../ds'
import { Demo, Section } from './Section'
import s from './sg.module.css'

const TONES: IconTone[] = ['bone', 'gold', 'frost', 'lumber', 'wheat', 'muted']

export function Icons() {
  return (
    <Section
      id="icons"
      title="图标"
      lead="代码里用语义名（read、gold），清单 assets-src/icons/manifest.json 决定对应哪个图形，换图不用改组件。"
    >
      {Object.entries(ICON_GROUPS).map(([group, names]) => (
        <div key={group} className={s.iconGroup}>
          <h3 className={s.demoTitle}>{group}</h3>
          <ul className={s.iconGrid}>
            {names.map(name => (
              <li key={name} title={ICON_SOURCES[name]}>
                <span className={s.iconSocket}><Icon name={name} /></span>
                <code>{name}</code>
              </li>
            ))}
          </ul>
        </div>
      ))}
      <div className={s.demoGrid}>
        <Demo title="色调" note="五种金属渐变加一种平涂，同一个图形按用途换色。">
          <ul className={s.toneRow}>
            {TONES.map(t => (
              <li key={t}><Icon name="lock" tone={t} size={34} /><code>{t}</code></li>
            ))}
          </ul>
        </Demo>
        <Demo title="署名" note="CC BY 3.0 要求署名，正式版放在关于页。">
          <p className={s.attribution}>{ICON_ATTRIBUTION}</p>
        </Demo>
      </div>
    </Section>
  )
}
