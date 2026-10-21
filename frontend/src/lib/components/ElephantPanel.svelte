<script lang="ts">
  import { api } from '../api';
  import { onMount,onDestroy } from 'svelte';
  import {
    Sliders,
    Eye,
    EyeOff,
    Pause,
    Play,
    Shield,
    ShieldOff,
    RotateCcw,
    Ghost,
    Skull,
    Bomb,
    UserPlus,
    Plus,
    Trash2,
    Sparkles,
    BookOpen,
    Zap,
  } from 'lucide-svelte';

  let heroLevel = $state('1');
  let unitScale = $state('1.0');
  let unitRawcode = $state('');
  let itemRawcode = $state('ckng');
  let abilityRawcode = $state('AOsh');
  let abilityLevel = $state('1');
  let techRawcode = $state('');
  let techLevel = $state('1');
  let xpRate = $state('1.0');
  function receiveParams(p:Record<string,string>){
    if(p.hero_level!==undefined)heroLevel=p.hero_level;
    if(p.unit_scale!==undefined)unitScale=p.unit_scale;
    if(p.unit_rawcode!==undefined)unitRawcode=p.unit_rawcode;
    if(p.item_rawcode!==undefined)itemRawcode=p.item_rawcode;
    if(p.ability_rawcode!==undefined)abilityRawcode=p.ability_rawcode;
    if(p.ability_level!==undefined)abilityLevel=p.ability_level;
    if(p.tech_rawcode!==undefined)techRawcode=p.tech_rawcode;
    if(p.tech_level!==undefined)techLevel=p.tech_level;
    if(p.xp_rate!==undefined)xpRate=p.xp_rate;
  }
  function received(event:Event){receiveParams((event as CustomEvent).detail);}
  async function refreshParams(){receiveParams(await api.getElephantParameters());}
  onMount(()=>{refreshParams();window.addEventListener('war3-elephant-parameters',received);window.addEventListener('war3-elephant-parameters-changed',refreshParams);});
  onDestroy(()=>{window.removeEventListener('war3-elephant-parameters',received);window.removeEventListener('war3-elephant-parameters-changed',refreshParams);});

  let actionFeedback = $state('');
  let isError = $state(false);

  // Confirm dialog
  let confirmDialog = $state<{ title: string; desc: string; action: () => Promise<void> } | null>(null);

  async function callAction(actionName: string, params: Record<string, any> = {}) {
    actionFeedback = `正在执行 [${actionName}]...`;
    isError = false;
    try {
      const res = await api.executeElephantAction(actionName, params);
      if (res.success) {
        actionFeedback = `✓ 操作 [${actionName}] 已完成`;
      } else {
        actionFeedback = `✗ 失败: ${res.error}`;
        isError = true;
      }
      setTimeout(() => (actionFeedback = ''), 3000);
    } catch (err: any) {
      actionFeedback = `✗ 异常: ${err.message || err}`;
      isError = true;
    }
  }

  function promptConfirm(title: string, desc: string, action: () => Promise<void>) {
    confirmDialog = { title, desc, action };
  }
</script>

