"""Clone inventory areas and remap native talent records to new ability instances."""
import struct
import war3_clone_bound_protocol as bound
import war3_clone_protocol as clone

PREFIX_SIZE=bound.WORK_SIZE
HANDLERS_OFFSET=PREFIX_SIZE
LAYOUT_OFFSET=PREFIX_SIZE+96
ROWS_OFFSET=LAYOUT_OFFSET+24
ROW_SIZE=4656
WORK_SIZE=ROWS_OFFSET+24*ROW_SIZE
ABI=struct.pack('<3I',0x2426807C,216,WORK_SIZE)
SIGNATURES=(
    ('UnitInventorySize','(Hunit;)I'),('UnitExtendedInventorySize','(Hunit;)I'),
    ('UnitItemInBagSlot','(Hunit;I)Hitem;'),('ConvertLoadoutSlot','(I)Hloadoutslot;'),
    ('UnitItemInEquipmentSlot','(Hunit;Hloadoutslot;)Hitem;'),('UnitAddItem','(Hunit;Hitem;)B'),
    ('UnitDropItemSlot','(Hunit;Hitem;I)B'),('UnitEquipItem','(Hunit;Hitem;)B'),
    ('UnitUnequipItemFromSlot','(Hunit;Hloadoutslot;)Hitem;'),('BlzGetUnitAbility','(Hunit;I)Hability;'),
    ('GetHandleId','(Hhandle;)I'),('GetItemEquipmentType','(Hitem;)HequipmentType;'))
LAYOUT_NAMES=('definition_class','definition_levels','talent_points','talent_flags')

def build_work(entries,tls,*,base,unit_resolver,expected_sources,layout,
               flags=clone.CLONE_KEEP|clone.CLONE_COPY_ABILITIES|clone.CLONE_COPY_ITEMS,
               spawn_x_bits=0,spawn_y_bits=0):
    prefix=bound.build_work(entries,tls,base=base,unit_resolver=unit_resolver,
        expected_sources=expected_sources,flags=flags,spawn_x_bits=spawn_x_bits,spawn_y_bits=spawn_y_bits)
    handlers=[]
    for name,signature in SIGNATURES:
        entry=entries.get(name)
        if entry is None or entry.name!=name or entry.signature!=signature:
            raise ValueError('Stateful clone native signature differs: '+name)
        handlers.append(entry.handler)
    payload=prefix+struct.pack('<12Q6I',*handlers,*(layout[key] for key in LAYOUT_NAMES),0,0)+bytes(24*ROW_SIZE)
    validate_work(payload);return payload

def validate_work(payload):
    if len(payload)!=WORK_SIZE:raise ValueError('Clone state work size differs')
    bound.validate_work(payload[:PREFIX_SIZE])
    handlers=struct.unpack_from('<12Q',payload,HANDLERS_OFFSET)
    if any(not 0x10000<=handler<0x800000000000 for handler in handlers) or len(set(handlers))!=12:
        raise ValueError('Invalid clone state native handler')
    cls,levels,points,flags,completed,reserved=struct.unpack_from('<6I',payload,LAYOUT_OFFSET)
    if not all(0<value<0x10000 for value in (cls,levels,points,flags)) or flags>8 or completed or reserved:
        raise ValueError('Invalid clone state layout or progress')
    requested=struct.unpack_from('<I',payload,688)[0]
    if requested & (clone.CLONE_COPY_ABILITIES|clone.CLONE_COPY_ITEMS)!=(clone.CLONE_COPY_ABILITIES|clone.CLONE_COPY_ITEMS):
        raise ValueError('Stateful clone requires skills and inventory together')
    if any(payload[ROWS_OFFSET:]):raise ValueError('Clone state outputs must start empty')

def state_rows(payload,count):
    rows=[]
    for index in range(count):
        offset=ROWS_OFFSET+index*ROW_SIZE
        classic,bag,abilities,controller,tiers,points,stage,verified,inventory,equipment=struct.unpack_from('<10I',payload,offset)
        if classic>6 or bag>30 or abilities>128 or tiers>6 or points>18 or stage>6 or verified>1:
            raise ValueError('Invalid clone state row bounds')
        records=struct.unpack_from('<6Q',payload,offset+48)
        codes=struct.unpack_from('<6I',payload,offset+96)
        flags=struct.unpack_from('<6I',payload,offset+120)
        items=[]
        for slot in range(45):
            source,created,code,charges,kind,placed=struct.unpack_from('<2QIi2I',payload,offset+144+slot*32)
            items.append(dict(area='classic' if slot<6 else 'bag' if slot<36 else 'equipment',
                slot=slot if slot<6 else slot-6 if slot<36 else slot-36,source=source,clone=created,
                rawcode=code,charges=charges,equipment_type=kind,verified=bool(placed)))
        rows.append(dict(classic_size=classic,bag_size=bag,ability_count=abilities,
            talent_controller=controller,talent_points=points,talent_records=records[:tiers],
            talent_codes=codes[:tiers],talent_flags=flags[:tiers],stage=stage,verified=bool(verified),items=items))
    return rows

def decode_work(payload,count,*,expected_sources):
    if len(payload)!=WORK_SIZE:raise ValueError('Incomplete clone state result')
    result=bound.decode_work(payload[:PREFIX_SIZE],count,expected_sources=expected_sources,max_items=45)
    completed,reserved=struct.unpack_from('<2I',payload,LAYOUT_OFFSET+16)
    if completed!=count or reserved:raise ValueError('Clone runtime state did not complete')
    states=state_rows(payload,count)
    seen=set()
    sources={item['source'] for state in states for item in state['items'] if item['source']}
    for row,state in zip(result['rows'],states):
        if state['stage']!=6 or not state['verified']:raise ValueError('Clone state has not been verified')
        copied=0
        for item in state['items']:
            if item['source']:
                if not item['clone'] or item['clone'] in sources or item['clone'] in seen or not item['rawcode'] or item['charges']<0 or not item['verified']:
                    raise ValueError('Clone item identity or placement verification failed')
                seen.add(item['clone']);copied+=1
            elif any(item[key] for key in ('clone','rawcode','charges','equipment_type','verified')):
                raise ValueError('Empty source slot unexpectedly owns a clone item')
        if row['item_count']!=copied:raise ValueError('Clone inventory total differs from placed items')
        row['runtime_state']=state
    result['runtime_state_verified']=True
    return result

def failure_status(payload):
    if len(payload)!=WORK_SIZE:return None
    result=bound.failure_status(payload[:PREFIX_SIZE])
    if result is not None:
        count=struct.unpack_from('<I',payload,80)[0]
        try:result['runtime_state_rows']=state_rows(payload,count)
        except ValueError:result['runtime_state_rows']='invalid_or_incomplete'
    return result
