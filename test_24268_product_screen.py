import ctypes as c
from pathlib import Path
from unittest.mock import Mock

import pytest

from war3_native_table import LiveNativeEntry
from war3_screen_protocol import SIGNATURES, build_work, decode_work
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
    dll.BridgeScreenTestRun.argtypes = [c.c_void_p, c.c_int32, c.c_int32, c.c_int]
    dll.BridgeScreenTestRun.restype = c.c_uint64
    return dll


def test_screen_query_returns_current_pixel_coordinates(fixture):
    payload = c.create_string_buffer(work())
    assert fixture.BridgeScreenTestRun(payload, 960, 540, 0) == (540 << 32) | 960
    result = decode_work(payload.raw[:128])
    assert (result["x"], result["y"]) == (960, 540)


def test_screen_query_propagates_failure(fixture):
    payload = c.create_string_buffer(work())
    assert fixture.BridgeScreenTestRun(payload, 960, 540, 1460) == 0
    with pytest.raises(ValueError, match="error=1460"):
        decode_work(payload.raw[:128])


def test_screen_transport_rejects_wrong_payload_before_target_access(monkeypatch):
    monkeypatch.setattr(transport, "window_thread", Mock(side_effect=AssertionError("opened")))
    with pytest.raises(ValueError):
        transport.dispatch(1, 2, 3, Path("missing.dll"), 0, bytes(127), kind="screen_mouse")


def test_screen_route_uses_current_engine_batch():
    trainer = object.__new__(product.War3Trainer)
    trainer._engine_instance_24268 = Mock()
    trainer._engine_instance_24268.return_value.mouse_screen_point.return_value = {"x": 960, "y": 540}
    trainer._native_selection_unavailable = True
    assert trainer.mouse_screen_point_24268() == (960, 540)
