"""Native ordinary-item equipment transaction with version-supplied layout."""
import struct
from war3_selection_protocol import build_work as selection_work, validate_work as selection_validate, decode_work as selection_decode

WORK_SIZE = 1672
ABI = struct.pack('<3I', 0x2426805b, 216, WORK_SIZE)
SIGNATURES = (
    ('GetItemTypeId', '(Hitem;)I'),
    ('GetItemEquipmentType', '(Hitem;)HequipmentType;'),
    ('GetItemType', '(Hitem;)Hitemtype;'),
    ('UnitEquipItem', '(Hunit;Hitem;)B'),
    ('UnitUnequipItemFromSlot', '(Hunit;Hloadoutslot;)Hitem;'),
    ('ConvertLoadoutSlot', '(I)Hloadoutslot;'),
    ('UnitItemInEquipmentSlot', '(Hunit;Hloadoutslot;)Hitem;'),
    ('UnitItemInBagSlot', '(Hunit;I)Hitem;'),
    ('UnitExtendedInventorySize', '(Hunit;)I'),
    ('BlzGetItemAbilityByIndex', '(Hitem;I)Hability;'),
    ('BlzGetAbilityId', '(Hability;)I'),
)
TRANSFER_SIGNATURES = (
    ('UnitRemoveItem', '(Hunit;Hitem;)V'),
    ('UnitAddItem', '(Hunit;Hitem;)B'),
    ('UnitItemInSlot', '(Hunit;I)Hitem;'),
    ('BlzGetItemBooleanField', '(Hitem;Hitembooleanfield;)B'),
    ('SetItemDroppable', '(Hitem;B)V'),
    ('RemoveItem', '(Hitem;)V'),
)
LAYOUT_NAMES = ('item_flags', 'item_class', 'item_equipment_type', 'equipment_count',
                'equipment_records', 'equipment_capacity', 'ability_owner', 'item_rawcode_mirror')
ORDINARY_CLASSES = (0,3,4,5,6,8)


def build_work(entries, tls, *, base, target, unit_full, item, item_full, equipment,
               action, slot, rawcode, original_class, flags, item_class, cached_type, layout,
               classic_inventory=0):
    handlers=[]
    for name, signature in SIGNATURES:
        e=entries.get(name)
        if e is None or (e.name,e.signature)!=(name,signature):
            raise ValueError('Equipment effect native signature differs: '+name)
        handlers.append(e.handler)
    transfer=[]
    for name,signature in TRANSFER_SIGNATURES:
        entry=entries.get(name)
        if entry is None or (entry.name,entry.signature)!=(name,signature):
            raise ValueError('Bag transfer native signature differs: '+name)
        transfer.append(entry.handler)
    payload=(selection_work(entries)+struct.pack('<18Q',*handlers,tls,base,target,unit_full,item,item_full,equipment)
             +struct.pack('<8I',*(layout[k] for k in LAYOUT_NAMES))
             +struct.pack('<8I',action,slot,rawcode,original_class,flags,item_class,cached_type,0)
             +bytes(1488-688)
             +struct.pack('<6Q', *transfer[:3], classic_inventory, *transfer[3:5])
             +bytes(112)+struct.pack('<Q',transfer[5])+bytes(16))
    validate_work(payload)
    return payload


