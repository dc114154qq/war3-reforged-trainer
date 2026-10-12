"""Decode failure details without changing the operation success contract."""
import struct

def record_status(kind,evidence,report):
    if kind=='direct_cast' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        from war3_direct_cast_protocol import WORK_SIZE
        if len(raw)==WORK_SIZE:
            action,rawcode=struct.unpack_from('<2I',raw,696)
            issued,error,completed=struct.unpack_from('<3I',raw,724)
            prior_cost,prior_cd,remaining,original_level,touched,activation,cast_order,expected_level=struct.unpack_from('<8I',raw,912)
            report['direct_cast_status']=dict(action=action,rawcode=rawcode,issued=issued,error=error,
                completed=completed,cleanup=struct.unpack_from('<I',raw,820)[0],
                prior_cost=prior_cost,prior_cooldown_field=prior_cd,prior_cooldown_remaining=remaining,
                original_level=original_level,touched=touched,activation=activation,
                cast_order=cast_order,expected_level=expected_level,
                source=struct.unpack_from('<Q',raw,672)[0],ability_handle=struct.unpack_from('<Q',raw,680)[0])
    if kind=='item_ability' and evidence.get('work_result_hex'):
        from war3_item_ability_protocol import status
        report['item_ability_status']=status(bytes.fromhex(evidence['work_result_hex']))
    if kind=='stat_details' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==1056:
            changed,error,completed,count=struct.unpack_from('<4I',raw,600)
            report['stat_details_status']=dict(error=error,completed=completed,
                changed=None if error else changed,present_count=count,
                diagnostic_stage=struct.unpack_from('<I',raw,1004)[0])
    if kind=='equipment_effect' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw) in (1488,1648,1672):
            error,completed,changed,cleanup=struct.unpack_from('<4I',raw,688)
            report['equipment_effect_status']=dict(error=error,completed=completed,
                changed=changed,cleanup=cleanup)
            if len(raw)>=1648:
                report['equipment_effect_status']['skip_code']=struct.unpack_from('<I',raw,1548)[0]
            if len(raw)==1672:
                retired,removed,called,released=struct.unpack_from('<4I',raw,1656)
                report['equipment_effect_status'].update(native_invalidated=retired,references_removed=removed,
                    destroy_called=called,owner_released=released)
    if kind=='item_safety' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==600:
            error,completed,skipped,equipment,droppable=struct.unpack_from('<5I',raw,564)
            report['item_safety_status']=dict(error=error,completed=completed,skipped=skipped,
                equipment_type=equipment,droppable=droppable,removed_verified=struct.unpack_from('<I',raw,592)[0],original_class=struct.unpack_from('<I',raw,596)[0])
    if kind=='game_speed' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==104:
            action,target,before,after,changed,error,completed,lock_before,lock_after,*reserved=struct.unpack_from('<12I',raw,56)
            status=dict(action=action,target=target,before=before,after=after,
                        error=error,completed=completed,lock_before=lock_before,lock_after=lock_after)
            # Only a fully observed, unchanged rejection is safe to retry manually.
            if (error==362 and action==1 and before==after and before in range(5)
                    and lock_before==lock_after and lock_before in (0,1)
                    and changed==0 and not any(reserved)):
                status['changed']=0
            report['game_speed_status']=status
    if kind=='ability' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        from war3_ability_protocol import WORK_SIZE as ABILITY_WORK_SIZE
        if len(raw)==ABILITY_WORK_SIZE:
            changed,error,completed=struct.unpack_from('<3I',raw,532)
            target_unit=struct.unpack_from('<Q',raw,832)[0]
            selected_count=struct.unpack_from('<I',raw,80)[0]
            rawcode,action,target_level=struct.unpack_from('<3I',raw,520)
            report['ability_status']=dict(changed=changed,error=error,completed=completed,target_unit=target_unit,
                rawcode=rawcode,action=action,target_level=target_level,selected_count=selected_count,
                rows=[dict(index=i,before=struct.unpack_from('<i',raw,544+8*i)[0],
                           after=struct.unpack_from('<i',raw,548+8*i)[0],
                           intermediate=struct.unpack_from('<i',raw,736+4*i)[0],
                           before_handle=struct.unpack_from('<Q',raw,864+24*i)[0],
                           after_handle=struct.unpack_from('<Q',raw,872+24*i)[0],
                           add_return=struct.unpack_from('<I',raw,880+24*i)[0],
                           activation=struct.unpack_from('<I',raw,884+24*i)[0])
                      for i in range(min(24,selected_count))])
    if kind=='ability_field' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==7688:
            changed,error,completed=struct.unpack_from('<3I',raw,624)
            report['ability_field_status']=dict(changed=changed,error=error,completed=completed)
    if kind=='item' and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        from war3_item_protocol import WORK_SIZE as ITEM_WORK_SIZE
        if len(raw)==ITEM_WORK_SIZE:
            changed,error,completed,skipped=struct.unpack_from('<4I',raw,572)
            report['item_status']=dict(changed=changed,error=error,completed=completed,skipped=skipped,
                creation_route=struct.unpack_from('<I',raw,6008)[0])
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
    if kind in ('clone','clone_bound') and evidence.get('work_result_hex'):
        raw=bytes.fromhex(evidence['work_result_hex'])
        if len(raw)==(2680 if kind=='clone_bound' else 1888):
            changed,error,completed=struct.unpack_from('<3I',raw,700)
            report['clone_status']=dict(changed=changed,error=error,completed=completed)
            from war3_clone_protocol import failure_status
            failure = failure_status(raw[:1888])
            if failure:
                report['clone_status'].update(failure)
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
        if len(raw) in (152,160):
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
