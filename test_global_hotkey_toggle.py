from pathlib import Path
import unittest

import war3_reforged_trainer as trainer


class GlobalHotkeyToggleTests(unittest.TestCase):
    def test_v103_places_single_hotkey_toggle_in_global_toolbar(self):
        source = Path(trainer.__file__).read_text(encoding="utf-8")
        toggle = 'text="启用全局快捷键"'

        self.assertEqual(source.count(toggle), 1)
        self.assertLess(source.index("top = ttk.Frame(outer)"), source.index(toggle))
        self.assertLess(source.index(toggle), source.index("notebook = ttk.Notebook(outer)"))
        self.assertIn("command=refresh_elephant_hotkeys", source[source.index(toggle) :][:180])


if __name__ == "__main__":
    unittest.main()
