import struct
from war3_selection_protocol import build_work as selection_work, decode_work as selection_result, validate_work as selection_validate

WORK_SIZE = 648
ABI = struct.pack('<3I', 0x24268044, 216, WORK_SIZE)
SIGNATURES = (
    ('UnitAddAbility', '(Hunit;I)B'),
    ('UnitRemoveAbility', '(Hunit;I)B'),
    ('SetUnitAbilityLevel', '(Hunit;II)I'),
    ('GetUnitAbilityLevel', '(Hunit;I)I'),
    ('BlzStartUnitAbilityCooldown', '(Hunit;IR)V'),
    ('BlzGetUnitAbilityCooldown', '(Hunit;II)R'),
    ('BlzGetUnitAbilityCooldownRemaining', '(Hunit;I)R'),
)

def build_work(entries, tls, ability, order, target_unit=0):
    hs=[]
    for name, sig in SIGNATURES:
        e=entries.get(name)
        if e is None or e.signature != sig: raise ValueError('Cooldown probe signature differs: '+name)
        hs.append(e.handler)
    payload=selection_work(entries)+struct.pack('<7Q2Q6I',*hs,tls,target_unit,ability,order,0,0,0,0)+bytes(WORK_SIZE-576)
    validate_work(payload);return payload

def validate_work(payload):
    if len(payload)!=WORK_SIZE: raise ValueError('Cooldown probe size differs')
    selection_validate(payload[:480])
    hs=struct.unpack_from('<7Q',payload,480)
    if any(not 0x10000<=x<0x800000000000 for x in hs): raise ValueError('Cooldown probe handler invalid')
    target,ability,order,changed,error,completed,count=struct.unpack_from('<Q6I',payload,544)
    if not ability or not order or error or changed or completed or count: raise ValueError('Cooldown probe output not empty')
    if target and not 0x10000<=target<0x800000000000: raise ValueError('Cooldown probe target invalid')
    if any(payload[576:]): raise ValueError('Cooldown probe tail not empty')

def decode_work(payload,count):
    if len(payload)!=WORK_SIZE: raise ValueError('Cooldown probe response incomplete')
    selection=selection_result(payload[:480],count)
    target,ability,order,changed,error,completed,count_out=struct.unpack_from('<Q6I',payload,544)
    base,remaining,after_remaining=struct.unpack_from('<3f',payload,576)
    levels=struct.unpack_from('<2i',payload,588)
    if error or completed!=1 or count_out!=count or changed!=1:
        stage, fault = struct.unpack_from('<2I', payload, 600)
        raise ValueError(f'Cooldown probe failed error={error}, stage={stage}, fault=0x{fault:x}')
    if sum(r['handle']==target for r in selection['rows'])!=1: raise ValueError('Cooldown probe target changed')
    return dict(selection=selection,target_unit=target,ability=ability,order=order,base=base,
                remaining=remaining,after_remaining=after_remaining,levels=levels)
