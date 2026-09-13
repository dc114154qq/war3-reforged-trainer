import importlib.util
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest

from test_classic_player_selection import Memory

spec = importlib.util.spec_from_file_location("loader_probe", Path(__file__).parent / "analysis/probe-loader-index-live.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class LoaderProbeTests(unittest.TestCase):
    def fixture(self, base=0x7FFDB5130000):
        memory = Memory()
        game = 0x7FF7229D0000
        header = bytearray(0x40)
        header[:2] = b"MZ"
        struct.pack_into("<I", header, 0x3C, 0x80)
        nt = bytearray(0x58)
        nt[:4] = b"PE\0\0"
        struct.pack_into("<H", nt, 4, 0x8664)
        struct.pack_into("<I", nt, 8, 42)
        struct.pack_into("<I", nt, 0x50, 0x2660000)
        memory.put(base, header)
        memory.put(base + 0x80, nt)
        memory.put(base + 0x21B6C40, struct.pack("<10Q", 0x3036, base, 0, 0,
                   base + 0x22906E8, 0x12DA, game, game + 0xE155000, 0, 0))
        data = struct.pack("<512I", *range(0x252BA, 0x254BA))
        memory.put(base + 0x22906E8, data)
        pe = SimpleNamespace(FILE_HEADER=SimpleNamespace(Machine=0x8664, TimeDateStamp=42),
             OPTIONAL_HEADER=SimpleNamespace(SizeOfImage=0x2660000),
             sections=[SimpleNamespace(VirtualAddress=0x2290000, Misc_VirtualSize=0x3D0000, Name=b".eid\0")],
             get_data=lambda rva, size: data)
        return memory, game, pe

    def test_context_rva_and_sample_remain_valid_after_aslr(self):
        for base in (0x7FFDB5130000, 0x7FFF0EA40000):
            with self.subTest(base=base):
                memory, game, pe = self.fixture(base)
                report = probe.inspect_context(memory, base, game, pe)
                self.assertEqual(report["context_rva"], "0x21b6c40")
                self.assertEqual(report["table_section"], ".eid")
                self.assertTrue(report["sample_matches_disk"])

    def test_stale_game_base_is_rejected_before_array_read(self):
        base = 0x7FFDB5130000
        memory, game, pe = self.fixture(base)
        del memory.data[base + 0x22906E8]
        with self.assertRaisesRegex(ValueError, "module bases"):
            probe.inspect_context(memory, base, game + 0x10000, pe)

    def test_wrong_pe_identity_is_rejected(self):
        base = 0x7FFDB5130000
        memory, game, pe = self.fixture(base)
        pe.FILE_HEADER.TimeDateStamp += 1
        with self.assertRaisesRegex(ValueError, "PE identity"):
            probe.inspect_context(memory, base, game, pe)

    def test_sample_outside_section_is_rejected(self):
        base = 0x7FFDB5130000
        memory, game, pe = self.fixture(base)
        pe.sections[0].Misc_VirtualSize = 0x700
        with self.assertRaisesRegex(ValueError, "outside loader sections"):
            probe.inspect_context(memory, base, game, pe)

    def test_short_read_is_not_treated_as_zero_data(self):
        base = 0x7FFDB5130000
        memory, game, pe = self.fixture(base)
        original = memory.read
        memory.read = lambda a, n: original(a, n)[:-1]
        with self.assertRaisesRegex(ValueError, "Short read"):
            probe.inspect_context(memory, base, game, pe)


if __name__ == "__main__":
    unittest.main()
