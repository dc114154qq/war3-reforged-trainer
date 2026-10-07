"""Generate equipment from a saved layout; never reuse serialized handles."""

def plan_choices(host):
    """Distinguish identically named saved plans without binding their targets."""
    records=[r for key,per_target in getattr(host,'_extension_saved_loadouts',{}).items()
             if int(key[0])==int(getattr(host,'pid',0)) for r in per_target.values()]
    choices={}
    for index,record in enumerate(records,1):
        name=record['name']
        if sum(r['name']==name for r in records)>1:
            code=int(record.get('unit_type_id',0)).to_bytes(4,'big').decode('ascii','replace')
            name=f'{name} [{code} #{index}]'
        if name in choices:raise ValueError('Saved plan display identities collide')
        choices[name]=record
    return choices


def run_loadout_batch(host, name, action, record=None):
    if action == 'restore' and name:
        choice=plan_choices(host).get(name)
        if choice is not None:name=choice['name']
    initial = host.extension_snapshot_24268()
    last = initial
    done, skipped, failures, item_skips, failure_explanations = [], [], [], [], []
    rows = tuple(initial.get('selection', {}).get('rows', ()))
    candidates = tuple(host._selected_candidates_snapshot(None)) if action != 'save' else ()
    if not rows:
        raise RuntimeError('No selected units')
    for row in rows:
        handle = int(row['handle'])
        try:
            if int(row.get('level', 0)) <= 0:
                skipped.append((handle, 'Not a hero'))
                continue
            candidate = None
            if action != 'save':
                matches = [c for c, h in candidates if int(h) == handle]
                if not matches:
                    # The external fallback returns full object identities;
                    # bind only an unambiguous type across both snapshots.
                    same_type = [r for r in rows if int(r['rawcode']) == int(row['rawcode'])]
                    if len(same_type) == 1:
                        matches = [c for c, _ in candidates if int(c.unit_type_id) == int(row['rawcode'])]
                if len(matches) != 1:
                    raise RuntimeError('Hero native/full identity mapping is not unique; no restore was issued')
                candidate = matches[0]
            with host._bound_elephant_selection(candidate, handle):
                current = host.extension_snapshot_24268()
                row = next((row for row in current.get('selection', {}).get('rows', ())
                            if int(row['handle']) == int(handle)), {})
                if int(row.get('level', 0)) <= 0:
                    skipped.append((handle, 'Not a hero'))
                    continue
                if int(current['bag_size']) != 30:
                    skipped.append((handle, 'No extended inventory'))
                    continue
                if action == 'save':
                    host._extension_pending_loadout_name = name
                    last = host.save_extension_loadout_24268()
                elif action == 'restore':
                    records = [record for per_target in getattr(host, '_extension_saved_loadouts', {}).values()
                               for record in per_target.values()
                               if int(record.get('unit_type_id', 0)) == int(row['rawcode'])
                               and (not name or record['name'] == name)]
                    if len(records) != 1:
                        skipped.append((handle, 'No unique matching saved hero'))
                        continue
                    host._extension_pending_restore_record = records[0]
                    host._extension_pending_restore_name = records[0]['name']
                    last = host.restore_extension_loadout_24268()
                else:
                    if record is None:
                        raise ValueError('A selected plan is required for apply')
                    host._extension_pending_restore_record = record
                    host._extension_pending_restore_name = record['name']
                    last = host.restore_extension_loadout_24268()
                item_skips.extend((handle,entry) for entry in last.get('loadout_item_skips',()))
                done.append(handle)
        except Exception as exc:
            from war3_error_messages import describe_error
            failures.append((handle, str(exc)))
            failure_explanations.append(describe_error(exc))
    last['loadout_batch'] = {
        'saved' if action == 'save' else 'restored': tuple(done),
        'skipped': tuple(skipped), 'failures': tuple(failures), 'item_skips': tuple(item_skips),
        'failure_explanations': tuple(failure_explanations),
    }
    return last


