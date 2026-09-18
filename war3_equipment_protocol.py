"""3.0 loadout equipment is separate from the six ordinary inventory slots."""
import struct
from war3_selection_protocol import build_work as selection,validate_work as validate_selection,decode_work as decode_selection

WORK_SIZE=872
ABI=struct.pack('<3I',0x2426802E,216,WORK_SIZE)
SIGNATURES=(('CreateItem','(IRR)Hitem;'),('GetItemTypeId','(Hitem;)I'),
 ('GetItemEquipmentType','(Hitem;)HequipmentType;'),('ConvertLoadoutSlot','(I)Hloadoutslot;'),
 ('UnitItemInEquipmentSlot','(Hunit;Hloadoutslot;)Hitem;'),('UnitEquipItem','(Hunit;Hitem;)B'),
 ('UnitUnequipItem','(Hunit;Hitem;)V'),('RemoveItem','(Hitem;)V'),
 ('UnitItemInSlot','(Hunit;I)Hitem;'),('UnitInventorySize','(Hunit;)I'))

def build_work(entries,tls,rawcode=0,action=0,target_unit=0,created=0,replaced=0):
    handlers=[]
    for name,sig in SIGNATURES:
        e=entries.get(name)
        if e is None or e.signature!=sig:raise ValueError('Equipment signature differs: '+name)
        handlers.append(e.handler)
    payload=selection(entries)+struct.pack('<11Q2Q8I2Q',*handlers,tls,target_unit,created,
        rawcode,action,0,0,0,0,0,0,0,replaced)+bytes(240)
    validate_work(payload);return payload

def validate_work(payload):
    if len(payload)!=WORK_SIZE:raise ValueError('Equipment payload size differs')
    validate_selection(payload[:480])
    h=struct.unpack_from('<11Q',payload,480)
    if any(not 0x10000<=p<0x800000000000 for p in h) or h[-1]%8:
        raise ValueError('Equipment handler/TLS invalid')
    target,expected,rawcode,action,error,done,kind,changed,rollback,reserved,created,old=struct.unpack_from('<2Q8I2Q',payload,568)
    if action not in (0,1,2) or (action!=2 and not rawcode) or (action and not target):
        raise ValueError('Equipment request invalid')
    if (action!=2 and (expected or old)) or (action==2 and (not expected or rawcode)):
        raise ValueError('Equipment restore identity invalid')
    if any((error,done,kind,changed,rollback,reserved,created)) or any(payload[632:]):
        raise ValueError('Equipment output must start empty')

def decode_work(payload,count):
    if len(payload)!=WORK_SIZE:raise ValueError('Equipment response size differs')
    selected=decode_selection(payload[:480],count)
    target,expected,rawcode,action,error,done,kind,changed,rollback,reserved,created,old=struct.unpack_from('<2Q8I2Q',payload,568)
    before=struct.unpack_from('<9Q',payload,632);after=struct.unpack_from('<9Q',payload,704)
    inventory_before=struct.unpack_from('<6Q',payload,776);inventory_after=struct.unpack_from('<6Q',payload,824)
    if error or rollback or done!=1 or reserved:
        raise ValueError(f'Equipment operation failed: error={error}, rollback_error={rollback}, completed={done}')
    if action:
        if sum(r['handle']==target for r in selected['rows'])!=1 or inventory_before!=inventory_after:
            raise ValueError('Equipment operation changed selection or ordinary inventory')
        differences=[i for i,(b,a) in enumerate(zip(before,after)) if b!=a]
        if len(differences)!=1 or changed!=1:raise ValueError('Equipment slot changes differ')
        slot=differences[0]
        if action==1 and (not created or after[slot]!=created or before[slot]!=old or not 1<=kind<=8):
            raise ValueError('Equipment insertion was not verified')
        if action==2 and (before[slot]!=expected or after[slot]!=old):
            raise ValueError('Equipment restoration was not verified')
    else:
        slot=None
        if changed or created or not 0<=kind<=8:raise ValueError('Invalid equipment classification')
    return dict(action=action,target_unit=target,rawcode=rawcode,equipment_type=kind,slot=slot,
        changed=changed,created=created,replaced=old,before=before,after=after,
        inventory_before=inventory_before,inventory_after=inventory_after)
