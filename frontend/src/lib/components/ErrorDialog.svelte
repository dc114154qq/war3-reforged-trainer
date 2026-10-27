<script lang="ts">
  import { onMount } from 'svelte';
  import type { UiNotice } from '../api';
  let {notice,onClose}:{notice:UiNotice;onClose:()=>void}=$props();
  let dialog:HTMLDialogElement;
  let copied=$state(false);
  async function copyDetails(){
    const details=(notice.details || []).map(d=>`${d.scope} / ${d.file}\n${d.message}${d.impact?'\n'+d.impact:''}`).join('\n\n');
    try{await navigator.clipboard.writeText([notice.message,details,notice.logPath || ''].filter(Boolean).join('\n\n'));copied=true;}
    catch{copied=false;}
  }
  function showPageDetails(){onClose();window.dispatchEvent(new CustomEvent('war3-map-catalog-issues'));}
  onMount(()=>{dialog.showModal();});
</script>

<dialog bind:this={dialog} class="error-dialog" aria-labelledby="error-title" oncancel={onClose}>
  <h2 id="error-title">{notice.title || '操作未完成'}</h2>
  <div class="error-content">
  <p class="error-reason">{notice.message}</p>
  {#if notice.details?.length}
    <section class="error-details" aria-label="具体原因">
      <h3>具体原因</h3>
      {#each notice.details as detail}
        <article><strong>{detail.scope} / {detail.file}</strong><p>{detail.message}</p>{#if detail.impact}<p>{detail.impact}</p>{/if}</article>
      {/each}
    </section>
  {/if}
  {#if notice.logPath && !notice.message.includes(notice.logPath)}
    <p>诊断日志：</p><p class="error-path">{notice.logPath}</p>
  {/if}
  </div>
  <div class="error-actions"><button class="btn btn-secondary" onclick={copyDetails}>{copied?'已复制':'复制完整原因'}</button>{#if notice.context==='map_catalog'}<button class="btn btn-secondary" onclick={showPageDetails}>查看页面详情</button>{/if}<button class="btn btn-primary" onclick={onClose}>知道了</button></div>
</dialog>

<style>
  .error-dialog {margin:auto;width:min(860px,calc(100vw - 32px));max-height:calc(100dvh - 32px);padding:22px;background:var(--bg-surface);color:var(--text-primary);border:2px solid var(--status-danger-text);border-radius:8px;overflow:hidden;box-shadow:0 16px 60px #0008;}
  .error-dialog[open]{display:flex;flex-direction:column;gap:12px;}
  .error-content{overflow:auto;min-height:0;flex:1;padding-right:8px;}
  .error-details article{margin:10px 0;padding:10px;border:1px solid var(--border-normal);border-radius:5px;white-space:pre-wrap;overflow-wrap:anywhere;user-select:text;line-height:1.65;}
  .error-details p{margin:6px 0;}h3{font-size:14px;}
  .error-dialog::backdrop {background:#0008;}
  h2 {font-size:18px;margin-bottom:14px;color:var(--status-danger-text);}
  .error-reason {white-space:pre-wrap;overflow-wrap:anywhere;user-select:text;line-height:1.7;}
  .error-path {overflow-wrap:anywhere;white-space:pre-wrap;user-select:text;font-family:var(--font-mono);}
  .error-actions {display:flex;justify-content:flex-end;flex-wrap:wrap;gap:8px;flex-shrink:0;padding-top:10px;border-top:1px solid var(--border-subtle);}
</style>
