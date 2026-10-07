"""Current-build hero batches, with no historical helper or analysis-script dependency."""
import json,os,sys,threading,time,struct
from pathlib import Path
from war3_object_registry import ObjectRegistry24268
from war3_thread_context import GameThreadContext24268
from war3_native_table import NativeTable24268
from war3_native_preflight import inspect_entries
from war3_selection_protocol import SIGNATURES
from war3_hero_protocol import SIGNATURES as HERO_SIGNATURES, build_work,decode_work
from war3_engine_transport import dispatch
from war3_game_session import GameSession, session_scope
from war3_game_profile import profile_scope
from war3_capabilities import CapabilitySet


_CURRENT_BRIDGE_FILENAMES = (
    'war3_bridge_24268.dll',
)


def classify_direct_cast_failure(kind, evidence, raw_result):
    """Classify a finished direct-cast callback without hiding unsafe states."""
    if kind != 'direct_cast' or len(raw_result) != 824:
        return None
    direct_error = struct.unpack_from('<I', raw_result, 728)[0]
    direct_completed = struct.unpack_from('<I', raw_result, 732)[0]
    direct_cleanup = struct.unpack_from('<I', raw_result, 820)[0]
    transport_released = all((
        evidence.get('callback_verified'),
        evidence.get('callback_exited'),
        evidence.get('work_freed'),
        evidence.get('block_freed'),
        evidence.get('image_unmap_status') == '0x0',
    ))
    if not direct_error or direct_completed or not transport_released:
        return None
    return {
        'error': direct_error,
        'completed': direct_completed,
        'cleanup': direct_cleanup,
        'session_continuable': direct_cleanup == 0,
    }


def _default_bridge_image():
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
    if not hasattr(sys,'_MEIPASS'):
        development = root / 'build' / 'architecture-runtime' / 'war3_bridge_24268.dll'
        if development.is_file():return development
    for filename in _CURRENT_BRIDGE_FILENAMES:
        candidate = root / 'tools' / filename
        if candidate.is_file():
            return candidate
    raise RuntimeError(
        'The validated 24268 bridge is missing from the executable bundle: '
        + str(root / 'tools' / _CURRENT_BRIDGE_FILENAMES[0])
    )

class EngineExecutionError(RuntimeError):
    def __init__(self,message,report):
        self.report=report
        dispatch=report.get('dispatch',{})
        state=dispatch.get('after_send') or dispatch.get('after_cleanup') or dispatch.get('after_install') or {}
        retry=dispatch.get('same_route_retry',{})
        attempts=int(dispatch.get('route_attempt') or 1)
        super().__init__(message+'; engine24268='+json.dumps(dict(
            pid=report.get('pid'),
            game_pid=report.get('pid'), target_game_pid=report.get('pid'),
            target_window_hwnd=report.get('hwnd'),
            trainer_pid=report.get('trainer_pid', os.getpid()),
            phase=state.get('query_stage'), install_stage=state.get('stage'),
            exception=state.get('exception_code'),
            retained=dispatch.get('allocations_retained',False),
            route=dispatch.get('image_route'), route_attempt=attempts,
            route_policy=dispatch.get('route_policy'),
            hook_kind=dispatch.get('hook_kind'),
            hook_install_api=dispatch.get('hook_install_api'),
            callback_received=dispatch.get('callback_received'),
            callback_exited=dispatch.get('callback_exited'),
            cleanup_verified=dispatch.get('cleanup_verified'),
            callback_lifecycle=dispatch.get('callback_lifecycle'),
            message_delivery=dispatch.get('message_delivery'),
            hwnd=dispatch.get('hwnd'),
            expected_callback_tid=dispatch.get('expected_callback_tid'),
            transport_error=dispatch.get('error'),
            same_route_retry=retry,
            ability_status=report.get('ability_status'),item_status=report.get('item_status'),
            equipment_status=report.get('equipment_status'),
            clone_status=report.get('clone_status'),world_status=report.get('world_status'),
            spawn_status=report.get('spawn_status'),
            attack_speed_status=report.get('attack_speed_status'),
            world_cast_status=report.get('world_cast_status'),
            ),ensure_ascii=False))

from war3_services.units import UnitsService
from war3_services.abilities import AbilitiesService
from war3_services.items import ItemsService
from war3_services.extensions import ExtensionsService
from war3_services.world import WorldService

