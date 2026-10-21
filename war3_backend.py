# -*- coding: utf-8 -*-
"""Warcraft III Reforged local trainer.

This replaces the old 32-bit game.dll trainer path with verified Reforged routes:
- Warcraft cheat input through PostMessageW, avoiding IME/keyboard layout issues.
- Reforged 64-bit selected-unit handle -> unit owner -> property table memory path.
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import ctypes
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from decimal import Decimal, InvalidOperation
import math
import os
import platform
import tempfile
import struct
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Iterable, Iterator

from war3_ability_fields import (
    ABILITY_FIELD_BY_KEY,
    AbilityFieldSpec,
    ability_fields_for_effect_class,
)
from war3_id_catalog import CATALOG_COUNTS, search_id_entries
from war3_item_fields import ITEM_FIELD_BY_KEY, ITEM_FIELD_CATALOG, ItemFieldSpec
from war3_3_extension_catalog import (
    EQUIPMENT_SLOT_NAMES,
    EQUIPMENT_SLOT_TYPES,
    EQUIPMENT_TYPE_NAMES,
    OFFICIAL_BACKPACKS,
    TALENT_CONTROLLERS,
)
from war3_3_stats import STAT_DETAIL_BY_KEY, STAT_DETAIL_SPECS
from war3_metadata import APP_VERSION, APP_RELEASE_CHANNEL, GAME_BUILD, PRODUCT_READ_MODE, PRODUCT_EDITION_LABEL, WIN10_COMPAT_REVISION
from war3_contracts import Region, ResourceCache, ResourceProperty, LocalPlayerResources, UnitCandidate, VisibleUnitPanel, UnitMemoryField, InventoryItem, AbilityInstance, UnitSelectionSummary, MemoryWriteSpec, NativeHandler, NativeAbilityInternals, NativeHelperOpResult, PersistentNativeUnitSnapshot, SelectedAbilityFieldContext, AbilityFieldValue, AbilityFieldSnapshot, ItemFieldContext, ItemFieldValue, ItemFieldSnapshot, JassSelectionProbeResult, NativeSelectionProbeResult, selection_confidence_text, format_rawcode, format_editable_float32, parse_integer_number, coerce_finite_float32, parse_int, parse_float, parse_changed_coordinate, parse_unit_identity, close_float




if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
TOKEN_ADJUST_PRIVILEGES = 0x0020
TOKEN_QUERY = 0x0008
SE_PRIVILEGE_ENABLED = 0x00000002
TOKEN_SESSION_ID = 12
TOKEN_INFORMATION_ELEVATION = 20
TOKEN_INTEGRITY_LEVEL = 25

MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
MEM_MAPPED = 0x40000
MEM_IMAGE = 0x1000000
PAGE_NOACCESS = 0x01
PAGE_READWRITE = 0x04
PAGE_GUARD = 0x100
PAGE_EXECUTE = 0x10
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80
READABLE_PROTECTS = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}
EXECUTABLE_PROTECTS = {PAGE_EXECUTE, PAGE_EXECUTE_READ, PAGE_EXECUTE_READWRITE, PAGE_EXECUTE_WRITECOPY}
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
WM_NULL = 0x0000
WM_QUIT = 0x0012
WM_HOTKEY = 0x0312
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_F1 = 0x70
VK_F11 = 0x7A
VK_F12 = 0x7B
VK_HOME = 0x24
VK_END = 0x23
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_NUMPAD1 = 0x61
VK_NUMPAD2 = 0x62
VK_NUMPAD3 = 0x63
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
MB_ICONASTERISK = 0x00000040
SW_RESTORE = 9
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
WH_CALLWNDPROC = 4
SMTO_ABORTIFHUNG = 0x0002
WAIT_OBJECT_0 = 0x00000000
WAIT_ABANDONED = 0x00000080
WAIT_TIMEOUT = 0x00000102
ERROR_NOT_SUPPORTED = 50
ERROR_NOT_FOUND = 1168
ERROR_PARTIAL_COPY = 299
ERROR_ACCESS_DENIED = 5
ERROR_NOT_ALL_ASSIGNED = 1300
ERROR_HOTKEY_ALREADY_REGISTERED = 1409


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

kernel32.OpenProcess.restype = ctypes.c_void_p
kernel32.QueryFullProcessImageNameW.argtypes = (
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.c_wchar_p,
    ctypes.POINTER(ctypes.c_ulong),
)
kernel32.QueryFullProcessImageNameW.restype = ctypes.c_bool
kernel32.GetCurrentProcess.restype = ctypes.c_void_p
kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p)
kernel32.CreateMutexW.restype = ctypes.c_void_p
kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
kernel32.WaitForSingleObject.restype = ctypes.c_ulong
kernel32.ReleaseMutex.argtypes = (ctypes.c_void_p,)
kernel32.ReleaseMutex.restype = ctypes.c_bool
kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
kernel32.CloseHandle.restype = ctypes.c_bool
kernel32.LoadLibraryW.argtypes = (ctypes.c_wchar_p,)
kernel32.LoadLibraryW.restype = ctypes.c_void_p
kernel32.GetProcAddress.argtypes = (ctypes.c_void_p, ctypes.c_char_p)
kernel32.GetProcAddress.restype = ctypes.c_void_p
kernel32.FreeLibrary.argtypes = (ctypes.c_void_p,)
kernel32.FreeLibrary.restype = ctypes.c_bool
user32.SetWindowsHookExW.argtypes = (
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_ulong,
)
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.UnhookWindowsHookEx.argtypes = (ctypes.c_void_p,)
user32.UnhookWindowsHookEx.restype = ctypes.c_bool
user32.SendMessageW.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)
user32.SendMessageW.restype = ctypes.c_void_p
user32.SendMessageTimeoutW.argtypes = (
    ctypes.c_void_p,
    ctypes.c_uint,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_uint,
    ctypes.c_uint,
    ctypes.POINTER(ctypes.c_void_p),
)
user32.SendMessageTimeoutW.restype = ctypes.c_void_p
user32.GetForegroundWindow.restype = ctypes.c_void_p
user32.GetWindowThreadProcessId.argtypes = (
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_ulong),
)
user32.GetWindowThreadProcessId.restype = ctypes.c_ulong
user32.IsWindowVisible.argtypes = (ctypes.c_void_p,)
user32.IsWindowVisible.restype = ctypes.c_bool
user32.IsIconic.argtypes = (ctypes.c_void_p,)
user32.IsIconic.restype = ctypes.c_bool


class LUID(ctypes.Structure):
    _fields_ = [
        ("LowPart", ctypes.c_ulong),
        ("HighPart", ctypes.c_long),
    ]


class LUID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Luid", LUID),
        ("Attributes", ctypes.c_ulong),
    ]


class TOKEN_PRIVILEGES(ctypes.Structure):
    _fields_ = [
        ("PrivilegeCount", ctypes.c_ulong),
        ("Privileges", LUID_AND_ATTRIBUTES * 1),
    ]


class TOKEN_ELEVATION(ctypes.Structure):
    _fields_ = [("TokenIsElevated", ctypes.c_ulong)]


class SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Sid", ctypes.c_void_p),
        ("Attributes", ctypes.c_ulong),
    ]


class TOKEN_MANDATORY_LABEL(ctypes.Structure):
    _fields_ = [("Label", SID_AND_ATTRIBUTES)]


advapi32.OpenProcessToken.argtypes = (
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_void_p),
)
advapi32.OpenProcessToken.restype = ctypes.c_bool
advapi32.LookupPrivilegeValueW.argtypes = (
    ctypes.c_wchar_p,
    ctypes.c_wchar_p,
    ctypes.POINTER(LUID),
)
advapi32.LookupPrivilegeValueW.restype = ctypes.c_bool
advapi32.AdjustTokenPrivileges.argtypes = (
    ctypes.c_void_p,
    ctypes.c_bool,
    ctypes.POINTER(TOKEN_PRIVILEGES),
    ctypes.c_ulong,
    ctypes.c_void_p,
    ctypes.c_void_p,
)
advapi32.AdjustTokenPrivileges.restype = ctypes.c_bool
advapi32.GetTokenInformation.argtypes = (
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.c_void_p,
    ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_ulong),
)
advapi32.GetTokenInformation.restype = ctypes.c_bool
advapi32.GetSidSubAuthorityCount.argtypes = (ctypes.c_void_p,)
advapi32.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
advapi32.GetSidSubAuthority.argtypes = (ctypes.c_void_p, ctypes.c_ulong)
advapi32.GetSidSubAuthority.restype = ctypes.POINTER(ctypes.c_ulong)
kernel32.GetCurrentProcessId.restype = ctypes.c_ulong
kernel32.ProcessIdToSessionId.argtypes = (
    ctypes.c_ulong,
    ctypes.POINTER(ctypes.c_ulong),
)
kernel32.ProcessIdToSessionId.restype = ctypes.c_bool


def _token_information_buffer(token: ctypes.c_void_p, information_class: int):
    required = ctypes.c_ulong()
    ctypes.set_last_error(0)
    advapi32.GetTokenInformation(
        token,
        information_class,
        None,
        0,
        ctypes.byref(required),
    )
    if not required.value:
        return None, ctypes.get_last_error()
    buffer = ctypes.create_string_buffer(required.value)
    if not advapi32.GetTokenInformation(
        token,
        information_class,
        buffer,
        required.value,
        ctypes.byref(required),
    ):
        return None, ctypes.get_last_error()
    return buffer, 0


def _token_runtime_diagnostics(process_handle: ctypes.c_void_p) -> dict[str, object]:
    token = ctypes.c_void_p()
    if not advapi32.OpenProcessToken(process_handle, TOKEN_QUERY, ctypes.byref(token)):
        return {"token_open_error": ctypes.get_last_error()}
    try:
        result: dict[str, object] = {}
        elevation, error = _token_information_buffer(token, TOKEN_INFORMATION_ELEVATION)
        if elevation is not None:
            result["elevated"] = bool(
                ctypes.cast(elevation, ctypes.POINTER(TOKEN_ELEVATION)).contents.TokenIsElevated
            )
        elif error:
            result["elevation_error"] = error

        session, error = _token_information_buffer(token, TOKEN_SESSION_ID)
        if session is not None:
            result["token_session_id"] = ctypes.c_ulong.from_buffer_copy(session.raw[:4]).value
        elif error:
            result["token_session_error"] = error

        label, error = _token_information_buffer(token, TOKEN_INTEGRITY_LEVEL)
        if label is not None:
            mandatory = ctypes.cast(
                label,
                ctypes.POINTER(TOKEN_MANDATORY_LABEL),
            ).contents
            sid = mandatory.Label.Sid
            if sid:
                count = advapi32.GetSidSubAuthorityCount(sid)
                if count and count.contents.value:
                    rid = advapi32.GetSidSubAuthority(sid, count.contents.value - 1)
                    if rid:
                        integrity_rid = int(rid.contents.value)
                        result["integrity_rid"] = integrity_rid
                        result["integrity"] = {
                            0x1000: "low",
                            0x2000: "medium",
                            0x2100: "medium_plus",
                            0x3000: "high",
                            0x4000: "system",
                        }.get(integrity_rid, f"rid_{integrity_rid}")
        elif error:
            result["integrity_error"] = error
        return result
    finally:
        kernel32.CloseHandle(token)


_debug_privilege_lock = threading.Lock()
_debug_privilege_enabled = False


def enable_debug_privilege() -> bool:
    global _debug_privilege_enabled
    if _debug_privilege_enabled:
        return True
    with _debug_privilege_lock:
        if _debug_privilege_enabled:
            return True
        token = ctypes.c_void_p()
        if not advapi32.OpenProcessToken(
            kernel32.GetCurrentProcess(),
            TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
            ctypes.byref(token),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            luid = LUID()
            if not advapi32.LookupPrivilegeValueW(None, "SeDebugPrivilege", ctypes.byref(luid)):
                raise ctypes.WinError(ctypes.get_last_error())
            privileges = TOKEN_PRIVILEGES(
                PrivilegeCount=1,
                Privileges=(LUID_AND_ATTRIBUTES(luid, SE_PRIVILEGE_ENABLED),),
            )
            ctypes.set_last_error(0)
            if not advapi32.AdjustTokenPrivileges(
                token,
                False,
                ctypes.byref(privileges),
                0,
                None,
                None,
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            error = ctypes.get_last_error()
            if error == ERROR_NOT_ALL_ASSIGNED:
                return False
            if error:
                raise ctypes.WinError(error)
            _debug_privilege_enabled = True
            return True
        finally:
            kernel32.CloseHandle(token)


class POINT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_ulong),
        ("pt", POINT),
        ("lPrivate", ctypes.c_ulong),
    ]


kernel32.GetCurrentThreadId.restype = ctypes.c_ulong
user32.RegisterHotKey.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint)
user32.RegisterHotKey.restype = ctypes.c_bool
user32.UnregisterHotKey.argtypes = (ctypes.c_void_p, ctypes.c_int)
user32.UnregisterHotKey.restype = ctypes.c_bool
user32.GetMessageW.argtypes = (ctypes.POINTER(MSG), ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint)
user32.GetMessageW.restype = ctypes.c_int
user32.PostThreadMessageW.argtypes = (ctypes.c_ulong, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t)
user32.PostThreadMessageW.restype = ctypes.c_bool
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.MessageBeep.argtypes = (ctypes.c_uint,)
user32.MessageBeep.restype = ctypes.c_bool


def play_read_success_sound() -> None:
    try:
        user32.MessageBeep(MB_ICONASTERISK)
    except Exception:
        pass


def call_with_read_success_sound(fn: Callable[[], str]) -> str:
    result = fn()
    play_read_success_sound()
    return result


@dataclass(frozen=True)
class GlobalHotkeySpec:
    name: str
    label: str
    modifiers: int
    virtual_key: int
    poll_on_conflict: bool = True


def async_hotkey_is_down(spec: GlobalHotkeySpec) -> bool:
    modifier_states = (
        (MOD_ALT, bool(int(user32.GetAsyncKeyState(VK_MENU)) & 0x8000)),
        (MOD_CONTROL, bool(int(user32.GetAsyncKeyState(VK_CONTROL)) & 0x8000)),
        (MOD_SHIFT, bool(int(user32.GetAsyncKeyState(VK_SHIFT)) & 0x8000)),
        (
            MOD_WIN,
            bool(
                (int(user32.GetAsyncKeyState(VK_LWIN)) & 0x8000)
                or (int(user32.GetAsyncKeyState(VK_RWIN)) & 0x8000)
            ),
        ),
    )
    if any(bool(spec.modifiers & mask) != is_down for mask, is_down in modifier_states):
        return False
    return bool(int(user32.GetAsyncKeyState(spec.virtual_key)) & 0x8000)


class GlobalHotkeyManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._registered_names: tuple[str, ...] = ()
        self._fallback_thread: threading.Thread | None = None
        self._fallback_stop: threading.Event | None = None
        self._fallback_names: tuple[str, ...] = ()

    @property
    def registered_names(self) -> tuple[str, ...]:
        with self._lock:
            return self._registered_names

    @property
    def fallback_names(self) -> tuple[str, ...]:
        with self._lock:
            return self._fallback_names

    def start(
        self,
        specs: Iterable[GlobalHotkeySpec],
        on_trigger: Callable[[str], None],
    ) -> dict[str, int]:
        self.stop()
        spec_list = tuple(specs)
        ready = threading.Event()
        errors: dict[str, int] = {}

        def worker() -> None:
            registered: dict[int, GlobalHotkeySpec] = {}
            thread_id = int(kernel32.GetCurrentThreadId())
            with self._lock:
                self._thread_id = thread_id
            try:
                for hotkey_id, spec in enumerate(spec_list, 1):
                    ctypes.set_last_error(0)
                    if user32.RegisterHotKey(
                        None,
                        hotkey_id,
                        spec.modifiers | MOD_NOREPEAT,
                        spec.virtual_key,
                    ):
                        registered[hotkey_id] = spec
                    else:
                        errors[spec.name] = ctypes.get_last_error()
                with self._lock:
                    self._registered_names = tuple(spec.name for spec in registered.values())
                ready.set()

                message = MSG()
                while True:
                    result = int(user32.GetMessageW(ctypes.byref(message), None, 0, 0))
                    if result <= 0:
                        break
                    if message.message != WM_HOTKEY:
                        continue
                    spec = registered.get(int(message.wParam))
                    if spec is None:
                        continue
                    try:
                        on_trigger(spec.name)
                    except Exception:
                        pass
            finally:
                for hotkey_id in registered:
                    user32.UnregisterHotKey(None, hotkey_id)
                with self._lock:
                    self._registered_names = ()
                    self._thread_id = 0
                ready.set()

        thread = threading.Thread(target=worker, name="war3-global-hotkeys", daemon=True)
        with self._lock:
            self._thread = thread
        thread.start()
        if not ready.wait(3.0):
            self.stop()
            raise RuntimeError("全局快捷键线程启动超时")
        fallback_specs = tuple(
            spec
            for spec in spec_list
            if errors.get(spec.name) == ERROR_HOTKEY_ALREADY_REGISTERED
            and spec.poll_on_conflict
        )
        if fallback_specs:
            fallback_stop = threading.Event()

            def fallback_worker() -> None:
                pressed = {spec.name: False for spec in fallback_specs}
                try:
                    while not fallback_stop.is_set():
                        for spec in fallback_specs:
                            is_down = async_hotkey_is_down(spec)
                            if is_down and not pressed[spec.name]:
                                try:
                                    on_trigger(spec.name)
                                except Exception:
                                    pass
                            pressed[spec.name] = is_down
                        fallback_stop.wait(0.02)
                finally:
                    current = threading.current_thread()
                    with self._lock:
                        if self._fallback_thread is current:
                            self._fallback_thread = None
                            self._fallback_stop = None
                            self._fallback_names = ()

            fallback_thread = threading.Thread(
                target=fallback_worker,
                name="war3-global-hotkeys-fallback",
                daemon=True,
            )
            with self._lock:
                self._fallback_thread = fallback_thread
                self._fallback_stop = fallback_stop
                self._fallback_names = tuple(spec.name for spec in fallback_specs)
            fallback_thread.start()
        return dict(errors)

    def stop(self) -> None:
        with self._lock:
            thread = self._thread
            thread_id = self._thread_id
            fallback_thread = self._fallback_thread
            fallback_stop = self._fallback_stop
        if fallback_stop is not None:
            fallback_stop.set()
        if fallback_thread is not None and fallback_thread.is_alive():
            fallback_thread.join(timeout=2.0)
        if thread is None:
            return
        if thread.is_alive() and thread_id:
            user32.PostThreadMessageW(thread_id, WM_QUIT, 0, 0)
            thread.join(timeout=2.0)
        with self._lock:
            if self._thread is thread and not thread.is_alive():
                self._thread = None
                self._thread_id = 0
                self._registered_names = ()


ELEPHANT_HOTKEY_SPECS = (
    GlobalHotkeySpec("read_unit", "Ctrl+F11  读取所有选中单位", MOD_CONTROL, VK_F11),
    GlobalHotkeySpec("hero_level", "Ctrl+Q  英雄等级", MOD_CONTROL, ord("Q")),
    GlobalHotkeySpec("instant_move", "Ctrl+X  瞬间移动", MOD_CONTROL, ord("X")),
    GlobalHotkeySpec("explode_unit", "Ctrl+W  瞬间爆炸目标单位", MOD_CONTROL, ord("W")),
    GlobalHotkeySpec("reveal_map", "Home  开图", 0, VK_HOME),
    GlobalHotkeySpec("hide_map", "End  关图", 0, VK_END),
    GlobalHotkeySpec("invulnerable", "Ctrl+E  无敌", MOD_CONTROL, ord("E")),
    GlobalHotkeySpec("vulnerable", "Ctrl+R  取消无敌", MOD_CONTROL, ord("R")),
    GlobalHotkeySpec("reset_cooldown", "Ctrl+Z  重置冷却", MOD_CONTROL, ord("Z")),
    GlobalHotkeySpec("clone_to_self", "Ctrl+A  复制单位给自己", MOD_CONTROL, ord("A")),
    GlobalHotkeySpec("duplicate_inventory", "Ctrl+D  复制背包物品", MOD_CONTROL, ord("D")),
    GlobalHotkeySpec("unit_scale", "Ctrl+P  设置大小", MOD_CONTROL, ord("P")),
    GlobalHotkeySpec("item_charges", "Ctrl+F  物品数量", MOD_CONTROL, ord("F")),
    GlobalHotkeySpec("drop_inventory", "Ctrl+T  丢弃背包所有物品", MOD_CONTROL, ord("T")),
    GlobalHotkeySpec("add_ability", "Ctrl+G  添加技能", MOD_CONTROL, ord("G")),
    GlobalHotkeySpec("clone_unit", "Ctrl+B  复制单位", MOD_CONTROL, ord("B")),
    GlobalHotkeySpec("take_control", "Ctrl+I  获取对方控制权", MOD_CONTROL, ord("I")),
    GlobalHotkeySpec("add_resources", "Ctrl+L  增加金币木材", MOD_CONTROL, ord("L")),
    GlobalHotkeySpec("mass_clone", "Ctrl+N  大量复制", MOD_CONTROL, ord("N")),
    GlobalHotkeySpec("ability_level", "Ctrl+H  设置技能等级", MOD_CONTROL, ord("H")),
    GlobalHotkeySpec("remove_ability", "Ctrl+J  删除技能", MOD_CONTROL, ord("J")),
    GlobalHotkeySpec("all_auras", "Ctrl+Num1  全光环", MOD_CONTROL, VK_NUMPAD1),
    GlobalHotkeySpec("all_passives", "Ctrl+Num2  全被动", MOD_CONTROL, VK_NUMPAD2),
    GlobalHotkeySpec("six_artifacts", "Ctrl+Num3  得到6个神器", MOD_CONTROL, VK_NUMPAD3),
    GlobalHotkeySpec("reinforcements", "Ctrl+K  呼叫增援", MOD_CONTROL, ord("K")),
    GlobalHotkeySpec("preset_item", "Ctrl+M  得到物品", MOD_CONTROL, ord("M")),
    GlobalHotkeySpec("preset_tech", "Ctrl+O  得到科技", MOD_CONTROL, ord("O")),
    GlobalHotkeySpec("create_all_items", "Ctrl+S  创建所有物品", MOD_CONTROL, ord("S")),
    GlobalHotkeySpec("ignore_collision", "Alt+L  无视碰撞体积", MOD_ALT, ord("L")),
    GlobalHotkeySpec("hero_attributes", "Alt+Q  设置属性", MOD_ALT, ord("Q")),
    GlobalHotkeySpec("skill_points", "Alt+W  增加技能点数", MOD_ALT, ord("W")),
    GlobalHotkeySpec("kill_owner_units", "Alt+E  秒杀玩家的所有单位", MOD_ALT, ord("E")),
    GlobalHotkeySpec("xp_rate", "Alt+R  增加经验获取率", MOD_ALT, ord("R")),
    GlobalHotkeySpec("reset_ability", "Alt+T  重置技能", MOD_ALT, ord("T")),
    GlobalHotkeySpec("all_debuffs", "Alt+Y  获得 debuff", MOD_ALT, ord("Y")),
    GlobalHotkeySpec("all_buffs", "Alt+U  获得 buff", MOD_ALT, ord("U")),
    GlobalHotkeySpec("fullscreen_swarm", "Alt+I  全屏腐臭蜂群", MOD_ALT, ord("I")),
    GlobalHotkeySpec("fullscreen_clap", "Alt+O  全屏雷霆一击", MOD_ALT, ord("O")),
    GlobalHotkeySpec("fullscreen_monsoon", "Alt+P  全屏季风", MOD_ALT, ord("P")),
    GlobalHotkeySpec("fullscreen_starfall", "Alt+A  全屏群星陨落", MOD_ALT, ord("A")),
    GlobalHotkeySpec("fullscreen_forked", "Alt+S  全屏叉状闪电", MOD_ALT, ord("S")),
    GlobalHotkeySpec("fullscreen_auto", "Alt+D  全屏自动特效攻击", MOD_ALT, ord("D")),
    GlobalHotkeySpec("toggle_unit_pause", "Alt+F  暂停/恢复单位", MOD_ALT, ord("F")),
    GlobalHotkeySpec("toggle_game_pause", "Alt+G  暂停/恢复游戏", MOD_ALT, ord("G")),
    GlobalHotkeySpec("end_game", "Alt+H  结束游戏", MOD_ALT, ord("H")),
    GlobalHotkeySpec("remove_all_abilities", "Alt+J  技能全删", MOD_ALT, ord("J")),
    GlobalHotkeySpec("ally_health_lock", "Alt+K  我方锁血", MOD_ALT, ord("K")),
    GlobalHotkeySpec("allied_cooldowns", "Alt+C  重置我方全部技能冷却", MOD_ALT, ord("C")),
    GlobalHotkeySpec("rapid_build", "Alt+V  持续快速建造/升级", MOD_ALT, ord("V")),
    GlobalHotkeySpec("instant_victory", "Alt+B  直接胜利", MOD_ALT, ord("B")),
    GlobalHotkeySpec("game_speed", "Alt+N  加速/恢复游戏", MOD_ALT, ord("N")),
    GlobalHotkeySpec("stat_hp_regen", "Ctrl+Alt+F1  生命值恢复", MOD_CONTROL | MOD_ALT, VK_F1),
    GlobalHotkeySpec("stat_mp_regen", "Ctrl+Alt+F2  法力恢复", MOD_CONTROL | MOD_ALT, VK_F1 + 1),
    GlobalHotkeySpec("stat_attack_speed", "Ctrl+Alt+F3  实际攻速", MOD_CONTROL | MOD_ALT, VK_F1 + 2),
    GlobalHotkeySpec("stat_critical_chance", "Ctrl+Alt+F4  致命一击几率%", MOD_CONTROL | MOD_ALT, VK_F1 + 3),
    GlobalHotkeySpec("stat_critical_damage", "Ctrl+Alt+F5  暴击伤害%", MOD_CONTROL | MOD_ALT, VK_F1 + 4),
    GlobalHotkeySpec("stat_spell_critical_chance", "Ctrl+Alt+F6  法术暴击几率%", MOD_CONTROL | MOD_ALT, VK_F1 + 5),
    GlobalHotkeySpec("stat_spell_critical_damage", "Ctrl+Alt+F7  法术暴击伤害%", MOD_CONTROL | MOD_ALT, VK_F1 + 6),
    GlobalHotkeySpec("stat_ability_speed_flat", "Ctrl+Alt+F8  技能速度", MOD_CONTROL | MOD_ALT, VK_F1 + 7),
    GlobalHotkeySpec("stat_ability_speed_percent", "Ctrl+Alt+F9  技能速度%", MOD_CONTROL | MOD_ALT, VK_F1 + 8),
    GlobalHotkeySpec("stat_ability_amp_flat", "Ctrl+Alt+F10  技能增强", MOD_CONTROL | MOD_ALT, VK_F1 + 9),
    GlobalHotkeySpec("stat_ability_amp_percent", "Ctrl+Alt+F11  技能增强%", MOD_CONTROL | MOD_ALT, VK_F11),
    GlobalHotkeySpec("stat_lifesteal_percent", "Ctrl+Alt+F12  生命窃取%", MOD_CONTROL | MOD_ALT, VK_F12),
    GlobalHotkeySpec("stat_ability_vamp_flat", "Ctrl+Alt+1  技能汲取", MOD_CONTROL | MOD_ALT, ord("1")),
    GlobalHotkeySpec("stat_ability_vamp_percent", "Ctrl+Alt+2  技能汲取%", MOD_CONTROL | MOD_ALT, ord("2")),
    GlobalHotkeySpec("stat_resolve_flat", "Ctrl+Alt+3  斗志", MOD_CONTROL | MOD_ALT, ord("3")),
    GlobalHotkeySpec("stat_resolve_percent", "Ctrl+Alt+4  斗志%", MOD_CONTROL | MOD_ALT, ord("4")),
    GlobalHotkeySpec("stat_magic_resistance_percent", "Ctrl+Alt+5  魔法抗性%", MOD_CONTROL | MOD_ALT, ord("5")),
)

class MEMORY_BASIC_INFORMATION64(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_ulonglong),
        ("AllocationBase", ctypes.c_ulonglong),
        ("AllocationProtect", ctypes.c_ulong),
        ("__alignment1", ctypes.c_ulong),
        ("RegionSize", ctypes.c_ulonglong),
        ("State", ctypes.c_ulong),
        ("Protect", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
        ("__alignment2", ctypes.c_ulong),
    ]

































NATIVE_COMPONENT_FIELD_SPECS = {
    key: (index, component, kind) for index, (key, component, kind) in enumerate((
        ("armor", "unit", "f32"), ("armor_type", "unit", "i32"),
        ("skill_points", "hero", "i32"), ("strength_growth", "hero", "f32"),
        ("intelligence_growth", "hero", "f32"), ("agility_growth", "hero", "f32"),
        ("xp", "hero", "i32"), ("base_strength", "hero", "i32"),
        ("base_agility", "hero", "i32"), ("move_speed", "move", "f32"),
    ))
}
CURRENT_ENGINE_UNIT_STAT_FIELDS = frozenset(("armor", "armor_type", "intelligence_total"))
for _attack_number in (1, 2):
    for _index, _name in enumerate(("multiplier", "multiplier_cache", "dice", "base1", "base2",
            "dice_cache", "internal_bonus1", "internal_bonus2", "sound", "type", "max_targets",
            "interval", "first_delay", "acquire_range", "projectile_speed", "range", "range_buffer")):
        NATIVE_COMPONENT_FIELD_SPECS[f"attack{_attack_number}_{_name}"] = (
            (16 if _attack_number == 1 else 48) + _index, "attack", "f32" if _index >= 11 else "i32")
for _index in range(5):
    NATIVE_COMPONENT_FIELD_SPECS[f"skill{_index+1}_learnable"] = (80+_index, "hero", "i32")
    NATIVE_COMPONENT_FIELD_SPECS[f"skill{_index+1}_requirement"] = (85+_index, "hero", "i32")


class NativeUnitFieldMemory:
    """One game-thread field response; missing bytes never trigger process reads."""

    def __init__(self, candidate: UnitCandidate, values: tuple[int, ...]):
        from war3_game_profile import current_profile
        current_profile().adapter.units.populate_field_snapshot(self, candidate, values)

    def read(self, address: int, size: int) -> bytes:
        for start, data in self._blocks.items():
            offset = address - start
            if 0 <= offset and 0 <= size <= len(data) - offset:
                return data[offset:offset + size]
        raise OSError("字段不在本次 DLL 快照中")

    def read_f32(self, address: int) -> float:
        return struct.unpack("<f", self.read(address, 4))[0]

    def read_i32(self, address: int) -> int:
        return struct.unpack("<i", self.read(address, 4))[0]

    def read_u32(self, address: int) -> int:
        return struct.unpack("<I", self.read(address, 4))[0]

    def read_u64(self, address: int) -> int:
        return struct.unpack("<Q", self.read(address, 8))[0]


























OCR_TEMPLATE_WIDTH = 24
OCR_TEMPLATE_HEIGHT = 28
OCR_TEMPLATE_BYTES = OCR_TEMPLATE_WIDTH * OCR_TEMPLATE_HEIGHT // 8
OCR_TEMPLATE_CHARS = "125/250055253635277308822234469999999"
OCR_TEMPLATE_DATA_B64 = (
    "AAAAAAAAAAIAAAcAAB8AAD8AAD8AAf8AAf8AAecAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcAAAcA"
    "AAcAAAAAAAAAAAAAAAAAADwAAf/AA//gB+fgB+fgB4HwD4BwDgBwDgBwAAHwAAPgAAfgAAfgAB/AAH4AAfwAA/AAB8AAB4AAB4AA"
    "B4AAD//wD//wD//wAAAAAAAAAAAAAAAAB//gB//gB//AB//ABwAADwAADwAADzwAD/8AD/8AD//AD8fgHwHgAAHwAADwAADwAADw"
    "HgDwHgHwHwPgD//gD//gD//AAf8AAAAAAAAAAAAAAAAAAAIAAAcAAAYAAB4AAB4AAB4AAB4AABwAADwAADwAADwAADgAADgAAHgA"
    "AHgAAHgAAGAAAOAAAOAAAOAAAOAAAcAAAcAAAcAAAAAAAAAAAAAAAAAAADwAAf/AA//gB+fgB+fgB4HwD4BwDgBwDgBwAAHwAAPg"
    "AAfgAAfgAB/AAD4AAfwAA/AAB8AAB4AAB4AAB4AAD//wD//wD//wAAAAAAAAAAAAAAAAADAAA//gA//gA//AA//AA4AAB4AAB4AA"
    "B5gAB/+AB//AB+fgB+fgD4HgAAHwAABwAABwDgBwDgHwD4PgD4PgB//gB//AAf+AAAAAAAAAAAAAAAAAADwAAf+AA//AB+fgB+fg"
    "B8PgB4HgDgBwDgBwDgBwDgBwDgBwDgBwDgBwDgBwDgBwDgBwDgHwB4HgB8PgB8PgA//gA//AAf+AAAAAAAAAAAAAAAAAABgAABAA"
    "AfAAB/AAD/gAHzwAHjwAHDwAOG4AOG4AOG4AOG4AOO4cOE48OE58OE74PE7wHEzgHpzAD/yAD/gAB/MAA4MAA/GAAAAAAAAAAAAA"
    "AAAAB//gB//gB//AB//ABwAADwAADwAADzgAD/8AD/8AD//AD8fgHwHgAAHwAADwAADwAADwHgDwHgHwHwPgD//gD//gD//AB/8A"
    "AAAAAAAAAAAAAAAAB//gB//gB//AB//ABwAADwAADwAADzgAD/8AD/8AD//AD8fgHwHgAAHwAADwAADwAADwHgDwHgHwHwPgD//g"
    "D//gD//AAf8AAAAAAAAAAAAAAAAAADwAAf/AA//gB+fgB+fgB4HwD4BwDgBwDgBwAAHwAAPgAAfgAAfgAB/AAD4AAfwAA/AAB+AA"
    "B4AAB4AAB4AAD//wD//wD//wAAAAAAAAAAAAAAAAABgAA//gA//gA//AA//AA4AAB4AAB4AAB5gAB/+AB//AB+fgB+fgD4HgAAHw"
    "AABwAABwDgBwDgHwD4PgD4PgB//gB//AAf+AAAAAAAAAAAAAAAAAADwAA/+AA//AB+fgB+fgB4HgD4HgDgHgAAHgAA/gAD/AAD/g"
    "AD/gAD/gAAHwAABwDgBwDgBwDgBwD4HwD4HwB//gA//AAf+AAAAAAAAAAAAAAAAAADwAAf+AA//AB+fgB+fgB8HgB4HgDgAADgAA"
    "D/+AD//AD//gD//gD4PgD4HgDgHwDgBwDgHgD4HgB8PgB8PgB//AA//AAf+AAAAAAAAAAAAAAAAAADwAA/+AA//AB+fgB+fgB4Hg"
    "D4HgDgHgAAHgAA/gAD/AAD/gAD/gAD/gAAHwAABwDgBwDgBwDgBwD4HwD4HwB//gB//AAf+AAAAAAAAAAAAAAAAAAA4AAAwAABwA"
    "D/wAD/wAD/gAHBgAHDAAHfAAH/gAH/gAHnwAPDwMAD4cAC48AC58OC54PfzgH/zAH/mAB/GAAA+AAfxAAAAAAAAAAAAAAAAAAAAA"
    "ADwAAP/AA//gB+fgB+fgB4HwD4BwDwBwDwBwAAHwAAPgAAfgAAfgAB/AAD4AAPwAA/AAB8AAB4AAB4AAB4AAD//wH//wD//wAAAA"
    "AAAAAAAAAAAAH//wH//wH//wH//wAAHgAAPgAAfAAAcAAA8AAA8AAA4AADwAADwAAHgAAHgAAHgAAHgAAPAAAPAAAPAAAPAAAPAA"
    "AcAAAcAAAAAAAAAAAAAAAAAAH//wH//wH//wH//wAAHgAAPgAAfAAA8AAA8AAA8AAA4AADwAADwAAHgAAHgAAHgAAHgAAPAAAPAA"
    "APAAAPAAAPAAAcAAAcAAAAAAAAAAAAAAAAAAAAeAAH/gAP/wAPz4AOA4AeA4AcA4AAA4AAH4AAfwAAf4AAf4AAf4AAA8AAAcAcAc"
    "AcAcAcAcAeA8AP/4AH/wAD/gH+AAP/gAAAAAAAAAAAAAAAAAADwAAf+AA//AB+fgB+fgB8PgB4HgDgBwDgBwDgBwDgBwDgBwDgBw"
    "DgBwDgBwDgBwDgBwDgBwB4HgB8PgB8PgA//gA//AAf+AAAAAAAAAAAAAAAAAADwAAf+AA//AB+fgB+fgB4HgB4HgB4HgB4HgB+fg"
    "A//AA//AA//AB//gD4HgDgBwDgBwDgBwDgBwD4HwD4HwB//gB//AAf+AAAAAAAAAAAAAAAAAADwAAf+AA//AB+fgB+fgB4HgB4Hg"
    "B4HgB4HgB+fgA//AA//AA//AB//gD4HgDgHwDgBwDgBwDgBwD4HwD4HwB//gB//AAf+AAAAAAAAAAAAAAAAAADwAAf/AA//gB+fg"
    "B+fgB4HwD4BwDgBwDgBwAAHwAAPgAAfgAAfgAB/AAD+AAfwAA/AAB+AAB4AAB4AAB4AAD//wD//wD//wAAAAAAAAAAAAAAAAADwA"
    "Af/AA//gB+fgB+fgB4HwD4BwDgBwDgBwAAHwAAPgAAfgAAfgAB/AAH+AAfwAA/AAB+AAB4AAB4AAB4AAD//wD//wD//wAAAAAAAA"
    "AAAAAAAAAAAAAA4AAAwAAcwAB/wAD/wAHB4APB4AOD4AOD4AAD4AAHwAAPwAAfgMAfAcB8A8DwB8HCHwHcHgP//AP/8AP/4AAAAA"
    "AAAAAAAAAAAAAAAAAAAAADwAAf+AA//AB+fgB+fgB4HgD4HgDgHgAAHgAA/gAD/AAD/gAD/gAD/gAAHwAABwDgBwDgBwDgBwD4Hw"
    "D4HwB//gA//AAf+AAAAAAAAAAAAAAAAAAAMAAAfAAA/AAB/AAB/AAB/AAD/AAHvAAfPAAePAA8PAB8PAB8PAD4PADgPAH//wH//4"
    "H//4AAfAAAPAAAPAAAPAAAPAAAPAAAAAAAAAAAAAAAAAAAMAAAfAAA/AAB/AAB/AAB/AAD/AAHvAAfPAA+PAA8PAB8PAB8PAD4PA"
    "DgPAH//wH//4H//4AAfAAAPAAAPAAAPAAAPAAAPAAAAAAAAAAAAAAAAAAAeAAB/gAD/wAHz4AHg4AHA4AOAAAOAAAP/gAP/wAP/4"
    "APB4APA4AOA8AOAcAOA4APA4AHh4AH/wAD/wAB/gH+AAP/AAAAAAAAAAAAAAAAAAAAAAAHgAA/8AB/+AB4eADwPADgHADgHADgDA"
    "DgDgDgHgDgHgDwPgB//gA//gAf/gAAHgAAHADgPADgPADwPAB/+AB/8AA/4AAEAAAAAAAAAAAAAAAAAAADgAA/+AB//AB8fAB8fA"
    "D4PgDgHgDgBgDgHwDgHwDgHwD4PwD4PwB//wA//wAf/wAAHwAAHgDgPgD4PgD4PgB//AB/+AA/4AAAAAAAAAAAAAAAAAADgAA/+A"
    "B//AB8fAB8fAD4PgDgHgDgBgDgBwDgHwDgHwD4PwD4PwB//wA//wAf/wAAHwAAHgDgPgD4PgD4PgB//AB/+AAf4AAAAAAAAAAAAA"
    "AAAAADgAA/+AB//AB8fgB8fgD4PgDgHgDgHgDgBwDgHwDgHwD4PwD4PwB//wA//wAf/wAAHwAAHgDgPgD4PgD4PgB//AB/+AA/4A"
    "AAAAAAAAAAAAAAAAADwAA/+AB//AB8fgB8fgD4PgDgHgDgHgDgBwDgHwDgHwD4PwD4PwB//wA//wAf/wAAHwAAHgDgPgD4PgD4Pg"
    "B//AB/+AAf4AAAAAAAAAAAAAAAAAADwAA/+AB//AB8fgB8fgD4PgDgHgDgHgDgBwDgHwDgHwD4PwD4PwB//wA//wAf/wAAHwAAHg"
    "DgPgD4PgD4PgB//AB/+AA/4AAAAAAAAAAAAAAAAAAA4AAAwAAcwAD/wAH/gAHnwAOBwAODwAOD4AOD4AOD4APH4AH/4MD/4cB/48"
    "AB58ADz4PfzgH/nAH/GAB+OAAA+AAfxAAAAAAAAAAAAA"
)


def _make_dpi_aware() -> None:
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def capture_physical_screen_image() -> Image.Image:
    raise RuntimeError("OCR/截图读取已禁用；当前选中目标只允许从内存 selected-handle 读取")


def _is_green_digit(rgb: tuple[int, int, int]) -> bool:
    r, g, b = rgb
    return g > 130 and g * 4 > r * 5 and g * 4 > b * 5


def _is_bright_digit(rgb: tuple[int, int, int]) -> bool:
    if _is_green_digit(rgb):
        return False
    r, g, b = rgb
    return max(r, g, b) > 125 and min(r, g, b) > 55


def _make_mask(
    image: Image.Image,
    box: tuple[int, int, int, int],
    predicate: Callable[[tuple[int, int, int]], bool],
) -> list[bytearray]:
    x0, y0, x1, y1 = box
    pix = image.load()
    return [
        bytearray(1 if predicate(pix[x, y]) else 0 for x in range(x0, x1))
        for y in range(y0, y1)
    ]


def _connected_components(mask: list[bytearray]) -> list[tuple[int, int, int, int, int]]:
    height = len(mask)
    width = len(mask[0]) if height else 0
    seen = [bytearray(width) for _ in range(height)]
    out: list[tuple[int, int, int, int, int]] = []
    for y in range(height):
        for x in range(width):
            if not mask[y][x] or seen[y][x]:
                continue
            stack = [(x, y)]
            seen[y][x] = 1
            min_x = max_x = x
            min_y = max_y = y
            area = 0
            while stack:
                cx, cy = stack.pop()
                area += 1
                min_x = min(min_x, cx)
                max_x = max(max_x, cx)
                min_y = min(min_y, cy)
                max_y = max(max_y, cy)
                for ny in range(max(0, cy - 1), min(height, cy + 2)):
                    for nx in range(max(0, cx - 1), min(width, cx + 2)):
                        if mask[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = 1
                            stack.append((nx, ny))
            out.append((min_x, min_y, max_x + 1, max_y + 1, area))
    return out


def _merge_fragment_boxes(
    boxes: list[tuple[int, int, int, int, int]],
) -> list[tuple[int, int, int, int, int]]:
    out: list[tuple[int, int, int, int, int]] = []
    for box in sorted(boxes, key=lambda item: (item[0], item[1])):
        bx0, by0, bx1, by1, b_area = box
        merged = False
        for idx, other in enumerate(out):
            ox0, oy0, ox1, oy1, o_area = other
            overlap = min(ox1, bx1) - max(ox0, bx0)
            gap = max(ox0, bx0) - min(ox1, bx1)
            v_overlap = min(oy1, by1) - max(oy0, by0)
            small_piece = min(o_area, b_area) < 45
            y_close = abs(((oy0 + oy1) / 2) - ((by0 + by1) / 2)) < 12
            if (overlap >= 2 or (gap <= 1 and small_piece and v_overlap >= 2)) and y_close:
                out[idx] = (
                    min(ox0, bx0),
                    min(oy0, by0),
                    max(ox1, bx1),
                    max(oy1, by1),
                    o_area + b_area,
                )
                merged = True
                break
        if not merged:
            out.append(box)
    return sorted(out, key=lambda item: item[0])


def _select_text_row(
    boxes: list[tuple[int, int, int, int, int]],
) -> list[tuple[int, int, int, int, int]]:
    groups: list[list[object]] = []
    for box in sorted(boxes, key=lambda item: item[1]):
        cy = (box[1] + box[3]) / 2
        for group in groups:
            if abs(cy - float(group[0])) < 8:
                members = group[1]
                assert isinstance(members, list)
                members.append(box)
                group[0] = (float(group[0]) * (len(members) - 1) + cy) / len(members)
                break
        else:
            groups.append([cy, [box]])
    candidates = [group[1] for group in groups if 5 <= len(group[1]) <= 12]
    if not candidates:
        raise RuntimeError("无法在底部面板找到生命/魔法数字")
    return sorted(
        max(
            candidates,
            key=lambda members: (
                len(members),
                sum(box[4] for box in members),
                sum((box[1] + box[3]) / 2 for box in members) / len(members),
            ),
        ),
        key=lambda item: item[0],
    )


def _extract_hp_mp_boxes(
    image: Image.Image,
) -> tuple[list[tuple[int, int, int, int, int]], list[tuple[int, int, int, int, int]]]:
    width, height = image.size
    x0, x1 = int(width * 0.25), int(width * 0.45)
    y0, y1 = int(height * 0.82), height
    green_mask = _make_mask(image, (x0, y0, x1, y1), _is_green_digit)
    green_boxes = []
    for bx0, by0, bx1, by1, area in _connected_components(green_mask):
        bw = bx1 - bx0
        bh = by1 - by0
        if area >= 30 and 8 <= bh <= 32 and 4 <= bw <= 30:
            green_boxes.append((bx0 + x0, by0 + y0, bx1 + x0, by1 + y0, area))
    hp_boxes = _select_text_row(green_boxes)

    mx0 = max(0, min(box[0] for box in hp_boxes) - 10)
    mx1 = min(width, max(box[2] for box in hp_boxes) + 8)
    my0 = min(box[1] for box in hp_boxes) + 31
    my1 = min(height, my0 + 25)
    bright_mask = _make_mask(image, (mx0, my0, mx1, my1), _is_bright_digit)
    mp_boxes = []
    for bx0, by0, bx1, by1, area in _connected_components(bright_mask):
        bw = bx1 - bx0
        bh = by1 - by0
        if area >= 20 and 6 <= bh <= 25 and 3 <= bw <= 34:
            mp_boxes.append((bx0 + mx0, by0 + my0, bx1 + mx0, by1 + my0, area))
    mp_boxes = [
        box
        for box in _merge_fragment_boxes(mp_boxes)
        if box[4] >= 25 and 6 <= box[3] - box[1] <= 28 and 3 <= box[2] - box[0] <= 34
    ]
    if len(mp_boxes) < 5:
        raise RuntimeError("无法在底部面板找到魔法数字")
    return hp_boxes, mp_boxes


def _extract_hp_boxes(image: Image.Image) -> list[tuple[int, int, int, int, int]]:
    width, height = image.size
    x0, x1 = int(width * 0.25), int(width * 0.45)
    y0, y1 = int(height * 0.82), height
    green_mask = _make_mask(image, (x0, y0, x1, y1), _is_green_digit)
    green_boxes = []
    for bx0, by0, bx1, by1, area in _connected_components(green_mask):
        bw = bx1 - bx0
        bh = by1 - by0
        if area >= 30 and 8 <= bh <= 32 and 4 <= bw <= 30:
            green_boxes.append((bx0 + x0, by0 + y0, bx1 + x0, by1 + y0, area))
    return _select_text_row(green_boxes)


def _normalize_glyph(
    image: Image.Image,
    box: tuple[int, int, int, int, int],
    predicate: Callable[[tuple[int, int, int]], bool],
) -> bytes:
    x0, y0, x1, y1, _area = box
    pix = image.load()
    source_width = max(1, x1 - x0)
    source_height = max(1, y1 - y0)
    raw = bytearray()
    for y in range(y0, y1):
        for x in range(x0, x1):
            raw.append(255 if predicate(pix[x, y]) else 0)
    glyph = Image.frombytes("L", (source_width, source_height), bytes(raw))
    scale = min((OCR_TEMPLATE_HEIGHT - 4) / source_height, (OCR_TEMPLATE_WIDTH - 4) / source_width)
    scaled_width = max(1, round(source_width * scale))
    scaled_height = max(1, round(source_height * scale))
    glyph = glyph.resize((scaled_width, scaled_height), Image.Resampling.NEAREST).convert("1")
    canvas = Image.new("1", (OCR_TEMPLATE_WIDTH, OCR_TEMPLATE_HEIGHT), 0)
    canvas.paste(glyph, ((OCR_TEMPLATE_WIDTH - scaled_width) // 2, (OCR_TEMPLATE_HEIGHT - scaled_height) // 2))
    bits = bytearray()
    canvas_bytes = bytes(1 if value else 0 for value in canvas.getdata())
    for offset in range(0, len(canvas_bytes), 8):
        byte = 0
        for bit in canvas_bytes[offset : offset + 8]:
            byte = (byte << 1) | bit
        bits.append(byte)
    return bytes(bits)


_OCR_TEMPLATES: list[tuple[str, bytes]] | None = None


def _ocr_templates() -> list[tuple[str, bytes]]:
    raise RuntimeError("OCR 模板已禁用；当前选中目标只允许从内存 selected-handle 读取")


def _bit_distance(left: bytes, right: bytes) -> float:
    diff = sum((a ^ b).bit_count() for a, b in zip(left, right))
    return diff / (OCR_TEMPLATE_WIDTH * OCR_TEMPLATE_HEIGHT)


def _classify_glyph(glyph: bytes) -> tuple[str, float]:
    score, char = min((_bit_distance(glyph, template), char) for char, template in _ocr_templates())
    return char, score


def _valid_bar_text(text: str) -> bool:
    if text.count("/") != 1:
        return False
    left, right = text.split("/", 1)
    return (
        1 <= len(left) <= 5
        and 1 <= len(right) <= 5
        and left.isdigit()
        and right.isdigit()
    )


def _best_bar_text(chars: list[tuple[str, float]]) -> str:
    best: tuple[float, str] | None = None
    count = len(chars)
    for drop_mask in range(1 << count):
        if drop_mask.bit_count() > 2:
            continue
        kept = [chars[idx] for idx in range(count) if not ((drop_mask >> idx) & 1)]
        text = "".join(char for char, _score in kept)
        if not _valid_bar_text(text):
            continue
        worst = max((score for _char, score in kept), default=9.0)
        if worst > 0.18:
            continue
        dropped_penalty = sum(chars[idx][1] for idx in range(count) if (drop_mask >> idx) & 1)
        total = worst + dropped_penalty + 0.05 * drop_mask.bit_count()
        if best is None or total < best[0]:
            best = (total, text)
    if best is None:
        raw = "".join(char for char, _score in chars)
        raise RuntimeError(f"OCR 无法稳定识别数值：{raw}")
    return best[1]


def _parse_bar_text(text: str) -> tuple[int, int]:
    left, right = text.split("/", 1)
    return int(left), int(right)


def read_selected_panel_from_image(image: Image.Image) -> VisibleUnitPanel:
    image = image.convert("RGB")
    hp_boxes, mp_boxes = _extract_hp_mp_boxes(image)
    hp_chars = [
        _classify_glyph(_normalize_glyph(image, box, _is_green_digit))
        for box in hp_boxes
    ]
    mp_chars = [
        _classify_glyph(_normalize_glyph(image, box, _is_bright_digit))
        for box in mp_boxes
    ]
    hp_text = _best_bar_text(hp_chars)
    mp_text = _best_bar_text(mp_chars)
    current_hp, max_hp = _parse_bar_text(hp_text)
    current_mp, max_mp = _parse_bar_text(mp_text)
    return VisibleUnitPanel(current_hp, max_hp, current_mp, max_mp, hp_text, mp_text)


def read_selected_panel_loose_from_image(image: Image.Image) -> VisibleUnitPanel:
    image = image.convert("RGB")
    hp_boxes = _extract_hp_boxes(image)
    hp_chars = [
        _classify_glyph(_normalize_glyph(image, box, _is_green_digit))
        for box in hp_boxes
    ]
    hp_text = _best_bar_text(hp_chars)
    current_hp, max_hp = _parse_bar_text(hp_text)
    try:
        _hp_boxes, mp_boxes = _extract_hp_mp_boxes(image)
        mp_chars = [
            _classify_glyph(_normalize_glyph(image, box, _is_bright_digit))
            for box in mp_boxes
        ]
        mp_text = _best_bar_text(mp_chars)
        current_mp, max_mp = _parse_bar_text(mp_text)
    except Exception:
        current_mp, max_mp, mp_text = -1, -1, ""
    return VisibleUnitPanel(current_hp, max_hp, current_mp, max_mp, hp_text, mp_text)


class ProcessMemory:
    def __init__(self, pid: int, write: bool = False):
        self.pid = int(pid)
        access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        if write:
            access |= PROCESS_VM_WRITE | PROCESS_VM_OPERATION
        self.handle = kernel32.OpenProcess(access, False, pid)
        error = ctypes.get_last_error() if not self.handle else 0
        if not self.handle and error == ERROR_ACCESS_DENIED:
            try:
                debug_enabled = enable_debug_privilege()
            except OSError:
                debug_enabled = False
            if debug_enabled:
                ctypes.set_last_error(0)
                self.handle = kernel32.OpenProcess(access, False, pid)
                error = ctypes.get_last_error() if not self.handle else 0
        if not self.handle:
            raise ctypes.WinError(error)
        from war3_game_session import verify_opened_process
        try:verify_opened_process(self)
        except Exception:
            kernel32.CloseHandle(self.handle);self.handle=None
            raise
        self._regions_cache: list[Region] | None = None

    def close(self) -> None:
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self) -> "ProcessMemory":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def regions(self, force_refresh: bool = False) -> list[Region]:
        if self._regions_cache is not None and not force_refresh:
            return list(self._regions_cache)
        mbi = MEMORY_BASIC_INFORMATION64()
        addr = 0
        out: list[Region] = []
        max_addr = 0x7FFFFFFFFFFF
        while addr < max_addr:
            res = kernel32.VirtualQueryEx(
                self.handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)
            )
            if not res:
                break
            protect = int(mbi.Protect)
            prot_low = protect & 0xFF
            if (
                mbi.State == MEM_COMMIT
                and not (protect & (PAGE_NOACCESS | PAGE_GUARD))
                and prot_low in READABLE_PROTECTS
            ):
                out.append(Region(int(mbi.BaseAddress), int(mbi.RegionSize), protect, int(mbi.Type)))
            addr = int(mbi.BaseAddress) + int(mbi.RegionSize)
        self._regions_cache = out
        return list(out)

    def read(self, address: int, size: int) -> bytes:
        if size < 0:
            raise ValueError("read size must be non-negative")
        if size == 0:
            return b""
        # 3.0 frequently places adjacent objects at a readable-region edge.
        # ReadProcessMemory may return ERROR_PARTIAL_COPY for a request that
        # crosses that edge even when every requested field is valid. Split at
        # page boundaries and preserve the exact-read contract for callers.
        result = bytearray()
        current = int(address)
        remaining = int(size)
        while remaining:
            chunk_size = min(remaining, 0x1000 - (current & 0xFFF))
            buf = ctypes.create_string_buffer(chunk_size)
            got = ctypes.c_size_t()
            ok = kernel32.ReadProcessMemory(
                self.handle, ctypes.c_void_p(current), buf, chunk_size, ctypes.byref(got)
            )
            if got.value:
                result.extend(buf.raw[: got.value])
                current += got.value
                remaining -= got.value
            if not ok and got.value == 0:
                raise ctypes.WinError(ctypes.get_last_error())
            if got.value != chunk_size:
                raise ctypes.WinError(ctypes.get_last_error() or ERROR_PARTIAL_COPY)
        return bytes(result)

    def read_i32(self, address: int) -> int:
        return struct.unpack("<i", self.read(address, 4))[0]

    def read_u32(self, address: int) -> int:
        return struct.unpack("<I", self.read(address, 4))[0]

    def read_f32(self, address: int) -> float:
        return struct.unpack("<f", self.read(address, 4))[0]

    def read_u64(self, address: int) -> int:
        return struct.unpack("<Q", self.read(address, 8))[0]

    def write_f32(self, address: int, value: float) -> None:
        data = struct.pack("<f", float(value))
        written = ctypes.c_size_t()
        ok = kernel32.WriteProcessMemory(
            self.handle, ctypes.c_void_p(address), data, len(data), ctypes.byref(written)
        )
        if not ok or written.value != len(data):
            raise ctypes.WinError(ctypes.get_last_error())

    def write_i32(self, address: int, value: int) -> None:
        data = struct.pack("<i", int(value))
        written = ctypes.c_size_t()
        ok = kernel32.WriteProcessMemory(
            self.handle, ctypes.c_void_p(address), data, len(data), ctypes.byref(written)
        )
        if not ok or written.value != len(data):
            raise ctypes.WinError(ctypes.get_last_error())

    def write_u32(self, address: int, value: int) -> None:
        data = struct.pack("<I", int(value))
        written = ctypes.c_size_t()
        ok = kernel32.WriteProcessMemory(
            self.handle, ctypes.c_void_p(address), data, len(data), ctypes.byref(written)
        )
        if not ok or written.value != len(data):
            raise ctypes.WinError(ctypes.get_last_error())

    def write_u64(self, address: int, value: int) -> None:
        data = struct.pack("<Q", int(value) & 0xFFFFFFFFFFFFFFFF)
        written = ctypes.c_size_t()
        ok = kernel32.WriteProcessMemory(
            self.handle, ctypes.c_void_p(address), data, len(data), ctypes.byref(written)
        )
        if not ok or written.value != len(data):
            raise ctypes.WinError(ctypes.get_last_error())

    def write_bytes(self, address: int, data: bytes) -> None:
        written = ctypes.c_size_t()
        ok = kernel32.WriteProcessMemory(
            self.handle, ctypes.c_void_p(address), data, len(data), ctypes.byref(written)
        )
        if not ok or written.value != len(data):
            raise ctypes.WinError(ctypes.get_last_error())

    def scan_bytes(self, pattern: bytes, max_region_size: int = 256 * 1024 * 1024) -> list[tuple[int, int, int]]:
        hits: list[tuple[int, int, int]] = []
        tail_len = max(0, len(pattern) - 1)
        for region in self.regions():
            if region.size > max_region_size:
                continue
            offset = 0
            tail = b""
            while offset < region.size:
                size = min(4 * 1024 * 1024, region.size - offset)
                try:
                    data = tail + self.read(region.base + offset, size)
                except OSError:
                    offset += size
                    tail = b""
                    continue
                start = 0
                while True:
                    idx = data.find(pattern, start)
                    if idx < 0:
                        break
                    address = region.base + offset - len(tail) + idx
                    if address >= region.base:
                        hits.append((address, region.protect, region.typ))
                    start = idx + 1
                tail = data[-tail_len:] if tail_len else b""
                offset += size
        return hits

    def scan_bytes_private(
        self,
        pattern: bytes,
        max_region_size: int | None = 64 * 1024 * 1024,
    ) -> list[int]:
        hits: list[int] = []
        tail_len = max(0, len(pattern) - 1)
        for region in self.regions():
            if (
                region.typ != MEM_PRIVATE
                or (max_region_size is not None and region.size > max_region_size)
            ):
                continue
            offset = 0
            tail = b""
            while offset < region.size:
                size = min(4 * 1024 * 1024, region.size - offset)
                try:
                    data = tail + self.read(region.base + offset, size)
                except OSError:
                    offset += size
                    tail = b""
                    continue
                start = 0
                while True:
                    idx = data.find(pattern, start)
                    if idx < 0:
                        break
                    address = region.base + offset - len(tail) + idx
                    if address >= region.base:
                        hits.append(address)
                    start = idx + 1
                tail = data[-tail_len:] if tail_len else b""
                offset += size
        return hits

    def scan_bytes_private_parallel(
        self,
        pattern: bytes,
        max_region_size: int | None = 64 * 1024 * 1024,
        *,
        max_workers: int | None = None,
    ) -> list[int]:
        """Scan independent private regions without serializing every RPM call."""
        eligible = tuple(
            region
            for region in self.regions()
            if region.typ == MEM_PRIVATE
            and (max_region_size is None or region.size <= max_region_size)
        )
        if not eligible:
            return []

        def scan_region(region: Region) -> list[int]:
            try:
                data = self.read(region.base, region.size)
            except OSError:
                return []
            hits: list[int] = []
            start = 0
            while True:
                index = data.find(pattern, start)
                if index < 0:
                    return hits
                hits.append(region.base + index)
                start = index + 1

        workers = max_workers or min(
            16,
            max(4, (os.cpu_count() or 4)),
        )
        with ThreadPoolExecutor(
            max_workers=min(workers, len(eligible)),
            thread_name_prefix="war3-private-scan",
        ) as executor:
            batches = executor.map(scan_region, eligible)
            return [
                address
                for batch in batches
                for address in batch
            ]

    def scan_bytes_private_many(
        self,
        patterns: Iterable[bytes],
        max_region_size: int | None = 64 * 1024 * 1024,
    ) -> dict[bytes, list[int]]:
        return self.scan_bytes_many(
            patterns,
            region_types=(MEM_PRIVATE,),
            max_region_size=max_region_size,
        )

    def scan_bytes_many(
        self,
        patterns: Iterable[bytes],
        *,
        region_types: tuple[int, ...],
        max_region_size: int | None = 64 * 1024 * 1024,
    ) -> dict[bytes, list[int]]:
        unique_patterns = tuple(dict.fromkeys(patterns))
        hits = {pattern: [] for pattern in unique_patterns}
        if not unique_patterns:
            return hits
        tail_len = max(len(pattern) for pattern in unique_patterns) - 1
        for region in self.regions():
            if (
                region.typ not in region_types
                or (max_region_size is not None and region.size > max_region_size)
            ):
                continue
            offset = 0
            tail = b""
            while offset < region.size:
                size = min(4 * 1024 * 1024, region.size - offset)
                try:
                    data = tail + self.read(region.base + offset, size)
                except OSError:
                    offset += size
                    tail = b""
                    continue
                block_base = region.base + offset - len(tail)
                for pattern in unique_patterns:
                    start = 0
                    while True:
                        index = data.find(pattern, start)
                        if index < 0:
                            break
                        address = block_base + index
                        if address >= region.base:
                            hits[pattern].append(address)
                        start = index + 1
                tail = data[-tail_len:] if tail_len else b""
                offset += size
        return hits

    def scan_i32(self, value: int) -> list[tuple[int, int, int]]:
        return self.scan_bytes(struct.pack("<i", int(value)))

    def scan_f32(self, value: float) -> list[tuple[int, int, int]]:
        return self.scan_bytes(struct.pack("<f", float(value)))


def _process_session_id(pid: int) -> int | None:
    if not pid:
        return None
    session = ctypes.c_ulong()
    ctypes.set_last_error(0)
    if not kernel32.ProcessIdToSessionId(int(pid), ctypes.byref(session)):
        return None
    return int(session.value)


def _process_runtime_diagnostics(pid: int | None) -> dict[str, object]:
    target_pid = int(pid) if pid else None
    result: dict[str, object] = {"pid": target_pid}
    if target_pid is None:
        return result
    result["session_id"] = _process_session_id(target_pid)
    try:
        result["executable"] = process_executable_path(target_pid)
    except Exception as exc:
        result["executable_error"] = repr(exc)
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, target_pid)
    if not handle:
        result["open_process_error"] = ctypes.get_last_error()
        return result
    try:
        result.update(_token_runtime_diagnostics(handle))
    finally:
        kernel32.CloseHandle(handle)
    return result


def _window_runtime_diagnostics(hwnd: int) -> dict[str, object]:
    hwnd = int(hwnd or 0)
    if not hwnd:
        return {"hwnd": "0x0"}
    owner = ctypes.c_ulong()
    thread_id = int(
        user32.GetWindowThreadProcessId(
            ctypes.c_void_p(hwnd),
            ctypes.byref(owner),
        )
    )
    return {
        "hwnd": hex(hwnd),
        "title": _window_text(hwnd),
        "visible": bool(user32.IsWindowVisible(ctypes.c_void_p(hwnd))),
        "pid": int(owner.value),
        "thread_id": thread_id,
    }


def diagnostic_target_identity(
    game_pid: int | None,
    windows=None,
    *,
    requested_pid: int | None = None,
    target_hwnd: int = 0,
) -> dict[str, object]:
    """Keep launch intent separate from the current target and observed windows."""
    requested = int(requested_pid) if requested_pid else None
    if requested is None:
        for index, arg in enumerate(sys.argv[1:], 1):
            value = arg.partition("=")[2] if arg.startswith("--pid=") else (
                sys.argv[index + 1] if arg == "--pid" and index + 1 < len(sys.argv) else None
            )
            if value is not None:
                try:
                    requested = int(value)
                except (TypeError, ValueError):
                    pass
    target = int(game_pid) if game_pid else None
    result = dict(
        requested_game_pid=requested,
        game_pid=target,
        target_game_pid=target,
        actual_target_pid=target,
        target_pid=target,
        target_window_pid=None,
        window_pid=None,
        target_window_hwnd=None,
        target_windows=[],
    )
    try:
        rows = enum_war3_windows() if windows is None else windows
        matches = [
            dict(hwnd=hex(int(hwnd)), pid=int(pid))
            for hwnd, pid, _title in rows
            if target is None or int(pid) == target
        ]
        result["target_windows"] = matches
        if len(matches) == 1:
            result.update(target_window_pid=matches[0]["pid"],
                          window_pid=matches[0]["pid"],
                          target_window_hwnd=matches[0]["hwnd"])
        if target_hwnd:
            observed = _window_runtime_diagnostics(target_hwnd)
            if observed.get("pid") and (target is None or observed["pid"] == target):
                result.update(
                    target_window_pid=observed["pid"],
                    window_pid=observed["pid"],
                    target_window_hwnd=observed["hwnd"],
                )
    except Exception as exc:
        result["target_window_lookup_error"] = repr(exc)
    return result


def diagnostic_game_build(pid: int | None) -> dict:
    """Report the loaded PE identity, never the trainer's historical default."""
    result = {'game_build': None, 'game_fingerprint': None, 'adapter_id': None,
              'adapter_version': None, 'bridge_protocol': '0x2426801c'}
    if not pid:
        return result
    try:
        from war3_object_registry import _enumerate_process_modules
        from war3_game_session import read_fingerprint
        from war3_game_profile import ProfileCatalog
        executable = process_executable_path(int(pid))
        with ProcessMemory(int(pid)) as memory:
            modules = [row for row in _enumerate_process_modules(memory)
                       if str(row[1]).casefold() == Path(executable).name.casefold()]
            if len(modules) != 1:
                raise RuntimeError('Game module identity is not unique')
            fingerprint = read_fingerprint(memory, int(modules[0][0]))
        result['game_fingerprint'] = fingerprint
        profile = ProfileCatalog().select_for_image(fingerprint, modules[0][1], modules[0][2])
        result.update(game_build=profile.data['game_version'], adapter_id=profile.id,
                      adapter_version=profile.data['adapter_version'],
                      adapter_selection=profile.selection_report())
    except Exception as exc:
        result['game_build_detection_error'] = repr(exc)
    return result


