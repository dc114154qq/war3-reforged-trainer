# -*- coding: utf-8 -*-

import unittest

from war3_id_catalog import CATALOG_COUNTS, ID_CATALOG, search_id_entries


class War3IdCatalogTests(unittest.TestCase):
    def test_catalog_contains_expected_object_counts(self):
        self.assertEqual(CATALOG_COUNTS, {"item": 283, "ability": 833, "unit": 864})

    def test_rawcodes_are_four_character_keys(self):
        for entries in ID_CATALOG.values():
            rawcodes = [entry.rawcode for entry in entries]
            self.assertEqual(len(rawcodes), len(set(rawcodes)))
            self.assertTrue(all(len(rawcode) == 4 for rawcode in rawcodes))

    def test_known_entries_have_bilingual_names(self):
        item = search_id_entries("item", "ckng")[0]
        ability = search_id_entries("ability", "AHhb")[0]
        unit = search_id_entries("unit", "Hpal")[0]
        self.assertEqual((item.name_zh, item.name_en), ("列王之冠+5", "Crown of Kings +5"))
        self.assertEqual((ability.name_zh, ability.name_en), ("圣光术", "Holy Light"))
        self.assertEqual((unit.name_zh, unit.name_en), ("圣骑士", "Paladin"))

    def test_search_matches_both_languages(self):
        self.assertIn("AHhb", {entry.rawcode for entry in search_id_entries("ability", "圣光")})
        self.assertIn("AHhb", {entry.rawcode for entry in search_id_entries("ability", "holy light")})
        self.assertIn("Hpal", {entry.rawcode for entry in search_id_entries("unit", "paladin")})


if __name__ == "__main__":
    unittest.main()
