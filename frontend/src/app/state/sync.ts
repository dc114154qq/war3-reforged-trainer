import { api, type UiNotice } from '../../lib/api'
import { useNotices } from './notices'
import { useParams } from './params'
import { useResources } from './resources'
import { useSystem } from './system'
import { useUnit } from './unit'

const STATUS_MS = 2500
const NOTIFICATIONS_MS = 500
const BRIDGE_TIMEOUT_MS = 10000

/** Route one backend notification to the store that owns it. */
function route(notice: UiNotice) {
  if (notice.kind === 'unit_read') useUnit.getState().received(notice.unit, notice.candidates)
  else if (notice.kind === 'parameters') useParams.getState().merge(notice.parameters)
  else useNotices.getState().push(notice)
}

/**
 * Connect the stores to the Python bridge: wait for pywebview, load the initial state,
 * then poll status every 2.5 s and notifications every 0.5 s (the 2.1.22 cadence).
 * api.ts keeps broadcasting failures and parameter changes as window events; they are
 * picked up here. Returns a function that stops everything.
 */
export function startSync(): () => void {
  let stopped = false
  let statusTimer = 0
  let noticeTimer = 0

  // When the game connects, load what the backend already holds about the selection and
  // resources (snapshots only; neither reads game memory).
  const unsubscribe = useSystem.subscribe((state, prev) => {
    if (state.status.connected && !prev.status.connected) {
      void useUnit.getState().loadSnapshot()
      void useResources.getState().poll()
    }
  })

  const onError = (e: Event) => useNotices.getState().push((e as CustomEvent<UiNotice>).detail)
  const onParams = (e: Event) => useParams.getState().merge((e as CustomEvent<Record<string, string>>).detail)
  const onParamsChanged = () => void useParams.getState().reload()
  window.addEventListener('war3-error', onError)
  window.addEventListener('war3-elephant-parameters', onParams)
  window.addEventListener('war3-elephant-parameters-changed', onParamsChanged)

  const pollStatus = async () => {
    await useSystem.getState().refresh()
    if (useSystem.getState().status.connected) await useResources.getState().poll()
    if (!stopped) statusTimer = window.setTimeout(pollStatus, STATUS_MS)
  }

  const pollNotifications = async () => {
    try {
      for (const notice of (await api.getUiNotifications()) ?? []) route(notice)
    } catch {
      // callApi already reported communication failures.
    } finally {
      if (!stopped) noticeTimer = window.setTimeout(pollNotifications, NOTIFICATIONS_MS)
    }
  }

  const begin = async () => {
    window.clearTimeout(bridgeTimer)
    const system = useSystem.getState()
    system.setBridgeReady()
    await system.refresh()
    // Startup in English needs the backend's translation table once.
    if (useSystem.getState().status.language === 'en') await system.setLanguage('en')
    await Promise.all([
      useUnit.getState().loadSnapshot(),
      useResources.getState().poll(),
      useParams.getState().reload(),
    ])
    if (stopped) return
    void pollStatus()
    void pollNotifications()
  }

  const bridgeTimer = window.setTimeout(() => {
    if (!useSystem.getState().bridgeReady) useNotices.getState().push('桌面通信尚未就绪，请重新打开修改器。')
  }, BRIDGE_TIMEOUT_MS)

  const onReady = () => void begin()
  if (window.pywebview?.api) void begin()
  else window.addEventListener('pywebviewready', onReady, { once: true })

  return () => {
    stopped = true
    unsubscribe()
    window.clearTimeout(statusTimer)
    window.clearTimeout(noticeTimer)
    window.clearTimeout(bridgeTimer)
    window.removeEventListener('pywebviewready', onReady)
    window.removeEventListener('war3-error', onError)
    window.removeEventListener('war3-elephant-parameters', onParams)
    window.removeEventListener('war3-elephant-parameters-changed', onParamsChanged)
  }
}