def collect_runtime_diagnostics(
    game_pid: int | None = None,
    *,
    requested_pid: int | None = None,
    target_hwnd: int = 0,
) -> dict[str, object]:
    """Capture failure context without scanning arbitrary processes."""
    trainer_pid = int(kernel32.GetCurrentProcessId() or os.getpid())
    foreground = int(user32.GetForegroundWindow() or 0)
    try:
        visible_windows = enum_war3_windows()
    except Exception as exc:
        visible_windows = []
        visible_windows_error = repr(exc)
    else:
        visible_windows_error = None

    candidates = []
    for hwnd, pid, title in visible_windows:
        row = {
            "hwnd": hex(int(hwnd)),
            "pid": int(pid),
            "title": title,
            "thread_id": int(
                user32.GetWindowThreadProcessId(
                    ctypes.c_void_p(hwnd),
                    None,
                )
            ),
        }
        row["process"] = _process_runtime_diagnostics(pid)
        candidates.append(row)

    trainer = {
        "pid": trainer_pid,
        "parent_pid": os.getppid(),
        "parent_process": _process_runtime_diagnostics(os.getppid()),
        "session_id": _process_session_id(trainer_pid),
        "executable": sys.executable,
        "source": __file__,
        "frozen": bool(getattr(sys, "frozen", False)),
        "argv": list(sys.argv),
        "current_thread_id": int(kernel32.GetCurrentThreadId()),
        "token": _token_runtime_diagnostics(kernel32.GetCurrentProcess()),
    }
    host = {
        "platform": platform.platform(aliased=True),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "win32_ver": platform.win32_ver(),
        "pointer_bits": ctypes.sizeof(ctypes.c_void_p) * 8,
    }
    target_pid = int(game_pid) if game_pid else None
    result: dict[str, object] = {
        "schema": 2,
        "app_version": APP_VERSION,
        "release_channel": APP_RELEASE_CHANNEL,
        **diagnostic_game_build(target_pid),
        "compat_revision": WIN10_COMPAT_REVISION,
        "trainer": trainer,
        **diagnostic_target_identity(
            target_pid,
            visible_windows,
            requested_pid=requested_pid,
            target_hwnd=target_hwnd,
        ),
        "target_game": _process_runtime_diagnostics(target_pid),
        "visible_warcraft_windows": candidates,
        "foreground_window": _window_runtime_diagnostics(foreground),
        "host": host,
        "se_debug_enabled": bool(_debug_privilege_enabled),
    }
    if visible_windows_error:
        result["visible_windows_error"] = visible_windows_error
    return result


