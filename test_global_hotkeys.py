import ctypes
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

import war3_reforged_trainer as trainer
from war3_ui_i18n import translate_ui_text


class GlobalHotkeyManagerTests(unittest.TestCase):
    def test_global_toggle_is_in_top_toolbar_and_title_is_branded(self):
        source = Path(trainer.__file__).read_text(encoding="utf-8")
        self.assertIn("by B站 两杯沈梦溪", source)
        self.assertEqual(source.count('text="启用全局快捷键"'), 1)
        self.assertLess(
            source.index("top = ttk.Frame(outer)"),
            source.index('text="启用全局快捷键"'),
        )

    def test_backup_product_exposes_only_backup_read_on_ctrl_f11(self):
        specs = {
            spec.name: spec
            for spec in trainer.ELEPHANT_HOTKEY_SPECS
        }

        self.assertEqual(
            (
                specs["backup_read_unit"].modifiers,
                specs["backup_read_unit"].virtual_key,
            ),
            (trainer.MOD_CONTROL, trainer.VK_F11),
        )
        self.assertNotIn("read_unit", specs)

    def test_ally_health_lock_hotkey_is_available(self):
        specs = {
            spec.name: spec
            for spec in trainer.ELEPHANT_HOTKEY_SPECS
        }
        self.assertEqual(
            (
                specs["ally_health_lock"].modifiers,
                specs["ally_health_lock"].virtual_key,
            ),
            (trainer.MOD_ALT, ord("K")),
        )

    def test_allied_cooldown_hotkey_is_available(self):
        specs = {
            spec.name: spec
            for spec in trainer.ELEPHANT_HOTKEY_SPECS
        }
        self.assertEqual(
            (
                specs["allied_cooldowns"].modifiers,
                specs["allied_cooldowns"].virtual_key,
            ),
            (trainer.MOD_ALT, ord("C")),
        )

    def test_cheat_hotkeys_are_available(self):
        specs = {
            spec.name: spec
            for spec in trainer.ELEPHANT_HOTKEY_SPECS
        }
        self.assertEqual(
            (specs["rapid_build"].modifiers, specs["rapid_build"].virtual_key),
            (trainer.MOD_ALT, ord("V")),
        )
        self.assertEqual(
            (specs["instant_victory"].modifiers, specs["instant_victory"].virtual_key),
            (trainer.MOD_ALT, ord("B")),
        )
        self.assertEqual(trainer.War3Trainer.CHEATS["快速建造/研究"], "warpten")
        self.assertEqual(
            trainer.War3Trainer.CHEATS["直接胜利"],
            "allyourbasearebelongtous",
        )

    def test_free_anti_resale_notice_is_next_to_pid(self):
        source = Path(trainer.__file__).read_text(encoding="utf-8")
        pid_entry = 'ttk.Entry(top, textvariable=pid_var, width=10, state="readonly").pack(side="left")'
        notice = "大象功能灵感来源于经典版大象修改器，本软件完全免费，谨防倒卖"
        self.assertLess(source.index(pid_entry), source.index(notice))

    def test_read_success_sound_only_plays_after_success(self):
        with patch.object(trainer, "play_read_success_sound") as sound:
            self.assertEqual(
                trainer.call_with_read_success_sound(lambda: "ok"),
                "ok",
            )
            sound.assert_called_once_with()

        with patch.object(trainer, "play_read_success_sound") as sound:
            with self.assertRaisesRegex(RuntimeError, "failed"):
                trainer.call_with_read_success_sound(
                    lambda: (_ for _ in ()).throw(RuntimeError("failed"))
                )
            sound.assert_not_called()

    def test_read_buttons_show_shortcuts_in_both_languages(self):
        labels = (
            "读取当前选中单位 (Ctrl+F11)",
            "备用读取 (Ctrl+F12)",
        )
        self.assertEqual(
            translate_ui_text(labels[0], "en"),
            "Read Selected Unit (Ctrl+F11)",
        )
        self.assertEqual(
            translate_ui_text(labels[1], "en"),
            "Backup Read (Ctrl+F12)",
        )

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
