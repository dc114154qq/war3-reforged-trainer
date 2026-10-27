<script lang="ts">
  import {onMount} from 'svelte';
  import type {MapCatalogRow} from '../api';
  let {entry,onClose}:{entry:MapCatalogRow;onClose:()=>void}=$props();
  let dialog:HTMLDialogElement;
  let copied=$state(false);
  function valueText(v:unknown):string{return v===null || v===undefined?'—':typeof v==='object'?JSON.stringify(v):String(v);}
  async function copy(){
    const rows=(entry.changes || []).map(c=>`${c.label} [${c.field}] ${c.level}/${c.index}\n${c.baseKnown?valueText(c.baseValue):'未收录原值'} → ${valueText(c.value)}\n${c.file}`).join('\n\n');
    try{await navigator.clipboard.writeText([entry.rawcode,entry.name,(entry.heroNames || []).join('、'),entry.scope,rows].filter(Boolean).join('\n'));copied=true;}catch{}
  }
  onMount(()=>{dialog.showModal();});
</script>

<dialog bind:this={dialog} class="catalog-entry-dialog" aria-labelledby="catalog-entry-title" oncancel={onClose}>
  <header><div><h2 id="catalog-entry-title">{entry.rawcode} · {entry.name}</h2>{#if entry.heroNames?.length}<p class="hero-names"><span>英雄本名：</span>{entry.heroNames.join('、')}</p>{/if}<p class="source"><span>来源章节：</span>{entry.scope} · <span>原型代码：</span>{entry.base}</p></div><button class="btn btn-secondary" onclick={onClose}>关闭详情</button></header>
  {#if entry.isHero}<p class="hero-note">本名来自物编；多个名称表示候选名字。</p>{/if}
  {#if entry.description}<details class="entry-description"><summary>描述／效果／单位介绍</summary><p>{entry.description}</p></details>{/if}
  <div class="field-table" aria-label="完整字段改动表" role="region">
    <table><colgroup><col class="col-label"/><col class="col-level"/><col class="col-before"/><col class="col-after"/><col class="col-file"/></colgroup>
      <thead><tr><th>字段中文名称／ID</th><th>等级／数据列</th><th>原值</th><th>地图中的值</th><th>来源文件</th></tr></thead>
      <tbody>{#each entry.changes || [] as change}<tr><td>{change.label}<div class="field-id mono">{change.field}</div></td><td>{change.level} / {change.index}</td><td>{change.baseKnown?valueText(change.baseValue):'未收录原值'}</td><td>{valueText(change.value)}{#if valueText(change.rawValue)!==valueText(change.value)}<div class="raw-value">{valueText(change.rawValue)}</div>{/if}</td><td>{change.file}</td></tr>{/each}</tbody>
    </table>
    {#if !entry.changes?.length}<p>这是以原生对象为原型新增的对象，未额外修改字段。</p>{/if}
  </div>
  <footer><span>共 {entry.changeCount} 个改动字段</span><button class="btn btn-secondary" onclick={copy}>{copied?'已复制':'复制全部字段'}</button><button class="btn btn-primary" onclick={onClose}>关闭详情</button></footer>
</dialog>

<style>
  .catalog-entry-dialog{margin:auto;width:min(1380px,calc(100vw - 32px));height:min(920px,calc(100dvh - 32px));max-width:calc(100vw - 32px);max-height:calc(100dvh - 32px);padding:0;border:1px solid var(--border-normal);border-radius:8px;background:var(--bg-surface);color:var(--text-primary);overflow:hidden;box-shadow:0 18px 60px #0009;}
  .catalog-entry-dialog[open]{display:flex;flex-direction:column;}.catalog-entry-dialog::backdrop{background:#0009;}
  header,footer{display:flex;gap:10px;justify-content:space-between;align-items:center;padding:14px 18px;flex-shrink:0;}
  header{border-bottom:1px solid var(--border-normal);}header>div{min-width:0;overflow-wrap:anywhere;max-height:24vh;overflow:auto;}h2{font-size:17px;margin:0;}.hero-names{font-size:15px;font-weight:600;margin:6px 0;}.source{font-size:12px;color:var(--text-secondary);margin:4px 0;}p{white-space:pre-wrap;overflow-wrap:anywhere;user-select:text;line-height:1.65;}
  .entry-description{margin:0 18px;padding:8px 0;flex-shrink:0;}.entry-description p{max-height:20vh;overflow:auto;margin:7px 0;}
  .hero-note{margin:0 18px 5px;font-size:12px;color:var(--text-secondary);flex-shrink:0;}
  .field-table{flex:1;min-height:0;overflow:auto;border-top:1px solid var(--border-subtle);border-bottom:1px solid var(--border-subtle);}
  table{border-collapse:collapse;table-layout:fixed;width:100%;min-width:1000px;font-size:13px;line-height:1.65;}.col-label{width:20%;}.col-level{width:8%;}.col-before,.col-after{width:27%;}.col-file{width:18%;}
  th{position:sticky;top:0;z-index:1;background:var(--bg-raised);text-align:left;}th,td{padding:11px 13px;vertical-align:top;border-bottom:1px solid var(--border-subtle);white-space:pre-wrap;overflow-wrap:anywhere;user-select:text;}.field-id,.raw-value{font-size:12px;color:var(--text-secondary);margin-top:5px;}.raw-value{padding-top:5px;border-top:1px dashed var(--border-subtle);}
  footer{justify-content:flex-end;flex-wrap:wrap;}footer>span{margin-right:auto;font-size:12px;color:var(--text-secondary);}
</style>
