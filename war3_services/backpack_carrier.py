"""Bind and inspect the actual official backpack item before repairing its host."""
from copy import deepcopy
from war3_game_session import GameSession,FullHandle,ObjectAddress

def _preserve(previous,current):
    for area in ('bag','equipment'):
        old=tuple(previous.get(area,()));new=tuple(current.get(area,()))
        for index,row in enumerate(old):
            occupied=bool(row.get('handle',0)) if isinstance(row,dict) else bool(row and row[0])
            if occupied and (index>=len(new) or row!=new[index]):
                raise RuntimeError('背包检查期间原有物品读回变化，已停止后续修复')
        if area=='bag' and int(previous.get('bag_size',0))==30 and (int(current.get('bag_size',0))!=30 or old!=new):
            raise RuntimeError('背包检查期间已有存储记录变化，已停止后续修复')

def inspect_backpack_carrier(host,target,classic,controller,snapshot,trace):
    engine=host._engine_instance_24268()
    if not isinstance(getattr(engine,'session',None),GameSession):
        trace.record('backpack_carrier_check_skipped',reason='typed_session_unavailable',target_unit=target)
        return None
    session=engine.session
    candidates=host._selected_candidates_snapshot(None)
    trace.record('backpack_identity_candidates',target_unit=target,
        candidates=[dict(native_handle=native,candidate=candidate) for candidate,native in candidates])
    matches=[candidate for candidate,native in candidates if int(native)==int(target)]
    if len(matches)!=1:raise RuntimeError('背包持有者与当前选中单位未匹配，已停止本次修复')
    candidate=matches[0]
    with engine.memory_factory(engine.pid) as memory:
        registry,_,_=session.prepare(memory)
        unit=session.bind_unit(memory,registry,ObjectAddress(candidate.unit_address))
        if unit.handle.value!=candidate.handle or unit.rawcode!=candidate.unit_type_id:
            raise RuntimeError('背包检查期间英雄对象变化，已停止本次修复')
        inventory=host._inventory_items_from_candidate(memory,candidate)
        items=[item for item in inventory if item.slot==1 and item.rawcode==int(classic['rawcode'])]
        if len(items)!=1:raise RuntimeError('经典栏中的背包实例未通过身份检查，已停止本次修复')
        item=session.bind_item(memory,registry,FullHandle(items[0].handle))
        trace.record('backpack_bound_identity',unit_ref=unit,item_ref=item,
            candidate=candidate,classic_item=classic,classic_inventory=inventory,
            matching_classic_items=len(items),session_epoch=session.epoch)
    names=('AIni','AEqu',int(controller).to_bytes(4,'big').decode('ascii'),'ASde')
    codes=[int.from_bytes(name.encode('ascii'),'big') for name in names]
    from war3_3_extension_catalog import TALENT_CONTROLLERS
    query_codes=tuple(dict.fromkeys(codes+[int.from_bytes(b'ASpc','big')]+
        [int.from_bytes(name.encode('ascii'),'big') for name in TALENT_CONTROLLERS]))
    checked=engine.extension(query_codes,target_unit=target)
    if int(checked.get('target_unit',0))!=int(target):raise RuntimeError('背包能力检查期间目标变化，已停止本次修复')
    _preserve(snapshot,checked)
    snapshot.setdefault('abilities',{}).update(checked.get('abilities',{}))
    for key in ('bag','equipment','bag_size'):snapshot[key]=checked[key]
    trace.record('backpack_unit_components_before_item_repair',snapshot=checked)
    args=dict(native_target=int(target),native_item=int(classic['handle']),slot=0)
    trace.record('backpack_item_abilities_before',item_full=item.handle.value,unit_full=unit.handle.value,expected_components=names)
    before=engine.item_abilities(unit,item,**args)
    trace.record('backpack_item_abilities_before_result',result=before)
    present={row['rawcode'] for row in before['abilities']}
    result=dict(before=deepcopy(before),expected_components=names,added=[],skipped=[],readbacks=[])
    for name,code in zip(names,codes):
        trace.record('backpack_item_component_decision',component=name,rawcode=code,
            item_ability_present=code in present,
            unit_level=int(snapshot.get('abilities',{}).get(code,0)),
            bag_size=int(snapshot.get('bag_size',0)),
            same_item_full=item.handle.value,same_unit_full=unit.handle.value)
        if code in present:
            trace.record('backpack_item_component_skip',component=name,reason='already_on_same_item')
            continue
        # Do not attach another storage/controller instance over live unit
        # storage, equipment or talents; their existing records own the data.
        active=int(snapshot.get('abilities',{}).get(code,0))>0
        if name=='AIni':active|=int(snapshot.get('bag_size',0))==30
        if active:
            result['skipped'].append(dict(component=name,reason='existing_unit_component'))
            trace.record('backpack_item_component_skip',component=name,reason='existing_unit_component',
                preserved_level=int(snapshot.get('abilities',{}).get(code,0)))
            continue
        trace.record('backpack_item_ability_add',component=name,ability_rawcode=code,item_full=item.handle.value,unit_full=unit.handle.value)
        try:
            observed=engine.item_abilities(unit,item,action=1,ability_rawcode=code,**args)
        except Exception as exc:
            report=dict(getattr(exc,'report',{}) or {})
            report['backpack_carrier']=deepcopy(result)
            error=RuntimeError(f'背包物品缺少 {name}，物品能力挂载也未通过读回；本次修复已停止')
            error.report=report
            raise error from exc
        trace.record('backpack_item_ability_add_result',component=name,result=observed)
        result['added'].append(name);result['readbacks'].append(observed)
        present={row['rawcode'] for row in observed['abilities']}
        current=engine.extension(query_codes,target_unit=target)
        if int(current.get('target_unit',0))!=int(target):raise RuntimeError('挂载能力期间目标变化，已停止后续修复')
        for code,level in snapshot.get('abilities',{}).items():
            if int(level)>0 and int(current.get('abilities',{}).get(code,0))!=int(level):
                raise RuntimeError('挂载背包能力后已有组件等级变化，已停止后续修复')
        for name in TALENT_CONTROLLERS:
            other=int.from_bytes(name.encode('ascii'),'big')
            if other!=int(controller) and int(current.get('abilities',{}).get(other,0))>0:
                raise RuntimeError('挂载背包能力后出现其他天赋控制器，已停止后续修复')
        _preserve(snapshot,current)
        snapshot.setdefault('abilities',{}).update(current.get('abilities',{}))
        for key in ('bag','equipment','bag_size'):snapshot[key]=current[key]
        trace.record('backpack_item_component_readback',component=name,snapshot=current)
    result['actual_open_effect_verified']=False
    return result
