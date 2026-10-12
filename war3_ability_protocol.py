"""Current-engine ability batch ABI: query/add/remove/level and reversible diagnostic."""
import struct
from war3_selection_protocol import build_work as selection_work,validate_work as selection_validate,decode_work as selection_result
from war3_native_journal import WORK_SIZE as JOURNAL_SIZE,build_work as journal_work,validate_work as validate_journal
JOURNAL_OFFSET=1440
WORK_SIZE=JOURNAL_OFFSET+JOURNAL_SIZE
ABI=struct.pack('<3I',0x2426806c,216,WORK_SIZE)
SIGNATURES=(('UnitAddAbility','(Hunit;I)B'),('UnitRemoveAbility','(Hunit;I)B'),
 ('SetUnitAbilityLevel','(Hunit;II)I'),('GetUnitAbilityLevel','(Hunit;I)I'),
 ('BlzGetUnitAbility','(Hunit;I)Hability;'),('BlzGetAbilityId','(Hability;)I'),
 ('BlzGetUnitAbilityByIndex','(Hunit;I)Hability;'))

def build_work(entries,tls,rawcode,action=0,level=0,target_unit=0):
    pointers=[]
    for name,sig in SIGNATURES:
        entry=entries.get(name)
        if entry is None or entry.name!=name or entry.signature!=sig:raise ValueError('Ability signature differs: '+name)
        pointers.append(entry.handler)
    if isinstance(target_unit,bool) or not isinstance(target_unit,int) or not 0<=target_unit<=0xffffffffffffffff:
        raise ValueError('Invalid ability target')
    payload=(selection_work(entries)+struct.pack('<5Q6I',*pointers[:4],tls,rawcode,action,level,0,0,0)
             +bytes(288)+struct.pack('<4Q',target_unit,*pointers[4:])+bytes(576)+journal_work())
    validate_work(payload);return payload

def validate_work(payload):
    if len(payload)!=WORK_SIZE:raise ValueError(f'Ability work must contain {WORK_SIZE} bytes')
    selection_validate(payload[:480])
    validate_journal(payload[JOURNAL_OFFSET:])
    values=struct.unpack_from('<5Q6I',payload,480);ptrs=values[:4];tls=values[4]
    rawcode,action,level,changed,error,completed=values[5:]
    ptrs=ptrs+struct.unpack_from('<3Q',payload,840)
    if (any(not 0x10000<=p<0x800000000000 for p in ptrs) or len(set(ptrs))!=7
        or not 0x10000<=tls<0x800000000000 or tls%8 or not rawcode or action not in range(6)
        or not 0<=level<=100000 or (action in (3,4) and not level) or (action in (0,2,5) and level)
        or changed or error or completed or any(payload[544:832]) or any(payload[864:JOURNAL_OFFSET])):raise ValueError('Invalid ability batch arguments')

def decode_work(payload,count):
    if len(payload)!=WORK_SIZE:raise ValueError('Truncated ability work')
    selection=selection_result(payload[:480],count)
    rawcode,action,level,changed,error,completed=struct.unpack_from('<6I',payload,520)
    rows=[];valid=not error and completed==count and count>0
    target_unit=struct.unpack_from('<Q',payload,832)[0]
    if target_unit and sum(row['handle']==target_unit for row in selection['rows'])!=1:valid=False
    for i,row in enumerate(selection['rows']):
        before,after=struct.unpack_from('<2i',payload,544+8*i)
        intermediate=struct.unpack_from('<i',payload,736+4*i)[0]
        before_handle,after_handle,add_return,activation=struct.unpack_from('<2Q2I',payload,864+24*i)
        ok=before>=0 and after>=0
        if target_unit and row['handle']!=target_unit:ok &= after==before and intermediate==before
        elif action==0:ok &= after==before
        elif action==1:ok &= after==(level or before or 1) and (bool(after_handle) or before>0)
        elif action==2:ok &= after==0 and not after_handle
        elif action==3:ok &= (bool(before_handle) or before>0) and after==level and after_handle==before_handle
        elif action==4:ok &= after==before and after_handle==before_handle and (before>0 or intermediate==level)
        elif action==5:ok &= after>0 and bool(after_handle)
        else:ok=False
        valid &= ok;rows.append(dict(row,before=before,after=after,intermediate=intermediate,
            before_handle=before_handle,after_handle=after_handle,add_return=add_return,
            activation=activation))
    if changed>count:valid=False
    if not valid:raise ValueError(f'Ability batch incomplete: error={error}, completed={completed}/{count}, changed={changed}')
    return dict(rows=rows,rawcode=rawcode,action=action,changed=changed,count=count,target_unit=target_unit)
