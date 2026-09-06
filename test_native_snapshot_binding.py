"""Snapshot ownership and item readback, with no live process access."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import threading
import unittest
from unittest.mock import Mock, patch

import war3_reforged_trainer as module


def make_snapshot():
    return module.PersistentNativeUnitSnapshot(
        handle=1, full_handle=0x100000001, owner_address=0x3000, unit_address=0x2000,
        owner=2, owner_id=1, type_id=0x68666f6f,
        hp=100, hp_max=200, mp=50, mp_max=60, x=10, y=20, move_speed=300,
        hero_level=5, hero_xp=100, strength=10, agility=20, intelligence=30,
        item_ids=(0x49303031, 0, 0, 0, 0, 0), item_charges=(3, 0, 0, 0, 0, 0),
        item_handles=(100, 0, 0, 0, 0, 0), item_addresses=(0x100005000, 0, 0, 0, 0, 0),
        ability_ids=(0x41303031,), ability_levels=(2,),
    )


def make_candidate(snapshot):
    return module.UnitCandidate(
        base=0, score=1000, hp_current_address=0, hp_max_address=0,
        mp_current_address=0, mp_max_address=0, note="",
        handle=snapshot.full_handle, owner_address=snapshot.owner_address,
        unit_address=snapshot.unit_address, unit_type_id=snapshot.type_id,
        selection_source="persistent_native", native_snapshot=snapshot,
    )


class NativeSnapshotBindingTests(unittest.TestCase):
    def setUp(self):
        self.trainer = object.__new__(module.War3Trainer)
        self.snapshot = make_snapshot()
        self.candidate = make_candidate(self.snapshot)
        self.trainer._last_persistent_native_snapshots = ()

    def test_new_read_on_other_thread_cannot_replace_inflight_summary(self):
        ready, replaced = threading.Event(), threading.Event()
        self.trainer._unit_owner_index = {}
        self.trainer._candidate_from_identity = Mock(return_value=replace(self.candidate, native_snapshot=None))
        self.trainer._panel_from_candidate = Mock(side_effect=AssertionError("Unexpected external panel read"))
        self.trainer._selected_components = Mock(side_effect=AssertionError("Unexpected legacy component lookup"))

        def first_read():
            selected = self.trainer._selected_candidates_snapshot(Mock(), persistent_snapshots=(self.snapshot,))
            ready.set()
            self.assertTrue(replaced.wait(5))
            return self.trainer._selected_summaries_from_snapshot(Mock(), selected)[0]

        with ThreadPoolExecutor(max_workers=1) as worker:
            future = worker.submit(first_read)
            self.assertTrue(ready.wait(5))
            # Same address but a different object generation and different data.
            self.trainer._last_persistent_native_snapshots = (replace(
                self.snapshot, full_handle=0x200000001, hp=999, x=500,
                hero_level=0, item_ids=(0,) * 6, ability_ids=(),
            ),)
            replaced.set()
            summary = future.result(timeout=5)
        self.assertIs(summary.candidate.native_snapshot, self.snapshot)
        self.assertEqual(summary.hp_text, "100/200")
        self.assertEqual(summary.mp_text, "50/60")
        self.assertEqual(summary.position, (10, 20))
        self.assertEqual(summary.ability_count, 1)
        self.assertTrue(summary.hero)
        self.assertEqual(summary.inventory, ("1:I001",))

    def test_bound_snapshot_wins_even_when_latest_has_same_identity(self):
        self.trainer._last_persistent_native_snapshots = (replace(self.snapshot, x=123),)
        self.assertIs(self.trainer._native_snapshot_for_candidate(self.candidate), self.snapshot)

    def test_unbound_manual_candidate_matches_complete_identity(self):
        candidate = replace(self.candidate, native_snapshot=None, selection_source="memory")
        for attribute in ("full_handle", "owner_address", "unit_address"):
            with self.subTest(attribute=attribute):
                self.trainer._last_persistent_native_snapshots = (replace(self.snapshot, **{attribute: 0xBAD}),)
                self.assertIsNone(self.trainer._native_snapshot_for_candidate(candidate))
        self.trainer._last_persistent_native_snapshots = (self.snapshot,)
        self.assertIs(self.trainer._native_snapshot_for_candidate(candidate), self.snapshot)

    def test_missing_or_mismatched_native_binding_never_uses_global_snapshot(self):
        self.trainer._last_persistent_native_snapshots = (self.snapshot,)
        for candidate in (replace(self.candidate, native_snapshot=None),
                          replace(self.candidate, handle=0xBAD),
                          replace(self.candidate, owner_address=0xBAD),
                          replace(self.candidate, unit_address=0xBAD)):
            with self.assertRaises(RuntimeError):
                self.trainer._native_snapshot_for_candidate(candidate)
        with self.assertRaises(RuntimeError):
            self.trainer._selected_summaries_from_snapshot(Mock(), [(self.candidate, 999)])

    def inventory_memory(self):
        memory = Mock()
        self.trainer._inventory_record_address = Mock(return_value=0x4000)
        self.trainer._looks_like_vtable = Mock(return_value=True)
        self.trainer._item_objects_from_handles = Mock(side_effect=AssertionError("Unexpected item scan"))
        item = self.snapshot.item_addresses[0]
        full_item = 0x123400000064
        def read_u64(address):
            if address == 0x4000 + 0xD4 or address == item + 0x18:
                return full_item
            if address == item:
                return 0x140001000
            return 0
        memory.read_u64.side_effect = read_u64
        memory.read_u32.side_effect = lambda address: self.snapshot.item_ids[0] if address == item + 0x70 else 0
        memory.read_i32.return_value = 7
        self.trainer._selected_components = Mock(return_value={"inventory": (0, 0x5000)})
        return memory

    def test_inventory_readback_reads_live_quantity_on_bound_object(self):
        memory = self.inventory_memory()
        self.trainer._last_persistent_native_snapshots = (replace(
            self.snapshot, item_addresses=(0x200005000,) * 6, item_charges=(900,) * 6,
        ),)
        items = self.trainer._inventory_items_from_candidate(memory, self.candidate)
        self.assertEqual(items[0].charges, 7)
        self.assertEqual(items[0].item_address, self.snapshot.item_addresses[0])
        self.assertEqual(len(items), 6)
        memory.read_i32.assert_called_once_with(self.snapshot.item_addresses[0] + self.trainer.ITEM_CHARGES_OFFSET)

    def test_quantity_write_verifies_new_value_instead_of_old_snapshot_value(self):
        memory = self.inventory_memory()
        memory.read_i32.return_value = 3
        self.trainer._set_item_charges_via_native_handler = Mock(
            side_effect=lambda *args: setattr(memory.read_i32, "return_value", 7))
        field = module.UnitMemoryField(
            key="inventory_slot_1_charges", label="quantity", value_type="i32", value=3,
            category="inventory",
            address=self.snapshot.item_addresses[0] + self.trainer.ITEM_CHARGES_OFFSET,
        )
        with patch.object(module.time, "sleep"):
            result = self.trainer._write_inventory_slot_charges_field(memory, self.candidate, field, 7)
        self.assertEqual(result.value, 7)
        self.assertEqual(self.snapshot.item_charges[0], 3)
        self.trainer._set_item_charges_via_native_handler.assert_called_once()
        self.trainer._item_objects_from_handles.assert_not_called()

    def test_changed_slot_during_reconnect_never_scans_items(self):
        memory = self.inventory_memory()
        self.trainer._persistent_native_initialized = False
        memory.read_u64.return_value = 0
        memory.read_u64.side_effect = None
        self.assertEqual(self.trainer._inventory_items_from_candidate(memory, self.candidate), [])
        self.trainer._item_objects_from_handles.assert_not_called()

    def test_unreadable_empty_slot_is_not_reported_as_valid_empty_inventory(self):
        memory = self.inventory_memory()
        empty = replace(self.snapshot, item_handles=(0,) * 6, item_addresses=(0,) * 6,
                        item_ids=(0,) * 6, item_charges=(0,) * 6)
        memory.read_u64.side_effect = OSError("slot unavailable")
        self.assertEqual(self.trainer._inventory_items_from_candidate(memory, make_candidate(empty)), [])
        self.trainer._item_objects_from_handles.assert_not_called()
