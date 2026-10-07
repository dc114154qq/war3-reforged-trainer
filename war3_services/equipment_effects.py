"""Ordinary items use native equip/remove; object classification belongs to a session."""
from collections import Counter
import struct
from war3_game_session import FullHandle, ObjectAddress, NativeHandle, session_scope
from war3_game_profile import profile_scope
from war3_selection_protocol import SIGNATURES as SELECTION


def skipped_snapshot(snapshot, rawcode):
    snapshot=dict(snapshot)
    code=int(rawcode).to_bytes(4,'big').decode('ascii','replace')
    snapshot['operation_skipped']=dict(rawcode=int(rawcode),reason_code='protected_legacy_item',
        reason=f'已跳过物品 {code}：旧式普通物品不可丢弃，转入扩展背包或装备槽可能触发战役脚本删除；未转移物品，可继续其他操作')
    return snapshot


def preflight_creation(host, rawcode, target):
    """No pickup event: temporary object is inspected and removed in one callback."""
    from war3_game_session import GameSession
    from war3_reforged_trainer import ProcessMemory
    from war3_item_safety_protocol import SIGNATURES, build_work, decode_work
    engine=host._engine_instance_24268()
    # Legacy test hosts have no live session and cannot dispatch a game callback.
    if not isinstance(getattr(engine,'session',None),GameSession):
        return {}
    session=engine.session
    with session.lock:
        candidate,_=host._direct_selected_context()
        with ProcessMemory(host.pid) as memory:
            registry,_,_=session.prepare(memory)
            unit=session.bind_unit(memory,registry,ObjectAddress(candidate.unit_address))
        def builder(entries,tls):
            with ProcessMemory(host.pid) as memory:
                registry,_,_=session.prepare(memory)
                session.resolve(memory,registry,unit)
            return build_work(entries,tls,target=target,rawcode=rawcode)
        return engine._execute('item_safety',tuple(n for n,_ in SELECTION+SIGNATURES),
            builder,decode_work,dict(target=target,rawcode=rawcode))


def active_abilities(host, memory, candidate):
    layout=host._engine_instance_24268().session.profile.section('equipment_runtime')
    return Counter(a.rawcode for a in host._ability_instances_from_candidate(
        memory,candidate,allow_global_scan=False)
        if memory.read_u64(a.data_address+layout['ability_owner'])==candidate.unit_address
        and memory.read_u32(a.data_address+layout['item_flags'])&0x48==0)


def require_creation_capacity(host, rawcode, target, definition=None):
    """Ordinary items need one temporary classic slot before bag insertion."""
    from war3_reforged_trainer import ProcessMemory
    engine=host._engine_instance_24268();session=engine.session
    classic=host.item_batch_24268()
    rows=[r for r in classic['rows'] if int(r['handle'])==int(target)]
    if len(rows)!=1:raise RuntimeError('Creation target is not uniquely selected')
    size=int(rows[0]['inventory_size'])
    if any(not r['handle'] for r in rows[0]['before'][:size]):
        return
    definition=definition or preflight_creation(host,rawcode,target)
    if not definition.get('equipment_type'):
        raise RuntimeError('Classic inventory is full; free one temporary slot before regenerating ordinary equipment. No item was created')


