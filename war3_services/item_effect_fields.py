"""Bound item-owned abilities: capture the source once, then revalidate each query."""
from dataclasses import dataclass
from math import isfinite
from uuid import uuid4
from types import MappingProxyType
from war3_game_session import ObjectAddress,FullHandle,session_scope
from war3_ability_fields import ability_fields_for_effect_class
from war3_contracts import AbilityFieldValue
from war3_item_effect_protocol import SIGNATURES,build_work,decode_work,descriptor
from war3_selection_protocol import SIGNATURES as SELECTION

AREAS={'classic':0,'bag':1,'equipment':2}
PROTECTED={'AIni','AEqu','ASpc','AInx','AInv','ASde','ATal'}

@dataclass(frozen=True)
class ItemEffectSource:
    area:str
    slot:int
    unit:object
    item:object
    native_unit:int
    native_item:int
    container_full:int
    rawcode:int

@dataclass(frozen=True)
class ItemEffectSnapshot:
    source:ItemEffectSource
    level:int
    abilities:tuple
    rows:tuple
    generation:str

def capture(host,area,slot):
    if area not in AREAS or isinstance(slot,bool) or not 0<=int(slot)<(6,30,9)[AREAS[area]]:
        raise ValueError('请选择有效的物品位置和槽位')
    slot=int(slot);engine=host._engine_instance_24268();session=engine.session
    candidates=host._selected_candidates_snapshot(None)
    if len(candidates)!=1:raise RuntimeError('请只选中一个持有物品的单位')
    candidate=candidates[0][0]
    refs=host._capture_unit_refs_24268((candidate,))
    bindings=engine.bind_unit_refs(refs,strict_selection=True)
    native=int(bindings[0][0].value)
    if bindings[0][1]!=refs[0]:raise RuntimeError('物品所属单位身份发生变化')
    with engine.memory_factory(engine.pid) as memory:
        registry,_,_=session.prepare(memory)
        with session_scope(session):
            if area=='classic':
                components=host._selected_components(memory,candidate.owner_address)
                if 'inventory' not in components:raise RuntimeError('当前单位没有普通物品栏')
                wrapper,container=components['inventory']
            else:
                code=int.from_bytes(('AIni' if area=='bag' else 'AEqu').encode(),'big')
                found=host._ability_instances_from_candidate(memory,candidate,required_rawcodes={code})
                if len(found)!=1:raise RuntimeError('当前单位没有唯一有效的背包或装备组件')
                wrapper,container=found[0].wrapper_address,found[0].data_address
            profile=session.profile;layout=profile.section('equipment_runtime');reg=profile.section('registry')
            count=int(memory.read_u64(container+layout['equipment_count']))
            if count!=(6,30,9)[AREAS[area]] or slot>=count:raise RuntimeError('物品栏槽位布局已变化')
            records=int(memory.read_u64(container+layout['equipment_records']))
            full=int(memory.read_u64(records+slot*profile.section('layouts')['equipment_record']['stride']))
            if full in (0,0xffffffffffffffff):raise ValueError('所选槽位没有物品')
            item=session.bind_item(memory,registry,FullHandle(full))
            container_full=int(memory.read_u64(wrapper+reg['owner_handle']))
    if area=='classic':
        result=engine.item_batch();rows=[r for r in result['rows'] if int(r['handle'])==native]
        if len(rows)!=1:raise RuntimeError('物品栏所属单位读回变化')
        current=rows[0]['before'][slot]
    else:
        result=engine.extension(target_unit=native);current=result['bag' if area=='bag' else 'equipment'][slot]
    if not current['handle'] or current['rawcode']!=item.rawcode:raise RuntimeError('物品实例已变化，请重新读取')
    return ItemEffectSource(area,slot,refs[0],item,native,int(current['handle']),container_full,int(item.rawcode))

