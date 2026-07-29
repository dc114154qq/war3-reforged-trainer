import struct
import unittest
from unittest.mock import patch

import war3_reforged_trainer as trainer


def rawcode(value: str) -> int:
    return struct.unpack(">I", value.encode("ascii"))[0]


class FakeProcessMemory:
    def __init__(self, values: dict[int, int]):
        self.values = dict(values)

    def read_u32(self, address: int) -> int:
        return self.values.get(address, 0)

    def write_u32(self, address: int, value: int) -> None:
        self.values[address] = value & 0xFFFFFFFF


class HeroSkillWriteTests(unittest.TestCase):
    HERO_DATA = 0x100000
    CONFIG_BASE = HERO_DATA + 0x204
    CACHE_BASE = HERO_DATA + 0x1BC
    CANDIDATE = trainer.UnitCandidate(
        base=0,
        score=0,
        hp_current_address=0,
        hp_max_address=0,
        mp_current_address=0,
        mp_max_address=0,
        note="test",
        owner_address=0x200000,
        unit_address=0x300000,
    )
    FIELD = trainer.UnitMemoryField(
        key="skill2_name",
        label="skill2",
        value_type="rawcode",
        value=rawcode("AHds"),
        address=CONFIG_BASE + 4,
        category="hero",
    )

    def setUp(self) -> None:
        self.subject = object.__new__(trainer.War3Trainer)
        self.old_rawcode = rawcode("AHds")
        self.new_rawcode = rawcode("AOsh")
        self.pm = FakeProcessMemory(
            {
                self.CONFIG_BASE + 4: self.old_rawcode,
                self.CACHE_BASE + 4: self.old_rawcode,
            }
        )

    def write_skill(self, native_level: int):
        with (
            patch.object(
                self.subject,
                "_selected_components",
                return_value={"hero": (0x400000, self.HERO_DATA)},
            ),
            patch.object(
                self.subject,
                "_hero_skill_instance_map_for_write",
                return_value=({}, []),
            ),
            patch.object(
                self.subject,
                "_selected_ability_level_for_candidate",
                return_value=native_level,
            ),
            patch.object(self.subject, "_find_engine_ability_data", return_value=0),
            patch.object(
                self.subject,
                "_refresh_selected_hero_command_card",
                return_value=False,
            ),
            patch.object(trainer.time, "sleep", return_value=None),
        ):
            return self.subject._write_hero_skill_name_field(
                self.pm,
                self.CANDIDATE,
                self.FIELD,
                self.new_rawcode,
            )

    def test_unlearned_skill_without_runtime_instance_updates_config_and_cache(self):
        result = self.write_skill(native_level=0)

        self.assertEqual(self.pm.read_u32(self.CONFIG_BASE + 4), self.new_rawcode)
        self.assertEqual(self.pm.read_u32(self.CACHE_BASE + 4), self.new_rawcode)
        self.assertEqual(result.value, self.new_rawcode)
        self.assertIn("native", result.note)

    def test_learned_skill_without_runtime_instance_is_rejected(self):
        with self.assertRaises(RuntimeError) as raised:
            self.write_skill(native_level=1)

        self.assertIn("native", str(raised.exception))
        self.assertEqual(self.pm.read_u32(self.CONFIG_BASE + 4), self.old_rawcode)
        self.assertEqual(self.pm.read_u32(self.CACHE_BASE + 4), self.old_rawcode)

    def test_missing_fast_path_instance_uses_unique_global_scan_match(self):
        fallback = trainer.AbilityInstance(
            slot=0,
            wrapper_address=0x500000,
            data_address=0x600000,
            wrapper_vtable=0x700000,
            data_vtable=0x800000,
            wrapper_tag_address=0x500018,
            wrapper_tag=0,
            handle=0x123,
            class_rawcode=self.old_rawcode,
            rawcode=self.old_rawcode,
            rawcode_address=0x600070,
        )
        with (
            patch.object(self.subject, "_find_engine_ability_data", return_value=0),
            patch.object(
                self.subject,
                "_ability_instances_from_candidate",
                return_value=[fallback],
            ) as scan,
        ):
            mapped, instances = self.subject._hero_skill_instance_map_for_write(
                self.pm,
                self.CANDIDATE,
                [0, self.old_rawcode, 0, 0, 0],
            )

        self.assertEqual(mapped[1].slot, 2)
        self.assertEqual(mapped[1].data_address, fallback.data_address)
        self.assertEqual(instances, [mapped[1]])
        scan.assert_called_once_with(
            self.pm,
            self.CANDIDATE,
            required_rawcodes={self.old_rawcode},
            allow_global_scan=True,
        )


if __name__ == "__main__":
    unittest.main()
