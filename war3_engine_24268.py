"""Current-build hero batches, with no historical helper or analysis-script dependency."""
import json,sys,threading,time,struct
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
            retained=report.get('dispatch',{}).get('allocations_retained',False),
            ability_status=report.get('ability_status'),item_status=report.get('item_status')),ensure_ascii=False))

class Engine24268:
    def __init__(self,pid,hwnd,memory_factory,image=None,report_sink=None):
        self.pid,self.hwnd,self.memory_factory=pid,hwnd,memory_factory
        self.report_sink=report_sink
        self.image=Path(image) if image is not None else Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'tools/war3_bridge_24268.dll'
        self.lock=threading.RLock();self.last_report={};self.quarantined=False

    def hero_progress(self,target=0):
        if isinstance(target,bool) or not isinstance(target,int) or not 0<=target<=100000:
            raise ValueError('Hero level must be integer 1..100000; 0 means read-only query')
        names=tuple(n for n,_ in SIGNATURES)+('SetHeroLevel',)
        return self._execute('hero',names,lambda entries,tls:build_work(entries,tls,target),decode_work,dict(target=target))

    def ability_batch(self,rawcode,action=0,level=0):
        from war3_ability_protocol import SIGNATURES as ABILITIES,build_work as build,decode_work as decode
        if (isinstance(rawcode,bool) or not isinstance(rawcode,int) or not 0<rawcode<=0xffffffff
            or isinstance(action,bool) or not isinstance(action,int) or action not in range(5)
            or isinstance(level,bool) or not isinstance(level,int) or not 0<=level<=100000
            or (action in (3,4) and not level) or (action in (0,2) and level)):
            raise ValueError('Invalid current-engine ability operation')
        names=tuple(n for n,_ in SIGNATURES+ABILITIES)
        return self._execute('ability',names,lambda entries,tls:build(entries,tls,rawcode,action,level),decode,
                             dict(rawcode=rawcode,action=action,level=level))

    def item_batch(self,action=0,rawcode=0,charges=-1):
        from war3_item_protocol import SIGNATURES as ITEMS,build_work as build,decode_work as decode
        if any(isinstance(v,bool) or not isinstance(v,int) for v in (action,rawcode,charges)):
            raise ValueError('Item arguments must be integers')
        if (action not in (0,1,2,3) or not 0<=rawcode<=0xffffffff or (action in (1,3) and not rawcode)
            or (action in (0,2) and rawcode) or not -1<=charges<=1000000000
            or (action in (2,3) and charges<1) or (action==0 and charges!=-1)):
            raise ValueError('Invalid item operation')
        names=tuple(n for n,_ in SIGNATURES+ITEMS)
        return self._execute('item',names,lambda entries,tls:build(entries,tls,action,rawcode,charges),decode,
                             dict(action=action,rawcode=rawcode,charges=charges))

    def _execute(self,kind,names,builder,decoder,request):
        with self.lock:
            if self.quarantined:raise EngineExecutionError('Previous dispatch retained resources; inspect before reconnecting',self.last_report)
            start=time.perf_counter();report={'pid':self.pid,'operation':kind,'request':request,'ok':False};self.last_report=report
            try:
                if not self.image.is_file():raise RuntimeError('Missing current 24268 bridge module: '+str(self.image))
                with self.memory_factory(self.pid) as memory:
                    registry=ObjectRegistry24268.attach(memory)
                    context=GameThreadContext24268(memory,registry.base,self.hwnd,self.pid)
                    mode=context.read_mode(memory);registry.local_player_for_mode(memory,mode.value)
                    context5=memory.read_u64(mode.tls+0x38)
                    entries=NativeTable24268(memory,context5).require(*names)
                    payload=builder(entries,mode.tls)
                    report['mappings']=inspect_entries(memory,registry.base,entries,True)
                    fresh=context.read_mode(memory)
                    if (fresh.tls!=mode.tls or fresh.value!=mode.value or memory.read_u64(fresh.tls+0x38)!=context5
                        or NativeTable24268(memory,context5).require(*names)!=entries):
                        raise RuntimeError('Current native context changed; no hero batch dispatched')
                    report['preflight_ms']=(time.perf_counter()-start)*1000
                    evidence=dispatch(self.pid,self.hwnd,mode.thread_id,self.image,mode.tls_index,payload,kind=kind)
                    report['dispatch']=evidence;self.quarantined=bool(evidence.get('allocations_retained'))
                    if kind=='ability' and evidence.get('work_result_hex'):
                        raw=bytes.fromhex(evidence['work_result_hex'])
                        if len(raw)==832:
                            changed,error,completed=struct.unpack_from('<3I',raw,532)
                            report['ability_status']=dict(changed=changed,error=error,completed=completed)
                    if kind=='item' and evidence.get('work_result_hex'):
                        raw=bytes.fromhex(evidence['work_result_hex'])
                        if len(raw)==5960:
                            changed,error,completed,skipped=struct.unpack_from('<4I',raw,564)
                            report['item_status']=dict(changed=changed,error=error,completed=completed,skipped=skipped)
                    if not (evidence.get('callback_verified') and evidence.get('query_completed') and evidence.get('work_freed')
                        and evidence.get('block_freed') and evidence.get('image_unmap_status')=='0x0'
                        and evidence['after_send']['tls_value']==hex(mode.tls)):
                        raise EngineExecutionError('Current-engine batch execution or cleanup failed; not retried',report)
                    result=decoder(bytes.fromhex(evidence['work_result_hex']),int(evidence['after_send']['query_result'],16))
                    report['result']=result;report['ok']=True
                    if evidence.get('recovered_tail_faults') and self.report_sink is not None:
                        try:report['recovery_log']=self.report_sink(report)
                        except Exception as exc:
                            raise EngineExecutionError('Operation verified but recovery log failed; do not repeat the write',report) from exc
                    return result
            except EngineExecutionError:raise
            except Exception as exc:
                report['error']=str(exc);raise EngineExecutionError(str(exc),report) from exc
            finally:report['elapsed_ms']=(time.perf_counter()-start)*1000