def classify_state(host, snapshot, slot, area, *, destruction=False):
    from war3_reforged_trainer import ProcessMemory
    engine=host._engine_instance_24268();session=engine.session
    candidate,_=host._direct_selected_context()
    from war3_3_extension_catalog import OFFICIAL_BACKPACKS
    if snapshot[area][slot]['rawcode'] in {int.from_bytes(x.encode('ascii'),'big') for x in OFFICIAL_BACKPACKS}:
        raise RuntimeError('背包入口物品不能放进装备槽；请保持在经典物品栏中')
    definition=preflight_creation(host,int(snapshot[area][slot]['rawcode']),int(snapshot['target_unit']))
    from war3_equipment_effect_protocol import ORDINARY_CLASSES
    if not destruction and (definition.get('equipment_type') or definition.get('original_class') not in ORDINARY_CLASSES):
        raise RuntimeError('普通物品原生分类不匹配，未执行装备写入')
    with ProcessMemory(host.pid) as memory:
        registry,_,_=session.prepare(memory)
        with profile_scope(session.profile):
            unit=session.bind_unit(memory,registry,ObjectAddress(candidate.unit_address))
            if unit.handle.value!=candidate.handle:
                raise RuntimeError('装备操作前英雄对象已变化')
            record=host._extension_inventory_equipment_records_24268(memory,candidate)
            layout=session.profile.section('equipment_runtime')
            full=memory.read_u64(record['AIni' if area=='bag' else 'AEqu']+slot*12)
            item=session.bind_item(memory,registry,FullHandle(full))
            row=snapshot[area][slot]
            if item.rawcode!=row['rawcode']:
                raise RuntimeError('装备操作前物品实例已变化')
            addr=session.resolve(memory,registry,item)
            instances=host._ability_instances_from_candidate(memory,candidate,
                required_rawcodes={int.from_bytes(b'AEqu','big')},allow_global_scan=False)
            if len(instances)!=1:raise RuntimeError('装备组件不是唯一实例')
            return dict(candidate=candidate,unit=unit,item=item,layout=layout,
                equipment=instances[0].data_address,base=registry.base,
                native_item=NativeHandle(row['handle']),native_unit=NativeHandle(snapshot['target_unit']),
                flags=memory.read_u32(addr+layout['item_flags']),
                item_class=memory.read_u32(addr+layout['item_class']),
                cached_type=memory.read_u32(addr+layout['item_equipment_type']),
                original_class=int(definition['original_class']),
                active=active_abilities(host,memory,candidate))


def build_bound_work(host,state,entries,tls,action,slot):
    from war3_reforged_trainer import ProcessMemory
    from war3_equipment_effect_protocol import build_work
    session=host._engine_instance_24268().session
    if state['item'].epoch!=session.epoch or state['unit'].session!=session.identity:
        raise RuntimeError('地图或进程身份在装备操作前已变化')
    with ProcessMemory(host.pid) as memory:
        registry,_,_=session.prepare(memory)
        session.resolve(memory,registry,state['unit']);session.resolve(memory,registry,state['item'])
    return build_work(entries,tls,base=state['base'],target=state['native_unit'].value,
        unit_full=state['unit'].handle.value,item=state['native_item'].value,
        item_full=state['item'].handle.value,equipment=state['equipment'],action=action,
        slot=slot,rawcode=state['item'].rawcode,original_class=state['original_class'],
        flags=state['flags'],item_class=state['item_class'],cached_type=state['cached_type'],layout=state['layout'])


def guard_drop(host,snapshot,slot):
    """Repair an inherited classifier before invoking the ordinary native drop."""
    from war3_game_session import GameSession
    if not isinstance(getattr(host._engine_instance_24268(),'session',None),GameSession):return snapshot
    state=classify_state(host,snapshot,slot,'bag',destruction=True)
    if state['flags']&0x4000 and not state['cached_type']:
        return repair_bag(host,snapshot,slot)
    return snapshot


def repair_bag(host,before,slot):
    from war3_equipment_effect_protocol import SIGNATURES,TRANSFER_SIGNATURES,decode_work
    session=host._engine_instance_24268().session
    with session.lock:
        state=classify_state(host,before,slot,'bag')
        if not state['flags']&0x4000 and not state['cached_type']:
            return before
        with session_scope(session):
            result=host._engine_instance_24268()._execute('equipment_effect',
                tuple(n for n,_ in SELECTION+SIGNATURES+TRANSFER_SIGNATURES),
                lambda entries,tls:build_bound_work(host,state,entries,tls,6,slot),
                decode_work,dict(action=6,target=state['native_unit'].value,item=state['native_item'].value,slot=slot))
        after=host.extension_snapshot_24268(state['native_unit'].value)
        if result.get('skipped'):return skipped_snapshot(after,state['item'].rawcode)
        matches=[r for r in after['bag'] if r['handle']==state['native_item'].value]
        if (len(matches)!=1 or matches[0]['rawcode']!=state['item'].rawcode or
                matches[0]['charges']!=before['bag'][slot]['charges']):
            session.uncertain=True
            raise RuntimeError('物品状态修复后的实例读回不一致，已停止后续写入')
        after['repaired_item']=dict(rawcode=state['item'].rawcode,slot=matches[0]['slot'],native_state_verified=True)
        return after