def summarize_engine_report(report: dict[str, object]) -> dict[str, object]:
    dispatch = report.get("dispatch") or {}
    if not isinstance(dispatch, dict):
        return {"operation": report.get("operation"), "report_error": "invalid dispatch"}

    def state_summary(name: str) -> dict[str, object] | None:
        state = dispatch.get(name)
        if not isinstance(state, dict):
            return None
        keys = (
            "hook",
            "target_tid",
            "message",
            "stage",
            "last_error",
            "callback_tid",
            "callback_count",
            "detached",
            "active",
            "query_result",
            "bridge_install_trace",
            "tls_value",
            "query_stage",
            "exception_code",
            "unwind_registered",
            "unwind_removed",
        )
        return {key: state.get(key) for key in keys if key in state}

    return {
        "schema": 1,
        "operation": report.get("operation"),
        "game_pid": report.get("pid"),
        "route": dispatch.get("image_route"),
        "route_policy": dispatch.get("route_policy"),
        "route_attempt": dispatch.get("route_attempt"),
        "same_route_retry": dispatch.get("same_route_retry"),
        "bridge_sha256": dispatch.get("image_sha256"),
        "hook_kind": dispatch.get("hook_kind"),
        "message_delivery": dispatch.get("message_delivery"),
        "target_window": dispatch.get("target_window"),
        "remote_api_resolution": dispatch.get("remote_api_resolution"),
        "image_map": dispatch.get("image_map"),
        "install_thread": dispatch.get("install_thread"),
        "after_install": state_summary("after_install"),
        "after_send": state_summary("after_send"),
        "after_cleanup": state_summary("after_cleanup"),
        "callback_verified": dispatch.get("callback_verified"),
        "query_completed": dispatch.get("query_completed"),
        "work_freed": dispatch.get("work_freed"),
        "block_freed": dispatch.get("block_freed"),
        "image_unmap_status": dispatch.get("image_unmap_status"),
        "allocations_retained": dispatch.get("allocations_retained"),
        "safe_to_release": dispatch.get("safe_to_release"),
        "transport_error": dispatch.get("error"),
    }


class Win10ReadLogger:
    MAX_ARCHIVE_LOGS = 128

    @classmethod
    def _prune_archives(cls, log_root: Path, reserve: int = 1, prefix: str = "win10-read") -> None:
        try:
            archives = sorted(
                log_root.glob(f"{prefix}-*-pid*.log"),
                key=lambda path: (path.stat().st_mtime_ns, path.name),
            )
        except OSError:
            return
        keep = max(cls.MAX_ARCHIVE_LOGS - max(int(reserve), 0), 0)
        expired = archives[:-keep] if keep else archives
        for path in expired:
            try:
                path.unlink()
                path.with_suffix('.jsonl').unlink(missing_ok=True)
            except OSError:
                pass

    def __init__(
        self,
        pid: int | None,
        prefix: str = "win10-read",
        *,
        requested_pid: int | None = None,
        target_hwnd: int = 0,
    ):
        self.game_pid = int(pid) if pid else None
        # Keep the legacy attribute for existing diagnostics callers while
        # making unknown targets explicit in the log schema and filename.
        self.pid = self.game_pid or 0
        self.requested_pid = int(requested_pid) if requested_pid else None
        self.target_hwnd = int(target_hwnd or 0)
        self.prefix = str(prefix)
        self.trainer_pid = os.getpid()
        self.trainer_parent_pid = os.getppid()
        self.started = time.perf_counter()
        self._lock = threading.Lock()
        self._files = []
        stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
        archive_suffix = (
            f"-tpid{self.trainer_pid}-tid{threading.get_ident()}"
            f"-sid{uuid.uuid4().hex[:10]}"
        )
        preferred_root = (
            Path(sys.executable).resolve().parent
            if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parent
        )
        roots = (
            preferred_root / "log",
            Path(tempfile.gettempdir()) / "War3ReforgedTrainer" / "log",
        )
        last_error: OSError | None = None
        for log_root in roots:
            opened = []
            try:
                log_root.mkdir(parents=True, exist_ok=True)
                self._prune_archives(log_root, prefix=self.prefix)
                archive_pid = str(self.game_pid) if self.game_pid is not None else "unknown"
                archive_path = log_root / f"{self.prefix}-{stamp}-pid{archive_pid}{archive_suffix}.log"
                latest_path = log_root / f"{self.prefix}-latest.log"
                opened.append(archive_path.open("x", encoding="utf-8-sig", buffering=1))
            except OSError as exc:
                last_error = exc
                for handle in opened:
                    handle.close()
                continue
            self.archive_path = archive_path
            self.latest_path = latest_path
            self.path = latest_path
            self._files = opened
            break
        else:
            raise RuntimeError(f"无法创建 Win10 读取诊断日志：{last_error}")
        target_identity = diagnostic_target_identity(
            self.game_pid,
            requested_pid=self.requested_pid,
            target_hwnd=self.target_hwnd,
        )
        self.log(
            "log_start",
            log_schema=2,
            app_version=APP_VERSION,
            release_channel=APP_RELEASE_CHANNEL,
            **diagnostic_game_build(self.game_pid),
            compat_revision=WIN10_COMPAT_REVISION,
            pid=self.game_pid,
            game_pid=self.game_pid,
            actual_target_pid=self.game_pid,
            window_pid=target_identity.get("window_pid"),
            target_identity=target_identity,
            trainer_parent_pid=self.trainer_parent_pid,
            archive=str(self.archive_path),
            latest=str(self.latest_path),
        )
        if self.prefix.startswith("trainer-error"):
            try:
                self.log(
                    "runtime_context",
                    context=collect_runtime_diagnostics(
                        self.game_pid,
                        requested_pid=self.requested_pid,
                        target_hwnd=self.target_hwnd,
                    ),
                )
            except Exception as exc:
                self.log("runtime_context_error", exception=repr(exc))

    @staticmethod
    def _format_value(value: object) -> str:
        if isinstance(value, str):
            return repr(value.replace("\r", "\\r").replace("\n", "\\n"))
        return repr(value)

    def log(self, event: str, **values: object) -> None:
        elapsed_ms = (time.perf_counter() - self.started) * 1000.0
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        details = " ".join(
            f"{key}={self._format_value(value)}" for key, value in values.items()
        )
        line = (
            f"[{timestamp}] +{elapsed_ms:010.1f}ms "
            f"trainer_pid={self.trainer_pid} "
            f"thread={threading.get_ident()} "
            f"win_thread={int(kernel32.GetCurrentThreadId())} event={event}"
        )
        if details:
            line += " " + details
        line += "\n"
        with self._lock:
            alive = []
            for handle in self._files:
                try:
                    handle.write(line)
                    handle.flush()
                except OSError:
                    try:
                        handle.close()
                    except OSError:
                        pass
                else:
                    alive.append(handle)
            self._files = alive

    def log_traceback(self, event: str, exc: BaseException) -> None:
        self.log(event, exception=repr(exc), traceback=traceback.format_exc())

    @contextmanager
    def stage(self, name: str, **values: object) -> Iterator[None]:
        started = time.perf_counter()
        self.log("stage_begin", stage=name, **values)
        try:
            yield
        except Exception as exc:
            self.log(
                "stage_error",
                stage=name,
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
                exception=repr(exc),
            )
            raise
        self.log(
            "stage_end",
            stage=name,
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
        )

    def close(self) -> None:
        if not self._files:
            return
        self.log("log_end", elapsed_ms=(time.perf_counter() - self.started) * 1000.0)
        with self._lock:
            files, self._files = self._files, []
        for handle in files:
            try:
                handle.close()
            except OSError:
                pass
        # Keep every archive intact and publish the convenience alias only
        # after the session is complete. os.replace makes readers see either
        # the previous complete log or this complete log, never a truncation.
        temp_latest = self.latest_path.with_name(
            f".{self.latest_path.name}.{self.trainer_pid}.{threading.get_ident()}.tmp"
        )
        try:
            import shutil
            shutil.copyfile(self.archive_path, temp_latest)
            os.replace(temp_latest, self.latest_path)
        except OSError:
            try:
                temp_latest.unlink()
            except OSError:
                pass


# Historical UI label only; this compatibility reader is used on Win10 and Win11.
def record_operation_failure(
    pid: int | None,
    operation: str,
    exc: BaseException,
    *,
    requested_pid: int | None = None,
    target_hwnd: int = 0,
) -> str:
    from war3_error_messages import describe_error
    logger = Win10ReadLogger(
        pid,
        prefix="trainer-error",
        requested_pid=requested_pid,
        target_hwnd=target_hwnd,
    )
    try:
        target_identity = diagnostic_target_identity(
            logger.game_pid,
            requested_pid=requested_pid,
            target_hwnd=target_hwnd,
        )
        logger.log("user_explanation", **describe_error(exc))
        logger.log("operation_failure", operation=operation, pid=logger.game_pid,
                   game_pid=logger.game_pid,
                   actual_target_pid=logger.game_pid,
                   window_pid=target_identity.get("window_pid"),
                   target_identity=target_identity,
                   trainer_parent_pid=os.getppid(),
                   executable=sys.executable, source=__file__,
                   exception_type=type(exc).__name__,
                   winerror=getattr(exc, "winerror", None),
                   hresult=getattr(exc, "hresult", None),
                   exception=repr(exc), traceback="".join(traceback.format_exception(exc)))
        session_report = getattr(exc, "session_report", None)
        if isinstance(session_report, dict):logger.log("game_session_report", report=session_report)
        engine_report = getattr(exc, "report", None)
        if isinstance(engine_report, dict):
            if isinstance(engine_report.get("integrity"), dict):
                logger.log("permission_check", **engine_report["integrity"])
            logger.log("engine24268_failure_summary", summary=summarize_engine_report(engine_report))
            logger.log("engine24268_execution_report", report=engine_report)
        # A later wrapper must not erase the earlier transport/identity result.
        failures = []
        seen = set()
        current = exc
        while current is not None and id(current) not in seen and len(failures) < 8:
            seen.add(id(current))
            entry = {"type": type(current).__name__, "message": str(current),
                     "winerror": getattr(current, "winerror", None)}
            report = getattr(current, "report", None)
            if isinstance(report, dict):
                entry["report"] = report
            failures.append(entry)
            current = current.__cause__ or current.__context__
        logger.log("failure_chain", failures=failures, truncated=current is not None)
        return str(logger.archive_path)
    finally:
        logger.close()


def record_engine_recovery(pid: int, report: dict) -> str:
    logger = Win10ReadLogger(pid, prefix="engine24268-recovery")
    try:
        logger.log("verified_tail_fault_recovery", report=report)
        return str(logger.archive_path)
    finally:
        logger.close()


class Win10ProcessMemory(ProcessMemory):
    EXACT_READ_LIMIT = 0x1000
    SCAN_CHUNK_SIZE = 0x10000
    PAGE_SIZE = 0x1000
    EXACT_RETRIES = 3

    def __init__(self, pid: int, diagnostics: Win10ReadLogger, write: bool = False):
        self.diagnostics = diagnostics
        self.read_calls = 0
        self.requested_bytes = 0
        self.read_failures = 0
        self.partial_copy_failures = 0
        self.tolerant_ranges = 0
        self.zero_filled_bytes = 0
        self.skipped_unreadable_reads = 0
        self._readable_region_starts: tuple[int, ...] = ()
        self._skipped_unreadable_callsites: dict[str, int] = {}
        self._skipped_unreadable_addresses: dict[int, int] = {}
        super().__init__(pid, write=write)
        self.diagnostics.log(
            "process_open",
            pid=pid,
            write=write,
            pointer_bits=ctypes.sizeof(ctypes.c_void_p) * 8,
            python=sys.version,
            windows=str(sys.getwindowsversion()),
        )

    def close(self) -> None:
        if self.handle:
            self.diagnostics.log(
                "process_memory_summary",
                read_calls=self.read_calls,
                requested_bytes=self.requested_bytes,
                read_failures=self.read_failures,
                partial_copy_failures=self.partial_copy_failures,
                tolerant_ranges=self.tolerant_ranges,
                zero_filled_bytes=self.zero_filled_bytes,
                skipped_unreadable_reads=self.skipped_unreadable_reads,
                skipped_unreadable_callsites=sorted(
                    self._skipped_unreadable_callsites.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )[:20],
                skipped_unreadable_addresses=[
                    (f"0x{address:x}", count)
                    for address, count in sorted(
                        self._skipped_unreadable_addresses.items(),
                        key=lambda item: item[1],
                        reverse=True,
                    )[:20]
                ],
            )
        super().close()

    def regions(self, force_refresh: bool = False) -> list[Region]:
        cache_hit = self._regions_cache is not None and not force_refresh
        regions = super().regions(force_refresh=force_refresh)
        if not cache_hit or not self._readable_region_starts:
            self._readable_region_starts = tuple(region.base for region in regions)
        if cache_hit:
            return regions
        type_counts: dict[int, int] = {}
        type_bytes: dict[int, int] = {}
        for region in regions:
            type_counts[region.typ] = type_counts.get(region.typ, 0) + 1
            type_bytes[region.typ] = type_bytes.get(region.typ, 0) + region.size
        self.diagnostics.log(
            "regions_refresh",
            count=len(regions),
            private_count=type_counts.get(MEM_PRIVATE, 0),
            private_bytes=type_bytes.get(MEM_PRIVATE, 0),
            image_count=type_counts.get(MEM_IMAGE, 0),
            image_bytes=type_bytes.get(MEM_IMAGE, 0),
            mapped_count=type_counts.get(MEM_MAPPED, 0),
            mapped_bytes=type_bytes.get(MEM_MAPPED, 0),
        )
        return regions

    def is_readable_range(self, address: int, size: int = 1) -> bool:
        address = int(address)
        size = int(size)
        if address < 0 or size < 0:
            return False
        if size == 0:
            return True
        end = address + size
        if end <= address:
            return False
        if self._regions_cache is None or not self._readable_region_starts:
            self.regions()
        regions = self._regions_cache or []
        starts = self._readable_region_starts
        index = bisect_right(starts, address) - 1
        if index < 0:
            return False
        current = address
        while current < end and index < len(regions):
            region = regions[index]
            region_end = region.base + region.size
            if not region.base <= current < region_end:
                return False
            current = min(end, region_end)
            if current >= end:
                return True
            index += 1
            if index >= len(regions) or regions[index].base != current:
                return False
        return False

    def _record_unreadable_skip(self, address: int, size: int) -> None:
        self.skipped_unreadable_reads += 1
        callsite = self._callsite()
        self._skipped_unreadable_callsites[callsite] = (
            self._skipped_unreadable_callsites.get(callsite, 0) + 1
        )
        if len(self._skipped_unreadable_addresses) < 256 or address in self._skipped_unreadable_addresses:
            self._skipped_unreadable_addresses[address] = (
                self._skipped_unreadable_addresses.get(address, 0) + 1
            )
        if self.skipped_unreadable_reads <= 20:
            region = self._query_region(address)
            self.diagnostics.log(
                "read_skipped_unreadable",
                address=f"0x{address:x}",
                requested=f"0x{size:x}",
                callsite=callsite,
                region=region,
            )
        elif self.skipped_unreadable_reads == 21:
            self.diagnostics.log("read_skipped_unreadable_suppressed")

    def _query_region(self, address: int) -> dict[str, int]:
        mbi = MEMORY_BASIC_INFORMATION64()
        result = kernel32.VirtualQueryEx(
            self.handle,
            ctypes.c_void_p(address),
            ctypes.byref(mbi),
            ctypes.sizeof(mbi),
        )
        if not result:
            return {}
        return {
            "base": int(mbi.BaseAddress),
            "size": int(mbi.RegionSize),
            "state": int(mbi.State),
            "protect": int(mbi.Protect),
            "type": int(mbi.Type),
        }

    @staticmethod
    def _callsite() -> str:
        frames = traceback.extract_stack(limit=7)[:-2]
        return " > ".join(f"{frame.name}:{frame.lineno}" for frame in frames[-4:])

    def _read_once(self, address: int, size: int) -> tuple[bytes, int, int, bool]:
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t(0)
        ctypes.set_last_error(0)
        ok = bool(
            kernel32.ReadProcessMemory(
                self.handle,
                ctypes.c_void_p(address),
                buf,
                ctypes.c_size_t(size),
                ctypes.byref(got),
            )
        )
        received = int(got.value)
        error = int(ctypes.get_last_error())
        if received != size and not error:
            error = ERROR_PARTIAL_COPY
        return buf.raw[:received], received, error, ok

    def _log_read_failure(
        self,
        address: int,
        size: int,
        received: int,
        error: int,
        attempt: int,
        mode: str,
    ) -> None:
        self.read_failures += 1
        if error == ERROR_PARTIAL_COPY:
            self.partial_copy_failures += 1
        region = self._query_region(address)
        self.diagnostics.log(
            "read_failure",
            mode=mode,
            address=f"0x{address:x}",
            requested=f"0x{size:x}",
            received=f"0x{received:x}",
            error=error,
            attempt=attempt,
            callsite=self._callsite(),
            region_base=f"0x{region.get('base', 0):x}",
            region_size=f"0x{region.get('size', 0):x}",
            region_state=f"0x{region.get('state', 0):x}",
            region_protect=f"0x{region.get('protect', 0):x}",
            region_type=f"0x{region.get('type', 0):x}",
        )

    @staticmethod
    def _raise_read_error(address: int, size: int, received: int, error: int) -> None:
        code = error or ERROR_PARTIAL_COPY
        exc = ctypes.WinError(code)
        exc.add_note(
            "ReadProcessMemory "
            f"address=0x{address:x} requested=0x{size:x} received=0x{received:x}"
        )
        raise exc

    def _read_exact(self, address: int, size: int) -> bytes:
        result = bytearray()
        current = int(address)
        remaining = int(size)
        while remaining:
            request = min(remaining, 0x1000 - (current & 0xFFF))
            data = b""
            received = 0
            error = 0
            for attempt in range(1, self.EXACT_RETRIES + 1):
                data, received, error, _ok = self._read_once(current, request)
                if received == request:
                    break
                self._log_read_failure(current, request, received, error, attempt, "exact-page")
                if error != ERROR_PARTIAL_COPY or attempt == self.EXACT_RETRIES:
                    break
                self._regions_cache = None
                time.sleep(0.002 * attempt)
            if received != request:
                self._raise_read_error(current, request, received, error)
            result.extend(data)
            current += request
            remaining -= request
        return bytes(result)

    def _read_tolerant(self, address: int, size: int) -> bytes:
        data, received, error, _ok = self._read_once(address, size)
        if received == size:
            return data
        self._log_read_failure(address, size, received, error, 1, "range_initial")
        if error != ERROR_PARTIAL_COPY:
            self._raise_read_error(address, size, received, error)

        self.tolerant_ranges += 1
        result = bytearray(size)
        recovered = 0
        if received:
            result[:received] = data
            recovered = received
        current = address + received
        end = address + size
        while current < end:
            chunk_address = current
            request_size = min(self.SCAN_CHUNK_SIZE, end - current)
            chunk, got, chunk_error, _chunk_ok = self._read_once(chunk_address, request_size)
            if got:
                offset = chunk_address - address
                result[offset : offset + got] = chunk
                recovered += got
                current = chunk_address + got
                if got == request_size:
                    continue
            if got != request_size:
                self._log_read_failure(
                    chunk_address,
                    request_size,
                    got,
                    chunk_error,
                    1,
                    "range_chunk",
                )
            if chunk_error != ERROR_PARTIAL_COPY:
                self._raise_read_error(current, request_size, got, chunk_error)
            if got:
                continue

            page_address = current
            page_size = min(
                self.PAGE_SIZE - (page_address & (self.PAGE_SIZE - 1)),
                end - page_address,
            )
            page, page_got, page_error, _page_ok = self._read_once(page_address, page_size)
            if page_got:
                offset = page_address - address
                result[offset : offset + page_got] = page
                recovered += page_got
                current = page_address + page_got
                if page_got == page_size:
                    continue
            self._log_read_failure(
                page_address,
                page_size,
                page_got,
                page_error,
                1,
                "range_page",
            )
            if page_error != ERROR_PARTIAL_COPY:
                self._raise_read_error(current, page_size, page_got, page_error)
            if page_got:
                continue

            region = self._query_region(current)
            if region and (
                region.get("state") != MEM_COMMIT
                or region.get("protect", 0) & (PAGE_NOACCESS | PAGE_GUARD)
                or (region.get("protect", 0) & 0xFF) not in READABLE_PROTECTS
            ):
                skip = min(
                    max(1, region["base"] + region["size"] - current),
                    end - current,
                )
            else:
                skip = page_size
            self.zero_filled_bytes += skip
            self.diagnostics.log(
                "range_skip",
                address=f"0x{current:x}",
                size=f"0x{skip:x}",
                error=page_error,
                region=region,
            )
            current += skip

        zero_filled = size - recovered
        self.diagnostics.log(
            "tolerant_read_complete",
            address=f"0x{address:x}",
            requested=f"0x{size:x}",
            recovered=f"0x{recovered:x}",
            zero_filled=f"0x{zero_filled:x}",
        )
        return bytes(result)

    def read(self, address: int, size: int) -> bytes:
        if size < 0:
            raise ValueError("读取长度不能为负数")
        if size == 0:
            return b""
        self.read_calls += 1
        self.requested_bytes += size
        if size <= self.EXACT_READ_LIMIT:
            if not self.is_readable_range(address, size):
                self._record_unreadable_skip(address, size)
                self._raise_read_error(address, size, 0, ERROR_PARTIAL_COPY)
            return self._read_exact(address, size)
        return self._read_tolerant(address, size)


