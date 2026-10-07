"""Inspect a temporary unowned item before any pickup/transfer event is emitted."""
import struct
from war3_selection_protocol import build_work as selection_work, validate_work as selection_validate, decode_work as selection_decode

WORK_SIZE = 600
ABI = struct.pack('<3I', 0x24268056, 216, WORK_SIZE)
SIGNATURES = (
    ('GetUnitX', '(Hunit;)R'), ('GetUnitY', '(Hunit;)R'),
    ('CreateItem', '(IRR)Hitem;'), ('GetItemTypeId', '(Hitem;)I'),
    ('GetItemEquipmentType', '(Hitem;)HequipmentType;'),
    ('GetItemType', '(Hitem;)Hitemtype;'),
    ('BlzGetItemBooleanField', '(Hitem;Hitembooleanfield;)B'), ('RemoveItem', '(Hitem;)V'),
)

def build_work(entries, tls, *, target, rawcode):
    handlers=[]
    for name, signature in SIGNATURES:
        entry=entries.get(name)
        if entry is None or (entry.name, entry.signature)!=(name, signature):
            raise ValueError('Item safety native signature differs: '+name)
        handlers.append(entry.handler)
    payload=selection_work(entries)+struct.pack('<10Q', *handlers, tls, target)+struct.pack('<I', rawcode)+bytes(36)
    validate_work(payload)
    return payload

def validate_work(payload):
    if len(payload)!=WORK_SIZE: raise ValueError('Item safety work size differs')
    selection_validate(payload[:480])
    handlers=struct.unpack_from('<10Q', payload,480)
    if any(not 0x10000<=value<0x800000000000 for value in handlers):
        raise ValueError('Item safety pointer/identity invalid')
    if handlers[8]%8 or not struct.unpack_from('<I',payload,560)[0] or any(payload[564:]):
        raise ValueError('Item safety request invalid')

def decode_work(payload, count):
    if len(payload)!=WORK_SIZE: raise ValueError('Item safety response incomplete')
    error,completed,skipped,equipment,droppable=struct.unpack_from('<5I',payload,564)
    removed,original_class=struct.unpack_from('<2I',payload,592)
    selection=selection_decode(payload[:480],count)
    target=struct.unpack_from('<Q',payload,552)[0]
    if sum(row['handle']==target for row in selection['rows'])!=1:
        raise ValueError('Item safety target changed')
    if error or completed!=1 or removed!=1 or original_class>8 or equipment>9 or droppable not in (0,1):
        raise ValueError(f'物品事前检查未完成：error={error}, removed={removed}')
    if skipped!=int(equipment==0 and droppable==0): raise ValueError('Item safety skip evidence differs')
    return dict(skipped=bool(skipped), rawcode=struct.unpack_from('<I',payload,560)[0],
                equipment_type=equipment,original_class=original_class,droppable=bool(droppable),removed_verified=True)

def failure_status(payload):
    if len(payload)!=WORK_SIZE:return None
    error,completed,skipped,equipment,droppable=struct.unpack_from('<5I',payload,564)
    temporary=struct.unpack_from('<Q',payload,584)[0]
    removed,original_class=struct.unpack_from('<2I',payload,592)
    if not error or completed:return None
    no_creation=error in (410,411,415) and not temporary and not removed
    cleaned=error in (412,413,416) and bool(temporary) and removed==1
    return dict(error=error,completed=completed,changed=0,cleanup=int(not (no_creation or cleaned)),
        session_continuable=bool((no_creation or cleaned) and not skipped))
