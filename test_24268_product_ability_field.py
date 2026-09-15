import ctypes as c
import struct
from pathlib import Path

import pytest

from war3_ability_field_protocol import (
    SIGNATURES,
    WORK_SIZE,
    build_work,
    decode_work,
    descriptor,
)
from war3_native_table import LiveNativeEntry
from war3_selection_protocol import SIGNATURES as SELECTION


def entries():
    return {
        name: LiveNativeEntry(name, signature, 0x300000 + index * 80, 0x500000 + index * 256)
        for index, (name, signature) in enumerate(SELECTION + SIGNATURES)
    }


def make_work(action=0, fields=None, target_unit=0):
    fields = fields or (descriptor(0x61626364, "integer", "field"),)
    return build_work(entries(), 0x10000000, 0x41487664, 3, action, fields, target_unit)


@pytest.fixture(scope="module")
def fixture():
    path = Path(__file__).parent / "analysis" / "bridge-build-check-ability-field" / "engine-hero-fixture.dll"
    dll = c.WinDLL(str(path))
    dll.BridgeAbilityFieldTestRun.argtypes = [c.c_void_p, c.c_int, c.c_int]
    dll.BridgeAbilityFieldTestRun.restype = c.c_uint64
    dll.BridgeAbilityFieldTestStat.argtypes = [c.c_int]
    dll.BridgeAbilityFieldTestStat.restype = c.c_int
    return dll


def run(dll, count, action=0, fields=None, scenario=0, target_unit=0):
    payload = c.create_string_buffer(make_work(action, fields, target_unit))
    returned = dll.BridgeAbilityFieldTestRun(payload, count, scenario)
    return payload.raw[:WORK_SIZE], int(returned), dll.BridgeAbilityFieldTestStat(1)


def test_read_roundtrip_supports_24_units_and_mixed_field_kinds(fixture):
    fields = (
        descriptor(0x61626364, "boolean", "field"),
        descriptor(0x65666768, "integer", "level"),
        descriptor(0x696A6B6C, "real", "level"),
    )
    data, count, gets = run(fixture, 24, fields=fields)
    result = decode_work(data, count)
    assert result["count"] == 24
    assert all(row["status"] == 1 for row in result["rows"])
    assert all(field["before"] == field["after"] for row in result["rows"] for field in row["values"])
    assert gets >= 24 * len(fields)


def test_write_roundtrip_is_batched_and_readback_verified(fixture):
    fields = (
        descriptor(0x61626364, "boolean", "field", 1),
        descriptor(0x65666768, "integer", "level", 0x12345678),
        descriptor(0x696A6B6C, "real", "level", struct.unpack("<I", struct.pack("<f", 7.5))[0]),
    )
    data, count, _ = run(fixture, 15, 1, fields=fields)
    result = decode_work(data, count)
    assert result["changed"] == 15 * len(fields)
    assert all(row["status"] == 1 for row in result["rows"])


def test_targeted_write_skips_other_selected_units(fixture):
    target = 0x100005
    data, count, _ = run(
        fixture,
        15,
        1,
        fields=(descriptor(0x61626364, "integer", "field", 99),),
        target_unit=target,
    )
    result = decode_work(data, count)
    assert [row["status"] for row in result["rows"]].count(1) == 1
    assert [row["status"] for row in result["rows"]].count(3) == 14


def test_read_allows_units_without_requested_ability(fixture):
    data, count, _ = run(fixture, 15, fields=(descriptor(0x61626364, "integer", "field"),), scenario=3)
    result = decode_work(data, count)
    assert result["rows"][2]["status"] == 2
    assert sum(row["status"] == 1 for row in result["rows"]) == 14


@pytest.mark.parametrize("scenario", [1, 2, 3])
def test_write_failure_never_decodes_as_success(fixture, scenario):
    data, count, _ = run(
        fixture,
        15,
        1,
        fields=(descriptor(0x61626364, "integer", "field", 99),),
        scenario=scenario,
    )
    with pytest.raises(ValueError):
        decode_work(data, count)


def test_payload_size_is_stable():
    assert len(make_work()) == WORK_SIZE == 7688