def _window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


WAR3_WINDOW_TITLES = frozenset({"Warcraft III", "Warcraft III Public Test"})


def enum_war3_windows() -> list[tuple[int, int, str]]:
    windows: list[tuple[int, int, str]] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_proc(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = _window_text(hwnd)
        if title not in WAR3_WINDOW_TITLES:
            return True
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        # A folder named Warcraft III has the same window title. Never bind
        # its explorer.exe process or count it as a second game client.
        executable = process_executable_path(int(pid.value))
        if Path(executable).name.casefold() not in {"warcraft iii.exe", "war3.exe"}:
            return True
        windows.append((int(hwnd), int(pid.value), title))
        return True

    user32.EnumWindows(enum_proc, None)
    return windows


def find_war3(pid: int | None = None) -> tuple[int, int]:
    matches = enum_war3_windows()
    if pid is not None:
        matches = [m for m in matches if m[1] == pid]
    if not matches:
        if pid is not None:
            executable = process_executable_path(pid)
            if executable and Path(executable).name.casefold() not in {"warcraft iii.exe", "war3.exe"}:
                raise RuntimeError("所选进程不是 Warcraft III 游戏，请清空 PID 后重新连接，或填写游戏进程的 PID")
        raise RuntimeError("没有找到 Warcraft III 正式服或测试服的可见窗口")
    if pid is None and len({match[1] for match in matches}) > 1:
        raise RuntimeError("Multiple Warcraft III clients are open; select an explicit PID")
    hwnd, found_pid, _title = matches[0]
    return hwnd, found_pid


def process_executable_path(pid: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.c_ulong(len(buffer))
        if not kernel32.QueryFullProcessImageNameW(
            handle, 0, buffer, ctypes.byref(length)
        ):
            return ""
        return buffer.value
    finally:
        kernel32.CloseHandle(handle)


def find_war3_by_executable_path(executable_path: str) -> tuple[int, int]:
    expected = executable_path.casefold()
    matches = [
        (hwnd, pid, title)
        for hwnd, pid, title in enum_war3_windows()
        if process_executable_path(pid).casefold() == expected
    ]
    if not matches:
        raise RuntimeError("没有找到同一 Warcraft III 安装目录的可见窗口")
    if len(matches) > 1:
        raise RuntimeError("同一 Warcraft III 安装目录存在多个客户端，请选择 PID")
    hwnd, found_pid, _title = matches[0]
    return hwnd, found_pid


def find_war3_with_retry(
    pid: int | None = None,
    attempts: int = 16,
    delay_seconds: float = 0.25,
    executable_path: str | None = None,
) -> tuple[int, int]:
    """Wait briefly for a game window that is between launch/loading states."""
    last_error: RuntimeError | None = None
    for attempt in range(max(1, int(attempts))):
        try:
            return find_war3(pid)
        except RuntimeError as exc:
            last_error = exc
            if executable_path:
                try:
                    return find_war3_by_executable_path(executable_path)
                except RuntimeError as affinity_error:
                    last_error = affinity_error
            elif "Multiple Warcraft III clients are open" in str(exc):
                # Without a remembered installation path, multiple clients are an
                # explicit-selection problem rather than a transient launch state.
                raise
            if attempt + 1 < max(1, int(attempts)):
                time.sleep(max(0.0, float(delay_seconds)))
    assert last_error is not None
    raise last_error


def resolve_requested_war3_pid(requested_pid: int | None) -> int | None:
    """Keep an explicit PID only while its visible Warcraft III window exists."""
    if requested_pid is None:
        return None
    if any(found_pid == int(requested_pid) for _hwnd, found_pid, _title in enum_war3_windows()):
        return int(requested_pid)
    return None


def is_war3_window(hwnd: int, pid: int) -> bool:
    if not hwnd or not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd):
        return False
    if _window_text(hwnd) not in WAR3_WINDOW_TITLES:
        return False
    found_pid = ctypes.c_ulong()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(found_pid))
    return int(found_pid.value) == pid


def focus_window(hwnd: int) -> None:
    user32.ShowWindow(hwnd, SW_RESTORE)
    time.sleep(0.12)
    foreground = user32.GetForegroundWindow()
    current_tid = kernel32.GetCurrentThreadId()
    target_tid = user32.GetWindowThreadProcessId(hwnd, None)
    foreground_tid = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
    if foreground_tid:
        user32.AttachThreadInput(current_tid, foreground_tid, True)
    user32.AttachThreadInput(current_tid, target_tid, True)
    user32.BringWindowToTop(hwnd)
    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
    user32.SetForegroundWindow(hwnd)
    user32.SetActiveWindow(hwnd)
    user32.SetFocus(hwnd)
    time.sleep(0.08)
    if foreground_tid:
        user32.AttachThreadInput(current_tid, foreground_tid, False)
    user32.AttachThreadInput(current_tid, target_tid, False)


def _post_enter(hwnd: int) -> None:
    user32.PostMessageW(hwnd, WM_KEYDOWN, VK_RETURN, 0x001C0001)
    time.sleep(0.04)
    user32.PostMessageW(hwnd, WM_KEYUP, VK_RETURN, 0xC01C0001)
    time.sleep(0.07)


def post_cheat(hwnd: int, text: str, delay: float = 0.75) -> None:
    focus_window(hwnd)
    _post_enter(hwnd)
    for ch in text:
        user32.PostMessageW(hwnd, WM_CHAR, ord(ch), 1)
        time.sleep(0.012)
    _post_enter(hwnd)
    time.sleep(delay)


def __getattr__(name):
    if name in ('NATIVE_PROFILE_ID','NATIVE_INDEX'):
        from diagnostics.war3_native_profile import PROFILE_ID,NATIVE_INDEX
        return PROFILE_ID if name=='NATIVE_PROFILE_ID' else NATIVE_INDEX
    raise AttributeError(name)

from war3_trainer_session import bind_trainer, uses_indexed_backend
from war3_services.facade_binding import bind_facades
from war3_adapter_legacy import LegacyAdapterMethods
from war3_adapter_state import ProfileMember, ProfileMembers
from war3_services.facade_native import NativeFacade
from war3_services.facade_extensions import ExtensionsFacade
from war3_services.facade_units import UnitsFacade
from war3_services.facade_abilities import AbilitiesFacade
from war3_services.facade_items import ItemsFacade
from war3_services.facade_resources import ResourcesFacade
from war3_services.facade_selection import SelectionFacade
from war3_services.facade_fields import FieldsFacade
bind_facades(globals(), (LegacyAdapterMethods, NativeFacade, ExtensionsFacade, UnitsFacade, AbilitiesFacade, ItemsFacade, ResourcesFacade, SelectionFacade, FieldsFacade,))

