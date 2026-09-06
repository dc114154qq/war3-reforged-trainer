"""Exercise public selected-unit operations without a live process or GUI."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

import war3_reforged_trainer as module


class NativeSelectedWriteRoutingTests(unittest.TestCase):
    def setUp(self):
        self.trainer = object.__new__(module.War3Trainer)
        self.memory = MagicMock()
        self.memory.__enter__.return_value = self.memory
        self.trainer._process_memory = Mock(return_value=self.memory)
        self.trainer._unit_owner_index = {}
        self.trainer._candidate_from_identity = Mock(side_effect=lambda pm, handle, owner, unit, note, score:
            module.UnitCandidate(base=0, score=score, hp_current_address=unit+0x100, hp_max_address=unit+0x110,
                                 mp_current_address=0, mp_max_address=0, note=note,
                                 handle=handle, owner_address=owner, unit_address=unit))
        self.current = self.snapshot(1)
        self.trainer.persistent_native_selected_snapshots = Mock(side_effect=lambda: (self.current,))
        for method in ("_locate_selected_unit_by_selection_manager", "_locate_selected_unit_by_known_unit_pointer",
                       "_discover_selected_handle_addresses", "_owner_for_handle", "_build_unit_object_index",
                       "_discover_native_selection_layout"):
            setattr(self.trainer, method, Mock(side_effect=AssertionError("Unexpected legacy locator")))
        self.trainer._write_unit_fields_to_candidate = Mock(return_value=["written"])
        self.trainer._write_basic_unit_values_to_candidate = Mock()
        self.trainer._panel_from_candidate = Mock(return_value="panel")
        self.trainer._candidate_with_selected_unit_type_id = Mock(side_effect=lambda pm, candidate: candidate)
        self.trainer._unit_fields_from_candidate = Mock(return_value=[])

    @staticmethod
    def snapshot(index):
        return SimpleNamespace(handle=index, full_handle=(index << 32) | index,
                               owner_address=index*0x10000, unit_address=index*0x20000, type_id=0x68666f6f)

    def assert_current(self, candidate):
        self.assertEqual(candidate.handle, self.current.full_handle)
        self.assertEqual(candidate.unit_address, self.current.unit_address)
        self.assertIs(candidate.native_snapshot, self.current)
        self.assertEqual(candidate.selection_source, "persistent_native")

    def test_legacy_flags_cannot_enable_scan_or_retries(self):
        with patch.object(module.time, "sleep", side_effect=AssertionError("Unexpected retry wait")):
            for panel in (False, True):
                for deep in (False, True):
                    with self.subTest(panel=panel, deep=deep):
                        self.assert_current(self.trainer.locate_selected_unit_by_handle(
                            self.memory, allow_panel_fallback=panel, allow_deep_scan=deep))
        self.trainer._process_memory.assert_not_called()
        self.assertEqual(self.memory.mock_calls, [])
        self.assertEqual(self.trainer.persistent_native_selected_snapshots.call_count, 4)

    def test_owned_memory_closes_on_success_and_native_error(self):
        self.assert_current(self.trainer.locate_selected_unit_by_handle())
        self.memory.__exit__.assert_called_once()
        self.memory.reset_mock()
        self.trainer.persistent_native_selected_snapshots.side_effect = RuntimeError("selection unavailable")
        with self.assertRaisesRegex(RuntimeError, "selection unavailable"):
            self.trainer.locate_selected_unit_by_handle(allow_deep_scan=True)
        self.memory.__exit__.assert_called_once()

    def test_public_writes_follow_new_native_identity_with_identical_panel_input(self):
        for index in (1, 2):
            self.current = self.snapshot(index)
            # The old panel values remain identical while selection changes.
            candidate = self.trainer.set_selected_unit(100, 50, 200, 60)
            self.assert_current(candidate)
            self.assert_current(self.trainer._write_basic_unit_values_to_candidate.call_args.args[1])
            self.assertEqual(self.trainer.write_selected_unit_field("hp_current", 200), "written")
            self.assert_current(self.trainer._write_unit_fields_to_candidate.call_args.args[1])
        self.assertEqual(self.trainer.persistent_native_selected_snapshots.call_count, 4)

    def test_empty_selection_never_writes_or_uses_previous_candidate(self):
        self.trainer.locate_selected_unit_by_handle(self.memory)
        self.trainer.persistent_native_selected_snapshots.side_effect = lambda: ()
        for action in (lambda: self.trainer.set_selected_unit(100, 50, 200, 60),
                       lambda: self.trainer.write_selected_unit_field("hp_current", 200)):
            with self.assertRaises(RuntimeError):
                action()
        self.trainer._write_unit_fields_to_candidate.assert_not_called()
        self.trainer._write_basic_unit_values_to_candidate.assert_not_called()

    def test_invalid_second_unit_prevents_partial_group_mapping_and_write(self):
        invalid = self.snapshot(2)
        invalid.full_handle = 0
        self.trainer.persistent_native_selected_snapshots.side_effect = lambda: (self.current, invalid)
        with self.assertRaises(RuntimeError):
            self.trainer.write_selected_unit_field("hp_current", 200)
        self.assertEqual(self.trainer._unit_owner_index, {})
        self.trainer._write_unit_fields_to_candidate.assert_not_called()

    def test_compatibility_panel_locator_and_current_read_keep_native_binding(self):
        self.assert_current(self.trainer.locate_selected_unit(100, 50, 200, 60))
        panel, candidate = self.trainer.locate_current_selected_unit()
        self.assertEqual(panel, "panel")
        self.assert_current(candidate)
        self.assert_current(self.trainer.prewarm_selected_unit_cache())

    def test_prewarm_failure_does_not_rediscover_legacy_selection_layout(self):
        error = RuntimeError("no stable selection")
        self.trainer.persistent_native_selected_snapshots.side_effect = error
        with self.assertRaises(RuntimeError) as caught:
            self.trainer.prewarm_selected_unit_cache()
        self.assertIs(caught.exception, error)
        self.trainer._discover_native_selection_layout.assert_not_called()
        self.trainer._unit_fields_from_candidate.assert_not_called()

    def test_unpinned_gui_lock_uses_fresh_selection_on_each_tick(self):
        source = Path(module.__file__)
        tree = ast.parse(source.read_text(encoding="utf-8"))
        node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "apply_locks_once")
        namespace = {"state": {"locks": {"hp": {"kind": "unit", "key": "hp_current", "value": "200"}}},
                     "trainer": lambda: self.trainer}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
        for index in (1, 2):
            self.current = self.snapshot(index)
            namespace["apply_locks_once"]()
            self.assert_current(self.trainer._write_unit_fields_to_candidate.call_args.args[1])
