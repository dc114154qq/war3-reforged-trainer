<script lang="ts">
  function focusField(node: HTMLInputElement) { node.focus(); }
  import { api } from '../api';
  import type { ItemFieldRow, ItemFieldsData } from '../types';
  import { Package, RefreshCw, Search, Check, AlertCircle, Edit2, X, Save } from 'lucide-svelte';

  let selectedSlot = $state('0'); // 0-5
  let filterText = $state('');
  let showZero = $state(true);
  let showUnsupported = $state(true);

  let isLoading = $state(false);
  let summary = $state('');
  let detail = $state('');
  let rows = $state<ItemFieldRow[]>([]);
  let feedback = $state('');
  let isError = $state(false);

  // Inline editing state
  let editingRowId = $state<string | null>(null);
  let editingValue = $state('');
  let isSaving = $state(false);

  const slots = [
    { id: '0', label: '槽位 1' },
    { id: '1', label: '槽位 2' },
    { id: '2', label: '槽位 3' },
    { id: '3', label: '槽位 4' },
    { id: '4', label: '槽位 5' },
    { id: '5', label: '槽位 6' },
  ];

  async function handleRead(slotId: string = selectedSlot) {
    selectedSlot = slotId;
    isLoading = true;
    feedback = '';
    try {
      const data: ItemFieldsData = await api.readItemFields(
        selectedSlot,
        filterText.trim(),
        showZero,
        showUnsupported
      );
      summary = data.summary;
      detail = data.detail;
      rows = data.rows || [];
      isError = false;
      if (rows.length === 0) {
        feedback = `当前槽位 [${parseInt(selectedSlot, 10) + 1}] 为空或未找到物品字段`;
      }
    } catch (err: any) {
      feedback = `读取失败: ${err.message || err}`;
      isError = true;
      rows = [];
    } finally {
      isLoading = false;
    }
  }

  function startEdit(row: ItemFieldRow) {
    editingRowId = row._iid;
    editingValue = row.value;
  }

  function cancelEdit() {
    editingRowId = null;
    editingValue = '';
  }

  async function saveEdit(row: ItemFieldRow) {
    isSaving = true;
    try {
      const res = await api.writeItemField(row._iid, editingValue);
      if (res.success) {
        if (res.data) { rows = res.data.rows; summary = res.data.summary; detail = res.data.detail; }
        editingRowId = null;
        feedback = `✓ 物品字段 [${row.name || row.field}] 已写入: ${editingValue}`;
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

  const filteredRows = $derived(
    rows.filter((r) => {
      if (!showZero && (r.value === '0' || r.value === '0.00' || r.value === '0.0')) return false;
      if (!showUnsupported && ['未开放', '未确认', '不支持'].includes(r.status)) return false;
      if (!filterText.trim()) return true;
      const q = filterText.toLowerCase();
      return (
        r.field.toLowerCase().includes(q) ||
        r.name.toLowerCase().includes(q) ||
        r.value.toLowerCase().includes(q)
      );
    })
  );
</script>

<div class="fields-container">
  <!-- Controls Bar -->
  <div class="controls-card">
    <div class="top-row">
      <div class="slot-selector">
        <span class="selector-label">物品栏槽位:</span>
        <div class="slot-chips">
          {#each slots as s}
            <button
              class="slot-chip {selectedSlot === s.id ? 'active' : ''}"
              onclick={() => handleRead(s.id)}
            >
              <Package size={13} />
              <span>{s.label}</span>
            </button>
          {/each}
        </div>
      </div>

      <div class="button-group">
        <button class="btn btn-primary" onclick={() => handleRead()} disabled={isLoading}>
          <RefreshCw size={14} class={isLoading ? 'spinning' : ''} />
          读取选定槽位
        </button>
      </div>
    </div>

    <div class="bottom-row">
      <div class="search-box flex-1">
        <Search size={14} class="search-icon" />
        <input
          type="text"
          class="input-field"
          placeholder="按字段标识 / 名称 / 数值过滤..."
          bind:value={filterText}
        />
      </div>

      <div class="filter-options">
        <label class="checkbox-label">
          <input type="checkbox" bind:checked={showZero} />
          <span>显示0值项</span>
        </label>
        <label class="checkbox-label">
          <input type="checkbox" bind:checked={showUnsupported} />
          <span>显示未支持字段</span>
        </label>
      </div>

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
      <Package size={14} class="accent-gold" />
      <span>{detail}</span>
    </div>
  {/if}

  <!-- Table -->
  <div class="table-container">
    {#if filteredRows.length === 0}
      <div class="empty-state">
        <Package size={36} class="empty-icon" />
        <div class="empty-title">{isLoading ? '正在读取物品字段...' : '当前槽位无数据'}</div>
        <div class="empty-desc">
          请确保游戏中选中持有物品的英雄或单位，选择对应槽位（槽位 1 - 6）并点击“读取选定槽位”。
        </div>
      </div>
    {:else}
      <table class="data-table">
        <thead>
          <tr>
            <th style="width: 150px;">字段标识 (Field)</th>
            <th style="width: 180px;">属性名称 / 说明</th>
            <th style="width: 90px;">类型</th>
            <th>当前数值</th>
            <th style="width: 100px;">状态</th>
            <th style="width: 80px; text-align: center;">操作</th>
          </tr>
        </thead>
        <tbody>
          {#each filteredRows as row}
            <tr class={editingRowId === row._iid ? 'editing-row' : ''}>
              <td class="mono font-semibold text-bright">{row.field}</td>
              <td class="text-gold">{row.name || '-'}</td>
              <td><span class="type-badge">{row.type}</span></td>
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
    <span>共显示 {filteredRows.length} / {rows.length} 个物品字段</span>
    <span class="tip">💡 支持读取和修改物品的使用次数(charges)、冷却时间、属性加成与分类标识</span>
  </div>
</div>

<style>
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

  .top-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .slot-selector {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .selector-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
  }

  .slot-chips {
    display: flex;
    gap: 6px;
  }

  .slot-chip {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 28px;
    padding: 0 10px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    color: var(--text-normal);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .slot-chip:hover {
    border-color: var(--color-gold);
    color: var(--text-bright);
  }

  .slot-chip.active {
    background: rgba(229, 193, 88, 0.15);
    border-color: var(--color-gold);
    color: var(--color-gold);
    font-weight: 700;
  }

  .bottom-row {
    display: flex;
    gap: 12px;
    align-items: center;
  }

  .flex-1 {
    flex: 1;
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
    height: 30px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 0 10px 0 32px;
    color: var(--text-bright);
    font-size: 12px;
    outline: none;
  }

  .search-box input:focus {
    border-color: var(--color-gold);
  }

  .filter-options {
    display: flex;
    align-items: center;
    gap: 14px;
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

  .mono {
    font-family: var(--font-mono);
  }

  .font-semibold {
    font-weight: 600;
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
