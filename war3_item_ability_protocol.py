"""Inspect/attach a capability to the same owned item; no item replacement."""
import struct
from war3_selection_protocol import build_work as selection_work, validate_work as selection_validate, decode_work as selection_decode

from war3_native_journal import WORK_SIZE as JOURNAL_SIZE,build_work as journal_work,validate_work as validate_journal
JOURNAL_OFFSET=1216
WORK_SIZE=JOURNAL_OFFSET+JOURNAL_SIZE
ABI=struct.pack('<3I',0x24268070,216,WORK_SIZE)
ERROR_REASONS={
    440:'请求参数无效',441:'当前选择与目标不一致',442:'经典物品栏快照无效',
    443:'物品附带能力列表无效',444:'物品能力查询结果不一致',445:'新增能力未生效',
    446:'检查期间物品栏发生变化',447:'原有物品能力发生变化',
    448:'单位完整身份已失效',449:'物品完整身份已失效',450:'单位身份字段不可读',
    451:'物品身份字段不可读',452:'单位身份发生变化',453:'物品身份发生变化',
    454:'物品编号副本不一致',455:'物品已离开原槽位',456:'原生物品编号不一致',
}
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
        rawcode,action,slot,ability_rawcode,0,0,0,0,0,0)+bytes(JOURNAL_OFFSET-624)+journal_work())
    validate_work(payload)
    return payload

def validate_work(payload):
    if len(payload)!=WORK_SIZE:raise ValueError('Item ability work size differs')
    selection_validate(payload[:480])
    validate_journal(payload[JOURNAL_OFFSET:])
    pointers=struct.unpack_from('<13Q',payload,480)
    if (any(not 0x10000<=v<0x800000000000 for v in pointers[:11]) or pointers[7]%8
            or not pointers[11] or not pointers[12]):
        raise ValueError('Item ability identity invalid')
    rawcode,action,slot,ability_rawcode,*output=struct.unpack_from('<10I',payload,584)
    if (not rawcode or action not in (0,1) or slot>=6 or
            (action==1 and not ability_rawcode) or any(output) or any(payload[624:JOURNAL_OFFSET])):
        raise ValueError('Item ability request invalid')

def status(payload):
    if len(payload)!=WORK_SIZE:return {}
    rawcode,action,slot,ability_rawcode,error,completed,changed,count,add_return,reserved=struct.unpack_from('<10I',payload,584)
    before,after=struct.unpack_from('<2Q',payload,624)
    handles=struct.unpack_from('<32Q',payload,640);codes=struct.unpack_from('<32I',payload,896)
    slots=lambda offset:[dict(handle=h,rawcode=r,charges=c) for h,r,c in
        (struct.unpack_from('<QIi',payload,offset+16*i) for i in range(6))]
    return dict(rawcode=rawcode,action=action,slot=slot,ability_rawcode=ability_rawcode,
        error=error,error_reason=ERROR_REASONS.get(error,''),completed=completed,changed=changed,add_return=add_return,
        lookup_evidence=dict(before=dict(direct=bool(reserved&1),indexed=bool(reserved&2)),
                             after=dict(direct=bool(reserved&4),indexed=bool(reserved&8))),
        before_handle=before,after_handle=after,ability_count=count,
        abilities=[dict(handle=handles[i],rawcode=codes[i]) for i in range(min(count,32))],
        classic_before=slots(1024),classic_after=slots(1120))

def decode_work(payload,count):
    row=status(payload)
    if not row:raise ValueError('Incomplete item ability response')
    selection=selection_decode(payload[:480],count)
    target,item,base,unit_full,item_full=struct.unpack_from('<5Q',payload,544)
    flags=struct.unpack_from('<I',payload,620)[0]
    if (row['error'] or row['completed']!=1 or row['ability_count']>32 or row['changed'] not in (0,1) or flags&~15 or
        row['classic_before']!=row['classic_after'] or
        sum(r['handle']==target for r in selection['rows'])!=1 or
        row['classic_after'][row['slot']]['handle']!=item or
        (row['action']==1 and not row['after_handle'])):
        operation='物品能力检查' if row['action']==0 else '物品能力挂载'
        reason=row['error_reason'] or '结果未通过一致性检查'
        raise ValueError(f"{operation}未通过读回：{reason}（错误 {row['error']}，能力 {row['ability_rawcode']}）")
    return dict(row,target_unit=target,item_handle=item,unit_full=unit_full,item_full=item_full,
                selection=selection,identity_verified=True)
