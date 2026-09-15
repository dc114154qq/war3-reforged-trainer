import ctypes as c
import struct
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from war3_native_table import LiveNativeEntry
from war3_selection_protocol import SIGNATURES as SELECTION
from war3_unit_action_protocol import (
    ACTION_QUERY_INVULNERABLE,
    ACTION_SET_INVULNERABLE,
    ACTION_SET_PAUSED,
    ACTION_SET_POSITION,
    ACTION_SET_SCALE,
    ACTION_TAKE_CONTROL,
    ACTION_ADD_SKILL_POINTS,
    ACTION_SIGNATURES,
    build_work,
    decode_work,
)
import war3_engine_transport as transport
import war3_reforged_trainer as product


def entries():
    return {
        name: LiveNativeEntry(name, signature, 0x300000 + i * 80, 0x500000 + i * 256)
        for i, (name, signature) in enumerate(SELECTION + ACTION_SIGNATURES)
    }


def work(action, value=0, **kwargs):
    return build_work(entries(), 0x10000000, action, value=value, **kwargs)


@pytest.fixture(scope="module")
def fixture():
    dll = c.WinDLL(str(Path(__file__).parent / "analysis/engine-clone-fixture.dll"))
    dll.BridgeUnitActionTestRun.argtypes = [c.c_void_p, c.c_int, c.c_int]
    dll.BridgeUnitActionTestRun.restype = c.c_uint64
    dll.BridgeUnitActionTestStat.argtypes = [c.c_int]
    dll.BridgeUnitActionTestStat.restype = c.c_int
    return dll


def run(dll, action, count=15, value=0, **kwargs):
    payload = c.create_string_buffer(work(action, value, **kwargs))
    returned = dll.BridgeUnitActionTestRun(payload, count, 0)
    return payload.raw[:1432], returned


@pytest.mark.parametrize("action,value", [
    (ACTION_SET_INVULNERABLE, 1),
    (ACTION_SET_PAUSED, 1),
    (ACTION_TAKE_CONTROL, 0),
])
def test_verified_state_actions_cover_all_selected_units(fixture, action, value):
    data, count = run(fixture, action, value=value)
    result = decode_work(data, count)
    assert result["count"] == 15
    assert result["completed"] == 15
    assert all(row["status"] == 1 for row in result["rows"])
    assert result["changed"] == 15


def test_query_action_returns_state_without_mutation(fixture):
    data, count = run(fixture, ACTION_QUERY_INVULNERABLE)
    result = decode_work(data, count)
    assert result["changed"] == 0
    assert all(row["before"] == row["after"] == 0 for row in result["rows"])


def test_position_action_reads_back_coordinates(fixture):
    x_bits = struct.unpack("<I", struct.pack("<f", 123.5))[0]
    y_bits = struct.unpack("<I", struct.pack("<f", -45.25))[0]
    data, count = run(fixture, ACTION_SET_POSITION, x_bits=x_bits, y_bits=y_bits)
    result = decode_work(data, count)
    assert result["changed"] == 15
    assert all(row["actual_x_bits"] == x_bits and row["actual_y_bits"] == y_bits for row in result["rows"])


def test_scale_action_is_batched(fixture):
    bits = struct.unpack("<I", struct.pack("<f", 2.0))[0]
    data, count = run(fixture, ACTION_SET_SCALE, scale_x_bits=bits, scale_y_bits=bits, scale_z_bits=bits)
    result = decode_work(data, count)
    assert result["changed"] == 15
    assert fixture.BridgeUnitActionTestStat(9) == 15


def test_skill_points_action_changes_heroes_only(fixture):
    data, count = run(fixture, ACTION_ADD_SKILL_POINTS, value=7)
    result = decode_work(data, count)
    assert result["changed"] == 5
    assert [row["status"] for row in result["rows"]].count(1) == 5
    assert [row["status"] for row in result["rows"]].count(2) == 10
    assert fixture.BridgeUnitActionTestStat(15) == 5


@pytest.mark.parametrize("name", [name for name, _ in ACTION_SIGNATURES])
def test_unit_action_requires_exact_signature(name):
    current = entries()
    current[name] = replace(current[name], signature="()V")
    action = ACTION_SET_INVULNERABLE if name in {"SetUnitInvulnerable", "BlzIsUnitInvulnerable"} else ACTION_SET_PAUSED
    with pytest.raises(ValueError):
        build_work(current, 0x10000000, action, value=1)


def test_invalid_unit_action_payload_rejected_before_target_access(monkeypatch):
    monkeypatch.setattr(transport, "window_thread", Mock(side_effect=AssertionError("target accessed")))
    with pytest.raises(ValueError):
        transport.dispatch(1, 2, 3, Path("missing.dll"), 0, bytes(1432), kind="unit_action")


def test_product_unit_actions_do_not_dispatch_legacy_helper():
    trainer = object.__new__(product.War3Trainer)
    trainer._native_selection_unavailable = True
    trainer.unit_action_batch_24268 = Mock(return_value={
        "count": 15,
        "changed": 15,
        "completed": 15,
        "rows": [{"after": 0, "actual_x_bits": 0, "actual_y_bits": 0}] * 15,
    })
    trainer._run_elephant_unit_bool = Mock(side_effect=AssertionError("legacy helper"))
    trainer._run_elephant_unit_void = Mock(side_effect=AssertionError("legacy helper"))
    trainer._run_bound_simple_unit_actions = Mock(side_effect=AssertionError("legacy helper"))
    assert trainer.set_selected_unit_invulnerable(False) == 15
    assert trainer.set_selected_unit_pathing(True) == 15
    assert trainer.set_selected_unit_paused(False) == 15
    assert trainer.reset_selected_unit_cooldown() == 15
    assert trainer.kill_selected_unit() == 15
    assert trainer.remove_selected_unit() == 15
    assert trainer.explode_selected_unit() == 15
    assert trainer.take_selected_unit_control() == 15
    trainer.add_selected_hero_skill_points(7)
    assert trainer.unit_action_batch_24268.call_count == 9


def test_current_engine_group_move_uses_one_position_batch_after_mouse_query():
    trainer = object.__new__(product.War3Trainer)
    trainer._native_selection_unavailable = True
    trainer.query_mouse_world_position = Mock(return_value=(123.5, -45.25))
    trainer.set_selected_group_position = Mock(return_value=15)
    trainer._run_native_helper_ops = Mock(side_effect=AssertionError("legacy group mover"))

    assert trainer.move_selected_group_to_mouse() == (15, 123.5, -45.25)
    trainer.query_mouse_world_position.assert_called_once_with()
    trainer.set_selected_group_position.assert_called_once_with(123.5, -45.25)


def test_current_engine_group_position_uses_verified_native_batch():
    trainer = object.__new__(product.War3Trainer)
    x_bits = struct.unpack("<I", struct.pack("<f", 123.5))[0]
    y_bits = struct.unpack("<I", struct.pack("<f", -45.25))[0]
    trainer.position_batch_24268 = Mock(return_value={
        "completed": 15,
        "changed": 15,
        "rows": [
            {"actual_x_bits": x_bits, "actual_y_bits": y_bits}
        ] * 15,
    })
    assert trainer.set_selected_group_position(123.5, -45.25) == 15
    trainer.position_batch_24268.assert_called_once()
