<script lang="ts">
  import { untrack } from 'svelte';
  import { api } from '../api';
  import type { SystemStatus } from '../types';
  import { RefreshCw, Zap, Shield, Globe, Power, Play, Volume2 } from 'lucide-svelte';

  let { status, currentTab, onRefreshAll }: {
    status: SystemStatus;
    currentTab: string;
    onRefreshAll: () => Promise<void>;
  } = $props();

  let pidInput = $state(untrack(() => status.pid ? String(status.pid) : ''));
  let connecting = $state(false);
  function toggleTheme() { const next = document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'; document.documentElement.dataset.theme = next; localStorage.setItem('war3-theme', next); }

  async function handleConnect() {
    connecting = true;
    try {
      const targetPid = pidInput.trim() ? parseInt(pidInput.trim(), 10) : null;
      await api.connectProcess(targetPid);
      await onRefreshAll();
    } catch (err) {
      console.error('Connect failed:', err);
    } finally {
      connecting = false;
    }
  }

  async function handleToggleHotkeys() {
    try {
      await api.setHotkeysEnabled(!status.hotkeysEnabled);
      await onRefreshAll();
    } catch (err) {
      console.error('Toggle hotkeys failed:', err);
    }
  }

  async function handleCancelDiscovery() {
    try {
      await api.cancelDiscovery();
      await onRefreshAll();
    } catch (err) {
      console.error('Cancel discovery failed:', err);
    }
  }

  async function handleReadUnit() {
    try {
      if(currentTab==='batch')window.dispatchEvent(new CustomEvent('war3-batch-read'));
      else {
        const result=await api.readAllSelectedUnits();
        window.dispatchEvent(new CustomEvent('war3-unit-read', {detail: result.unit}));
        window.dispatchEvent(new CustomEvent('war3-candidates-read', {detail: result.candidates}));
      }
      await onRefreshAll();
    } catch (err) {
      console.error('Read unit failed:', err);
    }
  }

  async function handleLanguageToggle() {
    const nextLang = status.language === 'zh' ? 'en' : 'zh';
    const result = await api.setUiLanguage(nextLang);
    window.dispatchEvent(new CustomEvent('war3-language', {detail: result}));
    await onRefreshAll();
  }
</script>

<header class="header">
  <!-- Top brand area -->
  <div class="brand-zone">
    <div class="logo-box">
      <div class="logo-crest">⚔️</div>
      <div class="brand-text">
        <div class="app-title">魔兽争霸 III 重制版修改器</div>
        <div class="app-sub">
          <span class="version-tag">v{status.appVersion}</span>
          <span class="edition-tag">{status.edition}</span>
          <span class="author">by B站两杯沈梦溪</span>
        </div>
      </div>
    </div>

    <!-- Live Connection Status Badge -->
    <div class="status-indicator">
      {#if status.connected}
        <div class="status-badge online">
          <span class="status-dot"></span>
          <span>已连接 {status.gameVersion || '待识别版本'} (PID: {status.pid})</span>
        </div>
      {:else}
        <div class="status-badge offline">
          <span class="status-dot"></span>
          <span>未挂载游戏进程</span>
        </div>
      {/if}
    </div>
  </div>

  <!-- Primary toolbar & controls -->
  <div class="actions-zone">
    <button class="btn btn-secondary btn-sm" onclick={toggleTheme}>深色 / 浅色</button>
    <div class="pid-group">
      <span class="label">PID</span>
      <input type="text" class="pid-input mono" placeholder="自动检测" bind:value={pidInput} />
      <button class="btn btn-secondary btn-sm" onclick={handleConnect} disabled={connecting}>
        <RefreshCw size={13} class={connecting ? 'spin' : ''} />
        {connecting ? '连接中...' : '连接/刷新'}
      </button>
      <button class="btn btn-secondary btn-sm" onclick={handleCancelDiscovery} title="取消后台自动指纹定位">
        取消定位
      </button>
    </div>

    <div class="divider"></div>

    <button class="btn btn-primary btn-sm highlight-btn" onclick={handleReadUnit}>
      <Play size={13} />
      读取所有选中单位
      <span class="kbd-badge">Ctrl+F11</span>
    </button>

    <div class="divider"></div>

    <label class="switch-label">
      <input
        type="checkbox"
        class="switch-input"
        checked={status.hotkeysEnabled}
        onchange={handleToggleHotkeys}
      />
      <div class="switch-slider"></div>
      <span class="toggle-text">
        <Zap size={13} class={status.hotkeysEnabled ? 'gold-icon' : ''} />
        全局快捷键
      </span>
    </label>

    <div class="divider"></div>

    <button class="btn btn-secondary btn-sm lang-btn" onclick={handleLanguageToggle}>
      <Globe size={13} />
      {status.language === 'zh' ? '中文' : 'English'}
    </button>
  </div>
</header>

<div class="system-ticker">
  <div class="ticker-content">
    <span class="ticker-badge">系统</span>
    <span class="ticker-text">{status.statusMessage}</span>
  </div>
</div>

<div class="credits">大象功能灵感来源于经典版大象修改器，本软件完全免费，谨防倒卖</div>

<style>
  .header {
    min-height: 60px;
    flex-shrink: 0;
    flex-wrap: wrap;
    gap: 8px;
    background: var(--bg-header);
    border-bottom: 1px solid var(--border-normal);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 16px;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.4);
    z-index: 100;
  }

  .brand-zone {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .logo-box {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .logo-crest {
    font-size: 20px;
    filter: drop-shadow(0 0 4px rgba(229, 193, 88, 0.4));
  }

  .brand-text {
    display: flex;
    flex-direction: column;
  }

  .app-title {
    font-weight: 700;
    font-size: 14px;
    color: var(--text-primary);
    letter-spacing: 0.5px;
    background: linear-gradient(90deg, var(--brand-start), var(--brand-end));
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  .app-sub {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    font-size: 10px;
  }

  .version-tag {
    color: var(--color-gold);
    font-weight: 600;
    font-family: var(--font-mono);
  }

  .edition-tag {
    color: var(--text-muted);
  }

  .actions-zone {
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .pid-group {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .pid-input {
    width: 72px;
    height: 26px;
    text-align: center;
    font-size: 11px;
  }

  .divider {
    width: 1px;
    height: 20px;
    background-color: var(--border-subtle);
  }

  .label {
    font-size: 11px;
    color: var(--text-muted);
    font-weight: 600;
  }

  .toggle-text {
    font-size: 12px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 5px;
    color: var(--text-secondary);
  }

  .header :global(.gold-icon) {
    color: var(--color-gold);
  }

  .system-ticker {
    min-height: 28px;
    flex-shrink: 0;
    background-color: var(--bg-abyss);
    border-bottom: 1px solid var(--border-subtle);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 5px 16px;
    font-size: 12px;
  }

  .ticker-content {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--text-primary);
    min-width: 0;
  }

  .ticker-badge {
    background-color: var(--status-neutral-bg);
    color: var(--text-gold);
    font-size: 11px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 3px;
    text-transform: uppercase;
  }

  .ticker-text {
    font-family: var(--font-sans);
    font-weight: 500;
    color: var(--text-primary);
    overflow-wrap:anywhere;
    user-select:text;
  }
  .author {color:var(--text-secondary);font-size:11px;}
  .credits {padding:4px 16px;flex-shrink:0;background:var(--bg-abyss);border-bottom:1px solid var(--border-subtle);font-size:11px;color:var(--text-secondary);overflow-wrap:anywhere;}


  .header :global(.spin) {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
