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


@pytest.mark.parametrize("action", [ACTION_TARGET, ACTION_IMMEDIATE, ACTION_POINT])
def test_world_effect_protocol_accepts_all_current_callback_modes(action):
    payload = build_work(entries(), 0x10000000, 0x41457362, action, resolver=0x700000)
    validate_work(payload)
    assert struct.unpack_from("<I", payload, 628)[0] == action


@pytest.mark.parametrize(
    "method,expected",
    [
        ("cast_fullscreen_clap", [("AHtc", "immediate"), ("AOws", "immediate")]),
        ("cast_fullscreen_starfall", [("AEsb", "immediate")]),
        ("cast_fullscreen_auto_effect", [("AEfk", "immediate")]),
    ],
)
def test_current_fullscreen_immediate_features_use_world_enumeration(method, expected):
    trainer = object.__new__(product.War3Trainer)
    trainer._native_selection_unavailable = True
    trainer._run_selected_ability_effect = Mock(side_effect=AssertionError("selected-only effect"))
    trainer._run_direct_ability_over_enemy_units = Mock(return_value=(4, 3))

    result = getattr(trainer, method)(success_limit=9)

    assert result == ((8, 6) if len(expected) == 2 else (4, 3))
    assert [call.args[:2] for call in trainer._run_direct_ability_over_enemy_units.call_args_list] == expected
    assert all(call.kwargs["success_limit"] == 9 for call in trainer._run_direct_ability_over_enemy_units.call_args_list)
