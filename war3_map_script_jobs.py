"""Independent offline script queues using the proven sequential file scheduler."""
from pathlib import Path
from copy import deepcopy
import threading
from war3_definition_jobs import DefinitionJobs
from war3_script_features import ScriptOptions
from war3_services.map_script_patch import prepare_map_script


class MapScriptJobs:
    def __init__(self, launch, on_error=None):
        self.launch, self.on_error = launch, on_error
        self.lock = threading.Lock()
        self.current = None
        self.failures = []

    def start(self, sources, folder='', options=None, combined=False):
        config = ScriptOptions.parse(options)
        if type(combined) is not bool:
            raise ValueError('组合处理选项无效。')
        failures = []
        def prepare(source, output, **kw):
            progress = kw['progress']
            definition_steps = 0
            def forward(stage, data):
                nonlocal definition_steps
                if combined and stage == 'definitions_chapter_begin':
                    definition_steps = data['total']
                    progress('chapter_begin', dict(data,total=2*definition_steps))
                elif combined and stage == 'definitions_chapter_verified':
                    progress('chapter_verified', data)
                elif combined and stage == 'chapter_begin':
                    progress(stage,dict(data,index=definition_steps+data['index'],total=definition_steps+data['total']))
                    return
                progress(stage,data)
            kw['progress'] = forward
            try:
                return prepare_map_script(source, output, options=config, combined=combined, **kw)
            except Exception as exc:
                failures.append(dict(source=str(source), reason=str(exc),
                    logPath=str(getattr(exc,'diagnostic_log_path','')),
                    details=deepcopy(getattr(exc,'user_details',[]))))
                raise
        def notify(exc):
            if self.on_error:
                error = RuntimeError('部分地图功能脚本未能完成，请查看具体文件和原因。')
                error.user_title = '地图功能脚本未能完成'
                error.user_details = [detail for failure in failures for detail in (
                    failure['details'] or [dict(scope=failure['source'],file='地图功能脚本',message=failure['reason'])])]
                error.diagnostic_log_path = next((f['logPath'] for f in failures if f['logPath']), '')
                self.on_error(error)
        with self.lock:
            if self.current and self.current.snapshot()['status'] in ('running','cancelling'):
                raise ValueError('地图脚本正在处理，请等待完成或先停止。')
            jobs = DefinitionJobs(prepare, self.launch, notify)
            started = jobs.start_batch(sources, folder)
            self.current = jobs
            self.failures = failures
        return started

    def snapshot(self, job_id=''):
        with self.lock:
            current = self.current
        if current is None:
            return dict(status='idle', jobId='', elapsed=0)
        state = current.snapshot(job_id)
        state['failures'] = deepcopy(self.failures)
        for row in state.get('files', ()):
            if row['status'] == 'succeeded':
                row['message'] = '功能脚本已写入副本，进入游戏后可独立使用。'
                row['usagePath'] = str(Path(row['reportPath']).parent/'游戏内功能使用说明.txt')
        result = state.get('result')
        if result:
            result['files'] = state['files']
            result['message'] = (f"地图功能处理结束：成功 {state['fileSucceeded']} 个，失败 {state['fileFailed']} 个。"
                '请使用成功副本进入游戏；通用功能无需修改器继续运行。')
        return state

    def cancel(self, job_id=''):
        with self.lock:
            current = self.current
        return current.cancel(job_id) if current else dict(success=True)
