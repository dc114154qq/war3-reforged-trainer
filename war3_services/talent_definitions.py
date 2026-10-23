"""Discover map-defined native ATal controllers using exact unit identities."""
from contextlib import contextmanager
from war3_3_extension_catalog import TALENT_CONTROLLERS
from war3_game_session import NativeHandle,UnitRef,session_scope

@contextmanager
def bound_target(host,snapshot,engine=None):
    engine=engine or host._engine_instance_24268();session=engine.session
    with session.lock:
        candidates=tuple(c for c,_ in host._selected_candidates_snapshot(None))
        refs=host._capture_unit_refs_24268(candidates)
        bindings=engine.bind_unit_refs(refs,strict_selection=True)
        if len(bindings)!=len(refs) or any(type(n) is not NativeHandle or type(r) is not UnitRef or r!=ref
                for (n,r),ref in zip(bindings,refs)):
            raise RuntimeError('天赋读取目标的编号与完整身份校验失败')
        matches=[(c,r) for c,(n,r) in zip(candidates,bindings) if n.value==int(snapshot['target_unit'])]
        if len(matches)!=1:raise RuntimeError('天赋读取目标已变化，请重新读取')
        candidate,ref=matches[0]
        with engine.memory_factory(engine.pid) as memory:
            registry,_,_=session.prepare(memory)
            with session_scope(session):
                session.resolve(memory,registry,ref)
                yield memory,registry,candidate,session.profile
                session.resolve(memory,registry,ref)

def enrich_snapshot(host,snapshot,engine):
    if not getattr(host,'pid',0):return snapshot
    definitions={};errors=[]
    try:
        with bound_target(host,snapshot,engine) as (memory,registry,candidate,profile):
            instances=host._ability_instances_from_candidate(memory,candidate,allow_global_scan=False)
            for instance in instances:
                if instance.class_rawcode!=int.from_bytes(b'ATal','big'):continue
                code=instance.rawcode.to_bytes(4,'big').decode('ascii')
                if code in TALENT_CONTROLLERS:continue
                if code in definitions:raise RuntimeError('当前单位有多个同码自定义天赋控制器')
                tiers=profile.adapter.talents.definition(memory,candidate,instance,registry)
                definitions[code]=dict(name='自定义天赋 '+code,tiers=tiers,instance_full=int(instance.handle))
                # Discovery already proves this is an attached live instance;
                # a level-zero controller still owns usable native point data.
                snapshot['abilities'][instance.rawcode]=max(1,int(snapshot['abilities'].get(instance.rawcode,0)))
    except Exception as exc:
        errors.append(str(exc))
    snapshot['talent_definitions']=definitions
    if errors:snapshot['talent_discovery_errors']=tuple(errors)
    return snapshot

def catalog(snapshot):
    result=dict(TALENT_CONTROLLERS)
    for code,value in snapshot.get('talent_definitions',{}).items():
        result[code]=(value['name'],tuple(tuple(row) for row in value['tiers']))
    return result

def read_custom_records(host,snapshot,controller,tiers):
    with bound_target(host,snapshot) as (memory,registry,candidate,profile):
        wanted=int.from_bytes(controller.encode('ascii'),'big')
        instances=host._ability_instances_from_candidate(memory,candidate,required_rawcodes={wanted},allow_global_scan=False)
        if len(instances)!=1:raise RuntimeError('自定义天赋控制器实例不唯一')
        expected=snapshot['talent_definitions'][controller]
        if (int(instances[0].handle)!=int(expected['instance_full'])
                or profile.adapter.talents.definition(memory,candidate,instances[0],registry)!=tiers):
            raise RuntimeError('自定义天赋定义或控制器已变化，请重新读取')
        return profile.adapter.talents.records(memory,candidate,instances,tiers,registry)
