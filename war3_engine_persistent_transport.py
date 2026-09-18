"""Session-scoped transport for the 3.0 in-process classic hook chain.

The bridge is manually mapped into the game because the game loader does not
reliably accept an ordinary hook DLL.  This module keeps that mapped image,
worker thread, and thread hook alive for the lifetime of one Engine24268
instance.  Each request replaces only the command/work block and posts one
message through the already-installed hook.
"""

from __future__ import annotations

import ctypes as c
import hashlib
import struct
import time
import traceback
import uuid
from pathlib import Path

import war3_engine_transport as base


P, U, Z = base.P, base.U, base.Z
PERSISTENT_HOOK_FLAG = 0x80000000
WH_GETMESSAGE = 3
COMMAND_SIZE = 216


def _batch_spec(kind: str, work_payload: bytes):
    if kind == "hero":
        from war3_hero_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"bridge_abi", b"BridgeHeroQuery"
    if kind == "ability":
        from war3_ability_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"ability_batch_abi", b"BridgeAbilityQuery"
    if kind == "ability_field":
        from war3_ability_field_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"ability_field_batch_abi", b"BridgeAbilityFieldQuery"
    if kind == "item":
        from war3_item_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"item_batch_abi", b"BridgeItemQuery"
    if kind == "item_catalog":
        from war3_item_catalog_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"item_catalog_batch_abi", b"BridgeItemCatalogQuery"
    if kind == "item_field":
        from war3_item_field_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"item_field_batch_abi", b"BridgeItemFieldQuery"
    if kind == "clone":
        from war3_clone_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"clone_batch_abi", b"BridgeCloneQuery"
    if kind == "unit_action":
        from war3_unit_action_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"unit_action_batch_abi", b"BridgeUnitActionQuery"
    if kind == "world":
        from war3_world_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"world_batch_abi", b"BridgeWorldQuery"
    if kind == "map_flags":
        from war3_map_flags_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"map_flags_batch_abi", b"BridgeMapFlagsQuery"
    if kind == "bulk":
        from war3_bulk_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"bulk_batch_abi", b"BridgeBulkQuery"
    if kind == "effect":
        from war3_effect_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"effect_batch_abi", b"BridgeEffectQuery"
    if kind == "world_effect":
        from war3_world_effect_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"world_effect_batch_abi", b"BridgeWorldEffectQuery"
    if kind == "spawn":
        from war3_spawn_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"spawn_batch_abi", b"BridgeSpawnQuery"
    if kind == "mouse":
        from war3_mouse_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"mouse_batch_abi", b"BridgeMouseQuery"
    if kind == "screen_mouse":
        from war3_screen_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"screen_mouse_batch_abi", b"BridgeScreenMouseQuery"
    if kind == "camera":
        from war3_camera_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"camera_batch_abi", b"BridgeCameraQuery"
    if kind == "position":
        from war3_position_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"position_batch_abi", b"BridgePositionQuery"
    if kind == "terrain":
        from war3_terrain_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"terrain_batch_abi", b"BridgeTerrainQuery"
    if kind == "map_bounds":
        from war3_map_bounds_protocol import ABI, validate_work
        validate_work(work_payload)
        return ABI, b"map_bounds_batch_abi", b"BridgeMapBoundsQuery"
    raise ValueError("Unknown current-engine batch kind")


def _clean_install_failure(report: dict) -> bool:
    state = report.get("after_cleanup") or report.get("after_install") or {}
    trace = state.get("bridge_install_trace", "")
    return bool(
        report.get("safe_to_release")
        and not report.get("allocations_retained")
        and state.get("stage") == 2
        and not state.get("hook")
        and state.get("callback_count") == 0
        and state.get("callback_tid") == 0
        and state.get("query_stage") == 0
        and (trace in ("0x105", "0x106") or state.get("last_error") in (126,))
    )


