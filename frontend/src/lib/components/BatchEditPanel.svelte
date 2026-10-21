<script lang="ts">
  import { onMount,onDestroy } from 'svelte';
  import { api } from '../api';
  import { Layers, CheckSquare, Square, RefreshCw, Check, Play, Trash2 } from 'lucide-svelte';

  interface BatchUnit {
    checked: boolean;
    rawcode: string;
    instance: string;
    hp: string;
    mp: string;
  }

  interface BatchReportRow {
    unit: string;
    field: string;
    target: string;
    status: string;
    reason: string;
  }

  let units = $state<BatchUnit[]>([]);
  let reports = $state<BatchReportRow[]>([]);
  let loading = $state(false);
  let statusMessage = $state('请先在游戏中拉框选中多个单位，然后点击“读取所有选中单位”');

  // Editable target fields
  let targetFields = $state<Record<string, string>>({
    hp_current: '',
    hp_max: '',
    mp_current: '',
    mp_max: '',
    base_strength: '',
    base_agility: '',
    base_intelligence: '',
    hero_level: '',
    move_speed: '',
    attack_speed: '',
  });

  let fieldDefinitions = $state<{key: string; label: string}[]>([]);

  async function handleReadUnits() {
    loading = true;
    try {
      const res = await api.batchReadUnits();
      if (res.success && res.units) {
        units = res.units;
        fieldDefinitions = res.fields || [];
        targetFields = Object.fromEntries(fieldDefinitions.map(f => [f.key, targetFields[f.key] || '']));
        statusMessage = `已成功解析 ${units.length} 个选中单位实例`;
      } else {
        statusMessage = res.error || '未读取到选中单位';
      }
    } catch (err: any) {
      statusMessage = err.message || '读取异常';
    } finally {
      loading = false;
    }
  }

  function handleSelectAll(checked: boolean) {
    for (const u of units) {
      u.checked = checked;
    }
  }
  onMount(()=>window.addEventListener('war3-batch-read',handleReadUnits));
  onDestroy(()=>window.removeEventListener('war3-batch-read',handleReadUnits));

  function handleClearTargets() {
    for (const k of Object.keys(targetFields)) {
      targetFields[k] = '';
    }
  }

  async function handleBatchWrite() {
    const selectedInstances = units.filter((u) => u.checked).map((u) => u.instance);
    if (selectedInstances.length === 0) {
      statusMessage = '请先勾选需要批量修改的单位';
      window.dispatchEvent(new CustomEvent('war3-error',{detail:statusMessage}));
      return;
    }
    const activeTargets: Record<string, string> = {};
    for (const [k, v] of Object.entries(targetFields)) {
      if (v.trim()) activeTargets[k] = v.trim();
    }
    if (Object.keys(activeTargets).length === 0) {
      statusMessage = '请至少填写一个目标修改值';
      window.dispatchEvent(new CustomEvent('war3-error',{detail:statusMessage}));
      return;
    }

    loading = true;
    try {
      const res = await api.batchWriteUnits(selectedInstances, activeTargets);
      if (res.success) {
        statusMessage = res.message || '批量修改已下发执行';
        reports = res.reports || [];
      } else {
        statusMessage = `批量修改失败: ${res.error}`;
      }
    } catch (err: any) {
      statusMessage = `执行异常: ${err.message || err}`;
    } finally {
      loading = false;
    }
  }
</script>

