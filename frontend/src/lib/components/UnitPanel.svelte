<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { api } from '../api';
  import type { SelectedUnitData, CandidateUnit, UnitFieldRow } from '../types';
  import { UserCheck, RefreshCw, Crosshair, Edit3, Lock, Search, Heart, Zap, Compass } from 'lucide-svelte';

  let unitData = $state<SelectedUnitData>({
    hasSelection: false,
    unitTypeId: '',
    identity: null,
    hp: { current: '', max: '', regen: '', target: '', regenTarget: '' },
    mp: { current: '', max: '', regen: '', target: '', regenTarget: '' },
    position: { xCurrent: '', yCurrent: '', xTarget: '', yTarget: '' },
    fields: [],
  });

  let candidates = $state<CandidateUnit[]>([]);
  let selectedCandidateIid = $state('');

  let fieldFilter = $state('');
  let selectedCategory = $state('全部');
  let selectedFieldRow = $state<UnitFieldRow | null>(null);
  let fieldTargetValue = $state('');
  let loading = $state(false);

  const categories = $derived(['全部', ...new Set(unitData.fields.map(f => f.category))]);

  let filteredFields = $derived.by(() => {
    let list = unitData.fields;
    if (selectedCategory !== '全部') {
      list = list.filter((f) => f.category === selectedCategory);
    }
    if (fieldFilter.trim()) {
      const q = fieldFilter.trim().toLowerCase();
      list = list.filter(
        (f) =>
          f.label.toLowerCase().includes(q) ||
          f.value.toLowerCase().includes(q) ||
          f.address.toLowerCase().includes(q) ||
          f.note.toLowerCase().includes(q)
      );
    }
    return list;
  });

  async function loadUnit() {
    loading = true;
    try {
      const res = await api.readSelectedUnit();
      unitData = res;
    } catch (err) {
      console.error(err);
    } finally {
      loading = false;
    }
  }

  function receivedUnit(event: Event) { unitData = (event as CustomEvent<SelectedUnitData>).detail; }
  function receivedCandidates(event: Event) {candidates=(event as CustomEvent<CandidateUnit[]>).detail;}
  onMount(() => {
    api.getSelectedUnitSnapshot().then(x=>unitData=x);
    api.getUnitCandidatesSnapshot().then(x=>candidates=x);
    window.addEventListener('war3-unit-read', receivedUnit);
    window.addEventListener('war3-candidates-read',receivedCandidates);
  });
  onDestroy(() => {window.removeEventListener('war3-unit-read', receivedUnit);window.removeEventListener('war3-candidates-read',receivedCandidates);});

  async function handleWriteUnit() {
    try {
      const res = await api.writeSelectedUnit({
        hpTarget: unitData.hp.target,
        mpTarget: unitData.mp.target,
        hpRegenTarget: unitData.hp.regenTarget,
        mpRegenTarget: unitData.mp.regenTarget,
        xTarget: unitData.position.xTarget,
        yTarget: unitData.position.yTarget,
      });
      if (res.success && res.data) {
        unitData = res.data;
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function handleRefreshCandidates() {
    try {
      candidates = await api.refreshUnitCandidates();
    } catch (err) {
      console.error(err);
    }
  }

  async function handleReadCandidate(candidateIid: string) {
    selectedCandidateIid = candidateIid;
    try {
      const res = await api.readSelectionCandidate(candidateIid);
      if (res.success && res.unit) {
        unitData = res.unit;
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function handleNativeLocator() {
    try {
      const res = await api.readNativeSelection();
      if (res.success && res.unit) {
        unitData = res.unit;
      }
    } catch (err) {
      console.error(err);
    }
  }

  function handleSelectField(field: UnitFieldRow) {
    selectedFieldRow = field;
    fieldTargetValue = field.value;
  }

  async function handleWriteField() {
    if (!selectedFieldRow) {window.dispatchEvent(new CustomEvent('war3-error',{detail:'请先选择需要操作的单位字段。'}));return;}
    try {
      const res = await api.writeUnitField(selectedFieldRow._iid, fieldTargetValue);
      if (res.success && res.data) {
        unitData = res.data;
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function handleLockField() {
    if (!selectedFieldRow) {window.dispatchEvent(new CustomEvent('war3-error',{detail:'请先选择需要操作的单位字段。'}));return;}
    try {
      await api.addUnitFieldLock(selectedFieldRow._iid, fieldTargetValue);
      await loadUnit();
    } catch (err) {
      console.error(err);
    }
  }
</script>

<div class="unit-layout">
  <!-- Left Column: Core Attributes, Actions, and Candidate Tree -->
  <div class="left-col">
    <div class="section-card">
      <div class="card-header">
        <UserCheck size={16} class="text-gold" />
        <span class="card-title">选中单位核心状态</span>
        <span class="unit-type font-mono">
          {#if unitData.unitTypeId}
            ID: <span class="rawcode-chip">{unitData.unitTypeId}</span>
          {:else}
            未选定
          {/if}
        </span>
      </div>

      <!-- HP/MP Stats Grid -->
      <div class="stats-grid">
        <div class="stat-box hp-box">
          <div class="stat-title"><Heart size={12} /> 生命值 (HP)</div>
          <div class="stat-current font-mono">
            {unitData.hp.current || '---'} / {unitData.hp.max || '---'}
          </div>
          <div class="stat-sub font-mono">回复: {unitData.hp.regen || '0.0'}/s</div>
          <div class="input-pair">
            <input type="text" placeholder="目标HP" class="mono input-sm" bind:value={unitData.hp.target} />
            <input type="text" placeholder="目标回复" class="mono input-sm" bind:value={unitData.hp.regenTarget} />
          </div>
        </div>

        <div class="stat-box mp-box">
          <div class="stat-title"><Zap size={12} /> 魔法值 (MP)</div>
          <div class="stat-current font-mono">
            {unitData.mp.current || '---'} / {unitData.mp.max || '---'}
          </div>
          <div class="stat-sub font-mono">回复: {unitData.mp.regen || '0.0'}/s</div>
          <div class="input-pair">
            <input type="text" placeholder="目标MP" class="mono input-sm" bind:value={unitData.mp.target} />
            <input type="text" placeholder="目标回复" class="mono input-sm" bind:value={unitData.mp.regenTarget} />
          </div>
        </div>
      </div>

      <!-- Coordinates -->
      <div class="coords-box">
        <div class="stat-title"><Compass size={12} /> 世界坐标 (X / Y)</div>
        <div class="coords-row">
          <span class="coord-tag font-mono">当前: ({unitData.position.xCurrent || '0.0'}, {unitData.position.yCurrent || '0.0'})</span>
          <div class="coord-inputs">
            <input type="text" placeholder="目标X" class="mono input-sm" bind:value={unitData.position.xTarget} />
            <input type="text" placeholder="目标Y" class="mono input-sm" bind:value={unitData.position.yTarget} />
          </div>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="action-buttons">
        <button class="btn btn-primary btn-sm" onclick={handleWriteUnit}>
          写入选中单位
        </button>
        <button class="btn btn-secondary btn-sm" onclick={loadUnit} disabled={loading}>
          <RefreshCw size={12} class={loading ? 'spin' : ''} /> 刷新字段表
        </button>
        <button class="btn btn-secondary btn-sm" onclick={handleRefreshCandidates}>
          列出候选单位
        </button>
        <button class="btn btn-secondary btn-sm" onclick={handleNativeLocator}>
          <Crosshair size={12} /> Native定位
        </button>
      </div>
    </div>

    <!-- Candidate Units Table -->
    <div class="section-card candidate-card">
      <div class="card-header">
        <span class="card-title">候选单位列表 ({candidates.length})</span>
        <button class="btn btn-secondary btn-sm" onclick={()=>handleReadCandidate(selectedCandidateIid)} disabled={!selectedCandidateIid}>读取所选候选</button>
        <span class="hint">双击行可直接切换到对应单位</span>
      </div>
      <div class="game-table-container table-scroll">
        <table class="game-table">
          <thead>
            <tr>
              <th>#</th>
              <th>可信度</th>
              <th>生命</th>
              <th>魔法</th>
              <th>坐标</th>
              <th>refs/known</th><th>组件</th><th>物品槽</th>
              <th>handle</th>
              <th>owner</th><th>unit</th>
            </tr>
          </thead>
          <tbody>
            {#if candidates.length === 0}
              <tr>
                <td colspan="11" class="empty-cell">暂无候选单位，点“列出候选单位”检索</td>
              </tr>
            {:else}
              {#each candidates as c}
                <tr
                  class={selectedCandidateIid === c._iid ? 'selected' : ''}
                  onclick={()=>selectedCandidateIid=c._iid}
                  ondblclick={() => handleReadCandidate(c._iid)}
                >
                  <td class="font-mono">{c.index}</td>
                  <td class="font-mono text-cyan">{c.confidence}</td>
                  <td class="font-mono text-crimson">{c.hp}</td>
                  <td class="font-mono text-cyan">{c.mp}</td>
                  <td class="font-mono">{c.position}</td>
                  <td class="font-mono">{c.evidence}</td><td>{c.components}</td><td>{c.inventory}</td>
                  <td class="font-mono text-muted">{c.handle}</td>
                  <td class="font-mono text-muted">{c.owner}</td><td class="font-mono text-muted">{c.unit}</td>
                </tr>
              {/each}
            {/if}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Right Column: Full Dynamic Synthetic Fields Workstation -->
  <div class="right-col">
    <div class="section-card full-fields-card">
      <div class="card-header">
        <div class="fields-header-left">
          <Edit3 size={16} class="text-gold" />
          <span class="card-title">单位动态字段表 (共 {unitData.fields.length} 项)</span>
        </div>
        <div class="fields-search-box">
          <Search size={13} class="text-muted" />
          <input
            type="text"
            placeholder="搜索字段名、地址、备注或数值..."
            class="filter-input"
            bind:value={fieldFilter}
          />
        </div>
      </div>

      <!-- Categories Pills -->
      <div class="category-pills">
        {#each categories as cat}
          <button
            class="pill-btn {selectedCategory === cat ? 'active' : ''}"
            onclick={() => (selectedCategory = cat)}
          >
            {cat}
          </button>
        {/each}
      </div>

      <!-- Fields Table -->
      <div class="game-table-container fields-table-scroll">
        <table class="game-table">
          <thead>
            <tr>
              <th style="width: 70px;">分类</th>
              <th style="width: 170px;">字段名称</th>
              <th style="width: 120px;">当前值</th>
              <th style="width: 60px;">类型</th>
              <th style="width: 130px;">内存地址</th>
              <th>说明与语义</th>
            </tr>
          </thead>
          <tbody>
            {#if filteredFields.length === 0}
              <tr>
                <td colspan="6" class="empty-cell">未匹配到字段记录</td>
              </tr>
            {:else}
              {#each filteredFields as f}
                <tr
                  class={selectedFieldRow?._iid === f._iid ? 'selected' : ''}
                  onclick={() => handleSelectField(f)}
                >
                  <td><span class="cat-badge">{f.category}</span></td>
                  <td><strong>{f.label}</strong></td>
                  <td class="font-mono text-gold">{f.value}</td>
                  <td class="font-mono text-muted">{f.type}</td>
                  <td class="font-mono text-muted">{f.address}</td>
                  <td class="text-secondary">{f.note}</td>
                </tr>
              {/each}
            {/if}
          </tbody>
        </table>
      </div>

      <!-- Single Field Target Modifier Bar -->
      <div class="field-modifier-bar">
        <div class="mod-info">
          <span class="label">选中字段:</span>
          <span class="mod-name">{selectedFieldRow?.label || '(未选择)'}</span>
          <span class="mod-addr font-mono">{selectedFieldRow?.address || ''}</span>
        </div>
        <div class="mod-actions">
          <input
            type="text"
            class="mono target-val-input"
            placeholder="填写新目标值"
            bind:value={fieldTargetValue}
            disabled={!selectedFieldRow}
          />
          <button
            class="btn btn-primary btn-sm"
            onclick={handleWriteField}
            disabled={!selectedFieldRow}
          >
            写入字段
          </button>
          <button
            class="btn btn-secondary btn-sm"
            onclick={handleLockField}
            disabled={!selectedFieldRow}
          >
            <Lock size={12} /> 锁定字段
          </button>
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .unit-layout {
    display: grid;
    grid-template-columns: 360px 1fr;
    gap: 12px;
    height: 100%;
    padding: 16px;
    overflow: hidden;
  }

  .left-col,
  .right-col {
    display: flex;
    flex-direction: column;
    gap: 12px;
    height: 100%;
    overflow: hidden;
  }

  .section-card {
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
    gap: 8px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-subtle);
  }

  .card-title {
    font-size: 13px;
    font-weight: 700;
    color: var(--text-primary);
  }

  .unit-type {
    margin-left: auto;
    font-size: 11px;
    color: var(--text-muted);
  }

  .hint {
    margin-left: auto;
    font-size: 10px;
    color: var(--text-muted);
  }

  .stats-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }

  .stat-box {
    background-color: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .hp-box { border-left: 3px solid var(--health-crimson); }
  .mp-box { border-left: 3px solid var(--mana-cyan); }

  .stat-title {
    font-size: 12px;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 5px;
    color: var(--text-primary);
  }

  .stat-current {
    font-size: 15px;
    font-weight: 800;
    color: var(--text-gold);
    letter-spacing: 0.5px;
  }

  .hp-box .stat-current {
    color: var(--status-danger-text);
  }

  .mp-box .stat-current {
    color: var(--mana-cyan);
  }

  .stat-sub {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-secondary);
  }

  .input-pair {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px;
    margin-top: 4px;
  }

  .input-sm {
    padding: 3px 6px;
    font-size: 11px;
    width: 100%;
  }

  .coords-box {
    background-color: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 8px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .coords-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
  }

  .coord-tag {
    font-size: 11px;
    color: var(--text-secondary);
  }

  .coord-inputs {
    display: flex;
    gap: 4px;
  }

  .coord-inputs input {
    width: 60px;
  }

  .action-buttons {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
  }

  .candidate-card {
    flex: 1;
    min-height: 180px;
    overflow: hidden;
  }

  .table-scroll {
    flex: 1;
  }

  .full-fields-card {
    height: 100%;
    overflow: hidden;
  }

  .fields-header-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .fields-search-box {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 6px;
    background-color: var(--bg-input);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 2px 8px;
  }

  .filter-input {
    border: none !important;
    background: transparent !important;
    padding: 2px 0 !important;
    font-size: 11px !important;
    width: 200px;
  }

  .category-pills {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-wrap: wrap;
    padding: 2px 0;
  }

  .pill-btn {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    color: var(--text-muted);
    font-size: 11px;
    padding: 2px 9px;
    cursor: pointer;
    transition: all 0.12s ease;
  }

  .pill-btn:hover {
    color: var(--text-primary);
    border-color: var(--border-normal);
  }

  .pill-btn.active {
    background-color: rgba(229, 193, 88, 0.15);
    border-color: var(--color-gold);
    color: var(--text-gold);
    font-weight: 600;
  }

  .fields-table-scroll {
    flex: 1;
    overflow-y: auto;
  }

  .cat-badge {
    background-color: var(--bg-card);
    border: 1px solid var(--border-subtle);
    color: var(--text-secondary);
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 10px;
  }

  .field-modifier-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background-color: var(--bg-surface);
    border: 1px solid var(--border-normal);
    border-radius: var(--radius-sm);
    padding: 8px 12px;
    gap: 12px;
  }

  .mod-info {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
  }

  .mod-name {
    font-weight: 700;
    color: var(--text-gold);
  }

  .mod-addr {
    font-size: 11px;
    color: var(--text-muted);
  }

  .mod-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .target-val-input {
    width: 140px;
    height: 28px;
  }

  .empty-cell {
    text-align: center;
    padding: 24px;
    color: var(--text-muted);
    font-style: italic;
  }

  .text-gold { color: var(--color-gold); }
  .text-crimson { color: var(--health-crimson); }
  .text-cyan { color: var(--mana-cyan); }
  .text-muted { color: var(--text-muted); }
  .text-secondary { color: var(--text-secondary); }

  .unit-layout :global(.spin) {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
