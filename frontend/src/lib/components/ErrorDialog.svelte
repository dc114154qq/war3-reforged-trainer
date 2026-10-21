<script lang="ts">
  import { onMount } from 'svelte';
  import type { UiNotice } from '../api';
  let {notice,onClose}:{notice:UiNotice;onClose:()=>void}=$props();
  let dialog:HTMLDialogElement;
  onMount(()=>{dialog.showModal();});
</script>

<dialog bind:this={dialog} class="error-dialog" aria-labelledby="error-title" oncancel={onClose}>
  <h2 id="error-title">{notice.title || '操作未完成'}</h2>
  <p class="error-reason">{notice.message}</p>
  {#if notice.logPath && !notice.message.includes(notice.logPath)}
    <p>诊断日志：</p><p class="error-path">{notice.logPath}</p>
  {/if}
  <div class="error-actions"><button class="btn btn-primary" onclick={onClose}>知道了</button></div>
</dialog>

<style>
  .error-dialog {margin:auto;width:min(640px,calc(100vw - 32px));max-height:calc(100vh - 32px);padding:22px;background:var(--bg-surface);color:var(--text-primary);border:2px solid var(--status-danger-text);border-radius:8px;overflow:auto;box-shadow:0 16px 60px #0008;}
  .error-dialog::backdrop {background:#0008;}
  h2 {font-size:18px;margin-bottom:14px;color:var(--status-danger-text);}
  .error-reason {white-space:pre-wrap;overflow-wrap:anywhere;user-select:text;line-height:1.7;}
  .error-path {overflow-wrap:anywhere;white-space:pre-wrap;user-select:text;font-family:var(--font-mono);}
  .error-actions {display:flex;justify-content:flex-end;margin-top:20px;}
</style>
