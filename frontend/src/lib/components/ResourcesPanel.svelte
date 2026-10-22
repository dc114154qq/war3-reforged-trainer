<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../api';
  import type { ResourceSnapshot, ResourceGroup, GoldMineData } from '../types';
  import { Coins, Trees, Users, RefreshCw, Lock, Plus, Minus } from 'lucide-svelte';

  let snapshot = $state<ResourceSnapshot>({
    current: { gold: '', lumber: '', food: '', foodCap: '' },
    targets: { gold: '1000000', lumber: '1000000', foodUsed: '0', foodCap: '100' },
    delta: '10000',
    groups: [],
  });

  let selectedGroup = $state<ResourceGroup | null>(null);
  let loading = $state(false);
  let mineAmount = $state('1000000');
  let mineBusy = $state(false);
  let mineSeconds = $state(0);
  let mineResult = $state<GoldMineData | null>(null);
  let mineError = $state('');

  async function handleMines(scope: 'selected' | 'world', write = false) {
    if (mineBusy) return;
    mineBusy = true;
    mineError = '';
    mineResult = null;
    mineSeconds = 0;
    const started = Date.now();
    const timer = setInterval(() => { mineSeconds = Math.floor((Date.now() - started) / 1000); }, 250);
    try {
      const res = await api.goldMines(scope, write ? mineAmount : undefined);
      mineResult = res.data ?? null;
      mineError = res.success ? '' : (res.error ?? '操作未完成');
    } catch (err) {
      mineError = err instanceof Error ? err.message : String(err);
    } finally {
      clearInterval(timer);
      mineBusy = false;
    }
  }

  async function loadData() {
    loading = true;
    try {
      const res = await api.getResourceSnapshot();
      snapshot = res;
      if (res.groups.length > 0 && !selectedGroup) {
        selectedGroup = res.groups[0];
      }
    } catch (err) {
      console.error(err);
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    loadData();
  });

  async function handleRefreshGroups() {
    loading = true;
    try {
      const res = await api.refreshResources();
      if (res.success) {
        snapshot = res.data;
        if (res.data.groups.length > 0) {
          selectedGroup = res.data.groups[0];
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      loading = false;
    }
  }

  async function handleSetResource(kind: string, val: string) {
    try {
      const res = await api.setResource(kind, val);
      if (res.success) snapshot = res.data;
    } catch (err) {
      console.error(err);
    }
  }

  async function handleAddResource(kind: string) {
    try {
      const res = await api.addResource(kind, snapshot.delta);
      if (res.success) snapshot = res.data;
    } catch (err) {
      console.error(err);
    }
  }

  async function handleLock(kind: string) {
    try {
      await api.addResourceLock(kind);
      await loadData();
    } catch (err) {
      console.error(err);
    }
  }
</script>

<div class="panel-layout">
  <!-- Top: Toolbar -->
  <div class="panel-header">
    <div class="header-left">
      <Coins size={18} class="panel-icon" />
      <h2 class="panel-title">玩家资源管理</h2>
    </div>
    <button class="btn btn-secondary btn-sm" onclick={handleRefreshGroups} disabled={loading}>
      <RefreshCw size={13} class={loading ? 'spin' : ''} />
      读取全部资源组
    </button>
  </div>

  <!-- Resource Group Tree Table -->
  <div class="groups-section">
    <div class="section-badge">检测到的内存资源组 ({snapshot.groups.length})</div>
    <div class="game-table-container table-wrap">
      <table class="game-table">
        <thead>
          <tr>
            <th>资源组别</th>
            <th>金币</th>
            <th>木材</th>
            <th>人口</th>
            <th>金币内存地址</th>
            <th>木材内存地址</th>
            <th>数据来源与证明</th>
          </tr>
        </thead>
        <tbody>
          {#if snapshot.groups.length === 0}
            <tr>
              <td colspan="7" class="empty-cell">未检测到内存资源组，请先连接魔兽争霸 III 进程并载入地图</td>
            </tr>
          {:else}
            {#each snapshot.groups as g}
              <tr
                class={selectedGroup?._iid === g._iid ? 'selected' : ''}
                onclick={async () => { selectedGroup = g; snapshot = await api.selectResourceGroup(g._iid); }}
              >
                <td><strong>{g.group}</strong></td>
                <td class="font-mono text-gold">{g.gold}</td>
                <td class="font-mono text-green">{g.lumber}</td>
                <td class="font-mono text-cyan">{g.food}</td>
                <td class="font-mono text-muted">{g.gold_address}</td>
                <td class="font-mono text-muted">{g.lumber_address}</td>
                <td class="text-secondary">{g.source}</td>
              </tr>
            {/each}
          {/if}
        </tbody>
      </table>
    </div>
  </div>

  <section class="resource-card gold-border mine-section" aria-label="金矿剩余金币">
    <div class="card-title"><Coins size={16} class="text-gold" /><span>金矿剩余金币</span></div>
    <p class="mine-help">设置的是每座金矿剩余可采的金币。全图操作包含其他玩家和中立金矿；非金矿、已移除的矿点会跳过。</p>
    <div class="mine-controls">
      <div class="input-row">
        <label for="mine-amount">每座金矿的目标剩余金币</label>
        <input id="mine-amount" type="text" inputmode="numeric" class="mono" bind:value={mineAmount} disabled={mineBusy} />
      </div>
      <div class="btn-row">
        <button class="btn btn-secondary btn-sm" disabled={mineBusy} onclick={() => handleMines('selected')}>读取选中金矿</button>
        <button class="btn btn-primary btn-sm" disabled={mineBusy} onclick={() => handleMines('selected', true)}>修改选中金矿</button>
        <button class="btn btn-secondary btn-sm" disabled={mineBusy} onclick={() => handleMines('world')}>读取全图金矿</button>
        <button class="btn btn-primary btn-sm" disabled={mineBusy} onclick={() => handleMines('world', true)}>批量修改全图金矿</button>
      </div>
    </div>
    <p class="mine-help">支持普通、缠绕和闹鬼金矿。数值范围 0–100000000；设为 0 会耗尽金矿。点击修改时会重新读取当前范围。</p>
    {#if mineBusy}
      <div class="mine-feedback" role="status">正在处理金矿… {mineSeconds} s</div>
    {:else if mineResult}
      <div class="mine-feedback" role="status">
        <span>金矿数量：{mineResult.count}</span>
        {#if mineResult.action}
          <span>已修改：{mineResult.changed}</span><span>已符合目标：{mineResult.unchanged}</span><span>跳过或失败：{mineResult.failed}</span>
        {/if}
        <span>范围：{mineResult.scope === 'world' ? '全图金矿' : '当前选中金矿'}</span>
      </div>
    {/if}
    {#if mineError}<p class="mine-error" role="alert">{mineError}</p>{/if}
    {#if mineResult}
      <div class="game-table-container table-wrap mine-table">
        <table class="game-table">
          <thead><tr><th>金矿代码</th><th>金矿类型</th><th>玩家槽位</th><th>坐标</th><th>读取时金币</th><th>操作后金币</th><th>结果</th></tr></thead>
          <tbody>
            {#each mineResult.rows as row (row.handle)}
              <tr><td class="font-mono">{row.rawcode}</td><td>{row.kind}</td><td>{row.owner}</td>
                <td class="font-mono">{row.x.toFixed(1)}, {row.y.toFixed(1)}</td><td class="font-mono">{row.before}</td>
                <td class="font-mono">{row.after < 0 ? '待确认' : row.after}</td><td>{row.status}{row.error ? ` (${row.error})` : ''}</td></tr>
            {:else}
              <tr><td colspan="7" class="empty-cell">当前范围未读取到金矿。</td></tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </section>

  <!-- Bottom Control Grid -->
  <div class="controls-grid">
    <!-- Card: Gold -->
    <div class="resource-card gold-border">
      <div class="card-title">
        <Coins size={16} class="text-gold" />
        <span>金币 (Gold)</span>
        <span class="current-val font-mono">当前: {snapshot.current.gold || '---'}</span>
      </div>
      <div class="card-inputs">
        <div class="input-row">
          <label for="gold-target">目标数值</label>
          <input id="gold-target" type="text" class="mono" bind:value={snapshot.targets.gold} />
        </div>
        <div class="btn-row">
          <button class="btn btn-primary btn-sm" onclick={() => handleSetResource('gold', snapshot.targets.gold)}>
            设置金币
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => handleLock('gold')}>
            <Lock size={12} /> 锁定金币
          </button>
        </div>
      </div>
    </div>

    <!-- Card: Lumber -->
    <div class="resource-card green-border">
      <div class="card-title">
        <Trees size={16} class="text-green" />
        <span>木材 (Lumber)</span>
        <span class="current-val font-mono">当前: {snapshot.current.lumber || '---'}</span>
      </div>
      <div class="card-inputs">
        <div class="input-row">
          <label for="lumber-target">目标数值</label>
          <input id="lumber-target" type="text" class="mono" bind:value={snapshot.targets.lumber} />
        </div>
        <div class="btn-row">
          <button class="btn btn-primary btn-sm" onclick={() => handleSetResource('lumber', snapshot.targets.lumber)}>
            设置木材
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => handleLock('lumber')}>
            <Lock size={12} /> 锁定木材
          </button>
        </div>
      </div>
    </div>

    <!-- Card: Food Used & Cap -->
    <div class="resource-card cyan-border">
      <div class="card-title">
        <Users size={16} class="text-cyan" />
        <span>人口 (Food)</span>
        <span class="current-val font-mono">当前: {snapshot.current.food || '---'} / {snapshot.current.foodCap || '---'}</span>
      </div>
      <div class="card-inputs">
        <div class="split-inputs">
          <div class="input-row">
            <label for="food-used-target">当前占用</label>
            <input id="food-used-target" type="text" class="mono" bind:value={snapshot.targets.foodUsed} />
          </div>
          <div class="input-row">
            <label for="food-cap-target">人口上限</label>
            <input id="food-cap-target" type="text" class="mono" bind:value={snapshot.targets.foodCap} />
          </div>
        </div>
        <div class="btn-row">
          <button class="btn btn-primary btn-sm" onclick={() => handleSetResource('food_used', snapshot.targets.foodUsed)}>
            改占用
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => handleLock('food_used')}>
            锁占用
          </button>
          <button class="btn btn-primary btn-sm" onclick={() => handleSetResource('food_cap', snapshot.targets.foodCap)}>
            改上限
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => handleLock('food_cap')}>
            锁上限
          </button>
        </div>
      </div>
    </div>

    <!-- Card: Increments +/- -->
    <div class="resource-card purple-border">
      <div class="card-title">
        <span>快速增量调节 (+/-)</span>
      </div>
      <div class="card-inputs">
        <div class="input-row">
          <label for="res-delta">单次增量</label>
          <input id="res-delta" type="text" class="mono" bind:value={snapshot.delta} />
        </div>
        <div class="btn-row">
          <button class="btn btn-secondary btn-sm" onclick={() => handleAddResource('gold')}>
            金币 +/-
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => handleAddResource('lumber')}>
            木材 +/-
          </button>
          <button class="btn btn-primary btn-sm" onclick={() => handleAddResource('both')}>
            金+木一起增减
          </button>
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .mine-section { flex-shrink: 0; min-width: 0; }
  .mine-controls { display: flex; align-items: end; gap: 12px; flex-wrap: wrap; }
  .mine-controls .input-row { min-width: 180px; flex: 0 1 240px; }
  .mine-help { margin: 0; font-size: 12px; line-height: 1.65; color: var(--text-secondary); overflow-wrap: anywhere; }
  .mine-feedback { display: flex; flex-wrap: wrap; gap: 6px 16px; color: var(--text-primary); line-height: 1.6; }
  .mine-error { margin: 0; color: var(--status-danger-text); line-height: 1.6; overflow-wrap: anywhere; }
  .mine-table { max-height: 280px; overflow: auto; }
  .mine-table table { min-width: 660px; }
  .panel-layout {
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

  .panel-layout :global(.panel-icon) {
    color: var(--color-gold);
  }

  .panel-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-bright);
  }

  .groups-section {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .section-badge {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
  }

  .table-wrap {
    max-height: 160px;
  }

  .empty-cell {
    text-align: center;
    padding: 24px;
    color: var(--text-muted);
    font-style: italic;
  }

  .controls-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 12px;
  }

  .resource-card {
    background-color: var(--bg-card);
    border: 1px solid var(--border-normal);
    border-radius: var(--radius-md);
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
  }

  .gold-border { border-top: 2px solid var(--gold-500); }
  .green-border { border-top: 2px solid var(--fel-green); }
  .cyan-border { border-top: 2px solid var(--mana-cyan); }
  .purple-border { border-top: 2px solid var(--arcane-purple); }

  .card-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 700;
    font-size: 13px;
    color: var(--text-primary);
  }

  .current-val {
    margin-left: auto;
    font-size: 13px;
    font-weight: 700;
    color: var(--text-gold);
    background: var(--bg-value);
    padding: 2px 8px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-subtle);
  }

  .green-border .current-val {
    color: var(--fel-green);
  }

  .cyan-border .current-val {
    color: var(--mana-cyan);
  }

  .card-inputs {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .input-row {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .input-row label {
    font-size: 11px;
    text-transform: uppercase;
    font-weight: 700;
    color: var(--text-secondary);
  }

  .split-inputs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }

  .btn-row {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 4px;
  }

  .text-gold { color: var(--color-gold); }
  .text-green { color: var(--fel-green); }
  .text-cyan { color: var(--mana-cyan); }
  .text-muted { color: var(--text-muted); }
  .text-secondary { color: var(--text-secondary); }

  .panel-layout :global(.spin) {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
