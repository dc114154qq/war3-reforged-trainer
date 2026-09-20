import ctypes as c
import struct
from types import SimpleNamespace
from unittest.mock import Mock, patch

import war3_engine_transport as transport


def test_remote_entry_allows_process_local_instrumentation():
    assert transport.remote_entry_valid(b"\xE9" + b"\x90" * 15)
    assert not transport.remote_entry_valid(bytes(16))
    assert not transport.remote_entry_valid(b"\x90" * 15)


class _Export:
    def __init__(self, name, address):
        self.name = name
        self.address = address


class _FakePE:
    DIRECTORY_ENTRY_EXPORT = SimpleNamespace(
        symbols=[
            _Export(b"bridge_abi", 0),
            _Export(b"BridgeInstall", 0x30),
            _Export(b"BridgeUninstall", 0x40),
            _Export(b"BridgeHeroQuery", 0x50),
        ],
    )
    OPTIONAL_HEADER = SimpleNamespace(
        DATA_DIRECTORY=[SimpleNamespace(Size=0) for _ in range(3)]
        + [SimpleNamespace(Size=0x24, VirtualAddress=0x200)],
    )

    @staticmethod
    def get_data(address, size):
        if address == 0 and size == len(transport.ABI):
            return transport.ABI
        return b"X" * size


def _hero_payload():
    return (
        struct.pack("<8Q", *[0x10000 + index * 0x100 for index in range(8)])
        + bytes(480 - 64)
        + struct.pack(
            "<5Q4I",
            0x20000,
            0x20100,
            0x20200,
            0x20300,
            0x100000,
            0,
            0,
            0,
            0,
        )
        + bytes(96)
    )


def test_dispatch_uses_target_loader_and_unloads_after_verified_callback(tmp_path):
    image = tmp_path / "war3_bridge_24268_2_0_1.dll"
    image.write_bytes(b"loader-backed bridge")
    command_states = [
        dict(
            hook=0x700,
            target_tid=44,
            message=55,
            nonce=66,
            stage=2,
            last_error=0,
            callback_tid=0,
            callback_count=0,
            detached=0,
            active=0,
            query_result="0x0",
            tls_value="0x0",
            query_stage=0,
            exception_code="0x0",
            unwind_registered=0,
            unwind_removed=0,
        ),
        dict(
            hook=0x700,
            target_tid=44,
            message=55,
            nonce=66,
            stage=3,
            last_error=0,
            callback_tid=44,
            callback_count=1,
            detached=1,
            active=0,
            query_result="0x1234",
            tls_value="0x100000",
            query_stage=2,
            exception_code="0x0",
            unwind_registered=0,
            unwind_removed=0,
        ),
    ]
    resolve_addresses = {
        ("user32", "SetWindowsHookExW"): 0x101,
        ("user32", "UnhookWindowsHookEx"): 0x102,
        ("user32", "CallNextHookEx"): 0x103,
        ("kernel32", "GetCurrentThreadId"): 0x104,
        ("kernel32", "GetLastError"): 0x105,
        ("kernel32", "Sleep"): 0x106,
        ("kernel32", "TlsGetValue"): 0x107,
        ("ntdll", "RtlAddFunctionTable"): 0x108,
        ("ntdll", "RtlDeleteFunctionTable"): 0x109,
        ("ntdll", "__C_specific_handler"): 0x10A,
    }
    allocations = iter((0x200000, 0x210000, 0x220000))
    thread_calls = []

    def fake_create_thread(_handle, _a, _b, address, _param, _flags, tid):
        thread_calls.append(address)
        c.cast(tid, c.POINTER(transport.U))[0] = 99 if address == 0x700030 else 98
        return 0x500000 + len(thread_calls)

    def fake_write(_handle, _address, _buffer, size, written):
        c.cast(written, c.POINTER(transport.Z))[0] = size
        return True

    fake_p = dict(transport.p)
    fake_p.update(
        open_process=Mock(return_value=1),
        close=Mock(return_value=True),
        alloc=Mock(side_effect=lambda *_args: next(allocations)),
        free=Mock(return_value=True),
        create_thread=fake_create_thread,
        wait=Mock(return_value=0),
        write=fake_write,
        bytes_at=Mock(return_value=b"X" * 16),
    )
    fake_p["api"] = lambda _library, _name, *_args: Mock(return_value=True)
    fake_h = dict(transport.h)
    fake_h.update(
        module_base=Mock(return_value=0x700000),
        send=Mock(return_value=True),
    )

    def fake_resolve(_memory, library, name):
        return resolve_addresses[(library, name)]

    def fake_fields(_handle, _address):
        return command_states.pop(0) if len(command_states) > 1 else command_states[0]

    def fake_window_thread(_hwnd, owner):
        c.cast(owner, c.POINTER(transport.U))[0] = 1234
        return 44

    def fake_map(_section, _handle, view, _zero_bits, _commit_size, _offset, size, _inherit, _allocation_type, _protect):
        c.cast(view, c.POINTER(transport.P))[0] = 0x700000
        c.cast(size, c.POINTER(transport.Z))[0] = 0x4000
        return 0

    fake_x = {
        "create_file": Mock(return_value=0x300000),
        "create_mapping": Mock(return_value=0x310000),
        "map_section": Mock(side_effect=fake_map),
        "unmap_section": Mock(return_value=0),
    }

    fake_pe = patch.object(transport.pefile, "PE", return_value=_FakePE())
    with fake_pe, patch.object(transport, "p", fake_p), patch.object(transport, "h", fake_h), \
            patch.object(transport, "resolve", side_effect=fake_resolve), \
            patch.object(transport, "x", fake_x), \
            patch.object(transport, "window_thread", side_effect=fake_window_thread), \
            patch.object(transport, "register_message", return_value=55), \
            patch.object(transport, "fields", side_effect=fake_fields):
        result = transport.dispatch(
            1234, 0x99, 44, image, 7, _hero_payload(), kind="hero",
        )

    assert result.get("image_route") == "manual_map", result
    assert result["image_map"]["method"] == "NtMapViewOfSection"
    assert result["image_unwind"]["count"] == 3
    assert result["image_unmap_status"] == "0x0"
    assert result["callback_verified"] is True
    assert result["query_completed"] is True
    assert result["safe_to_release"] is True
    assert result["same_route_retry"] == {"attempted": False}
    assert thread_calls[0] == 0x700030


