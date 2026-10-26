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
  const selectedPaths=$derived(mapPath.split(/\r?\n/).map(path=>path.trim().replace(/^"(.*)"$/,'$1')).filter(Boolean));
  const outputPaths=$derived((progress.files || []).filter(file=>file.status==='succeeded' && file.destination).map(file=>file.destination));
  const fileStates:Record<string,string>={queued:'等待处理',running:'正在处理',succeeded:'处理成功',failed:'处理失败',cancelled:'已停止',skipped:'尚未处理'};
  const jobStates:Record<string,string>={succeeded:'处理完成',partial:'部分文件处理失败',failed:'处理失败',cancelled:'处理已停止，原文件已保留。'};
  const stages:Record<string,string>={queued:'准备处理',custom_object_begin:'检查地图对象',custom_object_verified:'对象检查完成',custom_object_failed:'发现对象结构异常',source_hash_begin:'核对输入文件',start:'读取定义资料',copy_begin:'复制原文件',source_copied:'复制校验完成',scan_archive:'检查归档文件',chapter_begin:'处理章节',table_layout_verified:'检查数据表格式',write_table:'写入背包定义',archive_verify:'复查归档',verify_member:'核对原有文件',chapter_verified:'章节校验完成',replace_chapter:'保存战役章节',output_verify:'核对最终输出',verified:'准备完成输出',complete:'处理完成'};
  Object.assign(stages,{script_function_order_verified:'章节脚本顺序检查完成',script_validation_failed:'发现章节脚本错误',archive_compaction_begin:'整理归档中的旧数据',archive_compaction_complete:'归档整理完成',archive_compaction_skipped:'归档无需整理',archive_compaction_failed:'归档整理出错'});
  async function poll(id='') {
    try {
      progress=await api.getBackpackDefinitionProgress(id);
      if(progress.result)result=progress.result;
      else if(progress.status==='failed'){
        result={success:false,error:progress.error,logPath:progress.logPath};
      }
    } catch { /* The shared API presents the communication failure. */ }
    finally {if(!disposed && ['running','cancelling'].includes(progress.status))timer=setTimeout(()=>poll(progress.jobId),250);}
  }
  async function start(){
    starting=true;result=null;clearTimeout(timer);
    try {const job=selectedPaths.length>1?await api.startBackpackDefinitionsBatch(selectedPaths,outputFolder):await api.startBackpackDefinitions(selectedPaths[0] || '',outputFolder);if(job.success)await poll(job.jobId);}
    finally {starting=false;}
  }
  async function stop(){await api.cancelBackpackDefinitions(progress.jobId);progress.status='cancelling';}
  async function choose(folder=false){
    choosing=true;
    try {
      if(folder){const r=await api.chooseDefinitionFolder();if(r.path)outputFolder=r.path;}
      else {const r=await api.chooseDefinitionFiles();if(r.paths?.length)mapPath=r.paths.join('\n');}
    }
    finally {choosing=false;}
  }
  async function copyPath(path=result?.destination || ''){try {await navigator.clipboard.writeText(path);}catch {window.dispatchEvent(new CustomEvent('war3-error',{detail:'复制失败，请选中完整路径后复制。'}));}}
  onMount(()=>{poll();});
  onDestroy(()=>{disposed=true;clearTimeout(timer);});
</script>

