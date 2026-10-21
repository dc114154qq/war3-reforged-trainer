<script lang="ts">
  import { api } from '../api';
  import type { ArchiveRow, RpgCodeRow } from '../types';
  import { Archive, FolderSearch, FileText, Cpu, Search, Copy, Check, AlertCircle, RefreshCw } from 'lucide-svelte';

  let currentSubTab = $state<'campaign' | 'rpg'>('campaign');

  // Campaign subtab state
  let directoryPath = $state('');
  let archiveFiles = $state<any[]>([]);
  let selectedFile = $state('');
  let isScanningDir = $state(false);
  let isReadingArchive = $state(false);
  let archiveRows = $state<ArchiveRow[]>([]);
  let archiveFilter = $state('');

  // RPG subtab state
  let rpgPrefix = $state('-load');
  let manualText = $state('');
  let isScanningRpg = $state(false);
  let rpgRows = $state<RpgCodeRow[]>([]);
  let copiedRpgCode = $state<string | null>(null);

  // Status feedback
  let feedback = $state('');
  let isError = $state(false);

  // 1. Campaign actions
  async function handleScanDirectory() {
    isScanningDir = true;
    feedback = '正在扫描存档目录...';
    isError = false;
    try {
      const res = await api.scanArchiveDirectory(directoryPath);
      if (res.success) {
        archiveFiles = res.files || [];
        if (archiveFiles.length > 0) {
          selectedFile = archiveFiles[0].path;
          feedback = `✓ 找到 ${archiveFiles.length} 个战役存档文件`;
        } else {
          feedback = '未在指定目录中找到 .w3v 或 .w3z 存档文件';
        }
      } else {
        feedback = `✗ 扫描失败: ${res.error}`;
        isError = true;
      }
    } catch (err: any) {
      feedback = `✗ 异常: ${err.message || err}`;
      isError = true;
    } finally {
      isScanningDir = false;
    }
  }

  async function handleReadArchive() {
    if (!selectedFile) {
      feedback = '请先选择要解析的存档文件';
      window.dispatchEvent(new CustomEvent('war3-error',{detail:feedback}));
      isError = true;
      return;
    }
    isReadingArchive = true;
    feedback = '正在解析战役存档结构...';
    isError = false;
    try {
      const res = await api.readArchiveFile(selectedFile);
      if (res.success) {
        archiveRows = res.rows || [];
        feedback = `✓ 解析完成，共提取 ${archiveRows.length} 条英雄数据`;
      } else {
        feedback = `✗ 解析失败: ${res.error}`;
        isError = true;
      }
    } catch (err: any) {
      feedback = `✗ 异常: ${err.message || err}`;
      isError = true;
    } finally {
      isReadingArchive = false;
    }
  }

  async function handleReadLiveHeroes() {
    isReadingArchive = true;
    feedback = '正在从当前游戏内存读取战役英雄缓存...';
    isError = false;
    try {
      const res = await api.readLiveHeroes();
      if (res.success) {
        archiveRows = res.rows || [];
        feedback = `✓ 内存读取完成，共提取 ${archiveRows.length} 条英雄数据`;
      } else {
        feedback = `✗ 读取失败: ${res.error}`;
        isError = true;
      }
    } catch (err: any) {
      feedback = `✗ 异常: ${err.message || err}`;
      isError = true;
    } finally {
      isReadingArchive = false;
    }
  }

  // 2. RPG code actions
  async function handleScanRpgMemory() {
    isScanningRpg = true;
    feedback = `正在扫描游戏进程内存中的 ${rpgPrefix} 载入代码...`;
    isError = false;
    try {
      const res = await api.scanRpgCodesMemory(rpgPrefix);
      if (res.success) {
        rpgRows = res.rows || [];
        feedback = `✓ 扫描完成，找到 ${rpgRows.length} 条 RPG 存读档代码`;
      } else {
        feedback = `✗ 扫描失败: ${res.error}`;
        isError = true;
      }
    } catch (err: any) {
      feedback = `✗ 异常: ${err.message || err}`;
      isError = true;
    } finally {
      isScanningRpg = false;
    }
  }

  async function handleParseRpgText() {
    if (!manualText.trim()) {
      feedback = '请先在文本框中粘贴包含 RPG 代码的文本';
      window.dispatchEvent(new CustomEvent('war3-error',{detail:feedback}));
      isError = true;
      return;
    }
    isScanningRpg = true;
    feedback = '正在从文本中提取代码...';
    isError = false;
    try {
      const res = await api.parseRpgCodesText(manualText, rpgPrefix);
      if (res.success) {
        rpgRows = res.rows || [];
        feedback = `✓ 提取完成，解析出 ${rpgRows.length} 条代码`;
      } else {
        feedback = `✗ 解析失败: ${res.error}`;
        isError = true;
      }
    } catch (err: any) {
      feedback = `✗ 异常: ${err.message || err}`;
      isError = true;
    } finally {
      isScanningRpg = false;
    }
  }

  async function copyRpgCode(code: string) {
    try {
      await navigator.clipboard.writeText(code);
      copiedRpgCode = code;
      setTimeout(() => {
        if (copiedRpgCode === code) copiedRpgCode = null;
      }, 1800);
    } catch (err) {
      console.warn('Clipboard write failed:', err);
    }
  }

  const filteredArchiveRows = $derived(
    archiveRows.filter((r) => {
      if (!archiveFilter.trim()) return true;
      const q = archiveFilter.toLowerCase();
      return (
        r.scope.toLowerCase().includes(q) ||
        r.key.toLowerCase().includes(q) ||
        r.value.toLowerCase().includes(q)
      );
    })
  );