class Engine24268(UnitsService, AbilitiesService, ItemsService, ExtensionsService, WorldService):
    def __init__(self,pid,hwnd,memory_factory,image=None,report_sink=None,session=None,diagnostic=False):
        self.pid,self.hwnd,self.memory_factory=pid,hwnd,memory_factory
        self.report_sink=report_sink
        self.diagnostic=diagnostic
        self.image=Path(image) if image is not None else _default_bridge_image()
        self.lock=threading.RLock();self.last_report={};self.quarantined=False
        self._native_context_cache = None
        self._owns_session = session is None
        self.session = session or GameSession(pid,hwnd)
        self.lock = self.session.lock
        self.session.on_invalidate(self._invalidate_context)

    def _invalidate_context(self,reason):
        self._native_context_cache = None
        self.quarantined = bool(self.session.uncertain or self.session.retained)

    def close(self):
        if self._owns_session:return self.session.close()
        return {'closed':True,'retained':bool(self.session.retained),'uncertain':self.session.uncertain}

    def __del__(self):
        pass


    def _execute(self,kind,names,builder,decoder,request):
        from war3_operations import OPERATIONS
        operation=OPERATIONS.get(kind)
        if operation is None or operation.diagnostic and not self.diagnostic:
            raise ValueError('Unknown or diagnostic-only operation: '+kind)
        with self.lock:
            try:
                if self.quarantined or self.session.closed or self.session.uncertain or self.session.retained:
                    raise RuntimeError('Previous dispatch retained resources or execution unresolved; no automatic replay')
                if not self.image.is_file():raise RuntimeError('Missing current 24268 bridge module: '+str(self.image))
                with self.memory_factory(self.pid) as memory:
                    self.session.prepare(memory)
                self.session.require_write()
                if getattr(self.session,'native_registry_error',None):
                    raise RuntimeError('Native execution unavailable: '+self.session.native_registry_error)
                with session_scope(self.session):
                    CapabilitySet(self.session.profile).require(kind,request=request)
                    return self._execute_prepared(kind,names,builder,decoder,request)
            except EngineExecutionError:raise
            except Exception as exc:
                report={'pid':self.pid,'operation':kind,'ok':False,'error':str(exc),'dispatch':{},'session':self.session.snapshot()}
                self.last_report=report
                raise EngineExecutionError(str(exc),report) from exc

    def _execute_prepared(self,kind,names,builder,decoder,request):
        with self.lock:
            if self.quarantined:raise EngineExecutionError('Previous dispatch retained resources; inspect before reconnecting',self.last_report)
            start=time.perf_counter();report={
                'pid':self.pid, 'game_pid':self.pid,
                'target_game_pid':self.pid, 'trainer_pid':os.getpid(),
                'hwnd':self.hwnd, 'operation':kind, 'request':request, 'ok':False,
            };self.last_report=report
            try:
                from war3_integrity import require_matching_integrity
                report['integrity'] = require_matching_integrity(self.pid)
                if not self.image.is_file():raise RuntimeError('Missing current 24268 bridge module: '+str(self.image))
                with self.memory_factory(self.pid) as memory:
                    cache=self.session.cache.get('natives')
                    cache_hit=False
                    if cache is not None:
                        try:
                            context=cache['context']
                            registry=cache['registry']
                            mode=context.read_mode(memory)
                            context5=memory.read_u64(mode.tls+self.session.profile.section('context')['native_slot'])
                            if (mode.value != cache['mode'].value or mode.tls != cache['mode'].tls
                                    or context5 != cache['context5']):
                                cache=None
                            else:
                                cache_hit=True
                        except Exception:
                            cache=None
                    if cache is None:
                        registry,context,mode=self.session.prepare(memory)
                        context5=memory.read_u64(mode.tls+self.session.profile.section('context')['native_slot'])
                        native_table=NativeTable24268(memory,context5)
                        cache={
                            'context': context,
                            'registry': registry,
                            'mode': mode,
                            'context5': context5,
                            'entries': native_table.entries,
                        }
                        self._native_context_cache=cache
                        self.session.cache['natives']=cache
                    registry.local_player_for_mode(memory,mode.value)
                    all_entries=cache['entries']
                    missing=[name for name in names if name not in all_entries]
                    if missing:
                        raise RuntimeError('Missing native registrations: '+', '.join(missing))
                    entries={name: all_entries[name] for name in names}
                    if cache_hit:
                        from war3_native_table import validate_cached_entries
                        validate_cached_entries(memory,entries)
                    report['preflight_cached']=cache_hit
                    if kind in ('effect', 'world_effect'):
                        # The effect bridge uses this slot as the verified game
                        # module base for its in-process object-table resolver.
                        self._effect_resolver = registry.base
                        if kind == 'effect':
                            from war3_classic_selection import read_player_selection
                            player = registry.local_player_for_mode(memory, mode.value)
                            classic_selection = read_player_selection(memory, player)
                            self._effect_unit_map = tuple(
                                (memory.read_u64(unit + registry.layout['object_handle']), memory.read_u32(unit + registry.layout['object_rawcode']))
                                for unit in classic_selection.units
                            )
                        payload=builder(entries,mode.tls)
                    elif kind == 'attack_speed':
                        self._attack_speed_module_base = registry.base
                        payload=builder(entries,mode.tls)
                    elif kind == 'extension':
                        self._extension_resolver = registry.base
                        payload=builder(entries,mode.tls)
                    elif kind == 'equipment_probe':
                        self._extension_resolver = registry.base
                        payload=builder(entries,mode.tls)
                    elif kind == 'stat_details':
                        self._stat_resolver_base = registry.base
                        payload=builder(entries,mode.tls)
                    else:
                        payload=builder(entries,mode.tls)
                    report['mappings']=({} if cache_hit else inspect_entries(memory,registry.base,entries,True))
                    fresh=context.read_mode(memory)
                    if (fresh.tls!=mode.tls or fresh.value!=mode.value or memory.read_u64(fresh.tls+self.session.profile.section('context')['native_slot'])!=context5
                        or (not cache_hit and NativeTable24268(memory,context5).require(*names)!=entries)):
                        raise RuntimeError('Current native context changed; no hero batch dispatched')
                    report['preflight_ms']=(time.perf_counter()-start)*1000
                    # A single callback still processes the entire selected-unit
                    # batch. The hook itself is deliberately one-shot: a reused
                    # thread hook can remain installed after the game rebuilds
                    # its UI queue and then stall a later operation.
                    evidence=dispatch(
                        self.pid,self.hwnd,mode.thread_id,self.image,
                        mode.tls_index,payload,kind=kind,
                    )
                    report['dispatch']=evidence;self.quarantined=bool(evidence.get('allocations_retained'))
                    report['verification']=vars(self.session.finish(evidence))
                    report['adapter']={'id':self.session.profile.id,'digest':self.session.profile.digest,'epoch':self.session.epoch}
                    from war3_operation_reports import record_status
                    record_status(kind,evidence,report)
                    released_ok = (
                        not self.session.last_evidence.uncertain
                        and evidence.get('callback_verified')
                        and evidence.get('query_completed')
                        and evidence.get('work_freed')
                        and evidence.get('block_freed')
                        and evidence.get('image_unmap_status') == '0x0'
                        and evidence.get('after_send',{}).get('tls_value') == hex(mode.tls)
                    )
                    if not released_ok:
                        dispatch_report=report.get('dispatch',{})
                        attempts=int(dispatch_report.get('route_attempt') or 1)
                        retry=dispatch_report.get('same_route_retry',{})
                        if retry.get('attempted'):
                            message=f'Current-engine batch execution or cleanup failed after compatibility fallback ({attempts} route attempts)'
                        else:
                            message=f'Current-engine batch execution or cleanup failed ({attempts} route attempt)'
                        raise EngineExecutionError(message,report)
                    try:
                        result=decoder(bytes.fromhex(evidence['work_result_hex']),int(evidence['after_send']['query_result'],16))
                    except Exception:
                        # A completed callback only proves the bridge transaction
                        # ended.  A direct-cast business rejection is different
                        # from an unresolved bridge/resource state: the native
                        # callback reports its own cleanup word, so allow later
                        # independent operations when that word is zero and the
                        # transport lifecycle is fully released.
                        raw_result=bytes.fromhex(evidence.get('work_result_hex',''))
                        business_status=classify_direct_cast_failure(kind,evidence,raw_result)
                        if kind == 'equipment_effect':
                            from war3_equipment_effect_protocol import failure_status
                            business_status=failure_status(raw_result)
                        elif kind == 'item_safety':
                            from war3_item_safety_protocol import failure_status
                            business_status=failure_status(raw_result)
                        elif kind == 'stat_details':
                            from war3_stat_details_protocol import failure_status
                            business_status=failure_status(raw_result)
                        if business_status and business_status['session_continuable']:
                            report['business_status']=business_status
                            raise
                        if business_status:
                            report['business_status']=business_status
                        # Completed callback is not proof that a partially
                        # applied transaction is replayable.
                        statuses=[value for key,value in report.items() if key.endswith('_status') and isinstance(value,dict)]
                        proven_no_change=bool(statuses) and all(value.get('changed')==0 for value in statuses)
                        if not proven_no_change:
                            self.session.uncertain=True
                            self.session.last_evidence.uncertain=True
                            report['verification']=vars(self.session.last_evidence)
                        raise
                    report['result']=result;report['ok']=True
                    # Protocol decoding validates the declared postconditions; gameplay is a separate test.
                    from war3_operations import OPERATIONS
                    report['verification']=vars(self.session.finish(evidence,readback=OPERATIONS[kind].readback))
                    if evidence.get('recovered_tail_faults') and self.report_sink is not None:
                        try:report['recovery_log']=self.report_sink(report)
                        except Exception as exc:
                            raise EngineExecutionError('Operation verified but recovery log failed; do not repeat the write',report) from exc
                    return result
            except EngineExecutionError:
                self._native_context_cache=None
                self.session.cache.pop('natives',None)
                raise
            except Exception as exc:
                self._native_context_cache=None
                self.session.cache.pop('natives',None)
                if isinstance(getattr(exc,'integrity_report',None),dict):
                    report['integrity']=exc.integrity_report
                report['error']=str(exc);raise EngineExecutionError(str(exc),report) from exc
            finally:report['elapsed_ms']=(time.perf_counter()-start)*1000
