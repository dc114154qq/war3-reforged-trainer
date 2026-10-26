"""Tracked sequential archive jobs with per-file results and cancellation."""
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import os
import threading
import time
import uuid


def _sources(paths):
    if not isinstance(paths, (list, tuple)) or not 1 <= len(paths) <= 1000:
        raise ValueError('请选择 1 到 1000 个战役或地图文件。')
    result, seen = [], set()
    for value in paths:
        if not isinstance(value, str) or not value.strip().strip('"').strip():
            raise ValueError('文件路径不能为空。')
        path = Path(value.strip().strip('"')).expanduser().resolve()
        key = os.path.normcase(str(path))
        if key not in seen:
            result.append(path)
            seen.add(key)
    return result


class DefinitionJobs:
    def __init__(self, prepare, launch, on_error=None):
        self.prepare, self.launch, self.on_error = prepare, launch, on_error
        self.lock = threading.Lock()
        self.job = None
        self.cancel_event = None

    def start(self, source, folder=''):
        return self._start([str(source)], folder, batch=False)

    def start_batch(self, sources, folder=''):
        return self._start(sources, folder, batch=True)

    def _start(self, sources, folder, *, batch):
        paths = _sources(sources)
        output = Path(str(folder).strip().strip('"')).expanduser().resolve() if str(folder).strip() else None
        with self.lock:
            if self.job and self.job['status'] in ('running', 'cancelling'):
                raise ValueError('正在处理地图文件，请等待完成或先停止。')
            job_id = uuid.uuid4().hex
            self.cancel_event = threading.Event()
            cancel = self.cancel_event
            self.job = dict(jobId=job_id, status='running', stage='queued', chapter='', index=0, total=0,
                completed=0, currentFile=str(paths[0]), started=time.monotonic(), ended=None,
                result=None, error='', logPath='', batchMode=batch, outputFolder=str(output or ''),
                fileTotal=len(paths), fileIndex=0, fileCompleted=0, fileSucceeded=0, fileFailed=0,
                fileSkipped=0, files=[dict(source=str(path), status='queued', destination='',
                    message='', error='', logPath='', reportPath='') for path in paths])

        def progress(stage, data):
            with self.lock:
                job = self.job
                if job['jobId'] != job_id:
                    return
                job['stage'] = stage
                if data.get('log_path'):
                    job['logPath'] = data['log_path']
                    job['files'][job['fileIndex'] - 1]['logPath'] = data['log_path']
                if stage == 'chapter_begin':
                    job.update(index=data['index'], total=data['total'], chapter=data['name'], currentFile=data['name'])
                if stage == 'chapter_verified':
                    job['completed'] = job['index']
                if data.get('path'):
                    job['currentFile'] = data['path']
                elif data.get('name'):
                    job['currentFile'] = data['name']

        def notify(exc):
            if self.on_error:
                try:
                    self.on_error(exc)
                except Exception as notification_error:
                    with self.lock:
                        if self.job['jobId'] == job_id:
                            self.job['notificationError'] = str(notification_error)

        def worker():
            from war3_error_messages import format_error
            last_payload = None
            try:
                for file_index, source in enumerate(paths):
                    with self.lock:
                        if cancel.is_set():
                            break
                        item = self.job['files'][file_index]
                        item['status'] = 'running'
                        self.job.update(fileIndex=file_index + 1, stage='queued', chapter='', index=0,
                            total=0, completed=0, currentFile=str(source), logPath='')
                    try:
                        result = self.prepare(source, output or source.parent, progress=progress, cancel=cancel)
                        last_payload = dict(success=True, destination=result.output, report=asdict(result),
                            message=f'文件校验完成：共 {result.chapter_count} 个章节，补齐 {result.changed_chapters} 个章节。请使用新副本重新进入地图。')
                        # Keep completed outputs even when stop is pressed just
                        # after the archive service returns successfully.
                        with self.lock:
                            item.update(status='succeeded', destination=result.output, message=last_payload['message'],
                                logPath=result.log_path, reportPath=result.report_path)
                            self.job['fileSucceeded'] += 1
                            self.job['fileCompleted'] += 1
                            self.job['logPath'] = result.log_path
                    except Exception as exc:
                        with self.lock:
                            stopped = cancel.is_set()
                            item.update(status='cancelled' if stopped else 'failed', error=format_error(exc),
                                logPath=str(getattr(exc, 'diagnostic_log_path', '')) or item['logPath'])
                            self.job['logPath'] = item['logPath']
                            if not stopped:
                                self.job['fileFailed'] += 1
                                self.job['fileCompleted'] += 1
                        if not batch and not stopped:
                            notify(exc)
                        if stopped:
                            break
                with self.lock:
                    job = self.job
                    for item in job['files']:
                        if item['status'] == 'queued':
                            item.update(status='skipped', message='已停止，尚未处理。')
                            job['fileSkipped'] += 1
                    succeeded, failed = job['fileSucceeded'], job['fileFailed']
                    cancelled = cancel.is_set() and succeeded + failed < len(paths)
                    job['status'] = ('cancelled' if cancelled else 'partial' if succeeded and failed
                                     else 'failed' if failed else 'succeeded')
                    job['stage'] = 'complete'
                    if batch:
                        message = (f'批量处理结束：成功 {succeeded} 个，失败 {failed} 个，'
                                   f'未完成 {len(paths) - succeeded - failed} 个。成功的副本已保留，请查看下方输出路径。')
                        job['result'] = dict(success=not failed and not cancelled, batch=True, cancelled=cancelled,
                            message=message, files=deepcopy(job['files']))
                        job['error'] = message if failed else ''
                    elif succeeded:
                        job['result'] = last_payload
                    else:
                        job['error'] = job['files'][0]['error']
                if batch and failed:
                    # One summary popup; per-file errors stay in the results
                    # and cannot interrupt the remaining queue.
                    details = '\n'.join(f"{item['source']}：{item['error']}" for item in job['files'] if item['status'] == 'failed')
                    notify(RuntimeError(message + '\n' + details))
            except Exception as exc:
                with self.lock:
                    if self.job['jobId'] == job_id:
                        self.job.update(status='failed', error=format_error(exc))
                notify(exc)
            finally:
                with self.lock:
                    if self.job['jobId'] == job_id:
                        self.job['ended'] = time.monotonic()

        try:
            self.launch(worker, 'backpack-definition-files')
        except Exception:
            with self.lock:
                self.job.update(status='failed', ended=time.monotonic())
            raise
        return dict(success=True, jobId=job_id)

    def snapshot(self, job_id=''):
        with self.lock:
            if not self.job:
                return dict(status='idle', jobId='', elapsed=0)
            if job_id and job_id != self.job['jobId']:
                raise ValueError('这次处理记录已更新，请重新打开处理窗口。')
            result = deepcopy(self.job)
        result['elapsed'] = round((result.pop('ended') or time.monotonic()) - result.pop('started'), 1)
        return result

    def cancel(self, job_id=''):
        with self.lock:
            if self.job and (not job_id or self.job['jobId'] == job_id) and self.job['status'] in ('running', 'cancelling'):
                self.cancel_event.set()
                self.job['status'] = 'cancelling'
        return dict(success=True)