class PersistentBridgeSession:
    """Keep one manually mapped bridge and hook alive across batch calls."""

    def __init__(self, pid: int, hwnd: int, image: Path):
        self.pid = int(pid)
        self.hwnd = int(hwnd)
        self.image = Path(image)
        self._lock = __import__("threading").RLock()
        self._resource: dict | None = None
        self._last_close: dict = {}

    @property
    def active(self) -> bool:
        return self._resource is not None

    def _base_report(self, tid: int, attempt: int) -> dict:
        return {
            "pid": self.pid,
            "hwnd": hex(self.hwnd),
            "expected_callback_tid": int(tid),
            "target_window": {
                "hwnd": hex(self.hwnd),
                "pid": self.pid,
                "thread_id": int(tid),
            },
            "process_access": "0x43a",
            "hook_kind": "WH_GETMESSAGE",
            "message_delivery": "posted",
            "route_policy": "manual_map+WH_GETMESSAGE+PostMessage+persistent",
            "image": str(self.image),
            "image_sha256": hashlib.sha256(self.image.read_bytes()).hexdigest(),
            "calls_game_handlers": True,
            "query_mode": "current-engine",
            "delivery_mode": "posted",
            "image_route": "manual_map",
            "route_attempt": attempt,
            "persistent_transport": True,
        }

    @staticmethod
    def _pack_command(resource: dict, query: int, work: int, *,
                      message: int, nonce: int, stage: int, hook: int,
                      initial: bool) -> bytes:
        payload = struct.pack(
            "<7QIIQ6IQII",
            resource["hwnd"],
            *resource["api_addresses"],
            hook,
            resource["target_tid"],
            message,
            nonce,
            stage,
            0,
            0,
            0,
            0,
            0,
            resource["sleep_address"],
            0,
            WH_GETMESSAGE | PERSISTENT_HOOK_FLAG,
        )
        payload += struct.pack(
            "<9Q6I",
            resource["tls_get"],
            resource["add_table"],
            resource["delete_table"],
            resource["unwind_table"],
            resource["image_base"],
            query,
            0,
            0,
            resource["specific_handler"],
            resource["unwind_count"],
            resource["tls_index"],
            0,
            0,
            0 if initial else 1,
            0,
        )
        payload += struct.pack("<Q", work)
        if len(payload) != COMMAND_SIZE:
            raise RuntimeError(f"persistent bridge command size mismatch: {len(payload)}")
        return payload

    def _release_setup(
        self, report: dict, handle, file, section, block: int,
        work: int, view, image_base: int, thread,
    ) -> None:
        completed = not thread or base.p["wait"](thread, 1500) == 0
        if thread:
            report.setdefault("install_thread", {})["completed"] = completed
        if not completed:
            report["allocations_retained"] = True
            report["remote_thread_retained"] = True
            return
        if image_base and handle:
            try:
                status = int(base.x["unmap_section"](handle, view)) & 0xFFFFFFFF
                report["image_unmap_status"] = hex(status)
            except Exception as exc:
                report["image_unmap_error"] = repr(exc)
                report["allocations_retained"] = True
        if handle:
            for label, address in (("work_freed", work), ("block_freed", block)):
                if address and not report.get("allocations_retained"):
                    try:
                        report[label] = bool(base.p["free"](handle, address, 0, 0x8000))
                    except Exception as exc:
                        report[label + "_error"] = repr(exc)
                        report[label] = False
        if thread:
            base.p["close"](thread)
        if handle:
            base.p["close"](handle)
        if section:
            base.p["close"](section)
        if file:
            base.p["close"](file)
        report["safe_to_release"] = not report.get("allocations_retained")

    def _start(self, tid: int, tls_index: int, work_payload: bytes,
               kind: str, attempt: int) -> dict:
        report = self._base_report(tid, attempt)
        handle = file = section = thread = work = None
        block = 0
        view = P()
        image_base = 0
        try:
            expected_abi, marker_name, query_name = _batch_spec(kind, work_payload)
            owner = U()
            if base.window_thread(self.hwnd, c.byref(owner)) != tid or owner.value != self.pid:
                raise RuntimeError("Bridge target window/thread identity changed")
            if not self.image.is_file():
                raise RuntimeError("Missing current 24268 bridge module: " + str(self.image))
            pe = base.pefile.PE(str(self.image))
            exports = {symbol.name: symbol.address for symbol in pe.DIRECTORY_ENTRY_EXPORT.symbols}
            marker = exports.get(marker_name)
            if marker is None or pe.get_data(marker, len(expected_abi)) != expected_abi:
                raise ValueError("24268 bridge ABI differs; rebuild the current-engine module")
            install_rva = exports[b"BridgeInstall"]
            directory = pe.OPTIONAL_HEADER.DATA_DIRECTORY[3]
            if not directory.Size or directory.Size % 12:
                raise RuntimeError("Unwind table missing")

            handle = base.p["open_process"](0x43A, False, self.pid)
            if not handle:
                raise c.WinError(c.get_last_error())
            memory = type("Memory", (), {"handle": handle, "pid": self.pid})()
            api_specs = [
                ("user32", "SetWindowsHookExW"),
                ("user32", "UnhookWindowsHookEx"),
                ("user32", "CallNextHookEx"),
                ("kernel32", "GetCurrentThreadId"),
                ("kernel32", "GetLastError"),
            ]
            addresses = [base.resolve(memory, library, name) for library, name in api_specs]
            sleep_address = base.resolve(memory, "kernel32", "Sleep")
            report["remote_api_resolution"] = {
                f"{library}!{name}": hex(address)
                for (library, name), address in zip(api_specs, addresses)
            }
            report["remote_api_resolution"]["kernel32!Sleep"] = hex(sleep_address)

            report["image_map"] = {"method": "NtMapViewOfSection", "completed": False}
            file = base.x["create_file"](str(self.image), 0x80000000, 5, None, 3, 0x80, None)
            if file == P(-1).value:
                file = None
                raise c.WinError(c.get_last_error())
            section = base.x["create_mapping"](file, None, 0x1000002, 0, 0, None)
            if not section:
                raise c.WinError(c.get_last_error())
            size = Z()
            status = base.x["map_section"](
                section, handle, c.byref(view), 0, 0, None, c.byref(size), 2, 0, 2,
            )
            if status < 0:
                raise RuntimeError("Image map failed " + hex(status & 0xFFFFFFFF))
            image_base = int(view.value or 0)
            if not image_base:
                raise RuntimeError("Image map returned a null base")
            report["image_base"] = hex(image_base)
            report["image_map"] = {
                "method": "NtMapViewOfSection",
                "status": hex(status & 0xFFFFFFFF),
                "size": int(size.value),
                "completed": True,
            }
            for rva in (install_rva, exports[b"BridgeUninstall"]):
                if base.p["bytes_at"](handle, image_base + rva, 16) != pe.get_data(rva, 16):
                    raise RuntimeError("Image bytes differ")

            block = base.p["alloc"](handle, None, COMMAND_SIZE, 0x3000, 4)
            if not block:
                raise c.WinError(c.get_last_error())
            message = base.register_message("Codex.War3.PersistentDispatch." + str(uuid.uuid4()))
            if not message:
                raise c.WinError(c.get_last_error())
            nonce = int.from_bytes(__import__("os").urandom(8), "little") & 0x7FFFFFFFFFFFFFFF
            resource = {
                "handle": handle,
                "file": file,
                "section": section,
                "view": view,
                "image_base": image_base,
                "block": block,
                "work": 0,
                "thread": None,
                "target_tid": int(tid),
                "tls_index": int(tls_index),
                "hwnd": self.hwnd,
                "message": int(message),
                "nonce": int(nonce),
                "api_addresses": addresses,
                "sleep_address": sleep_address,
                "tls_get": base.resolve(memory, "kernel32", "TlsGetValue"),
                "add_table": base.resolve(memory, "ntdll", "RtlAddFunctionTable"),
                "delete_table": base.resolve(memory, "ntdll", "RtlDeleteFunctionTable"),
                "unwind_table": image_base + directory.VirtualAddress,
                "unwind_count": directory.Size // 12,
                "specific_handler": base.resolve(memory, "ntdll", "__C_specific_handler"),
                "exports": exports,
                "image": self.image,
                "memory": memory,
                "hook": 0,
                "unwind_registered": 0,
            }
            query = image_base + exports[query_name]
            work = base.p["alloc"](handle, None, len(work_payload), 0x3000, 4)
            if not work:
                raise c.WinError(c.get_last_error())
            written = Z()
            local_work = c.create_string_buffer(bytes(work_payload))
            if not base.p["write"](handle, work, local_work, len(work_payload), c.byref(written)) or written.value != len(work_payload):
                raise c.WinError(c.get_last_error())
            resource["work"] = work
            payload = self._pack_command(
                resource, query, work, message=message, nonce=nonce,
                stage=0, hook=0, initial=True,
            )
            buffer = c.create_string_buffer(payload)
            if not base.p["write"](handle, block, buffer, COMMAND_SIZE, c.byref(written)) or written.value != COMMAND_SIZE:
                raise c.WinError(c.get_last_error())
            remote_tid = U()
            thread = base.p["create_thread"](
                handle, None, 0, image_base + install_rva, block, 0, c.byref(remote_tid),
            )
            if not thread:
                raise c.WinError(c.get_last_error())
            resource["thread"] = thread
            report["install_thread"] = {"tid": int(remote_tid.value), "created": True}
            deadline = time.monotonic() + 1.5
            state = base.fields(handle, block)
            while state["stage"] < 2 and time.monotonic() < deadline:
                if base.p["wait"](thread, 0) == 0:
                    break
                time.sleep(0.005)
                state = base.fields(handle, block)
            report["after_install"] = state
            if state["stage"] != 2 or not state["hook"]:
                report["after_cleanup"] = state
                report["safe_to_release"] = True
                self._release_setup(report, handle, file, section, block, work, view, image_base, thread)
                return report
            resource["hook"] = int(state["hook"])
            resource["unwind_registered"] = int(state.get("unwind_registered", 0))
            self._resource = resource
            # Ownership moved to the session only after the hook is live.
            handle = file = section = thread = work = None
            block = 0
            image_base = 0
            return report
        except Exception as exc:
            report["error"] = repr(exc)
            report["traceback"] = traceback.format_exc()
            report["safe_to_release"] = False
            self._release_setup(report, handle, file, section, block, work, view, image_base, thread)
            return report

    def _submit(self, tid: int, tls_index: int, work_payload: bytes,
                kind: str, report: dict, *, initial: bool) -> dict:
        resource = self._resource
        if resource is None:
            raise RuntimeError("persistent bridge session is not active")
        if resource["target_tid"] != int(tid) or resource["tls_index"] != int(tls_index):
            raise RuntimeError("persistent bridge target thread context changed")
        _expected_abi, _marker_name, query_name = _batch_spec(kind, work_payload)
        query = resource["image_base"] + resource["exports"][query_name]
        nonce = (
            resource["nonce"]
            if initial
            else int.from_bytes(__import__("os").urandom(8), "little") & 0x7FFFFFFFFFFFFFFF
        )
        work = resource["work"]
        if not initial:
            work = base.p["alloc"](resource["handle"], None, len(work_payload), 0x3000, 4)
            if not work:
                raise c.WinError(c.get_last_error())
            written = Z()
            local_work = c.create_string_buffer(bytes(work_payload))
            if not base.p["write"](resource["handle"], work, local_work, len(work_payload), c.byref(written)) or written.value != len(work_payload):
                base.p["free"](resource["handle"], work, 0, 0x8000)
                raise c.WinError(c.get_last_error())
            resource["work"] = work
            payload = self._pack_command(
                resource, query, work, message=resource["message"], nonce=nonce,
                stage=2, hook=resource["hook"], initial=False,
            )
            buffer = c.create_string_buffer(payload)
            if not base.p["write"](resource["handle"], resource["block"], buffer, COMMAND_SIZE, c.byref(written)) or written.value != COMMAND_SIZE:
                raise c.WinError(c.get_last_error())
        reply = Z()
        post = base.p["api"](base.h["u"], "PostMessageW", c.c_int, P, U, Z, c.c_ssize_t)
        delivered = bool(post(self.hwnd, resource["message"], nonce, 0))
        report["post"] = {"enqueued": delivered, "error": c.get_last_error()}
        state = base.fields(resource["handle"], resource["block"])
        deadline = time.monotonic() + 1.5
        while delivered and state["stage"] != 3 and time.monotonic() < deadline:
            time.sleep(0.005)
            state = base.fields(resource["handle"], resource["block"])
        report["after_send"] = state
        report["persistent_session"] = {
            "active": True,
            "reused": not initial,
            "thread_id": resource["target_tid"],
            "hook": hex(resource["hook"]),
        }
        report["callback_verified"] = bool(
            delivered
            and state["stage"] == 3
            and state["callback_tid"] == tid
            and state["callback_count"] == 1
            and not state["detached"]
            and state["active"] == 0
        )
        report["query_completed"] = base.query_completed(state)
        if work and report["callback_verified"]:
            report["work_result_hex"] = base.p["bytes_at"](
                resource["handle"], work, len(work_payload),
            ).hex()
            report["work_freed"] = bool(base.p["free"](resource["handle"], work, 0, 0x8000))
            resource["work"] = 0
        else:
            report["work_freed"] = False
        report["block_freed"] = False
        report["image_unmap_status"] = "persistent"
        report["allocations_retained"] = False
        report["safe_to_release"] = False
        report["persistent_healthy"] = bool(
            report["callback_verified"] and report["query_completed"] and report["work_freed"]
        )
        return report

    def dispatch(self, pid: int, hwnd: int, tid: int, image: Path,
                 tls_index: int, work_payload: bytes, kind: str = "hero") -> dict:
        with self._lock:
            if (int(pid), int(hwnd), Path(image)) != (self.pid, self.hwnd, self.image):
                self.close()
                self.pid, self.hwnd, self.image = int(pid), int(hwnd), Path(image)
            if self._resource is not None:
                owner = U()
                current_tid = base.window_thread(self.hwnd, c.byref(owner))
                if owner.value != self.pid or current_tid != int(tid):
                    self.close()
            if self._resource is None:
                attempts = []
                for attempt, delay in enumerate((0.0, 0.04, 0.12, 0.30), 1):
                    if delay:
                        time.sleep(delay)
                    report = self._start(tid, tls_index, work_payload, kind, attempt)
                    if self._resource is None:
                        attempts.append({
                            "route_attempt": attempt,
                            "bridge_install_trace": (report.get("after_cleanup") or report.get("after_install") or {}).get("bridge_install_trace"),
                            "last_error": (report.get("after_cleanup") or report.get("after_install") or {}).get("last_error"),
                            "exception_code": (report.get("after_cleanup") or report.get("after_install") or {}).get("exception_code"),
                            "safe_to_release": report.get("safe_to_release"),
                        })
                        if _clean_install_failure(report) and attempt < 4:
                            continue
                        report["same_route_retry"] = {
                            "attempted": len(attempts) > 1,
                            "reason": "persistent_hook_install_failure" if len(attempts) > 1 else "none",
                            "attempts": attempts,
                        }
                        return report
                    try:
                        result = self._submit(tid, tls_index, work_payload, kind, report, initial=True)
                    except Exception as exc:
                        report["error"] = repr(exc)
                        report["traceback"] = traceback.format_exc()
                        self.close()
                        report["persistent_session"] = {"active": False}
                        return report
                    result["same_route_retry"] = {
                        "attempted": len(attempts) > 0,
                        "reason": "persistent_hook_install_failure" if attempts else "none",
                        "attempts": attempts,
                    }
                    if result.get("persistent_healthy"):
                        return result
                    self.close()
                    return result
                return report
            try:
                result = self._submit(tid, tls_index, work_payload, kind,
                                      self._base_report(tid, 1), initial=False)
            except Exception as exc:
                result = self._base_report(tid, 1)
                result["error"] = repr(exc)
                result["traceback"] = traceback.format_exc()
                self.close()
                return result
            if not result.get("persistent_healthy"):
                self.close()
            return result

    def close(self) -> dict:
        with self._lock:
            resource = self._resource
            if resource is None:
                return {"closed": True, "retained": False}
            report = {"closed": False, "retained": False}
            try:
                stop = c.c_ulong(1)
                written = Z()
                if not base.p["write"](
                    resource["handle"], resource["block"] + 104,
                    c.byref(stop), 4, c.byref(written),
                ):
                    raise c.WinError(c.get_last_error())
                completed = base.p["wait"](resource["thread"], 1500) == 0
                report["thread_completed"] = completed
                state = base.fields(resource["handle"], resource["block"])
                report["after_cleanup"] = state
                safe = bool(
                    completed
                    and state.get("detached")
                    and state.get("active") == 0
                    and (not state.get("unwind_registered") or state.get("unwind_removed"))
                )
                if not safe:
                    report["retained"] = True
                    return report
                if resource["work"]:
                    report["work_freed"] = bool(base.p["free"](
                        resource["handle"], resource["work"], 0, 0x8000,
                    ))
                    if not report["work_freed"]:
                        report["retained"] = True
                        return report
                    resource["work"] = 0
                status = int(base.x["unmap_section"](
                    resource["handle"], resource["view"],
                )) & 0xFFFFFFFF
                report["image_unmap_status"] = hex(status)
                if status != 0:
                    report["retained"] = True
                    return report
                report["block_freed"] = bool(base.p["free"](
                    resource["handle"], resource["block"], 0, 0x8000,
                ))
                if not report["block_freed"]:
                    report["retained"] = True
                    return report
                base.p["close"](resource["thread"])
                base.p["close"](resource["handle"])
                base.p["close"](resource["section"])
                base.p["close"](resource["file"])
                report["closed"] = bool(report["block_freed"])
                self._resource = None
                self._last_close = report
                return report
            except Exception as exc:
                report["error"] = repr(exc)
                report["traceback"] = traceback.format_exc()
                report["retained"] = True
                return report

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
