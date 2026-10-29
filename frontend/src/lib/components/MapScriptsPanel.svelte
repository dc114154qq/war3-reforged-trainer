<script lang="ts">
  import { onMount,onDestroy } from 'svelte';
  import { api,type MapScriptOptions,type MapScriptProgress } from '../api';
  let paths=$state('');
  let folder=$state('');
  let options=$state<MapScriptOptions>({prefix:'-mx',features:['resources','hero','units','abilities','items','automatic','world'],artifact_codes:['klmm','srtl','shdt','crdt','frhg','nspi'],resource_amount:10000});
  let saving=$state(false);
  let saved=$state(false);
  let progress=$state<MapScriptProgress>({status:'idle',jobId:'',elapsed:0});
  let starting=$state(false);
  let choosing=$state(false);
  let disposed=false;
  let timer:ReturnType<typeof setTimeout>;
  const selected=$derived(paths.split(/\r?\n/).map(x=>x.trim().replace(/^"(.*)"$/,'$1')).filter(Boolean));
  const busy=$derived(starting || ['running','cancelling'].includes(progress.status));
  const menus=[['原版菜单与按键','保留资源、自动化、单位属性、个人设置、玩家管理和帮助'],['原主菜单翻页','直接在火龙原主菜单增加功能，每页最多6项；没有另一个增强主菜单'],['地图目录','物品、技能、单位召唤与科技，包含当前章节的自定义内容'],['物品与英雄','六神器方案、具体物品槽操作、英雄成长与批量修改'],['传送与资源','位置标记、返回上次位置、部队集合、资源最低值与金矿金额'],['自动项与结果','绑定启用时的选择，血魔阈值、停止开关、收藏与执行结果']];
  const stages:Record<string,string>={queued:'准备处理',source_hash_begin:'核对输入文件',start:'复制并保留原文件',definitions_begin:'补齐3.0背包定义',definitions_complete:'背包定义补齐完成',catalogue_begin:'读取当前地图定义',script_baseline_check:'检查原始脚本',script_compile:'检查加入后的脚本',script_write:'写入功能脚本',chapter_begin:'处理章节',chapter_verified:'章节校验完成',archive_verify:'独立读回归档',verify_member:'核对原有文件',replace_chapter:'保存战役章节',verified:'完成最终校验',complete:'处理结束'};
  const states:Record<string,string>={succeeded:'处理完成',failed:'处理失败',partial:'部分文件处理失败',cancelled:'处理已停止，成功的副本已保留',queued:'等待处理',running:'正在处理',skipped:'尚未处理'};
  const stage=$derived(progress.stage?.startsWith('definitions_')?'补齐3.0背包定义':progress.stage?.startsWith('catalogue_')?'读取当前地图定义':stages[progress.stage || ''] || '正在检查文件');
  async function poll(id=''){
    try {progress=await api.getMapScriptProgress(id);}
    catch {/* The shared API presents errors. */}
    finally {if(!disposed && ['running','cancelling'].includes(progress.status))timer=setTimeout(()=>poll(progress.jobId),300);}
  }
  async function choose(output=false){
    choosing=true;
    try {if(output){const r=await api.chooseDefinitionFolder();if(r.path)folder=r.path;}else{const r=await api.chooseDefinitionFiles();if(r.paths?.length)paths=r.paths.join('\n');}}
    finally {choosing=false;}
  }
  async function start(combined=false){
    starting=true;clearTimeout(timer);
    try {const r=await api.startMapScripts(selected,folder,options,combined);if(r.success)await poll(r.jobId);}
    finally {starting=false;}
  }
  async function stop(){const r=await api.cancelMapScripts(progress.jobId);if(r.success)progress.status='cancelling';}
  async function savePlan(){saving=true;saved=false;try{const r=await api.saveMapScriptOptions(options);if(r.success){options=r.options;saved=true;}}finally{saving=false;}}
  async function copy(text:string){try {await navigator.clipboard.writeText(text);}catch {window.dispatchEvent(new CustomEvent('war3-error',{detail:'复制失败，请选中完整路径后复制。'}));}}
  onMount(()=>{poll();api.getMapScriptOptions().then(r=>{if(!disposed && r.success)options=r.options;}).catch(()=>{});});
  onDestroy(()=>{disposed=true;clearTimeout(timer);});
</script>

