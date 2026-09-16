import ctypes as c
from pathlib import Path

import pytest

from war3_map_flags_protocol import (
    ACTION_QUERY,
    ACTION_SET,
    SIGNATURES,
    build_work,
    decode_work,
)
from war3_native_table import LiveNativeEntry


def entries():
    return {
        name: LiveNativeEntry(name, signature, 0x300000 + i * 80, 0x500000 + i * 256)
        for i, (name, signature) in enumerate(SIGNATURES)
    }


@pytest.fixture(scope="module")
def fixture():
    dll = c.WinDLL(str(Path(__file__).parent / "analysis" / "engine-hero-fixture.dll"))
    dll.BridgeMapFlagsTestRun.argtypes = [c.c_void_p, c.c_int, c.c_int]
    dll.BridgeMapFlagsTestRun.restype = c.c_uint64
    return dll


def test_map_flags_protocol_and_fixture_round_trip(fixture):
    query = c.create_string_buffer(build_work(entries(), 0x10000000, ACTION_QUERY, 0))
    assert fixture.BridgeMapFlagsTestRun(query, ACTION_QUERY, 0) == 0x100000001
    result = decode_work(query.raw[:128])
    assert (result["after0"], result["after1"], result["changed"]) == (1, 1, 0)

    reveal = c.create_string_buffer(build_work(entries(), 0x10000000, ACTION_SET, 1))
    assert fixture.BridgeMapFlagsTestRun(reveal, ACTION_SET, 1) == 0
    result = decode_work(reveal.raw[:128])
    assert (result["after0"], result["after1"], result["changed"]) == (0, 0, 1)
