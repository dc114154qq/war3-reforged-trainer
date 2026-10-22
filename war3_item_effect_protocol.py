"""Numeric fields of an ability owned by one item in one bound inventory slot."""
import struct
from war3_selection_protocol import SIGNATURES as SELECTION,build_work as selection_work,validate_work as selection_validate,decode_work as selection_result
from war3_ability_field_protocol import SIGNATURES as ABILITY_FIELDS,descriptor

MAX_ABILITIES=32
MAX_FIELDS=32
WORK_SIZE=2584
ABI=struct.pack('<3I',0x24268077,216,WORK_SIZE)
FIELD_SIGNATURES=ABILITY_FIELDS[3:]
SOURCE_SIGNATURES=(('UnitItemInSlot','(Hunit;I)Hitem;'),('UnitItemInBagSlot','(Hunit;I)Hitem;'),
    ('UnitItemInEquipmentSlot','(Hunit;Hloadoutslot;)Hitem;'),('ConvertLoadoutSlot','(I)Hloadoutslot;'),
    ('GetItemTypeId','(Hitem;)I'),('BlzGetItemAbilityByIndex','(Hitem;I)Hability;'),
    ('BlzGetAbilityId','(Hability;)I'),('GetHandleId','(Hhandle;)I'))
SIGNATURES=FIELD_SIGNATURES+SOURCE_SIGNATURES

def build_work(entries,tls,*,base,target,item,unit_full,item_full,container_full,area,slot,
               index=0,level=1,action=0,fields=(),expected=(0,0,0,0),layout=(0,0,0,0),expected_value=None):
    pointers=[]
    for name,sig in SIGNATURES:
        e=entries.get(name)
        if e is None or (e.name,e.signature)!=(name,sig):raise ValueError('Item effect signature differs: '+name)
        pointers.append(e.handler)
    rows=tuple(fields)
    payload=bytearray(selection_work(entries))
    payload.extend(struct.pack('<21Q',*pointers,tls))
    payload.extend(struct.pack('<6Q',base,target,item,unit_full,item_full,container_full))
    payload.extend(struct.pack('<12I',area,slot,index,level,action,len(rows),expected[3],0,0,0,0,0))
    payload.extend(struct.pack('<3Q',*expected[:3]))
    payload.extend(struct.pack('<6I',*layout,0 if expected_value is None else expected_value,int(expected_value is not None)))
    for row in rows:payload.extend(struct.pack('<4I',*row))
    payload.extend(bytes(WORK_SIZE-len(payload)))
    validate_work(bytes(payload));return bytes(payload)

def validate_work(payload):
    if len(payload)!=WORK_SIZE:raise ValueError('Item effect work size differs')
    selection_validate(payload[:480])
    ptr=struct.unpack_from('<21Q',payload,480)
    if any(not 0x10000<=p<0x800000000000 for p in ptr) or ptr[-1]%8:raise ValueError('Item effect handler or TLS invalid')
    base,target,item,unit_full,item_full,container=struct.unpack_from('<6Q',payload,648)
    if not base or not all((target,item,unit_full,item_full,container)):raise ValueError('Item effect source identity missing')
    area,slot,index,level,action,count,code,*output=struct.unpack_from('<12I',payload,696)
    if area>2 or slot>=(6,30,9)[area] or index>=32 or not 1<=level<=1000 or action>1 or count>32 or any(output):
        raise ValueError('Item effect request invalid')
    ability,full,data=struct.unpack_from('<3Q',payload,744)
    if count and not all((ability,full,data,code)):raise ValueError('Item effect field target missing')
    if action and count!=1:raise ValueError('Edit one item ability field at a time')
    if not count and (action or any((ability,full,data,code))):raise ValueError('Item effect metadata request invalid')
    records,stride,code_offset,limit,expected_value,compare=struct.unpack_from('<6I',payload,768)
    if not 0 < records < 0x10000 or not 12 <= stride <= 4096 or not 8 <= code_offset <= stride-4 or not 1 <= limit <= 128 or compare>1 or (action and compare!=1):
        raise ValueError('Item effect layout or value guard invalid')
    for i in range(32):
        field,kind,scope,value=struct.unpack_from('<4I',payload,792+16*i)
        if i<count:
            if not field or kind>2 or scope>1:raise ValueError('Item effect field descriptor invalid')
        elif any((field,kind,scope,value)):raise ValueError('Unused item effect descriptor is not empty')
    if any(payload[1304:]):raise ValueError('Item effect output must start empty')

def status(payload):
    if len(payload)!=WORK_SIZE:return {}
    area,slot,index,level,action,count,code,error,completed,changed,abilities,effect=struct.unpack_from('<12I',payload,696)
    rows=[dict(handle=h,full=f,data=d,rawcode=r,effect_class=c,index=i)
        for i in range(min(abilities,32)) for h,f,d,r,c in [struct.unpack_from('<3Q2I',payload,1304+i*32)]]
    return dict(area=area,slot=slot,index=index,level=level,action=action,field_count=count,
        error=error,completed=completed,changed=changed,cleanup_uncertain=changed==2,
        abilities=rows,effect_class=effect,before=struct.unpack_from('<32I',payload,2328)[:count],
        after=struct.unpack_from('<32I',payload,2456)[:count])

def decode_work(payload,count):
    r=status(payload);selection=selection_result(payload[:480],count)
    base,target,item,unit_full,item_full,container=struct.unpack_from('<6Q',payload,648)
    if r['error'] or r['completed']!=1 or r['changed'] not in (0,1) or len(r['abilities'])>32:
        raise ValueError(f"物品附带技能操作失败：error={r['error']}, changed={r['changed']}")
    if sum(x['handle']==target for x in selection['rows'])!=1:raise ValueError('Item effect selection changed')
    if any(not all((a['handle'],a['full'],a['data'],a['rawcode'],a['effect_class'])) for a in r['abilities']):
        raise ValueError('Item effect returned incomplete ability identity')
    if len({a['handle'] for a in r['abilities']})!=len(r['abilities']):raise ValueError('Item effect repeated ability identity')
    if r['field_count']:
        if r['index']>=len(r['abilities']):raise ValueError('Item effect target disappeared')
        a=r['abilities'][r['index']];expected=struct.unpack_from('<3Q',payload,744)
        if (a['handle'],a['full'],a['data'])!=expected or a['rawcode']!=struct.unpack_from('<I',payload,720)[0]:
            raise ValueError('Item effect field result belongs to another ability')
    return dict(r,selection=selection,target_unit=target,item_handle=item,unit_full=unit_full,item_full=item_full)
