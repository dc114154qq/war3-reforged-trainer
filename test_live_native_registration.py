import unittest
from unittest.mock import Mock

from war3_native_table import LiveNativeEntry
from war3_reforged_trainer import NativeHandler, War3Trainer


class LiveRegistrationTests(unittest.TestCase):
    def test_registration_uses_live_addresses_and_skips_legacy_bootstrap(self):
        trainer = object.__new__(War3Trainer)
        trainer.PERSISTENT_NATIVE_NAMES = ("CreateUnit", "UnitAddAbility")
        trainer.NATIVE_HELPER_OP_PERSISTENT_REGISTER_NATIVE = 130
        trainer._native_helper_dll_path = Mock(return_value="legacy.dll")
        trainer._native_helper_live_dll_path = Mock(return_value="live.dll")
        calls = []
        trainer._run_native_helper_ops = Mock(side_effect=lambda unit, ops, timeout_ms: calls.append((unit, list(ops))) or [Mock(last_error=0), Mock(last_error=0)])
        entries = {
            "CreateUnit": LiveNativeEntry("CreateUnit", "(Hplayer;IRRR)Hunit;", 0x1, 0x700001),
            "UnitAddAbility": LiveNativeEntry("UnitAddAbility", "(Hunit;I)B", 0x2, 0x700002),
        }
        self.assertEqual(trainer.register_live_3_native_handlers(entries), 2)
        self.assertEqual(calls[0][0], 0)
        self.assertEqual(calls[0][1], [(130, 0, 0x700001, 0, 0), (130, 1, 0x700002, 0, 0)])
        self.assertEqual(trainer._native_handlers["CreateUnit"].handler_address, 0x700001)

    def test_unregistered_name_is_rejected_before_a_command(self):
        trainer = object.__new__(War3Trainer)
        trainer.PERSISTENT_NATIVE_NAMES = ("CreateUnit",)
        trainer.NATIVE_HELPER_OP_PERSISTENT_REGISTER_NATIVE = 130
        trainer._run_native_helper_ops = Mock()
        with self.assertRaises(ValueError):
            trainer.register_live_3_native_handlers({"Unknown": LiveNativeEntry("Unknown", "()V", 0, 1)})
        trainer._run_native_helper_ops.assert_not_called()


if __name__ == "__main__":
    unittest.main()
