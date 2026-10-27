<script lang="ts">
  import {
    Coins,
    UserCheck,
    Layers,
    Lock,
    Sparkles,
    Package,
    ShieldAlert,
    Sliders,
    Keyboard,
    Search,
    BookOpen,
    Archive,
    Swords,
  } from 'lucide-svelte';

  let { currentTab, onSelectTab }: {
    currentTab: string;
    onSelectTab: (tabId: string) => void;
  } = $props();

  const menuSections = [
    {
      group: '核心战况',
      items: [
        { id: 'resources', label: '玩家资源', icon: Coins },
        { id: 'unit', label: '选中单位', icon: UserCheck },
        { id: 'batch', label: '批量修改', icon: Layers },
        { id: 'locks', label: '锁定列表', icon: Lock },
      ],
    },
    {
      group: '属性与扩展',
      items: [
        { id: 'ability_fields', label: '技能字段', icon: Sparkles },
        { id: 'item_fields', label: '物品字段', icon: Package },
        { id: 'extensions', label: '3.0 扩展功能', icon: ShieldAlert },
      ],
    },
    {
      group: '大象经典',
      items: [
        { id: 'elephant', label: '大象经典作弊', icon: Sliders },
        { id: 'hotkeys', label: '全局快捷键', icon: Keyboard, badge: '68' },
      ],
    },
    {
      group: '资料检索',
      items: [
        { id: 'catalogs', label: 'ID 检索目录', icon: Search },
        { id: 'map_catalog', label: '地图自定义数据目录', icon: BookOpen },
        { id: 'equipment3', label: '3.0 新增装备', icon: Swords },
        { id: 'hero_skills', label: '3.0 英雄技能', icon: BookOpen },
      ],
    },
    {
      group: '存档工具',
      items: [
        { id: 'archive', label: '存档代码提取', icon: Archive },
      ],
    },
  ];
</script>

<aside class="sidebar">
  <div class="menu-scroll">
    {#each menuSections as section}
      <div class="menu-section">
        <div class="section-title">{section.group}</div>
        <div class="section-items">
          {#each section.items as item}
            <button
              class="nav-item {currentTab === item.id ? 'active' : ''}"
              onclick={() => onSelectTab(item.id)}
            >
              <item.icon size={15} class="nav-icon" />
              <span class="nav-label">{item.label}</span>
              {#if item.badge}
                <span class="badge">{item.badge}</span>
              {/if}
            </button>
          {/each}
        </div>
      </div>
    {/each}
  </div>
</aside>

<style>
  .sidebar {
    width: 215px;
    height: 100%;
    background-color: var(--bg-surface);
    border-right: 1px solid var(--border-subtle);
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
  }

  .menu-scroll {
    flex: 1;
    overflow-y: auto;
    padding: 12px 10px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .menu-section {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .section-title {
    font-size: 11px;
    text-transform: uppercase;
    font-weight: 700;
    color: var(--text-muted);
    letter-spacing: 0.6px;
    padding: 3px 8px;
  }

  .section-items {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .nav-item {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 12px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    text-align: left;
    transition: all 0.12s ease;
  }

  .nav-item:hover {
    background-color: var(--bg-card);
    color: var(--text-primary);
    border-color: rgba(255, 255, 255, 0.08);
  }

  .nav-item.active {
    background: linear-gradient(90deg, rgba(245, 158, 11, 0.22) 0%, rgba(245, 158, 11, 0.05) 100%);
    border-color: var(--border-gold);
    color: var(--text-gold);
    font-weight: 700;
  }

  .sidebar .nav-item.active :global(.nav-icon) {
    color: var(--color-gold);
  }

  .nav-label {
    flex: 1;
  }

  .badge {
    background-color: var(--color-gold);
    color: var(--text-on-accent);
    font-size: 11px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 10px;
    font-family: var(--font-mono);
  }
</style>
