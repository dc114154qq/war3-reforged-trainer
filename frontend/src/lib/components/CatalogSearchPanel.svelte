<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../api';
  import type { CatalogItemRow, CatalogSearchData } from '../types';
  import { Search, Copy, Check, Package, Sparkles, User, RefreshCw } from 'lucide-svelte';

  let currentKind = $state<'item' | 'ability' | 'unit'>('item');
  let searchQuery = $state('');
  let isLoading = $state(false);
  let rows = $state<CatalogItemRow[]>([]);
  let totalCount = $state(0);
  let matchCount = $state(0);
  let copiedCode = $state<string | null>(null);

  let searchTimeout: any = null;

  const kinds = [
    { id: 'item', label: '物品目录 (Items)', icon: Package },
    { id: 'ability', label: '技能目录 (Abilities)', icon: Sparkles },
    { id: 'unit', label: '单位目录 (Units)', icon: User },
  ] as const;

  async function performSearch(kind: 'item' | 'ability' | 'unit' = currentKind, query: string = searchQuery) {
    isLoading = true;
    try {
      const data: CatalogSearchData = await api.searchIdCatalog(kind, query);
      rows = data.rows || [];
      totalCount = data.totalCount || 0;
      matchCount = data.matchCount || 0;
    } catch (err) {
      console.error('searchIdCatalog error:', err);
    } finally {
      isLoading = false;
    }
  }

  function handleKindChange(kind: 'item' | 'ability' | 'unit') {
    currentKind = kind;
    performSearch(kind, searchQuery);
  }

  function handleQueryInput(val: string) {
    searchQuery = val;
    if (searchTimeout) clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      performSearch(currentKind, searchQuery);
    }, 250);
  }

  async function copyRawcode(code: string) {
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

  onMount(() => {
    performSearch('item', '');
  });
</script>

<div class="catalog-container">
  <!-- Header / Navigation -->
  <div class="header-bar">
    <div class="kind-tabs">
      {#each kinds as k}
        <button
          class="kind-tab {currentKind === k.id ? 'active' : ''}"
          onclick={() => handleKindChange(k.id)}
        >
          <k.icon size={14} />
          <span>{k.label}</span>
        </button>
      {/each}
    </div>

    <div class="stats-badge">
      匹配: <span class="accent-gold">{matchCount}</span> / 库收录: <span class="accent-gold">{totalCount}</span>
    </div>
  </div>

  <!-- Search Card -->
  <div class="search-card">
    <div class="search-box">
      <Search size={15} class="search-icon" />
      <input
        type="text"
        class="search-input"
        placeholder="搜索 FourCC 代号 (如 ckng, AHbz)、中文名称、英文名称或分类..."
        value={searchQuery}
        oninput={(e) => handleQueryInput((e.target as HTMLInputElement).value)}
      />
      {#if isLoading}
        <RefreshCw size={14} class="spinner" />
      {/if}
    </div>
  </div>

  <!-- Table View -->
  <div class="table-container">
    {#if rows.length === 0}
      <div class="empty-state">
        <Search size={36} class="empty-icon" />
        <div class="empty-title">未找到匹配的条目</div>
        <div class="empty-desc">
          尝试使用更通用的关键词（例如 "骑士"、"剑"、"光环"、"Paladin" 或 Rawcode 代号）
        </div>
      </div>
    {:else}
      <table class="data-table">
        <thead>
          <tr>
            <th style="width: 130px;">Rawcode (FourCC)</th>
            <th style="width: 260px;">中文名称</th>
            <th style="width: 260px;">英文名称 (English)</th>
            <th>分类 / 归属</th>
            <th style="width: 100px; text-align: center;">操作</th>
          </tr>
        </thead>
        <tbody>
          {#each rows as row}
            <tr>
              <td>
                <span class="rawcode-chip mono font-bold">
                  {row.rawcode}
                </span>
              </td>
              <td class="name-zh font-medium">
                {row.name_zh || '-'}
              </td>
              <td class="name-en text-muted">
                {row.name_en || '-'}
              </td>
              <td>
                <span class="category-pill">{row.category || '未分类'}</span>
              </td>
              <td style="text-align: center;">
                <button
                  class="btn-copy {copiedCode === row.rawcode ? 'copied' : ''}"
                  onclick={() => copyRawcode(row.rawcode)}
                  title="复制 FourCC 代号至剪贴板"
                >
                  {#if copiedCode === row.rawcode}
                    <Check size={12} />
                    <span>已复制</span>
                  {:else}
                    <Copy size={12} />
                    <span>复制</span>
                  {/if}
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>

  <!-- Footer Tip -->
  <div class="footer-bar">
    <span>💡 检索支持大小写忽略；点击“复制”即可获得4字节代号，用于大象面板、物品创建或技能添加</span>
  </div>
</div>

<style>
  .catalog-container {
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

  .kind-tabs {
    display: flex;
    gap: 6px;
  }

  .kind-tab {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 32px;
    padding: 0 12px;
    background: var(--bg-surface-sunken);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    color: var(--text-normal);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .kind-tab:hover {
    border-color: var(--color-gold);
    color: var(--text-bright);
  }

  .kind-tab.active {
    background: rgba(229, 193, 88, 0.15);
    border-color: var(--color-gold);
    color: var(--color-gold);
    font-weight: 700;
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

  .catalog-container :global(.search-icon) {
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

  .catalog-container :global(.spinner) {
    position: absolute;
    right: 12px;
    color: var(--color-gold);
    animation: spin 1s linear infinite;
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

  .mono {
    font-family: var(--font-mono);
  }

  .font-bold {
    font-weight: 700;
  }

  .font-medium {
    font-weight: 600;
  }

  .name-zh {
    color: var(--text-primary);
    font-size: 13px;
  }

  .name-en {
    color: var(--text-secondary);
    font-size: 12px;
  }

  .category-pill {
    display: inline-block;
    padding: 2px 8px;
    background: var(--bg-card);
    border: 1px solid var(--border-normal);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: 11px;
    font-weight: 600;
  }

  .btn-copy {
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

  .btn-copy:hover {
    border-color: var(--color-gold);
    color: var(--color-gold);
  }

  .btn-copy.copied {
    background: var(--status-success-bg);
    border-color: var(--status-success-text);
    color: var(--status-success-text);
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

  .catalog-container :global(.empty-icon) {
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
