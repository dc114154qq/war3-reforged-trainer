import ctypes as c
import struct
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from war3_native_table import LiveNativeEntry
from war3_spawn_protocol import SIGNATURES, build_work, decode_work
import war3_engine_transport as transport
import war3_reforged_trainer as product


def entries():
    return {
        name: LiveNativeEntry(name, signature, 0x300000 + i * 80, 0x500000 + i * 256)
        for i, (name, signature) in enumerate(SIGNATURES)
    }


def work(rawcode=0x68666F6F):
    return build_work(
        entries(),
        0x10000000,
        rawcode,
        struct.unpack("<I", struct.pack("<f", 12.5))[0],
        struct.unpack("<I", struct.pack("<f", -8.0))[0],
        struct.unpack("<I", struct.pack("<f", 90.0))[0],
    )


@pytest.fixture(scope="module")
def fixture():
    dll = c.WinDLL(str(Path(__file__).parent / "analysis" / "engine-hero-fixture.dll"))
    dll.BridgeSpawnTestRun.argtypes = [c.c_void_p, c.c_uint32, c.c_int]
    dll.BridgeSpawnTestRun.restype = c.c_uint64
    dll.BridgeSpawnTestStat.argtypes = [c.c_int]
    dll.BridgeSpawnTestStat.restype = c.c_int
    return dll


def run(dll, scenario=0):
    payload = c.create_string_buffer(work())
    returned = dll.BridgeSpawnTestRun(payload, 0x68666F6F, scenario)
    return payload.raw[:128], returned


def test_spawn_creates_requested_unit_and_preserves_coordinates(fixture):
    data, returned = run(fixture)
    result = decode_work(data)
    assert returned == result["created"] == 0x900000
    assert result["actual_rawcode"] == 0x68666F6F
    assert fixture.BridgeSpawnTestStat(0) == 1
    assert fixture.BridgeSpawnTestStat(1) == 0
    assert fixture.BridgeSpawnTestStat(4) == struct.unpack("<I", struct.pack("<f", 12.5))[0]
    assert fixture.BridgeSpawnTestStat(5) & 0xFFFFFFFF == struct.unpack("<I", struct.pack("<f", -8.0))[0]


@pytest.mark.parametrize("scenario,removed", [(1, 0), (2, 1)])
def test_spawn_failure_is_not_reported_success_and_wrong_type_is_removed(fixture, scenario, removed):
    data, returned = run(fixture, scenario)
    assert returned == 0
    with pytest.raises(ValueError):
        decode_work(data)
    assert fixture.BridgeSpawnTestStat(1) == removed


@pytest.mark.parametrize("name", [name for name, _ in SIGNATURES])
def test_spawn_requires_exact_signature(name):
    current = entries()
    current[name] = replace(current[name], signature="()V")
    with pytest.raises(ValueError):
        build_work(current, 0x10000000, 0x68666F6F)


def test_spawn_transport_rejects_wrong_payload_before_target_access(monkeypatch):
    monkeypatch.setattr(transport, "window_thread", Mock(side_effect=AssertionError("opened")))
    with pytest.raises(ValueError):
        transport.dispatch(1, 2, 3, Path("missing.dll"), 0, bytes(127), kind="spawn")


def test_current_create_local_unit_uses_spawn_batch_for_explicit_rawcode():
    trainer = object.__new__(product.War3Trainer)
    trainer._native_selection_unavailable = True
    trainer._coerce_memory_value = Mock(return_value=0x68666F6F)
    trainer.spawn_unit_24268 = Mock(return_value={"created": 0x900000})
    trainer._query_native_table_handlers = Mock(side_effect=AssertionError("legacy helper"))
    trainer._run_native_helper_ops = Mock(side_effect=AssertionError("legacy helper"))

    assert trainer.create_local_unit("hfoo", (12.5, -8.0)) == (0x68666F6F, 0x900000)
    trainer.spawn_unit_24268.assert_called_once_with(0x68666F6F, 12.5, -8.0)
