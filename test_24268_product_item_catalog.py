import ctypes as c
from pathlib import Path

import pytest

from war3_item_catalog_protocol import (
    ACTION_CREATE,
    ACTION_REMOVE,
    SIGNATURES,
    build_work,
    decode_work,
)
from war3_native_table import LiveNativeEntry


def entries():
    return {
        name: LiveNativeEntry(name, signature, 0x300000 + index * 0x80, 0x500000 + index * 0x100)
        for index, (name, signature) in enumerate(SIGNATURES)
    }


@pytest.fixture(scope="module")
def fixture():
    dll = c.WinDLL(str(Path(__file__).parent / "analysis/bridge-build-item-catalog-r5e/engine-hero-fixture.dll"))
    dll.BridgeItemCatalogTestRun.argtypes = [c.c_void_p, c.c_int, c.c_int]
    dll.BridgeItemCatalogTestRun.restype = c.c_uint64
    dll.BridgeItemCatalogTestStat.argtypes = [c.c_int]
    dll.BridgeItemCatalogTestStat.restype = c.c_int
    return dll


def run(dll, action=ACTION_CREATE, scenario=4, limit=0, dry_run=False, handles=(), rawcodes=()):
    payload = build_work(
        entries(),
        0x10000000,
        action=action,
        limit=limit,
        handles=handles,
        rawcodes=rawcodes,
        dry_run=dry_run,
    )
    buffer = c.create_string_buffer(payload)
    returned = dll.BridgeItemCatalogTestRun(buffer, action, scenario)
    return buffer.raw[: len(payload)], returned, (
        dll.BridgeItemCatalogTestStat(0),
        dll.BridgeItemCatalogTestStat(1),
    )


def test_current_engine_catalog_creates_every_loaded_item(fixture):
    data, returned, stats = run(fixture)
    result = decode_work(data)
    assert returned == 4
    assert result["total"] == 4
    assert result["created"] == 4
    assert len(result["handles"]) == 4
    assert stats == (4, 0)


def test_current_engine_catalog_dry_run_does_not_create_items(fixture):
    data, returned, stats = run(fixture, dry_run=True)
    result = decode_work(data)
    assert returned == 4
    assert result == {"total": 4, "created": 0, "handles": (), "dry_run": True}
    assert stats == (0, 0)


def test_current_engine_catalog_removes_returned_handles(fixture):
    handles = (0xA00001, 0xA00002, 0xA00003)
    data, returned, stats = run(fixture, action=ACTION_REMOVE, handles=handles)
    result = decode_work(data)
    assert returned == 3
    assert result == {"removed": 3, "count": 3}
    assert stats == (0, 3)


def test_current_engine_catalog_creates_decoded_resource_rawcodes(fixture):
    rawcodes = tuple(int.from_bytes(value.encode("ascii"), "big") for value in ("ckng", "ratf", "ofro"))
    data, returned, stats = run(fixture, action=3, rawcodes=rawcodes)
    result = decode_work(data)
    assert returned == 3
    assert result["total"] == 3
    assert result["created"] == 3
    assert len(result["handles"]) == 3
    assert stats == (3, 0)
