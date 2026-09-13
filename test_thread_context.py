import struct
import unittest
from unittest.mock import patch

from test_classic_player_selection import Memory
from war3_thread_context import GameThreadContext24268, TLS_INDEX_RVA, infer_tls_layout
from war3_object_registry import ObjectIdentityError


class ThreadContextTests(unittest.TestCase):
    def fixture(self, index=22):
        memory = Memory()
        reader = object.__new__(GameThreadContext24268)
        reader.base, reader.teb, reader.tid = 0x140000000, 0x900000, 123
        reader.primary_offset, reader.expansion_offset = 0x1480, 0x1780
        reader._window_thread = lambda: reader.tid
        memory.put(reader.base + TLS_INDEX_RVA, struct.pack("<I", index))
        if index < 64:
            slot = reader.teb + reader.primary_offset + index * 8
        else:
            memory.put(reader.teb + reader.expansion_offset, struct.pack("<Q", 0x980000))
            slot = 0x980000 + (index - 64) * 8
        memory.put(slot, struct.pack("<Q", 0xA00000))
        memory.put(0xA00078, struct.pack("<Q", 0xB00000))
        memory.put(0xB00020, struct.pack("<Q", 0xC00000))
        memory.put(0xC000B8, struct.pack("<Q", 0xD00000))
        memory.put(0xD030E8, struct.pack("<I", 1))
        return memory, reader, slot

    def test_derives_offsets_from_direct_gs_and_indirect_teb_forms(self):
        direct = bytes.fromhex("65488b04cd8014000065480b042580170000")
        indirect = bytes.fromhex("65488b042530000000488b84c880140000488b8880170000")
        self.assertEqual(infer_tls_layout(direct), (0x1480, 0x1780))
        self.assertEqual(infer_tls_layout(indirect), (0x1480, 0x1780))

    def test_derivation_is_not_fixed_to_this_os_offsets(self):
        code = bytes.fromhex("65488b04cd0018000065480b042500200000")
        self.assertEqual(infer_tls_layout(code), (0x1800, 0x2000))

    def test_unknown_or_ambiguous_os_code_is_rejected(self):
        for code in (b"\xc3", bytes.fromhex("65488b04cd8014000065488b04cd0018000065480b042580170000")):
            with self.assertRaises(ObjectIdentityError):
                infer_tls_layout(code)

    def test_primary_and_expanded_tls_indexes(self):
        for index in (0, 22, 63, 64, 1087):
            with self.subTest(index=index):
                memory, reader, _ = self.fixture(index)
                result = reader.read_mode(memory)
                self.assertEqual((result.value, result.tls_index, result.mode_object), (1, index, 0xD00000))

    def test_inactive_slot_has_no_fabricated_mode(self):
        memory, reader, slot = self.fixture()
        memory.put(slot, struct.pack("<Q", 0))
        self.assertIsNone(reader.sample_mode(memory))
        with self.assertRaisesRegex(ObjectIdentityError, "inactive"):
            reader.read_mode(memory, timeout_ms=0)

    def test_frame_disappearing_or_mode_changing_is_retried(self):
        for change in ("slot", "value", "index"):
            with self.subTest(change=change):
                memory, reader, slot = self.fixture()
                original = memory.read
                def read(address, size):
                    result = original(address, size)
                    if address == 0xD030E8:
                        target = {"slot": slot, "value": 0xD030E8, "index": reader.base + TLS_INDEX_RVA}[change]
                        memory.put(target, struct.pack("<Q" if change == "slot" else "<I", 0))
                    return result
                memory.read = read
                self.assertIsNone(reader.sample_mode(memory))

    def test_retry_stops_after_a_real_frame_sample(self):
        memory, reader, _ = self.fixture()
        real = reader.sample_mode(memory)
        with patch.object(reader, "sample_mode", side_effect=[None, real]), patch("war3_thread_context.time.sleep"):
            result = reader.read_mode(memory)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(result.value, 1)

    def test_retired_frame_read_retries_but_access_denied_does_not(self):
        memory, reader, _ = self.fixture()
        real = reader.sample_mode(memory)
        retired = OSError("retired page")
        retired.winerror = 299
        with patch.object(reader, "sample_mode", side_effect=[retired, real]), patch("war3_thread_context.time.sleep"):
            self.assertEqual(reader.read_mode(memory).attempts, 2)
        denied = OSError("access denied")
        denied.winerror = 5
        with patch.object(reader, "sample_mode", side_effect=denied):
            with self.assertRaises(OSError):
                reader.read_mode(memory)

    def test_thread_replacement_and_invalid_index_are_rejected(self):
        memory, reader, _ = self.fixture()
        reader._window_thread = lambda: 456
        with self.assertRaisesRegex(ObjectIdentityError, "thread changed"):
            reader.read_mode(memory)
        memory.put(reader.base + TLS_INDEX_RVA, struct.pack("<I", 1088))
        with self.assertRaisesRegex(ObjectIdentityError, "TLS bounds"):
            reader.sample_mode(memory)


if __name__ == "__main__":
    unittest.main()
