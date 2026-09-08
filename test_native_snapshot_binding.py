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
        base_strength=4, base_agility=5, base_intelligence=6,
        item_ids=(0x49303031, 0, 0, 0, 0, 0), item_charges=(3, 0, 0, 0, 0, 0),
        item_handles=(100, 0, 0, 0, 0, 0), item_addresses=(0x100005000, 0, 0, 0, 0, 0),
        item_full_handles=(0x123400000064, 0, 0, 0, 0, 0),
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


def snapshot_result(snapshot):
    row = [0] * 149
    row[:5] = [snapshot.handle, snapshot.unit_address, snapshot.owner, snapshot.owner_id, snapshot.type_id]
    row[5:12] = [module.War3Trainer._float_bits(v) for v in
                 (snapshot.hp, snapshot.hp_max, snapshot.mp, snapshot.mp_max, snapshot.x, snapshot.y, snapshot.move_speed)]
    row[12:17] = [snapshot.hero_level, snapshot.hero_xp, snapshot.strength, snapshot.agility, snapshot.intelligence]
    row[17:41] = [*snapshot.item_ids, *snapshot.item_charges, *snapshot.item_handles, *snapshot.item_addresses]
    row[41] = len(snapshot.ability_ids)
    row[42:42 + row[41]] = snapshot.ability_ids
    row[90:90 + row[41]] = snapshot.ability_levels
    row[138:140] = [snapshot.full_handle, snapshot.owner_address]
    row[143:149] = snapshot.item_full_handles
    row[140:143] = [snapshot.base_strength, snapshot.base_agility, snapshot.base_intelligence]
    return module.NativeHelperOpResult(kind=module.War3Trainer.NATIVE_HELPER_OP_PERSISTENT_UNIT_SNAPSHOT,
                                      result=1, extra_results=tuple(row))


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
        self.trainer.persistent_native_init = Mock()
        self.trainer._run_native_helper_ops = Mock(side_effect=[
            [snapshot_result(self.snapshot)],
            [module.NativeHelperOpResult(kind=136, result=1), module.NativeHelperOpResult(kind=137, result=7)],
        ])
        field = module.UnitMemoryField(
            key="inventory_slot_1_charges", label="quantity", value_type="i32", value=3,
            category="inventory",
            address=self.snapshot.item_addresses[0] + self.trainer.ITEM_CHARGES_OFFSET,
        )
        with patch.object(module.time, "sleep", side_effect=AssertionError("Unexpected fixed wait")):
            result = self.trainer._write_inventory_slot_charges_field(memory, self.candidate, field, 7)
        self.assertEqual(result.value, 7)
        self.assertEqual(self.snapshot.item_charges[0], 3)
        self.assertEqual(self.trainer._run_native_helper_ops.call_count, 2)
        self.trainer._item_objects_from_handles.assert_not_called()

    def test_native_quantity_write_needs_no_external_inventory_metadata(self):
        trainer = self.trainer
        trainer.persistent_native_init = Mock()
        trainer._selected_components = Mock(side_effect=AssertionError("Unexpected component lookup"))
        trainer._run_native_helper_ops = Mock(side_effect=[
            [snapshot_result(self.snapshot)],
            [module.NativeHelperOpResult(kind=136, result=1), module.NativeHelperOpResult(kind=137, result=1500)],
        ])
        field = module.UnitMemoryField(key="inventory_slot_1_charges", label="charges", value_type="i32",
                                       value=3, address=0, category="inventory", native_write=True)
        with patch.object(module.time, "sleep", side_effect=AssertionError("Unexpected wait")):
            result = trainer._write_inventory_slot_charges_field(Mock(), self.candidate, field, 1500)
        self.assertEqual(result.value, 1500)
        self.assertEqual(result.write_address, 0)
        self.assertTrue(result.native_write)
        self.assertEqual(trainer._run_native_helper_ops.call_args.args, (1, (
            (136, 0, self.candidate.unit_address, self.candidate.handle, self.candidate.owner_address),
            (137, 0, self.snapshot.item_addresses[0], self.snapshot.item_handles[0], 1500),
            (138, 0, self.snapshot.item_full_handles[0], 0, 0),
        )))

    def test_replaced_slot_after_refresh_cannot_receive_quantity_write(self):
        trainer = self.trainer
        trainer.persistent_native_init = Mock()
        changed = replace(self.snapshot, item_handles=(101, 0, 0, 0, 0, 0))
        trainer._run_native_helper_ops = Mock(return_value=[snapshot_result(changed)])
        field = module.UnitMemoryField(key="inventory_slot_1_charges", label="charges", value_type="i32",
                                       value=3, address=0, category="inventory", native_write=True)
        with self.assertRaisesRegex(RuntimeError, "changed before writing"):
            trainer._write_inventory_slot_charges_field(Mock(), self.candidate, field, 1500)
        self.assertEqual(trainer._run_native_helper_ops.call_count, 1)

    def test_same_slot_handle_address_and_rawcode_with_new_generation_cannot_be_written(self):
        trainer = self.trainer
        trainer.persistent_native_init = Mock()
        changed = replace(self.snapshot, item_full_handles=(self.snapshot.item_full_handles[0] + (1 << 32), 0, 0, 0, 0, 0))
        trainer._run_native_helper_ops = Mock(return_value=[snapshot_result(changed)])
        field = module.UnitMemoryField(key="inventory_slot_1_charges", label="charges", value_type="i32",
                                       value=3, address=0, category="inventory", native_write=True)
        with self.assertRaisesRegex(RuntimeError, "changed before writing"):
            trainer._write_inventory_slot_charges_field(Mock(), self.candidate, field, 1500)
        self.assertEqual(trainer._run_native_helper_ops.call_count, 1)

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

    def test_target_refresh_keeps_selection_cache_and_original_candidate_unchanged(self):
        self.trainer.persistent_native_init = Mock()
        unrelated = replace(self.snapshot, handle=2, full_handle=0x200000002, unit_address=0x4000)
        self.trainer._last_persistent_native_snapshots = (unrelated,)
        current = replace(self.snapshot, item_charges=(9, 0, 0, 0, 0, 0))
        self.trainer._run_native_helper_ops = Mock(return_value=[snapshot_result(current)])
        refreshed = self.trainer._refresh_native_candidate(self.candidate)
        self.assertEqual(refreshed.native_snapshot, current)
        self.assertEqual(self.candidate.native_snapshot.item_charges[0], 3)
        self.assertEqual(self.trainer._last_persistent_native_snapshots, (unrelated,))
        self.trainer._run_native_helper_ops.assert_called_once_with(1, ((
            133, 0, self.candidate.unit_address, self.candidate.handle, self.candidate.owner_address,
        ),))

    def test_target_refresh_rejects_wrong_returned_identity(self):
        self.trainer.persistent_native_init = Mock()
        for key in ("handle", "full_handle", "owner_address", "unit_address"):
            self.trainer._run_native_helper_ops = Mock(return_value=[snapshot_result(replace(self.snapshot, **{key: 999}))])
            with self.assertRaises(RuntimeError):
                self.trainer._refresh_native_candidate(self.candidate)

    def test_item_replacement_reads_new_object_without_wait_or_selection_query(self):
        memory = self.inventory_memory()
        self.trainer._item_object_cache = {}
        self.trainer.persistent_native_init = Mock()
        self.trainer.persistent_native_selected_snapshots = Mock(side_effect=AssertionError("Unexpected selection query"))
        current = self.snapshot
        old_item = current.item_addresses[0]
        old_full = 0x123400000064
        new_item, new_full, new_id = 0x100008000, 0x234500000065, 0x49303032
        new = replace(current, item_ids=(new_id, 0, 0, 0, 0, 0),
                      item_handles=(101, 0, 0, 0, 0, 0), item_addresses=(new_item, 0, 0, 0, 0, 0))
        self.trainer._run_native_helper_ops = Mock(side_effect=[[snapshot_result(current)], [snapshot_result(new)]])

        def replace_item(*args):
            def read_u64(address):
                if address in (0x4000 + 0xD4, new_item + 0x18):
                    return new_full
                if address == new_item:
                    return 0x140001000
                if old_item <= address < old_item + 0x1000:
                    raise OSError("old item freed")
                return 0
            memory.read_u64.side_effect = read_u64
            memory.read_u32.side_effect = lambda address: new_id if address == new_item + 0x70 else 0
            return old_full, 101, new_id

        self.trainer._set_inventory_slot_item_via_native_handler = Mock(side_effect=replace_item)
        field = module.UnitMemoryField(key="inventory_slot_1", label="item", value_type="rawcode",
                                       value=current.item_ids[0], category="inventory", address=old_item + 0x70,
                                       write_address=old_item + 0x70, write_type="rawcode")
        with patch.object(module.time, "sleep", side_effect=AssertionError("Unexpected fixed wait")):
            result = self.trainer._write_inventory_slot_field(memory, self.candidate, field, new_id)
        self.assertEqual(result.value, new_id)
        self.assertEqual((result.address, result.write_address), (new_item + 0x70,) * 2)
        self.assertEqual(self.trainer._run_native_helper_ops.call_count, 2)
        self.trainer.persistent_native_selected_snapshots.assert_not_called()
        self.trainer._item_objects_from_handles.assert_not_called()

    def test_target_command_passes_real_dispatch_validation_and_packing(self):
        trainer = self.trainer
        trainer._native_helper_command_path = Mock(return_value="unused-command-file")
        trainer._write_native_helper_command = Mock()
        trainer._native_helper_batch_hook = 1
        trainer._native_helper_batch_thread_id = threading.get_ident()
        trainer._wait_native_helper_result = Mock(return_value=[snapshot_result(self.snapshot)])
        ops = ((133, 0, self.candidate.unit_address, self.candidate.handle, self.candidate.owner_address),)
        trainer._run_native_helper_ops_locked(1, ops)
        payload = trainer._write_native_helper_command.call_args.args[1]
        header = trainer.NATIVE_HELPER_HEADER_STRUCT.unpack_from(payload)
        self.assertEqual(header[1], 35)
        self.assertEqual(header[4], 1)
        operation = trainer.NATIVE_HELPER_OP_STRUCT.unpack_from(payload, trainer.NATIVE_HELPER_HEADER_STRUCT.size)
        self.assertEqual(operation[:5], ops[0])
        trainer._wait_native_helper_result.assert_called_once_with("unused-command-file", 1, 1, 10000)
        trainer._write_native_helper_command.reset_mock()
        with self.assertRaises(RuntimeError):
            trainer._run_native_helper_ops_locked(0, ops)
        trainer._write_native_helper_command.assert_not_called()

    def test_manual_readback_refreshes_pinned_unit_without_changing_selection(self):
        trainer = self.trainer
        manual = replace(self.candidate, native_snapshot=None, selection_source="memory")
        trainer._last_persistent_native_snapshots = (self.snapshot,)
        trainer._process_memory = Mock()
        trainer._process_memory.return_value.__enter__ = Mock(return_value=Mock())
        trainer._process_memory.return_value.__exit__ = Mock(return_value=None)
        trainer._candidate_from_identity = Mock(return_value=manual)
        trainer.persistent_native_init = Mock()
        fresh = replace(self.snapshot, item_ids=(0x49303032, 0, 0, 0, 0, 0))
        trainer._run_native_helper_ops = Mock(return_value=[snapshot_result(fresh)])
        trainer._candidate_with_selected_unit_type_id = Mock(side_effect=lambda pm, candidate: candidate)
        trainer._panel_from_candidate = Mock(return_value="panel")
        trainer._unit_fields_from_candidate = Mock(return_value=[])
        _, candidate, _ = trainer.read_unit_fields_by_identity(manual.handle, manual.owner_address, manual.unit_address)
        self.assertEqual(candidate.native_snapshot, fresh)
        self.assertIs(trainer._unit_fields_from_candidate.call_args.args[1], candidate)
        self.assertEqual(trainer._last_persistent_native_snapshots, (self.snapshot,))
