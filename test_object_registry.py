import struct
import unittest

from test_classic_player_selection import Memory
from war3_object_registry import (
    ObjectRegistry24268, ObjectIdentityError, TIMESTAMP, IMAGE_SIZE,
    RESOLVER_RVA, RESOLVER_CODE, ROOT_RVA, UNIT_TAG, PLAYER_TAG,
    GAME_STATE_SLOT_RVA, GAME_STATE_CHECKS, decode_game_state,
)


class RegistryFixture(Memory):
    def __init__(self, base=0x7FF7229D0000):
        super().__init__()
        self.base, self.root, self.table, self.alternate = base, 0x400000, 0x500000, 0x580000
        header = bytearray(0x40)
        header[:2] = b"MZ"
        struct.pack_into("<I", header, 0x3C, 0x80)
        nt = bytearray(0x58)
        nt[:4] = b"PE\0\0"
        struct.pack_into("<H", nt, 4, 0x8664)
        struct.pack_into("<I", nt, 8, TIMESTAMP)
        struct.pack_into("<I", nt, 0x50, IMAGE_SIZE)
        self.put(base, header)
        self.put(base + 0x80, nt)
        self.put(base + RESOLVER_RVA, RESOLVER_CODE)
        for rva, code in GAME_STATE_CHECKS:
            self.put(base + rva, code)
        self.put(base + ROOT_RVA, struct.pack("<Q", self.root))
        for offset, table in ((0x18, self.table), (0x50, self.alternate)):
            self.put(self.root + offset, struct.pack("<Q16xI", table, 1))

    def unit(self, index, generation=10, *, alternate=False, owner=0x700000, unit=0x600000):
        handle = (generation << 32) | index | (0x80000000 if alternate else 0)
        table = self.alternate if alternate else self.table
        self.put(self.root + (0x68 if alternate else 0x30), struct.pack("<I", index + 1))
        self.put(table + index * 16, struct.pack("<IIQ", 0xFFFFFFFE, 0, owner))
        self.put(owner + 0x18, struct.pack("<QQ", UNIT_TAG, handle))
        self.put(owner + 0x90, struct.pack("<Q", unit))
        self.put(unit + 0x18, struct.pack("<Q", handle))
        return handle, owner, unit

    def player_array(self, count):
        state = 0x900000
        mask = (1 << 64) - 1
        value = ((state - 0x2D2C27903E7F5D3D) & mask) ^ 0x3A11C7B7EF67132B
        value = (value - 0x5BE06F37FC9B5B29) & mask
        value = ((value >> 30) | (value << 34)) & mask
        encoded = ((value << 1) | (value >> 63)) & mask
        self.put(self.base + GAME_STATE_SLOT_RVA, struct.pack("<Q", encoded))
        players = []
        for i in range(count):
            _, owner, player = self.unit(i, generation=i, owner=0x700000+i*0x1000, unit=0x600000+i*0x1000)
            self.put(owner + 0x18, struct.pack("<Q", PLAYER_TAG))
            players.append(player)
        self.put(state + 0x2698, struct.pack("<I", count))
        self.put(state + 0x26A0, struct.pack(f"<{count}Q", *players))
        return state, players


