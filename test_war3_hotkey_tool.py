import ctypes
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from war3_hotkey_engine import (
    CompiledBinding,
    HotkeyEngine,
    KBDLLHOOKSTRUCT,
    WM_KEYDOWN,
    WM_KEYUP,
    command_context_for,
    native_ability_hotkeys,
    plan_binding_action,
)
from war3_hotkey_engine import GameWindowSnapshot, WarcraftWindowGuard
from war3_hotkey_native import (
    CommandBarInternals,
    CommandContext,
    HOTKEY_FLAG_SAVE,
    NativeFrameBridge,
    OP_OVERRIDE_COMMAND_HOTKEY,
    OP_REFRESH_COMMAND_BAR,
    OP_STRUCT,
    ORIGIN_FRAME_COMMAND_BUTTON,
    ORIGIN_FRAME_ITEM_BUTTON,
    SelectionContext,
)
from war3_hotkey_model import (
    AppConfig,
    BindingConfig,
    ConfigStore,
    KeyParseError,
    binding_conflicts,
    default_app_config,
    default_profile,
    parse_keystroke,
    profile_from_dict,
    validate_profile,
)


class KeyParserTests(unittest.TestCase):
    def test_combination_is_canonical_and_layout_independent(self):
        stroke = parse_keystroke("shift + control + q")
        self.assertEqual(stroke.key, "Q")
        self.assertEqual(stroke.modifiers, frozenset({"CTRL", "SHIFT"}))
        self.assertEqual(stroke.canonical(), "Ctrl+Shift+Q")

    def test_mouse_aliases_are_supported_for_triggers_only(self):
        self.assertEqual(parse_keystroke("XButton1").canonical(), "Mouse4")
        with self.assertRaises(KeyParseError):
            parse_keystroke("Mouse4", allow_mouse=False)

    def test_duplicate_enabled_trigger_is_reported(self):
        bindings = [
            BindingConfig("one", "Ctrl+Q", "Q"),
            BindingConfig("two", "Control+Q", "W"),
            BindingConfig("disabled", "Ctrl+Q", "E", enabled=False),
        ]
        self.assertEqual(binding_conflicts(bindings), {"command: Ctrl+Q": ["one", "two"]})

    def test_same_key_is_allowed_in_different_command_contexts(self):
        bindings = [
            BindingConfig("ability_1", "Q", "Q", group="ability"),
            BindingConfig("spellbook_1", "Q", "Q", group="spellbook"),
            BindingConfig("shop_1", "Q", "Q", group="shop"),
        ]
        self.assertEqual(binding_conflicts(bindings), {})


class ActionPlannerTests(unittest.TestCase):
    @staticmethod
    def compiled(source="Q", target="Q", **changes):
        config = BindingConfig("test", source, target, **changes)
        return CompiledBinding(config, parse_keystroke(source), parse_keystroke(target, allow_mouse=False))

    def test_same_key_normal_binding_uses_original_game_input(self):
        action = plan_binding_action(self.compiled(), frozenset(), default_profile())
        self.assertFalse(action.send_target)
        self.assertFalse(action.smartcast)

    def test_same_key_smartcast_passes_key_then_clicks(self):
        action = plan_binding_action(self.compiled(smartcast=True), frozenset(), default_profile())
        self.assertFalse(action.send_target)
        self.assertTrue(action.smartcast)

    def test_self_cast_modifier_forces_target_and_self_click(self):
        action = plan_binding_action(self.compiled(smartcast=True), frozenset({"CTRL"}), default_profile())
        self.assertTrue(action.send_target)
        self.assertTrue(action.self_cast)
        self.assertTrue(action.smartcast)

    def test_modifier_used_by_binding_does_not_accidentally_self_cast(self):
        action = plan_binding_action(
            self.compiled(source="Ctrl+Q", target="NUM7", group="item"),
            frozenset({"CTRL"}),
            default_profile(),
        )
        self.assertTrue(action.send_target)
        self.assertFalse(action.self_cast)

    def test_autocast_modifier_right_clicks_command_slot(self):
        action = plan_binding_action(
            self.compiled(slot_index=2, group="ability"),
            frozenset({"SHIFT"}),
            default_profile(),
        )
        self.assertTrue(action.autocast_toggle)
        self.assertFalse(action.send_target)