<div class="batch-layout">
  <!-- Header & Toolbar -->
  <div class="panel-header">
    <div class="header-left">
      <Layers size={18} class="text-gold" />
      <h2 class="panel-title">多单位批量修改</h2>
    </div>
    <div class="header-actions">
      <button class="btn btn-primary btn-sm" onclick={handleReadUnits} disabled={loading}>
        <RefreshCw size={13} class={loading ? 'spin' : ''} />
        读取所有选中单位
      </button>
      <button class="btn btn-secondary btn-sm" onclick={() => handleSelectAll(true)}>
        <CheckSquare size={13} /> 全选
      </button>
      <button class="btn btn-secondary btn-sm" onclick={() => handleSelectAll(false)}>
        <Square size={13} /> 全不选
      </button>
      <button class="btn btn-primary btn-sm" onclick={handleBatchWrite} disabled={loading}>
        <Play size={13} /> 批量修改
      </button>
      <button class="btn btn-secondary btn-sm" onclick={handleClearTargets}>
        <Trash2 size={13} /> 清空目标值
      </button>
    </div>
  </div>

  <div class="status-banner">
    <span class="label">当前提示:</span> {statusMessage}
  </div>

  <!-- Two-column panes -->
  <div class="panes-grid">
    <!-- Left: Units Checklist -->
    <div class="pane-card">
      <div class="card-header">
        <span class="card-title">待处理单位列表 ({units.length})</span>
      </div>
      <div class="game-table-container table-wrap">
        <table class="game-table">
          <thead>
            <tr>
              <th style="width: 45px;">勾选</th>
              <th style="width: 80px;">单位代码</th>
              <th style="width: 120px;">实例地址</th>
              <th style="width: 70px;">生命</th>
              <th>魔法</th>
            </tr>
          </thead>
          <tbody>
            {#if units.length === 0}
              <tr>
                <td colspan="5" class="empty-cell">暂无单位，请拉框选中后读取</td>
              </tr>
            {:else}
              {#each units as u}
                <tr onclick={() => (u.checked = !u.checked)}>
                  <td>
                    <input type="checkbox" checked={u.checked} />
                  </td>
                  <td><span class="rawcode-chip">{u.rawcode}</span></td>
                  <td class="font-mono text-muted">{u.instance}</td>
                  <td class="font-mono text-crimson">{u.hp}</td>
                  <td class="font-mono text-cyan">{u.mp}</td>
                </tr>
              {/each}
            {/if}
          </tbody>
        </table>
      </div>
    </div>

    <!-- Right: Field Target Configs -->
    <div class="pane-card">
      <div class="card-header">
        <span class="card-title">批量目标属性配置</span>
        <span class="hint">留空的属性将保持单位原有数值不变</span>
      </div>
      <div class="fields-grid-scroll">
        <div class="fields-grid">
          {#each fieldDefinitions as fd}
            <div class="field-item">
              <label for="batch-{fd.key}">{fd.label}</label>
              <input
                id="batch-{fd.key}"
                type="text"
                class="mono"
                placeholder="保持原值"
                bind:value={targetFields[fd.key]}
              />
            </div>
          {/each}
        </div>
      </div>
    </div>
  </div>

  <!-- Execution Results Report Table -->
  <div class="report-section">
    <div class="section-title">执行报告与读回校验 ({reports.length} 条)</div>
    <div class="game-table-container report-table-wrap">
      <table class="game-table">
        <thead>
          <tr>
            <th style="width: 130px;">单位实例</th>
            <th style="width: 140px;">字段</th>
            <th style="width: 100px;">目标值</th>
            <th style="width: 70px;">结果</th>
            <th>读回或跳过原因</th>
          </tr>
        </thead>
        <tbody>
          {#if reports.length === 0}
            <tr>
              <td colspan="5" class="empty-cell">尚未执行批量修改</td>
            </tr>
          {:else}
            {#each reports as r}
              <tr>
                <td class="font-mono text-muted">{r.unit}</td>
                <td>{r.field}</td>
                <td class="font-mono text-gold">{r.target}</td>
                <td><span class="ok-chip">{r.status}</span></td>
                <td class="text-secondary">{r.reason}</td>
              </tr>
            {/each}
          {/if}
        </tbody>
      </table>
    </div>
  </div>
</div>

<style>
  .batch-layout {
    display: flex;
    flex-direction: column;
    gap: 12px;
    height: 100%;
    padding: 16px;
    overflow-y: auto;
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
    gap: 6px;
  }

  .status-banner {
    background-color: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 8px 14px;
    font-size: 12px;
    color: var(--text-normal);
  }
  .status-banner .label {
    font-weight: 700;
    color: var(--color-gold);
    margin-right: 6px;
  }

  .panes-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .pane-card {
    background-color: var(--bg-card);
    border: 1px solid var(--border-normal);
    border-radius: var(--radius-md);
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-subtle);
  }

  .card-title {
    font-size: 13px;
    font-weight: 700;
    color: var(--text-bright);
  }

  .hint {
    font-size: 11px;
    color: var(--text-muted);
  }

  .table-wrap {
    height: 190px;
  }

  .fields-grid-scroll {
    height: 190px;
    overflow-y: auto;
  }

  .fields-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  .field-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .field-item label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-bright);
  }

  .report-section {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .section-title {
    font-size: 12px;
    font-weight: 700;
    color: var(--text-primary);
  }

  .report-table-wrap {
    height: 140px;
  }

  .empty-cell {
    text-align: center;
    padding: 24px;
    color: var(--text-muted);
    font-style: italic;
  }

  .ok-chip {
    background-color: var(--status-success-bg);
    color: var(--status-success-text);
    padding: 1px 6px;
    border-radius: 2px;
    font-size: 10px;
    font-weight: 600;
  }

  .text-gold { color: var(--color-gold); }
  .text-crimson { color: var(--health-crimson); }
  .text-cyan { color: var(--mana-cyan); }
  .text-muted { color: var(--text-muted); }
  .text-secondary { color: var(--text-secondary); }

  .batch-layout :global(.spin) {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