def regenerate_loadout(host, saved, before, slot_types):
    target = int(before['target_unit'])
    layout = tuple(saved['equipment'])
    if len(layout) != len(slot_types):
        raise ValueError('Invalid saved equipment slot count')
    charges = tuple(saved.get('equipment_charges', (0,) * len(layout)))
    if len(charges) != len(layout) or any(not 0 <= int(v) <= 1_000_000_000 for v in charges):
        raise ValueError('Invalid saved item charges')
    needed = sum(bool(int(row[1])) for row in layout)
    old_layout = tuple((int(row['handle']), int(row['rawcode'])) for row in before['equipment'])
    free = int(before['bag_size']) - sum(bool(int(row['handle'])) for row in before['bag'])
    # Reserve staging and rollback capacity before creating anything. Old
    # equipment is preserved in the bag, including after a successful restore.
    if free < needed + sum(bool(handle) for handle, _ in old_layout):
        raise RuntimeError('扩展背包空位不足以生成套装并保留原装备，未开始恢复')
    requires_any = bool(saved.get('requires_any_slot')) or any(
        int(row[1]) and (len(row) < 3 or int(row[2]) not in (slot_types[index], 9))
        for index, row in enumerate(layout)
    )
    key = (int(getattr(host, 'pid', 0)), target)
    if requires_any and not getattr(host, '_extension_any_slot_enabled', {}).get(key):
        host.set_extension_equipment_any_slot_24268(True)
    created = []
    desired = []
    item_skips = []
    expected_charges = list(charges)
    try:
        for slot, row in enumerate(layout):
            rawcode = int(row[1])
            # Preserve a protected old instance before generating a replacement,
            # rather than discovering the restriction after other slots moved.
            if old_layout[slot][0]:
                from war3_services.equipment_effects import preflight_creation, skipped_snapshot
                check=preflight_creation(host,old_layout[slot][1],target)
                if check.get('skipped'):
                    reason=skipped_snapshot(before,old_layout[slot][1])['operation_skipped']
                    item_skips.append(dict(slot=slot,**reason))
                    desired.append(old_layout[slot])
                    expected_charges[slot]=int(before['equipment'][slot].get('charges',0))
                    continue
            if not rawcode:
                desired.append((0, 0))
                continue
            prior = host.extension_snapshot_24268()
            prior_handles = {int(item['handle']) for area in ('bag', 'equipment') for item in prior[area]}
            after = host.add_extension_item_24268(rawcode)
            if int(after['target_unit']) != target:
                raise RuntimeError('Loadout target changed during creation; no replay was issued')
            if after.get('operation_skipped'):
                item_skips.append(dict(slot=slot,**after['operation_skipped']))
                desired.append(old_layout[slot])
                expected_charges[slot]=int(before['equipment'][slot].get('charges',0))
                continue
            fresh = [item for item in after['bag'] if int(item['handle']) not in prior_handles
                     and int(item['rawcode']) == rawcode and int(item['handle'])]
            if len(fresh) != 1:
                raise RuntimeError('Generated loadout item identity is not unique')
            item = fresh[0]
            created.append((int(item['handle']), rawcode))
            current_type = int(item.get('equipment_type', int(row[2]) if len(row) > 2 else 0))
            if current_type not in (slot_types[slot], 9) and not getattr(host, '_extension_any_slot_enabled', {}).get(key):
                host.set_extension_equipment_any_slot_24268(True)
            host.set_extension_bag_charges_24268(int(item['slot']), int(charges[slot]))
            desired.append(created[-1])
        after = host._restore_extension_loadout_handles_24268(tuple(desired), target)
        actual = tuple((int(row['handle']), int(row['rawcode'])) for row in after['equipment'])
        if actual != tuple(desired):
            raise RuntimeError('Generated loadout slot readback differs')
        if tuple(int(row.get('charges', 0)) for row in after['equipment']) != tuple(int(v) for v in expected_charges):
            raise RuntimeError('Generated loadout charges readback differs')
        after['loadout_item_skips']=tuple(item_skips)
        return after
    except Exception as exc:
        errors = []
        try:
            host._restore_extension_loadout_handles_24268(old_layout, target)
        except Exception as rollback_exc:
            errors.append(str(rollback_exc))
        # Remove only newly generated instances, and only when they are
        # uniquely back in the bag. Never remove uncertain/equipped instances.
        for handle, rawcode in reversed(created):
            try:
                current = host.extension_snapshot_24268()
                if int(current['target_unit']) != target:
                    raise RuntimeError('Cleanup target changed')
                bag = [row for row in current['bag'] if int(row['handle']) == handle and int(row['rawcode']) == rawcode]
                if len(bag) != 1 or any(int(row['handle']) == handle for row in current['equipment']):
                    raise RuntimeError('Generated instance cleanup is uncertain')
                host._engine_instance_24268().extension(action=8, target_unit=target,
                    item_rawcode=rawcode, item_handle=handle)
                final = host.extension_snapshot_24268()
                if any(int(row['handle']) == handle for area in ('bag', 'equipment') for row in final[area]):
                    raise RuntimeError('Generated instance remains after cleanup')
            except Exception as cleanup_exc:
                errors.append(str(cleanup_exc))
        suffix = '; rollback/cleanup incomplete: ' + '; '.join(errors) if errors else ''
        raise RuntimeError(f'Loadout regeneration failed: {exc}{suffix}') from exc
