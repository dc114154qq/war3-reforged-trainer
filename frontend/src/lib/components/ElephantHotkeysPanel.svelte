<script lang="ts">
  import { onMount,onDestroy } from 'svelte';
  import { api } from '../api';
  import type { HotkeyItem } from '../types';
  import { Keyboard, CheckSquare, Square, Play, ShieldAlert, Sparkles, Search, Sliders } from 'lucide-svelte';

  let hotkeys = $state<HotkeyItem[]>([]);
  let searchQuery = $state('');
  let activeCategory = $state('all');
  let loading = $state(false);
  let feedbackMessage = $state('');
  let artifactCodes = $state<string[]>([]);
  async function saveCodes() {
    const result = await api.saveArtifactPlan([...artifactCodes]);
    feedbackMessage = result.success ? '神器方案已保存' : (result.error || '保存失败');
  }
  async function restoreCodes(){
    const r=await api.restoreDefaultArtifactPlan();
    if(r.success && r.plan){artifactCodes=r.plan.codes;feedbackMessage='默认神器方案已恢复并保存';}
  }

  const categoryTabs = [
    { id: 'all', label: '全部 68 项' },
    { id: 'stats', label: '17 项属性增强' },
    { id: 'combat', label: '单位与战斗' },
    { id: 'fullscreen', label: '全屏特效攻击' },
    { id: 'world', label: '地图与世界' },
    { id: 'general', label: '技能与物品' },
  ];

  let filteredHotkeys = $derived.by(() => {
    let list = hotkeys;
    if (activeCategory !== 'all') {
      list = list.filter((h) => h.category === activeCategory);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      list = list.filter(
        (h) =>
          h.name.toLowerCase().includes(q) ||
          h.label.toLowerCase().includes(q) ||
          h.key.toLowerCase().includes(q)
      );
    }
    return list;
  });

  async function loadHotkeys() {
    loading = true;
    try {
      hotkeys = await api.getAllHotkeys();
      artifactCodes = (await api.getArtifactPlan()).codes;
    } catch (err) {
      console.error(err);
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    loadHotkeys();
    window.addEventListener('war3-elephant-parameters',refreshParameters);
  });
  async function refreshParameters(){hotkeys=await api.getAllHotkeys();}
  onDestroy(()=>window.removeEventListener('war3-elephant-parameters',refreshParameters));

  async function handleToggle(h: HotkeyItem) {
    try {
      const next = !h.enabled;
      h.enabled = next;
      await api.setHotkeyCheck(h.name, next);
    } catch (err) {
      console.error(err);
    }
  }

  async function handleSelectAll(enabled: boolean) {
    try {
      const res = await api.setAllHotkeysChecks(enabled);
      if (res.success) {
        hotkeys = res.hotkeys;
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function handleParamChange(h: HotkeyItem, val: string) {
    if (!h.paramKey) return;
    h.paramValue = val;
    try {
      await api.setHotkeyParameter(h.paramKey, val);
    } catch (err) {
      console.error(err);
    }
  }

  async function handleTrigger(h: HotkeyItem) {
    feedbackMessage = `正在分发: ${h.label}...`;
    try {
      const res = h.name === 'six_artifacts'
        ? await api.applyArtifactPlan([...artifactCodes])
        : await api.triggerHotkey(h.name);
      if (res.success) {
        feedbackMessage = `✓ ${res.message || '操作成功'}`;
      } else {
        feedbackMessage = `✗ 错误: ${res.error}`;
      }
      setTimeout(() => (feedbackMessage = ''), 3000);
    } catch (err: any) {
      feedbackMessage = `✗ 执行异常: ${err.message || err}`;
    }
  }
</script>

<div class="hotkeys-layout">
  <!-- Header Bar -->
  <div class="panel-header">
    <div class="header-left">
      <Keyboard size={18} class="text-gold" />
      <h2 class="panel-title">大象全局快捷键</h2>
    </div>
    <div class="header-actions">
      {#if feedbackMessage}
        <span class="feedback-badge">{feedbackMessage}</span>
      {/if}
      <button class="btn btn-secondary btn-sm" onclick={() => handleSelectAll(true)}>
        <CheckSquare size={13} /> 全选可用
      </button>
      <button class="btn btn-secondary btn-sm" onclick={() => handleSelectAll(false)}>
        <Square size={13} /> 清空勾选
      </button>
    </div>
  </div>

  <!-- Filter & Category Rail -->
  <div class="filter-bar">
    <div class="category-tabs">
      {#each categoryTabs as tab}
        <button
          class="cat-tab {activeCategory === tab.id ? 'active' : ''}"
          onclick={() => (activeCategory = tab.id)}
        >
          {tab.label}
        </button>
      {/each}
    </div>
    <div class="search-box">
      <Search size={13} class="text-muted" />
      <input
        type="text"
        placeholder="搜索快捷键、按键或功能..."
        bind:value={searchQuery}
        class="search-input"
      />
    </div>
  </div>

  <!-- Hotkeys Grid -->
  <div class="hotkeys-grid-scroll">
    <div class="hotkeys-grid">
      {#each filteredHotkeys as h}
        <div class:artifact-row={h.name === 'six_artifacts'} class="hotkey-card {h.enabled ? 'enabled' : ''} {h.isDangerous ? 'dangerous' : ''}">
          <!-- Left: Checkbox & Key badge -->
          <div class="card-left">
            <button
              class="check-btn {h.enabled ? 'checked' : ''}"
              onclick={() => handleToggle(h)}
              title="切换启用状态"
            >
              {#if h.enabled}
                <CheckSquare size={16} class="text-gold" />
              {:else}
                <Square size={16} class="text-muted" />
              {/if}
            </button>
            <span class="kbd-badge">{h.key}</span>
          </div>

          <!-- Middle: Label & Warning -->
          <div class="card-info">
            <div class="hotkey-label">
              <span>{h.label}</span>
              {#if h.isDangerous}
                <span class="danger-tag" title="高风险指令">
                  <ShieldAlert size={10} /> 慎用
                </span>
              {/if}
            </div>
            <div class="hotkey-name font-mono">{h.name}</div>
          </div>

          <!-- Right: Parameter Input & Direct Trigger -->
          <div class="card-right">
            {#if h.name === 'six_artifacts'}
              <div class="artifact-inputs">{#each artifactCodes as code, slot}<label>槽{slot + 1}<input class="mono" aria-label={'神器槽 ' + (slot + 1)} maxlength="4" bind:value={artifactCodes[slot]} onchange={saveCodes} /></label>{/each}</div>
              <button class="btn btn-secondary btn-sm" onclick={restoreCodes}>恢复默认方案</button>
            {/if}
            {#if h.paramKey}
              <div class="param-input-box">
                <span class="param-label">{h.paramLabel || '参数'}:</span>
                <input
                  type="text"
                  class="mono param-input"
                  value={h.paramValue || ''}
                  onchange={(e) => handleParamChange(h, (e.target as HTMLInputElement).value)}
                />
              </div>
            {/if}
            <button
              class="btn btn-secondary btn-sm trigger-btn"
              onclick={() => handleTrigger(h)}
              title="执行此快捷键对应的功能"
            >
              <Play size={11} /> 触发
            </button>
          </div>
        </div>
      {/each}
    </div>
  </div>
</div>

<style>
  .artifact-row { grid-column:1 / -1; flex-wrap:wrap; }
  .artifact-inputs { display:flex; flex-wrap:wrap; gap:6px; max-width:100%; }
  .artifact-inputs label { display:flex; gap:3px; align-items:center; font-size:11px; }
  .artifact-inputs input { width:58px; padding:5px; background:var(--bg-input); color:var(--text-bright); border:1px solid var(--border-normal); }
  .card-right { flex-wrap:wrap; max-width:100%; }
  .hotkeys-layout {
    display: flex;
    flex-direction: column;
    gap: 12px;
    height: 100%;
    padding: 16px;
    overflow: hidden;
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--border-subtle);
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .panel-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-bright);
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .feedback-badge {
    background-color: rgba(229, 193, 88, 0.15);
    border: 1px solid var(--border-gold);
    color: var(--text-gold);
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    font-size: 11px;
    font-weight: 600;
  }

  .filter-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    background-color: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 6px 10px;
  }

  .category-tabs {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px;
  }

  .cat-tab {
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-size: 13px;
    font-weight: 500;
    padding: 5px 12px;
    border-radius: var(--radius-sm);
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.12s ease;
  }

  .cat-tab:hover {
    color: var(--text-primary);
    background-color: var(--bg-card);
  }

  .cat-tab.active {
    background-color: var(--bg-card);
    color: var(--text-gold);
    font-weight: 600;
    border: 1px solid var(--border-gold);
  }

  .search-box {
    display: flex;
    align-items: center;
    gap: 6px;
    background-color: var(--bg-input);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 3px 8px;
  }

  .search-input {
    border: none !important;
    background: transparent !important;
    padding: 2px 0 !important;
    font-size: 11px !important;
    width: 180px;
  }

  .hotkeys-grid-scroll {
    flex: 1;
    overflow-y: auto;
  }

  .hotkeys-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(360px, 100%), 1fr));
    gap: 8px;
    padding-bottom: 16px;
  }

  .hotkey-card {
    background-color: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 8px 10px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
    transition: all 0.12s ease;
  }

  .hotkey-card.enabled {
    border-color: var(--border-normal);
  }

  .hotkey-card.dangerous {
    border-left: 3px solid var(--health-crimson);
  }

  .hotkey-card:hover {
    background-color: var(--bg-card-hover);
    border-color: var(--border-gold);
  }

  .card-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .check-btn {
    background: transparent;
    border: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    padding: 0;
  }

  .card-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .hotkey-label {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-bright);
    display: flex;
    align-items: center;
    gap: 6px;
    white-space: normal;
    overflow-wrap: anywhere;
  }

  .hotkey-name {
    font-size: 11px;
    color: var(--text-muted);
    overflow-wrap: anywhere;
  }

  .danger-tag {
    background-color: var(--status-danger-bg);
    color: var(--status-danger-text);
    border: 1px solid rgba(239, 68, 68, 0.3);
    font-size: 10px;
    padding: 1px 5px;
    border-radius: 2px;
    display: inline-flex;
    align-items: center;
    gap: 2px;
  }

  .card-right {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-shrink: 0;
  }

  .param-input-box {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .param-label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-normal);
  }

  .param-input {
    width: 60px;
    height: 26px;
    font-size: 12px;
    text-align: center;
    padding: 2px 4px;
  }

  .trigger-btn {
    padding: 3px 8px;
    font-size: 11px;
  }

  .hotkeys-layout :global(.text-gold) { color: var(--color-gold); }
  .hotkeys-layout :global(.text-muted) { color: var(--text-muted); }
</style>