class ObjectRegistryTests(unittest.TestCase):
    def test_decoder_matches_live_observation(self):
        self.assertEqual(decode_game_state(0x8729A1FC670D744E), 0x2066166F980)

    def test_player_array_with_relocated_image_and_zero_player_handle(self):
        for count in (1, 28):
            with self.subTest(count=count):
                memory = RegistryFixture(0x140000000)
                _, players = memory.player_array(count)
                registry = ObjectRegistry24268(memory, memory.base)
                self.assertEqual(registry.players(memory), players)

    def test_wrong_player_count_duplicate_and_type_are_rejected(self):
        for fault in ("count", "duplicate", "type"):
            with self.subTest(fault=fault):
                memory = RegistryFixture()
                state, players = memory.player_array(2)
                registry = ObjectRegistry24268(memory, memory.base)
                if fault == "count":
                    memory.put(state + 0x2698, struct.pack("<I", 29))
                elif fault == "duplicate":
                    memory.put(state + 0x26A8, struct.pack("<Q", players[0]))
                else:
                    memory.put(0x700000 + 0x18, struct.pack("<Q", UNIT_TAG))
                with self.assertRaises(ObjectIdentityError):
                    registry.players(memory)

    def test_changed_player_accessor_is_rejected(self):
        memory = RegistryFixture()
        memory.put(memory.base + GAME_STATE_CHECKS[-1][0], b"\xcc")
        with self.assertRaisesRegex(ObjectIdentityError, "player-array code"):
            ObjectRegistry24268(memory, memory.base)

    def test_relocated_image_and_both_index_branches(self):
        for base in (0x7FF7229D0000, 0x140000000):
            for alternate in (False, True):
                with self.subTest(base=base, alternate=alternate):
                    memory = RegistryFixture(base)
                    handle, owner, unit = memory.unit(4, alternate=alternate)
                    registry = ObjectRegistry24268(memory, base)
                    self.assertEqual(registry.resolve_unit(memory, unit), (handle, owner))

    def test_new_unit_appears_without_rebuilding_an_index(self):
        memory = RegistryFixture()
        registry = ObjectRegistry24268(memory, memory.base)
        first = memory.unit(1)
        self.assertEqual(registry.resolve_unit(memory, first[2]), first[:2])
        second = memory.unit(7, owner=0x701000, unit=0x601000)
        self.assertEqual(registry.resolve_unit(memory, second[2]), second[:2])
        self.assertEqual(registry.resolve_unit(memory, first[2]), first[:2])

    def test_stale_generation_rejected_after_slot_reuse(self):
        memory = RegistryFixture()
        first = memory.unit(1)
        registry = ObjectRegistry24268(memory, memory.base)
        replacement = memory.unit(1, generation=11, owner=0x701000, unit=0x601000)
        with self.assertRaisesRegex(ObjectIdentityError, "generation"):
            registry.resolve_handle(memory, first[0])
        self.assertEqual(registry.resolve_unit(memory, replacement[2]), replacement[:2])

    def test_free_slot_and_out_of_bounds_are_rejected(self):
        memory = RegistryFixture()
        handle, _, _ = memory.unit(1)
        registry = ObjectRegistry24268(memory, memory.base)
        with self.assertRaisesRegex(ObjectIdentityError, "bounds"):
            registry.resolve_handle(memory, handle + 1)
        memory.put(memory.table + 16, struct.pack("<I", 0xFFFFFFFF))
        with self.assertRaisesRegex(ObjectIdentityError, "not live"):
            registry.resolve_handle(memory, handle)

    def test_wrong_unit_backlink_or_tag_is_rejected(self):
        for fault in ("backlink", "tag"):
            with self.subTest(fault=fault):
                memory = RegistryFixture()
                _, owner, unit = memory.unit(1)
                registry = ObjectRegistry24268(memory, memory.base)
                memory.put(owner + (0x90 if fault == "backlink" else 0x18), struct.pack("<Q", 0x800000))
                with self.assertRaisesRegex(ObjectIdentityError, "mismatches"):
                    registry.resolve_unit(memory, unit)

    def test_old_build_or_modified_code_does_not_use_profile(self):
        for fault in ("version", "code"):
            with self.subTest(fault=fault):
                memory = RegistryFixture()
                if fault == "version":
                    memory.put(memory.base + 0x88, struct.pack("<I", 0x69E54471))
                else:
                    memory.put(memory.base + RESOLVER_RVA, b"\xcc")
                with self.assertRaises(ObjectIdentityError):
                    ObjectRegistry24268(memory, memory.base)

    def test_table_move_during_lookup_is_rejected(self):
        memory = RegistryFixture()
        handle, _, _ = memory.unit(1)
        registry = ObjectRegistry24268(memory, memory.base)
        original = memory.read
        def moving_table(address, size):
            result = original(address, size)
            if address == memory.table + 16:
                memory.put(memory.root + 0x18, struct.pack("<Q", 0x590000))
            return result
        memory.read = moving_table
        with self.assertRaisesRegex(ObjectIdentityError, "changed"):
            registry.resolve_handle(memory, handle)

    def test_zero_full_handle_is_valid_for_non_unit_agent(self):
        memory = RegistryFixture()
        handle, owner, _ = memory.unit(0, generation=0)
        registry = ObjectRegistry24268(memory, memory.base)
        self.assertEqual(handle, 0)
        self.assertEqual(registry.resolve_handle(memory, handle), owner)

    def test_incomplete_read_is_rejected(self):
        memory = RegistryFixture()
        original = memory.read
        memory.read = lambda a, n: original(a, n)[:-1]
        with self.assertRaisesRegex(ObjectIdentityError, "Incomplete"):
            ObjectRegistry24268(memory, memory.base)


if __name__ == "__main__":
    unittest.main()
