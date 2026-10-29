<script lang="ts">
  import {onMount,onDestroy,tick} from 'svelte';
  import {api,type MapCatalogProgress,type MapCatalogRow} from '../api';
  import MapCatalogEntryDialog from './MapCatalogEntryDialog.svelte';
  let path=$state(''),kind=$state('item'),query=$state(''),scope=$state(''),changeType=$state('');
  let progress=$state<MapCatalogProgress>({jobId:'',status:'idle',elapsed:0});
  let rows=$state<MapCatalogRow[]>([]),detail=$state<MapCatalogRow|null>(null);
  let offset=$state(0),matches=$state(0),choosing=$state(false),starting=$state(false),loading=$state(false),exporting=$state(false);
  let exportedPath=$state(''),exportCount=$state(0),format=$state('csv');
  let issuesOpen=$state(false),diagnosticsBox=$state<HTMLElement>();
  let disposed=false,searchRevision=0,detailRevision=0;
  let timer:ReturnType<typeof setTimeout>,searchTimer:ReturnType<typeof setTimeout>;
  const busy=$derived(starting || ['running','cancelling'].includes(progress.status));
  const ready=$derived(['succeeded','partial'].includes(progress.status));
  const kinds=[['item','物品'],['ability','技能'],['unit','单位'],['upgrade','科技']];
  const phases:Record<string,string>={queued:'准备读取',hash:'核对输入文件',chapter:'读取章节',objects:'读取物编对象',tables:'检查数据表',chapter_complete:'章节读取完成',verify:'复核原文件',complete:'读取完成'};
  const statuses:Record<string,string>={succeeded:'读取完成',partial:'部分内容未能读取',failed:'读取失败',cancelled:'读取已停止'};
  const diagnostics=$derived(progress.diagnostics || progress.warnings || []);
  async function showIssues(){issuesOpen=true;await tick();diagnosticsBox?.scrollIntoView({block:'nearest'});}
  async function copyIssues(){await copy(diagnostics.map(d=>`${d.scope} / ${d.file}\n${d.message}${'impact' in d && d.impact?'\n'+d.impact:''}`).join('\n\n'));}
  async function poll(id='') {
    try {
      const before=progress;
      progress=await api.getMapCatalogProgress(id);
      if(ready && (before.jobId!==progress.jobId || !['succeeded','partial'].includes(before.status))){issuesOpen=progress.status==='partial';await search(0);}
    } catch {/* Shared API shows errors. */}
    finally {if(!disposed && ['running','cancelling'].includes(progress.status))timer=setTimeout(()=>poll(progress.jobId),400);}
  }
  async function choose(){choosing=true;try{const r=await api.chooseDefinitionFile();if(r.path)path=r.path;}catch{}finally{choosing=false;}}
  async function start(){
    starting=true;clearTimeout(timer);clearTimeout(searchTimer);++searchRevision;++detailRevision;
    rows=[];detail=null;matches=0;offset=0;scope='';exportedPath='';issuesOpen=false;
    try{const r=await api.startMapCatalog(path);if(r.success)await poll(r.jobId);}catch{}finally{starting=false;}
  }
  async function stop(){try{await api.cancelMapCatalog(progress.jobId);progress.status='cancelling';}catch{}}
  async function search(page=0){
    if(!ready)return;
    const revision=++searchRevision;++detailRevision;detail=null;loading=true;offset=page;
    try {
      const r=await api.searchMapCatalog(progress.jobId,kind,query,scope,changeType,page);
      if(revision!==searchRevision || disposed)return;
      rows=r.rows;matches=r.matchCount;
    }catch{if(revision===searchRevision){rows=[];matches=0;}}
    finally{if(revision===searchRevision)loading=false;}
  }
  function filter(){clearTimeout(searchTimer);++searchRevision;searchTimer=setTimeout(()=>search(0),200);}
  async function select(row:MapCatalogRow){
    const revision=++detailRevision;
    try{const r=await api.getMapCatalogEntry(progress.jobId,row.id);if(revision===detailRevision)detail=r;}catch{}
  }
  async function copy(text:string){try{await navigator.clipboard.writeText(text);}catch{window.dispatchEvent(new CustomEvent('war3-error',{detail:'复制失败，请选中完整文字后复制。'}));}}
  async function exportData(all:boolean){
    exporting=true;
    try{const r=await api.exportMapCatalog(progress.jobId,format,all?'':kind,all?'':query,all?'':scope,all?'':changeType);
      if(r.success && r.path){exportedPath=r.path;exportCount=r.count || 0;}
    }catch{}finally{exporting=false;}
  }
  onMount(()=>{poll();window.addEventListener('war3-map-catalog-issues',showIssues);return ()=>window.removeEventListener('war3-map-catalog-issues',showIssues);});
  onDestroy(()=>{disposed=true;++searchRevision;++detailRevision;clearTimeout(timer);clearTimeout(searchTimer);});
</script>

