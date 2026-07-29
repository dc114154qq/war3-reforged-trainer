import math
import struct
import unittest
from unittest.mock import patch

import war3_reforged_trainer as trainer


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


class FakeProcessMemory:
    def __init__(self, values: dict[int, float]):
        self.values = dict(values)
        self.writes: list[tuple[int, float]] = []

    def read_f32(self, address: int) -> float:
        return self.values[address]

    def write_f32(self, address: int, value: float) -> None:
        stored = f32(value)
        self.values[address] = stored
        self.writes.append((address, stored))


class LargeNumericRereadTests(unittest.TestCase):
    OWNER = 0x2000
    HP_PROP = 0x3000
    MP_PROP = 0x4000
    UNIT = 0x5000

    def setUp(self) -> None:
        self.subject = object.__new__(trainer.War3Trainer)
        offset = trainer.War3Trainer.SELECTED_HP_VALUE_OFFSET
        self.hp_current = self.HP_PROP + offset
        self.hp_max = self.hp_current + 0x10
        self.mp_current = self.MP_PROP + offset
        self.mp_max = self.mp_current + 0x10
        self.pm = FakeProcessMemory(
            {
                self.hp_current: f32(1000.0),
                self.hp_max: f32(1000.0),
                self.mp_current: f32(500.0),
                self.mp_max: f32(500.0),
            }
        )

    def candidate(self):
        def property_for_owner(_pm, owner, kind):
            self.assertEqual(owner, self.OWNER)
            return self.HP_PROP if kind == 1 else self.MP_PROP if kind == 2 else None

        with (
            patch.object(
                self.subject,
                "_property_from_owner",
                side_effect=property_for_owner,
            ),
            patch.object(
                self.subject,
                "_position_property_from_owner",
                return_value=None,
            ),
            patch.object(
                self.subject,
                "_unit_object_from_owner",
                return_value=self.UNIT,
            ),
        ):
            return self.subject._candidate_from_owner(
                self.pm,
                self.OWNER,
                1000,
                "test",
                handle=0x1234,
            )

    def test_large_vitals_can_be_reread_after_successful_write(self):
        before = self.candidate()
        self.assertIsNotNone(before)
        stored = f32(1.0e20)

        self.subject._write_basic_unit_values_to_candidate(
            self.pm,
            before,
            target_hp=stored,
            target_mp=stored,
            max_hp=stored,
            max_mp=stored,
        )

        after = self.candidate()
        self.assertIsNotNone(after)
        self.assertEqual(after.mp_current_address, self.mp_current)
        panel = self.subject._panel_from_candidate(self.pm, after)
        self.assertEqual(panel.current_hp, int(round(stored)))
        self.assertEqual(panel.current_mp, int(round(stored)))

        fields = []
        self.subject._append_unit_field(
            self.pm,
            fields,
            "hp_current",
            "hp",
            "f32",
            self.hp_current,
            "test",
        )
        self.assertEqual(len(fields), 1)
        self.assertNotIn("e", fields[0].value_text().lower())
        self.assertEqual(f32(float(fields[0].value_text())), stored)

    def test_invalid_float32_values_are_rejected_before_any_write(self):
        candidate = self.candidate()
        for invalid in ("nan", "inf", "1e500"):
            self.pm.writes.clear()
            with self.assertRaises(ValueError):
                self.subject._write_basic_unit_values_to_candidate(
                    self.pm,
                    candidate,
                    target_hp=invalid,
                    target_mp=None,
                    max_hp=None,
                    max_mp=None,
                )
            self.assertEqual(self.pm.writes, [])

    def test_large_finite_values_pass_vital_validation(self):
        self.assertTrue(self.subject._valid_current_limit(f32(1.0e20), f32(1.0e20)))
        self.assertFalse(self.subject._valid_current_limit(math.inf, f32(1.0e20)))
        self.assertFalse(self.subject._valid_current_limit(1.0, -1.0))

    def test_plain_decimal_float32_text_round_trips_extreme_values(self):
        for value in (
            12_345_678.0,
            1.0e20,
            1.0e-10,
            -98_765_432.0,
            1.401298464324817e-45,
        ):
            with self.subTest(value=value):
                stored = f32(value)
                text = trainer.format_editable_float32(stored)
                self.assertNotIn("e", text.lower())
                self.assertEqual(f32(float(text)), stored)

    def test_integer_scientific_notation_is_exact(self):
        self.assertEqual(trainer.parse_integer_number("1e6"), 1_000_000)
        self.assertEqual(trainer.parse_integer_number("-2.5e2"), -250)
        with self.assertRaises(ValueError):
            trainer.parse_integer_number("1e-1")


if __name__ == "__main__":
    unittest.main()
