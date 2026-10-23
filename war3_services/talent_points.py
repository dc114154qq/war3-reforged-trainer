"""Grant one canonical controller point without creating a map-defined item."""
from war3_game_session import UnitRef,NativeHandle,session_scope
from war3_external_backend import ExternalMemoryBackend
from war3_services.operation_trace import BackpackTrace
from war3_3_extension_catalog import TALENT_CONTROLLERS

class TalentPointTrace(BackpackTrace):
    prefix='talent-point';event_name='talent_point_phase'
    source_inputs=('talent_points.py','facade_extensions.py')

def grant_controller_point(host,snapshot,state,logger_factory):
    engine=host._engine_instance_24268();session=engine.session
    target=int(snapshot['target_unit']);controller=state['controller']
    with TalentPointTrace(host,logger_factory,dict(operation='grant_talent_point',target_unit=target,controller=controller)) as trace:
        trace.bind_engine(engine)
        trace.record('before',state=state,route='controller_point_counter',item_definition_required=False)
        with session.lock:
            candidates=tuple(candidate for candidate,_ in host._selected_candidates_snapshot(None))
            refs=host._capture_unit_refs_24268(candidates)
            bindings=engine.bind_unit_refs(refs,strict_selection=True)
            if len(bindings)!=len(candidates) or any(type(n) is not NativeHandle or type(r) is not UnitRef or r!=ref
                    for (n,r),ref in zip(bindings,refs)):
                raise RuntimeError('天赋加点目标的编号与完整身份校验失败')
            matches=[(c,r) for c,(n,r) in zip(candidates,bindings) if n.value==target]
            if len(matches)!=1:raise RuntimeError('天赋加点目标已不在当前选中列表中，请重新读取')
            candidate,unit=matches[0];code=int.from_bytes(controller.encode('ascii'),'big')
            with engine.memory_factory(engine.pid,write=True) as memory:
                registry,_,_=session.prepare(memory)
                with session_scope(session):
                    session.resolve(memory,registry,unit)
                    instances=host._ability_instances_from_candidate(memory,candidate,required_rawcodes={code},allow_global_scan=False)
                    if len(instances)!=1:raise RuntimeError('当前英雄的天赋控制器不唯一，请重新读取')
                    if state.get('controller_instance_full') and int(instances[0].handle)!=int(state['controller_instance_full']):
                        raise RuntimeError('自定义天赋控制器已被替换，请重新读取')
                    tiers=(TALENT_CONTROLLERS[controller][1] if controller in TALENT_CONTROLLERS else
                           tuple(tuple(row['choices']) for row in state['tiers']))
                    trace.record('bound',unit_ref=unit,controller_instance=instances[0],expected_points=state['remaining_points'])
                    result=ExternalMemoryBackend(session).increment_talent_point(memory,registry,unit,candidate,instances[0],
                        code,tiers,int(state['remaining_points']))
                    trace.record('write_readback',result=result)
            current=engine.bind_unit_refs((unit,),strict_selection=True)
            if current!=((NativeHandle(target),unit),):raise RuntimeError('加点后目标身份变化，请先重新读取，勿重复加点')
        trace.record('complete',point_readback_verified=True,result=result)
        return result
