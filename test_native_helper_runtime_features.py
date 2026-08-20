from pathlib import Path
import unittest
from unittest.mock import Mock

import war3_reforged_trainer as trainer_module


class _Memory:
    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _traceback):
        return None


class NativeHelperRuntimeFeatureTests(unittest.TestCase):
    def make_trainer(self):
        trainer = object.__new__(trainer_module.War3Trainer)
        trainer.query_mouse_world_position = Mock(return_value=(12.5, -8.0))
        trainer._process_memory = Mock(return_value=_Memory())
        trainer._elephant_handlers = Mock(
            side_effect=lambda _pm, names: {
                name: trainer_module.NativeHandler(name, 0x1000, 0x2000 + index)
                for index, name in enumerate(names)
            }
        )
        return trainer

    def test_selected_clone_uses_single_runtime_clone_transaction(self):
        trainer = self.make_trainer()
        candidate = Mock(handle=0x4455, unit_type_id=0x48666F6F)
        trainer._direct_selected_context = Mock(
            return_value=(candidate, candidate.handle)
        )
        trainer._run_native_helper_ops = Mock(
            return_value=[
                trainer_module.NativeHelperOpResult(
                    kind=trainer.NATIVE_HELPER_OP_JASS_CLONE_SELECTED_UNIT,
                    result=0x7788,
                )
            ]
        )

        rawcode, handle = trainer.create_local_unit(None)

        self.assertEqual((rawcode, handle), (candidate.unit_type_id, 0x7788))
        unit_handle, ops = trainer._run_native_helper_ops.call_args.args[:2]
        self.assertEqual(unit_handle, candidate.handle)
        self.assertEqual(len(ops), 14)
        self.assertEqual(
            ops[0][0],
            trainer.NATIVE_HELPER_OP_JASS_CLONE_SELECTED_UNIT,
        )
        self.assertTrue(
            all(
                op[0] == trainer.NATIVE_HELPER_OP_JASS_MULTI_ARG
                for op in ops[1:]
            )
        )

    def test_explicit_create_keeps_plain_create_path(self):
        trainer = self.make_trainer()
        trainer._coerce_memory_value = Mock(return_value=0x68666F6F)
        trainer._elephant_selected_candidate = Mock()
        trainer._direct_selected_context = Mock()
        trainer._run_native_helper_ops = Mock(
            return_value=[
                trainer_module.NativeHelperOpResult(
                    kind=trainer.NATIVE_HELPER_OP_JASS_CREATE_LOCAL_UNIT,
                    result=0x7788,
                )
            ]
        )

        trainer.create_local_unit("hfoo")

        unit_handle, ops = trainer._run_native_helper_ops.call_args.args[:2]
        self.assertEqual(unit_handle, 0)
        self.assertEqual(len(ops), 1)
        self.assertEqual(
            ops[0][0],
            trainer.NATIVE_HELPER_OP_JASS_CREATE_LOCAL_UNIT,
        )
        trainer._elephant_selected_candidate.assert_not_called()
        trainer._direct_selected_context.assert_not_called()

    def test_health_lock_heals_local_units_without_invulnerability(self):
        trainer = self.make_trainer()
        trainer._run_native_helper_ops = Mock(
            return_value=[
                trainer_module.NativeHelperOpResult(
                    kind=trainer.NATIVE_HELPER_OP_JASS_HEAL_LOCAL_UNITS,
                    result=3,
                )
            ]
        )

        self.assertEqual(trainer.heal_local_player_units(), 3)

        unit_handle, ops = trainer._run_native_helper_ops.call_args.args[:2]
        self.assertEqual(unit_handle, 0)
        self.assertEqual(ops[0][0], trainer.NATIVE_HELPER_OP_JASS_HEAL_LOCAL_UNITS)
        requested_names = trainer._elephant_handlers.call_args.args[1]
        self.assertNotIn("SetUnitInvulnerable", requested_names)
        self.assertIn("SetWidgetLife", requested_names)

    def test_python_and_c_helper_protocol_versions_match(self):
        helper_source = (
            Path(__file__).with_name("tools") / "war3_native_helper.c"
        ).read_text(encoding="utf-8")
        self.assertIn(
            f"#define WAR3_NATIVE_VERSION {trainer_module.War3Trainer.NATIVE_HELPER_VERSION}u",
            helper_source,
        )
        self.assertIn("WAR3_NATIVE_OP_JASS_HEAL_LOCAL_UNITS 117u", helper_source)
        self.assertIn("WAR3_NATIVE_OP_JASS_CLONE_SELECTED_UNIT 118u", helper_source)
        self.assertIn("WAR3_NATIVE_OP_JASS_SELECTED_UNITS 119u", helper_source)
        self.assertIn("uint64_t selected_units[12]", helper_source)
        self.assertIn("while (selected_count < 12u)", helper_source)
        self.assertIn("while (processed < 100000u)", helper_source)
        self.assertIn("get_unit_type_id(cmd.unit_handle) != op->rawcode", helper_source)
        self.assertIn("remove_unit(target)", helper_source)

    def test_elephant_handlers_discovers_every_requested_native(self):
        trainer = object.__new__(trainer_module.War3Trainer)
        trainer._native_handlers = {}
        requested = ("CreateUnit", "BlzGetItemIntegerField")

        def discover(_pm, names):
            self.assertTrue(set(requested).issubset(names))
            trainer._native_handlers.update(
                {
                    name: trainer_module.NativeHandler(name, 0x1000, 0x2000 + index)
                    for index, name in enumerate(requested)
                }
            )
            return trainer._native_handlers

        trainer._discover_native_handlers_near_table = Mock(side_effect=discover)

        handlers = trainer._elephant_handlers(object(), requested)

        self.assertEqual(set(handlers), set(requested))
        trainer._discover_native_handlers_near_table.assert_called_once()

    def test_elephant_handlers_reports_missing_native_without_key_error(self):
        trainer = object.__new__(trainer_module.War3Trainer)
        trainer._native_handlers = {}
        trainer._discover_native_handlers_near_table = Mock(return_value={})

        with self.assertRaisesRegex(
            RuntimeError,
            "缺少 native 函数：BlzGetItemIntegerField",
        ):
            trainer._elephant_handlers(object(), ("BlzGetItemIntegerField",))

    def test_selected_handles_uses_deduplicated_helper_extra_results(self):
        trainer = self.make_trainer()
        trainer._run_native_helper_ops = Mock(
            return_value=[
                trainer_module.NativeHelperOpResult(
                    kind=trainer.NATIVE_HELPER_OP_JASS_SELECTED_UNITS,
                    result=0x100,
                    extra_results=(0x100, 0x200, 0x100, 0x300),
                )
            ]
        )

        handles = trainer._elephant_selected_handles(object())

        self.assertEqual(handles, (0x100, 0x200, 0x300))
        _unit, ops = trainer._run_native_helper_ops.call_args.args[:2]
        self.assertEqual(ops[0][0], trainer.NATIVE_HELPER_OP_JASS_SELECTED_UNITS)
        self.assertEqual(len(ops), 3)

    def test_selected_handles_rejects_more_than_twelve(self):
        trainer = self.make_trainer()
        trainer._run_native_helper_ops = Mock(
            return_value=[
                trainer_module.NativeHelperOpResult(
                    kind=trainer.NATIVE_HELPER_OP_JASS_SELECTED_UNITS,
                    result=1,
                    extra_results=tuple(range(1, 14)),
                )
            ]
        )

        with self.assertRaisesRegex(RuntimeError, "超过安全上限"):
            trainer._elephant_selected_handles(object())

    def test_batch_selected_units_isolates_failure_and_restores_override(self):
        trainer = self.make_trainer()
        candidates = [
            Mock(unit_address=0x1000, unit_type_id=0x68666F6F),
            Mock(unit_address=0x2000, unit_type_id=0x686D696C),
            Mock(unit_address=0x3000, unit_type_id=0x686D7072),
        ]
        trainer._selected_candidates_snapshot = Mock(
            return_value=list(zip(candidates, (0x11, 0x22, 0x33)))
        )
        trainer._elephant_selection_override = None
        visited = []

        def action():
            candidate, handle = trainer._elephant_selection_override
            visited.append((candidate.unit_address, handle))
            if handle == 0x22:
                raise RuntimeError("unsupported")
            return handle

        succeeded, failed, results, errors = trainer.run_for_selected_units(action)

        self.assertEqual((succeeded, failed), (2, 1))
        self.assertEqual(results, (0x11, 0x33))
        self.assertEqual(visited, [(0x1000, 0x11), (0x2000, 0x22), (0x3000, 0x33)])
        self.assertIn("unsupported", errors[0])
        self.assertIsNone(trainer._elephant_selection_override)


if __name__ == "__main__":
    unittest.main()
