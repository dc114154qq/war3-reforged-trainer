"""Current item-batch protocol; complete six-slot before/after snapshots."""
import struct
from war3_selection_protocol import build_work as select_work,validate_work as validate_selection,decode_work as decode_selection
WORK_SIZE=5968
ABI=struct.pack('<3I',0x24268014,216,WORK_SIZE)
SIGNATURES=(('UnitAddItemById','(Hunit;I)Hitem;'),('UnitAddItemToSlotById','(Hunit;II)B'),('UnitItemInSlot','(Hunit;I)Hitem;'),
 ('UnitInventorySize','(Hunit;)I'),('GetItemTypeId','(Hitem;)I'),('GetItemCharges','(Hitem;)I'),
 ('SetItemCharges','(Hitem;I)V'),('RemoveItem','(Hitem;)V'),('UnitRemoveItem','(Hunit;Hitem;)V'))
OPTIONAL_SIGNATURES=('UnitAddItemToSlotById',)

def required_signatures(action):
    return SIGNATURES if action==7 else tuple(item for item in SIGNATURES if item[0] not in OPTIONAL_SIGNATURES)

def build_work(entries,tls,action=0,rawcode=0,charges=-1):
    pointers=[]
    for name,sig in SIGNATURES:
        e=entries.get(name)
        if e is None or e.name!=name or e.signature!=sig:
            if name in OPTIONAL_SIGNATURES and action!=7:
                pointers.append(0)
                continue
            raise ValueError('Item native signature differs: '+name)
        pointers.append(e.handler)
    payload=select_work(entries)+struct.pack('<10Q2Ii5I',*pointers,tls,rawcode,action,charges,0,0,0,0,0)+bytes(5376)
    validate_work(payload);return payload

def validate_work(payload):
    if len(payload)!=WORK_SIZE:raise ValueError('Item batch work must contain 5968 bytes')
    validate_selection(payload[:480]);v=struct.unpack_from('<10Q2Ii5I',payload,480)
    handlers=v[:9]
    action=v[12]
    required_indexes=range(9) if action==7 else (index for index in range(9) if index!=1)
    if any(not 0x10000<=handlers[index]<0x800000000000 for index in required_indexes):
        raise ValueError('Invalid item native pointers or TLS')
    present=[pointer for pointer in handlers if pointer]
    if len(set(present))!=len(present) or v[9]%8:
        raise ValueError('Invalid item native pointers or TLS')
    rawcode,action,charges,*outputs=v[10:]
    if action not in (0,1,2,3,4,5,6,7) or (action in (1,3,7) and not rawcode) or (action in (0,2,4,5,6) and rawcode):
        raise ValueError('Invalid item action/rawcode')
    if not -1<=charges<=1000000000 or (action in (2,3) and charges<1) or (action in (0,4,5,6) and charges!=-1) or (action==7 and not 0<=charges<6):
        raise ValueError('Invalid item charges')
    if any(outputs) or any(payload[592:]):raise ValueError('Item outputs must be zero')

def decode_work(payload,count):
    if len(payload)!=WORK_SIZE:raise ValueError('Incomplete item batch')
    selection=decode_selection(payload[:480],count)
    rawcode,action,target,changed,error,completed,skipped,reserved=struct.unpack_from('<2Ii5I',payload,560)
    rows=[];valid=bool(not error and not reserved and count and completed==count and skipped<=count)
    for i,unit in enumerate(selection['rows']):
        offset=592+224*i
        def snapshot(start):
            out=[]
            for slot in range(6):
                handle,code,charges=struct.unpack_from('<QIi',payload,start+16*slot)
                if (handle==0 and (code or charges)) or (handle and (not code or charges<0)):
                    raise ValueError('Invalid item snapshot')
                out.append(dict(slot=slot,handle=handle,rawcode=code,charges=charges))
            return out
        before=snapshot(offset);after=snapshot(offset+96)
        created,created_type,created_charges,size,status,slot,row_reserved=struct.unpack_from('<QIi4I',payload,offset+192)
        valid &= size<=6 and (action==5 or not row_reserved)
        if action==0:valid &= status==1 and before==after and not created
        elif action==2:
            valid &= status==4 and not created
            for b,a in zip(before,after):valid &= b['handle']==a['handle'] and b['rawcode']==a['rawcode'] and a['charges']==(target if b['handle'] else 0)
        elif action==3:valid &= status in (5,6) and before==after and (status==6 or bool(created and created_type==rawcode and created_charges==target))
        elif action==4:valid &= status==7 and not created and all(not item['handle'] for item in after)
        elif action==6:valid &= status==8 and not created and all(not item['handle'] for item in after)
        elif action==5:
            valid &= status in (6,9)
            for b,a in zip(before,after):
                if b['handle']:valid &= b==a
            if status==6:
                valid &= not created and not row_reserved
            else:
                valid &= bool(created and row_reserved > 0 and created_type)
        elif action==1:
            valid &= status in (2,3) and bool(created and created_type==rawcode and (target<0 or created_charges==target))
            for b,a in zip(before,after):
                if b['handle']:valid &= b==a
                else:valid &= a['handle'] in (0,created)
            if status==2:valid &= slot<6 and after[slot]['handle']==created
            if status==3:valid &= all(x['handle']!=created for x in after)
        elif action==7:
            valid &= 0<=target<6 and status in (10,11)
            valid &= after[target]['rawcode']==rawcode
            valid &= all(before[index]==after[index] for index in range(6) if index!=target)
            if status==10:
                valid &= bool(created) and slot==target and created_type==rawcode
            else:
                valid &= not created and before[target]['rawcode']==rawcode
        rows.append(dict(unit,inventory_size=size,before=before,after=after,created=created,created_type=created_type,created_charges=created_charges,status=status,created_slot=slot,reserved=row_reserved))
    if action==0:expected_changed=0
    elif action==1:expected_changed=count
    elif action==2:expected_changed=sum(bool(b['handle']) and b['charges']!=a['charges'] for r in rows for b,a in zip(r['before'],r['after']))
    elif action in (4,6):expected_changed=sum(bool(item['handle']) for r in rows for item in r['before'])
    elif action==5:expected_changed=sum(r['reserved'] for r in rows if r['status']==9)
    elif action==7:expected_changed=sum(r['before'][target]['rawcode']!=rawcode for r in rows)
    else:expected_changed=sum(r['status']==5 for r in rows)
    if changed!=expected_changed:valid=False
    created_handles=[r['created'] for r in rows if r['created']]
    originals={item['handle'] for r in rows for item in r['before'] if item['handle']}
    if len(set(created_handles))!=len(created_handles) or originals.intersection(created_handles):valid=False
    if sum(r['status']==6 for r in rows)!=skipped:valid=False
    if not valid:raise ValueError(f'Item batch incomplete: error={error}, completed={completed}/{count}, changed={changed}')
    return dict(rows=rows,count=count,changed=changed,skipped=skipped,
                stored=sum(r['status']==2 for r in rows),ground=sum(r['status']==3 for r in rows))
