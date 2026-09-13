import struct
import unittest
from unittest.mock import Mock

from war3_classic_selection import read_player_selection, SelectionReadError
from war3_reforged_trainer import War3Trainer


class Memory:
    def __init__(self):
        self.data = {}

    def put(self, address, data):
        self.data.update({address + i: v for i, v in enumerate(data)})

    def read(self, address, size):
        try:
            return bytes(self.data[address + i] for i in range(size))
        except KeyError as exc:
            raise OSError("Unmapped fixture read") from exc

    def player(self, player, count, first_unit=0x800000):
        manager = player + 0x7A8
        sentinel = (manager + 0x10) | 1
        nodes = [player + 0x100000 + i * 0x20 for i in range(count)]
        self.put(player + 0x168, struct.pack("<Q", manager))
        self.put(manager + 0x10, struct.pack("<QQII", nodes[-1] if nodes else manager + 0x10,
                                           nodes[0] if nodes else sentinel, count, 0))
        for i, node in enumerate(nodes):
            self.put(node + 8, struct.pack("<QQ", nodes[i + 1] if i + 1 < count else sentinel,
                                          first_unit + i * 0x1000))
        return manager, nodes


class SelectionTests(unittest.TestCase):
    def test_empty_and_1_14_24_units_with_relocated_players(self):
        for player in (0x200000, 0x2066DBFB018):
            for count in (0, 1, 14, 24):
                with self.subTest(player=player, count=count):
                    memory = Memory()
                    manager, _ = memory.player(player, count)
                    snapshot = read_player_selection(memory, player)
                    self.assertEqual((snapshot.player, snapshot.manager), (player, manager))
                    self.assertEqual(snapshot.units, tuple(0x800000 + i * 0x1000 for i in range(count)))

    def test_bad_count_tail_cycle_and_duplicate_are_rejected(self):
        for fault in ("count", "tail", "cycle", "duplicate", "short"):
            with self.subTest(fault=fault):
                memory = Memory()
                manager, nodes = memory.player(0x200000, 2)
                if fault == "count":
                    memory.put(manager + 0x20, struct.pack("<I", 25))
                elif fault == "tail":
                    memory.put(manager + 0x10, struct.pack("<Q", nodes[0]))
                elif fault == "cycle":
                    memory.put(nodes[0] + 8, struct.pack("<Q", nodes[0]))
                elif fault == "duplicate":
                    memory.put(nodes[1] + 0x10, struct.pack("<Q", 0x800000))
                else:
                    original = memory.read
                    memory.read = lambda a, n: original(a, n)[:-1]
                with self.assertRaises(SelectionReadError):
                    read_player_selection(memory, 0x200000)

    def test_same_count_mutation_is_detected(self):
        memory = Memory()
        _, nodes = memory.player(0x200000, 2)
        original = memory.read
        reads = 0
        def changing_read(address, size):
            nonlocal reads
            result = original(address, size)
            if address == nodes[1] + 8:
                reads += 1
                if reads == 1:
                    memory.put(nodes[1] + 0x10, struct.pack("<Q", 0x900000))
            return result
        memory.read = changing_read
        with self.assertRaisesRegex(SelectionReadError, "changed"):
            read_player_selection(memory, 0x200000)

    def test_empty_tail_is_untagged_as_observed_in_live_game(self):
        memory = Memory()
        manager, _ = memory.player(0x200000, 0)
        memory.put(manager + 0x10, struct.pack("<Q", (manager + 0x10) | 1))
        with self.assertRaisesRegex(SelectionReadError, "sentinel"):
            read_player_selection(memory, 0x200000)

    def trainer(self, players):
        trainer = object.__new__(War3Trainer)
        trainer._classic_selection_layout = None
        trainer._classic_selection_cache = ()
        trainer._classic_object_registry = Mock()
        trainer._classic_object_registry.players.return_value = players
        trainer._selection_player_pointer_candidates = Mock(return_value=players)
        trainer._build_unit_object_index = Mock(side_effect=AssertionError("Unexpected index scan"))
        return trainer

    def test_empty_cached_player_does_not_select_neighbors_or_scan(self):
        memory = Memory()
        manager, _ = memory.player(0x200000, 0)
        memory.player(0x200E10, 14)
        trainer = self.trainer([0x200000, 0x200E10])
        trainer._classic_selection_layout = (0x200000, manager, 0)
        self.assertEqual(trainer._classic_selection_candidates(memory), [])
        trainer._build_unit_object_index.assert_not_called()
        trainer._selection_player_pointer_candidates.assert_not_called()

    def test_adjacent_player_owns_the_list_not_the_first_player(self):
        memory = Memory()
        memory.player(0x200000, 0)
        manager, _ = memory.player(0x200E10, 1)
        trainer = self.trainer([0x200000, 0x200E10])
        trainer._classic_object_registry.resolve_unit.return_value = (123, 0x900000)
        candidate = object()
        trainer._candidate_from_identity = Mock(return_value=candidate)
        self.assertEqual(trainer._classic_selection_candidates(memory), [(candidate, 123)])
        self.assertEqual(trainer._classic_selection_layout, (0x200E10, manager, 0))
        trainer._build_unit_object_index.assert_not_called()

    def test_multiple_player_lists_are_not_ranked_by_size(self):
        memory = Memory()
        memory.player(0x200000, 1)
        memory.player(0x200E10, 24, first_unit=0xA00000)
        trainer = self.trainer([0x200000, 0x200E10])
        with self.assertRaisesRegex(RuntimeError, "多个玩家"):
            trainer._classic_selection_candidates(memory)
        trainer._build_unit_object_index.assert_not_called()

    def test_replaced_manager_is_followed_through_player_field(self):
        memory = Memory()
        manager, _ = memory.player(0x200000, 0)
        trainer = self.trainer([0x200000])
        trainer._classic_selection_layout = (0x200000, 0xDEADBEEF, 0x388)
        self.assertEqual(trainer._classic_selection_candidates(memory), [])
        self.assertEqual(trainer._classic_selection_layout, (0x200000, manager, 0))

    def test_identity_read_selection_change_discards_cached_results(self):
        memory = Memory()
        memory.player(0x200000, 1)
        trainer = self.trainer([0x200000])
        trainer._classic_selection_cache = ((object(), 777),)
        trainer._classic_object_registry.resolve_unit.return_value = (123, 0x900000)
        def changed_identity(*args):
            memory.player(0x200000, 0)
            return object()
        trainer._candidate_from_identity = changed_identity
        with self.assertRaisesRegex(SelectionReadError, "changed"):
            trainer._classic_selection_candidates(memory)
        self.assertEqual(trainer._classic_selection_cache, ())


if __name__ == "__main__":
    unittest.main()
