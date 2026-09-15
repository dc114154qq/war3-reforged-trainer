import ctypes as c
import struct
from pathlib import Path
from unittest.mock import Mock

import pytest

from war3_native_table import LiveNativeEntry
from war3_mouse_protocol import SIGNATURES, build_work, decode_work
import war3_engine_transport as transport
import war3_reforged_trainer as product


def work():
    entries = {
        name: LiveNativeEntry(name, signature, 0x300000 + i * 80, 0x500000 + i * 256)
        for i, (name, signature) in enumerate(SIGNATURES)
    }
    return build_work(entries, 0x10000000)


@pytest.fixture(scope="module")
def fixture():
    dll = c.WinDLL(str(Path(__file__).parent / "analysis" / "engine-hero-fixture.dll"))
    dll.BridgeMouseTestRun.argtypes = [c.c_void_p, c.c_uint32, c.c_uint32, c.c_int]
    dll.BridgeMouseTestRun.restype = c.c_uint64
    return dll


def run(dll, error=0):
    x_bits = struct.unpack("<I", struct.pack("<f", 123.5))[0]
    y_bits = struct.unpack("<I", struct.pack("<f", -45.25))[0]
    payload = c.create_string_buffer(work())
    returned = dll.BridgeMouseTestRun(payload, x_bits, y_bits, error)
    return payload.raw[:128], returned, x_bits, y_bits


def test_current_mouse_query_decodes_world_coordinates(fixture):
    data, returned, x_bits, y_bits = run(fixture)
    result = decode_work(data)
    assert returned == x_bits | (y_bits << 32)
    assert result["x"] == pytest.approx(123.5)
    assert result["y"] == pytest.approx(-45.25)


def test_current_mouse_query_propagates_world_point_failure(fixture):
    data, returned, _x_bits, _y_bits = run(fixture, error=1460)
    assert returned == 0
    with pytest.raises(ValueError, match="error=1460"):
        decode_work(data)


def test_mouse_transport_rejects_wrong_payload_before_target_access(monkeypatch):
    monkeypatch.setattr(transport, "window_thread", Mock(side_effect=AssertionError("opened")))
    with pytest.raises(ValueError):
        transport.dispatch(1, 2, 3, Path("missing.dll"), 0, bytes(127), kind="mouse")


def test_3_0_mouse_route_does_not_call_retired_helper():
    trainer = object.__new__(product.War3Trainer)
    trainer._native_selection_unavailable = True
    trainer.camera_snapshot_24268 = Mock(return_value={
        "target": (100.0, 200.0, 50.0),
        "eye": (100.0, 0.0, 250.0),
        "fields": (0.0, 5000.0, 5.3, 1.2217304764, 0.0, 1.5707963268, 0.0, 0.0),
        "screen": (32767, 32767),
    })
    trainer._client_size_24268 = Mock(return_value=(1706, 960))
    trainer._screen_scale_24268 = Mock(return_value=1.0)
    trainer._run_native_helper_ops = Mock(side_effect=AssertionError("retired helper"))
    assert trainer.query_mouse_world_position() == pytest.approx((100.0, 200.0), abs=0.1)
    trainer.camera_snapshot_24268.assert_called_once_with()
