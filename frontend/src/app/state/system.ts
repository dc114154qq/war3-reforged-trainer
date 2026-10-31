import { create } from 'zustand'
import { api } from '../../lib/api'
import type { SystemStatus } from '../../lib/types'

const INITIAL: SystemStatus = {
  appVersion: '',
  edition: '',
  connected: false,
  pid: null,
  gameVersion: null,
  adapterProfile: null,
  bridgeProfile: 3,
  hotkeysEnabled: false,
  statusMessage: '正在检测魔兽争霸 III 运行状态...',
  language: 'zh',
}

interface SystemState {
  status: SystemStatus
  /** window.pywebview.api is available. */
  bridgeReady: boolean
  /** A connect the user started is in flight; drives the clock spin. */
  connecting: boolean
  /** performance.now() when `connected` last turned true; the console uses it for the reveal. */
  connectedAt: number
  /** Backend translations for English mode, from set_ui_language. */
  translations: Record<string, string>

  setBridgeReady(): void
  /**
   * Read the backend status. Polls share a request already in flight; pass fresh after an
   * action, so the answer is read after the action instead of reusing an older request.
   */
  refresh(fresh?: boolean): Promise<void>
  connect(pid?: number | null): Promise<void>
  cancelDiscovery(): Promise<void>
  setHotkeysEnabled(enabled: boolean): Promise<void>
  setLanguage(language: 'zh' | 'en'): Promise<void>
}

let pending: Promise<void> | null = null

export const useSystem = create<SystemState>()((set, get) => ({
  status: INITIAL,
  bridgeReady: false,
  connecting: false,
  connectedAt: -Infinity,
  translations: {},

  setBridgeReady() { set({ bridgeReady: true }) },

  // Status polls overlap with user actions; share one request instead of stacking them.
  async refresh(fresh = false) {
    if (pending) {
      if (!fresh) return pending
      await pending
      if (pending) return pending
    }
    pending = (async () => {
      try {
        const status = await api.getSystemStatus()
        if (!status) return
        const was = get().status.connected
        set({ status, ...(status.connected && !was ? { connectedAt: performance.now() } : {}) })
      } catch (err) {
        console.warn('get_system_status failed:', err)
      } finally {
        pending = null
      }
    })()
    return pending
  },

  async connect(pid) {
    set({ connecting: true })
    try {
      await api.connectProcess(pid ?? null)
    } catch {
      // callApi already raised the failure as a notice.
    } finally {
      await get().refresh(true)
      set({ connecting: false })
    }
  },

  async cancelDiscovery() {
    try { await api.cancelDiscovery() } catch { /* reported by callApi */ }
    await get().refresh(true)
  },

  async setHotkeysEnabled(enabled) {
    // Flip the lamp at once; the fresh status afterwards corrects it if the backend refused.
    set(st => ({ status: { ...st.status, hotkeysEnabled: enabled } }))
    try { await api.setHotkeysEnabled(enabled) } catch { /* reported by callApi */ }
    await get().refresh(true)
  },

  async setLanguage(language) {
    try {
      const result = await api.setUiLanguage(language)
      if (result?.success) {
        set(st => ({ translations: result.translations ?? {}, status: { ...st.status, language } }))
        document.documentElement.lang = language === 'en' ? 'en' : 'zh-CN'
      }
    } catch { /* reported by callApi */ }
    await get().refresh(true)
  },
}))