class NativeFrameBridgeTests(unittest.TestCase):
    def test_visual_ability_rows_preserve_game_order(self):
        profile = default_profile()
        hotkeys = native_ability_hotkeys(profile)
        self.assertEqual([item[:2] for item in hotkeys[:4]], [(0, 0), (0, 1), (0, 2), (0, 3)])
        self.assertEqual([item[:2] for item in hotkeys[8:]], [(2, 0), (2, 1), (2, 2), (2, 3)])

    def test_native_hotkey_override_refreshes_live_command_bar_after_save(self):
        bridge = NativeFrameBridge(Path("missing-test-helper.dll"))
        bridge.connect = lambda _hwnd, _pid: None
        bridge._command_bar = CommandBarInternals(
            game_ui_get=0x1000,
            command_bar_offset=0x678,
            submenu_link_offset=0x2E8,
            set_hotkey=0x2000,
            set_hotkey_hero_only=0x3000,
            set_hotkey_quick_cast=0x4000,
            save_hotkeys=0x5000,
            refresh_command_bar=0x6000,
            overriding_hotkey_enabled=0x7000,
        )
        captured = []
        bridge._dispatch = lambda _hwnd, _pid, operations, **_kwargs: captured.extend(operations) or 1

        bridge.override_command_hotkeys(
            10,
            20,
            ((row, column, ord("Q") + row * 4 + column, 0) for row in range(3) for column in range(4)),
        )

        self.assertEqual(len(captured), 13)
        last_override = OP_STRUCT.unpack(captured[11])
        refresh = OP_STRUCT.unpack(captured[12])
        self.assertEqual(last_override[0], OP_OVERRIDE_COMMAND_HOTKEY)
        self.assertEqual(last_override[7], HOTKEY_FLAG_SAVE)
        self.assertEqual(refresh[0], OP_REFRESH_COMMAND_BAR)
        self.assertEqual(refresh[1], 0x678)
        self.assertEqual(refresh[2], 0x1000)
        self.assertEqual(refresh[3], 0x6000)
        self.assertEqual(refresh[4], 0x7000)
        self.assertEqual(refresh[7], 1)

    def test_native_hotkey_override_can_be_disabled_and_refreshed(self):
        bridge = NativeFrameBridge(Path("missing-test-helper.dll"))
        bridge.connect = lambda _hwnd, _pid: None
        bridge._command_bar = CommandBarInternals(
            game_ui_get=0x1000,
            command_bar_offset=0x678,
            submenu_link_offset=0x2E8,
            refresh_command_bar=0x6000,
            overriding_hotkey_enabled=0x7000,
        )
        captured = []
        bridge._dispatch = lambda _hwnd, _pid, operation, **kwargs: captured.append((operation, kwargs)) or 1

        bridge.set_command_hotkey_override_enabled(10, 20, False)

        operation, kwargs = captured[0]
        refresh = OP_STRUCT.unpack(operation)
        self.assertEqual(refresh[0], OP_REFRESH_COMMAND_BAR)
        self.assertEqual(refresh[7], 0)
        self.assertEqual(kwargs["expected_kind"], OP_REFRESH_COMMAND_BAR)

    def test_disabled_group_is_not_compiled_into_input_hooks(self):
        profile = default_profile()
        profile.enabled_groups["ability"] = False
        engine = HotkeyEngine(profile)
        compiled = [binding for values in engine._keyboard_bindings.values() for binding in values]
        self.assertFalse(any(binding.config.group == "ability" for binding in compiled))
        self.assertTrue(any(binding.config.group == "spellbook" for binding in compiled))

    def test_cached_window_refresh_does_not_rescan_windows(self):
        guard = WarcraftWindowGuard()
        guard._snapshot = GameWindowSnapshot(hwnd=123, pid=456, executable="Warcraft III.exe", title="Warcraft III")
        guard._cached_window_is_valid = lambda _snapshot: True
        guard._client_screen_rect = lambda _hwnd: (0, 0, 100, 100)
        guard._scan = lambda: (_ for _ in ()).throw(AssertionError("cached window unexpectedly rescanned"))
        snapshot = guard.snapshot(force=True)
        self.assertEqual(snapshot.hwnd, 123)
        self.assertEqual(snapshot.client_rect, (0, 0, 100, 100))

    def test_command_context_prioritizes_submenu_then_neutral_shop(self):
        owned = SelectionContext(True, False, 0)
        neutral = SelectionContext(True, True, 24)
        self.assertEqual(command_context_for(CommandContext(False), owned), "ability")
        self.assertEqual(command_context_for(CommandContext(False), neutral), "shop")
        self.assertEqual(command_context_for(CommandContext(True), neutral), "spellbook")

    def test_slot_groups_map_to_reforged_origin_frames(self):
        bridge = NativeFrameBridge(Path("missing-test-helper.dll"))
        calls = []
        bridge.click_origin = lambda hwnd, pid, frame_type, index, **kwargs: calls.append(
            (hwnd, pid, frame_type, index)
        ) or 123
        self.assertEqual(bridge.click_slot(10, 20, "ability", 4), 123)
        self.assertEqual(bridge.click_slot(10, 20, "spellbook", 5), 123)
        self.assertEqual(bridge.click_slot(10, 20, "shop", 6), 123)
        self.assertEqual(bridge.click_slot(10, 20, "item", 2), 123)
        self.assertEqual(calls, [
            (10, 20, ORIGIN_FRAME_COMMAND_BUTTON, 4),
            (10, 20, ORIGIN_FRAME_COMMAND_BUTTON, 5),
            (10, 20, ORIGIN_FRAME_COMMAND_BUTTON, 6),
            (10, 20, ORIGIN_FRAME_ITEM_BUTTON, 2),
        ])

    def test_key_capture_uses_virtual_keys_not_text_input(self):
        captured = []
        engine = HotkeyEngine(default_profile())
        engine.begin_key_capture(captured.append)
        self.assertTrue(engine._handle_key_capture(ord("Q"), True, False, False, frozenset({"CTRL"})))
        self.assertEqual(captured, ["Ctrl+Q"])

    def test_escape_cancels_key_capture(self):
        captured = []
        engine = HotkeyEngine(default_profile())
        engine.begin_key_capture(captured.append)
        self.assertTrue(engine._handle_key_capture(0x1B, True, False, False, frozenset()))
        self.assertEqual(captured, [None])

    def test_binding_selection_follows_live_command_context(self):
        engine = HotkeyEngine(default_profile())
        bindings = [
            CompiledBinding(
                BindingConfig(f"{group}_1", "Q", "Q", group=group, slot_index=0),
                parse_keystroke("Q"),
                parse_keystroke("Q", allow_mouse=False),
            )
            for group in ("ability", "spellbook", "shop")
        ]
        engine._command_context = "ability"
        self.assertEqual(engine._matching_binding(bindings, frozenset()).config.group, "ability")
        engine._command_context = "spellbook"
        self.assertEqual(engine._matching_binding(bindings, frozenset()).config.group, "spellbook")
        engine._command_context = "shop"
        self.assertEqual(engine._matching_binding(bindings, frozenset()).config.group, "shop")

    def test_item_binding_is_available_in_every_command_context(self):
        engine = HotkeyEngine(default_profile())
        binding = CompiledBinding(
            BindingConfig("item_1", "1", "1", group="item", slot_index=0),
            parse_keystroke("1"),
            parse_keystroke("1", allow_mouse=False),
        )
        for context in ("ability", "spellbook", "shop"):
            engine._command_context = context
            self.assertIs(engine._matching_binding([binding], frozenset()), binding)

    def test_passthrough_smartcast_only_clicks_current_cursor(self):
        profile = default_profile()
        profile.smartcast_delay_ms = 0
        binding = CompiledBinding(
            BindingConfig("ability_1", "Q", "Q", smartcast=True, group="ability", slot_index=0),
            parse_keystroke("Q"),
            parse_keystroke("Q", allow_mouse=False),
        )

        class Guard:
            @staticmethod
            def snapshot(*, force=False):
                return GameWindowSnapshot(hwnd=10, pid=20, foreground=True)

        class FrameBridge:
            def click_slot(self, *_args, **_kwargs):
                raise AssertionError("passthrough smartcast must not click the command frame")

        clicks = []
        engine = HotkeyEngine(profile, guard=Guard(), frame_bridge=FrameBridge())
        engine.sender.send_click = lambda button, **_kwargs: clicks.append(button) or True
        action = plan_binding_action(binding, frozenset(), profile)

        engine._execute_binding(action)

        self.assertFalse(action.send_target)
        self.assertEqual(clicks, ["left"])

    def test_enabled_normal_hotkey_is_not_swallowed_by_keyboard_hook(self):
        profile = default_profile()

        class Guard:
            @staticmethod
            def is_foreground():
                return True

        class User32:
            @staticmethod
            def CallNextHookEx(*_args):
                return 777

        engine = HotkeyEngine(profile, guard=Guard())
        event = KBDLLHOOKSTRUCT(ord("Q"), 0, 0, 0, 0)
        pointer = ctypes.addressof(event)
        with patch("war3_hotkey_engine.user32", User32):
            self.assertEqual(engine._keyboard_callback(0, WM_KEYDOWN, pointer), 777)
            self.assertEqual(engine._keyboard_callback(0, WM_KEYUP, pointer), 777)
        self.assertFalse(engine._active_binding_keys)
        self.assertTrue(engine._actions.empty())

    def test_enabled_smartcast_hotkey_passes_through_and_queues_click(self):
        profile = default_profile()
        profile.bindings[8].smartcast = True

        class Guard:
            @staticmethod
            def is_foreground():
                return True

        class User32:
            @staticmethod
            def CallNextHookEx(*_args):
                return 777

        engine = HotkeyEngine(profile, guard=Guard())
        event = KBDLLHOOKSTRUCT(ord("Q"), 0, 0, 0, 0)
        with patch("war3_hotkey_engine.user32", User32):
            self.assertEqual(engine._keyboard_callback(0, WM_KEYDOWN, ctypes.addressof(event)), 777)

        action = engine._actions.get_nowait()
        self.assertTrue(action.smartcast)
        self.assertFalse(action.send_target)
        self.assertFalse(engine._active_binding_keys)


