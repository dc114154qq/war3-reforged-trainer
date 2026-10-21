<script lang="ts">
  import { onMount,onDestroy } from 'svelte';
  import { api,type DefinitionProgress,type DefinitionResult } from '../api';
  let {mapPath=$bindable(''),outputFolder=$bindable(''),onClose}:{mapPath?:string;outputFolder?:string;onClose:()=>void}=$props();
  let progress=$state<DefinitionProgress>({jobId:'',status:'idle',elapsed:0});
  let result=$state<DefinitionResult|null>(null);
  let starting=$state(false);
  let choosing=$state(false);
  let timer:ReturnType<typeof setTimeout>;
  let disposed=false;
  const busy=$derived(starting || ['running','cancelling'].includes(progress.status));
  const stages:Record<string,string>={queued:'准备处理',source_hash_begin:'核对输入文件',start:'读取定义资料',copy_begin:'复制原文件',source_copied:'复制校验完成',scan_archive:'检查归档文件',chapter_begin:'处理章节',table_layout_verified:'检查数据表格式',write_table:'写入背包定义',archive_verify:'复查归档',verify_member:'核对原有文件',chapter_verified:'章节校验完成',replace_chapter:'保存战役章节',output_verify:'核对最终输出',verified:'准备完成输出',complete:'处理完成'};
  async function poll(id='') {
    try {
      progress=await api.getBackpackDefinitionProgress(id);
      if(progress.status==='succeeded')result=progress.result || null;
      else if(progress.status==='failed'){
        result={success:false,error:progress.error,logPath:progress.logPath};
      }
      if(!disposed && ['running','cancelling'].includes(progress.status))timer=setTimeout(()=>poll(progress.jobId),250);
    } catch { /* The shared API presents the communication failure. */ }
  }
  async function start(){
    starting=true;result=null;clearTimeout(timer);
    try {const job=await api.startBackpackDefinitions(mapPath,outputFolder);if(job.success)await poll(job.jobId);}
    finally {starting=false;}
  }
  async function stop(){await api.cancelBackpackDefinitions(progress.jobId);progress.status='cancelling';}
  async function choose(folder=false){
    choosing=true;
    try {const r=folder?await api.chooseDefinitionFolder():await api.chooseDefinitionFile();if(r.path){if(folder)outputFolder=r.path;else mapPath=r.path;}}
    finally {choosing=false;}
  }
  async function copyPath(){try {await navigator.clipboard.writeText(result?.destination || '');}catch {window.dispatchEvent(new CustomEvent('war3-error',{detail:'复制失败，请选中完整路径后复制。'}));}}
  onMount(()=>{poll();});
  onDestroy(()=>{disposed=true;clearTimeout(timer);});
</script>

<div class="modal-overlay">
  <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="definition-title" tabindex="-1">
    <div class="modal-header"><h2 id="definition-title">补齐战役／地图背包定义（生成新副本）</h2><button class="btn btn-secondary" aria-label="关闭处理窗口" onclick={onClose}>关闭</button></div>
    <div class="modal-body">
      <p>添加背包提示“背包装备未定义”时，选择战役或地图补齐定义。原文件会保留；完成后请使用下方新副本重新进入地图。已有存档仍保留保存时的数据。</p>
      <div class="path-heading"><label for="def-path">地图/战役文件完整路径</label><button class="btn btn-secondary btn-sm" onclick={()=>choose()} disabled={busy || choosing}>选择文件…</button></div>
      <textarea id="def-path" class="mono" rows="3" bind:value={mapPath} disabled={busy} placeholder="支持 .w3n / .w3x / .w3m，也可以粘贴完整路径"></textarea>
      <div class="path-heading"><label for="def-output">输出文件夹（留空则放在原文件旁边）</label><button class="btn btn-secondary btn-sm" onclick={()=>choose(true)} disabled={busy || choosing}>选择文件夹…</button></div>
      <textarea id="def-output" class="mono" rows="2" bind:value={outputFolder} disabled={busy}></textarea>
      {#if progress.status!=='idle'}
        <div class="progress-box" role="status" aria-live="polite">
          <strong>{progress.status==='cancelling'?'正在停止，请稍候…':progress.status==='cancelled'?'处理已停止，原文件已保留。':stages[progress.stage || ''] || '正在处理'}</strong>
          <div>已用时间：{progress.elapsed.toFixed(1)} 秒</div>
          {#if progress.total}<div>章节进度：{progress.completed || 0} / {progress.total}；当前第 {progress.index} 章</div><progress aria-label="章节处理进度" max={progress.total} value={progress.completed || 0}></progress>{:else if busy}<progress aria-label="正在检查文件"></progress>{/if}
          {#if progress.chapter}<div class="dest-text">当前章节：{progress.chapter}</div>{/if}
          {#if progress.currentFile}<div class="dest-text">当前文件：{progress.currentFile}</div>{/if}
          {#if progress.logPath}<div class="dest-text">处理日志：{progress.logPath}</div>{/if}
        </div>
      {/if}
      {#if result}
        <div class="result-box" class:ok={result.success} class:err={!!result.error}>
          {#if result.error}<p>{result.error}</p>{#if result.logPath}<div class="dest-text">处理日志：{result.logPath}</div>{/if}
          {:else}<p>{result.message}</p><strong>输出文件完整路径：</strong><div class="dest-text mono">{result.destination}</div><button class="btn btn-secondary btn-sm" onclick={copyPath}>复制完整路径</button>
            {#if result.report}<div class="dest-text">处理报告：{result.report.report_path}</div><div class="dest-text">处理日志：{result.report.log_path}</div>{/if}
          {/if}
        </div>
      {/if}
    </div>
    <div class="modal-footer">{#if busy}<span>关闭窗口后仍会继续处理，可重新打开查看。</span><button class="btn btn-danger" disabled={progress.status==='cancelling'} onclick={stop}>停止处理</button>{:else}<button class="btn btn-primary" onclick={start} disabled={!mapPath.trim() || choosing}>立即补齐定义</button>{/if}</div>
  </div>
</div>

<style>
  .modal-overlay {position:fixed;inset:0;background:#0008;z-index:400;display:flex;align-items:center;justify-content:center;padding:16px;}
  .modal-box {width:760px;max-width:100%;max-height:100%;display:flex;flex-direction:column;background:var(--bg-surface);border:1px solid var(--border-normal);border-radius:8px;box-shadow:0 16px 50px #0007;min-width:0;}
  .modal-header,.modal-footer {display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;padding:12px 16px;flex-shrink:0;}
  .modal-header {border-bottom:1px solid var(--border-subtle);}
  h2 {font-size:16px;color:var(--text-primary);}
  .modal-body {overflow:auto;padding:16px;display:flex;flex-direction:column;gap:10px;min-width:0;line-height:1.7;color:var(--text-secondary);}
  .path-heading {display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;}
  textarea {width:100%;resize:vertical;min-height:52px;padding:8px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.6;}
  .progress-box,.result-box {padding:12px;border:1px solid var(--border-normal);border-radius:6px;background:var(--bg-raised);color:var(--text-primary);min-width:0;}
  .result-box.ok {background:var(--status-success-bg);color:var(--status-success-text);}
  .result-box.err {background:var(--status-danger-bg);color:var(--status-danger-text);}
  .dest-text {white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;user-select:text;margin:6px 0;}
  progress {width:100%;height:12px;accent-color:var(--color-gold);}
  .modal-footer {border-top:1px solid var(--border-subtle);justify-content:flex-end;font-size:12px;color:var(--text-secondary);}
</style>
