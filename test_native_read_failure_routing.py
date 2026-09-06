"""Exercise GUI read callbacks without starting Tk, the EXE, or Warcraft."""
import ast
from pathlib import Path
import time
import unittest
from unittest.mock import Mock, call


class NativeReadFailureRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = Path(__file__).with_name("war3_reforged_trainer.py")
        cls.tree = ast.parse(cls.source.read_text(encoding="utf-8-sig"))

    def load_callback(self, name, namespace):
        node = next(n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef) and n.name == name)
        module = ast.Module(body=[node], type_ignores=[])
        exec(compile(module, str(self.source), "exec"), namespace)
        return namespace[name]

    def test_read_errors_do_not_scan_or_offer_old_candidates(self):
        for callback in ("read_unit", "read_unit_fields", "read_unit_native_selection"):
            for attach_failure in (False, True):
                with self.subTest(callback=callback, attach_failure=attach_failure):
                    error = RuntimeError("native selection unavailable")
                    trainer = Mock()
                    trainer.read_selected_unit_fields.side_effect = error
                    trainer.probe_native_selection_manager.side_effect = error
                    root = Mock()
                    clear_readout, populate_candidates = Mock(), Mock()
                    namespace = {
                        "time": time,
                        "trainer": Mock(side_effect=error) if attach_failure else Mock(return_value=trainer),
                        "root": root,
                        "clear_selected_unit_readout": clear_readout,
                        "populate_selection_candidates": populate_candidates,
                        "populate_recovery_candidates": Mock(side_effect=AssertionError("Unexpected scan")),
                    }
                    with self.assertRaises(RuntimeError) as raised:
                        self.load_callback(callback, namespace)()
                    self.assertIs(raised.exception, error)
                    self.assertEqual(root.after.call_args_list, [
                        call(0, clear_readout), call(0, populate_candidates, []),
                    ])
                    trainer.list_selection_candidates.assert_not_called()
                    namespace["populate_recovery_candidates"].assert_not_called()

    def test_successful_read_still_populates_current_native_selection(self):
        trainer = Mock()
        panel = Mock(current_hp=10, hp_text="10/10", mp_text="0/0")
        candidate = Mock(selection_source="persistent_native", base=1, unit_address=2, note="", owner_address=3, handle=4)
        trainer.read_selected_unit_fields.return_value = panel, candidate, []
        trainer.selected_unit_summaries.return_value = ("current selected unit",)
        root, populate_readout, populate_candidates = Mock(), Mock(), Mock()
        namespace = {
            "time": time, "trainer": Mock(return_value=trainer), "root": root,
            "populate_auto_selected_unit_readout": populate_readout,
            "populate_selection_candidates": populate_candidates,
        }
        result = self.load_callback("read_unit", namespace)()
        self.assertIn("1 个单位", result)
        self.assertEqual(root.after.call_args_list, [
            call(0, populate_readout, panel, candidate, [], True),
            call(0, populate_candidates, ["current selected unit"]),
        ])
        trainer.list_selection_candidates.assert_not_called()
