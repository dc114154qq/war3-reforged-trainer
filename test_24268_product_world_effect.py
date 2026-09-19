import struct
from unittest.mock import Mock

import pytest

from war3_native_table import LiveNativeEntry
from war3_selection_protocol import SIGNATURES as SELECTION_SIGNATURES
from war3_world_effect_protocol import (
    ACTION_IMMEDIATE,
    ACTION_POINT,
    ACTION_TARGET,
    SIGNATURES,
    build_work,
    validate_work,
)
import war3_reforged_trainer as product


def entries():
    return {
        name: LiveNativeEntry(name, signature, 0x300000 + i * 80, 0x500000 + i * 256)
        for i, (name, signature) in enumerate(SELECTION_SIGNATURES + SIGNATURES)
    }


def test_world_effect_does_not_require_selected_group_native():
    payload_entries = {
        name: LiveNativeEntry(name, signature, 0x300000 + i * 80, 0x500000 + i * 256)
        for i, (name, signature) in enumerate(SIGNATURES)
    }
    payload = build_work(payload_entries, 0x10000000, 0x41457362, ACTION_IMMEDIATE, resolver=0x700000)
    validate_work(payload)


@pytest.mark.parametrize("action", [ACTION_TARGET, ACTION_IMMEDIATE, ACTION_POINT])
def test_world_effect_protocol_accepts_all_current_callback_modes(action):
    payload = build_work(entries(), 0x10000000, 0x41457362, action, resolver=0x700000)
    validate_work(payload)
    assert struct.unpack_from("<I", payload, 628)[0] == action


@pytest.mark.parametrize(
    "method,expected",
    [
        ("cast_fullscreen_swarm", [("ACca", "point"), ("ACcv", "point"), ("AOsh", "point")]),
        ("cast_fullscreen_monsoon", [("ANmo", "point")]),
        ("cast_fullscreen_forked_lightning", [("ACfl", "target")]),
    ],
)
def test_current_fullscreen_targeted_features_use_world_enumeration(method, expected):
    trainer = object.__new__(product.War3Trainer)
    trainer._native_selection_unavailable = True
    trainer._run_selected_ability_effect = Mock(side_effect=AssertionError("selected-only effect"))
    trainer._run_direct_ability_over_enemy_units = Mock(return_value=(4, 3))

    result = getattr(trainer, method)(success_limit=9)

    assert result == (4 * len(expected), 3 * len(expected))
    assert [call.args[:2] for call in trainer._run_direct_ability_over_enemy_units.call_args_list] == expected
    assert all(call.kwargs["success_limit"] == 9 for call in trainer._run_direct_ability_over_enemy_units.call_args_list)


@pytest.mark.parametrize(
    "method,args,expected",
    [
        ("cast_fullscreen_clap", {}, [("AHtc", "noarg"), ("AOws", "noarg")]),
        ("cast_fullscreen_starfall", {}, [("AEsb", "immediate")]),
        ("cast_fullscreen_auto_effect", {"success_limit": 9}, [("AEfk", "noarg")]),
    ],
)
def test_current_fullscreen_area_features_stay_on_local_caster(method, args, expected):
    trainer = object.__new__(product.War3Trainer)
    trainer._native_selection_unavailable = True
    trainer._run_direct_ability_over_enemy_units = Mock(
        side_effect=AssertionError("enemy units must not become the caster")
    )
    trainer._run_selected_ability_effect = Mock(return_value=(1, 1))

    result = getattr(trainer, method)(**args)

    assert result == ((2, 2) if len(expected) == 2 else (1, 1))
    assert [call.args[:2] for call in trainer._run_selected_ability_effect.call_args_list] == expected
    assert all(call.kwargs["area"] == 100000.0 for call in trainer._run_selected_ability_effect.call_args_list)