def validate_work(payload):
    if len(payload)!=WORK_SIZE:raise ValueError('Equipment effect work size differs')
    selection_validate(payload[:480])
    q=struct.unpack_from('<18Q',payload,480)
    if any(not 0x10000<=p<0x800000000000 for p in q[:11]+q[11:14]+(q[15],q[17])):
        raise ValueError('Equipment effect pointers/handles invalid')
    if q[11]%8 or not q[14] or not q[16]:raise ValueError('Equipment effect full identity invalid')
    offsets=struct.unpack_from('<8I',payload,624)
    if any(not 0<o<=0x10000 for o in offsets):raise ValueError('Equipment effect layout invalid')
    action,slot,rawcode,original,flags,kind,cached,reserved=struct.unpack_from('<8I',payload,656)
    if (action not in (1,2,3,4,5,6,7) or slot >= (6 if action == 3 else 30 if action in (4,6) else 9)
            or not rawcode or original not in (range(9) if action in (4,5) else ORDINARY_CLASSES) or reserved):
        raise ValueError('Equipment effect request invalid')
    if action in (1,3) and (kind!=original or cached or flags&0x4000):
        raise ValueError('Ordinary item was already classified/equipped')
    if action==2 and (not flags&0x4000 or not (
            (kind==7 and cached in range(1,9)) or (kind==original and cached==0))):
        raise ValueError('Ordinary equipment classification differs')
    if action==6 and (not flags&0x4000 or kind!=original or cached):
        raise ValueError('Inherited bag item classification differs')
    if action==7 and (kind!=original or cached):
        raise ValueError('Inherited equipment repair classification differs')
    if any(payload[688:1488]):raise ValueError('Equipment effect outputs must be zero')
    transfer=struct.unpack_from('<3Q',payload,1488)
    if any(not 0x10000<=p<0x800000000000 for p in transfer + struct.unpack_from('<2Q',payload,1520)):
        raise ValueError('Bag transfer handlers invalid')
    classic_inventory=struct.unpack_from('<Q',payload,1512)[0]
    if action==3 and not 0x10000<=classic_inventory<0x800000000000:
        raise ValueError('Bag transfer inventory identity invalid')
    if action!=3 and classic_inventory:raise ValueError('Unexpected classic inventory identity')
    remove=struct.unpack_from('<Q',payload,1648)[0]
    if not 0x10000<=remove<0x800000000000:
        raise ValueError('Item destruction handler invalid')
    if any(payload[1536:1648]) or any(payload[1656:]):
        raise ValueError('Equipment transaction evidence must be zero')


