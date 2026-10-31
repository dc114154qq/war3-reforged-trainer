import { useState } from 'react'
import * as Popover from '@radix-ui/react-popover'
import { Button, Checkbox, ICON_ATTRIBUTION, Icon, PillGroup, TextField } from '../../ds'
import { useSystem } from '../state/system'
import { useT } from '../i18n'
import s from './SystemMenu.module.css'

/**
 * Everything the 2.1.22 header carried besides navigation: manual PID, connect/refresh,
 * stop locating, global hotkeys, language, status text, version and credits.
 */
export function SystemMenu() {
  const t = useT()
  const status = useSystem(st => st.status)
  const bridgeReady = useSystem(st => st.bridgeReady)
  const connecting = useSystem(st => st.connecting)
  const { connect, cancelDiscovery, setHotkeysEnabled, setLanguage } = useSystem.getState()
  const [pid, setPid] = useState('')

  const submitConnect = () => {
    const value = pid.trim()
    void connect(value ? Number.parseInt(value, 10) : null)
  }

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button type="button" className={s.trigger} aria-label={t('系统')} data-testid="system-menu">
          <Icon name="settings" />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className={`ds-frame-ornate ${s.panel}`} align="end" sideOffset={8} collisionPadding={12}>
          <section className={s.block}>
            <div className={s.row}>
              <TextField
                className={s.pid}
                aria-label="PID"
                placeholder={t('自动检测')}
                inputMode="numeric"
                value={pid}
                onChange={e => setPid(e.target.value.replace(/\D/g, ''))}
                onKeyDown={e => { if (e.key === 'Enter') submitConnect() }}
              />
              <Button size="sm" icon="refresh" disabled={!bridgeReady || connecting} onClick={submitConnect} data-testid="connect-refresh">
                {t('连接/刷新')}
              </Button>
              <Button size="sm" disabled={!bridgeReady} onClick={() => void cancelDiscovery()}>{t('取消定位')}</Button>
            </div>
            {status.connected && (
              <p className={s.meta}>{t('游戏版本')} {status.gameVersion}，PID {status.pid}</p>
            )}
          </section>

          <section className={s.block}>
            <Checkbox
              label={t('启用全局快捷键')}
              checked={status.hotkeysEnabled}
              disabled={!bridgeReady}
              onChange={e => void setHotkeysEnabled(e.target.checked)}
            />
            <PillGroup<'zh' | 'en'>
              label={t('界面语言')}
              value={status.language}
              onChange={lang => void setLanguage(lang)}
              options={[{ value: 'zh', label: '中文' }, { value: 'en', label: 'English' }]}
            />
          </section>

          <section className={s.block}>
            <h3 className={s.heading}>{t('状态')}</h3>
            <p className={s.status} data-testid="status-message">{t(status.statusMessage)}</p>
          </section>

          <footer className={s.about}>
            <p className={s.version}>
              {status.appVersion && `v${status.appVersion}`}　by B站两杯沈梦溪、chatgpt和claude
            </p>
            <p>{t('大象功能灵感来源于经典版大象修改器，本软件完全免费，谨防倒卖')}</p>
            <p>{t('思源宋体按 SIL Open Font License 1.1 使用。')} {t(ICON_ATTRIBUTION)}</p>
          </footer>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