@bind_trainer
class War3Trainer(NativeFacade, ExtensionsFacade, UnitsFacade, AbilitiesFacade, ItemsFacade, ResourcesFacade, SelectionFacade, FieldsFacade):
    @property
    def _native_selection_unavailable(self):
        # Deprecated compatibility name: current sessions have a fixed indexed
        # read backend and per-capability native execution, never a global switch.
        if getattr(self,"_game_session",None) is not None:return True
        return self._diagnostic_native_selection_unavailable

    @_native_selection_unavailable.setter
    def _native_selection_unavailable(self,value):
        self._diagnostic_native_selection_unavailable=bool(value)

    _PROCESS_NATIVE_HANDLER_CACHE: dict[tuple[int, int], dict[str, NativeHandler]] = {}
    # Native registrations and their code addresses belong to the game
    # process, not to a GUI/session object.  Keep the verified bindings at
    # process scope so isolated read sessions follow the classic DLL model:
    # resolve the native table once, then call the cached entries.
    _PROCESS_NATIVE_HANDLER_CACHE: dict[int, dict[str, NativeHandler]] = {}
    # Verified for the live 2.0.4.23745 process in this session. Fallback scanning is used
    # when these addresses are stale.
    KNOWN_RESOURCE_PAIRS = [
        (0x1A5FB6DD1F0, 0x1A5FB6DD2D0),
    ]

    CHEATS = {
        "无敌并一击必杀": "whosyourdaddy",
        "显示全地图": "iseedeadpeople",
        "无限魔法": "thereisnospoon",
        "直接胜利": "allyourbasearebelongtous",
        "取消人口限制": "pointbreak",
        "刷新技能冷却": "thedudeabides",
        "所有升级": "sharpandshiny",
        "允许全部研究": "whoisjohngalt",
        "取消科技树限制": "synergy",
        "失败后继续": "strengthandhonor",
        "禁用胜利条件": "itvexesme",
    }
    PROP_TAG = 0x6072656C5E70726F
    POSITION_PROP_TAG = 0x607063755E70726F
    RESOURCE_PROP_TAG = 0x60666C675E70726F
    UNIT_OWNER_TAG = 0x2B7733752B61676C
    ITEM_OWNER_TAG = 0x6974656D2B61676C
    PLAYER_COMPONENT_TAG = 0x2B706C792B61676C
    COMPONENT_TAGS = {
        "move": 0x416D6F762B61676C,    # lga+vomA
        "attack": 0x4161746B2B61676C,  # lga+ktaA
        "hero": 0x414865722B61676C,    # lga+reHA
        "inventory": 0x41496E762B61676C,  # lga+vnIA
    }
    COMPONENT_NAMES = {value: key for key, value in COMPONENT_TAGS.items()}
    CLI_UNIT_FIELD_KEYS = {
        "xp": "xp",
        "skill_points": "skill_points",
        "base_str": "base_strength",
        "base_agi": "base_agility",
        "int": "intelligence_total",
        "intelligence": "intelligence_total",
        "add_str": "strength_growth",
        "add_int": "intelligence_growth",
        "add_agi": "agility_growth",
        "move_speed": "move_speed",
        "armor": "armor",
        "defense": "armor",
        "armor_type": "armor_type",
        "attack_type": "attack1_type",
        "attack_speed": "attack1_true_speed",
        "attack_damage_level": "attack1_base1",
        "attack_damage_item": "attack1_internal_bonus1",
    }
    FIELD_KEY_ALIASES = {
        "added_strength": "strength_growth",
        "added_intelligence": "intelligence_growth",
        "added_agility": "agility_growth",
        "attack_max_targets": "attack1_max_targets",
        "attack1_damage_level": "attack1_base1",
        "attack2_damage_level": "attack2_base1",
        "attack1_damage_item": "attack1_internal_bonus1",
        "attack2_damage_item": "attack2_internal_bonus1",
        "attack1_speed": "attack1_projectile_speed",
        "attack2_speed": "attack2_projectile_speed",
    }
    # Reforged keeps the current selection handle in this mapped game-state block.
    # The value is validated through the live unit-owner index before any write.
    KNOWN_SELECTED_HANDLE_ADDRESSES = (
        0x80001F3845,
        0x80001F3495,
        0x80001F30F4,
        0x80001F2EC4,
        0x80001F2F23,
        0x80001F2F31,
    )
    KNOWN_SELECTED_HANDLE_OFFSETS = tuple(address & 0xFFFFFFFF for address in KNOWN_SELECTED_HANDLE_ADDRESSES)
    SELECTION_STATE_REGION_LOW20 = 0xBF000
    KNOWN_SELECTED_REGION_OFFSETS = tuple(
        (address & 0xFFFFF) - 0xBF000
        for address in KNOWN_SELECTED_HANDLE_ADDRESSES
        if (address & 0xFFFFF) >= 0xBF000
    )
    KNOWN_SELECTED_UNIT_POINTER_ADDRESSES = (
        0x80001F2700,
        0x80001F2710,
        0x80001F27C8,
        0x80001F27D0,
        0x80001F29C0,
        0x80001F29D0,
        0x80001F2A00,
        0x80001F2A68,
        0x80001F2A90,
        0x80001F2AA0,
        0x80001F2AE8,
        0x80001F2AF8,
        0x80001F2B20,
        0x80001F2D68,
        0x80001F2DB0,
        0x80001F2DD0,
        0x80001F2F00,
        0x80001F2F10,
    )
    KNOWN_SELECTED_UNIT_POINTER_REGION_OFFSETS = tuple(
        (address & 0xFFFFF) - 0xBF000
        for address in KNOWN_SELECTED_UNIT_POINTER_ADDRESSES
        if (address & 0xFFFFF) >= 0xBF000
    )
    CPLAYER_SELECTION_MANAGER_OFFSET = ProfileMember("selection", "manager")
    SELECTION_MANAGER_ALT_LIST_OFFSET = ProfileMember("layouts", "selection", "alternate_list")
    SELECTION_MANAGER_MAX_UNITS = 64
    SELECTED_BATCH_MAX_UNITS = 24
    WIN10_STRONG_SELECTION_SCORE = 155
    UNIT_OWNER_POINTER_SEARCH_RADIUS = 0x2000000
    HERO_SKILL_SLOT_COUNT = 5
    ABILITY_WRAPPER_SCAN_BACK = 0x70000
    ABILITY_WRAPPER_SCAN_FORWARD = 0x12000
    COMPONENT_WRAPPER_SCAN_BACK = 0x70000
    COMPONENT_WRAPPER_SCAN_FORWARD = 0x12000
    UNIT_COMPONENT_DATA_OFFSETS = ProfileMember("layouts", "legacy_component_slots")
    ABILITY_RUNTIME_TEMPLATE_QWORD_OFFSETS = ProfileMembers(*(("layouts", "ability", name) for name in ("vtable", "rawcode", "mirror_rawcode", "data_cache", "template_extra")))
    ITEM_CHARGES_OFFSET = ProfileMember("layouts", "item", "charges")
    ITEM_CHARGES_FLAG_OFFSET = ProfileMember("equipment_runtime", "item_flags")
    ITEM_CHARGES_EMPTY_FLAG = 0x1000
    SELECTED_HP_VALUE_OFFSET = ProfileMember("layouts", "property", "value")
    NATIVE_HANDLER_NAMES = (
        "UnitAddAbility",
        "UnitRemoveAbility",
        "SetUnitAbilityLevel",
        "GetUnitAbilityLevel",
        "UnitAddItem",
        "UnitAddItemById",
        "UnitItemInSlot",
        "UnitRemoveItem",
        "RemoveItem",
        "GetItemTypeId",
        "SetItemCharges",
        "GetUnitTypeId",
        "UnitInventorySize",
    )
    JASS_SELECTION_NATIVE_NAMES = (
        "CreateGroup",
        "SyncSelections",
        "GetLocalPlayer",
        "GroupEnumUnitsSelected",
        "FirstOfGroup",
        "GetHandleId",
        "DestroyGroup",
    )
    WIN10_SELECTION_NATIVE_NAMES = (
        "CreateGroup",
        "GetLocalPlayer",
        "GroupEnumUnitsSelected",
        "FirstOfGroup",
        "GetHandleId",
        "DestroyGroup",
    )
    NATIVE_RECORD_STRIDE = 0x88
    NATIVE_RECORD_PROFILE_ANCHORS = {
        "FogMaskEnable": 0xF0C0,
        "CreateGroup": 0x143A0,
        "FirstOfGroup": 0x15280,
        "GetWidgetLife": 0x158E0,
        "SetHeroInt": 0x189C0,
        "SetHeroLevel": 0x18F10,
        "CreateItem": 0x1DB90,
        "GetLocalPlayer": 0x1EC90,
        "EndGame": 0x202E0,
        "PauseGame": 0x27050,
        "BlzGetAbilityId": 0x39590,
    }
    NATIVE_RECORD_PROFILE_EXTERNALS = {
        "SetPlayerAlliance": 0xCB90,
        "IsFogMaskEnabled": 0xF148,
        "GroupEnumUnitsOfPlayer": 0x14A88,
        "GroupEnumUnitsSelected": 0x14D30,
        "UnitStripHeroLevel": 0x18C68,
        "UnitModifySkillPoints": 0x18CF0,
        "GetUnitAbilityLevel": 0x192C8,
        "SetUnitInvulnerable": 0x194E8,
        "GetHeroInt": 0x18B58,
        "UnitRemoveAbility": 0x1B330,
        "UnitApplyTimedLife": 0x1B990,
        "SetUnitAbilityLevel": 0x1BD48,
        "UnitResetCooldown": 0x1BDD0,
        "IssueImmediateOrderById": 0x1C078,
        "IssuePointOrderById": 0x1C188,
        "IssueTargetOrderById": 0x1C320,
        "SetPlayerTechMaxAllowed": 0x1F048,
        "SetPlayerTechResearched": 0x1F1E0,
        "SetPlayerHandicapXP": 0x1FD90,
        "ChooseRandomItem": 0x26390,
        "BlzSetUnitMaxMana": 0x33B40,
        "BlzUnitHideAbility": 0x34D50,
        "BlzIsUnitInvulnerable": 0x34F70,
        "BlzGetUnitAbility": 0x36FD8,
        "BlzGetUnitAbilityByIndex": 0x37060,
        "BlzGetAbilityRealLevelField": 0x39948,
        "BlzSetAbilityRealLevelField": 0x39FA8,
    }
    ELEPHANT_NATIVE_NAMES = (
        "SetHeroLevel",
        "GetHeroLevel",
        "UnitStripHeroLevel",
        "SuspendHeroXP",
        "IsSuspendedXP",
        "SetUnitInvulnerable",
        "BlzIsUnitInvulnerable",
        "UnitResetCooldown",
        "SetUnitPathing",
        "SetUnitScale",
        "KillUnit",
        "SetUnitExploded",
        "RemoveUnit",
        "PauseUnit",
        "IsUnitPaused",
        "PauseGame",
        "EndGame",
        "FogEnable",
        "FogMaskEnable",
        "IsFogEnabled",
        "IsFogMaskEnabled",
        "GetLocalPlayer",
        "GetOwningPlayer",
        "SetUnitOwner",
        "CreateUnit",
        "CreateItem",
        "ChooseRandomItem",
        "UnitAddItemById",
        "UnitItemInSlot",
        "UnitRemoveItem",
        "RemoveItem",
        "GetItemTypeId",
        "GetItemCharges",
        "SetItemCharges",
        "UnitAddAbility",
        "UnitRemoveAbility",
        "SetUnitAbilityLevel",
        "GetUnitAbilityLevel",
        "GetUnitFacing",
        "GetUnitState",
        "SetWidgetLife",
        "BlzGetUnitMaxHP",
        "BlzSetUnitMaxHP",
        "BlzGetUnitMaxMana",
        "BlzSetUnitMaxMana",
        "GetHeroXP",
        "SetHeroXP",
        "GetHeroStr",
        "SetHeroStr",
        "GetHeroAgi",
        "SetHeroAgi",
        "GetHeroInt",
        "SetHeroInt",
        "GetHeroSkillPoints",
        "UnitModifySkillPoints",
        "BlzGetUnitAbilityByIndex",
        "BlzGetUnitAbility",
        "BlzGetAbilityId",
        "BlzGetAbilityRealLevelField",
        "BlzSetAbilityRealLevelField",
        "BlzUnitHideAbility",
        "SetPlayerTechResearched",
        "SetPlayerTechMaxAllowed",
        "SetPlayerHandicapXP",
        "Player",
        "SetPlayerAlliance",
        "CreateGroup",
        "GroupEnumUnitsSelected",
        "GroupEnumUnitsOfPlayer",
        "FirstOfGroup",
        "GetHandleId",
        "GroupRemoveUnit",
        "DestroyGroup",
        "SetUnitPosition",
        "GetUnitX",
        "GetUnitY",
        "GetUnitTypeId",
        "GetWidgetLife",
        "SetUnitState",
        "IssuePointOrderById",
        "IssueTargetOrderById",
        "IssueImmediateOrderById",
        "UnitApplyTimedLife",
        "IsPlayerEnemy",
    )
    ABILITY_FIELD_NATIVE_NAMES = (
        "BlzGetUnitAbility",
        "BlzGetAbilityId",
        "GetUnitAbilityLevel",
        "BlzGetAbilityBooleanField",
        "BlzSetAbilityBooleanField",
        "BlzGetAbilityIntegerField",
        "BlzSetAbilityIntegerField",
        "BlzGetAbilityRealField",
        "BlzSetAbilityRealField",
        "BlzGetAbilityBooleanLevelField",
        "BlzSetAbilityBooleanLevelField",
        "BlzGetAbilityIntegerLevelField",
        "BlzSetAbilityIntegerLevelField",
        "BlzGetAbilityRealLevelField",
        "BlzSetAbilityRealLevelField",
    )
    ABILITY_FIELD_GETTER_NAMES = {
        ("boolean", "field"): "BlzGetAbilityBooleanField",
        ("integer", "field"): "BlzGetAbilityIntegerField",
        ("real", "field"): "BlzGetAbilityRealField",
        ("boolean", "level"): "BlzGetAbilityBooleanLevelField",
        ("integer", "level"): "BlzGetAbilityIntegerLevelField",
        ("real", "level"): "BlzGetAbilityRealLevelField",
    }
    ABILITY_FIELD_SETTER_NAMES = {
        ("boolean", "field"): "BlzSetAbilityBooleanField",
        ("integer", "field"): "BlzSetAbilityIntegerField",
        ("real", "field"): "BlzSetAbilityRealField",
        ("boolean", "level"): "BlzSetAbilityBooleanLevelField",
        ("integer", "level"): "BlzSetAbilityIntegerLevelField",
        ("real", "level"): "BlzSetAbilityRealLevelField",
    }
    ITEM_FIELD_NATIVE_NAMES = (
        "UnitItemInSlot",
        "GetItemTypeId",
        "BlzGetItemBooleanField",
        "BlzSetItemBooleanField",
        "BlzGetItemIntegerField",
        "BlzSetItemIntegerField",
        "BlzGetItemRealField",
        "BlzSetItemRealField",
    )
    ITEM_FIELD_GETTER_NAMES = {
        "boolean": "BlzGetItemBooleanField",
        "integer": "BlzGetItemIntegerField",
        "real": "BlzGetItemRealField",
    }
    ITEM_FIELD_SETTER_NAMES = {
        "boolean": "BlzSetItemBooleanField",
        "integer": "BlzSetItemIntegerField",
        "real": "BlzSetItemRealField",
    }
    NATIVE_SELECTION_HANDLER_NAMES = (
        "IsUnitSelected",
    )
    WIN10_COMPAT_NATIVE_NAMES = tuple(
        dict.fromkeys(
            (
                *ELEPHANT_NATIVE_NAMES,
                *ABILITY_FIELD_NATIVE_NAMES,
                *ITEM_FIELD_NATIVE_NAMES,
                *NATIVE_HANDLER_NAMES,
                *JASS_SELECTION_NATIVE_NAMES,
                *NATIVE_SELECTION_HANDLER_NAMES,
                "GetHeroInt",
            )
        )
    )
    NATIVE_HELPER_MAGIC = 0x33524757
    NATIVE_HELPER_VERSION = 71
    NATIVE_HELPER_CLONE_FLAG_HERO = 0x01
    NATIVE_HELPER_CLONE_FLAG_INVENTORY = 0x02
    NATIVE_HELPER_CLONE_FLAG_PRESERVE_OWNER = 0x04
    NATIVE_HELPER_STATUS_PENDING = 1
    NATIVE_HELPER_STATUS_OK = 2
    NATIVE_HELPER_MAX_OPS = 16
    NATIVE_HELPER_OP_STRUCT = struct.Struct("<IIQQQQII")
    NATIVE_HELPER_HEADER_STRUCT = struct.Struct("<IIIIQII")
    NATIVE_HELPER_OP_INTERNAL_ABILITY_BEGIN = 30
    NATIVE_HELPER_OP_INTERNAL_ABILITY_FIND = 31
    NATIVE_HELPER_OP_INTERNAL_ABILITY_ADD = 32
    NATIVE_HELPER_OP_INTERNAL_ABILITY_END = 33
    NATIVE_HELPER_OP_INTERNAL_ABILITY_REFRESH = 34
    NATIVE_HELPER_OP_INTERNAL_ABILITY_REMOVE = 35
    NATIVE_HELPER_OP_SET_ITEM_CHARGES = 40
    NATIVE_HELPER_OP_REMOVE_ITEM_SLOT = 41
    NATIVE_HELPER_OP_ADD_ITEM_TO_SLOT_BY_ID = 42
    NATIVE_HELPER_OP_GET_ITEM_TYPE_IN_SLOT = 43
    NATIVE_HELPER_OP_SET_HERO_INT = 60
    NATIVE_HELPER_OP_GET_HERO_INT = 61
    NATIVE_HELPER_OP_JASS_SELECTED_UNIT = 50
    NATIVE_HELPER_OP_JASS_SELECTED_UNIT_ARG = 51
    NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_QUERY = 52
    NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_SET = 53
    NATIVE_HELPER_OP_JASS_PLAYER_STATE_QUERY = 54
    NATIVE_HELPER_OP_JASS_PLAYER_STATE_SET = 55
    NATIVE_HELPER_OP_JASS_UNIT_VOID = 70
    NATIVE_HELPER_OP_JASS_UNIT_BOOL = 71
    NATIVE_HELPER_OP_JASS_UNIT_INT_BOOL = 72
    NATIVE_HELPER_OP_JASS_UNIT_RAWCODE = 73
    NATIVE_HELPER_OP_JASS_UNIT_RAWCODE_LEVEL = 74
    NATIVE_HELPER_OP_JASS_UNIT_SCALE = 75
    NATIVE_HELPER_OP_JASS_WORLD_BOOL = 76
    NATIVE_HELPER_OP_JASS_UNIT_INT_QUERY = 77
    NATIVE_HELPER_OP_JASS_EXPLODE_UNIT = 78
    NATIVE_HELPER_OP_JASS_TAKE_OWNERSHIP = 79
    NATIVE_HELPER_OP_JASS_CREATE_LOCAL_UNIT = 80
    NATIVE_HELPER_OP_JASS_CLEAR_INVENTORY = 81
    NATIVE_HELPER_OP_JASS_SET_LOCAL_TECH = 82
    NATIVE_HELPER_OP_JASS_SET_LOCAL_XP_RATE = 83
    NATIVE_HELPER_OP_JASS_KILL_OWNER_UNITS = 84
    NATIVE_HELPER_OP_JASS_MULTI_ARG = 85
    NATIVE_HELPER_OP_JASS_PEACE_MODE = 86
    NATIVE_HELPER_OP_JASS_WORLD_INT_QUERY = 87
    NATIVE_HELPER_OP_JASS_FOG_BOOL = 88
    NATIVE_HELPER_OP_JASS_SET_INVENTORY_CHARGES = 89
    NATIVE_HELPER_OP_JASS_DUPLICATE_INVENTORY = 90
    NATIVE_HELPER_OP_JASS_DROP_INVENTORY = 91
    NATIVE_HELPER_OP_JASS_REMOVE_ALL_ABILITIES = 92
    NATIVE_HELPER_OP_QUERY_WORLD_POINT = 93
    NATIVE_HELPER_OP_JASS_SET_UNIT_POSITION = 94
    NATIVE_HELPER_OP_CREATE_ALL_ITEMS = 95
    NATIVE_HELPER_OP_REMOVE_ITEM_HANDLES = 98
    NATIVE_HELPER_OP_REMOVE_ITEM_HANDLES_ARG = 99
    NATIVE_HELPER_OP_CAST_ABILITY = 100
    NATIVE_HELPER_OP_DIRECT_ABILITY_TARGET = 101
    NATIVE_HELPER_OP_DIRECT_ABILITY_IMMEDIATE = 102
    NATIVE_HELPER_OP_DIRECT_ABILITY_POINT = 103
    NATIVE_HELPER_OP_DIRECT_ABILITY_NOARG_DERIVED = 104
    NATIVE_HELPER_OP_DIRECT_ABILITY_BUFF = 105
    NATIVE_HELPER_OP_DIRECT_ABILITY_ENUM = 106
    NATIVE_HELPER_OP_JASS_ABILITY_REAL_LEVEL_FIELD_SET = 107
    NATIVE_HELPER_OP_JASS_UNIT_RESOLVE = 109
    NATIVE_HELPER_OP_JASS_UNIT_RESOLVE_ARG = 120
    NATIVE_HELPER_OP_JASS_ABILITY_FIELD_GET = 110
    NATIVE_HELPER_OP_JASS_ABILITY_LEVEL_FIELD_GET = 111
    NATIVE_HELPER_OP_JASS_ABILITY_SCALAR_FIELD_SET = 112
    NATIVE_HELPER_OP_JASS_ABILITY_REAL_FIELD_SET = 113
    NATIVE_HELPER_OP_JASS_ABILITY_SCALAR_LEVEL_FIELD_SET = 114
    NATIVE_HELPER_OP_JASS_ITEM_FIELD_GET = 115
    NATIVE_HELPER_OP_JASS_ITEM_FIELD_SET = 116
    NATIVE_HELPER_OP_JASS_HEAL_LOCAL_UNITS = 117
    NATIVE_HELPER_OP_JASS_CLONE_SELECTED_UNIT = 118
    NATIVE_HELPER_OP_JASS_SELECTED_UNITS = 119
    NATIVE_HELPER_OP_JASS_RESET_LOCAL_COOLDOWNS = 121
    NATIVE_HELPER_OP_PERSISTENT_REGISTER_NATIVE = 130
    NATIVE_HELPER_OP_PERSISTENT_SELECTED_SNAPSHOT = 131
    NATIVE_HELPER_OP_MOVE_SELECTED_GROUP_TO_MOUSE = 132
    NATIVE_HELPER_OP_PERSISTENT_UNIT_SNAPSHOT = 133
    NATIVE_HELPER_OP_JASS_SET_UNIT_STATE = 134
    NATIVE_HELPER_OP_JASS_SET_UNIT_INT = 135
    NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY = 136
    NATIVE_HELPER_OP_SET_BOUND_ITEM_CHARGES = 137
    NATIVE_HELPER_OP_BOUND_ITEM_IDENTITY = 138
    NATIVE_HELPER_OP_BOOTSTRAP_NATIVE_TABLE = 139
    NATIVE_HELPER_OP_QUERY_NATIVE_TABLE = 140
    NATIVE_HELPER_OP_BOUND_ABILITY_METADATA = 141
    NATIVE_HELPER_OP_BOUND_ABILITY_IDENTITY = 142
    NATIVE_HELPER_OP_BOUND_ABILITY_CONTEXT = 143
    NATIVE_HELPER_OP_BOUND_INVENTORY_ITEM = 144
    NATIVE_HELPER_OP_BOUND_ITEM_TYPE = 145
    NATIVE_HELPER_OP_BOUND_ABILITY_LIST = 146
    NATIVE_HELPER_OP_BOUND_UNIT_FIELDS = 147
    NATIVE_HELPER_OP_SET_UNIT_REGEN = 148
    NATIVE_HELPER_OP_BOUND_INVENTORY = 149
    NATIVE_HELPER_OP_REPLACE_INVENTORY_ITEM = 150
    NATIVE_HELPER_OP_REPLACE_INVENTORY_CONTEXT = 151
    NATIVE_HELPER_OP_WRITE_COMPONENT_FIELDS = 152
    NATIVE_HELPER_OP_SET_BOUND_HERO_INT = 153
    NATIVE_HELPER_OP_REPLACE_HERO_SKILL = 154
    NATIVE_HELPER_OP_IDENTITY_UNIT_SNAPSHOT = 155
    NATIVE_HELPER_OP_MANAGE_BOUND_ABILITY = 156
    NATIVE_HELPER_OP_BOUND_DIRECT_ABILITY = 157
    NATIVE_HELPER_OP_START_ABILITY_EFFECT = 158
    NATIVE_HELPER_OP_ABILITY_EFFECT_OPTIONS = 159
    NATIVE_HELPER_OP_FINISH_ABILITY_EFFECT = 160
    NATIVE_HELPER_OP_ENABLE_BOUND_TOGGLE = 161
    NATIVE_HELPER_OP_BOUND_WORLD_EFFECT = 162
    NATIVE_HELPER_OP_SET_BOUND_HERO_BASE = 163
    NATIVE_HELPER_OP_SET_BOUND_HERO_ATTRIBUTES = 164
    NATIVE_HELPER_OP_SET_BOUND_HERO_LEVEL = 165
    NATIVE_HELPER_OP_ADD_BOUND_HERO_SKILL_POINTS = 166
    NATIVE_HELPER_OP_BOUND_INVENTORY_BATCH = 167
    NATIVE_HELPER_OP_BOUND_ITEM_CREATE = 168
    NATIVE_HELPER_OP_BOUND_OWNER_KILL = 169
    NATIVE_HELPER_OP_UNLOCK_TALENT_TIER = 170
    PERSISTENT_NATIVE_SNAPSHOT_QWORDS = 154
    NATIVE_BASIC_FIELD_ARGUMENTS = {
        "hp_current": ("target_hp", "hp"),
        "hp_max": ("max_hp", "hp_max"),
        "mp_current": ("target_mp", "mp"),
        "mp_max": ("max_mp", "mp_max"),
        "hp_regen": ("target_hp_regen", "hp_regen"),
        "mp_regen": ("target_mp_regen", "mp_regen"),
        "x": ("target_x", "x"),
        "y": ("target_y", "y"),
    }
    PERSISTENT_NATIVE_NAMES = (
        "UnitAddAbility",
        "UnitRemoveAbility",
        "SetUnitAbilityLevel",
        "BlzGetUnitAbility",
        "CreateGroup",
        "GetLocalPlayer",
        "GroupEnumUnitsSelected",
        "FirstOfGroup",
        "GroupRemoveUnit",
        "DestroyGroup",
        "GetHandleId",
        "GetOwningPlayer",
        "GetPlayerId",
        "GetUnitTypeId",
        "GetUnitState",
        "GetUnitX",
        "GetUnitY",
        "GetUnitMoveSpeed",
        "GetHeroLevel",
        "SetHeroLevel",
        "UnitStripHeroLevel",
        "SuspendHeroXP",
        "IsSuspendedXP",
        "UnitModifySkillPoints",
        "GetHeroXP",
        "GetHeroStr",
        "GetHeroAgi",
        "GetHeroInt",
        "SetHeroInt",
        "SetHeroStr",
        "SetHeroAgi",
        "UnitItemInSlot",
        "UnitInventorySize",
        "CreateItem",
        "UnitAddItemById",
        "RemoveItem",
        "UnitRemoveItem",
        "IsItemOwned",
        "GetItemTypeId",
        "GetItemCharges",
        "BlzGetUnitAbilityByIndex",
        "BlzGetAbilityId",
        "GetUnitAbilityLevel",
        "SetUnitPosition",
        "SetUnitState",
        "SetItemCharges",
        "BlzGetAbilityRealLevelField",
        "BlzSetAbilityRealLevelField",
        "BlzUnitHideAbility",
        "IssueImmediateOrderById",
        "GetUnitCurrentOrder",
        "GroupEnumUnitsOfPlayer",
        "Player",
        "GetWidgetLife",
        "IsPlayerEnemy",
    )

    def __init__(self, pid: int | None = None):
        self.hwnd, self.pid = find_war3_with_retry(pid)
        self._executable_path = process_executable_path(self.pid)
        self._unit_owner_index: dict[int, int] = {}
        self._unit_owner_index_lock = threading.RLock()
        self._unit_object_index_cache: dict[int, tuple[int, int]] | None = None
        self._selected_handle_addresses = list(self.KNOWN_SELECTED_HANDLE_ADDRESSES)
        self._item_object_cache: dict[int, int] = {}
        self._native_handlers: dict[str, NativeHandler] = dict(
            self._PROCESS_NATIVE_HANDLER_CACHE.get((self.pid, self.hwnd), {})
        )
        self._native_table_region: tuple[int, int] | None = None
        self._native_table_regions: list[tuple[int, int]] = []
        self._native_table_blob: tuple[int, int, bytes] | None = None
        self._native_hero_int_set_address = 0
        self._native_hero_int_get_address = 0
        self._jass_unit_resolver_address = 0
        self._buff_data_constructor_address = 0
        self._pending_direct_effects: set[tuple[int, int]] = set()
        self._pending_direct_effects_lock = threading.Lock()
        self._native_helper_lock = threading.RLock()
        self._persistent_bootstrap_lock = threading.RLock()
        self._native_helper_batch_hook = None
        self._native_helper_batch_thread_id = None
        self._native_helper_persistent_module = None
        self._native_helper_persistent_hook = None
        self._native_helper_persistent_pid = 0
        self._native_helper_persistent_thread_id = 0
        self._persistent_native_initialized = False
        self._persistent_bootstrap_stop = threading.Event()
        self._persistent_bootstrap_thread: threading.Thread | None = None
        self._ability_runtime_templates: dict[tuple[int, int, int], dict[str, object]] = {}
        self._ability_instance_by_data: dict[tuple[int, int, int], AbilityInstance] = {}
        self._selection_player_candidates: list[int] = []
        self._selected_components_cache: dict[tuple[int, int, int], dict[str, tuple[int, int]]] = {}
        self._component_index_cache: dict[int, dict[str, tuple[int, int]]] | None = None
        self._component_index_misses: set[int] = set()
        self._unit_component_layout_confirmed = False
        self._ability_instances_cache: dict[tuple[int, int, int, bool], list[AbilityInstance]] = {}
        self._ability_field_write_disabled = False
        self._item_field_write_disabled = False
        self._selection_manager_offset = self.CPLAYER_SELECTION_MANAGER_OFFSET
        self._selection_list_offsets = (0, self.SELECTION_MANAGER_ALT_LIST_OFFSET)
        self._resource_candidates_by_start: dict[int, list[ResourceCache]] = {}
        self._win10_session_trainer: War3Trainer | None = None
        self._win10_session_identity: tuple[int, int, int] | None = None
        self._last_win10_jass_unit_handle = 0
        self._last_win10_jass_player_handle = 0
        self._last_win10_jass_handle_id = 0
        self._last_win10_native_recovered = 0
        self._last_win10_native_missing: tuple[str, ...] = ()
        self._last_selected_summaries: tuple[UnitSelectionSummary, ...] = ()
        self._last_persistent_native_snapshots: tuple[PersistentNativeUnitSnapshot, ...] = ()
        self._elephant_selection_override: tuple[UnitCandidate, int] | None = None
        # 3.0 keeps the canonical selection manager at CPlayer+0x168.
        self._classic_selection_layout: tuple[int, int, int] | None = None
        self._classic_selection_cache: tuple[tuple[UnitCandidate, int], ...] = ()
        self._classic_object_registry = None
        self._classic_thread_context = None
        self._last_classic_mode = None
        # File presence is not proof of a working 24268 executor. The current
        # DLL still contains the historical bootstrap profile; indexed objects
        # are the primary path, not a fallback after a 30-second native timeout.
        self._native_selection_unavailable = True
        self._native_fallback_reason = "24268 executor handshake not validated; indexed primary path"
        self._classic_resource_cache: ResourceCache | None = None
        self._talent_icon_display = None
        self._talent_icon_display_error = ""
        from war3_game_session import GameSession
        from war3_trainer_session import invalidate_trainer, CACHE_DEFAULTS
        from war3_adapter_state import attach_adapter_cache
        self._session_memory_factory = ProcessMemory
        self._game_session = GameSession(self.pid,self.hwnd)
        attach_adapter_cache(self, self._game_session, CACHE_DEFAULTS, preserve=True)
        self._game_session.on_invalidate(lambda reason: invalidate_trainer(self,reason))
        self._start_persistent_bootstrap()

    def close(self) -> None:
        stop = getattr(self, "_persistent_bootstrap_stop", None)
        if stop is not None:
            stop.set()
        display = getattr(self, "_talent_icon_display", None)
        if display is not None:
            try:
                display.close()
            except Exception as exc:
                self._talent_icon_display_error = f"天赋图标模块关闭未确认，映射引用已保留：{exc}"
            else:
                self._talent_icon_display = None
        engine = getattr(self, "_engine24268", None)
        if engine is not None:
            try:
                engine.close()
            except Exception:
                pass
        with self._native_helper_lock:
            module = self._native_helper_persistent_module
            hook = self._native_helper_persistent_hook
            self._native_helper_persistent_module = None
            self._native_helper_persistent_hook = None
            self._native_helper_persistent_pid = 0
            self._native_helper_persistent_thread_id = 0
            self._persistent_native_initialized = False
            if hook:
                user32.UnhookWindowsHookEx(ctypes.c_void_p(hook))
            if module:
                kernel32.FreeLibrary(ctypes.c_void_p(module))
        session = self._win10_session_trainer
        if isinstance(session, BackupReadWar3Trainer):
            session.close_session_diagnostics()
        self._win10_session_trainer = None
        self._win10_session_identity = None
        thread = getattr(self, "_persistent_bootstrap_thread", None)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=0.25)
        self._persistent_bootstrap_thread = None
        game_session = getattr(self,'_game_session',None)
        if game_session is not None:game_session.close()

    def _process_memory(self, write: bool = False) -> ProcessMemory:
        return ProcessMemory(self.pid, write=write)

    def refresh_window(self, allow_pid_change: bool = False) -> None:
        if is_war3_window(self.hwnd, self.pid):
            return
        old_pid = self.pid
        new_hwnd, new_pid = find_war3_with_retry(
            None if allow_pid_change else self.pid,
            executable_path=getattr(self, "_executable_path", "") or None,
        )
        if new_pid != old_pid:
            display = getattr(self, "_talent_icon_display", None)
            if display is not None:
                try:
                    display.close()
                except Exception as exc:
                    self._talent_icon_display_error = f"旧游戏的天赋图标模块清理未确认，PID 切换已中止：{exc}"
                    raise RuntimeError(self._talent_icon_display_error) from exc
                self._talent_icon_display = None
        self.hwnd, self.pid = new_hwnd, new_pid
        if self.pid != old_pid:
            self._executable_path = process_executable_path(self.pid)
            engine = getattr(self, "_engine24268", None)
            if engine is not None:
                try:
                    engine.close()
                except Exception:
                    pass
            self._close_native_helper_persistent()
            previous_win10_session = self._win10_session_trainer
            if isinstance(previous_win10_session, BackupReadWar3Trainer):
                previous_win10_session.close_session_diagnostics()
            self._unit_owner_index = {}
            self._unit_object_index_cache = None
            self._selected_handle_addresses = list(self.KNOWN_SELECTED_HANDLE_ADDRESSES)
            self._item_object_cache = {}
            self._native_handlers = {}
            self._native_table_region = None
            self._native_table_regions = []
            self._native_table_blob = None
            self._native_hero_int_set_address = 0
            self._native_hero_int_get_address = 0
            self._jass_unit_resolver_address = 0
            self._buff_data_constructor_address = 0
            self._pending_direct_effects = set()
            self._ability_runtime_templates = {}
            self._ability_instance_by_data = {}
            self._selection_player_candidates = []
            self._selected_components_cache = {}
            self._component_index_cache = None
            self._component_index_misses = set()
            self._unit_component_layout_confirmed = False
            self._ability_instances_cache = {}
            self._ability_field_write_disabled = False
            self._item_field_write_disabled = False
            self._selection_manager_offset = self.CPLAYER_SELECTION_MANAGER_OFFSET
            self._selection_list_offsets = (0, self.SELECTION_MANAGER_ALT_LIST_OFFSET)
            self._resource_candidates_by_start = {}
            self._win10_session_trainer = None
            self._win10_session_identity = None
            self._last_win10_jass_unit_handle = 0
            self._last_win10_jass_player_handle = 0
            self._last_win10_jass_handle_id = 0
            self._last_win10_native_recovered = 0
            self._last_win10_native_missing = ()
            self._last_selected_summaries = ()
            self._last_persistent_native_snapshots = ()
            self._elephant_selection_override = None
            self._classic_selection_layout = None
            self._classic_selection_cache = ()
            self._classic_object_registry = None
            self._classic_thread_context = None
            self._last_classic_mode = None
            # A reconnect invalidates execution readiness regardless of DLL presence.
            self._native_selection_unavailable = True
            self._native_fallback_reason = "24268 executor handshake not validated; indexed primary path"
            self._classic_resource_cache = None
            self._start_persistent_bootstrap()

    def _close_native_helper_persistent(self) -> None:
        with self._native_helper_lock:
            module = self._native_helper_persistent_module
            hook = self._native_helper_persistent_hook
            self._native_helper_persistent_module = None
            self._native_helper_persistent_hook = None
            self._native_helper_persistent_pid = 0
            self._native_helper_persistent_thread_id = 0
            self._persistent_native_initialized = False
            if hook:
                user32.UnhookWindowsHookEx(ctypes.c_void_p(hook))
            if module:
                kernel32.FreeLibrary(ctypes.c_void_p(module))

    def _start_persistent_bootstrap(self) -> None:
        previous = getattr(self, "_persistent_bootstrap_stop", None)
        if previous is not None:
            previous.set()
        stop = threading.Event()
        self._persistent_bootstrap_stop = stop
        if getattr(self, "_native_selection_unavailable", False):
            # Do not spawn a retry loop for an unvalidated build/transport.
            stop.set()
            self._persistent_bootstrap_thread = None
            return
        pid = int(self.pid)
        thread = threading.Thread(
            target=self._persistent_bootstrap_loop,
            args=(pid, stop),
            name=f"war3-persistent-bootstrap-{pid}",
            daemon=True,
        )
        self._persistent_bootstrap_thread = thread
        thread.start()

    def _persistent_bootstrap_loop(self, pid: int, stop: threading.Event) -> None:
        if getattr(self, "_native_selection_unavailable", False):
            try:
                with self._process_memory() as memory:
                    selected = self._classic_selection_candidates(memory)
                    self._last_selected_summaries = self._selected_summaries_from_snapshot(
                        memory, selected,
                    )
                stop.wait()
            except Exception:
                # The first explicit read will retry the bounded discovery and
                # surface the detailed failure to the UI.
                return
            return
        native_ready = False
        while not stop.is_set() and int(getattr(self, "pid", 0)) == pid:
            bootstrap_complete = False
            try:
                if not native_ready:
                    with self._persistent_bootstrap_lock:
                        self.persistent_native_init(timeout_ms=15000)
                    native_ready = True
            except Exception:
                native_ready = False
                try:
                    with self._process_memory() as memory:
                        selected = self._classic_selection_candidates(memory)
                        self._last_selected_summaries = self._selected_summaries_from_snapshot(
                            memory, selected,
                        )
                    stop.wait()
                    return
                except Exception:
                    stop.wait(1.0)
                    continue
            try:
                native_selection = self.persistent_native_selected_snapshots(
                    timeout_ms=5000,
                )
                if not native_selection:
                    stop.wait(0.5)
                    continue
                selected = self._selected_candidates_snapshot(
                    None,
                    persistent_snapshots=native_selection,
                )
                self._last_selected_summaries = (
                    self._selected_summaries_from_snapshot(None, selected)
                )
            except Exception:
                # Native registration stays valid when the map is still
                # loading or a selected unit cannot yet be mapped.
                pass
            else:
                bootstrap_complete = True
            if bootstrap_complete:
                # A thread-specific Windows hook is removed when its owner
                # thread exits. Keep this injector thread alive.
                stop.wait()
                return
            stop.wait(1.0)

    def focus(self) -> None:
        focus_window(self.hwnd)

    def send_cheat(self, text: str) -> None:
        post_cheat(self.hwnd, text)

    def _refresh_selected_hero_command_card(self) -> bool:
        try:
            user32.PostMessageW(self.hwnd, WM_KEYDOWN, VK_F1, 0x003B0001)
            time.sleep(0.04)
            user32.PostMessageW(self.hwnd, WM_KEYUP, VK_F1, 0xC03B0001)
            time.sleep(0.12)
            return True
        except Exception:
            return False

    def read_selected_panel(self) -> VisibleUnitPanel:
        selected = self._selected_candidates_snapshot(None)
        if not selected:
            raise RuntimeError("游戏当前没有可操作的选中单位")
        candidate = selected[0][0]
        return self._panel_from_candidate(None, candidate)

    @staticmethod
    def _region_for_address(regions: list[Region], address: int) -> Region | None:
        for region in regions:
            if region.base <= address < region.base + region.size:
                return region
        return None

    @staticmethod
    def _is_executable_image_address(regions: list[Region], address: int) -> bool:
        region = War3Trainer._region_for_address(regions, address)
        return bool(region and (region.protect & 0xFF) in EXECUTABLE_PROTECTS)

    @staticmethod
    def _decode_native_string_from_blob(
        pm: ProcessMemory,
        blob: bytes,
        base: int,
        offset: int,
    ) -> str | None:
        if offset < 0 or offset + 24 > len(blob):
            return None
        ptr, size, capacity = struct.unpack_from("<QQQ", blob, offset)
        if not 0 < size < 80:
            return None
        record = base + offset
        inline_capacity = capacity & 0xFF
        try:
            if ptr == record + 0x18 and inline_capacity >= size:
                end = offset + 0x18 + int(size)
                if end > len(blob):
                    data = pm.read(record + 0x18, int(size))
                else:
                    data = blob[offset + 0x18 : end]
            else:
                if not War3Trainer._sane_heap_ptr(ptr):
                    return None
                if not size <= capacity < 0x1000:
                    return None
                data = pm.read(ptr, int(size))
        except OSError:
            return None
        if any(byte < 32 or byte > 126 for byte in data):
            return None
        try:
            return data.decode("ascii")
        except UnicodeDecodeError:
            return None

    @staticmethod
    def _decode_native_name_from_record(
        pm: ProcessMemory,
        record: int,
        *,
        external_names: dict[int, str] | None = None,
    ) -> str | None:
        try:
            ptr = pm.read_u64(record)
            size = pm.read_u64(record + 8)
            capacity = pm.read_u64(record + 16)
        except OSError:
            return None
        if not 0 < size < 80:
            return None
        try:
            if ptr == record + 0x18 and (capacity & 0xFF) >= size:
                data = pm.read(record + 0x18, int(size))
            elif external_names is not None and ptr in external_names:
                name = external_names[ptr]
                return name if len(name) == size else None
            elif War3Trainer._sane_heap_ptr(ptr) and size <= capacity < 0x1000:
                data = pm.read(ptr, int(size))
            else:
                return None
        except OSError:
            return None
        if any(byte < 32 or byte > 126 for byte in data):
            return None
        try:
            return data.decode("ascii")
        except UnicodeDecodeError:
            return None

    @staticmethod
    def _decode_native_string_from_blob_win10(
        pm: ProcessMemory,
        blob: bytes,
        base: int,
        offset: int,
        external_names: dict[int, str] | None = None,
    ) -> str | None:
        if offset < 0 or offset + 24 > len(blob):
            return None
        ptr, size, capacity = struct.unpack_from("<QQQ", blob, offset)
        if not 0 < size < 80:
            return None
        record = base + offset
        inline_capacity = capacity & 0xFF
        try:
            if ptr == record + 0x18 and inline_capacity >= size:
                end = offset + 0x18 + int(size)
                if end > len(blob):
                    return None
                data = blob[offset + 0x18 : end]
            else:
                if ptr < 0x10000 or ptr > 0x7FFFFFFFFFFF:
                    return None
                known_name = external_names.get(ptr) if external_names is not None else None
                if known_name is not None and len(known_name) == size:
                    data = known_name.encode("ascii")
                elif size <= capacity < 0x1000:
                    data = pm.read(ptr, int(size))
                else:
                    return None
        except OSError:
            return None
        if any(byte < 32 or byte > 126 for byte in data):
            return None
        try:
            return data.decode("ascii")
        except UnicodeDecodeError:
            return None

    @staticmethod
    def _iter_readable_blocks_win10(
        pm: ProcessMemory,
        address: int,
        size: int,
        block_size: int = 4 * 1024 * 1024,
        min_block_size: int = 0x1000,
    ) -> Iterator[tuple[int, bytes]]:
        def live_readable_ranges(
            range_address: int,
            range_length: int,
        ) -> Iterator[tuple[int, int]]:
            query_region = getattr(pm, "_query_region", None)
            if not callable(query_region):
                yield range_address, range_length
                return
            current = range_address
            end = range_address + range_length
            while current < end:
                region = query_region(current)
                if not region:
                    yield current, end - current
                    return
                region_base = int(region.get("base", current))
                region_end = region_base + max(1, int(region.get("size", 1)))
                next_address = min(end, max(current + 1, region_end))
                protect = int(region.get("protect", 0))
                if (
                    int(region.get("state", 0)) == MEM_COMMIT
                    and not protect & (PAGE_NOACCESS | PAGE_GUARD)
                    and (protect & 0xFF) in READABLE_PROTECTS
                ):
                    yield current, next_address - current
                current = next_address

        def read_block(block_address: int, block_length: int) -> Iterator[tuple[int, bytes]]:
            try:
                yield block_address, pm.read(block_address, block_length)
                return
            except OSError:
                if block_length <= min_block_size:
                    return
            split = max(min_block_size, (block_length // 2) & ~(min_block_size - 1))
            if split <= 0 or split >= block_length:
                return
            yield from read_block(block_address, split)
            yield from read_block(block_address + split, block_length - split)

        offset = 0
        while offset < size:
            length = min(block_size, size - offset)
            pending_address = 0
            pending = bytearray()
            for live_address, live_length in live_readable_ranges(
                address + offset,
                length,
            ):
                for piece_address, piece in read_block(live_address, live_length):
                    if pending and pending_address + len(pending) != piece_address:
                        yield pending_address, bytes(pending)
                        pending.clear()
                    if not pending:
                        pending_address = piece_address
                    pending.extend(piece)
            if pending:
                yield pending_address, bytes(pending)
            offset += length

    def _scan_bytes_regions_win10(
        self,
        pm: ProcessMemory,
        pattern: bytes,
        *,
        region_types: tuple[int, ...],
        max_region_size: int | None,
    ) -> list[int]:
        return self._scan_bytes_regions_many_win10(
            pm,
            (pattern,),
            region_types=region_types,
            max_region_size=max_region_size,
        )[pattern]

    def _scan_bytes_regions_many_win10(
        self,
        pm: ProcessMemory,
        patterns: Iterable[bytes],
        *,
        region_types: tuple[int, ...],
        max_region_size: int | None,
    ) -> dict[bytes, list[int]]:
        unique_patterns = tuple(dict.fromkeys(patterns))
        hits = {pattern: [] for pattern in unique_patterns}
        if not unique_patterns:
            return hits
        tail_len = max(len(pattern) for pattern in unique_patterns) - 1
        for region in pm.regions():
            if (
                region.typ not in region_types
                or (max_region_size is not None and region.size > max_region_size)
            ):
                continue
            tail = b""
            previous_end = 0
            for block_address, block in self._iter_readable_blocks_win10(
                pm,
                region.base,
                region.size,
            ):
                if previous_end != block_address:
                    tail = b""
                data = tail + block
                data_base = block_address - len(tail)
                for pattern in unique_patterns:
                    start = 0
                    while True:
                        offset = data.find(pattern, start)
                        if offset < 0:
                            break
                        hit = data_base + offset
                        if hit >= region.base:
                            hits[pattern].append(hit)
                        start = offset + 1
                tail = data[-tail_len:] if tail_len else b""
                previous_end = block_address + len(block)
        return hits

    def _scan_bytes_private_win10(
        self,
        pm: ProcessMemory,
        pattern: bytes,
        max_region_size: int | None = 64 * 1024 * 1024,
    ) -> list[int]:
        hits: list[int] = []
        tail_len = max(0, len(pattern) - 1)
        for region in pm.regions():
            if (
                region.typ != MEM_PRIVATE
                or (max_region_size is not None and region.size > max_region_size)
            ):
                continue
            tail = b""
            previous_end = 0
            for block_address, block in self._iter_readable_blocks_win10(
                pm,
                region.base,
                region.size,
            ):
                if previous_end != block_address:
                    tail = b""
                data = tail + block
                start = 0
                while True:
                    offset = data.find(pattern, start)
                    if offset < 0:
                        break
                    address = block_address - len(tail) + offset
                    if address >= region.base:
                        hits.append(address)
                    start = offset + 1
                tail = data[-tail_len:] if tail_len else b""
                previous_end = block_address + len(block)
        return hits

    def _scan_bytes_private_many_win10(
        self,
        pm: ProcessMemory,
        patterns: Iterable[bytes],
        max_region_size: int | None = 64 * 1024 * 1024,
    ) -> dict[bytes, list[int]]:
        unique_patterns = tuple(dict.fromkeys(patterns))
        hits = {pattern: [] for pattern in unique_patterns}
        if not unique_patterns:
            return hits
        tail_len = max(len(pattern) for pattern in unique_patterns) - 1
        for region in pm.regions():
            if (
                region.typ != MEM_PRIVATE
                or (max_region_size is not None and region.size > max_region_size)
            ):
                continue
            tail = b""
            previous_end = 0
            for block_address, block in self._iter_readable_blocks_win10(
                pm,
                region.base,
                region.size,
            ):
                if previous_end != block_address:
                    tail = b""
                data = tail + block
                data_base = block_address - len(tail)
                for pattern in unique_patterns:
                    start = 0
                    while True:
                        offset = data.find(pattern, start)
                        if offset < 0:
                            break
                        address = data_base + offset
                        if address >= region.base:
                            hits[pattern].append(address)
                        start = offset + 1
                tail = data[-tail_len:] if tail_len else b""
                previous_end = block_address + len(block)
        return hits

    def _scan_native_table_region_candidates_win10(
        self,
        pm: ProcessMemory,
        regions: list[Region],
        max_region_size: int | None,
    ) -> list[Region]:
        pattern = b"UnitAddAbility\0"
        candidates: dict[tuple[int, int], Region] = {}
        for hit in self._scan_bytes_private_win10(
            pm,
            pattern,
            max_region_size=max_region_size,
        ):
            record = hit - 0x18
            region = self._region_for_address(regions, hit)
            if region is None or region.typ != MEM_PRIVATE:
                continue
            try:
                handler = pm.read_u64(record - 8)
                ptr = pm.read_u64(record)
                size = pm.read_u64(record + 8)
            except OSError:
                continue
            if (
                ptr == hit
                and size == len("UnitAddAbility")
                and self._is_executable_image_address(regions, handler)
            ):
                candidates[(region.base, region.size)] = region
        return sorted(candidates.values(), key=lambda item: item.base, reverse=True)

    def _scan_native_table_reference_candidates_win10(
        self,
        pm: ProcessMemory,
        regions: list[Region],
        max_region_size: int | None,
    ) -> list[Region]:
        name = "UnitAddAbility"
        record_types = (MEM_PRIVATE, MEM_MAPPED)
        string_addresses = self._scan_bytes_regions_win10(
            pm,
            name.encode("ascii"),
            region_types=(MEM_PRIVATE, MEM_MAPPED, MEM_IMAGE),
            max_region_size=max_region_size,
        )
        if not string_addresses:
            return []

        string_addresses = list(dict.fromkeys(string_addresses))
        pointer_patterns = {
            struct.pack("<Q", address): address
            for address in string_addresses
        }
        pointer_hits = self._scan_bytes_regions_many_win10(
            pm,
            pointer_patterns,
            region_types=record_types,
            max_region_size=max_region_size,
        )
        candidates: dict[tuple[int, int], Region] = {}
        for pointer_pattern, records in pointer_hits.items():
            string_address = pointer_patterns[pointer_pattern]
            for record in records:
                if record & 7:
                    continue
                region = self._region_for_address(regions, record)
                if region is None or region.typ not in record_types:
                    continue
                try:
                    handler = pm.read_u64(record - 8)
                    ptr = pm.read_u64(record)
                    size = pm.read_u64(record + 8)
                    capacity = pm.read_u64(record + 16)
                except OSError:
                    continue
                if (
                    ptr == string_address
                    and size == len(name)
                    and size <= capacity < 0x1000
                    and self._is_executable_image_address(regions, handler)
                ):
                    candidates[(region.base, region.size)] = region
        return sorted(candidates.values(), key=lambda item: item.base, reverse=True)

    def _find_native_table_regions_win10(
        self,
        pm: ProcessMemory,
        regions: list[Region],
    ) -> list[Region]:
        discovery_error: RuntimeError | None = None
        try:
            return self._find_native_table_regions(pm, regions)
        except RuntimeError as exc:
            discovery_error = exc

        candidates = self._scan_native_table_region_candidates_win10(
            pm,
            regions,
            64 * 1024 * 1024,
        )
        if not candidates:
            candidates = self._scan_native_table_region_candidates_win10(
                pm,
                regions,
                None,
            )
        if not candidates:
            regions = pm.regions(force_refresh=True)
            candidates = self._scan_native_table_reference_candidates_win10(
                pm,
                regions,
                64 * 1024 * 1024,
            )
        if not candidates:
            regions = pm.regions(force_refresh=True)
            candidates = self._scan_native_table_reference_candidates_win10(
                pm,
                regions,
                None,
            )
        if not candidates:
            if discovery_error is not None:
                raise discovery_error
            raise RuntimeError("未找到 Warcraft III native 函数表")

        self._native_table_regions = [
            (region.base, region.size)
            for region in candidates
        ]
        primary = candidates[0]
        self._native_table_region = (primary.base, primary.size)
        self._native_table_blob = None
        return candidates

    def _find_native_table_regions(
        self,
        pm: ProcessMemory,
        regions: list[Region],
    ) -> list[Region]:
        if self._native_table_regions:
            cached: list[Region] = []
            for cached_base, cached_size in self._native_table_regions:
                region = self._region_for_address(regions, cached_base)
                if (
                    region is None
                    or region.base != cached_base
                    or region.size != cached_size
                    or region.typ != MEM_PRIVATE
                ):
                    cached = []
                    break
                cached.append(region)
            if cached:
                return cached

        pattern = b"UnitAddAbility\0"
        candidates: dict[tuple[int, int], Region] = {}
        for hit in pm.scan_bytes_private_parallel(
            pattern,
            max_region_size=2 * 1024 * 1024,
        ):
            record = hit - 0x18
            region = self._region_for_address(regions, hit)
            if region is None or region.typ != MEM_PRIVATE:
                continue
            try:
                handler = pm.read_u64(record - 8)
                ptr = pm.read_u64(record)
                size = pm.read_u64(record + 8)
            except OSError:
                continue
            if (
                ptr == hit
                and size == len("UnitAddAbility")
                and self._is_executable_image_address(regions, handler)
            ):
                candidates[(region.base, region.size)] = region
        if not candidates:
            raise RuntimeError("未找到 Warcraft III native 函数表")

        ordered = sorted(candidates.values(), key=lambda item: item.base, reverse=True)
        self._native_table_regions = [(region.base, region.size) for region in ordered]
        primary = ordered[0]
        self._native_table_region = (primary.base, primary.size)
        try:
            self._native_table_blob = (primary.base, primary.size, pm.read(primary.base, primary.size))
        except OSError:
            self._native_table_blob = None
        return ordered

    def _find_native_table_region(self, pm: ProcessMemory, regions: list[Region]) -> Region:
        return self._find_native_table_regions(pm, regions)[0]

    def _native_table_blob_for_region(self, pm: ProcessMemory, region: Region) -> bytes:
        if self._native_table_blob is not None:
            cached_base, cached_size, cached_blob = self._native_table_blob
            if cached_base == region.base and cached_size == region.size:
                return cached_blob
        blob = pm.read(region.base, region.size)
        self._native_table_blob = (region.base, region.size, blob)
        return blob

    def _native_handler_from_record_blob(
        self,
        pm: ProcessMemory,
        regions: list[Region],
        blob: bytes,
        base: int,
        record_offset: int,
        name: str,
    ) -> NativeHandler | None:
        if record_offset < 8 or record_offset + 24 > len(blob):
            return None
        try:
            handler = struct.unpack_from("<Q", blob, record_offset - 8)[0]
            ptr, size, capacity = struct.unpack_from("<QQQ", blob, record_offset)
        except struct.error:
            return None
        if size != len(name):
            return None
        record = base + record_offset
        inline_capacity = capacity & 0xFF
        try:
            if ptr == record + 0x18 and inline_capacity >= size:
                end = record_offset + 0x18 + int(size)
                if end > len(blob):
                    return None
                data = blob[record_offset + 0x18 : end]
            else:
                if not self._sane_heap_ptr(ptr) or not size <= capacity < 0x1000:
                    return None
                data = pm.read(ptr, int(size))
        except OSError:
            return None
        if data != name.encode("ascii"):
            return None
        if not self._is_executable_image_address(regions, handler):
            return None
        return NativeHandler(name, record, handler)

    def _find_native_handlers_in_table_blob(
        self,
        pm: ProcessMemory,
        regions: list[Region],
        blob: bytes,
        base: int,
        names: set[str],
    ) -> dict[str, NativeHandler]:
        found: dict[str, NativeHandler] = {}
        for name in sorted(names):
            pattern = name.encode("ascii") + b"\0"
            start = 0
            while True:
                hit = blob.find(pattern, start)
                if hit < 0:
                    break
                handler = self._native_handler_from_record_blob(
                    pm,
                    regions,
                    blob,
                    base,
                    hit - 0x18,
                    name,
                )
                if handler is not None:
                    found[name] = handler
                    break
                start = hit + 1
        return found

    def _find_native_handler_by_name_scan(
        self,
        pm: ProcessMemory,
        regions: list[Region],
        name: str,
    ) -> NativeHandler | None:
        pattern = name.encode("ascii") + b"\0"
        for hit in pm.scan_bytes_private(pattern, max_region_size=2 * 1024 * 1024):
            record = hit - 0x18
            region = self._region_for_address(regions, hit)
            if region is None or region.typ != MEM_PRIVATE:
                continue
            try:
                handler = pm.read_u64(record - 8)
                ptr = pm.read_u64(record)
                size = pm.read_u64(record + 8)
            except OSError:
                continue
            if ptr != hit or size != len(name):
                continue
            if self._is_executable_image_address(regions, handler):
                return NativeHandler(name, record, handler)
        return None

    def _find_native_handlers_by_exact_name_scan(
        self,
        pm: ProcessMemory,
        regions: list[Region],
        names: Iterable[str],
    ) -> dict[str, NativeHandler]:
        wanted = tuple(dict.fromkeys(names))
        if not wanted:
            return {}
        patterns = tuple(name.encode("ascii") + b"\0" for name in wanted)
        string_region_types = (MEM_PRIVATE, MEM_MAPPED, MEM_IMAGE)
        record_region_types = (MEM_PRIVATE, MEM_MAPPED)
        if isinstance(pm, Win10ProcessMemory):
            hits = self._scan_bytes_regions_many_win10(
                pm,
                patterns,
                region_types=string_region_types,
                max_region_size=None,
            )
        else:
            hits = pm.scan_bytes_many(
                patterns,
                region_types=string_region_types,
                max_region_size=None,
            )
        by_pattern = {
            name.encode("ascii") + b"\0": name
            for name in wanted
        }
        external_names = {
            address: by_pattern[pattern]
            for pattern, addresses in hits.items()
            for address in addresses
        }
        found: dict[str, NativeHandler] = {}

        def validated_handler(name: str, record: int) -> NativeHandler | None:
            if record & 7:
                return None
            region = self._region_for_address(regions, record)
            if region is None or region.typ not in record_region_types:
                return None
            try:
                handler = pm.read_u64(record - 8)
            except OSError:
                return None
            if not self._is_executable_image_address(regions, handler):
                return None
            if self._decode_native_name_from_record(
                pm,
                record,
                external_names=external_names,
            ) != name:
                return None
            return NativeHandler(name, record, handler)

        for pattern, addresses in hits.items():
            name = by_pattern[pattern]
            for hit in addresses:
                handler = validated_handler(name, hit - 0x18)
                if handler is not None:
                    found[name] = handler
                    break

        unresolved_addresses = {
            address: name
            for address, name in external_names.items()
            if name not in found
        }
        if unresolved_addresses:
            pointer_patterns = {
                struct.pack("<Q", address): address
                for address in unresolved_addresses
            }
            if isinstance(pm, Win10ProcessMemory):
                pointer_hits = self._scan_bytes_regions_many_win10(
                    pm,
                    pointer_patterns,
                    region_types=record_region_types,
                    max_region_size=None,
                )
            else:
                pointer_hits = pm.scan_bytes_many(
                    pointer_patterns,
                    region_types=record_region_types,
                    max_region_size=None,
                )
            for pointer_pattern, records in pointer_hits.items():
                string_address = pointer_patterns[pointer_pattern]
                name = unresolved_addresses[string_address]
                if name in found:
                    continue
                for record in records:
                    handler = validated_handler(name, record)
                    if handler is not None:
                        found[name] = handler
                        break
        return found

    def _recover_native_external_names_win10(
        self,
        pm: ProcessMemory,
        regions: list[Region],
        external_records: Iterable[tuple[int, int]],
        missing: Iterable[str],
    ) -> dict[int, str]:
        missing_by_length: dict[int, set[str]] = {}
        for name in missing:
            missing_by_length.setdefault(len(name), set()).add(name)

        recovered: dict[int, str] = {}
        for pointer, size in external_records:
            names_for_size = missing_by_length.get(size)
            if not names_for_size:
                continue
            region = self._region_for_address(regions, pointer)
            if (
                region is None
                or region.typ not in (MEM_PRIVATE, MEM_MAPPED, MEM_IMAGE)
                or pointer + size > region.base + region.size
            ):
                continue
            try:
                data = pm.read(pointer, size)
                name = data.decode("ascii")
            except (OSError, UnicodeDecodeError):
                continue
            if name in names_for_size:
                recovered[pointer] = name
        return recovered

    def _discover_native_handlers(
        self,
        pm: ProcessMemory,
        names: Iterable[str] | None = None,
    ) -> dict[str, NativeHandler]:
        return self._query_native_table_handlers(names or self.NATIVE_HANDLER_NAMES)

    def _discover_native_handlers_near_table_win10(
        self,
        pm: ProcessMemory,
        names: Iterable[str],
    ) -> dict[str, NativeHandler]:
        return self._query_native_table_handlers(names)

    def _discover_native_handlers_near_table(
        self,
        pm: ProcessMemory,
        names: Iterable[str],
    ) -> dict[str, NativeHandler]:
        return self._query_native_table_handlers(names)

    def verify_native_handlers(self) -> dict[str, NativeHandler]:
        return self._query_native_table_handlers(self.NATIVE_HANDLER_NAMES)

    @staticmethod
    def _read_rel32_call(pm: ProcessMemory, address: int) -> int:
        data = pm.read(address, 5)
        if len(data) != 5 or data[0] != 0xE8:
            raise RuntimeError(f"0x{address:x} 不是预期的 call rel32 指令")
        rel = struct.unpack_from("<i", data, 1)[0]
        return address + 5 + rel

    def _rel32_calls_in_function(
        self,
        pm: ProcessMemory,
        address: int,
        *,
        max_bytes: int = 0xC0,
    ) -> list[int]:
        regions = pm.regions()
        code = pm.read(address, max_bytes)
        calls: list[int] = []
        for instruction in Cs(CS_ARCH_X86, CS_MODE_64).disasm(code, address):
            if instruction.mnemonic.startswith("ret"):
                break
            if instruction.size == 5 and instruction.bytes[0] == 0xE8:
                rel = struct.unpack_from("<i", instruction.bytes, 1)[0]
                target = instruction.address + instruction.size + rel
                if self._is_executable_image_address(regions, target):
                    calls.append(target)
        return calls

    def _rel32_jumps_in_function(
        self,
        pm: ProcessMemory,
        address: int,
        *,
        max_bytes: int = 0x80,
    ) -> list[int]:
        regions = pm.regions()
        code = pm.read(address, max_bytes)
        jumps: list[int] = []
        for instruction in Cs(CS_ARCH_X86, CS_MODE_64).disasm(code, address):
            if instruction.mnemonic.startswith("ret"):
                break
            if instruction.size == 5 and instruction.bytes[0] == 0xE9:
                rel = struct.unpack_from("<i", instruction.bytes, 1)[0]
                target = instruction.address + instruction.size + rel
                if self._is_executable_image_address(regions, target):
                    jumps.append(target)
        return jumps

    def _discover_native_ability_internals(self, pm: ProcessMemory) -> NativeAbilityInternals:
        from war3_game_profile import current_profile
        return current_profile().adapter.legacy._discover_native_ability_internals(self, pm)

    @classmethod
    def _native_helper_command_size(cls) -> int:
        return (
            cls.NATIVE_HELPER_HEADER_STRUCT.size
            + cls.NATIVE_HELPER_OP_STRUCT.size * cls.NATIVE_HELPER_MAX_OPS
        )

    def _native_helper_dll_path(self) -> Path:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        candidate = base / "tools" / "war3_engine_24268.dll"
        if candidate.is_file():
            return candidate
        raise RuntimeError("The 24268 engine execution module has not been built and validated")

    def _native_helper_live_dll_path(self) -> Path:
        return self._native_helper_dll_path()

    def _discover_agent_resolver(self, pm: ProcessMemory, state_handler: int) -> int:
        calls = self._native_function_calls(pm, state_handler)
        if len(calls) != 2:
            return 0
        state_code = pm.read(calls[1], 0x90)
        candidates: list[int] = []
        for offset in range(len(state_code) - 11):
            if state_code[offset:offset + 3] != b"\x48\x81\xc1" or state_code[offset + 7] != 0xE8:
                continue
            getter = self._read_rel32_call(pm, calls[1] + offset + 7)
            instructions = list(Cs(CS_ARCH_X86, CS_MODE_64).disasm(pm.read(getter, 0x20), getter))
            expected = [("mov", "edx, dword ptr [rcx + 0x14]"), ("mov", "ecx, dword ptr [rcx + 0x10]")]
            if [(ins.mnemonic, ins.op_str) for ins in instructions[3:5]] != expected:
                continue
            if len(instructions) > 5 and instructions[5].mnemonic == "call":
                candidates.append(self._read_rel32_call(pm, instructions[5].address))
        if len(candidates) != 2 or candidates[0] != candidates[1]:
            return 0
        resolver = candidates[0]
        if not self._is_executable_image_address(pm.regions(), resolver):
            return 0
        return resolver

    @staticmethod
    def _native_function_calls(pm: ProcessMemory, address: int) -> list[int]:
        calls: list[int] = []
        for instruction in Cs(CS_ARCH_X86, CS_MODE_64).disasm(pm.read(address, 0x180), address):
            if instruction.mnemonic == "ret":
                break
            if instruction.mnemonic == "call" and instruction.op_str.startswith("0x"):
                calls.append(int(instruction.op_str, 16))
        return calls

    def persistent_native_init(self, *, timeout_ms: int = 30000) -> int:
        if getattr(self,"_game_session",None) is not None or getattr(self, "_native_selection_unavailable", False):
            raise RuntimeError("24268 native executor is not validated; legacy bootstrap was not dispatched")
        from diagnostics.war3_native_profile import PROFILE_ID as NATIVE_PROFILE_ID
        with self._persistent_bootstrap_lock:
            if getattr(self, "_persistent_native_initialized", False):
                return len(self.PERSISTENT_NATIVE_NAMES)
            results = self._run_native_helper_ops(
                0, ((self.NATIVE_HELPER_OP_BOOTSTRAP_NATIVE_TABLE, NATIVE_PROFILE_ID, 0, 0, 0),),
                timeout_ms=timeout_ms,
            )
            count = len(self.PERSISTENT_NATIVE_NAMES)
            if len(results) != 1 or results[0].last_error or results[0].result != count:
                raise RuntimeError("DLL native 表初始化结果不完整")
            values = tuple(results[0].extra_results)
            if len(values) != count + 3 or any(not 0x10000 <= value < 0x0000800000000000 for value in values):
                raise RuntimeError("DLL native 表初始化地址无效")
            handlers = {
                name: NativeHandler(name, 0, values[index + 3])
                for index, name in enumerate(self.PERSISTENT_NATIVE_NAMES)
            }
            # No PID cache or heap string records: DLL validated this game context.
            self._native_handlers = handlers
            self._jass_unit_resolver_address = values[0]
            self._persistent_native_initialized = True
            return count

    def register_live_3_native_handlers(self, entries, *, timeout_ms: int = 10000) -> int:
        """Register verified 3.0 handlers without invoking the old bootstrap."""
        from war3_native_table import LiveNativeEntry
        if not entries:
            raise ValueError("3.0 native registration set is empty")
        unknown = [name for name in entries if name not in self.PERSISTENT_NATIVE_NAMES]
        if unknown:
            raise ValueError("3.0 native not present in helper ABI: " + ", ".join(unknown))
        if not all(isinstance(entry, LiveNativeEntry) for entry in entries.values()):
            raise TypeError("entries must contain LiveNativeEntry values")
        ordered = []
        for name, entry in entries.items():
            index = self.PERSISTENT_NATIVE_NAMES.index(name)
            ordered.append((self.NATIVE_HELPER_OP_PERSISTENT_REGISTER_NATIVE,
                            index, entry.handler, 0, 0))
        results = self._run_native_helper_ops(0, ordered, timeout_ms=timeout_ms)
        if len(results) != len(ordered) or any(result.last_error for result in results):
            raise RuntimeError("3.0 native handler registration failed")
        self._native_handlers = {
            name: NativeHandler(name, 0, entries[name].handler) for name in entries
        }
        return len(results)

    def _query_native_table_handlers(self, names: Iterable[str]) -> dict[str, NativeHandler]:
        if getattr(self,"_game_session",None) is not None or getattr(self, "_native_selection_unavailable", False):
            requested = ", ".join(dict.fromkeys(str(name) for name in names))
            raise RuntimeError(
                "Warcraft III 3.0 当前未启用旧版 native helper；"
                f"该功能仍待 3.0 handler 适配：{requested}"
            )
        from diagnostics.war3_native_profile import PROFILE_ID as NATIVE_PROFILE_ID, NATIVE_INDEX
        wanted = tuple(dict.fromkeys(names))
        unknown = [name for name in wanted if name not in NATIVE_INDEX]
        if unknown:
            raise RuntimeError("当前 native 配置不支持：" + ", ".join(unknown))
        self.persistent_native_init()
        missing = [name for name in wanted if name not in self._native_handlers]
        found: dict[str, NativeHandler] = {}
        for start in range(0, len(missing), self.NATIVE_HELPER_MAX_OPS):
            batch = missing[start:start + self.NATIVE_HELPER_MAX_OPS]
            results = self._run_native_helper_ops(0, tuple(
                (self.NATIVE_HELPER_OP_QUERY_NATIVE_TABLE, NATIVE_INDEX[name], 0, NATIVE_PROFILE_ID, 0)
                for name in batch
            ))
            if len(results) != len(batch):
                raise RuntimeError("DLL native 表查询结果数量不符")
            for name, result in zip(batch, results):
                if result.last_error or not 0x10000 <= result.result < 0x0000800000000000:
                    raise RuntimeError("DLL native 表查询失败：" + name)
                found[name] = NativeHandler(name, 0, result.result)
        self._native_handlers.update(found)
        return {name: self._native_handlers[name] for name in wanted}

    def persistent_native_selected_snapshots(
        self,
        *,
        timeout_ms: int = 30000,
    ) -> tuple[PersistentNativeUnitSnapshot, ...]:
        self.persistent_native_init(timeout_ms=timeout_ms)
        snapshot_op = ((self.NATIVE_HELPER_OP_PERSISTENT_SELECTED_SNAPSHOT, 0, 0, 0, 0),)
        try:
            result = self._run_native_helper_ops(
                0,
                snapshot_op,
                timeout_ms=timeout_ms,
            )[0]
        except RuntimeError as exc:
            # A stale in-process hook can survive a game-side reload. Rebuild
            # the registration once for this process when the helper reports
            # ERROR_PROC_NOT_FOUND; other errors must remain visible.
            if "error=127" not in str(exc) and "last_error=127" not in str(exc):
                raise
            self._close_native_helper_persistent()
            self.persistent_native_init(timeout_ms=timeout_ms)
            result = self._run_native_helper_ops(
                0,
                snapshot_op,
                timeout_ms=timeout_ms,
            )[0]
        snapshots = self._parse_persistent_native_snapshots(result)
        self._last_persistent_native_snapshots = snapshots
        return snapshots

    def _classic_selection_candidates(
        self,
        pm: ProcessMemory,
    ) -> list[tuple[UnitCandidate, int]]:
        # The compatibility-shaped selection reader is still used by a few
        # legacy-facing entry points, but its registry, TLS context and list
        # decoder must use the profile already bound to this GameSession.
        # Without this scope those helpers silently consult the process-global
        # default profile (currently 3.0.0.24268) when called outside an
        # Engine24268 dispatch.  That rejects a valid 3.0.1.24332 image
        # before any unit identity is read.
        from war3_game_profile import current_profile, profile_scope

        session = getattr(self, "_game_session", None)
        profile = session.profile if session is not None else current_profile()
        cached_registry = getattr(self, "_classic_object_registry", None)
        cached_profile = getattr(cached_registry, "profile", None)
        cached_digest = getattr(cached_profile, "digest", None)
        # Test doubles and legacy compatibility callers may inject a registry
        # object without a real GameProfile.  Only invalidate an actual
        # profile-bound cache; do not discard such injected readers merely
        # because a mock happens to expose a ``digest`` attribute.
        if isinstance(cached_digest, str) and cached_digest != profile.digest:
            self._classic_object_registry = None
            self._classic_thread_context = None
            self._classic_selection_cache = ()
            self._classic_selection_layout = None
            self._last_classic_mode = None
        with profile_scope(profile):
            return self._classic_selection_candidates_for_profile(pm)

    def _classic_selection_candidates_for_profile(
        self,
        pm: ProcessMemory,
    ) -> list[tuple[UnitCandidate, int]]:
        """Read the actual local player's canonical 3.0 selection and identities."""
        from war3_classic_selection import read_player_selection, SelectionReadError
        from war3_object_registry import ObjectRegistry24268
        from war3_thread_context import GameThreadContext24268

        self._classic_selection_cache = ()
        self._classic_selection_layout = None
        self._last_classic_mode = None
        if self._classic_object_registry is None:
            self._classic_object_registry = ObjectRegistry24268.attach(pm)
        if self._classic_thread_context is None:
            self._classic_thread_context = GameThreadContext24268(
                pm, self._classic_object_registry.base, self.hwnd, self.pid)
        mode = self._classic_thread_context.read_mode(pm)
        self._last_classic_mode = mode
        player = self._classic_object_registry.local_player_for_mode(pm, mode.value)
        selection = read_player_selection(pm, player)

        self._classic_selection_layout = (selection.player, selection.manager, 0)
        if not selection.units:
            self._classic_selection_cache = ()
            return []

        selected = []
        for unit in selection.units:
            handle, owner = self._classic_object_registry.resolve_unit(pm, unit)
            candidate = self._candidate_from_identity(
                pm, handle, owner, unit,
                f"3.0 classic selection player=0x{selection.player:x} count={len(selection.units)}",
                1000, 0,
            )
            if candidate is None:
                from war3_game_profile import current_profile
                from war3_selection_diagnostics import inspect_candidate_failure
                failure = RuntimeError("3.0 classic selection identity validation failed")
                failure.report = {
                    "operation": "selection",
                    "selection_failure": getattr(self, "_last_selection_candidate_failure", {}),
                    "full_handle": handle, "owner": owner, "unit": unit,
                    "game_fingerprint": current_profile().fingerprint,
                }
                try:
                    failure.report["selection_failure_evidence"] = inspect_candidate_failure(
                        pm, owner, unit, handle, current_profile(),
                    )
                except Exception as diagnostic_error:
                    failure.report["diagnostic_capture_error"] = repr(diagnostic_error)
                raise failure
            selected.append((candidate, handle))
        # Identity reads may take time; don't publish a list from an earlier
        # selection if the user has changed it while those reads were running.
        if read_player_selection(pm, selection.player) != selection:
            raise SelectionReadError("Selection changed during identity resolution")
        self._classic_selection_cache = tuple(selected)
        return selected

    def _parse_persistent_native_snapshots(
        self, result: NativeHelperOpResult,
    ) -> tuple[PersistentNativeUnitSnapshot, ...]:
        values = tuple(int(value) for value in result.extra_results)
        count = int(result.result)
        if not 0 <= count <= self.SELECTED_BATCH_MAX_UNITS:
            raise RuntimeError("游戏返回的选中单位数量超过安全上限")
        expected = count * self.PERSISTENT_NATIVE_SNAPSHOT_QWORDS
        if len(values) < expected:
            raise RuntimeError(
                "persistent native snapshot 长度异常："
                f"{len(values)}<{expected}"
            )
        snapshots: list[PersistentNativeUnitSnapshot] = []
        extra_cursor = expected
        for index in range(count):
            row = values[
                index * self.PERSISTENT_NATIVE_SNAPSHOT_QWORDS:
                (index + 1) * self.PERSISTENT_NATIVE_SNAPSHOT_QWORDS
            ]
            if not 0 <= row[153] <= 15:
                raise RuntimeError("Native snapshot contains an invalid component mask")
            scalar = row[:17]
            (
                handle,
                unit_address,
                owner,
                owner_id,
                type_id,
                hp_bits,
                hp_max_bits,
                mp_bits,
                mp_max_bits,
                x_bits,
                y_bits,
                move_speed_bits,
                hero_level,
                hero_xp,
                strength,
                agility,
                intelligence,
            ) = scalar
            item_ids = tuple(row[17:23])
            item_charges = tuple(row[23:29])
            item_handles = tuple(row[29:35])
            item_addresses = tuple(row[35:41])
            ability_count = int(row[41])
            if not 0 <= ability_count <= 4096:
                raise RuntimeError("persistent native snapshot 技能数量超过安全上限")
            base_count = min(48, ability_count)
            ability_ids = tuple(row[42:42 + base_count])
            ability_levels = tuple(row[90:90 + base_count])
            if ability_count > 48:
                overflow = (ability_count - 48) * 2
                if len(values) - extra_cursor < overflow:
                    raise RuntimeError("persistent native snapshot 技能扩展结果长度异常")
                extra_pairs = values[extra_cursor:extra_cursor + overflow]
                extra_cursor += overflow
                ability_ids += tuple(extra_pairs[0::2])
                ability_levels += tuple(extra_pairs[1::2])
            snapshots.append(
                PersistentNativeUnitSnapshot(
                    handle=handle,
                    unit_address=unit_address,
                    owner=owner,
                    owner_id=owner_id,
                    type_id=type_id,
                    hp=struct.unpack("<f", struct.pack("<I", hp_bits & 0xFFFFFFFF))[0],
                    hp_max=struct.unpack("<f", struct.pack("<I", hp_max_bits & 0xFFFFFFFF))[0],
                    mp=struct.unpack("<f", struct.pack("<I", mp_bits & 0xFFFFFFFF))[0],
                    mp_max=struct.unpack("<f", struct.pack("<I", mp_max_bits & 0xFFFFFFFF))[0],
                    x=struct.unpack("<f", struct.pack("<I", x_bits & 0xFFFFFFFF))[0],
                    y=struct.unpack("<f", struct.pack("<I", y_bits & 0xFFFFFFFF))[0],
                    move_speed=struct.unpack("<f", struct.pack("<I", move_speed_bits & 0xFFFFFFFF))[0],
                    hero_level=hero_level & 0xFFFFFFFFFFFFFFFF,
                    hero_xp=hero_xp & 0xFFFFFFFFFFFFFFFF,
                    strength=ctypes.c_int32(strength & 0xFFFFFFFF).value,
                    agility=ctypes.c_int32(agility & 0xFFFFFFFF).value,
                    intelligence=ctypes.c_int32(intelligence & 0xFFFFFFFF).value,
                    item_ids=item_ids,
                    item_charges=item_charges,
                    item_handles=item_handles,
                    item_addresses=item_addresses,
                    item_full_handles=tuple(row[143:149]),
                    component_mask=int(row[153]),
                    ability_ids=ability_ids,
                    ability_levels=ability_levels,
                    full_handle=int(row[138]),
                    owner_address=int(row[139]),
                    base_strength=ctypes.c_int32(row[140] & 0xFFFFFFFF).value,
                    base_agility=ctypes.c_int32(row[141] & 0xFFFFFFFF).value,
                    base_intelligence=ctypes.c_int32(row[142] & 0xFFFFFFFF).value,
                    hp_property=int(row[149]),
                    mp_property=int(row[150]),
                    hp_regen=self._float_from_bits(row[151]) if row[149] else None,
                    mp_regen=self._float_from_bits(row[152]) if row[150] else None,
                )
            )
        if extra_cursor != len(values):
            raise RuntimeError(
                "persistent native snapshot 附加结果长度异常："
                f"{len(values) - extra_cursor}"
            )
        return tuple(snapshots)

    def _refresh_native_candidate(self, candidate: UnitCandidate) -> UnitCandidate:
        previous = self._native_snapshot_for_candidate(candidate)
        if previous is None:
            return candidate
        self.persistent_native_init()
        result = self._run_native_helper_ops(previous.handle, ((
            self.NATIVE_HELPER_OP_PERSISTENT_UNIT_SNAPSHOT, 0,
            candidate.unit_address, candidate.handle, candidate.owner_address,
        ),))[0]
        snapshots = self._parse_persistent_native_snapshots(result)
        if len(snapshots) != 1:
            raise RuntimeError("当前 native 快照已经失效，请重新读取选中单位")
        current = snapshots[0]
        if (current.handle, current.full_handle, current.owner_address, current.unit_address) != (
            previous.handle, candidate.handle, candidate.owner_address, candidate.unit_address
        ):
            raise RuntimeError("当前 native 快照已经失效，请重新读取选中单位")
        # Refresh property metadata too: a unit can replace its properties
        # without changing its own generation.
        refreshed = self._candidate_from_native_snapshot(None, current)
        if refreshed is None:
            raise RuntimeError("当前 native 快照已经失效，请重新读取选中单位")
        return replace(refreshed, score=candidate.score, note=candidate.note,
                       selection_slot_address=candidate.selection_slot_address)

    def _native_helper_command_path(self) -> Path:
        return Path(tempfile.gettempdir()) / f"war3_reforged_native_{self.pid}.bin"

    @staticmethod
    def _write_native_helper_command(path: Path, payload: bytes) -> None:
        last_error: PermissionError | None = None
        for attempt in range(8):
            try:
                path.write_bytes(payload)
                return
            except PermissionError as exc:
                last_error = exc
                if attempt == 0:
                    try:
                        path.chmod(0o600)
                    except OSError:
                        pass
                time.sleep(min(0.01 * (attempt + 1), 0.05))
        assert last_error is not None
        raise last_error

    @staticmethod
    def _read_native_helper_command(path: Path) -> bytes | None:
        try:
            return path.read_bytes()
        except PermissionError:
            return None

    def _pack_native_helper_command(
        self,
        unit_address: int,
        ops: Iterable[tuple[int, int, int, int, int]],
    ) -> bytes:
        op_list = list(ops)
        if not 0 < len(op_list) <= self.NATIVE_HELPER_MAX_OPS:
            raise RuntimeError("native helper 操作数量无效")
        payload = bytearray(
            self.NATIVE_HELPER_HEADER_STRUCT.pack(
                self.NATIVE_HELPER_MAGIC,
                self.NATIVE_HELPER_VERSION,
                self.NATIVE_HELPER_STATUS_PENDING,
                len(op_list),
                unit_address & 0xFFFFFFFFFFFFFFFF,
                0,
                0,
            )
        )
        for kind, rawcode, handler, arg0, arg1 in op_list:
            payload += self.NATIVE_HELPER_OP_STRUCT.pack(
                kind & 0xFFFFFFFF,
                rawcode & 0xFFFFFFFF,
                handler & 0xFFFFFFFFFFFFFFFF,
                arg0 & 0xFFFFFFFFFFFFFFFF,
                arg1 & 0xFFFFFFFFFFFFFFFF,
                0,
                0,
                0,
            )
        payload += b"\x00" * (
            self.NATIVE_HELPER_OP_STRUCT.size * (self.NATIVE_HELPER_MAX_OPS - len(op_list))
        )
        return bytes(payload)

    def _parse_native_helper_results(self, data: bytes, op_count: int) -> list[NativeHelperOpResult]:
        if len(data) < self._native_helper_command_size():
            raise RuntimeError("native helper 返回数据长度异常")
        magic, version, status, actual_count, _unit, last_error, extra_count = (
            self.NATIVE_HELPER_HEADER_STRUCT.unpack_from(data, 0)
        )
        if magic != self.NATIVE_HELPER_MAGIC or version != self.NATIVE_HELPER_VERSION:
            raise RuntimeError("native helper 返回协议不匹配")
        if status != self.NATIVE_HELPER_STATUS_OK:
            details = ""
            for index in range(min(actual_count, self.NATIVE_HELPER_MAX_OPS)):
                operation = self.NATIVE_HELPER_OP_STRUCT.unpack_from(
                    data, self.NATIVE_HELPER_HEADER_STRUCT.size + index * self.NATIVE_HELPER_OP_STRUCT.size)
                if operation[0] == self.NATIVE_HELPER_OP_MANAGE_BOUND_ABILITY and operation[6]:
                    actual_level = str(operation[4]) if operation[7] & 1 else "unavailable"
                    details = (f" ability={format_rawcode(operation[1])} action={operation[2]}"
                               f" requested_level={operation[3]} actual_level={actual_level}")
                    break
            if actual_count == op_count == 2:
                operation = self.NATIVE_HELPER_OP_STRUCT.unpack_from(
                    data, self.NATIVE_HELPER_HEADER_STRUCT.size + self.NATIVE_HELPER_OP_STRUCT.size)
                if operation[0] == self.NATIVE_HELPER_OP_REPLACE_HERO_SKILL:
                    details = f" skill_phase={operation[5]} skill_cleanup_error={operation[7]}"
                elif operation[0] == self.NATIVE_HELPER_OP_BOUND_DIRECT_ABILITY:
                    details = f" direct_effect_completed={operation[5]} direct_cleanup_error={operation[7]}"
                elif operation[0] == self.NATIVE_HELPER_OP_FINISH_ABILITY_EFFECT:
                    details = f" effect_token={operation[2]} effect_cleanup_error={operation[7]}"
                elif operation[0] == self.NATIVE_HELPER_OP_ENABLE_BOUND_TOGGLE:
                    details = f" toggle_order_accepted={operation[5]} toggle_cleanup_error={operation[7]}"
                elif operation[0] == self.NATIVE_HELPER_OP_BOUND_WORLD_EFFECT:
                    details = f" world_attempts={operation[5] >> 32} world_callbacks={operation[5] & 0xFFFFFFFF} world_cleanup_error={operation[7]}"
                elif operation[0] == self.NATIVE_HELPER_OP_SET_BOUND_HERO_LEVEL:
                    details = f" xp_restore_error={operation[4]}"
                elif operation[0] == self.NATIVE_HELPER_OP_BOUND_INVENTORY_BATCH:
                    details = f" inventory_verified={operation[5]}"
                elif operation[0] == self.NATIVE_HELPER_OP_BOUND_ITEM_CREATE:
                    details = f" item_creations_acknowledged={operation[5]} last_created_handle={operation[3]}"
                elif operation[0] == self.NATIVE_HELPER_OP_BOUND_OWNER_KILL:
                    details = f" owner_kill_callbacks={operation[5]} owner_kill_skipped={operation[3]} owner_kill_cleanup_error={operation[7]}"
            if actual_count == op_count == 3:
                base, size = self.NATIVE_HELPER_HEADER_STRUCT.size, self.NATIVE_HELPER_OP_STRUCT.size
                operation = self.NATIVE_HELPER_OP_STRUCT.unpack_from(data, base + size)
                context = self.NATIVE_HELPER_OP_STRUCT.unpack_from(data, base + 2*size)
                if operation[0] == self.NATIVE_HELPER_OP_START_ABILITY_EFFECT:
                    details = f" effect_token={operation[5]} effect_executed={operation[3]} effect_cleanup_error={operation[7]}"
                if (operation[0] == self.NATIVE_HELPER_OP_REPLACE_INVENTORY_ITEM
                        and context[0] == self.NATIVE_HELPER_OP_REPLACE_INVENTORY_CONTEXT):
                    details = f" item_recovery_error={context[5]} item_cleanup_error={context[4]}"
            phase = ""
            if actual_count >= 2:
                phase_value = self.NATIVE_HELPER_OP_STRUCT.unpack_from(
                    data, self.NATIVE_HELPER_HEADER_STRUCT.size + self.NATIVE_HELPER_OP_STRUCT.size
                )[5]
                if phase_value:
                    phase = f" clone_phase=0x{phase_value:x}"
            raise RuntimeError(f"native helper 执行失败：status={status} last_error={last_error}{phase}{details}")
        if actual_count != op_count:
            raise RuntimeError(f"native helper 返回操作数量异常：{actual_count}!={op_count}")
        extra_offset = self._native_helper_command_size()
        extra_size = int(extra_count) * 8
        if len(data) < extra_offset + extra_size:
            raise RuntimeError("native helper 附加结果长度异常")
        extra_results = (
            tuple(struct.unpack_from(f"<{extra_count}Q", data, extra_offset))
            if extra_count
            else ()
        )
        results: list[NativeHelperOpResult] = []
        base = self.NATIVE_HELPER_HEADER_STRUCT.size
        for index in range(op_count):
            offset = base + index * self.NATIVE_HELPER_OP_STRUCT.size
            kind, _rawcode, _handler, arg0, arg1, result, op_error, _reserved = (
                self.NATIVE_HELPER_OP_STRUCT.unpack_from(data, offset)
            )
            if op_error:
                raise RuntimeError(f"native helper 操作 {index + 1} 失败：error={op_error}")
            results.append(NativeHelperOpResult(
                kind=kind,
                result=result,
                last_error=op_error,
                arg0=arg0,
                arg1=arg1,
                extra_results=extra_results if index == 0 else (),
            ))
        return results

    def _run_native_helper_ops(
        self,
        unit_address: int,
        ops: Iterable[tuple[int, int, int, int, int]],
        *,
        timeout_ms: int = 10000,
    ) -> list[NativeHelperOpResult]:
        op_list = list(ops)
        talent_unlock_only = bool(op_list) and all(
            int(operation[0]) in {
                self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY,
                self.NATIVE_HELPER_OP_UNLOCK_TALENT_TIER,
            }
            for operation in op_list
        ) and any(
            int(operation[0]) == self.NATIVE_HELPER_OP_UNLOCK_TALENT_TIER
            for operation in op_list
        )
        if getattr(self,"_game_session",None) is not None or (getattr(self, "_native_selection_unavailable", False) and not talent_unlock_only):
            raise RuntimeError(
                "Warcraft III 3.0 当前未启用旧版 native helper；"
                "该操作尚未迁移到 3.0 经典链路"
            )
        wait_ms = max(5000, min(300000, int(timeout_ms) + 5000))
        try:
            with self._native_helper_lock:
                self._ensure_native_helper_persistent_hook(wait_ms=wait_ms)
                with self._native_helper_transaction(wait_ms=wait_ms):
                    return self._run_native_helper_ops_locked(
                        unit_address,
                        op_list,
                        timeout_ms=timeout_ms,
                    )
        except Exception as exc:
            if isinstance(exc, TimeoutError):
                # A stalled 3.0 executor must not be reused for later writes.
                # Mark this trainer session unavailable so read-only callers
                # can use the indexed/classic fallback and mutators fail fast.
                self._native_selection_unavailable = True
                self._native_fallback_reason = f"engine executor timeout: {exc}"
            self._write_native_helper_failure_log(unit_address, exc)
            raise

    def _write_native_helper_failure_log(self, unit_address: int, exc: BaseException) -> None:
        try:
            logger = Win10ReadLogger(int(self.pid), prefix="native-helper")
            logger.log(
                "native_helper_failure",
                unit_address=f"0x{int(unit_address):x}",
                pid=int(self.pid),
                helper_dll=str(self._native_helper_dll_path()),
                protocol=int(self.NATIVE_HELPER_VERSION),
            )
            logger.log_traceback("native_helper_exception", exc)
            self._last_native_helper_log_path = str(logger.latest_path)
            logger.close()
        except Exception:
            # A diagnostic failure must never hide the original helper error.
            pass

    @contextmanager
    def _native_helper_transaction(self, *, wait_ms: int = 300000) -> Iterator[None]:
        if (
            self._native_helper_batch_hook is not None
            and self._native_helper_batch_thread_id == threading.get_ident()
        ):
            yield
            return
        with self._native_helper_lock:
            mutex = kernel32.CreateMutexW(
                None,
                False,
                f"Local\\War3ReforgedTrainer.NativeHelper.{self.pid}",
            )
            if not mutex:
                raise ctypes.WinError(ctypes.get_last_error())
            wait_result = int(kernel32.WaitForSingleObject(
                mutex,
                max(5000, min(300000, int(wait_ms))),
            ))
            if wait_result not in (WAIT_OBJECT_0, WAIT_ABANDONED):
                kernel32.CloseHandle(mutex)
                if wait_result == WAIT_TIMEOUT:
                    raise TimeoutError("等待 Warcraft native helper 事务锁超时")
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                yield
            finally:
                release_error = 0
                if not kernel32.ReleaseMutex(mutex):
                    release_error = ctypes.get_last_error()
                kernel32.CloseHandle(mutex)
                if release_error:
                    raise ctypes.WinError(release_error)

    @contextmanager
    def _native_helper_batch_transaction(self, *, wait_ms: int = 300000) -> Iterator[None]:
        with self._native_helper_lock:
            if (
                self._native_helper_persistent_hook
                and self._native_helper_persistent_module
                and self._native_helper_persistent_pid == self.pid
            ):
                mutex = kernel32.CreateMutexW(
                    None,
                    False,
                    f"Local\\War3ReforgedTrainer.NativeHelper.{self.pid}",
                )
                if not mutex:
                    raise ctypes.WinError(ctypes.get_last_error())
                wait_result = int(kernel32.WaitForSingleObject(
                    mutex,
                    max(5000, min(300000, int(wait_ms))),
                ))
                if wait_result not in (WAIT_OBJECT_0, WAIT_ABANDONED):
                    kernel32.CloseHandle(mutex)
                    if wait_result == WAIT_TIMEOUT:
                        raise TimeoutError("等待 Warcraft native helper 批事务锁超时")
                    raise ctypes.WinError(ctypes.get_last_error())
                self._native_helper_batch_hook = self._native_helper_persistent_hook
                self._native_helper_batch_thread_id = threading.get_ident()
                try:
                    yield
                finally:
                    self._native_helper_batch_hook = None
                    self._native_helper_batch_thread_id = None
                    release_error = 0
                    if not kernel32.ReleaseMutex(mutex):
                        release_error = ctypes.get_last_error()
                    kernel32.CloseHandle(mutex)
                    if release_error:
                        raise ctypes.WinError(release_error)
                return
            mutex = kernel32.CreateMutexW(
                None,
                False,
                f"Local\\War3ReforgedTrainer.NativeHelper.{self.pid}",
            )
            if not mutex:
                raise ctypes.WinError(ctypes.get_last_error())
            wait_result = int(kernel32.WaitForSingleObject(
                mutex,
                max(5000, min(300000, int(wait_ms))),
            ))
            if wait_result not in (WAIT_OBJECT_0, WAIT_ABANDONED):
                kernel32.CloseHandle(mutex)
                if wait_result == WAIT_TIMEOUT:
                    raise TimeoutError("等待 Warcraft native helper 批事务锁超时")
                raise ctypes.WinError(ctypes.get_last_error())

            module = kernel32.LoadLibraryW(str(self._native_helper_dll_path()))
            if not module:
                kernel32.ReleaseMutex(mutex)
                kernel32.CloseHandle(mutex)
                raise ctypes.WinError(ctypes.get_last_error())
            hook = None
            try:
                proc = kernel32.GetProcAddress(module, b"War3HookProc")
                if not proc:
                    raise ctypes.WinError(ctypes.get_last_error())
                pid = ctypes.c_ulong()
                tid = user32.GetWindowThreadProcessId(
                    ctypes.c_void_p(self.hwnd),
                    ctypes.byref(pid),
                )
                if not tid or int(pid.value) != self.pid:
                    raise RuntimeError("Warcraft III 窗口线程已失效")
                hook = user32.SetWindowsHookExW(
                    WH_CALLWNDPROC,
                    ctypes.c_void_p(proc),
                    ctypes.c_void_p(module),
                    int(tid),
                )
                if not hook:
                    raise ctypes.WinError(ctypes.get_last_error())
                self._native_helper_batch_hook = hook
                self._native_helper_batch_thread_id = threading.get_ident()
                try:
                    yield
                finally:
                    self._native_helper_batch_hook = None
                    self._native_helper_batch_thread_id = None
                    user32.UnhookWindowsHookEx(hook)
            finally:
                kernel32.FreeLibrary(module)
                release_error = 0
                if not kernel32.ReleaseMutex(mutex):
                    release_error = ctypes.get_last_error()
                kernel32.CloseHandle(mutex)
                if release_error:
                    raise ctypes.WinError(release_error)

    def _ensure_native_helper_persistent_hook(self, *, wait_ms: int = 300000) -> None:
        if (
            self._native_helper_persistent_hook
            and self._native_helper_persistent_module
            and self._native_helper_persistent_pid == self.pid
        ):
            return
        self._close_native_helper_persistent()
        mutex = kernel32.CreateMutexW(
            None,
            False,
            f"Local\\War3ReforgedTrainer.NativeHelper.{self.pid}",
        )
        if not mutex:
            raise ctypes.WinError(ctypes.get_last_error())
        wait_result = int(kernel32.WaitForSingleObject(
            mutex,
            max(5000, min(300000, int(wait_ms))),
        ))
        if wait_result not in (WAIT_OBJECT_0, WAIT_ABANDONED):
            kernel32.CloseHandle(mutex)
            if wait_result == WAIT_TIMEOUT:
                raise TimeoutError("等待 Warcraft native helper 常驻事务锁超时")
            raise ctypes.WinError(ctypes.get_last_error())
        module = None
        hook = None
        try:
            module = kernel32.LoadLibraryW(str(self._native_helper_dll_path()))
            if not module:
                raise ctypes.WinError(ctypes.get_last_error())
            proc = kernel32.GetProcAddress(module, b"War3HookProc")
            if not proc:
                raise ctypes.WinError(ctypes.get_last_error())
            pid = ctypes.c_ulong()
            tid = user32.GetWindowThreadProcessId(
                ctypes.c_void_p(self.hwnd),
                ctypes.byref(pid),
            )
            if not tid or int(pid.value) != self.pid:
                raise RuntimeError("Warcraft III 窗口线程已失效")
            target_tid = int(getattr(self, "_native_helper_target_thread_id", tid))
            hook = user32.SetWindowsHookExW(
                WH_CALLWNDPROC,
                ctypes.c_void_p(proc),
                ctypes.c_void_p(module),
                target_tid,
            )
            if not hook:
                raise ctypes.WinError(ctypes.get_last_error())
            self._native_helper_persistent_module = module
            self._native_helper_persistent_hook = hook
            self._native_helper_persistent_pid = self.pid
            self._native_helper_persistent_thread_id = target_tid
            module = None
            hook = None
        finally:
            if hook:
                user32.UnhookWindowsHookEx(ctypes.c_void_p(hook))
            if module:
                kernel32.FreeLibrary(ctypes.c_void_p(module))
            release_error = 0
            if not kernel32.ReleaseMutex(mutex):
                release_error = ctypes.get_last_error()
            kernel32.CloseHandle(mutex)
            if release_error:
                raise ctypes.WinError(release_error)

    def _wait_native_helper_result(
        self,
        command_path: Path,
        hook: int,
        op_count: int,
        timeout_ms: int,
    ) -> list[NativeHelperOpResult]:
        deadline = time.monotonic() + (timeout_ms / 1000.0)
        last_status = self.NATIVE_HELPER_STATUS_PENDING
        while time.monotonic() < deadline:
            if getattr(self, "_native_helper_message_mode", "send") == "post":
                sent = user32.PostThreadMessageW(
                    int(self._native_helper_persistent_thread_id), WM_NULL, 0, 0,
                )
            else:
                message_result = ctypes.c_void_p()
                sent = user32.SendMessageTimeoutW(
                    ctypes.c_void_p(self.hwnd),
                    WM_NULL,
                    None,
                    None,
                    SMTO_ABORTIFHUNG,
                    150,
                    ctypes.byref(message_result),
                )
            data = self._read_native_helper_command(command_path)
            if data is None:
                time.sleep(0.01)
                continue
            last_status = struct.unpack_from("<I", data, 8)[0]
            if last_status != self.NATIVE_HELPER_STATUS_PENDING:
                return self._parse_native_helper_results(data, op_count)
            if not sent:
                # The hook normally completes on the same UI-thread message
                # dispatch. A 20 ms polling quantum made every native action
                # visibly lag, and multiplied that lag for legacy per-unit
                # batch actions. Keep a small yield for CPU fairness while
                # retaining the outer timeout as the hang guard.
                time.sleep(0.002)
                continue
            time.sleep(0.002)
        raise TimeoutError(f"native helper 执行超时：status={last_status}")

    def _run_native_helper_ops_locked(
        self,
        unit_address: int,
        ops: Iterable[tuple[int, int, int, int, int]],
        *,
        timeout_ms: int = 10000,
    ) -> list[NativeHelperOpResult]:
        op_list = list(ops)
        allowed_kinds = {
            self.NATIVE_HELPER_OP_INTERNAL_ABILITY_BEGIN,
            self.NATIVE_HELPER_OP_INTERNAL_ABILITY_FIND,
            self.NATIVE_HELPER_OP_INTERNAL_ABILITY_ADD,
            self.NATIVE_HELPER_OP_INTERNAL_ABILITY_END,
            self.NATIVE_HELPER_OP_INTERNAL_ABILITY_REFRESH,
            self.NATIVE_HELPER_OP_INTERNAL_ABILITY_REMOVE,
            self.NATIVE_HELPER_OP_SET_ITEM_CHARGES,
            self.NATIVE_HELPER_OP_REMOVE_ITEM_SLOT,
            self.NATIVE_HELPER_OP_ADD_ITEM_TO_SLOT_BY_ID,
            self.NATIVE_HELPER_OP_GET_ITEM_TYPE_IN_SLOT,
            self.NATIVE_HELPER_OP_SET_HERO_INT,
            self.NATIVE_HELPER_OP_GET_HERO_INT,
            self.NATIVE_HELPER_OP_JASS_SELECTED_UNIT,
            self.NATIVE_HELPER_OP_JASS_SELECTED_UNIT_ARG,
            self.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_QUERY,
            self.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_SET,
            self.NATIVE_HELPER_OP_JASS_PLAYER_STATE_QUERY,
            self.NATIVE_HELPER_OP_JASS_PLAYER_STATE_SET,
            self.NATIVE_HELPER_OP_JASS_UNIT_VOID,
            self.NATIVE_HELPER_OP_JASS_UNIT_BOOL,
            self.NATIVE_HELPER_OP_JASS_UNIT_INT_BOOL,
            self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE,
            self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE_LEVEL,
            self.NATIVE_HELPER_OP_JASS_UNIT_SCALE,
            self.NATIVE_HELPER_OP_JASS_WORLD_BOOL,
            self.NATIVE_HELPER_OP_JASS_UNIT_INT_QUERY,
            self.NATIVE_HELPER_OP_JASS_EXPLODE_UNIT,
            self.NATIVE_HELPER_OP_JASS_TAKE_OWNERSHIP,
            self.NATIVE_HELPER_OP_JASS_CREATE_LOCAL_UNIT,
            self.NATIVE_HELPER_OP_JASS_CLEAR_INVENTORY,
            self.NATIVE_HELPER_OP_JASS_SET_LOCAL_TECH,
            self.NATIVE_HELPER_OP_JASS_SET_LOCAL_XP_RATE,
            self.NATIVE_HELPER_OP_JASS_KILL_OWNER_UNITS,
            self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
            self.NATIVE_HELPER_OP_JASS_PEACE_MODE,
            self.NATIVE_HELPER_OP_JASS_WORLD_INT_QUERY,
            self.NATIVE_HELPER_OP_JASS_FOG_BOOL,
            self.NATIVE_HELPER_OP_JASS_SET_INVENTORY_CHARGES,
            self.NATIVE_HELPER_OP_JASS_DUPLICATE_INVENTORY,
            self.NATIVE_HELPER_OP_JASS_DROP_INVENTORY,
            self.NATIVE_HELPER_OP_JASS_REMOVE_ALL_ABILITIES,
            self.NATIVE_HELPER_OP_QUERY_WORLD_POINT,
            self.NATIVE_HELPER_OP_JASS_SET_UNIT_POSITION,
            self.NATIVE_HELPER_OP_CREATE_ALL_ITEMS,
            self.NATIVE_HELPER_OP_REMOVE_ITEM_HANDLES,
            self.NATIVE_HELPER_OP_REMOVE_ITEM_HANDLES_ARG,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_TARGET,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_IMMEDIATE,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_POINT,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_NOARG_DERIVED,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_BUFF,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_ENUM,
            self.NATIVE_HELPER_OP_JASS_ABILITY_REAL_LEVEL_FIELD_SET,
            self.NATIVE_HELPER_OP_JASS_UNIT_RESOLVE,
            self.NATIVE_HELPER_OP_JASS_UNIT_RESOLVE_ARG,
            self.NATIVE_HELPER_OP_JASS_ABILITY_FIELD_GET,
            self.NATIVE_HELPER_OP_JASS_ABILITY_LEVEL_FIELD_GET,
            self.NATIVE_HELPER_OP_JASS_ABILITY_SCALAR_FIELD_SET,
            self.NATIVE_HELPER_OP_JASS_ABILITY_REAL_FIELD_SET,
            self.NATIVE_HELPER_OP_JASS_ABILITY_SCALAR_LEVEL_FIELD_SET,
            self.NATIVE_HELPER_OP_JASS_ITEM_FIELD_GET,
            self.NATIVE_HELPER_OP_JASS_ITEM_FIELD_SET,
            self.NATIVE_HELPER_OP_JASS_HEAL_LOCAL_UNITS,
            self.NATIVE_HELPER_OP_JASS_CLONE_SELECTED_UNIT,
            self.NATIVE_HELPER_OP_JASS_SELECTED_UNITS,
            self.NATIVE_HELPER_OP_JASS_RESET_LOCAL_COOLDOWNS,
            self.NATIVE_HELPER_OP_PERSISTENT_REGISTER_NATIVE,
            self.NATIVE_HELPER_OP_PERSISTENT_SELECTED_SNAPSHOT,
            self.NATIVE_HELPER_OP_MOVE_SELECTED_GROUP_TO_MOUSE,
            self.NATIVE_HELPER_OP_PERSISTENT_UNIT_SNAPSHOT,
            self.NATIVE_HELPER_OP_JASS_SET_UNIT_STATE,
            self.NATIVE_HELPER_OP_JASS_SET_UNIT_INT,
            self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY,
            self.NATIVE_HELPER_OP_SET_BOUND_ITEM_CHARGES,
            self.NATIVE_HELPER_OP_BOUND_ITEM_IDENTITY,
            self.NATIVE_HELPER_OP_BOOTSTRAP_NATIVE_TABLE,
            self.NATIVE_HELPER_OP_QUERY_NATIVE_TABLE,
            self.NATIVE_HELPER_OP_BOUND_ABILITY_METADATA,
            self.NATIVE_HELPER_OP_BOUND_ABILITY_IDENTITY,
            self.NATIVE_HELPER_OP_BOUND_ABILITY_CONTEXT,
            self.NATIVE_HELPER_OP_BOUND_ABILITY_LIST,
            self.NATIVE_HELPER_OP_BOUND_UNIT_FIELDS,
            self.NATIVE_HELPER_OP_SET_UNIT_REGEN,
            self.NATIVE_HELPER_OP_BOUND_INVENTORY,
            self.NATIVE_HELPER_OP_REPLACE_INVENTORY_ITEM,
            self.NATIVE_HELPER_OP_REPLACE_INVENTORY_CONTEXT,
            self.NATIVE_HELPER_OP_WRITE_COMPONENT_FIELDS,
            self.NATIVE_HELPER_OP_SET_BOUND_HERO_INT,
            self.NATIVE_HELPER_OP_REPLACE_HERO_SKILL,
            self.NATIVE_HELPER_OP_IDENTITY_UNIT_SNAPSHOT,
            self.NATIVE_HELPER_OP_MANAGE_BOUND_ABILITY,
            self.NATIVE_HELPER_OP_BOUND_DIRECT_ABILITY,
            self.NATIVE_HELPER_OP_START_ABILITY_EFFECT,
            self.NATIVE_HELPER_OP_ABILITY_EFFECT_OPTIONS,
            self.NATIVE_HELPER_OP_FINISH_ABILITY_EFFECT,
            self.NATIVE_HELPER_OP_ENABLE_BOUND_TOGGLE,
            self.NATIVE_HELPER_OP_BOUND_WORLD_EFFECT,
            self.NATIVE_HELPER_OP_SET_BOUND_HERO_BASE,
            self.NATIVE_HELPER_OP_SET_BOUND_HERO_ATTRIBUTES,
            self.NATIVE_HELPER_OP_SET_BOUND_HERO_LEVEL,
            self.NATIVE_HELPER_OP_ADD_BOUND_HERO_SKILL_POINTS,
            self.NATIVE_HELPER_OP_BOUND_INVENTORY_BATCH,
            self.NATIVE_HELPER_OP_BOUND_ITEM_CREATE,
            self.NATIVE_HELPER_OP_BOUND_OWNER_KILL,
            self.NATIVE_HELPER_OP_UNLOCK_TALENT_TIER,
            self.NATIVE_HELPER_OP_BOUND_INVENTORY_ITEM,
            self.NATIVE_HELPER_OP_BOUND_ITEM_TYPE,
        }
        if any(kind not in allowed_kinds for kind, _rawcode, _handler, _arg0, _arg1 in op_list):
            raise RuntimeError("native helper 仅允许结构化验证后的白名单操作")
        unit_kinds = {
            self.NATIVE_HELPER_OP_INTERNAL_ABILITY_BEGIN,
            self.NATIVE_HELPER_OP_INTERNAL_ABILITY_FIND,
            self.NATIVE_HELPER_OP_INTERNAL_ABILITY_ADD,
            self.NATIVE_HELPER_OP_INTERNAL_ABILITY_END,
            self.NATIVE_HELPER_OP_INTERNAL_ABILITY_REFRESH,
            self.NATIVE_HELPER_OP_INTERNAL_ABILITY_REMOVE,
            self.NATIVE_HELPER_OP_SET_ITEM_CHARGES,
            self.NATIVE_HELPER_OP_REMOVE_ITEM_SLOT,
            self.NATIVE_HELPER_OP_ADD_ITEM_TO_SLOT_BY_ID,
            self.NATIVE_HELPER_OP_GET_ITEM_TYPE_IN_SLOT,
            self.NATIVE_HELPER_OP_SET_HERO_INT,
            self.NATIVE_HELPER_OP_GET_HERO_INT,
            self.NATIVE_HELPER_OP_JASS_UNIT_VOID,
            self.NATIVE_HELPER_OP_JASS_UNIT_BOOL,
            self.NATIVE_HELPER_OP_JASS_UNIT_INT_BOOL,
            self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE,
            self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE_LEVEL,
            self.NATIVE_HELPER_OP_JASS_UNIT_SCALE,
            self.NATIVE_HELPER_OP_JASS_UNIT_INT_QUERY,
            self.NATIVE_HELPER_OP_JASS_EXPLODE_UNIT,
            self.NATIVE_HELPER_OP_JASS_TAKE_OWNERSHIP,
            self.NATIVE_HELPER_OP_JASS_CLEAR_INVENTORY,
            self.NATIVE_HELPER_OP_JASS_KILL_OWNER_UNITS,
            self.NATIVE_HELPER_OP_JASS_SET_INVENTORY_CHARGES,
            self.NATIVE_HELPER_OP_JASS_DUPLICATE_INVENTORY,
            self.NATIVE_HELPER_OP_JASS_DROP_INVENTORY,
            self.NATIVE_HELPER_OP_JASS_REMOVE_ALL_ABILITIES,
            self.NATIVE_HELPER_OP_JASS_SET_UNIT_POSITION,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_TARGET,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_IMMEDIATE,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_POINT,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_NOARG_DERIVED,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_BUFF,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_ENUM,
            self.NATIVE_HELPER_OP_JASS_ABILITY_REAL_LEVEL_FIELD_SET,
            self.NATIVE_HELPER_OP_JASS_UNIT_RESOLVE,
            self.NATIVE_HELPER_OP_JASS_ABILITY_FIELD_GET,
            self.NATIVE_HELPER_OP_JASS_ABILITY_LEVEL_FIELD_GET,
            self.NATIVE_HELPER_OP_JASS_ABILITY_SCALAR_FIELD_SET,
            self.NATIVE_HELPER_OP_JASS_ABILITY_REAL_FIELD_SET,
            self.NATIVE_HELPER_OP_JASS_ABILITY_SCALAR_LEVEL_FIELD_SET,
            self.NATIVE_HELPER_OP_JASS_ITEM_FIELD_GET,
            self.NATIVE_HELPER_OP_JASS_ITEM_FIELD_SET,
            self.NATIVE_HELPER_OP_JASS_CLONE_SELECTED_UNIT,
            self.NATIVE_HELPER_OP_BOUND_DIRECT_ABILITY,
        }
        unit_kinds.add(self.NATIVE_HELPER_OP_PERSISTENT_UNIT_SNAPSHOT)
        unit_kinds.add(self.NATIVE_HELPER_OP_JASS_SET_UNIT_STATE)
        unit_kinds.add(self.NATIVE_HELPER_OP_JASS_SET_UNIT_INT)
        unit_kinds.add(self.NATIVE_HELPER_OP_VALIDATE_UNIT_IDENTITY)
        unit_kinds.add(self.NATIVE_HELPER_OP_SET_BOUND_ITEM_CHARGES)
        unit_kinds.add(self.NATIVE_HELPER_OP_SET_UNIT_REGEN)
        unit_kinds.add(self.NATIVE_HELPER_OP_UNLOCK_TALENT_TIER)
        if any(kind in unit_kinds for kind, _rawcode, _handler, _arg0, _arg1 in op_list) and not unit_address:
            raise RuntimeError("当前单位缺少运行时 unit 指针，不能调用 native helper")
        command_path = self._native_helper_command_path()
        self._write_native_helper_command(
            command_path,
            self._pack_native_helper_command(unit_address, op_list),
        )
        active_hook = None
        if (
            self._native_helper_batch_hook is not None
            and self._native_helper_batch_thread_id == threading.get_ident()
        ):
            active_hook = self._native_helper_batch_hook
        elif (
            self._native_helper_persistent_hook is not None
            and self._native_helper_persistent_pid == self.pid
        ):
            active_hook = self._native_helper_persistent_hook
        if active_hook is not None:
            return self._wait_native_helper_result(
                command_path,
                active_hook,
                len(op_list),
                timeout_ms,
            )
        dll_path = self._native_helper_dll_path()
        module = kernel32.LoadLibraryW(str(dll_path))
        if not module:
            raise ctypes.WinError(ctypes.get_last_error())
        hook = None
        try:
            proc = kernel32.GetProcAddress(module, b"War3HookProc")
            if not proc:
                raise ctypes.WinError(ctypes.get_last_error())
            pid = ctypes.c_ulong()
            tid = user32.GetWindowThreadProcessId(ctypes.c_void_p(self.hwnd), ctypes.byref(pid))
            if not tid or int(pid.value) != self.pid:
                raise RuntimeError("Warcraft III 窗口线程已失效")
            hook = user32.SetWindowsHookExW(
                WH_CALLWNDPROC,
                ctypes.c_void_p(proc),
                ctypes.c_void_p(module),
                int(tid),
            )
            if not hook:
                raise ctypes.WinError(ctypes.get_last_error())
            return self._wait_native_helper_result(
                command_path,
                hook,
                len(op_list),
                timeout_ms,
            )
        finally:
            if hook:
                user32.UnhookWindowsHookEx(hook)
            kernel32.FreeLibrary(module)

    @staticmethod
    def _float_bits(value: float) -> int:
        return struct.unpack("<I", struct.pack("<f", float(value)))[0]

    @staticmethod
    def _float_from_bits(value: int) -> float:
        return struct.unpack("<f", struct.pack("<I", int(value) & 0xFFFFFFFF))[0]

    def _elephant_handlers(
        self,
        pm: ProcessMemory,
        names: Iterable[str],
    ) -> dict[str, NativeHandler]:
        requested = tuple(dict.fromkeys(names))
        handlers = self._query_native_table_handlers(requested)
        missing = tuple(name for name in requested if name not in handlers)
        if missing:
            raise RuntimeError("缺少 native 函数：" + ", ".join(missing))
        return {name: handlers[name] for name in requested}

    def _candidate_from_native_snapshot(
        self, pm: ProcessMemory | None, snapshot: PersistentNativeUnitSnapshot,
    ) -> UnitCandidate | None:
        if not (snapshot.handle and snapshot.full_handle and snapshot.owner_address and snapshot.unit_address):
            return None
        # The DLL validates the whole snapshot, including property membership,
        # before publishing it. Keep that identity intact without external
        # mapping/scans. Targeted reads and mutations revalidate it in the DLL.
        hp, mp = snapshot.hp_property, snapshot.mp_property
        return UnitCandidate(
            base=hp, score=1000,
            hp_current_address=hp + 0xD0 if hp else 0,
            hp_max_address=hp + 0xE0 if hp else 0,
            hp_regen_address=hp + 0xD4 if hp else 0,
            mp_current_address=mp + 0xD0 if mp else 0,
            mp_max_address=mp + 0xE0 if mp else 0,
            mp_regen_address=mp + 0xD4 if mp else 0,
            note="native engine identity and property snapshot",
            handle=snapshot.full_handle, owner_address=snapshot.owner_address,
            unit_address=snapshot.unit_address, unit_type_id=int(snapshot.type_id),
            selection_source="persistent_native", native_snapshot=snapshot,
        )

    def _elephant_selected_candidate(self, pm: ProcessMemory) -> UnitCandidate:
        if self._elephant_selection_override is not None:
            return self._elephant_selection_override[0]
        try:
            if getattr(self, "_native_selection_unavailable", False):
                raise RuntimeError("3.0 native selection disabled after verified timeout")
            snapshots = self.persistent_native_selected_snapshots(timeout_ms=10000)
        except Exception:
            if not hasattr(self, "_native_selection_unavailable"):
                raise
            self._native_selection_unavailable = True
            with self._process_memory() as memory:
                selected = self._classic_selection_candidates(memory)
            if not selected:
                raise RuntimeError("游戏当前没有可操作的选中单位")
            return selected[0][0]
        if not snapshots:
            raise RuntimeError("游戏当前没有可操作的选中单位")
        snapshot = snapshots[0]
        if not (snapshot.full_handle and snapshot.owner_address and snapshot.unit_address):
            raise RuntimeError("native helper 未返回完整当前单位身份，已拒绝同步扫描")
        candidate = self._candidate_from_native_snapshot(pm, snapshot)
        if candidate is None:
            raise RuntimeError("当前 native 快照已经失效，请重新读取选中单位")
        return replace(candidate, unit_type_id=int(snapshot.type_id),
                       selection_source="persistent_native", native_snapshot=snapshot)

    def _elephant_selected_handle(self, pm: ProcessMemory) -> int:
        if self._elephant_selection_override is not None:
            return self._elephant_selection_override[1]
        try:
            if getattr(self, "_native_selection_unavailable", False):
                raise RuntimeError("3.0 native selection disabled after verified timeout")
            snapshots = self.persistent_native_selected_snapshots(timeout_ms=30000)
        except Exception:
            if not hasattr(self, "_native_selection_unavailable"):
                raise
            self._native_selection_unavailable = True
            with self._process_memory() as memory:
                selected = self._classic_selection_candidates(memory)
            if not selected:
                raise RuntimeError("游戏当前没有可操作的选中单位")
            return int(selected[0][1])
        unit_handle = int(snapshots[0].handle) if snapshots else 0
        if not unit_handle:
            raise RuntimeError("游戏当前没有可操作的选中单位")
        return unit_handle

    def _elephant_selected_handles(self, pm: ProcessMemory) -> tuple[int, ...]:
        try:
            if getattr(self, "_native_selection_unavailable", False):
                raise RuntimeError("3.0 native selection disabled after verified timeout")
            snapshots = self.persistent_native_selected_snapshots(timeout_ms=30000)
        except Exception:
            if not hasattr(self, "_native_selection_unavailable"):
                raise
            self._native_selection_unavailable = True
            with self._process_memory() as memory:
                selected = self._classic_selection_candidates(memory)
            handles = tuple(dict.fromkeys(int(handle) for _candidate, handle in selected))
            if not handles:
                raise RuntimeError("游戏当前没有可操作的选中单位")
            return handles
        handles = tuple(dict.fromkeys(int(snapshot.handle) for snapshot in snapshots if snapshot.handle))
        if not handles:
            raise RuntimeError("游戏当前没有可操作的选中单位")
        if len(handles) > self.SELECTED_BATCH_MAX_UNITS:
            raise RuntimeError("游戏返回的选中单位数量超过安全上限")
        return handles

    @contextmanager
    def _bound_elephant_selection(
        self,
        candidate: UnitCandidate,
        unit_handle: int,
    ) -> Iterator[None]:
        previous = self._elephant_selection_override
        self._elephant_selection_override = (candidate, int(unit_handle))
        try:
            yield
        finally:
            self._elephant_selection_override = previous

    def _selected_candidates_snapshot(
        self,
        pm: ProcessMemory | None,
        *,
        persistent_snapshots: Iterable[PersistentNativeUnitSnapshot] | None = None,
    ) -> list[tuple[UnitCandidate, int]]:
        if persistent_snapshots is None and getattr(self, "_game_session", None) is not None:
            # Production reads use the version-bound external reader directly.
            # Do not label this deliberate backend choice as a native timeout.
            if pm is not None:
                return self._classic_selection_candidates(pm)
            with self._process_memory() as memory:
                return self._classic_selection_candidates(memory)
        if persistent_snapshots is None:
            try:
                if getattr(self, "_native_selection_unavailable", False):
                    raise RuntimeError("3.0 native selection disabled after verified timeout")
                persistent_snapshots = self.persistent_native_selected_snapshots()
            except Exception as native_error:
                if not hasattr(self, "_native_selection_unavailable"):
                    raise
                self._native_selection_unavailable = True
                try:
                    with self._process_memory() as memory:
                        return self._classic_selection_candidates(memory)
                except Exception as classic_error:
                    raise RuntimeError(
                        "native selection unavailable and 3.0 classic selection failed: "
                        f"native={native_error}; classic={classic_error}"
                    ) from classic_error
        else:
            persistent_snapshots = tuple(persistent_snapshots)
        if not persistent_snapshots:
            # Empty native selection is authoritative even if another thread
            # has just reset the registration flag during a reconnect.
            raise RuntimeError("native helper 当前没有稳定的选中单位快照")
        if len(persistent_snapshots) > self.SELECTED_BATCH_MAX_UNITS:
            raise RuntimeError("游戏返回的选中单位数量超过安全上限")
        selected: list[tuple[UnitCandidate, int]] = []
        seen_units: set[int] = set()
        seen_handles: set[int] = set()
        for snapshot in persistent_snapshots:
            if not (
                snapshot.handle and snapshot.full_handle
                and snapshot.owner_address and snapshot.unit_address
            ):
                raise RuntimeError(
                    "native 快照缺少完整单位身份，已拒绝回退到旧选择器；请重试"
                )
            candidate = self._candidate_from_native_snapshot(pm, snapshot)
            if (
                candidate is None
                or (candidate.handle, candidate.owner_address, candidate.unit_address)
                != (snapshot.full_handle, snapshot.owner_address, snapshot.unit_address)
                or snapshot.unit_address in seen_units
                or snapshot.handle in seen_handles
            ):
                raise RuntimeError("Native selection changed while mapping its field objects; retry the read")
            seen_units.add(candidate.unit_address)
            seen_handles.add(snapshot.handle)
            candidate = replace(
                candidate,
                note=(
                    "persistent_native "
                    f"handle=0x{snapshot.handle:x} type=0x{snapshot.type_id:x}; "
                    f"{candidate.note}"
                ),
                selection_source="persistent_native",
                unit_type_id=int(snapshot.type_id),
                native_snapshot=snapshot,
            )
            selected.append((candidate, snapshot.handle))
        # Publish only after the whole group has passed identity checks. A
        # failed mapping must not leave a partially accepted selection behind.
        self._unit_owner_index.update({
            candidate.handle: candidate.owner_address for candidate, _handle in selected
        })
        return selected

    def _selected_summaries_from_snapshot(
        self,
        pm: ProcessMemory,
        snapshot: Iterable[tuple[UnitCandidate, int]],
    ) -> tuple[UnitSelectionSummary, ...]:
        snapshot = tuple(snapshot)
        if (
            snapshot
            and all(
                candidate.selection_source == "persistent_native"
                for candidate, _unit_handle in snapshot
            )
        ):
            summaries: list[UnitSelectionSummary] = []
            for candidate, unit_handle in snapshot:
                item = self._native_snapshot_for_candidate(candidate)
                if item is None or item.handle != unit_handle:
                    raise RuntimeError("当前 native 快照已经失效，请重新读取选中单位")
                inventory = tuple(
                    f"{slot}:{format_rawcode(rawcode)}"
                    for slot, rawcode in enumerate(item.item_ids, start=1)
                    if rawcode
                )
                components = {
                    name for bit, name in enumerate(("inventory", "hero", "move", "attack"))
                    if item.component_mask & (1 << bit)
                }
                summaries.append(
                    UnitSelectionSummary(
                        candidate=candidate,
                        refs=1,
                        known_hits=2,
                        region_base=0,
                        hp_text=f"{int(round(item.hp))}/{int(round(item.hp_max))}",
                        mp_text=f"{int(round(item.mp))}/{int(round(item.mp_max))}",
                        position=(item.x, item.y),
                        components=tuple(sorted(components)),
                        inventory=inventory,
                        ability_count=len(item.ability_ids),
                        hero="hero" in components,
                    )
                )
            return tuple(summaries)

        if pm is None and snapshot:
            with self._process_memory() as summary_memory:
                return self._selected_summaries_from_snapshot(summary_memory, snapshot)

        owners = {
            candidate.owner_address
            for candidate, _unit_handle in snapshot
            if candidate.owner_address
        }
        # Prefer each unit's direct component pointers. This keeps a selected
        # group read bounded by its size; the existing process-wide scan remains
        # the fallback inside _selected_components when direct pointers fail.
        components_by_owner = {
            owner: self._selected_components(pm, owner)
            for owner in owners
        }
        return tuple(
            self._selection_summary_from_candidate(
                pm,
                candidate,
                refs=1,
                known_hits=2,
                region_base=0,
                components=components_by_owner.get(candidate.owner_address),
                include_inventory=True,
                include_abilities=False,
            )
            for candidate, _unit_handle in snapshot
        )

    def selected_unit_summaries(self) -> tuple[UnitSelectionSummary, ...]:
        return self._last_selected_summaries

    def run_for_selected_units(
        self,
        action: Callable[[], object],
    ) -> tuple[int, int, tuple[object, ...], tuple[str, ...]]:
        # One persistent native snapshot supplies both the verified object
        # identity and its current JASS handle.
        snapshot = self._selected_candidates_snapshot(None)
        results: list[object] = []
        errors: list[str] = []

        def process_snapshot() -> None:
            for candidate, unit_handle in snapshot:
                try:
                    with self._bound_elephant_selection(candidate, unit_handle):
                        results.append(action())
                except Exception as exc:
                    errors.append(
                        f"{format_rawcode(candidate.unit_type_id) if candidate.unit_type_id else '未知单位'}"
                        f"(0x{candidate.unit_address:x}): {exc}"
                    )

        if (len(snapshot) > 1 and hasattr(self, "_native_helper_lock")
                and not getattr(self, "_native_selection_unavailable", False)):
            with self._native_helper_batch_transaction():
                process_snapshot()
        else:
            process_snapshot()
        return len(results), len(errors), tuple(results), tuple(errors)

    def _direct_selected_context(self) -> tuple[UnitCandidate, int]:
        if self._elephant_selection_override is not None:
            return self._elephant_selection_override
        snapshot = self._selected_candidates_snapshot(None)
        if not snapshot:
            raise RuntimeError("游戏当前没有可操作的选中单位")
        # Use the candidate and JASS handle from one snapshot. Resolving them
        # through two independent scans can pair a current unit with a stale
        # handle when the game refreshes its selection state.
        return snapshot[0]

    def _resolve_jass_unit_handle(self, unit_handle: int, *, allow_missing: bool = False) -> int:
        if not unit_handle:
            return 0
        self.persistent_native_init()
        resolver = int(self._jass_unit_resolver_address)
        if not resolver:
            raise RuntimeError("native 表没有提供单位句柄解析函数")
        try:
            return int(self._run_native_helper_ops(
                unit_handle,
                ((
                    self.NATIVE_HELPER_OP_JASS_UNIT_RESOLVE,
                    0,
                    resolver,
                    0,
                    0,
                ),),
            )[0].result)
        except RuntimeError as exc:
            if allow_missing and (
                f"error={ERROR_NOT_FOUND}" in str(exc)
                or f"last_error={ERROR_NOT_FOUND}" in str(exc)
            ):
                return 0
            raise

    def _resolve_jass_unit_handles_batch(
        self,
        pm: ProcessMemory,
        unit_handles: Iterable[int],
        *,
        allow_missing: bool = False,
    ) -> dict[int, int]:
        handles = tuple(dict.fromkeys(int(handle) for handle in unit_handles if int(handle)))
        if not handles:
            return {}
        del pm
        self.persistent_native_init()
        resolver = int(self._jass_unit_resolver_address)
        if not resolver:
            raise RuntimeError("native 表没有提供单位句柄解析函数")
        try:
            results = self._run_native_helper_ops(
                0,
                tuple(
                    (
                        self.NATIVE_HELPER_OP_JASS_UNIT_RESOLVE_ARG,
                        0,
                        resolver,
                        handle,
                        0,
                    )
                    for handle in handles
                ),
            )
        except RuntimeError:
            if allow_missing:
                return {}
            raise
        return {
            handle: int(result.result)
            for handle, result in zip(handles, results)
            if int(result.result)
        }

    def _remove_captured_engine_ability_instance(
        self,
        candidate: UnitCandidate,
        unit_handle: int,
        data_address: int,
    ) -> None:
        resolved_unit = self._resolve_jass_unit_handle(unit_handle, allow_missing=True)
        if not resolved_unit:
            return
        if resolved_unit != candidate.unit_address:
            raise RuntimeError(
                "临时技能清理前单位身份已变化："
                f"0x{resolved_unit:x}!=0x{candidate.unit_address:x}"
            )
        self._remove_engine_ability_instance(None, candidate, data_address)

    def prewarm_elephant_functions(self) -> int:
        if getattr(self, "_native_selection_unavailable", False):
            # 3.0 direct paths bind to the verified object registry and do not
            # need the retired native execution bootstrap. Keep this method
            # useful for the UI instead of turning prewarm into an error.
            with self._process_memory() as memory:
                selected = self._classic_selection_candidates(memory)
                direct = 0
                for candidate, _handle in selected:
                    if candidate.owner_address and candidate.unit_address:
                        direct += 1
                return direct
        persistent_count = self.persistent_native_init()
        handlers = self._discover_native_handlers_near_table(
            None,
            self.ELEPHANT_NATIVE_NAMES,
        )
        try:
            selected = self._selected_candidates_snapshot(None)
            self._selected_summaries_from_snapshot(None, selected)
        except (RuntimeError, OSError):
            # Initialization must remain usable before a unit is selected.
            pass
        return max(len(handlers), persistent_count)


class BackupReadWar3Trainer(War3Trainer):
    """War3 trainer view that accepts verified low virtual addresses."""

    LOW_ADDRESS_LIMIT = 0x100000000

    def __init__(self, pid: int | None = None):
        super().__init__(pid)
        self._readable_pointer_bases: tuple[int, ...] = ()
        self._readable_pointer_ends: tuple[int, ...] = ()
        self._backup_selected_identity: tuple[int, int, int] | None = None
        self._backup_diagnostics: Win10ReadLogger | None = None

    def adopt_session_diagnostics(self, diagnostics: Win10ReadLogger) -> None:
        if self._backup_diagnostics is diagnostics:
            return
        self.close_session_diagnostics()
        self._backup_diagnostics = diagnostics

    def close_session_diagnostics(self) -> None:
        diagnostics, self._backup_diagnostics = self._backup_diagnostics, None
        if diagnostics is not None:
            diagnostics.close()

    def bind_selected_identity(self, identity: tuple[int, int, int]) -> None:
        normalized = tuple(int(value) for value in identity)
        if len(normalized) != 3 or not normalized[2]:
            raise ValueError("备用读取单位身份无效")
        self._backup_selected_identity = normalized

    def _process_memory(self, write: bool = False) -> ProcessMemory:
        del write
        raise RuntimeError("备用读取后端已禁用；当前版本必须使用持久 native helper")

    @staticmethod
    def _require_win10_memory(pm: ProcessMemory) -> Win10ProcessMemory:
        if not isinstance(pm, Win10ProcessMemory):
            raise RuntimeError("备用读取操作拒绝回落到普通内存路径")
        return pm

    def _discover_native_handlers(
        self,
        pm: ProcessMemory,
        names: Iterable[str] | None = None,
    ) -> dict[str, NativeHandler]:
        return self._query_native_table_handlers(names or self.NATIVE_HANDLER_NAMES)

    def _discover_native_handlers_near_table(
        self,
        pm: ProcessMemory,
        names: Iterable[str],
    ) -> dict[str, NativeHandler]:
        return self._query_native_table_handlers(names)

    def _resource_property_groups(
        self,
        pm: ProcessMemory,
        warm_unit_owner_index: bool = False,
    ) -> dict[int, dict[int, ResourceProperty]]:
        safe_pm = self._require_win10_memory(pm)
        return War3Trainer._resource_property_groups_win10(
            self,
            safe_pm,
            warm_unit_owner_index,
        )

    def _scan_component_index(
        self,
        pm: ProcessMemory,
    ) -> dict[int, dict[str, tuple[int, int]]]:
        safe_pm = self._require_win10_memory(pm)
        return War3Trainer._scan_component_index_win10(
            self,
            safe_pm,
        )

    def _elephant_selected_candidate(self, pm: ProcessMemory) -> UnitCandidate:
        if self._elephant_selection_override is not None:
            return self._elephant_selection_override[0]
        return War3Trainer._elephant_selected_candidate(self, pm)

    def _elephant_selected_handle(self, pm: ProcessMemory) -> int:
        if self._elephant_selection_override is not None:
            return self._elephant_selection_override[1]
        return War3Trainer._elephant_selected_handle(self, pm)

    def _direct_selected_context(self) -> tuple[UnitCandidate, int]:
        # candidate.handle is the full object generation, not a JASS handle.
        # Keep selection and its executable handle paired by the native path.
        return War3Trainer._direct_selected_context(self)

    def _resolve_jass_unit_handle(
        self,
        unit_handle: int,
        *,
        allow_missing: bool = False,
    ) -> int:
        with self._process_memory() as pm:
            return self._resolve_jass_unit_handle_win10(
                self._require_win10_memory(pm),
                unit_handle,
                allow_missing=allow_missing,
            )

    def set_readable_pointer_regions(self, regions: Iterable[Region]) -> dict[str, object]:
        ranges: list[tuple[int, int]] = []
        for region in sorted(regions, key=lambda item: item.base):
            start = max(int(region.base), 0x10000)
            end = min(int(region.base + region.size), self.LOW_ADDRESS_LIMIT)
            if end - start < 8:
                continue
            if ranges and start <= ranges[-1][1]:
                previous_start, previous_end = ranges[-1]
                ranges[-1] = (previous_start, max(previous_end, end))
            else:
                ranges.append((start, end))
        self._readable_pointer_bases = tuple(start for start, _end in ranges)
        self._readable_pointer_ends = tuple(end for _start, end in ranges)
        return {
            "low_region_count": len(ranges),
            "low_readable_bytes": sum(end - start for start, end in ranges),
            "low_min": f"0x{ranges[0][0]:x}" if ranges else "",
            "low_max": f"0x{ranges[-1][1]:x}" if ranges else "",
        }

    def _sane_heap_ptr(self, value: int) -> bool:
        value = int(value)
        if War3Trainer._sane_heap_ptr(value):
            return True
        if value < 0x10000 or value >= self.LOW_ADDRESS_LIMIT:
            return False
        index = bisect_right(self._readable_pointer_bases, value) - 1
        return bool(
            index >= 0
            and value + 8 <= self._readable_pointer_ends[index]
        )












