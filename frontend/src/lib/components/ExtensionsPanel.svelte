<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../api';
  import DefinitionDialog from './DefinitionDialog.svelte';
  import type { ExtensionsSnapshot, BagItemRow, EquipmentItemRow, TalentRow } from '../types';
  import { ShieldAlert, RefreshCw, Plus, Trash2, Copy, FileText, Wrench, Download, Upload, Check, AlertTriangle } from 'lucide-svelte';

  let snapshot = $state<ExtensionsSnapshot>({
    status: '尚未读取 3.0 扩展状态',
    bag: [],
    equipment: [],
    talents: [],
    officialBackpacks: [],
    currentBackpackChoice: '',
    loadoutName: '套装1',
  });

  let selectedBagIid = $state('');
  let selectedEquipIid = $state('');
  let selectedTalentIid = $state('');

  let bagRawcodeInput = $state('');
  let bagChargesInput = $state('1');
  let backpackChoice = $state('');

  let loadoutNameInput = $state('套装1');
  let selectedLoadoutName = $state('');
  function restorePlanName() {
    return selectedLoadoutName || ((snapshot.loadoutNames || []).includes(loadoutNameInput) ? loadoutNameInput : '');
  }
  let talentChoiceInput = $state('');

  let loading = $state(false);
  let equipmentBusy = $state(false);
  let equipmentElapsed = $state(0);
  let actionMessage = $state('');

  // Definition Repair Dialog state
  let showDefModal = $state(false);
  let defMapPath = $state('');
  let defOutputFolder = $state('');
  async function loadData() {
    loading = true;
    try {
      snapshot = await api.refreshExtensionStatus();
      if (!backpackChoice && snapshot.officialBackpacks.length > 0) {
        backpackChoice = snapshot.currentBackpackChoice || snapshot.officialBackpacks[0];
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

  async function handleBagAction(action: string, params: Record<string, any> = {}) {
    try {
      const res = await api.extensionBagAction(action, { row_iid: selectedBagIid, ...params });
      if (res.success && res.data) {
        snapshot = res.data;
        actionMessage = `背包操作 [${action}] 执行完成`;
        setTimeout(() => (actionMessage = ''), 5000);
      } else {
        actionMessage = res.error || '操作未完成';
      }
    } catch (err: any) {
      actionMessage = `错误: ${err.message || err}`;
    }
  }

  async function handleEquipmentAction(action: string, params: Record<string, any> = {}) {
    if (equipmentBusy) return;
    equipmentBusy = true;
    equipmentElapsed = 0;
    const started = Date.now();
    const timer = setInterval(() => equipmentElapsed = Math.floor((Date.now() - started) / 1000), 1000);
    actionMessage = action.includes('restore') ? '正在恢复套装并按部位装备，请稍候…' : '正在处理装备，请稍候…';
    try {
      const res = await api.extensionEquipmentAction(action, { row_iid: selectedEquipIid, bag_row_iid: selectedBagIid, ...params });
      if (res.success && res.data) {
        snapshot = res.data;
        actionMessage = res.message || `装备操作 [${action}] 执行完成`;
        setTimeout(() => (actionMessage = ''), 5000);
      } else {
        actionMessage = res.error || '操作未完成';
      }
    } catch (err: any) {
      actionMessage = `错误: ${err.message || err}`;
    } finally {
      clearInterval(timer);
      equipmentBusy = false;
    }
  }

  async function handleTalentAction(action: string, params: Record<string, any> = {}) {
    try {
      const res = await api.extensionTalentAction(action, { row_iid: selectedTalentIid, ...params });
      if (res.success && res.data) {
        snapshot = res.data;
        actionMessage = `天赋操作 [${action}] 执行完成`;
        setTimeout(() => (actionMessage = ''), 5000);
      } else {
        actionMessage = res.error || '操作未完成';
      }
    } catch (err: any) {
      actionMessage = `错误: ${err.message || err}`;
    }
  }

</script>

<div class="ext-layout">
  <!-- Header Bar -->
  <div class="panel-header">
    <div class="header-left">
      <ShieldAlert size={18} class="text-gold" />
      <h2 class="panel-title">3.0 扩展功能 (30格背包 / 9槽装备 / 天赋树)</h2>
      {#if snapshot.status}
        <span class="status-chip mono">{snapshot.status}</span>
      {/if}
    </div>
    <div class="header-actions">
      {#if actionMessage}
        <span class="action-badge">{actionMessage}</span>
      {/if}
      <button class="btn btn-primary btn-sm" onclick={loadData} disabled={loading}>
        <RefreshCw size={13} class={loading ? 'spin' : ''} /> 读取扩展状态
      </button>
    </div>
  </div>

  <div class="definition-tools">
    <button class="btn btn-secondary btn-sm" onclick={() => (showDefModal = true)}>
      <Wrench size={13} /> 补齐战役/地图背包定义
    </button>
    <span>如果添加背包时提示“背包装备未定义”，使用此键为战役或地图添加定义。</span>
  </div>

  <!-- Upper Grid: 30-Slot Bag & 9-Slot Equipment -->
  <div class="upper-grid">
    <!-- 30-Slot Bag -->
    <div class="ext-card">
      <div class="card-header">
        <span class="card-title">30 格扩展背包 ({snapshot.bag.length} 件)</span>
        <span class="hint">单选项目可操作</span>
      </div>
      <div class="game-table-container table-wrap">
        <table class="game-table">
          <thead>
            <tr>
              <th style="width: 50px;">槽位</th>
              <th style="width: 80px;">物品 ID</th>
              <th style="width: 60px;">数量</th>
              <th>内存句柄 (Handle)</th>
            </tr>
          </thead>
          <tbody>
            {#if snapshot.bag.length === 0}
              <tr>
                <td colspan="4" class="empty-cell">背包为空或尚未连接 3.0 扩展支持</td>
              </tr>
            {:else}
              {#each snapshot.bag as b}
                <tr
                  class={selectedBagIid === b._iid ? 'selected' : ''}
                  onclick={() => (selectedBagIid = b._iid)}
                >
                  <td class="font-mono">#{b.slot}</td>
                  <td><span class="rawcode-chip">{b.rawcode}</span></td>
                  <td class="font-mono text-gold">{b.charges}</td>
                  <td class="font-mono text-muted">{b.handle}</td>
                </tr>
              {/each}
            {/if}
          </tbody>
        </table>
      </div>

      <!-- Bag Controls -->
      <div class="card-controls">
        <div class="control-row">
          <input type="text" placeholder="物品ID" class="mono input-sm" style="width: 80px;" bind:value={bagRawcodeInput} />
          <input type="text" placeholder="数量" class="mono input-sm" style="width: 50px;" bind:value={bagChargesInput} />
          <button class="btn btn-primary btn-sm" onclick={() => handleBagAction('add_item', { rawcode: bagRawcodeInput, charges: bagChargesInput })}>
            <Plus size={12} /> 添加物品
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => handleBagAction('set_charges', { charges: bagChargesInput })}>
            改数量
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => handleBagAction('duplicate')}>
            <Copy size={12} /> 复制
          </button>
          <button class="btn btn-danger btn-sm" onclick={() => handleBagAction('destroy')}>
            <Trash2 size={12} /> 销毁
          </button>
        </div>

        <div class="control-row">
          <select class="select-sm" bind:value={backpackChoice}>
            {#each snapshot.officialBackpacks as bp}
              <option value={bp}>{bp}</option>
            {/each}
          </select>
          <button class="btn btn-secondary btn-sm" onclick={() => handleBagAction('add_official_backpack', { choice: backpackChoice })}>
            添加官方背包装备
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => handleBagAction('repair_item')}>
            修复状态
          </button>
        </div>
      </div>
    </div>

    <!-- 9-Slot Equipment -->
    <div class="ext-card">
      <fieldset disabled={equipmentBusy} style="display: contents;">
      <div class="card-header">
        <span class="card-title">9 槽装备 ({snapshot.equipment.length} 件)</span>
        <span class="hint">按装备部位装配</span>
      </div>
      <div class="game-table-container table-wrap">
        <table class="game-table">
          <thead>
            <tr>
              <th style="width: 70px;">装备槽</th>
              <th style="width: 80px;">物品 ID</th>
              <th style="width: 60px;">类型</th>
              <th style="width: 50px;">数量</th>
              <th>内存句柄 (Handle)</th>
            </tr>
          </thead>
          <tbody>
            {#if snapshot.equipment.length === 0}
              <tr>
                <td colspan="5" class="empty-cell">当前单位未穿戴装备</td>
              </tr>
            {:else}
              {#each snapshot.equipment as eq}
                <tr
                  class={selectedEquipIid === eq._iid ? 'selected' : ''}
                  onclick={() => (selectedEquipIid = eq._iid)}
                >
                  <td class="font-mono text-gold">{eq.slot}</td>
                  <td><span class="rawcode-chip">{eq.rawcode}</span></td>
                  <td>{eq.type}</td>
                  <td class="font-mono">{eq.charges}</td>
                  <td class="font-mono text-muted">{eq.handle}</td>
                </tr>
              {/each}
            {/if}
          </tbody>
        </table>
      </div>

      <!-- Equipment Controls -->
      <div class="card-controls">
        <div class="control-row">
          <button class="btn btn-primary btn-sm" onclick={() => handleEquipmentAction('equip_bag_to_slot')}>放入所选装备槽</button>
          <button class="btn btn-secondary btn-sm" onclick={() => handleEquipmentAction('unequip')}>
            卸下所选
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => handleEquipmentAction('audit')}>
            审计装备
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => handleEquipmentAction('repair_misplaced')}>
            修复错槽
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => handleEquipmentAction('enable_any_slot')}>
            开启任意槽
          </button>
          <button class="btn btn-danger btn-sm" onclick={() => handleEquipmentAction('destroy')}>
            <Trash2 size={12} /> 销毁
          </button>
        </div>

        <div class="control-row">
          <select class="input-sm" bind:value={selectedLoadoutName} onchange={(e) => { if (e.currentTarget.value) loadoutNameInput = e.currentTarget.value; }}><option value="">自动匹配已保存方案</option>{#each snapshot.loadoutNames || [] as name}<option value={name}>{name}</option>{/each}</select>
          <button class="btn btn-secondary btn-sm" onclick={() => handleEquipmentAction('export_loadouts')}>导出方案</button>
          <button class="btn btn-secondary btn-sm" onclick={() => handleEquipmentAction('import_loadouts')}>导入方案</button>
          <input type="text" placeholder="套装名称" class="input-sm" style="width: 90px;" bind:value={loadoutNameInput} />
          <button class="btn btn-primary btn-sm" onclick={() => handleEquipmentAction('save_loadout', { name: loadoutNameInput })}>
            保存套装
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => handleEquipmentAction('restore_loadout', { name: restorePlanName() })}>
            恢复套装
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => handleEquipmentAction('save_all_loadouts', { name: loadoutNameInput })}>
            一键保存全英雄
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => handleEquipmentAction('restore_all_loadouts', { name: restorePlanName() })}>
            一键恢复全英雄
          </button>
        </div>
        {#if equipmentBusy}<p role="status" class="hint">正在处理装备，已用时 {equipmentElapsed} 秒；完成后会核对九个部位。</p>{/if}
      </div>
      </fieldset>
    </div>
  </div>

  <div class="control-row"><select class="input-sm" bind:value={talentChoiceInput}><option value="">选择天赋</option>{#each snapshot.talentChoices || [] as choice}<option value={choice}>{choice}</option>{/each}</select><button class="btn btn-primary btn-sm" onclick={() => handleTalentAction('add_choice', {choice: talentChoiceInput})}>添加所选天赋</button></div>
  <!-- Lower Section: Talents Tree -->
  <div class="ext-card talents-card">
    <div class="card-header">
      <span class="card-title">3.0 官方战役天赋树 ({snapshot.talents.length} 层记录)</span>
      <div class="header-actions">
        <button class="btn btn-secondary btn-sm" onclick={() => handleTalentAction('grant_point')}>
          +1 天赋点
        </button>
        <button class="btn btn-danger btn-sm" onclick={() => handleTalentAction('reset_talents')}>
          重置天赋 (洗点)
        </button>
        <button class="btn btn-secondary btn-sm" onclick={() => handleTalentAction('refresh_icons')}>
          刷新天赋图标
        </button>
      </div>
    </div>
    <div class="game-table-container talents-table-wrap">
      <table class="game-table">
        <thead>
          <tr>
            <th style="width: 130px;">天赋树归属</th>
            <th style="width: 50px;">层级</th>
            <th style="width: 320px;">候选天赋池</th>
            <th>已激活选择</th>
          </tr>
        </thead>
        <tbody>
          {#if snapshot.talents.length === 0}
            <tr>
              <td colspan="4" class="empty-cell">未检测到英雄天赋树结构</td>
            </tr>
          {:else}
            {#each snapshot.talents as t}
              <tr
                class={selectedTalentIid === t._iid ? 'selected' : ''}
                onclick={() => (selectedTalentIid = t._iid)}
              >
                <td><strong>{t.hero}</strong></td>
                <td class="font-mono text-cyan">T{t.tier}</td>
                <td class="font-mono text-secondary">{t.choices}</td>
                <td class="font-mono text-gold font-bold">{t.selected || '(未点)'}</td>
              </tr>
            {/each}
          {/if}
        </tbody>
      </table>
    </div>
  </div>

  {#if showDefModal}<DefinitionDialog bind:mapPath={defMapPath} bind:outputFolder={defOutputFolder} onClose={()=>showDefModal=false} />{/if}
</div>

<style>
  .definition-tools { display:flex; flex-wrap:wrap; align-items:center; gap:8px; line-height:1.6; overflow-wrap:anywhere; }
  .ext-layout {
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

  .status-chip {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-gold);
    background: rgba(245, 158, 11, 0.12);
    border: 1px solid rgba(245, 158, 11, 0.3);
    padding: 2px 8px;
    border-radius: var(--radius-sm);
  }

  .header-actions {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .action-badge {
    background-color: rgba(229, 193, 88, 0.15);
    border: 1px solid var(--border-gold);
    color: var(--text-gold);
    font-size: 11px;
    padding: 3px 8px;
    border-radius: var(--radius-sm);
  }

  .upper-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }

  .ext-card {
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
    color: var(--text-primary);
  }

  .hint {
    font-size: 10px;
    color: var(--text-muted);
  }

  .table-wrap {
    height: 160px;
  }

  .talents-card {
    flex: 1;
  }

  .talents-table-wrap {
    height: 140px;
  }

  .card-controls {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .control-row {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .input-sm {
    height: 26px;
    padding: 2px 6px;
    font-size: 11px;
  }

  .select-sm {
    height: 26px;
    padding: 2px 6px;
    font-size: 11px;
    background-color: var(--bg-input);
    color: var(--text-primary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    max-width: 170px;
  }

  .empty-cell {
    text-align: center;
    padding: 24px;
    color: var(--text-muted);
    font-style: italic;
  }

  .text-gold { color: var(--color-gold); }
  .text-cyan { color: var(--mana-cyan); }
  .text-muted { color: var(--text-muted); }
  .text-secondary { color: var(--text-secondary); }

  .ext-layout :global(.spin) {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
