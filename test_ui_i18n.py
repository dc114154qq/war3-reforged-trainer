# -*- coding: utf-8 -*-

import ast
import re
import unittest
from pathlib import Path

import war3_reforged_trainer as trainer
from war3_ui_i18n import detect_ui_language, translate_ui_text


HAN_TEXT = re.compile(r"[\u4e00-\u9fff]")


class UiLocalizationTests(unittest.TestCase):
    def test_dark_theme_configures_black_surfaces_and_white_text(self):
        class Root:
            def __init__(self):
                self.config = {}
                self.options = {}
            def configure(self, **kwargs):
                self.config.update(kwargs)
            def option_add(self, pattern, value):
                self.options[pattern] = value
            def winfo_class(self):
                return "Tk"
            def winfo_children(self):
                return ()
        class Style:
            def __init__(self):
                self.config = {}
                self.maps = {}
            def theme_names(self):
                return ("clam",)
            def theme_use(self, name):
                self.theme = name
            def configure(self, name, **kwargs):
                self.config[name] = kwargs
            def map(self, name, **kwargs):
                self.maps[name] = kwargs
        root, style = Root(), Style()
        palette = trainer.apply_ui_theme(root, style, True)
        self.assertEqual(palette["background"], "#0f1115")
        self.assertEqual(palette["foreground"], "#f4f5f7")
        self.assertEqual(root.config["background"], palette["background"])
        self.assertEqual(style.config["Treeview"]["foreground"], palette["foreground"])
        self.assertEqual(style.config["TEntry"]["fieldbackground"], palette["field"])

    def test_dark_mode_toggle_stays_in_the_visible_left_toolbar(self):
        source = Path(trainer.__file__).read_text(encoding="utf-8")
        hotkey = source.index('text="启用全局快捷键"')
        dark = source.index('text="深色模式"')
        pid = source.index('ttk.Label(top, text="PID")')
        self.assertLess(hotkey, dark)
        self.assertLess(dark, pid)
        self.assertEqual(source.count('text="深色模式"'), 1)
        dark_block = source[dark:pid]
        self.assertIn('.pack(side="left"', dark_block)

    def test_detects_chinese_windows_locales(self):
        self.assertEqual(detect_ui_language("zh-CN"), "zh")
        self.assertEqual(detect_ui_language("zh_Hant_TW"), "zh")

    def test_defaults_non_chinese_locales_to_english(self):
        self.assertEqual(detect_ui_language("en-US"), "en")
        self.assertEqual(detect_ui_language("de-DE"), "en")

    def test_chinese_mode_preserves_source_text(self):
        source = "备用读取失败：WinError 299"
        self.assertEqual(translate_ui_text(source, "zh"), source)

    def test_english_mode_preserves_technical_values(self):
        translated = translate_ui_text(
            "技能 AOsh 已添加；handle=0x1234",
            "en",
        )
        self.assertNotRegex(translated, HAN_TEXT)
        self.assertIn("AOsh", translated)
        self.assertIn("0x1234", translated)

    def test_all_trainer_literals_and_hotkey_labels_have_english_display(self):
        source_path = Path(trainer.__file__)
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        display_sources: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                values = (node.value,)
            elif isinstance(node, ast.JoinedStr):
                values = tuple(
                    value.value
                    for value in node.values
                    if isinstance(value, ast.Constant) and isinstance(value.value, str)
                )
            else:
                values = ()
            display_sources.update(value for value in values if HAN_TEXT.search(value))
        display_sources.update(spec.label for spec in trainer.ELEPHANT_HOTKEY_SPECS)
        display_sources.discard("中文")

        untranslated = {
            source_text: translate_ui_text(source_text, "en")
            for source_text in display_sources
            if HAN_TEXT.search(translate_ui_text(source_text, "en"))
        }
        self.assertEqual(untranslated, {})


if __name__ == "__main__":
    unittest.main()
