import ast
import ctypes as c
import struct
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from war3_native_table import LiveNativeEntry
from war3_selection_protocol import SIGNATURES as SELECTION
from war3_clone_protocol import (
    CLONE_COPY_ABILITIES,
    CLONE_COPY_ITEMS,
    CLONE_KEEP,
    SIGNATURES,
    build_work,
    decode_work,
)
import war3_engine_transport as transport


def entries():
    return {
        name: LiveNativeEntry(name, signature, 0x300000 + i * 80, 0x500000 + i * 256)
        for i, (name, signature) in enumerate(SELECTION + SIGNATURES)
    }


def work(flags=CLONE_COPY_ABILITIES | CLONE_COPY_ITEMS):
    return build_work(entries(), 0x10000000, flags=flags)


@pytest.fixture(scope="module")
def fixture():
    dll = c.WinDLL(str(Path(__file__).parent / "analysis/engine-clone-fixture.dll"))
    dll.BridgeCloneTestRun.argtypes = [c.c_void_p, c.c_int, c.c_int]
    dll.BridgeCloneTestRun.restype = c.c_uint64
    dll.BridgeCloneTestStat.argtypes = [c.c_int]
    dll.BridgeCloneTestStat.restype = c.c_int
    return dll


def run(dll, count=15, scenario=0, flags=CLONE_COPY_ABILITIES | CLONE_COPY_ITEMS):
    payload = c.create_string_buffer(work(flags))
    returned = dll.BridgeCloneTestRun(payload, count, scenario)
    stats = tuple(dll.BridgeCloneTestStat(i) for i in range(4))
    return payload.raw[:1872], returned, stats


def test_temporary_clone_copies_abilities_and_items_then_cleans_every_clone(fixture):
    data, count, stats = run(fixture)
    result = decode_work(data, count)
    assert result["count"] == 15
    assert result["changed"] == 15
    assert all(row["status"] == 2 for row in result["rows"])
    assert sum(row["ability_count"] for row in result["rows"]) == 5
    assert sum(row["item_count"] for row in result["rows"]) == 5
    assert stats == (15, 15, 5, 5)


def test_keep_clone_retains_rows_and_does_not_run_cleanup(fixture):
    data, count, stats = run(fixture, flags=CLONE_KEEP | CLONE_COPY_ABILITIES | CLONE_COPY_ITEMS)
    result = decode_work(data, count)
    assert result["kept"] and all(row["status"] == 1 for row in result["rows"])
    assert stats == (15, 0, 5, 5)


def test_clone_preserves_hero_skill_points(fixture):
    data, count, _stats = run(
        fixture,
        count=1,
        flags=CLONE_KEEP | CLONE_COPY_ABILITIES,
    )
    result = decode_work(data, count)
    assert result["count"] == 1
    assert result["rows"][0]["level"] == 1
    assert fixture.BridgeCloneTestStat(4) == 0


@pytest.mark.parametrize("scenario", [1, 2, 3])
def test_clone_failure_is_not_reported_success_and_cleans_created_objects(fixture, scenario):
    data, count, stats = run(fixture, scenario=scenario)
    with pytest.raises(ValueError):
        decode_work(data, count)
    assert stats[0] == stats[1]


def test_keep_clone_failure_rolls_back_previously_created_clones(fixture):
    data, count, stats = run(
        fixture,
        scenario=4,
        flags=CLONE_KEEP | CLONE_COPY_ABILITIES | CLONE_COPY_ITEMS,
    )
    with pytest.raises(ValueError):
        decode_work(data, count)
    assert stats[0] == 3
    assert stats[1] == 3


def test_engine_buff_exposed_as_unit_ability_is_skipped(fixture):
    data, count, stats = run(
        fixture,
        count=1,
        scenario=5,
        flags=CLONE_COPY_ABILITIES,
    )
    result = decode_work(data, count)
    assert result["count"] == 1
    assert result["changed"] == 1
    assert result["rows"][0]["status"] == 2
    assert result["rows"][0]["ability_count"] == 0
    assert stats == (1, 1, 0, 0)


@pytest.mark.parametrize("name", [name for name, _ in SIGNATURES])
def test_clone_requires_exact_current_signature(name):
    current = entries()
    current[name] = replace(current[name], signature="()V")
    with pytest.raises(ValueError):
        build_work(current, 0x10000000)


@pytest.mark.parametrize("size", [0, 480, 1855, 1857, 8193])
def test_invalid_clone_work_rejected_before_target_access(monkeypatch, size):
    monkeypatch.setattr(transport, "window_thread", Mock(side_effect=AssertionError("target accessed")))
    with pytest.raises(ValueError):
        transport.dispatch(1, 2, 3, Path("missing.dll"), 0, bytes(size), kind="clone")


def test_gui_clone_path_uses_one_current_engine_batch():
    tree = ast.parse((Path(__file__).parent / "war3_reforged_trainer.py").read_text(encoding="utf8"))
    function = next(node for node in ast.walk(tree)
                    if isinstance(node, ast.FunctionDef) and node.name == "elephant_create_unit")
    trainer = Mock()
    trainer._native_selection_unavailable = True
    trainer.clone_batch_24268.return_value = {
        "count": 15,
        "rows": [{"ability_count": 1, "item_count": 1}] * 15,
    }
    env = {
        "elephant_trainer": lambda: trainer,
        "elephant_batch": Mock(side_effect=AssertionError("per-unit batch")),
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<clone-gui>", "exec"), env)
    assert "15" in env["elephant_create_unit"](True)
    trainer.clone_batch_24268.assert_called_once_with(
        keep=True, preserve_owner=False, copy_abilities=True, copy_items=True
    )


def test_keep_flag_is_part_of_the_wire_request():
    payload = work(CLONE_KEEP | CLONE_COPY_ABILITIES)
    values = struct.unpack_from("<26Q8I", payload, 480)
    assert values[26] & CLONE_KEEP