def repair_equipment(host, before):
    """Rehydrate inherited instance classifiers in place, without equip events."""
    from war3_reforged_trainer import ProcessMemory
    from war3_equipment_effect_protocol import SIGNATURES,TRANSFER_SIGNATURES,decode_work,ORDINARY_CLASSES
    engine=host._engine_instance_24268();session=engine.session
    kinds=(1,2,3,4,5,5,6,7,8)
    repaired=[];skipped=[]
    with session.lock:
        current=before
        for slot,row in enumerate(before['equipment']):
            if not row['handle']:
                continue
            state=classify_state(host,current,slot,'equipment',destruction=True)
            if state['original_class'] not in ORDINARY_CLASSES:
                skipped.append(dict(slot=slot,reason='正式装备无需普通物品分类修复'))
                continue
            if (state['item_class']==7 and state['cached_type']==kinds[slot]
                    and state['flags']&0x4000):
                skipped.append(dict(slot=slot,reason='装备状态正常，无需修复'))
                continue
            if state['item_class']!=state['original_class'] or state['cached_type']:
                raise RuntimeError('装备实例分类与跨章节丢失状态不符，未修改该物品；请保留日志')
            with session_scope(session):
                result=engine._execute('equipment_effect',
                    tuple(n for n,_ in SELECTION+SIGNATURES+TRANSFER_SIGNATURES),
                    lambda entries,tls:build_bound_work(host,state,entries,tls,7,slot),decode_work,
                    dict(action=7,target=state['native_unit'].value,item=state['native_item'].value,slot=slot))
            after=host.extension_snapshot_24268(state['native_unit'].value)
            identity=lambda rows:tuple((r['slot'],r['handle'],r['rawcode'],r['charges']) for r in rows)
            with ProcessMemory(host.pid) as memory:
                registry,_,_=session.prepare(memory)
                session.resolve(memory,registry,state['unit'])
                session.resolve(memory,registry,state['item'])
                active=active_abilities(host,memory,state['candidate'])
            if (after['target_unit']!=current['target_unit'] or current['bag']!=after['bag']
                    or identity(current['equipment'])!=identity(after['equipment'])
                    or after['equipment'][slot]['equipment_type']!=current['equipment'][slot]['equipment_type']
                    or active!=state['active']):
                session.uncertain=True
                raise RuntimeError('原位修复后的装备实例、数量、分类或能力读回不一致，已停止后续写入')
            repaired.append(dict(slot=slot,rawcode=row['rawcode'],native=row['handle'],
                full=state['item'].handle.value,runtime_classification_verified=True,
                native_definition_type_unchanged=True,
                ability_list_unchanged=True))
            current=after
        current=dict(current)
        current['equipment_state_repair']=dict(repaired=repaired,skipped=skipped,
            in_place=True,no_equip_or_drop_events=True)
        return current