def test_dispatch_retries_only_after_clean_hook_install_failure():
    first = {
        "route_attempt": 1,
        "image_map": {"method": "NtMapViewOfSection", "completed": True},
        "safe_to_release": True,
        "allocations_retained": False,
        "after_cleanup": {
            "stage": 2,
            "hook": 0,
            "callback_tid": 0,
            "callback_count": 0,
            "query_stage": 0,
            "bridge_install_trace": "0x105",
            "last_error": 126,
            "exception_code": "0xc0000005",
        },
    }
    second = {"route_attempt": 2, "callback_verified": True}
    with patch.object(transport, "_dispatch_once", side_effect=[first, second]) as dispatch_once:
        result = transport.dispatch(1, 2, 3, None, 4, b"", kind="camera")

    assert result["same_route_retry"]["attempted"] is True
    assert result["same_route_retry"]["reason"] == "clean_hook_install_failure"
    assert result["same_route_retry"]["first_attempt"]["last_error"] == 126
    assert dispatch_once.call_count == 2
    assert dispatch_once.call_args_list[0].kwargs["attempt"] == 1
    assert dispatch_once.call_args_list[1].kwargs["attempt"] == 2


def test_dispatch_does_not_retry_when_resources_are_retained():
    report = {
        "route_attempt": 1,
        "safe_to_release": False,
        "allocations_retained": True,
        "after_cleanup": {
            "stage": 2,
            "hook": 0,
            "callback_tid": 0,
            "callback_count": 0,
            "query_stage": 0,
            "bridge_install_trace": "0x105",
            "last_error": 126,
            "exception_code": "0xc0000005",
        },
    }
    with patch.object(transport, "_dispatch_once", return_value=report) as dispatch_once:
        result = transport.dispatch(1, 2, 3, None, 4, b"", kind="camera")

    assert result["same_route_retry"] == {"attempted": False}
    dispatch_once.assert_called_once()
