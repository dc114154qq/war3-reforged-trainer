import struct
import ctypes as c
from pathlib import Path
import pytest

from war3_native_table import LiveNativeEntry
from war3_position_protocol import SIGNATURES, WORK_SIZE, build_work, decode_work
from war3_selection_protocol import SIGNATURES as SELECTION_SIGNATURES


def entries():
    return {
        name: LiveNativeEntry(name, signature, 0x300000 + index * 80, 0x500000 + index * 256)
        for index, (name, signature) in enumerate(SELECTION_SIGNATURES + SIGNATURES)
    }


def test_position_work_decodes_all_selected_units_with_float_readback():
    x_bits = struct.unpack("<I", struct.pack("<f", 123.5))[0]
    y_bits = struct.unpack("<I", struct.pack("<f", -45.25))[0]
    payload = bytearray(build_work(entries(), 0x10000000, x_bits, y_bits))
    struct.pack_into("<2Q4I", payload, 64, 0x10, 0x20, 15, 0, 1, 0)
    for index in range(15):
        before_x = struct.unpack("<I", struct.pack("<f", 10.0 + index))[0]
        before_y = struct.unpack("<I", struct.pack("<f", 20.0 + index))[0]
        actual_x = struct.unpack("<I", struct.pack("<f", 123.5 + index))[0]
        actual_y = struct.unpack("<I", struct.pack("<f", -45.25 + index))[0]
        struct.pack_into("<Q6I", payload, 544 + index * 32, 0x1000 + index,
                         before_x, before_y, 1, 0, actual_x, actual_y)
        struct.pack_into("<QIi", payload, 96 + index * 16, 0x1000 + index, 0x41303030 + index, 0)
    struct.pack_into("<3I", payload, 528, 15, 0, 15)
    result = decode_work(bytes(payload), 15)
    assert len(result["rows"]) == 15
    assert result["changed"] == result["completed"] == 15


def test_position_work_has_stable_size():
    assert WORK_SIZE == 1312


@pytest.fixture(scope="module")
def fixture():
    dll = c.WinDLL(str(Path(__file__).parent / "analysis/bridge-build-check-r32/engine-hero-fixture.dll"))
    dll.BridgePositionTestRun.argtypes = [c.c_void_p, c.c_int]
    dll.BridgePositionTestRun.restype = c.c_uint64
    dll.BridgePositionTestStat.argtypes = [c.c_int]
    dll.BridgePositionTestStat.restype = c.c_int
    return dll


def test_position_fixture_preserves_offsets_and_reads_before_and_after(fixture):
    x_bits = struct.unpack("<I", struct.pack("<f", 123.5))[0]
    y_bits = struct.unpack("<I", struct.pack("<f", -45.25))[0]
    payload = c.create_string_buffer(build_work(entries(), 0x10000000, x_bits, y_bits))
    count = fixture.BridgePositionTestRun(payload, 15)
    result = decode_work(payload.raw[:WORK_SIZE], count)
    assert result["count"] == result["changed"] == result["completed"] == 15
    assert [fixture.BridgePositionTestStat(i) for i in range(4)] == [15, 15, 30, 30]
