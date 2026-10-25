<script lang="ts">
  function focusField(node: HTMLInputElement) { node.focus(); }
  import { api } from '../api';
  import type { AbilityFieldRow, AbilityFieldsData } from '../types';
  import { Sparkles, RefreshCw, Search, Check, AlertCircle, Edit2, X, Save } from 'lucide-svelte';

  let rawcode = $state('AHhb');
  let level = $state<number | undefined>(1);
  let filterText = $state('');
  let showZero = $state(true);
  let showUnsupported = $state(true);

  let isLoading = $state(false);
  let summary = $state('');
  let detail = $state('');
  let rows = $state<AbilityFieldRow[]>([]);
  let feedback = $state('');
  let isError = $state(false);

  // Inline editing state
  let editingRowId = $state<string | null>(null);
  let editingValue = $state('');
  let isSaving = $state(false);

  async function handleRead() {
    if (!rawcode.trim()) {
      feedback = '请输入有效的技能 Rawcode (如 AHbz)';
      window.dispatchEvent(new CustomEvent('war3-error',{detail:feedback}));
      isError = true;
      return;
    }
    isLoading = true;
    feedback = '';
    try {
      const data: AbilityFieldsData = await api.readAbilityFields(
        rawcode.trim(),
        String(level ?? 1),
        filterText.trim(),
        showZero,
        showUnsupported
      );
      summary = data.summary;
      detail = data.detail;
      rows = data.rows || [];
      isError = false;
      if (rows.length === 0) {
        feedback = '未找到匹配的技能字段，请确保游戏运行且选中包含该技能的单位';
      }
    } catch (err: any) {
      feedback = `读取失败: ${err.message || err}`;
      isError = true;
      rows = [];
      summary = '';
      detail = '';
      editingRowId = null;
    } finally {
      isLoading = false;
    }
  }

  function startEdit(row: AbilityFieldRow) {
    editingRowId = row._iid;
    editingValue = row.value;
  }

  function cancelEdit() {
    editingRowId = null;
    editingValue = '';
  }

  async function saveEdit(row: AbilityFieldRow) {
    isSaving = true;
    try {
      const res = await api.writeAbilityField(row._iid, editingValue);
      if (res.success) {
        if (res.data) { rows = res.data.rows; summary = res.data.summary; detail = res.data.detail; }
        editingRowId = null;
        feedback = `✓ 字段 [${row.name || row.field}] 已写入: ${editingValue}`;
        isError = false;
      } else {
        feedback = `✗ 写入失败: ${res.error}`;
        isError = true;
      }
      setTimeout(() => (feedback = ''), 3000);
    } catch (err: any) {
      feedback = `✗ 异常: ${err.message || err}`;
      isError = true;
    } finally {
      isSaving = false;
    }
  }

  // Filter rows locally if already fetched
  const filteredRows = $derived(
    rows.filter((r) => {
      if (!showZero && (r.value === '0' || r.value === '0.00' || r.value === '0.0')) return false;
      if (!showUnsupported && ['未开放', '未确认', '不支持'].includes(r.status)) return false;
      if (!filterText.trim()) return true;
      const q = filterText.toLowerCase();
      return (
        r.field.toLowerCase().includes(q) ||
        r.name.toLowerCase().includes(q) ||
        (r.searchText || '').toLowerCase().includes(q) ||
        r.value.toLowerCase().includes(q)
      );
    })
  );
</script>