def destroy(host,before,slot,area,*,expected=None):
    from war3_equipment_effect_protocol import SIGNATURES,TRANSFER_SIGNATURES,decode_work
    session=host._engine_instance_24268().session
    with session.lock:
        state=classify_state(host,before,slot,area,destruction=True)
        if expected is not None and any(state[key]!=expected[key]
                for key in ('unit','item','native_unit','native_item')):
            raise RuntimeError('确认销毁后英雄、地图或物品实例已变化，未执行删除；请刷新后重新选择')
        action=4 if area=='bag' else 5
        with session_scope(session):
            result=host._engine_instance_24268()._execute('equipment_effect',
                tuple(n for n,_ in SELECTION+SIGNATURES+TRANSFER_SIGNATURES),
                lambda entries,tls:build_bound_work(host,state,entries,tls,action,slot),
                decode_work,dict(action=action,target=state['native_unit'].value,item=state['native_item'].value,slot=slot))
        session.retire_item(state['item'])
        after=host.extension_snapshot_24268(state['native_unit'].value)
        if any(int(row['handle'])==state['native_item'].value for a in ('bag','equipment') for row in after[a]):
            session.uncertain=True
            raise RuntimeError('销毁后仍读到物品引用，已停止后续写入')
        after['destroyed_item']=dict(rawcode=state['item'].rawcode,area=area,slot=slot,
            **result['destruction_evidence'])
        return after


def perform(host, before, source_slot, equipment_slot, *, equip):
    from war3_reforged_trainer import ProcessMemory
    from war3_equipment_effect_protocol import SIGNATURES,TRANSFER_SIGNATURES,build_work,decode_work
    engine=host._engine_instance_24268();session=engine.session
    with session.lock:
        state=classify_state(host,before,source_slot,'bag' if equip else 'equipment')
        with session_scope(session):
            def builder(entries,tls):
                return build_bound_work(host,state,entries,tls,1 if equip else 2,equipment_slot)
            try:
                result=engine._execute('equipment_effect',tuple(n for n,_ in SELECTION+SIGNATURES+TRANSFER_SIGNATURES),
                    builder,decode_work,dict(action=1 if equip else 2,target=state['native_unit'].value,
                        item=state['native_item'].value,slot=equipment_slot))
            except Exception:
                status=engine.last_report.get('business_status',{})
                if status.get('session_continuable'):
                    try:
                        with ProcessMemory(host.pid) as memory:
                            registry,_,_=session.prepare(memory)
                            session.resolve(memory,registry,state['unit'])
                            session.resolve(memory,registry,state['item'])
                            active=active_abilities(host,memory,state['candidate'])
                        if active!=state['active']:
                            raise RuntimeError('Item ability rollback differs from the original unit')
                        status['ability_rollback_verified']=True
                    except Exception as rollback_exc:
                        session.uncertain=True
                        status['session_continuable']=False
                        status['ability_rollback_verified']=False
                        status['ability_rollback_error']=str(rollback_exc)
                raise
            after=host.extension_snapshot_24268(state['native_unit'].value)
            if result.get('skipped'):
                return skipped_snapshot(after,state['item'].rawcode)
            with ProcessMemory(host.pid) as memory:
                registry,_,_=session.prepare(memory)
                session.resolve(memory,registry,state['unit']);session.resolve(memory,registry,state['item'])
                active=active_abilities(host,memory,state['candidate'])
            expected=Counter(result['ability_ids'])
            differences={code:active[code]-state['active'][code] for code in expected}
            verified=all(delta==(expected[code] if equip else -expected[code])
                         for code,delta in differences.items())
            no_effect_source=bool(expected) and all(
                state['active'][code] == 0 and active[code] == 0 for code in expected
            )
            effect_already_present=bool(expected) and all(
                state['active'][code] > 0 and active[code] == state['active'][code]
                for code in expected
            )
            after['equipment_effect_sync']=dict(status='native_applied' if equip else 'native_removed',
                ability_ids=result['ability_ids'],ability_deltas=differences,verified=verified,
                instance=state['item'].handle.value)
            if not verified:
                if no_effect_source:
                    after['equipment_effect_sync'].update(
                        status='no_effect_source', verified=True,
                        reason='物品已完成槽位读回，但游戏未提供可挂载的装备能力'
                    )
                    return after
                if effect_already_present:
                    after['equipment_effect_sync'].update(
                        status='effect_already_present', verified=True,
                        reason='同一能力在单位上已有来源，读回数量未变化；未把它误报成新增能力'
                    )
                    return after
                session.uncertain=True
                raise RuntimeError('装备槽位已改变，但物品能力增减未通过验证；已阻止重复执行，请保存日志')
            return after