</script>

<div class="archive-container">
  <!-- Subtab Switcher -->
  <div class="tab-header">
    <div class="tab-buttons">
      <button
        class="subtab-btn {currentSubTab === 'campaign' ? 'active' : ''}"
        onclick={() => (currentSubTab = 'campaign')}
      >
        <Archive size={14} />
        <span>战役存档提取 (.w3v / .w3z)</span>
      </button>
      <button
        class="subtab-btn {currentSubTab === 'rpg' ? 'active' : ''}"
        onclick={() => (currentSubTab = 'rpg')}
      >
        <Cpu size={14} />
        <span>RPG 载入码扫描 (-load)</span>
      </button>
    </div>

    {#if feedback}
      <div class="feedback-badge {isError ? 'error' : 'success'}">
        {#if isError}
          <AlertCircle size={13} />
        {:else}
          <Check size={13} />
        {/if}
        <span>{feedback}</span>
      </div>
    {/if}
  </div>

  <!-- Subtab 1: Campaign Archive -->
  {#if currentSubTab === 'campaign'}
    <div class="subtab-content">
      <div class="control-panel">
        <div class="input-row">
          <div class="field-group flex-1">
            <label for="archive-dir">存档目录路径 (留空将自动检索魔兽争霸官方存档目录)</label>
            <input
              id="archive-dir"
              type="text"
              class="input-field"
              placeholder="C:\Users\...\Documents\Warcraft III\Save"
              bind:value={directoryPath}
            />
          </div>
          <button class="btn btn-secondary" onclick={handleScanDirectory} disabled={isScanningDir}>
            <FolderSearch size={14} class={isScanningDir ? 'spinning' : ''} />
            扫描目录
          </button>
        </div>

        {#if archiveFiles.length > 0}
          <div class="file-picker-row">
            <label for="archive-file-select">选择目标存档文件:</label>
            <select id="archive-file-select" class="select-field flex-1" bind:value={selectedFile}>
              {#each archiveFiles as f}
                <option value={f.path}>{f.name} ({f.size || '未知大小'})</option>
              {/each}
            </select>

            <button class="btn btn-primary" onclick={handleReadArchive} disabled={isReadingArchive}>
              <FileText size={14} class={isReadingArchive ? 'spinning' : ''} />
              解析此存档
            </button>
            <button class="btn btn-secondary" onclick={handleReadLiveHeroes} disabled={isReadingArchive}>
              <RefreshCw size={14} class={isReadingArchive ? 'spinning' : ''} />
              直接读当前内存英雄
            </button>
          </div>
        {/if}

        {#if archiveRows.length > 0}
          <div class="filter-row">
            <div class="search-box flex-1">
              <Search size={14} class="search-icon" />
              <input
                type="text"
                class="input-field"
                placeholder="过滤提取到的英雄属性 / 技能 / 物品..."
                bind:value={archiveFilter}
              />
            </div>
            <span class="count-badge">共提取 {filteredArchiveRows.length} / {archiveRows.length} 项</span>
          </div>
        {/if}
      </div>

      <div class="table-container">
        {#if archiveRows.length === 0}
          <div class="empty-state">
            <Archive size={36} class="empty-icon" />
            <div class="empty-title">未载入战役数据</div>
            <div class="empty-desc">
              点击“扫描目录”寻找本地单人战役存档，或在进行战役时点击“直接读当前内存英雄”提取英雄跨关卡属性与装备缓存。
            </div>
          </div>
        {:else}
          <table class="data-table">
            <thead>
              <tr>
                <th style="width: 140px;">作用域 / 英雄</th>
                <th style="width: 220px;">属性键名 (Key)</th>
                <th style="width: 100px;">数据类型</th>
                <th>提取数值 / 数据内容</th>
              </tr>
            </thead>
            <tbody>
              {#each filteredArchiveRows as row}
                <tr>
                  <td><span class="scope-pill">{row.scope}</span></td>
                  <td class="font-semibold text-bright">{row.key}</td>
                  <td><span class="type-pill">{row.type}</span></td>
                  <td class="mono value-text">{row.value}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </div>
    </div>
  {/if}

  <!-- Subtab 2: RPG Load Codes -->
  {#if currentSubTab === 'rpg'}
    <div class="subtab-content">
      <div class="control-panel">
        <div class="input-row">
          <div class="field-group narrow">
            <label for="prefix-input">命令前缀</label>
            <input
              id="prefix-input"
              type="text"
              class="input-field mono bold"
              placeholder="-load"
              bind:value={rpgPrefix}
            />
          </div>

          <div class="action-buttons-group">
            <button class="btn btn-primary" onclick={handleScanRpgMemory} disabled={isScanningRpg}>
              <Cpu size={14} class={isScanningRpg ? 'spinning' : ''} />
              从魔兽内存扫描
            </button>
          </div>
        </div>

        <div class="manual-box">
          <label for="text-parse-input">或从聊天记录/本地文档中粘贴文本提取:</label>
          <div class="textarea-row">
            <textarea
              id="text-parse-input"
              class="textarea-field"
              rows={2}
              placeholder="在此粘贴包含 -load 或代码的聊天记录、截图OCR文本或日志..."
              bind:value={manualText}
            ></textarea>
            <button class="btn btn-secondary parse-btn" onclick={handleParseRpgText} disabled={isScanningRpg}>
              从文本提取
            </button>
          </div>
        </div>
      </div>

      <div class="table-container">
        {#if rpgRows.length === 0}
          <div class="empty-state">
            <Cpu size={36} class="empty-icon" />
            <div class="empty-title">未扫描到 RPG 载入代码</div>
            <div class="empty-desc">
              在联机 RPG 防守或剧情地图中，点击“从魔兽内存扫描”可自动提取最近接收的存档代码；也可以在上方文本框粘贴后提取。
            </div>
          </div>
        {:else}
          <table class="data-table">
            <thead>
              <tr>
                <th style="width: 120px;">类型</th>
                <th>载入代码 (Load Code)</th>
                <th style="width: 140px;">数据来源</th>
                <th style="width: 100px; text-align: center;">操作</th>
              </tr>
            </thead>
            <tbody>
              {#each rpgRows as row}
                <tr>
                  <td><span class="scope-pill">{row.kind}</span></td>
                  <td>
                    <span class="rpg-code-text mono">{row.code}</span>
                  </td>
                  <td class="text-muted">{row.source}</td>
                  <td style="text-align: center;">
                    <button
                      class="btn-copy {copiedRpgCode === row.code ? 'copied' : ''}"
                      onclick={() => copyRpgCode(row.code)}
                      title="复制完整载入代码"
                    >
                      {#if copiedRpgCode === row.code}
                        <Check size={12} />
                        <span>已复制</span>
                      {:else}
                        <Copy size={12} />
                        <span>复制</span>
                      {/if}
                    </button>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .archive-container {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 16px;
    gap: 12px;
    background-color: var(--bg-surface);
    overflow: hidden;
  }

  .tab-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .tab-buttons {
    display: flex;
    gap: 8px;
  }

  .subtab-btn {
    display: flex;
    align-items: center;
    gap: 6px;
    height: 32px;
    padding: 0 14px;
    background: var(--bg-surface-sunken);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    color: var(--text-normal);
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .subtab-btn:hover {
    border-color: var(--color-gold);
    color: var(--text-bright);
  }

  .subtab-btn.active {
    background: rgba(229, 193, 88, 0.15);
    border-color: var(--color-gold);
    color: var(--color-gold);
    font-weight: 700;
  }

  .feedback-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    padding: 4px 10px;
    border-radius: var(--radius-sm);
  }

  .feedback-badge.success {
    background: var(--status-success-bg);
    border: 1px solid rgba(46, 204, 113, 0.3);
    color: var(--status-success-text);
  }

  .feedback-badge.error {
    background: var(--status-danger-bg);
    border: 1px solid rgba(231, 76, 60, 0.3);
    color: var(--status-danger-text);
  }

  .subtab-content {
    display: flex;
    flex-direction: column;
    flex: 1;
    gap: 12px;
    overflow: hidden;
  }

  .control-panel {
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

  .file-picker-row {
    display: flex;
    gap: 10px;
    align-items: center;
  }

  .file-picker-row label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .filter-row {
    display: flex;
    gap: 12px;
    align-items: center;
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
    width: 100px;
  }

  .flex-1 {
    flex: 1;
  }

  .input-field,
  .select-field {
    height: 32px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 0 10px;
    color: var(--text-bright);
    font-size: 12px;
    outline: none;
  }

  .input-field:focus,
  .select-field:focus {
    border-color: var(--color-gold);
  }

  .manual-box {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .manual-box label {
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
  }

  .textarea-row {
    display: flex;
    gap: 10px;
    align-items: stretch;
  }

  .textarea-field {
    flex: 1;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    padding: 6px 10px;
    color: var(--text-bright);
    font-size: 12px;
    font-family: var(--font-mono);
    outline: none;
    resize: none;
  }

  .textarea-field:focus {
    border-color: var(--color-gold);
  }

  .parse-btn {
    width: 100px;
  }

  .search-box {
    position: relative;
    display: flex;
    align-items: center;
  }

  .archive-container .search-box :global(.search-icon) {
    position: absolute;
    left: 10px;
    color: var(--text-muted);
    pointer-events: none;
  }

  .search-box input {
    width: 100%;
    padding-left: 32px;
  }

  .count-badge {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
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

  .scope-pill {
    display: inline-block;
    padding: 2px 8px;
    background: rgba(245, 158, 11, 0.15);
    color: var(--color-gold);
    border: 1px solid rgba(245, 158, 11, 0.35);
    border-radius: var(--radius-sm);
    font-size: 12px;
    font-weight: 600;
    font-family: var(--font-mono);
  }

  .type-pill {
    display: inline-block;
    padding: 2px 8px;
    background: var(--bg-raised);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    font-size: 11px;
    font-weight: 600;
    color: var(--text-normal);
    font-family: var(--font-mono);
  }

  .value-text {
    color: var(--text-bright);
    word-break: break-all;
  }

  .rpg-code-text {
    font-size: 13px;
    font-weight: 600;
    color: var(--fel-green);
    word-break: break-all;
    user-select: all;
  }

  .btn-copy {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    color: var(--text-normal);
    font-size: 11px;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .btn-copy:hover {
    border-color: var(--color-gold);
    color: var(--color-gold);
  }

  .btn-copy.copied {
    background: var(--status-success-bg);
    border-color: var(--status-success-text);
    color: var(--status-success-text);
  }

  .mono {
    font-family: var(--font-mono);
  }

  .font-semibold {
    font-weight: 600;
  }

  .bold {
    font-weight: 700;
  }

  .text-bright {
    color: var(--text-bright);
  }

  .text-muted {
    color: var(--text-muted);
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

  .archive-container :global(.empty-icon) {
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

  .archive-container :global(.spinning) {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
