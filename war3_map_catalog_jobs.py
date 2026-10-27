"""Background offline scans with bounded catalogue queries and stable job IDs."""
from copy import deepcopy
import json,threading,time,uuid
from war3_services.map_catalog import scan_map_catalog,filter_rows,export_catalog


class CatalogReadNotice(RuntimeError):
    def __init__(self,issues):
        super().__init__('部分目录字段未能完整读取；其他条目已保留，可以继续检索和导出。\n'+json.dumps(issues,ensure_ascii=False))
        self.user_details=deepcopy(issues)
        self.user_title='目录读取完成，部分字段需要注意'


class MapCatalogJobs:
    def __init__(self,launch,on_error):
        self.launch,self.on_error=launch,on_error
        self.lock=threading.RLock();self.job=None;self.result=None;self.search_index={};self.cancel_event=threading.Event()

    def start(self,source):
        with self.lock:
            if self.job and self.job['status'] in ('running','cancelling'):raise ValueError('正在读取地图目录，请先停止或等待完成。')
            identity=uuid.uuid4().hex;cancel=threading.Event();self.cancel_event=cancel;self.result=None;self.search_index={}
            self.job=dict(jobId=identity,status='running',stage='queued',source=str(source),scope='',file='',index=0,total=0,
                started=time.monotonic(),ended=None,error='',counts={},scopes=[],warnings=[],rowCount=0)
        def progress(stage,data):
            with self.lock:
                if self.job['jobId']==identity:self.job.update(stage=stage,**data)
        def work():
            try:
                result=scan_map_catalog(source,progress=progress,cancel=cancel)
                search_index={row['id']:(' '.join(str(row[k]) for k in ('rawcode','base','name','description','scope'))+' '+' '.join(row.get('heroNames',[]))+' '+json.dumps(row['changes'],ensure_ascii=False)).casefold() for row in result['rows']}
                with self.lock:
                    self.result=result;self.search_index=search_index;self.job.update(status='succeeded' if result['complete'] else 'partial',
                        stage='complete',counts=result['counts'],scopes=result['scopes'],warnings=result['warnings'],
                        diagnostics=result.get('diagnostics',[]),
                        rowCount=len(result['rows']),sourceSha256=result['sourceSha256'],notice=result['notice'])
                if not result['complete']:
                    self.on_error(CatalogReadNotice(result['warnings']))
            except InterruptedError as exc:
                with self.lock:
                    if self.job['jobId']==identity:self.job.update(status='cancelled',error=str(exc))
            except Exception as exc:
                with self.lock:
                    if self.job['jobId']==identity:self.job.update(status='failed',error=str(exc))
                self.on_error(exc)
            finally:
                with self.lock:
                    if self.job['jobId']==identity:self.job['ended']=time.monotonic()
        try:self.launch(work,'map-object-catalog')
        except Exception:
            with self.lock:self.job.update(status='failed',ended=time.monotonic())
            raise
        return dict(success=True,jobId=identity)

    def snapshot(self,identity=''):
        with self.lock:
            if not self.job:return dict(status='idle',jobId='',elapsed=0)
            if identity and identity!=self.job['jobId']:raise ValueError('目录已重新读取，请刷新列表。')
            value=deepcopy(self.job)
        value['elapsed']=round((value.pop('ended') or time.monotonic())-value.pop('started'),1)
        return value

    def cancel(self,identity=''):
        with self.lock:
            if self.job and (not identity or identity==self.job['jobId']) and self.job['status'] in ('running','cancelling'):
                self.cancel_event.set();self.job['status']='cancelling'
        return dict(success=True)

    def _result(self,identity):
        if not self.job or identity!=self.job['jobId'] or self.result is None:raise ValueError('请先读取地图目录；重新读取后请使用新目录。')
        return self.result

    def search(self,identity,kind='',query='',scope='',change_type='',offset=0,limit=100):
        if not isinstance(offset,int) or offset<0 or not isinstance(limit,int) or not 1<=limit<=200:raise ValueError('目录分页参数无效。')
        with self.lock:result=self._result(identity);search_index=self.search_index
        matches=list(filter_rows(result,kind,query,scope,change_type,search_index))
        rows=[{k:v for k,v in row.items() if k!='changes'} for row in matches[offset:offset+limit]]
        return dict(success=True,jobId=identity,rows=rows,matchCount=len(matches),totalCount=len(result['rows']),offset=offset)

    def detail(self,identity,row_id):
        with self.lock:
            result=self._result(identity)
            try:row=result['rows'][int(row_id)]
            except (ValueError,TypeError,IndexError):raise ValueError('目录条目已失效，请重新选择。')
            if row['id']!=str(row_id):raise ValueError('目录条目编号无效。')
            return deepcopy(row)

    def export(self,identity,path,kind='',query='',scope='',change_type=''):
        with self.lock:result=self._result(identity)
        path,count=export_catalog(path,result,kind=kind,query=query,scope=scope,change_type=change_type)
        return dict(success=True,path=path,count=count)