<div class="modal-overlay">
  <div class="modal-box" role="dialog" aria-modal="true" aria-labelledby="definition-title" tabindex="-1">
    <div class="modal-header"><h2 id="definition-title">补齐战役／地图背包定义（生成新副本）</h2><button class="btn btn-secondary" aria-label="关闭处理窗口" onclick={onClose}>关闭</button></div>
    <div class="modal-body">
      <p>添加背包提示“背包装备未定义”时，选择战役或地图补齐定义。原文件会保留；完成后请使用下方新副本重新进入地图。已有存档仍保留保存时的数据。</p>
      <div class="path-heading"><label for="def-path">地图/战役文件完整路径</label><button class="btn btn-secondary btn-sm" onclick={()=>choose()} disabled={busy || choosing}>选择文件（可多选）…</button></div>
      <textarea id="def-path" class="mono" rows="4" bind:value={mapPath} disabled={busy} placeholder="支持 .w3n / .w3x / .w3m，每行一个完整路径"></textarea>
      <p class="input-help">可一次选择多个文件，也可以每行粘贴一个完整路径。已填入 {selectedPaths.length} 个文件；相同路径会自动去重。</p>
      <div class="path-heading"><label for="def-output">输出文件夹（留空则放在原文件旁边）</label><button class="btn btn-secondary btn-sm" onclick={()=>choose(true)} disabled={busy || choosing}>选择文件夹…</button></div>
      <textarea id="def-output" class="mono" rows="2" bind:value={outputFolder} disabled={busy}></textarea>
      {#if progress.status!=='idle'}
        <div class="progress-box" role="status" aria-live="polite">
          <strong>{progress.status==='cancelling'?'正在停止，请稍候…':jobStates[progress.status] || stages[progress.stage || ''] || '正在处理'}</strong>
          <div>已用时间：{progress.elapsed.toFixed(1)} 秒</div>
          {#if progress.batchMode}
            <div>文件进度：{progress.fileCompleted || 0} / {progress.fileTotal}；成功 {progress.fileSucceeded || 0}，失败 {progress.fileFailed || 0}</div>
            <progress aria-label="批量文件处理进度" max={progress.fileTotal || 1} value={progress.fileCompleted || 0}></progress>
            {#if busy}<div>当前第 {progress.fileIndex || 1} 个文件</div>{/if}
          {/if}
          {#if progress.total}<div>章节进度：{progress.completed || 0} / {progress.total}；当前第 {progress.index} 章</div><progress aria-label="章节处理进度" max={progress.total} value={progress.completed || 0}></progress>{:else if busy}<progress aria-label="正在检查文件"></progress>{/if}
          {#if progress.chapter}<div class="dest-text">当前章节：{progress.chapter}</div>{/if}
          {#if progress.currentFile}<div class="dest-text">当前文件：{progress.currentFile}</div>{/if}
          {#if progress.logPath}<div class="dest-text">处理日志：{progress.logPath}</div>{/if}
        </div>
      {/if}
      {#if result}
        <div class="result-box" class:ok={result.success} class:err={!!result.error || !!(result.batch && progress.fileFailed)}>
          {#if result.error}<p>{result.error}</p>{#if result.logPath}<div class="dest-text">处理日志：{result.logPath}</div>{/if}
          {:else if result.batch}<p>{result.message}</p>
          {:else}<p>{result.message}</p><strong>输出文件完整路径：</strong><div class="dest-text mono">{result.destination}</div><button class="btn btn-secondary btn-sm" onclick={()=>copyPath()}>复制完整路径</button>
            {#if result.report}<div class="dest-text">处理报告：{result.report.report_path}</div><div class="dest-text">处理日志：{result.report.log_path}</div>{/if}
          {/if}
        </div>
      {/if}
      {#if progress.batchMode && progress.files?.length}
        <section class="batch-results" aria-label="批量处理结果">
          <div class="path-heading"><strong>逐个文件的处理结果</strong><button class="btn btn-secondary btn-sm" disabled={!outputPaths.length} onclick={()=>copyPath(outputPaths.join('\n'))}>复制全部输出路径</button></div>
          <ol>
            {#each progress.files as file}
              <li class="file-result" class:file-failed={file.status==='failed'}>
                <div class="file-state">{fileStates[file.status] || file.status}</div>
                <div class="dest-text mono">{file.source}</div>
                {#if file.destination}<strong>输出文件完整路径：</strong><div class="dest-text mono output-path">{file.destination}</div><button class="btn btn-secondary btn-sm" onclick={()=>copyPath(file.destination)}>复制完整路径</button>{/if}
                {#if file.error}<p class="dest-text">{file.error}</p>{/if}
                {#if file.logPath}<div class="dest-text">处理日志：{file.logPath}</div>{/if}
                {#if file.reportPath}<div class="dest-text">处理报告：{file.reportPath}</div>{/if}
              </li>
            {/each}
          </ol>
        </section>
      {/if}
    </div>
    <div class="modal-footer">{#if busy}<span>关闭窗口后仍会继续处理，可重新打开查看。</span><button class="btn btn-danger" disabled={starting || progress.status==='cancelling'} onclick={stop}>停止处理</button>{:else}<button class="btn btn-primary" onclick={start} disabled={!selectedPaths.length || choosing}>{selectedPaths.length>1?`批量补齐定义（${selectedPaths.length} 个文件）`:'立即补齐定义'}</button>{/if}</div>
  </div>
</div>

<style>
  .input-help {margin:0;font-size:12px;overflow-wrap:anywhere;}
  .batch-results {min-width:0;}
  .batch-results ol {margin:8px 0 0;padding-left:24px;}
  .file-result {padding:10px;margin:8px 0;border:1px solid var(--border-normal);border-radius:6px;min-width:0;background:var(--bg-raised);}
  .file-failed {border-color:var(--status-danger-text);}
  .file-state {font-weight:600;}
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
