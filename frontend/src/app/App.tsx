import { useEffect } from 'react'
import { useShellHotkeys } from './hotkeys'
import { startSync } from './state/sync'
import { Console } from './shell/Console'
import { NoticeDialog } from './shell/NoticeDialog'
import { Stage } from './shell/Stage'
import { TopBand } from './shell/TopBand'
import s from './App.module.css'

/** Top band, stage, console: the three rows of the redesign (plan, section 4.1). */
export function App() {
  useEffect(() => startSync(), [])
  useShellHotkeys()
  return (
    <div className={s.app} data-testid="app">
      <TopBand />
      <Stage />
      <Console />
      <NoticeDialog />
    </div>
  )
}
