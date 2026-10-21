<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../api';
  import type { Equipment3Row, Equipment3SearchData } from '../types';
  import { Swords, Search, Copy, Check, RefreshCw, PlusCircle, AlertCircle } from 'lucide-svelte';

  let searchQuery = $state('');
  let isLoading = $state(false);
  let rows = $state<Equipment3Row[]>([]);
  let totalCount = $state(0);
  let matchCount = $state(0);
  let copiedCode = $state<string | null>(null);
  let actionFeedback = $state('');
  let isError = $state(false);

  let searchTimeout: any = null;

  async function performSearch(query: string = searchQuery) {
    isLoading = true;
    try {
      const data: Equipment3SearchData = await api.search3Equipment(query);
      rows = data.rows || [];
      totalCount = data.totalCount || 0;
      matchCount = data.matchCount || 0;
    } catch (err: any) {
      console.error('search3Equipment error:', err);
    } finally {
      isLoading = false;
    }
  }

  function handleQueryInput(val: string) {
    searchQuery = val;
    if (searchTimeout) clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      performSearch(searchQuery);
    }, 250);
  }

  async function copyCode(code: string) {
    try {
      await navigator.clipboard.writeText(code);
      copiedCode = code;
      setTimeout(() => {
        if (copiedCode === code) copiedCode = null;
      }, 1800);
    } catch (err) {
      console.warn('Clipboard write failed:', err);
    }
  }

  async function handleCreateItem(code: string, name: string) {
    actionFeedback = `正在为选中单位创建 [${name} (${code})]...`;
    isError = false;
    try {
      const res = await api.executeElephantAction('create_item', { item_rawcode: code });
      if (res.success) {
        actionFeedback = `✓ 已创建 [${name}] 到选中英雄或脚下`;
      } else {
        actionFeedback = `✗ 创建失败: ${res.error}`;
        isError = true;
      }
      setTimeout(() => (actionFeedback = ''), 3500);
    } catch (err: any) {
      actionFeedback = `✗ 异常: ${err.message || err}`;
      isError = true;
    }
  }

  onMount(() => {
    performSearch('');
  });
</script>

