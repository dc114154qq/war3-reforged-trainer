<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { api } from './lib/api';
  import type { UiNotice } from './lib/api';
  import type { SystemStatus } from './lib/types';

  import Header from './lib/components/Header.svelte';
  import ErrorDialog from './lib/components/ErrorDialog.svelte';
  import Sidebar from './lib/components/Sidebar.svelte';

  // Panels
  import ResourcesPanel from './lib/components/ResourcesPanel.svelte';
  import UnitPanel from './lib/components/UnitPanel.svelte';
  import BatchEditPanel from './lib/components/BatchEditPanel.svelte';
  import LocksPanel from './lib/components/LocksPanel.svelte';
  import AbilityFieldsPanel from './lib/components/AbilityFieldsPanel.svelte';
  import ItemFieldsPanel from './lib/components/ItemFieldsPanel.svelte';
  import ExtensionsPanel from './lib/components/ExtensionsPanel.svelte';
  import ElephantPanel from './lib/components/ElephantPanel.svelte';
  import ElephantHotkeysPanel from './lib/components/ElephantHotkeysPanel.svelte';
  import CatalogSearchPanel from './lib/components/CatalogSearchPanel.svelte';
  import Equipment3CatalogPanel from './lib/components/Equipment3CatalogPanel.svelte';
  import HeroSkillsCatalogPanel from './lib/components/HeroSkillsCatalogPanel.svelte';
  import ArchiveExtractionPanel from './lib/components/ArchiveExtractionPanel.svelte';

  let currentTab = $state('resources');
  let visitedTabs = $state(['resources']);
  function selectTab(tabId: string) { currentTab = tabId; if (!visitedTabs.includes(tabId)) visitedTabs = [...visitedTabs, tabId]; }

  let systemStatus = $state<SystemStatus>({
    appVersion: '2.1.20',
    edition: '正在读取版本信息',
    connected: false,
    pid: null,
    gameVersion: null,
    adapterProfile: null,
    bridgeProfile: 3,
    hotkeysEnabled: false,
    statusMessage: '正在检测魔兽争霸 III 运行状态...',
    language: 'zh',
  });

  let errors = $state<UiNotice[]>([]);
  const seenNotices=new Set<number>();
  function queueError(notice:UiNotice) {
    if(notice.id && seenNotices.has(notice.id))return;
    if(notice.id)seenNotices.add(notice.id);
    if(errors.some(x=>x.message===notice.message))return;
    errors=[...errors,notice];
  }
  function showError(event: Event) {const d=(event as CustomEvent).detail;queueError(typeof d==='string'?{message:d}:d);}
  let refreshTimer: any = null;
  let notificationTimer: ReturnType<typeof setTimeout>;
  let disposed=false;
  async function pollNotifications(){
    try {for(const n of await api.getUiNotifications()){
      if(n.kind==='unit_read'){
        window.dispatchEvent(new CustomEvent('war3-unit-read',{detail:n.unit}));
        window.dispatchEvent(new CustomEvent('war3-candidates-read',{detail:n.candidates}));
      }else if(n.kind==='parameters')window.dispatchEvent(new CustomEvent('war3-elephant-parameters',{detail:n.parameters}));
      else queueError(n);
    }}
    catch {/* callApi already reports communication errors. */}
    finally {if(!disposed)notificationTimer=setTimeout(pollNotifications,500);}
  }
  let pendingStatus: Promise<void> | null = null;

  function fetchStatus(): Promise<void> {
    if (pendingStatus) return pendingStatus;
    pendingStatus = (async () => {
      try {
        const res = await api.getSystemStatus();
        if (res) systemStatus = res;
      } catch (err) {
        console.warn('fetchStatus failed:', err);
      } finally {
        pendingStatus = null;
      }
    })();
    return pendingStatus;
  }

  onMount(() => {
    window.addEventListener('war3-error', showError);
    window.addEventListener('pywebviewready', fetchStatus);
    document.documentElement.dataset.theme = localStorage.getItem('war3-theme') || 'dark';
    if (window.pywebview?.api) fetchStatus();
    pollNotifications();
    // Periodic status refresh every 2.5 seconds
    refreshTimer = setInterval(fetchStatus, 2500);
  });

  onDestroy(() => {
    if (refreshTimer) clearInterval(refreshTimer);
    disposed=true;clearTimeout(notificationTimer);
    window.removeEventListener('pywebviewready', fetchStatus);
    window.removeEventListener('war3-error', showError);
  });
</script>

<div class="app-layout">
  <!-- Top Navigation Header -->
  <Header status={systemStatus} {currentTab} onRefreshAll={fetchStatus} />

  {#if errors.length}{#key errors[0]}<ErrorDialog notice={errors[0]} onClose={()=>errors=errors.slice(1)} />{/key}{/if}
  <!-- Main Body: Sidebar + Active Panel -->
  <div class="body-layout">
    <Sidebar {currentTab} onSelectTab={selectTab} />

    <main class="main-viewport">
      {#each visitedTabs as tabId}<section class="panel-slot" hidden={tabId !== currentTab}>
      {#if tabId === 'resources'}
        <ResourcesPanel />
      {:else if tabId === 'unit'}
        <UnitPanel />
      {:else if tabId === 'batch'}
        <BatchEditPanel />
      {:else if tabId === 'locks'}
        <LocksPanel />
      {:else if tabId === 'ability_fields'}
        <AbilityFieldsPanel />
      {:else if tabId === 'item_fields'}
        <ItemFieldsPanel />
      {:else if tabId === 'extensions'}
        <ExtensionsPanel />
      {:else if tabId === 'elephant'}
        <ElephantPanel />
      {:else if tabId === 'hotkeys'}
        <ElephantHotkeysPanel />
      {:else if tabId === 'catalogs'}
        <CatalogSearchPanel />
      {:else if tabId === 'equipment3'}
        <Equipment3CatalogPanel />
      {:else if tabId === 'hero_skills'}
        <HeroSkillsCatalogPanel />
      {:else if tabId === 'archive'}
        <ArchiveExtractionPanel />
      {/if}
      </section>{/each}
    </main>
  </div>
</div>

<style>
  .panel-slot { height:100%; min-width:0; }
  .panel-slot[hidden] { display:none; }
  .app-layout {
    display: flex;
    flex-direction: column;
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    background-color: var(--bg-surface);
    color: var(--text-normal);
  }

  .body-layout {
    display: flex;
    flex: 1;
    overflow: hidden;
    position: relative;
  }

  .main-viewport {
    flex: 1;
    height: 100%;
    overflow: hidden;
    background: var(--bg-surface);
    position: relative;
  }
</style>
