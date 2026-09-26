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
    "method,args,expected",
    [
        ("cast_fullscreen_swarm", {}, [("ACca", 852218, 2), ("ACcv", 852218, 2), ("AOsh", 852125, 2)]),
        ("cast_fullscreen_clap", {}, [("AHtc", 852096, 1), ("AOws", 852127, 1)]),
        ("cast_fullscreen_monsoon", {}, [("ANmo", 852591, 2)]),
        ("cast_fullscreen_starfall", {}, [("AEsb", 852183, 1)]),
        ("cast_fullscreen_forked_lightning", {}, [("ACfl", 852587, 3)]),
        ("cast_fullscreen_auto_effect", {"success_limit": 9}, [("AEfk", 852526, 1)]),
    ],
)
def test_current_fullscreen_area_features_stay_on_local_caster(method, args, expected):
    trainer = object.__new__(product.War3Trainer)
    trainer._native_selection_unavailable = True
    trainer._run_direct_ability_over_enemy_units = Mock(
        side_effect=AssertionError("enemy units must not become the caster")
    )
    trainer.cast_native_area_24268 = Mock(return_value={})

    result = getattr(trainer, method)(**args)

    assert result == (len(expected), len(expected))
    assert [(call.args[0], call.args[1], call.kwargs["cast_kind"])
            for call in trainer.cast_native_area_24268.call_args_list] == expected


@pytest.mark.parametrize("method", ["cast_fullscreen_swarm", "cast_fullscreen_monsoon"])
def test_current_fullscreen_point_features_use_native_point_orders(method):
    trainer = object.__new__(product.War3Trainer)
    trainer.cast_native_area_24268 = Mock(return_value={})

    getattr(trainer, method)()

    assert all(call.kwargs["cast_kind"] == 2
               for call in trainer.cast_native_area_24268.call_args_list)


def test_current_point_effect_forwards_area_to_effect_bridge():
    trainer = object.__new__(product.War3Trainer)
    trainer._native_selection_unavailable = True
    trainer.effect_batch_24268 = Mock(return_value={"changed": 1})

    result = trainer._run_selected_ability_effect_locked(
        "ANmo", "point", area=100000.0, point=(0.0, 0.0)
    )

    assert result == (1, 1)
    assert trainer.effect_batch_24268.call_args.kwargs["area"] == 100000.0