<div class="equipment-container">
  <!-- Top Bar -->
  <div class="header-bar">
    <div class="title-with-icon">
      <Swords size={18} class="accent-gold" />
      <h2>3.0 官方战役与重制版装备宝典</h2>
    </div>

    <div class="stats-badge">
      收录: <span class="accent-gold">{totalCount}</span> 件 / 匹配: <span class="accent-gold">{matchCount}</span>
    </div>
  </div>

  <!-- Search Box -->
  <div class="search-card">
    <div class="search-box">
      <Search size={15} class="search-icon" />
      <input
        type="text"
        class="search-input"
        placeholder="搜索装备名称 (如 霜之哀伤、统御之盔)、FourCC 代号或效果说明..."
        value={searchQuery}
        oninput={(e) => handleQueryInput((e.target as HTMLInputElement).value)}
      />
      {#if isLoading}
        <RefreshCw size={14} class="spinner" />
      {/if}
    </div>
  </div>

  {#if actionFeedback}
    <div class="feedback-banner {isError ? 'error' : 'success'}">
      {#if isError}
        <AlertCircle size={15} />
      {:else}
        <Check size={15} />
      {/if}
      <span>{actionFeedback}</span>
    </div>
  {/if}

  <!-- Table View -->
  <div class="table-container">
    {#if rows.length === 0}
      <div class="empty-state">
        <Swords size={36} class="empty-icon" />
        <div class="empty-title">未找到匹配的 3.0 装备</div>
        <div class="empty-desc">
          尝试清空搜索框以查看全部 325 件官方重制版专属神兵、圣物与饰品
        </div>
      </div>
    {:else}
      <table class="data-table">
        <thead>
          <tr>
            <th style="width: 120px;">FourCC 代号</th>
            <th style="width: 220px;">装备名称</th>
            <th>属性与被动效果说明</th>
            <th style="width: 160px; text-align: center;">快捷操作</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as row}
            <tr>
              <td>
                <span class="rawcode-chip mono font-bold">{row.code}</span>
              </td>
              <td>
                <span class="equipment-name font-semibold">{row.name}</span>
              </td>
              <td>
                <span class="description-text">{row.description || '无特殊被动描述'}</span>
              </td>
              <td style="text-align: center;">
                <div class="row-actions">
                  <button
                    class="btn-sm {copiedCode === row.code ? 'copied' : ''}"
                    onclick={() => copyCode(row.code)}
                    title="复制 FourCC 代号"
                  >
                    {#if copiedCode === row.code}
                      <Check size={12} />
                      <span>已复制</span>
                    {:else}
                      <Copy size={12} />
                      <span>复制</span>
                    {/if}
                  </button>
                  <button
                    class="btn-sm primary"
                    onclick={() => handleCreateItem(row.code, row.name)}
                    title="直接给选中单位生成此装备"
                  >
                    <PlusCircle size={12} />
                    <span>创建</span>
                  </button>
                </div>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>

  <!-- Footer Tip -->
  <div class="footer-bar">
    <span>来源：Warcraft III 3.0.1.24360 官方中文装备资料。不同地图可能修改同一代码的效果；生成物品需要当前地图有对应定义。</span>
  </div>
</div>

<style>
  .equipment-container {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 16px;
    gap: 12px;
    background-color: var(--bg-surface);
    overflow: hidden;
  }

  .header-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .title-with-icon {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .title-with-icon h2 {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-bright);
    margin: 0;
  }

  .stats-badge {
    font-size: 12px;
    color: var(--text-muted);
    background: var(--bg-surface-sunken);
    padding: 4px 10px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-subtle);
  }

  .accent-gold {
    color: var(--color-gold);
    font-weight: 700;
  }

  .search-card {
    background: var(--bg-surface-sunken);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 8px 12px;
  }

  .search-box {
    position: relative;
    display: flex;
    align-items: center;
  }

  .equipment-container :global(.search-icon) {
    position: absolute;
    left: 10px;
    color: var(--text-muted);
    pointer-events: none;
  }

  .search-input {
    width: 100%;
    height: 32px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 0 36px 0 34px;
    color: var(--text-bright);
    font-size: 13px;
    outline: none;
    transition: border-color 0.15s ease;
  }

  .search-input:focus {
    border-color: var(--color-gold);
  }

  .equipment-container :global(.spinner) {
    position: absolute;
    right: 12px;
    color: var(--color-gold);
    animation: spin 1s linear infinite;
  }

  .feedback-banner {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border-radius: var(--radius-sm);
    font-size: 12px;
  }

  .feedback-banner.success {
    background: var(--status-success-bg);
    border: 1px solid rgba(46, 204, 113, 0.3);
    color: var(--status-success-text);
  }

  .feedback-banner.error {
    background: var(--status-danger-bg);
    border: 1px solid rgba(231, 76, 60, 0.3);
    color: var(--status-danger-text);
  }

  .table-container {
    flex: 1;
    overflow-y: auto;
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    background: var(--bg-surface-sunken);
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }

  .data-table th {
    background: var(--bg-raised);
    color: var(--color-gold);
    font-weight: 700;
    font-size: 12px;
    text-align: left;
    padding: 8px 12px;
    border-bottom: 1px solid var(--border-normal);
    position: sticky;
    top: 0;
    z-index: 1;
    letter-spacing: 0.3px;
  }

  .data-table td {
    padding: 7px 12px;
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-normal);
    font-size: 13px;
  }

  .data-table tbody tr:hover {
    background-color: var(--bg-raised);
  }

  .rawcode-chip {
    display: inline-block;
    padding: 2px 8px;
    background: rgba(245, 158, 11, 0.15);
    border: 1px solid rgba(245, 158, 11, 0.4);
    border-radius: var(--radius-sm);
    color: var(--text-gold);
    letter-spacing: 0.5px;
    font-size: 13px;
    font-weight: 700;
  }

  .equipment-name {
    color: var(--text-primary);
    font-size: 14px;
    font-weight: 700;
  }

  .description-text {
    color: var(--text-secondary);
    line-height: 1.5;
    font-size: 13px;
  }

  .row-actions {
    display: flex;
    justify-content: center;
    gap: 6px;
  }

  .btn-sm {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    color: var(--text-normal);
    font-size: 11px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn-sm:hover {
    border-color: var(--color-gold);
    color: var(--color-gold);
  }

  .btn-sm.primary {
    background: rgba(229, 193, 88, 0.12);
    border-color: rgba(229, 193, 88, 0.3);
    color: var(--color-gold);
  }

  .btn-sm.primary:hover {
    background: var(--color-gold);
    color: var(--text-on-accent);
  }

  .btn-sm.copied {
    background: var(--status-success-bg);
    border-color: var(--status-success-text);
    color: var(--status-success-text);
  }

  .mono {
    font-family: var(--font-mono);
  }

  .font-bold {
    font-weight: 700;
  }

  .font-semibold {
    font-weight: 600;
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    padding: 40px;
    text-align: center;
    gap: 10px;
  }

  .equipment-container :global(.empty-icon) {
    color: var(--text-muted);
    opacity: 0.4;
  }

  .empty-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-normal);
  }

  .empty-desc {
    font-size: 12px;
    color: var(--text-muted);
    max-width: 440px;
    line-height: 1.5;
  }

  .footer-bar {
    font-size: 11px;
    color: var(--text-muted);
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