<div class="map-catalog">
  <header><h2>地图自定义数据目录</h2><span>无需启动游戏</span></header>
  <details class="source-settings" open={!ready}><summary>选择或更换战役／地图</summary>
  <p class="help">选择一张战役或地图，列出它新增或修改的物品、技能、单位和科技。原生且未修改的对象不列入目录，原文件不会被修改。</p>
  <div class="source-controls">
    <label for="map-catalog-path">战役／地图完整路径</label>
    <textarea id="map-catalog-path" bind:value={path} rows="2" disabled={busy || exporting} placeholder="支持 .w3n / .w3x / .w3m"></textarea>
    <div class="actions">
      <button class="btn btn-secondary" onclick={choose} disabled={busy || choosing || exporting}>选择战役／地图…</button>
      <button class="btn btn-primary" onclick={start} disabled={!path.trim() || busy || choosing || exporting}>读取自定义目录</button>
      {#if busy}<button class="btn btn-danger" onclick={stop} disabled={starting || progress.status==='cancelling'}>停止读取</button>{/if}
    </div>
  </div>
  </details>
  {#if progress.status!=='idle'}
    <div class="scan-status" aria-live="polite">
      <strong>{progress.status==='cancelling'?'正在停止，请稍候…':statuses[progress.status] || phases[progress.stage || ''] || '正在读取'}</strong>
      <span>已用时间：{progress.elapsed.toFixed(1)} 秒</span>
      {#if busy}<progress aria-label="地图目录读取进度" max={progress.total || undefined} value={progress.total?Math.max(0,(progress.index || 1)-1):undefined}></progress>{/if}
      {#if busy && progress.scope}<div class="full-path">{progress.index || 0} / {progress.total || 0} · {progress.scope}</div>{/if}
      {#if busy && progress.file}<div class="full-path">{progress.file}</div>{/if}
      {#if progress.error}<div class="full-path">{progress.error}</div>{/if}
    </div>
  {/if}
  {#if ready}
    <p class="help full-path">已读取文件：{progress.source}</p>
    <details class="scope-help"><summary>目录范围与章节说明</summary><p class="help">战役共用数据只列一次；章节记录表示该章节自己的修改。目录读取静态物编和数据表，脚本运行后临时修改的内容不在此目录中。</p></details>
    {#if diagnostics.length}
      <section class="diagnostics" bind:this={diagnosticsBox} class:has-warning={progress.status==='partial'} aria-label="目录读取详情">
        <div class="diagnostic-heading"><strong>{progress.status==='partial'?'部分字段需要注意':'目录读取完成，有附加文字提示'}</strong><button class="btn btn-secondary btn-sm" onclick={()=>issuesOpen=!issuesOpen}>{issuesOpen?'收起原因':'查看具体原因'}</button><button class="btn btn-secondary btn-sm" onclick={copyIssues}>复制完整原因</button></div>
        {#if issuesOpen}<div class="diagnostic-body" role="region" aria-label="具体原因列表">
          {#each diagnostics as warning}<article><strong class="full-path">{warning.scope} / {warning.file}</strong><p class="full-path">{warning.message}</p>{#if 'impact' in warning && warning.impact}<p class="full-path">{warning.impact}</p>{/if}</article>{/each}
        </div>{/if}
      </section>
    {/if}
  {/if}
  <div class="filters">
    <div class="kind-tabs">{#each kinds as [id,label]}<button class="btn" class:btn-primary={kind===id} class:btn-secondary={kind!==id} disabled={!ready || exporting} onclick={()=>{kind=id;search(0);}}><span>{label}</span> ({progress.counts?.[id] || 0})</button>{/each}</div>
    <label>来源章节<select bind:value={scope} onchange={()=>search(0)} disabled={!ready || exporting}><option value="">全部来源</option>{#each progress.scopes || [] as s}<option value={s}>{s}</option>{/each}</select></label>
    <label>改动类型<select bind:value={changeType} onchange={()=>search(0)} disabled={!ready || exporting}><option value="">新增与修改</option><option value="added">新增对象</option><option value="modified">修改原生对象</option></select></label>
    <input class="query" aria-label="搜索自定义目录" bind:value={query} oninput={filter} disabled={!ready || exporting} placeholder="搜索代码、名称、说明、字段或数值…" />
  </div>
  <div class="exports">
    <span>匹配：{matches} / {progress.rowCount || 0}</span>
    <select aria-label="导出格式" bind:value={format} disabled={exporting}><option value="csv">CSV（Excel 可打开）</option><option value="json">JSON（含完整字段）</option></select>
    <button class="btn btn-secondary" onclick={()=>exportData(false)} disabled={!ready || exporting || loading}>导出当前筛选</button>
    <button class="btn btn-secondary" onclick={()=>exportData(true)} disabled={!ready || exporting}>导出全部四类数据</button>
    {#if exporting}<span>正在导出…</span>{/if}
  </div>
  {#if exportedPath}<div class="export-result"><strong>导出完成：</strong>{exportCount}<div class="full-path">{exportedPath}</div><button class="btn btn-secondary btn-sm" onclick={()=>copy(exportedPath)}>复制完整路径</button></div>{/if}
  <div class="object-list">
    <table><thead><tr><th>对象代码</th><th>名称</th><th>描述／效果／单位介绍</th><th>改动类型</th><th>来源章节</th><th>原型代码</th><th>操作</th></tr></thead>
      <tbody>{#each rows as row}<tr class:selected={detail?.id===row.id}>
        <td class="mono">{row.rawcode}</td><td><div>{row.name}</div>{#if row.isHero}<div class="hero-name"><span>英雄本名：</span>{row.heroNames?.length?row.heroNames.join('、'):'物编未提供固定本名'}</div>{/if}</td><td class="description">{row.description || '该对象未提供说明，可查看具体修改字段。'}</td>
        <td>{row.changeType==='added'?'新增对象':'修改原生对象'}<br />{row.changeCount}</td><td>{row.scope}</td><td class="mono">{row.base}</td>
        <td><button class="btn btn-secondary btn-sm" onclick={()=>copy(row.rawcode)}>复制代码</button><button class="btn btn-secondary btn-sm" onclick={()=>select(row)}>查看改动</button></td>
      </tr>{/each}</tbody></table>
    {#if !rows.length}<p class="empty">{loading?'正在检索…':ready?'当前筛选没有新增或修改的对象。':'请先选择战役或地图并读取目录。'}</p>{/if}
  </div>
  <div class="pagination"><button class="btn btn-secondary btn-sm" disabled={!ready || loading || offset===0} onclick={()=>search(Math.max(0,offset-100))}>上一页</button><span>{matches?offset+1:0}–{Math.min(offset+100,matches)} / {matches}</span><button class="btn btn-secondary btn-sm" disabled={!ready || loading || offset+100>=matches} onclick={()=>search(offset+100)}>下一页</button></div>
  {#if detail}
    <MapCatalogEntryDialog entry={detail} onClose={()=>detail=null}/>
  {/if}
</div>

<style>
  .map-catalog{height:100%;min-height:0;display:flex;flex-direction:column;gap:10px;padding:16px;overflow:auto;color:var(--text-primary);background:var(--bg-surface);}
  header,.actions,.filters,.exports,.pagination{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
  header{justify-content:space-between;}h2{font-size:17px;margin:0;}header span,.help{font-size:12px;color:var(--text-secondary);line-height:1.65;margin:0;}
  .source-controls{display:flex;flex-direction:column;gap:6px;}textarea{width:100%;min-height:50px;resize:vertical;padding:8px;white-space:pre-wrap;overflow-wrap:anywhere;}
  .full-path{overflow-wrap:anywhere;white-space:pre-wrap;word-break:break-word;user-select:text;min-width:0;line-height:1.6;}
  .scan-status,.export-result{padding:10px;border:1px solid var(--border-normal);border-radius:6px;background:var(--bg-raised);}.scan-status>span{margin-left:10px;font-size:12px;}progress{width:100%;height:10px;}
  .diagnostics{flex-shrink:0;min-width:0;border:1px solid var(--border-normal);border-radius:6px;background:var(--bg-raised);}.diagnostics.has-warning{border-color:var(--status-danger-text);}.diagnostic-heading{display:flex;align-items:center;flex-wrap:wrap;gap:8px;padding:9px 11px;}.diagnostic-heading>strong{margin-right:auto;}.diagnostic-body{max-height:36vh;min-height:90px;overflow:auto;padding:0 11px 8px;}.diagnostic-body article{padding:8px 0;border-top:1px solid var(--border-subtle);}.diagnostic-body p{margin:6px 0;}.hero-name{font-size:12px;font-weight:600;margin-top:6px;color:var(--text-primary);}
  .kind-tabs{display:flex;gap:5px;}.filters label{display:flex;align-items:center;gap:6px;font-size:12px;}.filters select{max-width:230px;}.query{min-width:230px;flex:1;padding:7px;}select{padding:6px;}.exports{font-size:12px;}.exports>span:first-child{margin-right:auto;}
  .object-list{flex:1 0 300px;min-height:280px;overflow:auto;border:1px solid var(--border-normal);border-radius:6px;}
  table{width:100%;min-width:900px;border-collapse:collapse;table-layout:fixed;font-size:12px;}th{position:sticky;top:0;background:var(--bg-raised);text-align:left;color:var(--text-primary);z-index:1;}th,td{padding:9px;border-bottom:1px solid var(--border-subtle);vertical-align:top;white-space:pre-wrap;overflow-wrap:anywhere;user-select:text;}th:first-child{width:90px;}th:nth-child(2){width:150px;}th:nth-child(3){width:300px;}td .btn{margin-bottom:5px;}tr.selected{background:var(--bg-raised);}.description{line-height:1.6;}.empty{padding:20px;color:var(--text-secondary);}.pagination{justify-content:center;font-size:12px;}
  .source-controls,.scan-status,.filters,.exports,.pagination,header,.help,.export-result{flex-shrink:0;}
  .source-settings,.scope-help{flex-shrink:0;font-size:12px;}.source-settings>summary,.scope-help>summary{cursor:pointer;padding:5px 0;color:var(--text-secondary);}.source-settings>.help{margin:5px 0 8px;}
</style>
