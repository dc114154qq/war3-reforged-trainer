import unittest
from unittest.mock import Mock

from war3_reforged_trainer import ResourceCache, War3Trainer


class ResourceAdditionTests(unittest.TestCase):
    def setUp(self):
        self.trainer = object.__new__(War3Trainer)
        self.cache = ResourceCache(
            gold_address=0x1000,
            lumber_address=0x2000,
            gold=0,
            lumber=0,
            block_start_kind=1,
            owner_key=0x3000,
        )
        self.trainer.locate_local_player_resource_cache = Mock(return_value=self.cache)
        self.trainer.validate_local_player_resource_cache = Mock(return_value=self.cache)
        self.trainer.write_resource_cache = Mock(return_value=self.cache)
        self.trainer.read_resource_cache = Mock(
            side_effect=AssertionError("generic resource scoring must not be used")
        )

    def test_add_both_targets_validated_local_player_when_resources_are_zero(self):
        self.trainer.add_gold_and_lumber(100000)

        self.trainer.locate_local_player_resource_cache.assert_called_once_with()
        self.trainer.validate_local_player_resource_cache.assert_called_once_with(
            self.cache
        )
        self.trainer.write_resource_cache.assert_called_once_with(
            self.cache,
            target_gold=100000,
            target_lumber=100000,
        )
        self.trainer.read_resource_cache.assert_not_called()

    def test_single_resource_additions_use_the_same_local_player_path(self):
        self.trainer.add_gold(25)
        self.trainer.write_resource_cache.assert_called_with(
            self.cache,
            target_gold=25,
        )

        self.trainer.write_resource_cache.reset_mock()
        self.trainer.add_lumber(40)
        self.trainer.write_resource_cache.assert_called_once_with(
            self.cache,
            target_lumber=40,
        )


if __name__ == "__main__":
    unittest.main()
