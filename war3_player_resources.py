"""Indexed player-state properties for build 24268 (no region scanning)."""
import struct


SOURCE = "3.0 indexed player properties"
PROPERTY_TAG = 0x60666C675E70726F
PLAYER_TAG = 0x2B706C792B61676C
REQUIRED_STATES = (0, 1, 2, 4, 5, 6)


def read_player_properties(memory, registry, player, player_id):
    from war3_game_profile import current_profile
    profile = getattr(registry, "profile", None) or current_profile()
    return profile.adapter.properties.player_properties(
        memory, registry, player, player_id, PROPERTY_TAG, PLAYER_TAG, REQUIRED_STATES,
    )
