"""Current-build hero batches, with no historical helper or analysis-script dependency."""
import json,sys,threading,time
from pathlib import Path
from war3_object_registry import ObjectRegistry24268
from war3_thread_context import GameThreadContext24268
from war3_native_table import NativeTable24268
from war3_native_preflight import inspect_entries
from war3_selection_protocol import SIGNATURES
from war3_hero_protocol import build_work,decode_work
from war3_engine_transport import dispatch

class EngineExecutionError(RuntimeError):
    def __init__(self,message,report):
        self.report=report
        state=report.get('dispatch',{}).get('after_send',{})
        super().__init__(message+'; engine24268='+json.dumps(dict(pid=report.get('pid'),
            phase=state.get('query_stage'),exception=state.get('exception_code'),
            retained=report.get('dispatch',{}).get('allocations_retained',False)),ensure_ascii=False))

class Engine24268:
    def __init__(self,pid,hwnd,memory_factory,image=None):
        self.pid,self.hwnd,self.memory_factory=pid,hwnd,memory_factory
        self.image=Path(image) if image is not None else Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'tools/war3_bridge_24268.dll'
        self.lock=threading.RLock();self.last_report={};self.quarantined=False

    def hero_progress(self,target=0):
        if isinstance(target,bool) or not isinstance(target,int) or not 0<=target<=100000:
            raise ValueError('Hero level must be integer 1..100000; 0 means read-only query')
        with self.lock:
            if self.quarantined:raise EngineExecutionError('Previous dispatch retained resources; inspect before reconnecting',self.last_report)
            start=time.perf_counter();report={'pid':self.pid,'target':target,'ok':False};self.last_report=report
            try:
                if not self.image.is_file():raise RuntimeError('Missing current 24268 bridge module: '+str(self.image))
                with self.memory_factory(self.pid) as memory:
                    registry=ObjectRegistry24268.attach(memory)
                    context=GameThreadContext24268(memory,registry.base,self.hwnd,self.pid)
                    mode=context.read_mode(memory);registry.local_player_for_mode(memory,mode.value)
                    context5=memory.read_u64(mode.tls+0x38)
                    names=tuple(n for n,_ in SIGNATURES)+('SetHeroLevel',)
                    entries=NativeTable24268(memory,context5).require(*names)
                    payload=build_work(entries,mode.tls,target)
                    report['mappings']=inspect_entries(memory,registry.base,entries,True)
                    fresh=context.read_mode(memory)
                    if (fresh.tls!=mode.tls or fresh.value!=mode.value or memory.read_u64(fresh.tls+0x38)!=context5
                        or NativeTable24268(memory,context5).require(*names)!=entries):
                        raise RuntimeError('Current native context changed; no hero batch dispatched')
                    report['preflight_ms']=(time.perf_counter()-start)*1000
                    evidence=dispatch(self.pid,self.hwnd,mode.thread_id,self.image,mode.tls_index,payload)
                    report['dispatch']=evidence;self.quarantined=bool(evidence.get('allocations_retained'))
                    if not (evidence.get('callback_verified') and evidence.get('query_completed') and evidence.get('work_freed')
                        and evidence.get('block_freed') and evidence.get('image_unmap_status')=='0x0'
                        and evidence['after_send']['tls_value']==hex(mode.tls)):
                        raise EngineExecutionError('Hero batch execution or cleanup failed; not retried',report)
                    result=decode_work(bytes.fromhex(evidence['work_result_hex']),int(evidence['after_send']['query_result'],16))
                    report['result']=result;report['ok']=True;return result
            except EngineExecutionError:raise
            except Exception as exc:
                report['error']=str(exc);raise EngineExecutionError(str(exc),report) from exc
            finally:report['elapsed_ms']=(time.perf_counter()-start)*1000
