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

    def test_native_food_updates_use_the_helper_route(self):
        native_cache = ResourceCache(
            gold_address=0,
            lumber_address=0,
            gold=10,
            lumber=20,
            food_used=3,
            food_cap=10,
            source="persistent native player state",
        )
        self.trainer.read_resource_cache = Mock(return_value=native_cache)
        self.trainer.write_resource_cache = Mock(return_value=native_cache)

        result = self.trainer.set_food(target_used=7, target_cap=18)

        self.assertIs(result, native_cache)
        self.trainer.write_resource_cache.assert_called_once_with(
            native_cache,
            target_food_used=7,
            target_food_cap=18,
        )


if __name__ == "__main__":
    unittest.main()