class ConfigTests(unittest.TestCase):
    def test_default_profile_has_all_wfe_slot_grids(self):
        profile = default_profile()
        self.assertEqual(len([item for item in profile.bindings if item.group == "ability"]), 12)
        self.assertEqual(len([item for item in profile.bindings if item.group == "item"]), 6)
        self.assertEqual(len([item for item in profile.bindings if item.group == "spellbook"]), 12)
        self.assertEqual(len([item for item in profile.bindings if item.group == "shop"]), 12)
        validate_profile(profile)

    def test_config_round_trip_preserves_all_slot_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            config = default_app_config()
            config.profiles["Default"].bindings[0].source = "Ctrl+Q"
            store.save(config)
            loaded = store.load()
            self.assertEqual(len(loaded.profiles["Default"].bindings), 42)
            self.assertEqual(loaded.profiles["Default"].bindings[0].source, "Ctrl+Q")
            json.loads(store.path.read_text(encoding="utf-8"))

    def test_legacy_command_and_inventory_bindings_are_migrated(self):
        profile = profile_from_dict({
            "bindings": [
                {"binding_id": "command_1", "source": "F1", "target": "Q", "group": "command", "slot_index": 0},
                {"binding_id": "inventory_1", "source": "F2", "target": "NUM7", "group": "inventory", "slot_index": 0},
            ]
        })
        by_id = {binding.binding_id: binding for binding in profile.bindings}
        self.assertEqual(by_id["ability_1"].source, "F1")
        self.assertEqual(by_id["ability_1"].target, "F1")
        self.assertEqual(by_id["item_1"].source, "F2")
        self.assertEqual(len(profile.bindings), 42)
        self.assertEqual(profile.enabled_groups, {
            "ability": True,
            "item": True,
            "spellbook": True,
            "shop": True,
        })

    def test_group_switches_round_trip_and_disabled_group_allows_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ConfigStore(Path(directory) / "config.json")
            config = default_app_config()
            profile = config.profiles["Default"]
            profile.enabled_groups["ability"] = False
            profile.bindings[0].source = "Q"
            profile.bindings[8].source = "Q"

            store.save(config)
            loaded = store.load()

            self.assertFalse(loaded.profiles["Default"].enabled_groups["ability"])


if __name__ == "__main__":
    unittest.main()
