"""Inventory display is owned by the native snapshot, not heap metadata."""
from dataclasses import replace
from unittest.mock import Mock

import pytest
import war3_reforged_trainer as module
from test_native_hero_fields import context


@pytest.mark.parametrize('hero', [False, True])
@pytest.mark.parametrize('component', [False, True])
def test_missing_metadata_keeps_all_native_slots_and_quantities(hero, component):
    trainer, memory, candidate = context(False, hero)
    trainer._native_unit_field_memory.return_value.components = {'inventory': (0, 0x5000)} if component else {}
    trainer._native_unit_field_memory.return_value.inventory_items = []
    snapshot = replace(candidate.native_snapshot,
                       item_ids=(0x49303031, 0, 0, 0, 0, 0x49303032),
                       item_handles=(100, 0, 0, 0, 0, 200),
                       item_addresses=(0x100005000, 0, 0, 0, 0, 0x100006000),
                       item_full_handles=(0x123400000064, 0, 0, 0, 0, 0x5678000000c8),
                       item_charges=(1234, 0, 0, 0, 0, 99))
    candidate = replace(candidate, native_snapshot=snapshot)
    trainer._last_persistent_native_snapshots = (replace(snapshot, item_charges=(999,) * 6),)
    fields = {f.key: f for f in trainer._unit_fields_from_candidate(memory, candidate)}
    for slot in range(1, 7):
        item, charges = fields[f'inventory_slot_{slot}'], fields[f'inventory_slot_{slot}_charges']
        assert (item.value, charges.value) == (snapshot.item_ids[slot - 1], snapshot.item_charges[slot - 1])
        assert not item.writable
        assert charges.writable == bool(snapshot.item_handles[slot - 1])
    if not component:
        trainer._inventory_items_from_candidate.assert_not_called()


def test_valid_metadata_preserves_existing_write_capability_but_not_its_stale_values():
    trainer, memory, candidate = context(False, False)
    trainer._native_unit_field_memory.return_value.components = {'inventory': (0, 0x5000)}
    snapshot = candidate.native_snapshot
    trainer._native_unit_field_memory.return_value.inventory_items = [module.InventoryItem(
        slot=1, handle=0x123400000064, handle_address=0x6000,
        rawcode=snapshot.item_ids[0], item_address=snapshot.item_addresses[0],
        rawcode_address=0x7000, charges=888, charges_address=0x8000)]
    fields = {f.key: f for f in trainer._unit_fields_from_candidate(memory, candidate)}
    assert fields['inventory_slot_1'].writable
    assert fields['inventory_slot_1_charges'].writable
    assert fields['inventory_slot_1_charges'].value == 3
    assert fields['inventory_slot_1_charges'].write_address == 0
    assert fields['inventory_slot_1_charges'].native_write


@pytest.mark.parametrize('mismatch', ['rawcode', 'item_address'])
def test_changed_metadata_cannot_supply_write_addresses_for_old_display(mismatch):
    trainer, memory, candidate = context(False, False)
    trainer._native_unit_field_memory.return_value.components = {'inventory': (0, 0x5000)}
    snapshot = candidate.native_snapshot
    item = module.InventoryItem(slot=1, handle=12, handle_address=0x6000,
                                rawcode=snapshot.item_ids[0], item_address=snapshot.item_addresses[0],
                                rawcode_address=0x7000, charges_address=0x8000)
    trainer._native_unit_field_memory.return_value.inventory_items = [replace(item, **{mismatch: 0xBAD})]
    fields = {f.key: f for f in trainer._unit_fields_from_candidate(memory, candidate)}
    assert fields['inventory_slot_1'].value == snapshot.item_ids[0]
    assert not fields['inventory_slot_1'].writable
    assert fields['inventory_slot_1_charges'].native_write


def test_incomplete_inventory_payload_is_not_displayed_as_empty_slots():
    trainer, memory, candidate = context(False, False)
    for changes in ({'item_charges': ()}, {'item_handles': (0,) * 6}):
        bad = replace(candidate, native_snapshot=replace(candidate.native_snapshot, **changes))
        with pytest.raises(RuntimeError):
            trainer._unit_fields_from_candidate(memory, bad)
