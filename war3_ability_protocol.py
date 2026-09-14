"""Current-engine ability batch ABI: query/add/remove/level and reversible diagnostic."""
import struct
from war3_selection_protocol import build_work as selection_work,validate_work as selection_validate,decode_work as selection_result
WORK_SIZE=832
ABI=struct.pack('<3I',0x24268011,216,WORK_SIZE)
SIGNATURES=(('UnitAddAbility','(Hunit;I)B'),('UnitRemoveAbility','(Hunit;I)B'),
 ('SetUnitAbilityLevel','(Hunit;II)I'),('GetUnitAbilityLevel','(Hunit;I)I'))

def build_work(entries,tls,rawcode,action=0,level=0):
    pointers=[]
    for name,sig in SIGNATURES:
        entry=entries.get(name)
        if entry is None or entry.name!=name or entry.signature!=sig:raise ValueError('Ability signature differs: '+name)
        pointers.append(entry.handler)
    payload=selection_work(entries)+struct.pack('<5Q6I',*pointers,tls,rawcode,action,level,0,0,0)+bytes(288)
    validate_work(payload);return payload

def validate_work(payload):
    if len(payload)!=WORK_SIZE:raise ValueError('Ability work must contain 832 bytes')
    selection_validate(payload[:480])
    values=struct.unpack_from('<5Q6I',payload,480);ptrs=values[:4];tls=values[4]
    rawcode,action,level,changed,error,completed=values[5:]
    if (any(not 0x10000<=p<0x800000000000 for p in ptrs) or len(set(ptrs))!=4
        or not 0x10000<=tls<0x800000000000 or tls%8 or not rawcode or action not in range(5)
        or not 0<=level<=100000 or (action in (3,4) and not level) or (action in (0,2) and level)
        or changed or error or completed or any(payload[544:])):raise ValueError('Invalid ability batch arguments')

def decode_work(payload,count):
    if len(payload)!=WORK_SIZE:raise ValueError('Truncated ability work')
    selection=selection_result(payload[:480],count)
    rawcode,action,level,changed,error,completed=struct.unpack_from('<6I',payload,520)
    rows=[];valid=not error and completed==count and count>0
    for i,row in enumerate(selection['rows']):
        before,after=struct.unpack_from('<2i',payload,544+8*i)
        intermediate=struct.unpack_from('<i',payload,736+4*i)[0]
        ok=before>=0 and after>=0
        if action==0:ok &= after==before
        elif action==1:ok &= after==(level or before or 1)
        elif action==2:ok &= after==0
        elif action==3:ok &= before>0 and after==level
        elif action==4:ok &= after==before and (before>0 or intermediate==level)
        else:ok=False
        valid &= ok;rows.append(dict(row,before=before,after=after,intermediate=intermediate))
    if changed>count:valid=False
    if not valid:raise ValueError(f'Ability batch incomplete: error={error}, completed={completed}/{count}, changed={changed}')
    return dict(rows=rows,rawcode=rawcode,action=action,changed=changed,count=count)
