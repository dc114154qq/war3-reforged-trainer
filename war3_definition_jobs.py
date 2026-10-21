"""Tracked offline archive work with independent progress and cancellation."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import threading,time,uuid


class DefinitionJobs:
    def __init__(self, prepare, launch, on_error=None):
        self.prepare,self.launch=prepare,launch
        self.on_error=on_error
        self.lock=threading.Lock()
        self.job=None
        self.cancel_event=None

    def start(self, source, folder=''):
        source=Path(str(source).strip().strip('"')).expanduser()
        folder=Path(str(folder).strip().strip('"')).expanduser() if str(folder).strip() else source.resolve().parent
        with self.lock:
            if self.job and self.job['status'] in ('running','cancelling'):
                raise ValueError('正在处理另一份地图，请等待完成或先停止。')
            job_id=uuid.uuid4().hex
            self.cancel_event=threading.Event();cancel=self.cancel_event
            started=time.monotonic()
            self.job=dict(jobId=job_id,status='running',stage='queued',chapter='',index=0,total=0,
                          completed=0,currentFile=str(source),started=started,ended=None,result=None,error='',logPath='')

        def progress(stage,data):
            with self.lock:
                job=self.job
                if job['jobId']!=job_id:return
                job['stage']=stage
                if data.get('log_path'):job['logPath']=data['log_path']
                if stage=='chapter_begin':
                    job.update(index=data['index'],total=data['total'],chapter=data['name'],currentFile=data['name'])
                if stage=='chapter_verified':job['completed']=job['index']
                if data.get('path'):job['currentFile']=data['path']
                elif data.get('name'):job['currentFile']=data['name']
        def worker():
            try:
                result=self.prepare(source,folder,progress=progress,cancel=cancel)
                payload=dict(success=True,destination=result.output,report=asdict(result),
                    message=f'文件校验完成：共 {result.chapter_count} 个章节，补齐 {result.changed_chapters} 个章节。请使用新副本重新进入地图。')
                with self.lock:self.job.update(status='succeeded',stage='complete',result=payload,logPath=result.log_path)
            except Exception as exc:
                from war3_error_messages import format_error
                if not cancel.is_set() and self.on_error:self.on_error(exc)
                with self.lock:self.job.update(status='cancelled' if cancel.is_set() else 'failed',
                    error=format_error(exc),logPath=str(getattr(exc,'diagnostic_log_path','')))
            finally:
                with self.lock:self.job['ended']=time.monotonic()
        try:self.launch(worker,'backpack-definition-files')
        except Exception:
            with self.lock:self.job.update(status='failed',ended=time.monotonic())
            raise
        return dict(success=True,jobId=job_id)

    def snapshot(self, job_id=''):
        with self.lock:
            if not self.job:return dict(status='idle',jobId='',elapsed=0)
            if job_id and job_id!=self.job['jobId']:
                raise ValueError('这次处理记录已更新，请重新打开处理窗口。')
            result=deepcopy(self.job)
        result['elapsed']=round((result.pop('ended') or time.monotonic())-result.pop('started'),1)
        return result

    def cancel(self,job_id=''):
        with self.lock:
            if self.job and (not job_id or self.job['jobId']==job_id) and self.job['status'] in ('running','cancelling'):
                self.cancel_event.set();self.job['status']='cancelling'
        return dict(success=True)