<div class="map-scripts">
  <header><h2>经典版火龙修改器</h2><span class="tag">HKE 1.25B · 无需启动游戏</span></header>
  <p class="intro">把功能写进地图或战役副本。处理后可以关闭修改器，在游戏里用菜单或命令独立操作。原文件保留。</p>
  <p class="scope">支持本地单人 JASS 地图／战役；Lua 暂不支持。3.0 背包继续使用原有专用功能，本脚本不接管背包或扩展装备。</p>
  <section class="activation"><strong>进入副本后，依次按 ↑、↑、←、↓ 激活</strong><p>激活后先按 ↑ 再按 Esc（1 秒内）呼出主菜单。先按 ↑ 再双击单位可呼出单位菜单。</p><p>输入 <code>-h</code> 看键盘帮助，<code>-c</code> 看命令帮助，<code>-u</code> 看单位命令。</p></section>
  <fieldset disabled={busy || choosing}>
    <div class="path-heading"><label for="script-paths">地图／战役完整路径（每行一个）</label><button class="btn btn-secondary" onclick={()=>choose()}>选择文件（可多选）…</button></div>
    <textarea id="script-paths" rows="3" bind:value={paths} placeholder="支持 .w3n / .w3x / .w3m，每行一个完整路径"></textarea>
    <div class="path-heading"><label for="script-output">输出文件夹（留空则放在原文件旁边）</label><button class="btn btn-secondary" onclick={()=>choose(true)}>选择文件夹…</button></div>
    <textarea id="script-output" rows="2" bind:value={folder}></textarea>
    <section class="artifact-plan"><strong>火龙主菜单里的六神器方案</strong><p class="scope">填写6个普通物品代码，注入时一起写进地图。游戏内点“领取六神器方案”即可；满包不会删除原物品。保存后下次打开仍保留。</p><div class="artifact-codes">{#each options.artifact_codes as code,i}<label>第{i+1}件<input aria-label={`火龙神器代码${i+1}`} maxlength="4" bind:value={options.artifact_codes[i]} oninput={()=>saved=false} class="mono" /></label>{/each}</div><button class="btn btn-secondary" disabled={saving} onclick={savePlan}>{saving?'正在保存…':saved?'方案已保存':'保存六神器方案'}</button></section>
    <div class="feature-grid">{#each menus as [name,detail]}<article class="feature"><strong>{name}</strong><small>{detail}</small></article>{/each}</div>
  </fieldset>
  <div class="actions"><button class="btn btn-primary" data-action="scripts" disabled={busy || !selected.length} onclick={()=>start()}>注入火龙功能脚本</button><button class="btn btn-secondary" data-action="combined" disabled={busy || !selected.length} onclick={()=>start(true)}>补齐3.0背包定义并注入火龙</button>{#if busy}<button class="btn btn-danger" disabled={progress.status==='cancelling'} onclick={stop}>停止处理</button>{/if}</div>
  <p class="scope">组合按钮生成用于 3.0 的副本。已有背包定义会保留；单独注入火龙不需要 3.0。功能来自 HkeW3mModifier 2.06 附带的原版 HKE 1.25B，原作者为火龙 / WuHansen。</p>
  {#if progress.status!=='idle'}<section class="script-progress" aria-live="polite"><strong>{progress.status==='cancelling'?'正在停止，请稍候…':busy?stage:states[progress.status]}</strong><div>文件进度：{progress.fileCompleted || 0} / {progress.fileTotal || 0}；已用时间：{progress.elapsed.toFixed(1)} 秒</div><progress aria-label="脚本文件处理进度" max={progress.fileTotal || 1} value={progress.fileCompleted || 0}></progress>{#if busy && progress.total}<div>处理步骤：{progress.completed || 0} / {progress.total}；{progress.chapter}</div><progress aria-label="脚本章节处理进度" max={progress.total} value={progress.completed || 0}></progress>{/if}{#if busy}<div class="full-path">当前：{progress.currentFile}</div>{/if}{#if progress.logPath}<div class="full-path">处理日志：{progress.logPath}</div>{/if}</section>{/if}
  {#if progress.files?.length}<section class="script-results"><h3>逐文件结果与完整输出路径</h3>{#each progress.files as file}<article class:failed={file.status==='failed'}><div><strong>{states[file.status] || file.status}</strong><span class="full-path">{file.source}</span></div>{#if file.destination}<p class="result-note">功能脚本已写入副本，进入游戏后可独立使用。</p><div class="full-path output-path">{file.destination}</div><button class="btn btn-secondary" onclick={()=>copy(file.destination)}>复制输出路径</button>{#if file.usagePath}<div class="full-path">游戏内命令说明：{file.usagePath}</div><button class="btn btn-secondary" onclick={()=>copy(file.usagePath || '')}>复制说明路径</button>{/if}{/if}{#if file.error}<p class="failure-reason">{progress.failures?.find(x=>x.source===file.source)?.reason || file.error}</p>{/if}{#if file.logPath}<div class="full-path">处理日志：{file.logPath}</div>{/if}</article>{/each}</section>{/if}
  <details class="instructions"><summary>使用与兼容说明</summary><p>功能和参数随地图保存，游戏内操作不会请求修改器。旧存档不会自动得到新脚本，请从新副本的章节入口进入。</p><p>新增功能直接位于火龙原主菜单，用上一页／下一页切换。目录中可以搜索名称或代码，精确数值按游戏内提示输入；位置、收藏和最近记录限当前章节。不增加镜头设置、操作目标管理或单位信息页。</p><p>方向键、命令与原版正常功能保留。地图本身未定义的单位、技能或物品不能凭空补出；地图自身的触发器仍可能覆盖修改。目录在进入章节后分批准备。</p><p>已有 3.0 背包的单位会跳过火龙额外背包切换；3.0 背包控制能力与载体受到保护。其他功能也不复制 3.0 扩展槽、天赋及剧情私有状态。</p><p>兼容处理保留地图用于识别单位的数据，隔离脚本名称，并移除了旧脚本的隐藏接管命令和标题校验递归计时器。</p></details>
</div>

<style>
  .map-scripts{height:100%;overflow:auto;padding:20px;display:flex;flex-direction:column;gap:12px;color:var(--text-primary)}
  header,.path-heading,.actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap}header h2{font-size:18px;margin:0}.tag{font-size:11px;color:var(--text-secondary);border:1px solid var(--border-subtle);padding:3px 7px;border-radius:4px}
  p{margin:0;line-height:1.65}.intro{font-size:13px}.scope,.instructions{font-size:12px;color:var(--text-secondary)}
  fieldset{border:0;padding:0;margin:0;display:flex;flex-direction:column;gap:10px;min-width:0;flex-shrink:0}.path-heading{justify-content:space-between;font-size:12px}
  textarea{background:var(--bg-surface);color:var(--text-primary);border:1px solid var(--border-subtle);border-radius:4px;padding:7px;font:12px Consolas,'Microsoft YaHei',monospace;min-width:0;width:100%;box-sizing:border-box;resize:vertical;white-space:pre-wrap;overflow-wrap:anywhere}textarea:focus{outline:1px solid var(--border-focus)}
  .feature-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px}.feature{padding:10px;background:var(--bg-surface);border:1px solid var(--border-subtle);border-radius:4px;}.feature strong{font-size:12px}.feature small{display:block;font-size:11px;line-height:1.5;color:var(--text-secondary);margin-top:3px}.activation{flex-shrink:0;border:1px solid var(--border-gold);border-radius:5px;padding:12px;background:var(--bg-surface);font-size:12px;line-height:1.7}.activation strong{color:var(--text-gold)}code{font-family:Consolas,monospace;font-weight:700}
  .actions button{white-space:normal;height:auto;min-height:32px;line-height:1.45;padding:7px 12px}.script-progress,.script-results,.instructions{flex-shrink:0}.script-progress{padding:12px;border:1px solid var(--border-subtle);border-radius:4px;font-size:12px;display:flex;flex-direction:column;gap:7px}.script-progress progress{width:100%;height:8px}.full-path{overflow-wrap:anywhere;word-break:break-word;white-space:pre-wrap;user-select:text;font:12px/1.65 Consolas,'Microsoft YaHei',monospace}.script-results h3{font-size:14px;margin:0 0 8px}.script-results article{padding:12px;border:1px solid var(--border-subtle);background:var(--bg-surface);border-radius:4px;display:flex;flex-direction:column;gap:8px;margin-bottom:8px}.script-results article strong{display:block;margin-bottom:4px}.script-results button{align-self:flex-start}.result-note{font-size:12px}.output-path{border-left:3px solid #10b981;padding-left:8px}.failure-reason{color:var(--text-primary);background:var(--bg-surface-elevated);border-left:3px solid #ef4444;padding:10px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.instructions{padding-bottom:20px}.instructions summary{cursor:pointer;color:var(--text-primary)}.instructions p{margin-top:8px}
  .artifact-plan{padding:12px;border:1px solid var(--border-subtle);border-radius:4px;display:flex;flex-direction:column;gap:9px;font-size:12px}.artifact-plan button{align-self:flex-start}.artifact-codes{display:grid;grid-template-columns:repeat(auto-fit,minmax(95px,1fr));gap:8px}.artifact-codes label{display:flex;flex-direction:column;gap:5px;color:var(--text-secondary)}.artifact-codes input{width:100%;min-width:0;box-sizing:border-box;color:var(--text-primary);background:var(--bg-surface);border:1px solid var(--border-subtle);padding:7px;border-radius:4px}
  @media(max-width:900px){.map-scripts{padding:12px}.path-heading button{font-size:11px}}
</style>
