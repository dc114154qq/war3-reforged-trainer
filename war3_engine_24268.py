"""Current-build hero batches, with no historical helper or analysis-script dependency."""
import json,sys,threading,time,struct
from pathlib import Path
from war3_object_registry import ObjectRegistry24268
from war3_thread_context import GameThreadContext24268
from war3_native_table import NativeTable24268
from war3_native_preflight import inspect_entries
from war3_selection_protocol import SIGNATURES
from war3_hero_protocol import SIGNATURES as HERO_SIGNATURES, build_work,decode_work
from war3_engine_transport import dispatch

class EngineExecutionError(RuntimeError):
    def __init__(self,message,report):
        self.report=report
        state=report.get('dispatch',{}).get('after_send',{})
        super().__init__(message+'; engine24268='+json.dumps(dict(pid=report.get('pid'),
            phase=state.get('query_stage'),exception=state.get('exception_code'),
            retained=report.get('dispatch',{}).get('allocations_retained',False),
            ability_status=report.get('ability_status'),item_status=report.get('item_status'),
            clone_status=report.get('clone_status'),world_status=report.get('world_status')),ensure_ascii=False))

class Engine24268:
    def __init__(self,pid,hwnd,memory_factory,image=None,report_sink=None):
        self.pid,self.hwnd,self.memory_factory=pid,hwnd,memory_factory
        self.report_sink=report_sink
        self.image=Path(image) if image is not None else Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))/'tools/war3_bridge_24268_current_r36.dll'
        self.lock=threading.RLock();self.last_report={};self.quarantined=False

    def hero_progress(self,target=0):
        if isinstance(target,bool) or not isinstance(target,int) or not 0<=target<=100000:
            raise ValueError('Hero level must be integer 1..100000; 0 means read-only query')
        names=tuple(n for n,_ in SIGNATURES)+tuple(n for n,_ in HERO_SIGNATURES)
        return self._execute('hero',names,lambda entries,tls:build_work(entries,tls,target),decode_work,dict(target=target))

    def ability_batch(self,rawcode,action=0,level=0):
        from war3_ability_protocol import SIGNATURES as ABILITIES,build_work as build,decode_work as decode
        if (isinstance(rawcode,bool) or not isinstance(rawcode,int) or not 0<rawcode<=0xffffffff
            or isinstance(action,bool) or not isinstance(action,int) or action not in range(6)
            or isinstance(level,bool) or not isinstance(level,int) or not 0<=level<=100000
            or (action in (3,4) and not level) or (action in (0,2,5) and level)):
            raise ValueError('Invalid current-engine ability operation')
        names=tuple(n for n,_ in SIGNATURES+ABILITIES)
        return self._execute('ability',names,lambda entries,tls:build(entries,tls,rawcode,action,level),decode,
                             dict(rawcode=rawcode,action=action,level=level))

    def ability_field_batch(self, rawcode, level, action, fields, target_unit=0):
        from war3_ability_field_protocol import (
            SIGNATURES as FIELD_SIGNATURES,
            build_work as build,
            decode_work as decode,
        )
        if (isinstance(rawcode, bool) or not isinstance(rawcode, int) or not 0 < rawcode <= 0xFFFFFFFF
                or isinstance(level, bool) or not isinstance(level, int) or not 1 <= level <= 1000
                or isinstance(action, bool) or action not in (0, 1)
                or isinstance(target_unit, bool) or not isinstance(target_unit, int)
                or not 0 <= target_unit <= 0xFFFFFFFFFFFFFFFF):
            raise ValueError('Invalid current-engine ability field operation')
        names = tuple(n for n, _ in SIGNATURES + FIELD_SIGNATURES)
        return self._execute(
            'ability_field',
            names,
            lambda entries, tls: build(
                entries, tls, rawcode, level, action, fields, target_unit,
            ),
            decode,
            dict(rawcode=rawcode, level=level, action=action,
                 field_count=len(fields), target_unit=target_unit),
        )

    def item_batch(self,action=0,rawcode=0,charges=-1):
        from war3_item_protocol import SIGNATURES as ITEMS,build_work as build,decode_work as decode
        if any(isinstance(v,bool) or not isinstance(v,int) for v in (action,rawcode,charges)):
            raise ValueError('Item arguments must be integers')
        if (action not in (0,1,2,3,4,5,6,7) or not 0<=rawcode<=0xffffffff or (action in (1,3,7) and not rawcode)
            or (action in (0,2,4,5,6) and rawcode) or not -1<=charges<=1000000000
            or (action in (2,3) and charges<1) or (action in (0,1,4,5,6) and charges!=-1)
            or (action==7 and not 0<=charges<6)):
            raise ValueError('Invalid item operation')
        from war3_item_protocol import required_signatures
        names=tuple(n for n,_ in SIGNATURES)+tuple(n for n,_ in required_signatures(action))
        return self._execute('item',names,lambda entries,tls:build(entries,tls,action,rawcode,charges),decode,
                             dict(action=action,rawcode=rawcode,charges=charges))

    def item_field_batch(self, slot, action, fields, target_unit=0):
        from war3_item_field_protocol import (
            SIGNATURES as FIELD_SIGNATURES,
            build_work as build,
            decode_work as decode,
        )
        if (isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot < 6
                or isinstance(action, bool) or action not in (0, 1)
                or isinstance(target_unit, bool) or not isinstance(target_unit, int)
                or not 0 <= target_unit <= 0xFFFFFFFFFFFFFFFF):
            raise ValueError('Invalid current-engine item field operation')
        names = tuple(n for n, _ in SIGNATURES + FIELD_SIGNATURES)
        return self._execute(
            'item_field',
            names,
            lambda entries, tls: build(entries, tls, slot, action, fields, target_unit),
            decode,
            dict(slot=slot, action=action, field_count=len(fields), target_unit=target_unit),
        )

    def clone_batch(self, *, keep=False, preserve_owner=False,
                    copy_abilities=True, copy_items=True,
                    spawn_x_bits=0, spawn_y_bits=0):
        from war3_clone_protocol import (
            SIGNATURES as CLONE_SIGNATURES,
            CLONE_COPY_ABILITIES, CLONE_COPY_ITEMS, CLONE_KEEP,
            CLONE_PRESERVE_OWNER, build_work as build, decode_work as decode,
        )
        flags = 0
        if keep: flags |= CLONE_KEEP
        if preserve_owner: flags |= CLONE_PRESERVE_OWNER
        if copy_abilities: flags |= CLONE_COPY_ABILITIES
        if copy_items: flags |= CLONE_COPY_ITEMS
        names = tuple(n for n, _ in SIGNATURES + CLONE_SIGNATURES)
        return self._execute(
            'clone', names,
            lambda entries, tls: build(entries, tls, flags=flags,
                                       spawn_x_bits=spawn_x_bits,
                                       spawn_y_bits=spawn_y_bits),
            decode,
            dict(keep=keep, preserve_owner=preserve_owner,
                 copy_abilities=copy_abilities, copy_items=copy_items),
        )

    def unit_action_batch(self, action, *, value=0, x_bits=0, y_bits=0,
                          scale_x_bits=0, scale_y_bits=0, scale_z_bits=0):
        from war3_unit_action_protocol import (
            ACTION_SIGNATURES, build_work as build, decode_work as decode,
        )
        if not isinstance(action, int) or isinstance(action, bool):
            raise ValueError('Invalid current-engine unit action')
        names = tuple(n for n, _ in SIGNATURES + ACTION_SIGNATURES)
        return self._execute(
            'unit_action', names,
            lambda entries, tls: build(
                entries, tls, action, value=value, x_bits=x_bits, y_bits=y_bits,
                scale_x_bits=scale_x_bits, scale_y_bits=scale_y_bits,
                scale_z_bits=scale_z_bits,
            ),
            decode,
            dict(action=action, value=value, x_bits=x_bits, y_bits=y_bits,
                 scale_x_bits=scale_x_bits, scale_y_bits=scale_y_bits,
                 scale_z_bits=scale_z_bits),
        )

    def position_batch(self, x_bits, y_bits):
        from war3_position_protocol import SIGNATURES as POSITION_SIGNATURES, build_work as build, decode_work as decode
        if (isinstance(x_bits, bool) or not isinstance(x_bits, int)
                or isinstance(y_bits, bool) or not isinstance(y_bits, int)):
            raise ValueError('Position bits must be integers')
        names = tuple(n for n, _ in SIGNATURES + POSITION_SIGNATURES)
        return self._execute(
            'position', names,
            lambda entries, tls: build(entries, tls, x_bits, y_bits),
            decode,
            dict(x_bits=x_bits, y_bits=y_bits),
        )

    def world_batch(self, action, rawcode=0, value=0):
        from war3_world_protocol import SIGNATURES as WORLD_SIGNATURES, build_work as build, decode_work as decode
        if (isinstance(action, bool) or not isinstance(action, int) or action not in range(1, 7)
                or isinstance(rawcode, bool) or not isinstance(rawcode, int) or not 0 <= rawcode <= 0xffffffff
                or isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xffffffff):
            raise ValueError('Invalid current-engine world operation')
        names = tuple(n for n, _ in WORLD_SIGNATURES)
        return self._execute(
            'world', names,
            lambda entries, tls: build(entries, tls, action, rawcode, value),
            decode,
            dict(action=action, rawcode=rawcode, value=value),
        )

    def bulk_batch(self, action, value=0):
        from war3_bulk_protocol import SIGNATURES as BULK_SIGNATURES, build_work as build, decode_work as decode
        if (isinstance(action, bool) or action not in range(1, 5)
                or isinstance(value, bool) or value not in (0, 1)):
            raise ValueError('Invalid current-engine bulk action')
        names = tuple(n for n, _ in BULK_SIGNATURES)
        return self._execute(
            'bulk', names,
            lambda entries, tls: build(entries, tls, action, value),
            decode,
            dict(action=action, value=value),
        )

    def effect_batch(self, rawcode, action, x_bits=0, y_bits=0, *, area_bits=0, passes=1):
        from war3_effect_protocol import SIGNATURES as EFFECT_SIGNATURES, build_work as build, decode_work as decode
        if (isinstance(rawcode, bool) or not isinstance(rawcode, int) or not 0 < rawcode <= 0xFFFFFFFF
                or isinstance(action, bool) or action not in range(1, 5)
                or any(isinstance(value, bool) or not isinstance(value, int)
                       for value in (x_bits, y_bits, area_bits, passes))
                or not 0 <= area_bits <= 0xFFFFFFFF or not 1 <= passes <= 255):
            raise ValueError('Invalid current-engine effect operation')
        wire_x = x_bits if action == 3 else area_bits
        wire_y = y_bits if action == 3 else passes
        names = tuple(n for n, _ in SIGNATURES + EFFECT_SIGNATURES)
        return self._execute(
            'effect', names,
            lambda entries, tls: build(
                entries, tls, rawcode, action, wire_x, wire_y, area_bits,
            ),
            decode,
            dict(rawcode=rawcode, action=action, x_bits=x_bits, y_bits=y_bits,
                 area_bits=area_bits, passes=passes),
        )

    def world_effect_batch(self, rawcode, action, success_limit=0):
        from war3_world_effect_protocol import (
            SIGNATURES as WORLD_EFFECT_SIGNATURES,
            build_work as build,
            decode_work as decode,
        )
        if (isinstance(rawcode, bool) or not isinstance(rawcode, int) or not 0 < rawcode <= 0xFFFFFFFF
                or isinstance(action, bool) or action not in (1, 3)
                or isinstance(success_limit, bool) or not 0 <= success_limit <= 65535):
            raise ValueError('Invalid current-engine world effect operation')
        names = tuple(n for n, _ in WORLD_EFFECT_SIGNATURES)
        return self._execute(
            'world_effect', names,
            lambda entries, tls: build(entries, tls, rawcode, action, success_limit),
            decode,
            dict(rawcode=rawcode, action=action, success_limit=success_limit),
        )

    def spawn_batch(self, rawcode, x_bits=0, y_bits=0, facing_bits=0):
        from war3_spawn_protocol import SIGNATURES as SPAWN_SIGNATURES, build_work as build, decode_work as decode
        values = (rawcode, x_bits, y_bits, facing_bits)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValueError('Spawn arguments must be integers')
        if not 0 < rawcode <= 0xFFFFFFFF or any(not 0 <= value <= 0xFFFFFFFF for value in values[1:]):
            raise ValueError('Invalid current-engine spawn operation')
        names = tuple(n for n, _ in SPAWN_SIGNATURES)
        return self._execute(
            'spawn', names,
            lambda entries, tls: build(entries, tls, rawcode, x_bits, y_bits, facing_bits),
            decode,
            dict(rawcode=rawcode, x_bits=x_bits, y_bits=y_bits, facing_bits=facing_bits),
        )

    def mouse_world_point(self):
        from war3_mouse_protocol import SIGNATURES as MOUSE_SIGNATURES, build_work as build, decode_work as decode
        return self._execute(
            'mouse', tuple(n for n, _ in MOUSE_SIGNATURES),
            lambda entries, tls: build(entries, tls),
            decode,
            {},
        )

    def mouse_screen_point(self):
        from war3_screen_protocol import SIGNATURES as SCREEN_SIGNATURES, build_work as build, decode_work as decode
        return self._execute(
            'screen_mouse', tuple(n for n, _ in SCREEN_SIGNATURES),
            lambda entries, tls: build(entries, tls),
            decode,
            {},
        )

    def camera_snapshot(self):
        from war3_camera_protocol import SIGNATURES as CAMERA_SIGNATURES, build_work as build, decode_work as decode
        return self._execute(
            'camera', tuple(n for n, _ in CAMERA_SIGNATURES),
            lambda entries, tls: build(entries, tls),
            decode,
            {},
        )

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
                    if kind=='ability_field' and evidence.get('work_result_hex'):
                        raw=bytes.fromhex(evidence['work_result_hex'])
                        if len(raw)==7688:
                            changed,error,completed=struct.unpack_from('<3I',raw,624)
                            report['ability_field_status']=dict(changed=changed,error=error,completed=completed)
                    if kind=='item' and evidence.get('work_result_hex'):
                        raw=bytes.fromhex(evidence['work_result_hex'])
                        if len(raw)==5968:
                            changed,error,completed,skipped=struct.unpack_from('<4I',raw,572)
                            report['item_status']=dict(changed=changed,error=error,completed=completed,skipped=skipped)
                    if kind=='item_field' and evidence.get('work_result_hex'):
                        raw=bytes.fromhex(evidence['work_result_hex'])
                        if len(raw)==5136:
                            changed,error,completed=struct.unpack_from('<3I',raw,552+12)
                            report['item_field_status']=dict(changed=changed,error=error,completed=completed)
                    if kind=='clone' and evidence.get('work_result_hex'):
                        raw=bytes.fromhex(evidence['work_result_hex'])
                        if len(raw)==1848:
                            changed,error,completed=struct.unpack_from('<3I',raw,676)
                            report['clone_status']=dict(changed=changed,error=error,completed=completed)
                    if kind=='unit_action' and evidence.get('work_result_hex'):
                        raw=bytes.fromhex(evidence['work_result_hex'])
                        if len(raw)==1432:
                            changed,error,completed=struct.unpack_from('<3I',raw,624)
                            report['unit_action_status']=dict(changed=changed,error=error,completed=completed)
                    if kind=='position' and evidence.get('work_result_hex'):
                        raw=bytes.fromhex(evidence['work_result_hex'])
                        if len(raw)==1312:
                            changed,error,completed=struct.unpack_from('<3I',raw,528)
                            report['position_status']=dict(changed=changed,error=error,completed=completed)
                    if kind=='world' and evidence.get('work_result_hex'):
                        raw=bytes.fromhex(evidence['work_result_hex'])
                        if len(raw)==128:
                            changed,error,completed=struct.unpack_from('<3I',raw,100)
                            report['world_status']=dict(changed=changed,error=error,completed=completed)
                    if kind=='bulk' and evidence.get('work_result_hex'):
                        raw=bytes.fromhex(evidence['work_result_hex'])
                        if len(raw)==624:
                            changed,error,completed=struct.unpack_from('<3I',raw,608)
                            report['bulk_status']=dict(changed=changed,error=error,completed=completed)
                    if kind=='effect' and evidence.get('work_result_hex'):
                        raw=bytes.fromhex(evidence['work_result_hex'])
                        if len(raw)==1160:
                            changed,error,completed=struct.unpack_from('<3I',raw,568)
                            report['effect_status']=dict(changed=changed,error=error,completed=completed)
                    if kind=='world_effect' and evidence.get('work_result_hex'):
                        raw=bytes.fromhex(evidence['work_result_hex'])
                        if len(raw)==648:
                            attempts,error,successes,completed=struct.unpack_from('<4I',raw,628)
                            report['world_effect_status']=dict(
                                attempts=attempts, error=error,
                                successes=successes, completed=completed,
                            )
                    if kind=='spawn' and evidence.get('work_result_hex'):
                        raw=bytes.fromhex(evidence['work_result_hex'])
                        if len(raw)==128:
                            changed,error,completed=struct.unpack_from('<3I',raw,56)
                            report['spawn_status']=dict(changed=changed,error=error,completed=completed)
                    if kind=='mouse' and evidence.get('work_result_hex'):
                        raw=bytes.fromhex(evidence['work_result_hex'])
                        if len(raw)==128:
                            changed,error,completed=struct.unpack_from('<3I',raw,48)
                            report['mouse_status']=dict(changed=changed,error=error,completed=completed)
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
