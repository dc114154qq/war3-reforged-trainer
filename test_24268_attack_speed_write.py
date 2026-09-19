import ctypes as c
from dataclasses import replace
from pathlib import Path
import struct
from unittest.mock import Mock

import pytest

from war3_attack_speed_protocol import SIGNATURES, build_work, decode_work
from war3_spawn_protocol import (
    SIGNATURES as SPAWN_SIGNATURES,
    build_work as build_spawn_work,
    decode_work as decode_spawn_work,
)
from war3_native_table import LiveNativeEntry
from war3_selection_protocol import SIGNATURES as SELECTION_SIGNATURES
from war3_reforged_trainer import UnitCandidate, War3Trainer


def entries():
    return {
        name: LiveNativeEntry(name, signature, 0x300000 + index * 80, 0x500000 + index * 256)
        for index, (name, signature) in enumerate(SELECTION_SIGNATURES + SIGNATURES)
    }


def work(target_aps=0.0):
    return build_work(
        entries(), 0x10000000, 0x200000, 0x300000,
        0x97550000002F, 0x68666F6F, 0x7FF600000000, target_aps,
    )


@pytest.fixture(scope="module")
def fixture_dll():
    path = Path(__file__).parent / "analysis/bridge-build-attack-speed-20260919/engine-hero-fixture.dll"
    assert path.is_file()
    dll = c.WinDLL(str(path))
    dll.BridgeAttackSpeedTestRun.argtypes = [c.c_void_p]
    dll.BridgeAttackSpeedTestRun.restype = c.c_uint64
    dll.BridgeAttackSpeedTestBase.restype = c.c_uint32
    dll.BridgeSpawnTestRun.argtypes = [c.c_void_p, c.c_uint32, c.c_int]
    dll.BridgeSpawnTestRun.restype = c.c_uint64
    dll.BridgeSpawnTestStat.argtypes = [c.c_int]
    dll.BridgeSpawnTestStat.restype = c.c_int
    return dll


def run(dll, target_aps=0.0):
    buffer = c.create_string_buffer(work(target_aps))
    returned = dll.BridgeAttackSpeedTestRun(buffer)
    return decode_work(buffer.raw[:640], returned)


def test_exact_engine_query_reports_true_attack_speed(fixture_dll):
    result = run(fixture_dll)
    assert result["speed_factor"] == pytest.approx(1.5)
    assert result["base_cooldown"] == pytest.approx(2.2)
    assert result["effective_interval"] == pytest.approx(2.2 / 1.5)
    assert result["true_aps"] == pytest.approx(1.5 / 2.2)
    assert result["changed"] == 0


def test_true_attack_speed_write_is_reduced_to_native_base_cooldown(fixture_dll):
    result = run(fixture_dll, 1.25)
    assert result["after_true_aps"] == pytest.approx(1.25)
    assert result["after_base_cooldown"] == pytest.approx(1.5 / 1.25)
    base = struct.unpack("<f", struct.pack("<I", fixture_dll.BridgeAttackSpeedTestBase()))[0]
    assert base == pytest.approx(1.2)


def test_ctrl_k_spawn_uses_pointer_real_arguments(fixture_dll):
    spawn_entries = {
        name: LiveNativeEntry(name, signature, 0x600000 + index * 80, 0x700000 + index * 256)
        for index, (name, signature) in enumerate(SPAWN_SIGNATURES)
    }
    x_bits = struct.unpack("<I", struct.pack("<f", -123.5))[0]
    y_bits = struct.unpack("<I", struct.pack("<f", 456.25))[0]
    facing_bits = struct.unpack("<I", struct.pack("<f", 90.0))[0]
    payload = c.create_string_buffer(build_spawn_work(
        spawn_entries, 0x10000000, 0x68637468, x_bits, y_bits, facing_bits,
    ))
    returned = fixture_dll.BridgeSpawnTestRun(payload, 0x68637468, 0)
    result = decode_spawn_work(payload.raw[:128], returned)
    assert result["created"] == 0x900000
    assert fixture_dll.BridgeSpawnTestStat(4) & 0xFFFFFFFF == x_bits
    assert fixture_dll.BridgeSpawnTestStat(5) & 0xFFFFFFFF == y_bits
    assert fixture_dll.BridgeSpawnTestStat(6) & 0xFFFFFFFF == facing_bits


def test_expected_speed_keeps_session_high_watermark_by_unit_type():
    trainer = object.__new__(War3Trainer)
    trainer._expected_attack_speed_by_type = {}
    import threading
    trainer._expected_attack_speed_lock = threading.RLock()
    assert trainer._observe_expected_attack_speed(0x486D6B67, 0, 0.7) == pytest.approx(0.7)
    assert trainer._observe_expected_attack_speed(0x486D6B67, 0, 0.6) == pytest.approx(0.7)
    assert trainer._observe_expected_attack_speed(0x486D6B67, 0, 0.8) == pytest.approx(0.8)
    assert trainer._observe_expected_attack_speed(0x486D6B67, 1, 0.5) == pytest.approx(0.5)


def test_product_true_speed_write_uses_exact_engine_transaction():
    trainer = object.__new__(War3Trainer)
    candidate = UnitCandidate(
        base=1, score=1, hp_current_address=1, hp_max_address=2,
        mp_current_address=3, mp_max_address=4, note="test",
        owner_address=0x500000, handle=0x97550000972F,
        unit_address=0x200000, unit_type_id=0x486D6B67,
    )
    field = Mock(key="attack1_true_speed", address=0x300228)
    trainer._selected_components = Mock(return_value={"attack": (0x400000, 0x300000)})
    trainer.attack_speed_24268 = Mock(return_value={
        "true_aps": 0.7, "after_true_aps": 0.8,
        "base_cooldown": 2.0, "after_base_cooldown": 1.75,
    })
    from war3_reforged_trainer import UnitMemoryField
    field = UnitMemoryField(
        key="attack1_true_speed", label="真正的攻速", value_type="f32",
        value=0.7, address=0x300228, category="攻击", native_write=True,
    )
    written = trainer._write_true_attack_speed_field(Mock(), candidate, field, "0.8")
    assert written.value == pytest.approx(0.8)
    trainer.attack_speed_24268.assert_called_once_with(candidate, 0x300000, 0.8, 0)