def transfer_created(host, target, native_item, rawcode):
    """Bind a generated classic instance and move it through native bag insertion."""
    from war3_reforged_trainer import ProcessMemory
    from war3_equipment_effect_protocol import SIGNATURES, TRANSFER_SIGNATURES, build_work, decode_work
    engine=host._engine_instance_24268(); session=engine.session
    classic=host.item_batch_24268()
    units=[row for row in classic['rows'] if int(row['handle'])==int(target)]
    if len(units)!=1:raise RuntimeError('Generated item target is not uniquely selected')
    items=[row for row in units[0]['before'] if int(row['handle'])==int(native_item) and int(row['rawcode'])==int(rawcode)]
    if len(items)!=1:raise RuntimeError('Generated item is not uniquely in classic inventory; no transfer issued')
    definition=preflight_creation(host,rawcode,target)
    if definition.get('skipped'):
        return skipped_snapshot(host.extension_snapshot_24268(target),rawcode)
    slot=int(items[0]['slot'])
    selected=host._selected_candidates_snapshot(None)
    matches=[c for c,h in selected if int(h)==int(target)]
    if not matches and sum(row['rawcode']==units[0]['rawcode'] for row in classic['rows'])==1:
        matches=[c for c,_ in selected if c.unit_type_id==units[0]['rawcode']]
    if len(matches)!=1:raise RuntimeError('Generated item hero identity is not unique')
    candidate=matches[0]
    with ProcessMemory(host.pid) as memory:
        registry,_,_=session.prepare(memory)
        unit=session.bind_unit(memory,registry,ObjectAddress(candidate.unit_address))
        inventory=host._inventory_items_from_candidate(memory,candidate)
        owned=[row for row in inventory if row.slot==slot+1 and row.rawcode==rawcode]
        if len(owned)!=1:raise RuntimeError('Generated item full identity differs from classic native slot')
        component=host._selected_components(memory,candidate.owner_address).get('inventory')
        if component is None:raise RuntimeError('Generated item classic inventory component disappeared')
        classic_inventory=host._inventory_record_address(memory,candidate,component[1])
        if not classic_inventory:raise RuntimeError('Generated item classic inventory records are invalid')
        item=session.bind_item(memory,registry,FullHandle(owned[0].handle))
        address=session.resolve(memory,registry,item)
        layout=session.profile.section('equipment_runtime')
        original=int(definition['original_class'])
        components=host._ability_instances_from_candidate(memory,candidate,
            required_rawcodes={int.from_bytes(b'AEqu','big')},allow_global_scan=False)
        if len(components)!=1:raise RuntimeError('Bag transfer equipment component is not unique')
        state=dict(base=registry.base,unit_full=unit.handle.value,item_full=item.handle.value,
            classic_inventory=classic_inventory,
            equipment=components[0].data_address,original_class=original,
            flags=memory.read_u32(address+layout['item_flags']),
            item_class=memory.read_u32(address+layout['item_class']),
            cached_type=memory.read_u32(address+layout['item_equipment_type']))
    def builder(entries,tls):
        with ProcessMemory(host.pid) as memory:
            registry,_,_=session.prepare(memory)
            session.resolve(memory,registry,unit);session.resolve(memory,registry,item)
        return build_work(entries,tls,**state,target=target,item=native_item,
            rawcode=rawcode,action=3,slot=slot,layout=layout)
    result=engine._execute('equipment_effect',tuple(n for n,_ in SELECTION+SIGNATURES+TRANSFER_SIGNATURES),
        builder,decode_work,dict(action=3,target=target,item=native_item,rawcode=rawcode))
    after=host.extension_snapshot_24268(target)
    return skipped_snapshot(after,rawcode) if result.get('skipped') else after