<div class="elephant-layout">
  <!-- Header -->
  <div class="panel-header">
    <div class="header-left">
      <Sliders size={18} class="text-gold" />
      <h2 class="panel-title">大象经典功能</h2>
    </div>
    <div class="header-actions">
      {#if actionFeedback}
        <span class="feedback-badge {isError ? 'err' : 'ok'}">{actionFeedback}</span>
      {/if}
      <button class="btn btn-primary btn-sm" onclick={() => callAction('prewarm_elephant')}>
        <Zap size={13} /> 初始化大象功能
      </button>
    </div>
  </div>

  <!-- Action Grid (3 columns) -->
  <div class="actions-grid">
    <!-- Box 1: Map & Game -->
    <div class="action-card">
      <div class="card-header">
        <Eye size={15} class="text-gold" />
        <span class="card-title">地图与战局全局控制</span>
      </div>
      <div class="card-content">
        <div class="btn-grid-2">
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('reveal_map')}>
            <Eye size={12} /> 全开视野
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('hide_map')}>
            <EyeOff size={12} /> 恢复迷雾
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('pause_game')}>
            <Pause size={12} /> 暂停游戏
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('resume_game')}>
            <Play size={12} /> 恢复游戏
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('peace_on')}>
            开启和平模式
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('peace_off')}>
            关闭和平模式
          </button>
        </div>
        <button
          class="btn btn-danger btn-sm"
          onclick={() => promptConfirm('强制结束对局', '确定要立刻强制结束当前游戏战局吗？', () => callAction('end_game'))}
        >
          结束当前游戏
        </button>
      </div>
    </div>

    <!-- Box 2: Hero & Unit Status -->
    <div class="action-card">
      <div class="card-header">
        <Shield size={15} class="text-gold" />
        <span class="card-title">英雄与单位状态修改</span>
      </div>
      <div class="card-content">
        <div class="inline-input-row">
          <span class="row-label">英雄等级:</span>
          <input type="text" class="mono input-sm" style="width: 50px;" bind:value={heroLevel} onchange={()=>api.setElephantParameter('hero_level',heroLevel)} />
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('hero_level_read')}>读取</button>
          <button class="btn btn-primary btn-sm" onclick={() => callAction('hero_level_set', { level: heroLevel })}>设置</button>
        </div>

        <div class="btn-grid-2">
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('invulnerable')}>
            <Shield size={12} /> 无敌 (Invulnerable)
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('vulnerable')}>
            <ShieldOff size={12} /> 取消无敌
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('collision_off')}>
            <Ghost size={12} /> 关闭碰撞体积
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('collision_on')}>
            开启碰撞体积
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('pause_unit')}>
            暂停单位
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('resume_unit')}>
            恢复单位
          </button>
        </div>

        <button class="btn btn-secondary btn-sm" onclick={() => callAction('reset_cooldown')}>
          <RotateCcw size={12} /> 重置技能冷却 (Reset CD)
        </button>

        <div class="inline-input-row">
          <span class="row-label">单位模型缩放:</span>
          <input type="text" class="mono input-sm" style="width: 60px;" bind:value={unitScale} onchange={()=>api.setElephantParameter('unit_scale',unitScale)} />
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('set_scale', { scale: unitScale })}>设置缩放</button>
        </div>
      </div>
    </div>

    <!-- Box 3: Target Unit & Owner -->
    <div class="action-card">
      <div class="card-header">
        <Skull size={15} class="text-gold" />
        <span class="card-title">目标单位与阵营控制</span>
      </div>
      <div class="card-content">
        <button class="btn btn-primary btn-sm" onclick={() => callAction('take_control')}>
          <UserPlus size={12} /> 强行获取目标单位控制权
        </button>
        <div class="btn-grid-2">
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('kill_unit')}>
            <Skull size={12} /> 秒杀目标
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('explode_unit')}>
            <Bomb size={12} /> 瞬间爆炸
          </button>
        </div>
        <button class="btn btn-secondary btn-sm" onclick={() => callAction('remove_unit')}>
          完全删除单位对象
        </button>

        <button
          class="btn btn-danger btn-sm"
          onclick={() =>
            promptConfirm(
              '秒杀所属阵营全部单位',
              '警告：此操作将秒杀当前选中单位所属玩家的所有部队与建筑，确定继续？',
              () => callAction('kill_owner_units')
            )}
        >
          秒杀该玩家全部阵营单位
        </button>
      </div>
    </div>

    <!-- Box 4: Unit Creation & Items -->
    <div class="action-card">
      <div class="card-header">
        <Plus size={15} class="text-gold" />
        <span class="card-title">单位召唤与物品注入</span>
      </div>
      <div class="card-content">
        <div class="inline-input-row">
          <span class="row-label">单位ID:</span>
          <input type="text" class="mono input-sm" placeholder="如 hfoo" bind:value={unitRawcode} onchange={()=>api.setElephantParameter('unit_rawcode',unitRawcode)} />
          <button class="btn btn-primary btn-sm" onclick={() => callAction('create_unit', { rawcode: unitRawcode, to_self: false })}>
            生成单位
          </button>
        </div>

        <button class="btn btn-secondary btn-sm" onclick={() => callAction('create_unit', { rawcode: unitRawcode, to_self: true })}>
          复制选中单位归属给自己
        </button>

        <div class="inline-input-row">
          <span class="row-label">物品ID:</span>
          <input type="text" class="mono input-sm" placeholder="如 ckng" bind:value={itemRawcode} onchange={()=>api.setElephantParameter('item_rawcode',itemRawcode)} />
          <button class="btn btn-primary btn-sm" onclick={() => callAction('add_item', { rawcode: itemRawcode })}>
            添加物品
          </button>
        </div>

        <button
          class="btn btn-danger btn-sm"
          onclick={() =>
            promptConfirm('清空背包', '确定要删除当前选中单位背包中的全部 6 格物品吗？', () => callAction('clear_inventory'))}
        >
          <Trash2 size={12} /> 清空单位背包
        </button>
      </div>
    </div>

    <!-- Box 5: Abilities -->
    <div class="action-card">
      <div class="card-header">
        <Sparkles size={15} class="text-gold" />
        <span class="card-title">技能赋予与等级操控</span>
      </div>
      <div class="card-content">
        <div class="inline-input-row">
          <span class="row-label">技能ID:</span>
          <input type="text" class="mono input-sm" style="width: 70px;" bind:value={abilityRawcode} onchange={()=>api.setElephantParameter('ability_rawcode',abilityRawcode)} />
          <span class="row-label">等级:</span>
          <input type="text" class="mono input-sm" style="width: 40px;" bind:value={abilityLevel} onchange={()=>api.setElephantParameter('ability_level',abilityLevel)} />
        </div>

        <div class="btn-grid-2">
          <button class="btn btn-primary btn-sm" onclick={() => callAction('add_ability', { rawcode: abilityRawcode, level: abilityLevel })}>
            添加技能
          </button>
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('remove_ability', { rawcode: abilityRawcode })}>
            删除技能
          </button>
        </div>

        <button class="btn btn-secondary btn-sm" onclick={() => callAction('set_ability_level', { rawcode: abilityRawcode, level: abilityLevel })}>
          设定指定技能等级
        </button>
      </div>
    </div>

    <!-- Box 6: Tech & XP -->
    <div class="action-card">
      <div class="card-header">
        <BookOpen size={15} class="text-gold" />
        <span class="card-title">玩家科技等级与经验倍率</span>
      </div>
      <div class="card-content">
        <div class="inline-input-row">
          <span class="row-label">科技ID:</span>
          <input type="text" class="mono input-sm" style="width: 70px;" bind:value={techRawcode} onchange={()=>api.setElephantParameter('tech_rawcode',techRawcode)} />
          <span class="row-label">等级:</span>
          <input type="text" class="mono input-sm" style="width: 40px;" bind:value={techLevel} onchange={()=>api.setElephantParameter('tech_level',techLevel)} />
        </div>

        <button class="btn btn-primary btn-sm" onclick={() => callAction('set_tech', { rawcode: techRawcode, level: techLevel })}>
          设定玩家科技等级
        </button>

        <div class="inline-input-row">
          <span class="row-label">经验获取倍率:</span>
          <input type="text" class="mono input-sm" style="width: 70px;" bind:value={xpRate} onchange={()=>api.setElephantParameter('xp_rate',xpRate)} />
          <button class="btn btn-secondary btn-sm" onclick={() => callAction('set_xp_rate', { rate: xpRate })}>
            设定经验倍率
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Confirm Dialog Modal -->
  {#if confirmDialog}
    <div class="modal-overlay">
      <div class="confirm-modal">
        <div class="modal-title">{confirmDialog.title}</div>
        <div class="modal-desc">{confirmDialog.desc}</div>
        <div class="modal-btns">
          <button class="btn btn-secondary btn-sm" onclick={() => (confirmDialog = null)}>取消</button>
          <button
            class="btn btn-danger btn-sm"
            onclick={async () => {
              const act = confirmDialog?.action;
              confirmDialog = null;
              if (act) await act();
            }}
          >
            确认执行
          </button>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .elephant-layout {
    display: flex;
    flex-direction: column;
    gap: 14px;
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
    gap: 8px;
  }

  .feedback-badge {
    padding: 3px 8px;
    border-radius: var(--radius-sm);
    font-size: 11px;
    font-weight: 600;
  }
  .feedback-badge.ok {
    background-color: var(--status-success-bg);
    border: 1px solid var(--fel-green);
    color: var(--status-success-text);
  }
  .feedback-badge.err {
    background-color: var(--status-danger-bg);
    border: 1px solid var(--health-crimson);
    color: var(--status-danger-text);
  }

  .actions-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 12px;
  }

  .action-card {
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
    color: var(--text-bright);
  }

  .card-content {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .btn-grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
  }

  .inline-input-row {
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .row-label {
    font-size: 12px;
    color: var(--text-normal);
    font-weight: 600;
  }

  .input-sm {
    height: 28px;
    padding: 3px 8px;
    font-size: 12px;
  }

  /* Modal */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background-color: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .confirm-modal {
    width: 380px;
    background-color: var(--bg-surface);
    border: 1px solid var(--health-crimson);
    border-radius: var(--radius-md);
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.8);
  }

  .modal-title {
    font-size: 14px;
    font-weight: 700;
    color: var(--text-primary);
  }

  .modal-desc {
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.5;
  }

  .modal-btns {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
  }

  .elephant-layout :global(.text-gold) { color: var(--color-gold); }
</style>
