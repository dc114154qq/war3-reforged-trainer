<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../api';
  import type { LockItem } from '../types';
  import { Lock, Unlock, Play, RefreshCw, AlertCircle, Check } from 'lucide-svelte';

  let locks = $state<LockItem[]>([]);
  let isLoading = $state(false);
  let feedback = $state('');
  let isError = $state(false);

  async function loadLocks() {
    isLoading = true;
    try {
      locks = await api.getLocks();
    } catch (err: any) {
      feedback = `获取锁定列表失败: ${err.message || err}`;
      isError = true;
    } finally {
      isLoading = false;
    }
  }

  async function handleApplyOnce() {
    feedback = '正在执行单次写入...';
    isError = false;
    try {
      const res = await api.applyLocksOnce();
      if (res.success) {
        feedback = res.message || '✓ 单次写入完成';
      } else {
        feedback = `✗ 执行失败: ${res.error}`;
        isError = true;
      }
      setTimeout(() => (feedback = ''), 3000);
    } catch (err: any) {
      feedback = `✗ 异常: ${err.message || err}`;
      isError = true;
    }
  }

  async function handleRemove(lockIid: string) {
    try {
      const res = await api.removeLock(lockIid);
      if (res.success) {
        locks = res.locks;
        feedback = '✓ 已解除锁定';
      } else {
        feedback = `✗ 解除失败: ${res.error}`;
        isError = true;
      }
      setTimeout(() => (feedback = ''), 2500);
    } catch (err: any) {
      feedback = `✗ 异常: ${err.message || err}`;
      isError = true;
    }
  }

  onMount(() => {
    loadLocks();
  });
</script>

<div class="locks-container">
  <div class="header-bar">
    <div class="title-area">
      <div class="title-with-icon">
        <Lock size={18} class="accent-gold" />
        <h2>锁定列表与定值守护</h2>
      </div>
      <div class="stats-badge">当前已锁定: <span class="accent-gold">{locks.length}</span> 项</div>
    </div>

    <div class="actions">
      <button class="btn btn-secondary" onclick={loadLocks} disabled={isLoading}>
        <RefreshCw size={14} class={isLoading ? 'spinning' : ''} />
        刷新
      </button>
      <button class="btn btn-primary" onclick={handleApplyOnce} disabled={isLoading || locks.length === 0}>
        <Play size={14} />
        全部单次写入
      </button>
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

  <div class="table-container">
    {#if locks.length === 0}
      <div class="empty-state">
        <Unlock size={36} class="empty-icon" />
        <div class="empty-title">当前没有活动的内存锁定项</div>
        <div class="empty-desc">
          在【玩家资源】点击“锁定”按钮，或在【选中单位】详细属性中点击“锁定”，均会在此处自动生成守护项。
        </div>
      </div>
    {:else}
      <table class="data-table">
        <thead>
          <tr>
            <th style="width: 120px;">作用域</th>
            <th>监控属性名称 / 标识</th>
            <th style="width: 180px;">锁定数值 / 状态</th>
            <th style="width: 90px; text-align: center;">操作</th>
          </tr>
        </thead>
        <tbody>
          {#each locks as lock}
            <tr>
              <td>
                <span class="scope-tag">{lock.scope}</span>
              </td>
              <td>
                <span class="label-text">{lock.label}</span>
              </td>
              <td>
                <span class="value-badge">{lock.value}</span>
              </td>
              <td style="text-align: center;">
                <button
                  class="btn-icon-danger"
                  title="解除此属性的锁定"
                  onclick={() => handleRemove(lock._iid)}
                >
                  <Unlock size={14} />
                  <span>解锁</span>
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </div>
</div>

<style>
  .locks-container {
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
    border-bottom: 1px solid var(--border-subtle);
    padding-bottom: 12px;
  }

  .title-area {
    display: flex;
    align-items: baseline;
    gap: 12px;
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
    background: var(--bg-raised);
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-subtle);
  }

  .accent-gold {
    color: var(--color-gold);
    font-weight: 700;
  }

  .actions {
    display: flex;
    gap: 8px;
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

  .locks-container :global(.empty-icon) {
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
    max-width: 420px;
    line-height: 1.5;
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }

  .data-table th {
    background: var(--bg-table-header);
    color: var(--text-gold);
    font-weight: 700;
    text-align: left;
    padding: 8px 12px;
    border-bottom: 2px solid var(--border-subtle);
    position: sticky;
    top: 0;
    z-index: 1;
    font-size: 12px;
    letter-spacing: 0.5px;
  }

  .data-table td {
    padding: 8px 12px;
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-normal);
    font-size: 13px;
  }

  .data-table tbody tr:hover {
    background-color: var(--bg-raised);
  }

  .scope-tag {
    display: inline-block;
    padding: 2px 8px;
    background: rgba(245, 158, 11, 0.15);
    color: var(--color-gold);
    border: 1px solid rgba(245, 158, 11, 0.35);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: 12px;
    font-weight: 600;
  }

  .label-text {
    font-weight: 600;
    font-size: 13px;
    color: var(--text-bright);
  }

  .value-badge {
    display: inline-block;
    font-family: var(--font-mono);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    padding: 3px 10px;
    border-radius: var(--radius-sm);
    color: var(--fel-green);
    font-weight: 700;
    font-size: 13px;
  }

  .btn-icon-danger {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    background: transparent;
    border: 1px solid rgba(231, 76, 60, 0.3);
    color: var(--status-danger-text);
    border-radius: var(--radius-sm);
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn-icon-danger:hover {
    background: var(--status-danger-bg);
    border-color: var(--status-danger-text);
  }

  .locks-container :global(.spinning) {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
