import unittest
from pathlib import Path

import war3_reforged_trainer as trainer
from war3_item_fields import ITEM_FIELD_BY_KEY, ITEM_FIELD_CATALOG, rawcode_to_int


class ItemFieldCatalogTests(unittest.TestCase):
    def test_catalog_contains_all_reforged_numeric_and_boolean_item_fields(self):
        self.assertEqual(len(ITEM_FIELD_CATALOG), 20)
        self.assertEqual(
            {field.value_kind for field in ITEM_FIELD_CATALOG},
            {"boolean", "integer", "real", "string"},
        )
        self.assertEqual(
            sum(field.runtime_supported for field in ITEM_FIELD_CATALOG),
            19,
        )

    def test_field_ids_are_big_endian_rawcodes(self):
        for field in ITEM_FIELD_CATALOG:
            self.assertEqual(field.field_id, rawcode_to_int(field.rawcode))
            self.assertIs(ITEM_FIELD_BY_KEY[(field.rawcode, field.value_kind)], field)

    def test_item_field_native_ops_are_whitelisted(self):
        source = Path(trainer.__file__).read_text(encoding="utf-8")
        self.assertIn("NATIVE_HELPER_OP_JASS_ITEM_FIELD_GET = 115", source)
        self.assertIn("NATIVE_HELPER_OP_JASS_ITEM_FIELD_SET = 116", source)
        self.assertIn('"BlzGetItemIntegerField"', source)
        self.assertIn('"BlzSetItemRealField"', source)

    def test_normal_edition_item_fields_use_fixed_normal_source(self):
        source = Path(trainer.__file__).read_text(encoding="utf-8")
        self.assertIn('PRODUCT_READ_MODE = "normal"', source)
        self.assertIn("win10_compat=current_display_uses_win10()", source)


if __name__ == "__main__":
    unittest.main()