def decode_work(payload,count):
    if len(payload)!=WORK_SIZE:raise ValueError('Equipment effect response incomplete')
    values=struct.unpack_from('<12I',payload,688)
    error,completed,changed,cleanup,*_=values
    if error or completed!=1 or cleanup or values[10]>32:
        raise ValueError(f'普通物品原生装备事务失败：error={error}, completed={completed}, cleanup={cleanup}')
    droppable_before,droppable_after,rollback,skip_code=struct.unpack_from('<4I',payload,1536)
    if droppable_before not in (0,1) or droppable_before!=droppable_after or rollback or skip_code not in (0,1):
        raise ValueError('Item droppable state was not preserved')
    before=struct.unpack_from('<9Q',payload,736)
    after=struct.unpack_from('<9Q',payload,808)
    bag_before=struct.unpack_from('<30Q',payload,880)
    bag_after=struct.unpack_from('<30Q',payload,1120)
    action,slot,rawcode,original,*_=struct.unpack_from('<8I',payload,656)
    item=struct.unpack_from('<Q',payload,600)[0]
    target=struct.unpack_from('<Q',payload,584)[0]
    selection=selection_decode(payload[:480],count)
    if sum(row['handle']==target for row in selection['rows'])!=1:
        raise ValueError('普通物品装备目标身份已变化')
    if skip_code:
        untouched=(not changed and droppable_before==0 and before==after and bag_before==bag_after
            and struct.unpack_from('<6Q',payload,1552)==struct.unpack_from('<6Q',payload,1600)
            and values[4:7]==values[7:10])
        if not untouched:raise ValueError('Item skip changed inventory or classifier')
        return dict(action=action,slot=slot,rawcode=rawcode,changed=0,cleanup=0,
                    skipped=True,reason_code='protected_legacy_item',before=before,after=after,
                    bag_before=bag_before,bag_after=bag_after,
                    droppable_before=droppable_before,droppable_after=droppable_after)
    if changed!=1:raise ValueError('Equipment change was not verified')
    if action in (4,5):
        retired,cleared,called,owner_released=struct.unpack_from('<4I',payload,1656)
        valid=(retired==cleared==called==1 and owner_released in (0,1) and item not in after and item not in bag_after)
        if action==4:
            valid &= bag_before[slot]==item and before==after and all(
                a==(0 if i==slot else b) for i,(b,a) in enumerate(zip(bag_before,bag_after)))
        else:
            valid &= before[slot]==item and bag_before==bag_after and all(
                a==(0 if i==slot else b) for i,(b,a) in enumerate(zip(before,after)))
    elif action==7:
        valid=(before==after and bag_before==bag_after and before[slot]==item and
               before.count(item)==1 and values[7]==values[4]|0x4000 and values[8]==7 and
               values[9]==(1,2,3,4,5,5,6,7,8)[slot])
    elif action==6:
        valid=(before==after and bag_before[slot]==item and bag_before.count(item)==bag_after.count(item)==1
               and values[8]==original and values[9]==0 and not values[7]&0x4000)
    elif action==3:
        valid=(item not in bag_before and bag_after.count(item)==1 and before==after
               and values[8]==original and values[9]==0 and not values[7]&0x4000)
    elif action==1:
        kind=(1,2,3,4,5,5,6,7,8)[slot]
        valid=(not before[slot] and after[slot]==item and bag_before.count(item)==1 and item not in bag_after
               and values[7]&0x4000 and values[8]==7 and values[9]==kind)
    else:
        valid=(before[slot]==item and not after[slot] and item not in bag_before and bag_after.count(item)==1
               and values[8]==original and values[9]==0 and not values[7]&0x4000)
    if not valid or any(before[i]!=after[i] for i in range(9) if i!=slot):
        raise ValueError('普通物品原生装备槽位后置条件不一致：'
            f'action={action}, slot={slot}, item=0x{item:x}, '
            f'bag_matches={bag_before.count(item)}->{bag_after.count(item)}, '
            f'equipped_matches={before.count(item)}->{after.count(item)}, '
            f'class={values[5]}->{values[8]}, type={values[6]}->{values[9]}, '
            f'flags=0x{values[4]:x}->0x{values[7]:x}')
    if sorted(x for x in bag_before if x and x!=item)!=sorted(x for x in bag_after if x and x!=item):
        raise ValueError('普通物品装备事务改变了其他背包实例')
    classic_before=struct.unpack_from('<6Q',payload,1552)
    classic_after=struct.unpack_from('<6Q',payload,1600)
    if action != 3 and classic_before != classic_after:
        raise ValueError('Equipment transaction changed classic inventory')
    return dict(action=action,slot=slot,rawcode=rawcode,changed=changed,cleanup=cleanup,
                destruction_evidence=(dict(native_invalidated=bool(retired),references_removed=bool(cleared),
                    owner_released=bool(owner_released)) if action in (4,5) else None),
                ability_ids=struct.unpack_from('<32I',payload,1360)[:values[10]],
                before=before,after=after,bag_before=bag_before,bag_after=bag_after,
                flags_before=values[4],flags_after=values[7],
                droppable_before=droppable_before,droppable_after=droppable_after)


def failure_status(payload):
    """Accept only complete rollback evidence, never a native return code alone."""
    if len(payload)!=WORK_SIZE:return None
    error,completed,changed,cleanup,*values=struct.unpack_from('<12I',payload,688)
    before,after,rolled_back,reserved=struct.unpack_from('<4I',payload,1536)
    if not error or completed:return None
    unchanged=(struct.unpack_from('<9Q',payload,736)==struct.unpack_from('<9Q',payload,808)
        and sorted(struct.unpack_from('<30Q',payload,880))==sorted(struct.unpack_from('<30Q',payload,1120))
        and struct.unpack_from('<6Q',payload,1552)==struct.unpack_from('<6Q',payload,1600)
        and values[1:3]==values[4:6] and values[0]&0x4000==values[3]&0x4000
        and before in (0,1) and before==after)
    return dict(error=error,completed=completed,changed=changed,cleanup=cleanup,
        session_continuable=bool(rolled_back==1 and not reserved and not changed and not cleanup and unchanged))
