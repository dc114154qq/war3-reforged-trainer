"""Inspect/attach a capability to the same owned item; no item replacement."""
import struct
from war3_selection_protocol import build_work as selection_work, validate_work as selection_validate, decode_work as selection_decode

WORK_SIZE=1216
ABI=struct.pack('<3I',0x24268067,216,WORK_SIZE)
SIGNATURES=(
    ('UnitItemInSlot','(Hunit;I)Hitem;'),('GetItemTypeId','(Hitem;)I'),
    ('GetItemCharges','(Hitem;)I'),('BlzGetItemAbility','(Hitem;I)Hability;'),
    ('BlzGetItemAbilityByIndex','(Hitem;I)Hability;'),('BlzGetAbilityId','(Hability;)I'),
    ('BlzItemAddAbility','(Hitem;I)B'),
)

def build_work(entries,tls,*,target,item,base,unit_full,item_full,rawcode,slot=0,action=0,ability_rawcode=0):
    handlers=[]
    for name,signature in SIGNATURES:
        entry=entries.get(name)
        if entry is None or (entry.name,entry.signature)!=(name,signature):
            raise ValueError('Item ability native signature differs: '+name)
        handlers.append(entry.handler)
    payload=(selection_work(entries)+struct.pack('<13Q10I',*handlers,tls,target,item,base,unit_full,item_full,
        rawcode,action,slot,ability_rawcode,0,0,0,0,0,0)+bytes(WORK_SIZE-624))
    validate_work(payload)
    return payload

def validate_work(payload):
    if len(payload)!=WORK_SIZE:raise ValueError('Item ability work size differs')
    selection_validate(payload[:480])
    pointers=struct.unpack_from('<13Q',payload,480)
    if (any(not 0x10000<=v<0x800000000000 for v in pointers[:11]) or pointers[7]%8
            or not pointers[11] or not pointers[12]):
        raise ValueError('Item ability identity invalid')
    rawcode,action,slot,ability_rawcode,*output=struct.unpack_from('<10I',payload,584)
    if (not rawcode or action not in (0,1) or slot>=6 or
            (action==1 and not ability_rawcode) or any(output) or any(payload[624:])):
        raise ValueError('Item ability request invalid')

def status(payload):
    if len(payload)!=WORK_SIZE:return {}
    rawcode,action,slot,ability_rawcode,error,completed,changed,count,add_return,reserved=struct.unpack_from('<10I',payload,584)
    before,after=struct.unpack_from('<2Q',payload,624)
    handles=struct.unpack_from('<32Q',payload,640);codes=struct.unpack_from('<32I',payload,896)
    slots=lambda offset:[dict(handle=h,rawcode=r,charges=c) for h,r,c in
        (struct.unpack_from('<QIi',payload,offset+16*i) for i in range(6))]
    return dict(rawcode=rawcode,action=action,slot=slot,ability_rawcode=ability_rawcode,
        error=error,completed=completed,changed=changed,add_return=add_return,
        before_handle=before,after_handle=after,ability_count=count,
        abilities=[dict(handle=handles[i],rawcode=codes[i]) for i in range(min(count,32))],
        classic_before=slots(1024),classic_after=slots(1120))

def decode_work(payload,count):
    row=status(payload)
    if not row:raise ValueError('Incomplete item ability response')
    selection=selection_decode(payload[:480],count)
    target,item,base,unit_full,item_full=struct.unpack_from('<5Q',payload,544)
    if (row['error'] or row['completed']!=1 or row['ability_count']>32 or row['changed'] not in (0,1) or
        row['classic_before']!=row['classic_after'] or
        sum(r['handle']==target for r in selection['rows'])!=1 or
        row['classic_after'][row['slot']]['handle']!=item or
        (row['action']==1 and not row['after_handle'])):
        raise ValueError(f"物品能力挂载未通过读回：error={row['error']}, component={row['ability_rawcode']}")
    return dict(row,target_unit=target,item_handle=item,unit_full=unit_full,item_full=item_full,
                selection=selection,identity_verified=True)
