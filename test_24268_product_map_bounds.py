import struct

import pytest

from war3_map_bounds_protocol import SIGNATURES, WORK_SIZE, build_work, decode_work
from war3_native_table import LiveNativeEntry


def entries():
    return {
        name: LiveNativeEntry(name, signature, 0x300000 + index * 80, 0x500000 + index * 256)
        for index, (name, signature) in enumerate(SIGNATURES)
    }


def test_map_bounds_work_decodes_finite_ordered_rect():
    payload = bytearray(build_work(entries(), 0x10000000))
    values = [
        struct.unpack("<I", struct.pack("<f", value))[0]
        for value in (-8192.0, 8192.0, -4096.0, 4096.0)
    ]
    struct.pack_into("<4I4I", payload, 48, *values, 1, 0, 1, 0)
    result = decode_work(bytes(payload))
    assert result["min_x"] == pytest.approx(-8192.0)
    assert result["max_y"] == pytest.approx(4096.0)


def test_map_bounds_work_has_stable_size():
    assert WORK_SIZE == 128