<div class="fields-container">
  <!-- Controls Bar -->
  <div class="controls-card">
    <div class="input-row">
      <div class="field-group">
        <label for="rawcode-input">技能 Rawcode</label>
        <div class="input-with-tag">
          <input
            id="rawcode-input"
            type="text"
            class="input-field mono bold"
            placeholder="AHbz"
            maxlength="4"
            bind:value={rawcode}
            onkeydown={(e) => e.key === 'Enter' && handleRead()}
          />
        </div>
      </div>

      <div class="field-group narrow">
        <label for="level-input">技能等级</label>
        <input
          id="level-input"
          type="number"
          min="1"
          max="1000"
          class="input-field mono"
          bind:value={level}
          onkeydown={(e) => e.key === 'Enter' && handleRead()}
        />
      </div>

      <div class="field-group flex-1">
        <label for="filter-input">实时检索过滤</label>
        <div class="search-box">
          <Search size={14} class="search-icon" />
          <input
            id="filter-input"
            type="text"
            class="input-field"
            placeholder="按字段名 / 中文注释 / 数值筛选..."
            bind:value={filterText}
          />
        </div>
      </div>

      <div class="button-group">
        <button class="btn btn-primary" onclick={handleRead} disabled={isLoading}>
          <RefreshCw size={14} class={isLoading ? 'spinning' : ''} />
          读取技能字段
        </button>
      </div>
    </div>

    <div class="filter-options">
      <label class="checkbox-label">
        <input type="checkbox" bind:checked={showZero} />
        <span>显示数值为 0 的项</span>
      </label>
      <label class="checkbox-label">
        <input type="checkbox" bind:checked={showUnsupported} />
        <span>显示未支持字段</span>
      </label>
      {#if summary}
        <span class="summary-pill">{summary}</span>
      {/if}
    </div>
  </div>

  {#if feedback}
    <div class="feedback-banner {isError ? 'error' : 'success'}">
      {#if isError}
        <AlertCircle size={15} />
      {:else}
        <Check size={15} />
      {/if}
      <span>{feedback}</span>
    </div>
  {/if}

  {#if detail}
    <div class="detail-box">
      <Sparkles size={14} class="accent-gold" />
      <span>{detail}</span>
    </div>
  {/if}

  <!-- Table -->
  <div class="table-container">
    {#if filteredRows.length === 0}
      <div class="empty-state">
        <Sparkles size={36} class="empty-icon" />
        <div class="empty-title">{isLoading ? '正在查询技能字段...' : '无技能字段数据'}</div>
        <div class="empty-desc">
          输入目标技能的 FourCC (如 AHbz - 暴风雪, AHfs - 烈焰风暴, AHab - 辉煌光环)，然后点击“读取技能字段”。
        </div>
      </div>
    {:else}
      <table class="data-table">
        <thead>
          <tr>
            <th style="width: 140px;">字段标识 (Field)</th>
            <th style="width: 160px;">中文名称 / 说明</th>
            <th style="width: 80px;">类型</th>
            <th style="width: 80px;">作用域</th>
            <th>当前数值</th>
            <th style="width: 90px;">状态</th>
            <th style="width: 80px; text-align: center;">操作</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredRows as row}
            <tr class={editingRowId === row._iid ? 'editing-row' : ''}>
              <td class="mono font-semibold text-bright">{row.field}</td>
              <td class="text-gold field-name">{row.name || '-'}</td>
              <td><span class="type-badge">{row.type}</span></td>
              <td class="text-muted">{row.scope || '-'}</td>
              <td>
                {#if editingRowId === row._iid}
                  <div class="inline-edit-box">
                    <input
                      type="text"
                      class="edit-input mono"
                      bind:value={editingValue}
                      onkeydown={(e) => {
                        if (e.key === 'Enter') saveEdit(row);
                        if (e.key === 'Escape') cancelEdit();
                      }}
                      use:focusField
                    />
                  </div>
                {:else}
                  <span class="value-display mono">{row.value}</span>
                {/if}
              </td>
              <td>
                <span class="status-badge {row.status.includes('只读') ? 'readonly' : row.status.includes('已修改') ? 'modified' : ''}">
                  {row.status || '正常'}
                </span>
              </td>
              <td style="text-align: center;">
                {#if editingRowId === row._iid}
                  <div class="edit-actions">
                    <button class="btn-icon save" onclick={() => saveEdit(row)} disabled={isSaving} title="保存修改">
                      <Save size={13} />
                    </button>
                    <button class="btn-icon cancel" onclick={cancelEdit} title="取消">
                      <X size={13} />
                    </button>
                  </div>
                {:else}
                  <button class="btn-icon edit" onclick={() => startEdit(row)} title="编辑此字段值">
                    <Edit2 size={13} />
                  </button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>

  <div class="footer-bar">
    <span>共显示 {filteredRows.length} / {rows.length} 个字段</span>
    <span class="tip">💡 双击数值或点击编辑图标即可修改并写入游戏内存</span>
  </div>
</div>

<style>
  .field-name {
    min-width: 160px;
    max-width: 280px;
    white-space: normal;
    overflow-wrap: anywhere;
    line-height: 1.5;
  }

  .fields-container {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 16px;
    gap: 12px;
    background-color: var(--bg-surface);
    overflow: hidden;
  }

  .controls-card {
    background: var(--bg-surface-sunken);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .input-row {
    display: flex;
    gap: 12px;
    align-items: flex-end;
  }

  .field-group {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .field-group label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
  }

  .field-group.narrow {
    width: 80px;
  }

  .field-group.flex-1 {
    flex: 1;
  }

  .input-field {
    height: 32px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 0 10px;
    color: var(--text-bright);
    font-size: 13px;
    outline: none;
    transition: border-color 0.15s ease;
  }

  .input-field:focus {
    border-color: var(--color-gold);
  }

  .mono {
    font-family: var(--font-mono);
  }

  .bold {
    font-weight: 700;
    letter-spacing: 0.5px;
  }

  .search-box {
    position: relative;
    display: flex;
    align-items: center;
  }

  .fields-container .search-box :global(.search-icon) {
    position: absolute;
    left: 10px;
    color: var(--text-muted);
    pointer-events: none;
  }

  .search-box input {
    width: 100%;
    padding-left: 32px;
  }

  .button-group {
    display: flex;
    gap: 8px;
  }

  .filter-options {
    display: flex;
    align-items: center;
    gap: 16px;
    font-size: 12px;
    color: var(--text-muted);
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    user-select: none;
  }

  .summary-pill {
    margin-left: auto;
    font-size: 11px;
    background: rgba(229, 193, 88, 0.1);
    color: var(--color-gold);
    border: 1px solid rgba(229, 193, 88, 0.2);
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
  }

  .detail-box {
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--bg-raised);
    padding: 6px 12px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-subtle);
    font-size: 12px;
    color: var(--text-normal);
  }

  .fields-container :global(.accent-gold) {
    color: var(--color-gold);
  }

  .text-gold {
    color: var(--color-gold);
    font-weight: 500;
  }

  .text-bright {
    color: var(--text-bright);
  }

  .text-muted {
    color: var(--text-muted);
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

  .data-table tbody tr.editing-row {
    background-color: rgba(229, 193, 88, 0.08);
  }

  .type-badge {
    display: inline-block;
    padding: 2px 7px;
    background: var(--bg-card);
    border: 1px solid var(--border-normal);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
  }

  .value-display {
    font-weight: 600;
    color: var(--fel-green);
  }

  .status-badge {
    display: inline-block;
    font-size: 11px;
    padding: 1px 6px;
    border-radius: var(--radius-sm);
    background: var(--status-neutral-bg);
    color: var(--text-muted);
  }

  .status-badge.readonly {
    color: var(--status-warning-text);
    background: var(--status-warning-bg);
  }

  .status-badge.modified {
    color: var(--status-success-text);
    background: var(--status-success-bg);
  }

  .inline-edit-box {
    display: flex;
    align-items: center;
  }

  .edit-input {
    height: 24px;
    background: var(--bg-surface);
    border: 1px solid var(--color-gold);
    border-radius: var(--radius-sm);
    padding: 0 6px;
    color: var(--text-bright);
    font-size: 12px;
    width: 120px;
  }

  .edit-actions {
    display: flex;
    justify-content: center;
    gap: 4px;
  }

  .btn-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 24px;
    height: 24px;
    border-radius: var(--radius-sm);
    background: transparent;
    border: 1px solid var(--border-subtle);
    cursor: pointer;
    color: var(--text-muted);
    transition: all 0.15s ease;
  }

  .btn-icon.edit:hover {
    color: var(--color-gold);
    border-color: var(--color-gold);
  }

  .btn-icon.save {
    color: var(--status-success-text);
    border-color: rgba(46, 204, 113, 0.4);
  }

  .btn-icon.save:hover {
    background: var(--status-success-bg);
  }

  .btn-icon.cancel:hover {
    color: var(--status-danger-text);
    border-color: rgba(231, 76, 60, 0.4);
  }

  .footer-bar {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: var(--text-muted);
    padding: 2px 0;
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

  .fields-container :global(.empty-icon) {
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

  .fields-container :global(.spinning) {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
