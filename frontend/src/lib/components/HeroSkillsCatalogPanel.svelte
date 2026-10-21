<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../api';
  import type { HeroSkillRow, HeroSkillsSearchData } from '../types';
  import { BookOpen, Search, Copy, Check, RefreshCw, PlusCircle, AlertCircle, User } from 'lucide-svelte';

  let selectedHero = $state('');
  let searchQuery = $state('');
  let isLoading = $state(false);

  let heroesList = $state<string[]>([]);
  let rows = $state<HeroSkillRow[]>([]);
  let totalCount = $state(0);
  let matchCount = $state(0);

  let copiedCode = $state<string | null>(null);
  let actionFeedback = $state('');
  let isError = $state(false);

  let searchTimeout: any = null;

  async function performSearch(hero: string = selectedHero, query: string = searchQuery) {
    isLoading = true;
    try {
      const data: HeroSkillsSearchData = await api.search3HeroSkills(hero, query);
      rows = data.rows || [];
      totalCount = data.totalCount || 0;
      matchCount = data.matchCount || 0;
      if (data.heroes && data.heroes.length > 0 && heroesList.length === 0) {
        heroesList = data.heroes;
      }
    } catch (err: any) {
      console.error('search3HeroSkills error:', err);
    } finally {
      isLoading = false;
    }
  }

  function handleHeroSelect(hero: string) {
    selectedHero = hero;
    performSearch(hero, searchQuery);
  }

  function handleQueryInput(val: string) {
    searchQuery = val;
    if (searchTimeout) clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
      performSearch(selectedHero, searchQuery);
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

  async function handleAddAbility(code: string, name: string) {
    actionFeedback = `正在给选中单位赋予技能 [${name} (${code})]...`;
    isError = false;
    try {
      const res = await api.executeElephantAction('add_ability', { ability_rawcode: code, ability_level: '1' });
      if (res.success) {
        actionFeedback = `✓ 已成功添加技能 [${name}] 到选中英雄`;
      } else {
        actionFeedback = `✗ 添加失败: ${res.error}`;
        isError = true;
      }
      setTimeout(() => (actionFeedback = ''), 3500);
    } catch (err: any) {
      actionFeedback = `✗ 异常: ${err.message || err}`;
      isError = true;
    }
  }

  onMount(() => {
    performSearch('', '');
  });
</script>

<div class="skills-container">
  <!-- Header Bar -->
  <div class="header-bar">
    <div class="title-with-icon">
      <BookOpen size={18} class="accent-gold" />
      <h2>3.0 战役新角色技能宝典</h2>
    </div>

    <div class="stats-badge">
      收录: <span class="accent-gold">{totalCount}</span> 个 / 匹配: <span class="accent-gold">{matchCount}</span>
    </div>
  </div>

  <!-- Search & Filter Card -->
  <div class="search-card">
    <div class="filter-row">
      <div class="hero-selector">
        <label for="hero-select">所属战役英雄:</label>
        <div class="select-wrapper">
          <User size={13} class="select-icon" />
          <select
            id="hero-select"
            class="select-field"
            bind:value={selectedHero}
            onchange={(e) => handleHeroSelect((e.target as HTMLSelectElement).value)}
          >
            <option value="">全部英雄技能 ({totalCount})</option>
            {#each heroesList as h}
              <option value={h}>{h}</option>
            {/each}
          </select>
        </div>
      </div>

      <div class="search-box flex-1">
        <Search size={15} class="search-icon" />
        <input
          type="text"
          class="search-input"
          placeholder="搜索技能名称、FourCC 代号、效果或技能描述..."
          value={searchQuery}
          oninput={(e) => handleQueryInput((e.target as HTMLInputElement).value)}
        />
        {#if isLoading}
          <RefreshCw size={14} class="spinner" />
        {/if}
      </div>
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

  <!-- Table -->
  <div class="table-container">
    {#if rows.length === 0}
      <div class="empty-state">
        <BookOpen size={36} class="empty-icon" />
        <div class="empty-title">未找到匹配的战役英雄技能</div>
        <div class="empty-desc">
          尝试选择“全部英雄技能”或更换搜索词（例如 "暴风雪"、"治疗"、"复活" 或技能代号）
        </div>
      </div>
    {:else}
      <table class="data-table">
        <thead>
          <tr>
            <th style="width: 120px;">FourCC 代号</th>
            <th style="width: 140px;">所属英雄</th>
            <th style="width: 180px;">技能名称</th>
            <th style="width: 70px;">等级</th>
            <th>技能效果与作用机制说明</th>
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
                <span class="hero-tag">{row.hero}</span>
              </td>
              <td>
                <span class="skill-name font-semibold">{row.name}</span>
              </td>
              <td>
                <span class="level-badge mono">{row.levels || '1'}</span>
              </td>
              <td>
                <span class="description-text">{row.description || '-'}</span>
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
                    onclick={() => handleAddAbility(row.code, row.name)}
                    title="给当前选中的单位直接添加此技能"
                  >
                    <PlusCircle size={12} />
                    <span>添加</span>
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
    <span>技能取自官方 3.0 战役英雄的技能列表；不同地图可能修改同代码的效果。添加技能需要当前地图有对应定义。</span>
  </div>
</div>

<style>
  .skills-container {
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

  .filter-row {
    display: flex;
    gap: 12px;
    align-items: center;
  }

  .hero-selector {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .hero-selector label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .select-wrapper {
    position: relative;
    display: flex;
    align-items: center;
  }

  .skills-container :global(.select-icon) {
    position: absolute;
    left: 8px;
    color: var(--text-muted);
    pointer-events: none;
  }

  .select-field {
    height: 32px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 0 10px 0 28px;
    color: var(--text-bright);
    font-size: 12px;
    outline: none;
    cursor: pointer;
  }

  .select-field:focus {
    border-color: var(--color-gold);
  }

  .flex-1 {
    flex: 1;
  }

  .search-box {
    position: relative;
    display: flex;
    align-items: center;
  }

  .skills-container :global(.search-icon) {
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

  .skills-container :global(.spinner) {
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

  .hero-tag {
    display: inline-block;
    padding: 3px 8px;
    background: var(--bg-card);
    border: 1px solid var(--border-normal);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
    font-size: 12px;
    font-weight: 600;
  }

  .skill-name {
    color: var(--text-primary);
    font-size: 14px;
    font-weight: 700;
  }

  .level-badge {
    display: inline-block;
    padding: 2px 8px;
    background: var(--bg-card);
    border: 1px solid var(--border-normal);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: 12px;
    font-weight: 600;
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

  .skills-container :global(.empty-icon) {
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