def query(host,source,level,fields=(),ability=None,action=0,expected_value=None):
    engine=host._engine_instance_24268();session=engine.session
    expected=(0,0,0,0) if ability is None else (ability['handle'],ability['full'],ability['data'],ability['rawcode'])
    def builder(entries,tls):
        with engine.memory_factory(engine.pid) as memory:
            registry,_,_=session.prepare(memory)
            session.resolve(memory,registry,source.unit);session.resolve(memory,registry,source.item)
            layout=session.profile.section('layouts')['item']
            records=tuple(layout[k] for k in ('ability_records','ability_record_stride','ability_record_rawcode','ability_record_limit'))
            if not all(records):raise RuntimeError('当前适配包尚未开放物品附带技能字段')
            return build_work(entries,tls,layout=records,expected_value=expected_value,base=registry.base,target=source.native_unit,item=source.native_item,
                unit_full=source.unit.handle.value,item_full=source.item.handle.value,container_full=source.container_full,
                area=AREAS[source.area],slot=source.slot,index=ability['index'] if ability else 0,
                level=level,action=action,fields=fields,expected=expected)
    try:
        return engine._execute('item_effect',tuple(n for n,_ in SELECTION+SIGNATURES),builder,decode_work,
            dict(action=action,area=source.area,slot=source.slot,target=source.native_unit,item=source.native_item,
                item_full=source.item.handle.value,rawcode=source.rawcode,ability=expected,level=level,fields=fields,expected_value=expected_value))
    except Exception as exc:
        status=(getattr(exc,'report',None) or {}).get('item_effect_status',{})
        if status.get('cleanup_uncertain'):
            session.cache['item_effect_write_disabled']=True
        raise

def read(host,area='classic',slot=0,level=1):
    if isinstance(level,bool):raise ValueError('请输入整数等级')
    level=int(level)
    if not 1<=level<=1000:raise ValueError('字段等级应在1到1000之间')
    source=capture(host,area,slot)
    metadata=query(host,source,level);abilities=tuple(MappingProxyType(dict(a)) for a in metadata['abilities']);rows=[]
    from war3_3_extension_catalog import TALENT_CONTROLLERS
    protected=PROTECTED|set(TALENT_CONTROLLERS)
    for ability in abilities:
        code=ability['rawcode'].to_bytes(4,'big').decode('ascii','replace')
        effect=ability['effect_class'].to_bytes(4,'big').decode('ascii','replace')
        if code in protected or effect in protected:
            rows.append((ability,None,'背包、装备或天赋控制组件：仅列出，不编辑其内部字段'))
            continue
        specs=tuple(sorted(ability_fields_for_effect_class(effect),key=lambda s:not bool(s.use_specific)))
        levels=query(host,source,1,(descriptor(int.from_bytes(b'alev','big'),'integer','field'),),ability)['before'][0]
        supported=[s for s in specs if s.runtime_supported and (s.scope!='level' or 1<=level<=levels)]
        values={}
        for start in range(0,len(supported),32):
            batch=supported[start:start+32]
            result=query(host,source,level,tuple(descriptor(s.field_id,s.value_kind,s.scope) for s in batch),ability)
            for s,bits in zip(batch,result['before']):
                value=host._decode_ability_field_value(s,bits)
                if isinstance(value,float) and not isfinite(value):value=None
                values[(s.rawcode,s.value_kind,s.scope)]=value
        for s in specs:
            value=values.get((s.rawcode,s.value_kind,s.scope))
            note=('字段等级超过该物品技能的 '+str(levels)+' 级' if s.scope=='level' and not 1<=level<=levels else '' if s.runtime_supported else '字符串或等级数组字段暂未开放')
            rows.append((ability,AbilityFieldValue(s,value,'可写' if value is not None and s.writable else '未开放',note),''))
    return ItemEffectSnapshot(source,level,abilities,tuple(rows),uuid4().hex)

def write(host,snapshot,row_index,text):
    if host._engine_instance_24268().session.cache.get('item_effect_write_disabled',False):raise RuntimeError('之前的物品技能字段恢复待确认，请重新连接后再编辑')
    if not isinstance(snapshot,ItemEffectSnapshot):raise ValueError('请先读取当前物品附带技能')
    if isinstance(row_index,bool) or not 0<=int(row_index)<len(snapshot.rows):raise ValueError('物品字段已失效，请重新读取')
    ability,field,note=snapshot.rows[int(row_index)]
    if field is None or field.value is None or not field.spec.writable or not field.spec.runtime_supported:
        raise ValueError('请选择可写的数值字段')
    value=host._coerce_ability_field_value(field.spec,text)
    target=host._current_engine_ability_field_bits(field.spec,value)
    d=descriptor(field.spec.field_id,field.spec.value_kind,field.spec.scope,target)
    result=query(host,snapshot.source,snapshot.level,(d,),ability,1,host._current_engine_ability_field_bits(field.spec,field.value))
    actual=host._decode_ability_field_value(field.spec,result['after'][0])
    if not host._ability_field_values_equal(field.spec,actual,value):raise RuntimeError('物品技能数值读回不一致')
    return actual

