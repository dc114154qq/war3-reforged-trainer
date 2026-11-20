"""Capture the 30-slot bag and restore missing items through the game inventory API."""
from collections import Counter

from war3_loadout_storage import BAG_SLOTS, validate_backpack
from war3_services.loadout_runtime import restore_scope


def backpack_rows(snapshot):
    rows = tuple(snapshot['bag'][:BAG_SLOTS])
    if (int(snapshot['bag_size']) != BAG_SLOTS or len(rows) != BAG_SLOTS
            or any(int(row['slot']) != index for index, row in enumerate(rows))):
        raise RuntimeError('当前英雄没有可用的 30 格扩展背包，请先开通背包')
    return rows


def _bag_items(snapshot):
    items = {}
    equipped = {int(row['handle']) for row in snapshot['equipment']}
    for row in backpack_rows(snapshot):
        handle = int(row['handle'])
        rawcode = int(row['rawcode'])
        if bool(handle) != bool(rawcode) or handle and (handle in items or handle in equipped):
            raise RuntimeError('背包物品身份不一致，请重新读取扩展状态')
        if handle:
            items[handle] = (rawcode, int(row['charges']))
    return items


def capture_backpack(snapshot):
    items = _bag_items(snapshot)
    return validate_backpack(tuple(items.get(int(row['handle']), (0, 0)) for row in backpack_rows(snapshot)))


def restore_backpack(host, initial, equipment_result, saved, name):
    """Fill empty slots. Each matching live instance satisfies one saved entry."""
    from war3_error_messages import describe_error
    from war3_services.loadout_talents import _Guard

    target = int(initial['target_unit'])
    if int(equipment_result['target_unit']) != target:
        raise RuntimeError('套装恢复后英雄发生变化，未开始恢复背包')
    inventory = _bag_items(equipment_result)
    pending = [(slot, code, quantity) for slot, (code, quantity) in enumerate(saved) if code]
    report = dict(requested=len(pending), present=0, restored=0, skipped=[])
    remaining = []
    existing = Counter(inventory.values())
    for entry in pending:
        _, code, quantity = entry
        if existing[(code, quantity)]:
            existing[(code, quantity)] -= 1
            report['present'] += 1
        else:
            remaining.append(entry)

    if not remaining:
        return dict(equipment_result, loadout_backpack=report)

    def skip(entry, reason, reason_en, **details):
        slot, code, quantity = entry
        report['skipped'].append(dict(slot=slot, rawcode=code, quantity=quantity,
            reason=reason, reason_en=reason_en, **details))

    equipment = equipment_result['equipment']
    guard = _Guard(host, equipment_result)
    inventory_changed = False
    with restore_scope(host, target, name) as runtime:
        runtime.record('backpack_restore_start', requested=report['requested'], present=report['present'])
        for index, entry in enumerate(remaining):
            _, code, quantity = entry
            if len(inventory) == BAG_SLOTS:
                for rest in remaining[index:]:
                    skip(rest, '扩展背包已满', 'The extended backpack is full')
                break
            try:
                # Fresh snapshots around writes also verify that a pickup or
                # stack merge did not change any existing item or equipment.
                guard.check_identity()
                before = host.extension_snapshot_24268()
                if (int(before['target_unit']) != target or before['equipment'] != equipment
                        or _bag_items(before) != inventory):
                    raise RuntimeError('恢复期间英雄或库存发生变化，请刷新后重试')
                added = host.add_extension_item_24268(code)
                if int(added['target_unit']) != target or added['equipment'] != equipment:
                    raise RuntimeError('生成物品后英雄或装备栏发生变化，请刷新检查')
                observed = _bag_items(added)
                if added.get('operation_skipped') and observed == inventory:
                    reason = added['operation_skipped']['reason']
                    skip(entry, reason, 'This quest or protected legacy item cannot be transferred safely')
                    continue
                inventory_changed = True
                fresh = set(observed) - inventory.keys()
                if (len(fresh) != 1 or any(observed.get(h) != item for h, item in inventory.items())):
                    raise RuntimeError('没有核对到唯一新物品，或原有物品发生变化，请刷新检查')
                handle = next(iter(fresh))
                if observed[handle][0] != code:
                    raise RuntimeError('背包中新物品的代码不一致，请刷新检查')
                if observed[handle][1] != quantity:
                    guard.check_identity()
                    slot = next(row['slot'] for row in added['bag'] if int(row['handle']) == handle)
                    added = host.set_extension_bag_charges_24268(slot, quantity, expected_item=(handle, code))
                    observed = _bag_items(added)
                expected = dict(inventory)
                expected[handle] = (code, quantity)
                if int(added['target_unit']) != target or added['equipment'] != equipment or observed != expected:
                    raise RuntimeError('背包物品数量或位置读回不一致，请刷新检查')
                inventory = observed
                report['restored'] += 1
                runtime.record('backpack_item_restored', saved_slot=entry[0], rawcode=code,
                    charges=quantity, item_handle=handle)
            except Exception as exc:
                reason = describe_error(exc)
                reason_en = describe_error(exc, 'en')
                if reason['category'] == 'classic_inventory_full' or (
                        reason['operation'] == 'item_safety' and reason['business_error'] == 411):
                    skip(entry, reason['reason'], reason_en['reason'])
                    continue
                skip(entry, reason['reason'] if reason['reason_confirmed'] else str(exc),
                     reason_en['reason'], execution_report=getattr(exc, 'report', None))
                for rest in remaining[index+1:]:
                    skip(rest, '上一个物品的结果需要核对，本次未处理', 'Refresh to check the previous item before retrying')
                runtime.record('backpack_restore_interrupted', report=report)
                inventory_changed = True
                break
        runtime.record('backpack_restore_complete', report=report)

    # Inventory-only work omits talent data. Re-read the complete snapshot
    # before the caller restores talents and refreshes the page.
    current = equipment_result
    if inventory_changed:
        try:
            guard.check_identity()
            current = host.extension_snapshot_24268(target)
            if int(current['target_unit']) != target:
                raise RuntimeError('背包恢复完成后，选中英雄发生变化')
            if not report['skipped'] and (current['equipment'] != equipment or _bag_items(current) != inventory):
                raise RuntimeError('恢复后再次核对时，背包或装备栏发生变化')
        except Exception as exc:
            failure = RuntimeError('装备处理已结束，背包恢复结果需要重新读取后核对')
            failure.report = dict(operation='loadout_backpack', target_unit=target, backpack=report)
            raise failure from exc
    return {**current, **{key: value for key, value in equipment_result.items() if key.startswith('loadout_')},
            'loadout_backpack': report}
