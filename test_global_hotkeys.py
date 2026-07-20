import ctypes
import threading
import time
import unittest

import war3_reforged_trainer as trainer


class GlobalHotkeyManagerTests(unittest.TestCase):
    def test_poll_fallback_is_available_for_every_shortcut(self):
        fallback_names = {
            spec.name
            for spec in trainer.ELEPHANT_HOTKEY_SPECS
            if spec.poll_on_conflict
        }
        self.assertEqual(
            fallback_names,
            {spec.name for spec in trainer.ELEPHANT_HOTKEY_SPECS},
        )

    def test_registered_conflict_uses_edge_triggered_fallback(self):
        specs = tuple(
            spec
            for spec in trainer.ELEPHANT_HOTKEY_SPECS
            if spec.name in {"hero_level", "reveal_map", "toggle_game_pause"}
        )
        key_state = {spec.name: False for spec in specs}
        triggered = []
        triggered_event = threading.Event()
        original_register = trainer.user32.RegisterHotKey
        original_async_check = trainer.async_hotkey_is_down

        def reject_registration(_hwnd, _hotkey_id, _modifiers, _virtual_key):
            ctypes.set_last_error(trainer.ERROR_HOTKEY_ALREADY_REGISTERED)
            return False

        def fake_async_check(spec):
            return key_state[spec.name]

        def on_trigger(name):
            triggered.append(name)
            triggered_event.set()

        manager = trainer.GlobalHotkeyManager()
        try:
            trainer.user32.RegisterHotKey = reject_registration
            trainer.async_hotkey_is_down = fake_async_check
            errors = manager.start(specs, on_trigger)

            self.assertEqual(
                errors,
                {
                    spec.name: trainer.ERROR_HOTKEY_ALREADY_REGISTERED
                    for spec in specs
                },
            )
            self.assertEqual(manager.registered_names, ())
            self.assertEqual(
                manager.fallback_names,
                tuple(spec.name for spec in specs),
            )

            key_state["hero_level"] = True
            self.assertTrue(triggered_event.wait(1.0))
            time.sleep(0.08)
            self.assertEqual(triggered, ["hero_level"])
        finally:
            manager.stop()
            trainer.user32.RegisterHotKey = original_register
            trainer.async_hotkey_is_down = original_async_check

        self.assertEqual(manager.fallback_names, ())


if __name__ == "__main__":
    unittest.main()
