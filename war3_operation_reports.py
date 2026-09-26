"""Decode failure details without changing the operation success contract."""
import struct

def record_status(kind,evidence,report):
    if kind=='ability' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        from war3_ability_protocol import WORK_SIZE as ABILITY_WORK_SIZE
        if len(raw)==ABILITY_WORK_SIZE:
            changed,error,completed=struct.unpack_from('<3I',raw,532)
            target_unit=struct.unpack_from('<Q',raw,832)[0]
            report['ability_status']=dict(changed=changed,error=error,completed=completed,target_unit=target_unit)
    if kind=='ability_field' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==7688:
            changed,error,completed=struct.unpack_from('<3I',raw,624)
            report['ability_field_status']=dict(changed=changed,error=error,completed=completed)
    if kind=='item' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==6008:
            changed,error,completed,skipped=struct.unpack_from('<4I',raw,572)
            report['item_status']=dict(changed=changed,error=error,completed=completed,skipped=skipped)
            report['item_rows']=[dict(index=i,created=struct.unpack_from('<Q',raw,592+224*i+192)[0],
                status=struct.unpack_from('<I',raw,592+224*i+212)[0],
                trace=struct.unpack_from('<I',raw,592+224*i+220)[0])
                for i in range(min(24,struct.unpack_from('<I',raw,80)[0]))]
    if kind=='item_catalog' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)>=72:
            values=struct.unpack_from('<4Q10I',raw,0)
            report['item_catalog_status']=dict(
                action=values[4],total=values[10],created=values[11],
                error=values[12],completed=values[13],
            )
    if kind=='equipment' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==872:
            rawcode,action,error,completed,equipment_type,changed,rollback_error,_=struct.unpack_from('<8I',raw,584)
            report['equipment_status']=dict(rawcode=rawcode,action=action,error=error,
                completed=completed,equipment_type=equipment_type,changed=changed,
                rollback_error=rollback_error)
    if kind=='item_field' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==5136:
            changed,error,completed=struct.unpack_from('<3I',raw,552+12)
            report['item_field_status']=dict(changed=changed,error=error,completed=completed)
    if kind=='clone' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==1872:
            changed,error,completed=struct.unpack_from('<3I',raw,700)
            report['clone_status']=dict(changed=changed,error=error,completed=completed)
    if kind=='unit_action' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==1432:
            changed,error,completed=struct.unpack_from('<3I',raw,624)
            report['unit_action_status']=dict(changed=changed,error=error,completed=completed)
    if kind in ('position', 'position_target') and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==1312:
            changed,error,completed=struct.unpack_from('<3I',raw,528)
            report['position_status']=dict(changed=changed,error=error,completed=completed)
    if kind=='world' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==128:
            (action,diagnostic_phase,value,changed,error,completed,
             after0,after1,fault_low,fault_high)=struct.unpack_from('<10I',raw,88)
            report['world_status']=dict(
                action=action, value=value, changed=changed,
                error=error, completed=completed,
                after0=after0, after1=after1,
                diagnostic_phase=diagnostic_phase,
                fault_address=hex((fault_high<<32)|fault_low) if (fault_low or fault_high) else None,
            )
            if diagnostic_phase and (fault_low or fault_high):
                registers=struct.unpack_from('<8Q',raw,0)
                labels=(
                    ('first_rip','second_rip','first_access','first_address',
                     'second_access','second_address','is_fog_handler','is_mask_handler')
                    if diagnostic_phase<=2 else
                    ('first_rip','second_rip','rsp','rbx','rax','rcx','rdx','r8')
                )
                report['world_status']['fault_context']=dict(zip(
                    labels,
                    (hex(value) for value in registers),
                ))
    if kind=='bulk' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==624:
            changed,error,completed=struct.unpack_from('<3I',raw,608)
            report['bulk_status']=dict(changed=changed,error=error,completed=completed)
    if kind=='effect' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==1168:
            changed,error,completed=struct.unpack_from('<3I',raw,576)
            report['effect_status']=dict(changed=changed,error=error,completed=completed)
    if kind=='world_effect' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==656:
            attempts,error,successes,completed=struct.unpack_from('<4I',raw,636)
            report['world_effect_status']=dict(
                attempts=attempts, error=error,
                successes=successes, completed=completed,
            )
    if kind=='world_cast' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==760:
            issued,error,completed=struct.unpack_from('<3I',raw,724)
            source,ability_handle,target=struct.unpack_from('<3Q',raw,672)
            report['world_cast_status']=dict(
                action=struct.unpack_from('<I',raw,696)[0],
                source=source,ability_handle=ability_handle,target=target,
                added=struct.unpack_from('<I',raw,720)[0],
                issued=issued,error=error,completed=completed,
            )
    if kind=='spawn' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==128:
            changed,error,completed=struct.unpack_from('<3I',raw,56)
            report['spawn_status']=dict(changed=changed,error=error,completed=completed)
    if kind=='attack_speed' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==640:
            changed,error,completed=struct.unpack_from('<3I',raw,604)
            report['attack_speed_status']=dict(
                changed=changed,error=error,completed=completed,
                base_bits=hex(struct.unpack_from('<I',raw,576)[0]),
                factor_bits=hex(struct.unpack_from('<I',raw,580)[0]),
                effective_bits=hex(struct.unpack_from('<I',raw,584)[0]),
                true_aps_bits=hex(struct.unpack_from('<I',raw,588)[0]),
                after_base_bits=hex(struct.unpack_from('<I',raw,592)[0]),
                after_effective_bits=hex(struct.unpack_from('<I',raw,596)[0]),
                after_true_aps_bits=hex(struct.unpack_from('<I',raw,600)[0]),
            )
    if kind=='mouse' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==128:
            changed,error,completed=struct.unpack_from('<3I',raw,48)
            report['mouse_status']=dict(changed=changed,error=error,completed=completed)
