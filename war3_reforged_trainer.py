# -*- coding: utf-8 -*-
"""Warcraft III Reforged local trainer.

This replaces the old 32-bit game.dll trainer path with verified Reforged routes:
- Warcraft cheat input through PostMessageW, avoiding IME/keyboard layout issues.
- Reforged 64-bit selected-unit handle -> unit owner -> property table memory path.
"""

from __future__ import annotations

import argparse
from bisect import bisect_right
from contextlib import contextmanager
import ctypes
import math
import tempfile
import struct
import sys
import threading
import time
import traceback
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable, Iterable, Iterator

from war3_ability_fields import (
    ABILITY_FIELD_BY_KEY,
    AbilityFieldSpec,
    ability_fields_for_effect_class,
)


APP_VERSION = "1.0.2"
WIN10_COMPAT_REVISION = "backup-r4-live-selection"


if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008

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
VK_F1 = 0x70
VK_HOME = 0x24
VK_END = 0x23
VK_NUMPAD1 = 0x61
VK_NUMPAD2 = 0x62
VK_NUMPAD3 = 0x63
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
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


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

kernel32.OpenProcess.restype = ctypes.c_void_p
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


@dataclass(frozen=True)
class GlobalHotkeySpec:
    name: str
    label: str
    modifiers: int
    virtual_key: int


class GlobalHotkeyManager:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._registered_names: tuple[str, ...] = ()

    @property
    def registered_names(self) -> tuple[str, ...]:
        with self._lock:
            return self._registered_names

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
        return dict(errors)

    def stop(self) -> None:
        with self._lock:
            thread = self._thread
            thread_id = self._thread_id
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


@dataclass(frozen=True)
class Region:
    base: int
    size: int
    protect: int
    typ: int


@dataclass(frozen=True)
class ResourceCache:
    gold_address: int
    lumber_address: int
    gold: int
    lumber: int
    food_used_address: int = 0
    food_cap_address: int = 0
    food_limit_address: int = 0
    food_used: int = 0
    food_cap: int = 0
    food_limit: int = 0
    block_start_kind: int = 0
    source: str = ""
    owner_key: int = 0
    header_value: int = 0
    player_value: int = 0
    score: int = 0


@dataclass(frozen=True)
class ResourceProperty:
    kind: int
    address: int
    value: int
    owner_key: int


@dataclass(frozen=True)
class LocalPlayerResources:
    player_id: int
    gold: int
    lumber: int
    food_used: int
    food_cap: int


@dataclass(frozen=True)
class UnitCandidate:
    base: int
    score: int
    hp_current_address: int
    hp_max_address: int
    mp_current_address: int
    mp_max_address: int
    note: str
    hp_regen_address: int = 0
    mp_regen_address: int = 0
    owner_address: int = 0
    handle: int = 0
    unit_address: int = 0
    x_address: int = 0
    y_address: int = 0
    position_property_address: int = 0
    selection_source: str = ""
    selection_slot_address: int = 0
    unit_type_id: int = 0

    @property
    def hp_visible_address(self) -> int:
        return self.hp_max_address

    @property
    def mp_visible_address(self) -> int:
        return self.mp_max_address


@dataclass(frozen=True)
class VisibleUnitPanel:
    current_hp: int
    max_hp: int
    current_mp: int
    max_mp: int
    hp_text: str
    mp_text: str


@dataclass(frozen=True)
class UnitMemoryField:
    key: str
    label: str
    value_type: str
    value: int | float
    address: int
    category: str
    write_address: int = 0
    write_type: str = ""
    write_base: float = 0.0
    note: str = ""
    extra_writes: tuple[tuple[int, str], ...] = ()

    @property
    def writable(self) -> bool:
        return bool(self.write_address and self.write_type)

    def value_text(self) -> str:
        if self.value_type == "rawcode":
            return format_rawcode(int(self.value))
        if self.value_type in {"u64", "ptr"}:
            return f"0x{int(self.value):x}"
        if isinstance(self.value, float):
            return f"{self.value:.6g}"
        return str(self.value)


@dataclass(frozen=True)
class InventoryItem:
    slot: int
    handle: int
    handle_address: int
    item_address: int = 0
    rawcode: int = 0
    rawcode_address: int = 0
    mirror_rawcode: int = 0
    mirror_rawcode_address: int = 0
    ability_rawcode: int = 0
    ability_rawcode_address: int = 0
    charges: int = 0
    charges_address: int = 0

    @property
    def rawcode_text(self) -> str:
        return format_rawcode(self.rawcode) if self.rawcode else ""


@dataclass(frozen=True)
class AbilityInstance:
    slot: int
    wrapper_address: int
    data_address: int
    wrapper_vtable: int
    data_vtable: int
    wrapper_tag_address: int
    wrapper_tag: int
    handle: int
    class_rawcode: int
    rawcode: int
    rawcode_address: int
    mirror_rawcode_address: int = 0
    data_cache_address: int = 0
    data_cache_pointer: int = 0

    @property
    def class_text(self) -> str:
        return format_rawcode(self.class_rawcode) if self.class_rawcode else ""

    @property
    def rawcode_text(self) -> str:
        return format_rawcode(self.rawcode) if self.rawcode else ""


@dataclass(frozen=True)
class UnitSelectionSummary:
    candidate: UnitCandidate
    refs: int
    known_hits: int
    region_base: int
    hp_text: str
    mp_text: str
    position: tuple[float, float] | None
    components: tuple[str, ...]
    inventory: tuple[str, ...]
    ability_count: int
    hero: bool


def selection_confidence_text(summary: "UnitSelectionSummary") -> str:
    note = summary.candidate.note
    if note.startswith("remembered_identity=") or note.startswith("manual_candidate"):
        return "已验证"
    if note.startswith("selected_handle=") or note.startswith("selected_unit_slot=") or summary.known_hits >= 2:
        return "强"
    if note.startswith("global_unit_scan"):
        return "扫描"
    return "候选"


@dataclass(frozen=True)
class MemoryWriteSpec:
    label: str
    address: int
    value_type: str
    value: int | float | str


@dataclass(frozen=True)
class NativeHandler:
    name: str
    record_address: int
    handler_address: int


@dataclass(frozen=True)
class NativeAbilityInternals:
    find_address: int
    begin_address: int
    add_address: int
    end_address: int
    refresh_address: int
    remove_address: int


@dataclass(frozen=True)
class NativeHelperOpResult:
    kind: int
    result: int
    last_error: int = 0
    arg0: int = 0
    arg1: int = 0
    extra_results: tuple[int, ...] = ()


@dataclass(frozen=True)
class SelectedAbilityFieldContext:
    candidate: UnitCandidate
    unit_handle: int
    ability_handle: int
    ability_rawcode: int
    effect_class: int
    effect_class_verified: bool
    effect_class_note: str
    current_level: int
    handlers: dict[str, NativeHandler]

    @property
    def unit_identity(self) -> tuple[int, int, int]:
        return (
            self.candidate.handle,
            self.candidate.owner_address,
            self.candidate.unit_address,
        )


@dataclass(frozen=True)
class AbilityFieldValue:
    spec: AbilityFieldSpec
    value: bool | int | float | None
    status: str
    note: str = ""

    def value_text(self) -> str:
        if self.value is None:
            return ""
        if self.spec.value_kind == "boolean":
            return "true" if bool(self.value) else "false"
        if self.spec.value_kind == "real":
            return f"{float(self.value):.7g}"
        return str(int(self.value))


@dataclass(frozen=True)
class AbilityFieldSnapshot:
    ability_rawcode: int
    effect_class: int
    current_level: int
    requested_level: int
    fields: tuple[AbilityFieldValue, ...]
    unit_identity: tuple[int, int, int] = (0, 0, 0)
    effect_class_verified: bool = True
    effect_class_note: str = ""


@dataclass(frozen=True)
class JassSelectionProbeResult:
    unit_handle: int
    handle_id: int
    player_handle: int
    candidate: UnitCandidate | None
    note: str


@dataclass(frozen=True)
class NativeSelectionProbeResult:
    selection_manager_offset: int
    primary_list_offset: int
    alternate_list_offset: int
    is_unit_selected_handler: int
    group_enum_selected_handler: int
    candidate: UnitCandidate | None
    note: str


def format_rawcode(raw: int) -> str:
    raw &= 0xFFFFFFFF
    data = struct.pack(">I", raw)
    if all(32 <= byte < 127 for byte in data):
        return data.decode("ascii")
    return f"0x{raw:08x}"


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
        access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        if write:
            access |= PROCESS_VM_WRITE | PROCESS_VM_OPERATION
        self.handle = kernel32.OpenProcess(access, False, pid)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
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
        buf = ctypes.create_string_buffer(size)
        got = ctypes.c_size_t()
        ok = kernel32.ReadProcessMemory(
            self.handle, ctypes.c_void_p(address), buf, size, ctypes.byref(got)
        )
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())
        return buf.raw[: got.value]

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

    def scan_bytes_private(self, pattern: bytes, max_region_size: int = 64 * 1024 * 1024) -> list[int]:
        hits: list[int] = []
        tail_len = max(0, len(pattern) - 1)
        for region in self.regions():
            if region.typ != MEM_PRIVATE or region.size > max_region_size:
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

    def scan_bytes_private_many(
        self,
        patterns: Iterable[bytes],
        max_region_size: int = 64 * 1024 * 1024,
    ) -> dict[bytes, list[int]]:
        unique_patterns = tuple(dict.fromkeys(patterns))
        hits = {pattern: [] for pattern in unique_patterns}
        if not unique_patterns:
            return hits
        tail_len = max(len(pattern) for pattern in unique_patterns) - 1
        for region in self.regions():
            if region.typ != MEM_PRIVATE or region.size > max_region_size:
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


class Win10ReadLogger:
    def __init__(self, pid: int):
        self.pid = int(pid)
        self.started = time.perf_counter()
        self._lock = threading.Lock()
        self._files = []
        stamp = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
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
                archive_path = log_root / f"win10-read-{stamp}-pid{self.pid}.log"
                latest_path = log_root / "win10-read-latest.log"
                for path in (archive_path, latest_path):
                    opened.append(path.open("w", encoding="utf-8-sig", buffering=1))
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
        self.log(
            "log_start",
            app_version=APP_VERSION,
            compat_revision=WIN10_COMPAT_REVISION,
            pid=self.pid,
            archive=str(self.archive_path),
            latest=str(self.latest_path),
        )

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
            f"thread={threading.get_ident()} event={event}"
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


# Historical UI label only; this compatibility reader is used on Win10 and Win11.
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
        last_received = 0
        last_error = 0
        for attempt in range(1, self.EXACT_RETRIES + 1):
            data, received, error, _ok = self._read_once(address, size)
            if received == size:
                return data
            last_received = received
            last_error = error
            self._log_read_failure(address, size, received, error, attempt, "exact")
            if error != ERROR_PARTIAL_COPY or attempt == self.EXACT_RETRIES:
                break
            self._regions_cache = None
            time.sleep(0.002 * attempt)
        self._raise_read_error(address, size, last_received, last_error)

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


def enum_war3_windows() -> list[tuple[int, int, str]]:
    windows: list[tuple[int, int, str]] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_proc(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        title = _window_text(hwnd)
        if title != "Warcraft III":
            return True
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        windows.append((int(hwnd), int(pid.value), title))
        return True

    user32.EnumWindows(enum_proc, None)
    return windows


def find_war3(pid: int | None = None) -> tuple[int, int]:
    matches = enum_war3_windows()
    if pid is not None:
        matches = [m for m in matches if m[1] == pid]
    if not matches:
        raise RuntimeError("没有找到标题为 Warcraft III 的可见窗口")
    hwnd, found_pid, _title = matches[0]
    return hwnd, found_pid


def is_war3_window(hwnd: int, pid: int) -> bool:
    if not hwnd or not user32.IsWindow(hwnd) or not user32.IsWindowVisible(hwnd):
        return False
    if _window_text(hwnd) != "Warcraft III":
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


class War3Trainer:
    # Verified for the live 2.0.4.23745 process in this session. Fallback scanning is used
    # when these addresses are stale.
    KNOWN_RESOURCE_PAIRS = [
        (0x1A5FB6DD1F0, 0x1A5FB6DD2D0),
    ]

    CHEATS = {
        "无敌并一击必杀": "whosyourdaddy",
        "显示全地图": "iseedeadpeople",
        "无限魔法": "thereisnospoon",
        "快速建造/研究": "warpten",
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
        "attack_speed": "attack1_interval",
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
    CPLAYER_SELECTION_MANAGER_OFFSET = 0x168
    SELECTION_MANAGER_ALT_LIST_OFFSET = 0x3D0
    SELECTION_MANAGER_MAX_UNITS = 64
    WIN10_STRONG_SELECTION_SCORE = 155
    UNIT_OWNER_POINTER_SEARCH_RADIUS = 0x2000000
    HERO_SKILL_SLOT_COUNT = 5
    ABILITY_WRAPPER_SCAN_BACK = 0x70000
    ABILITY_WRAPPER_SCAN_FORWARD = 0x12000
    COMPONENT_WRAPPER_SCAN_BACK = 0x70000
    COMPONENT_WRAPPER_SCAN_FORWARD = 0x12000
    UNIT_COMPONENT_DATA_OFFSETS = {
        "inventory": 0x5A0,
        "hero": 0x5A8,
        "move": 0x5B0,
        "attack": 0x5C0,
    }
    ABILITY_RUNTIME_TEMPLATE_QWORD_OFFSETS = (0x0, 0x70, 0x78, 0xA0, 0x148)
    ITEM_CHARGES_OFFSET = 0x8D0
    ITEM_CHARGES_FLAG_OFFSET = 0x38
    ITEM_CHARGES_EMPTY_FLAG = 0x1000
    SELECTED_HP_VALUE_OFFSET = 0xD0
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
        "SetItemCharges",
        "UnitAddAbility",
        "UnitRemoveAbility",
        "SetUnitAbilityLevel",
        "GetUnitAbilityLevel",
        "BlzSetUnitMaxMana",
        "SetHeroStr",
        "SetHeroAgi",
        "SetHeroInt",
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
    NATIVE_SELECTION_HANDLER_NAMES = (
        "IsUnitSelected",
    )
    WIN10_COMPAT_NATIVE_NAMES = tuple(
        dict.fromkeys(
            (
                *ELEPHANT_NATIVE_NAMES,
                *ABILITY_FIELD_NATIVE_NAMES,
                *NATIVE_HANDLER_NAMES,
                *JASS_SELECTION_NATIVE_NAMES,
                *NATIVE_SELECTION_HANDLER_NAMES,
                "GetHeroInt",
            )
        )
    )
    NATIVE_HELPER_MAGIC = 0x33524757
    NATIVE_HELPER_VERSION = 16
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
    NATIVE_HELPER_OP_JASS_ABILITY_FIELD_GET = 110
    NATIVE_HELPER_OP_JASS_ABILITY_LEVEL_FIELD_GET = 111
    NATIVE_HELPER_OP_JASS_ABILITY_SCALAR_FIELD_SET = 112
    NATIVE_HELPER_OP_JASS_ABILITY_REAL_FIELD_SET = 113
    NATIVE_HELPER_OP_JASS_ABILITY_SCALAR_LEVEL_FIELD_SET = 114

    def __init__(self, pid: int | None = None):
        self.hwnd, self.pid = find_war3(pid)
        self._unit_owner_index: dict[int, int] = {}
        self._selected_handle_addresses = list(self.KNOWN_SELECTED_HANDLE_ADDRESSES)
        self._item_object_cache: dict[int, int] = {}
        self._native_handlers: dict[str, NativeHandler] = {}
        self._native_table_region: tuple[int, int] | None = None
        self._native_table_regions: list[tuple[int, int]] = []
        self._native_table_blob: tuple[int, int, bytes] | None = None
        self._native_hero_int_set_address = 0
        self._native_hero_int_get_address = 0
        self._jass_unit_resolver_address = 0
        self._buff_data_constructor_address = 0
        self._pending_direct_effects: set[tuple[int, int]] = set()
        self._hidden_toggle_abilities: set[tuple[int, int]] = set()
        self._pending_direct_effects_lock = threading.Lock()
        self._native_helper_lock = threading.RLock()
        self._ability_runtime_templates: dict[tuple[int, int, int], dict[str, object]] = {}
        self._ability_instance_by_data: dict[tuple[int, int, int], AbilityInstance] = {}
        self._selection_player_candidates: list[int] = []
        self._selected_components_cache: dict[tuple[int, int, int], dict[str, tuple[int, int]]] = {}
        self._component_index_cache: dict[int, dict[str, tuple[int, int]]] | None = None
        self._component_index_misses: set[int] = set()
        self._unit_component_layout_confirmed = False
        self._ability_instances_cache: dict[tuple[int, int, int, bool], list[AbilityInstance]] = {}
        self._ability_field_write_disabled = False
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

    def refresh_window(self, allow_pid_change: bool = False) -> None:
        if is_war3_window(self.hwnd, self.pid):
            return
        old_pid = self.pid
        self.hwnd, self.pid = find_war3(None if allow_pid_change else self.pid)
        if self.pid != old_pid:
            self._unit_owner_index = {}
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
            self._hidden_toggle_abilities = set()
            self._ability_runtime_templates = {}
            self._ability_instance_by_data = {}
            self._selection_player_candidates = []
            self._selected_components_cache = {}
            self._component_index_cache = None
            self._component_index_misses = set()
            self._unit_component_layout_confirmed = False
            self._ability_instances_cache = {}
            self._ability_field_write_disabled = False
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
        with ProcessMemory(self.pid) as pm:
            candidate = self.locate_selected_unit_by_handle(pm, allow_deep_scan=True)
            return self._panel_from_candidate(pm, candidate)

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
                    return None
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
                if not War3Trainer._sane_heap_ptr(ptr):
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
            for piece_address, piece in read_block(address + offset, length):
                if pending and pending_address + len(pending) != piece_address:
                    yield pending_address, bytes(pending)
                    pending.clear()
                if not pending:
                    pending_address = piece_address
                pending.extend(piece)
            if pending:
                yield pending_address, bytes(pending)
            offset += length

    def _scan_bytes_private_win10(
        self,
        pm: ProcessMemory,
        pattern: bytes,
        max_region_size: int = 64 * 1024 * 1024,
    ) -> list[int]:
        hits: list[int] = []
        tail_len = max(0, len(pattern) - 1)
        for region in pm.regions():
            if region.typ != MEM_PRIVATE or region.size > max_region_size:
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

    def _scan_native_table_region_candidates_win10(
        self,
        pm: ProcessMemory,
        regions: list[Region],
        max_region_size: int,
    ) -> list[Region]:
        pattern = b"UnitAddAbility\0"
        candidates: dict[tuple[int, int], Region] = {}
        for hit in pm.scan_bytes_private(pattern, max_region_size=max_region_size):
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

    def _discover_native_handlers(
        self,
        pm: ProcessMemory,
        names: Iterable[str] | None = None,
    ) -> dict[str, NativeHandler]:
        wanted = set(names or self.NATIVE_HANDLER_NAMES)
        if wanted and wanted.issubset(self._native_handlers):
            return {name: self._native_handlers[name] for name in wanted}

        regions = pm.regions()
        table_region = self._find_native_table_region(pm, regions)
        blob = self._native_table_blob_for_region(pm, table_region)
        found = self._find_native_handlers_in_table_blob(
            pm,
            regions,
            blob,
            table_region.base,
            wanted.difference(self._native_handlers),
        )
        for offset in range(8, len(blob) - 24, 8):
            if wanted.issubset(self._native_handlers.keys() | found.keys()):
                break
            handler = struct.unpack_from("<Q", blob, offset - 8)[0]
            if not self._is_executable_image_address(regions, handler):
                continue
            name = self._decode_native_string_from_blob(pm, blob, table_region.base, offset)
            if name not in wanted:
                continue
            record = table_region.base + offset
            found[name] = NativeHandler(name, record, handler)
            if wanted.issubset(found):
                break
        self._native_handlers.update(found)
        for name in sorted(wanted.difference(self._native_handlers)):
            handler = self._find_native_handler_by_name_scan(pm, regions, name)
            if handler is not None:
                self._native_handlers[name] = handler
        missing = wanted.difference(self._native_handlers)
        if missing:
            raise RuntimeError("未找到 native 函数：" + ", ".join(sorted(missing)))
        return {name: self._native_handlers[name] for name in wanted}

    def _discover_native_handlers_near_table_win10(
        self,
        pm: ProcessMemory,
        names: Iterable[str],
    ) -> dict[str, NativeHandler]:
        wanted = set(names)
        missing = wanted.difference(self._native_handlers)
        if not missing:
            return {name: self._native_handlers[name] for name in wanted}

        regions = pm.regions()
        anchors = self._find_native_table_regions(pm, regions)
        found: dict[str, NativeHandler] = {}
        external_records: set[tuple[int, int]] = set()
        executable_regions = sorted(
            (
                (region.base, region.base + region.size)
                for region in regions
                if (region.protect & 0xFF) in EXECUTABLE_PROTECTS
            ),
            key=lambda item: item[0],
        )
        executable_starts = [start for start, _end in executable_regions]

        def is_executable(address: int) -> bool:
            index = bisect_right(executable_starts, address) - 1
            return index >= 0 and address < executable_regions[index][1]

        def scan_ranges_for(
            candidate_anchors: Iterable[Region],
            external_names: dict[int, str] | None = None,
        ) -> None:
            scan_ranges: list[tuple[int, int]] = []
            for anchor in sorted(candidate_anchors, key=lambda item: item.base):
                start = max(0, anchor.base - 0x80000)
                end = anchor.base + anchor.size + 0x80000
                if scan_ranges and start <= scan_ranges[-1][1]:
                    previous_start, previous_end = scan_ranges[-1]
                    scan_ranges[-1] = (previous_start, max(previous_end, end))
                else:
                    scan_ranges.append((start, end))

            for scan_start, scan_end in scan_ranges:
                for region in sorted(regions, key=lambda item: item.base):
                    if region.typ != MEM_PRIVATE:
                        continue
                    region_start = max(region.base, scan_start - 8)
                    region_end = min(region.base + region.size, scan_end)
                    if region_end - region_start < 32:
                        continue
                    for block_start, blob in self._iter_readable_blocks_win10(
                        pm,
                        region_start,
                        region_end - region_start,
                    ):
                        if len(blob) < 32:
                            continue
                        wanted_lengths = {len(name) for name in missing}
                        first_record = max(scan_start, (block_start + 7) & ~7)
                        if first_record - block_start < 8:
                            first_record += 8
                        block_end = block_start + len(blob)
                        for record in range(first_record, block_end - 24, 8):
                            offset = record - block_start
                            handler = struct.unpack_from("<Q", blob, offset - 8)[0]
                            if not is_executable(handler):
                                continue
                            size = struct.unpack_from("<Q", blob, offset + 8)[0]
                            if size not in wanted_lengths:
                                continue
                            ptr = struct.unpack_from("<Q", blob, offset)[0]
                            if ptr != record + 0x18 and self._sane_heap_ptr(ptr):
                                external_records.add((ptr, int(size)))
                            name = self._decode_native_string_from_blob_win10(
                                pm,
                                blob,
                                block_start,
                                offset,
                                external_names,
                            )
                            if name not in missing:
                                continue
                            found[name] = NativeHandler(name, record, handler)
                            missing.remove(name)
                            if not missing:
                                return

        def recover_external_names_from_regions() -> dict[int, str]:
            recovered: dict[int, str] = {}
            readable_cache: dict[tuple[int, int], list[tuple[int, bytes]]] = {}
            missing_by_length: dict[int, set[str]] = {}
            for name in missing:
                missing_by_length.setdefault(len(name), set()).add(name)
            for pointer, size in external_records:
                names_for_size = missing_by_length.get(size)
                if not names_for_size:
                    continue
                region = self._region_for_address(regions, pointer)
                if region is None or region.typ != MEM_PRIVATE:
                    continue
                key = (region.base, region.size)
                blocks = readable_cache.get(key)
                if blocks is None:
                    blocks = list(self._iter_readable_blocks_win10(pm, region.base, region.size))
                    readable_cache[key] = blocks
                for block_address, block in blocks:
                    offset = pointer - block_address
                    if offset < 0 or offset + size > len(block):
                        continue
                    data = block[offset : offset + size]
                    try:
                        name = data.decode("ascii")
                    except UnicodeDecodeError:
                        break
                    if name in names_for_size:
                        recovered[pointer] = name
                    break
            return recovered

        def recover_handlers_from_record_profile() -> None:
            translations: dict[int, int] = {}
            known_handlers = dict(self._native_handlers)
            known_handlers.update(found)
            for name, profile_offset in self.NATIVE_RECORD_PROFILE_ANCHORS.items():
                handler = known_handlers.get(name)
                if handler is None:
                    continue
                translation = handler.record_address - profile_offset
                translations[translation] = translations.get(translation, 0) + 1
            if not translations:
                return
            translation, votes = max(translations.items(), key=lambda item: item[1])
            if votes < 6:
                return
            for name, profile_offset in self.NATIVE_RECORD_PROFILE_EXTERNALS.items():
                if name not in missing:
                    continue
                record = translation + profile_offset
                region = self._region_for_address(regions, record)
                if region is None or region.typ != MEM_PRIVATE:
                    continue
                try:
                    handler_address = pm.read_u64(record - 8)
                    size = pm.read_u64(record + 8)
                except OSError:
                    continue
                if size != len(name) or not is_executable(handler_address):
                    continue
                found[name] = NativeHandler(name, record, handler_address)
                missing.remove(name)

        scan_ranges_for(anchors)
        if missing:
            external_names = recover_external_names_from_regions()
            if external_names:
                scan_ranges_for(anchors, external_names)
        if missing:
            recover_handlers_from_record_profile()
        if missing:
            broad_anchors = self._scan_native_table_region_candidates_win10(
                pm,
                regions,
                64 * 1024 * 1024,
            )
            anchor_by_region = {
                (anchor.base, anchor.size): anchor
                for anchor in (*anchors, *broad_anchors)
            }
            anchors = list(anchor_by_region.values())
            scan_ranges_for(anchors)
            if missing:
                external_names = recover_external_names_from_regions()
                if external_names:
                    scan_ranges_for(anchors, external_names)
        if missing:
            patterns = {(name.encode("ascii") + b"\0"): name for name in missing}
            external_names = {}
            for pattern, addresses in pm.scan_bytes_private_many(
                patterns,
                max_region_size=64 * 1024 * 1024,
            ).items():
                name = patterns[pattern]
                for address in addresses:
                    external_names[address] = name
            scan_ranges_for(anchors, external_names)

        self._native_handlers.update(found)
        if missing:
            raise RuntimeError(
                "在 native 表邻域未找到函数：" + ", ".join(sorted(missing))
            )
        return {name: self._native_handlers[name] for name in wanted}

    def _discover_native_handlers_near_table(
        self,
        pm: ProcessMemory,
        names: Iterable[str],
    ) -> dict[str, NativeHandler]:
        wanted = set(names)
        missing = wanted.difference(self._native_handlers)
        if not missing:
            return {name: self._native_handlers[name] for name in wanted}

        regions = pm.regions()
        anchors = self._find_native_table_regions(pm, regions)
        scan_ranges: list[tuple[int, int]] = []
        for anchor in sorted(anchors, key=lambda item: item.base):
            start = max(0, anchor.base - 0x80000)
            end = anchor.base + anchor.size + 0x80000
            if scan_ranges and start <= scan_ranges[-1][1]:
                previous_start, previous_end = scan_ranges[-1]
                scan_ranges[-1] = (previous_start, max(previous_end, end))
            else:
                scan_ranges.append((start, end))
        wanted_lengths = {len(name) for name in missing}
        found: dict[str, NativeHandler] = {}
        executable_regions = sorted(
            (
                (region.base, region.base + region.size)
                for region in regions
                if (region.protect & 0xFF) in EXECUTABLE_PROTECTS
            ),
            key=lambda item: item[0],
        )
        executable_starts = [start for start, _end in executable_regions]

        def is_executable(address: int) -> bool:
            index = bisect_right(executable_starts, address) - 1
            return index >= 0 and address < executable_regions[index][1]

        for scan_start, scan_end in scan_ranges:
            for region in sorted(regions, key=lambda item: item.base):
                if region.typ != MEM_PRIVATE:
                    continue
                region_start = max(region.base, scan_start - 8)
                region_end = min(region.base + region.size, scan_end)
                if region_end - region_start < 32:
                    continue
                try:
                    blob = pm.read(region_start, region_end - region_start)
                except OSError:
                    continue
                first_record = max(scan_start, (region_start + 7) & ~7)
                if first_record - region_start < 8:
                    first_record += 8
                for record in range(first_record, region_end - 24, 8):
                    offset = record - region_start
                    handler = struct.unpack_from("<Q", blob, offset - 8)[0]
                    if not is_executable(handler):
                        continue
                    size = struct.unpack_from("<Q", blob, offset + 8)[0]
                    if size not in wanted_lengths:
                        continue
                    name = self._decode_native_string_from_blob(pm, blob, region_start, offset)
                    if name not in missing:
                        continue
                    found[name] = NativeHandler(name, record, handler)
                    missing.remove(name)
                    wanted_lengths = {len(item) for item in missing}
                    if not missing:
                        break
                if not missing:
                    break
            if not missing:
                break

        self._native_handlers.update(found)
        if missing:
            raise RuntimeError(
                "在 native 表邻域未找到函数：" + ", ".join(sorted(missing))
            )
        return {name: self._native_handlers[name] for name in wanted}

    def verify_native_handlers(self) -> dict[str, NativeHandler]:
        with ProcessMemory(self.pid) as pm:
            return self._discover_native_handlers(pm, self.NATIVE_HANDLER_NAMES)

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
        for offset in range(0, max(0, len(code) - 4)):
            opcode = code[offset]
            if opcode == 0xE8:
                rel = struct.unpack_from("<i", code, offset + 1)[0]
                target = address + offset + 5 + rel
                if self._is_executable_image_address(regions, target):
                    calls.append(target)
            if opcode == 0xC3 and offset > 0x10:
                break
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
        for offset in range(0, max(0, len(code) - 4)):
            opcode = code[offset]
            if opcode == 0xE9:
                rel = struct.unpack_from("<i", code, offset + 1)[0]
                target = address + offset + 5 + rel
                if self._is_executable_image_address(regions, target):
                    jumps.append(target)
            if opcode == 0xC3 and offset > 0x10:
                break
        return jumps

    def _discover_native_ability_internals(self, pm: ProcessMemory) -> NativeAbilityInternals:
        handlers = self._discover_native_handlers(pm, ("UnitAddAbility", "UnitRemoveAbility"))
        add_handler = handlers["UnitAddAbility"].handler_address
        remove_handler = handlers["UnitRemoveAbility"].handler_address
        add_calls = self._rel32_calls_in_function(pm, add_handler)
        remove_calls = self._rel32_calls_in_function(pm, remove_handler)
        if len(add_calls) < 6:
            raise RuntimeError(
                f"UnitAddAbility 内部调用数量异常：{len(add_calls)}，不能安全创建技能"
            )
        if len(remove_calls) < 4:
            raise RuntimeError(
                f"UnitRemoveAbility 内部调用数量异常：{len(remove_calls)}，不能安全删除技能"
            )
        internals = NativeAbilityInternals(
            find_address=add_calls[1],
            begin_address=add_calls[2],
            add_address=add_calls[3],
            end_address=add_calls[4],
            refresh_address=add_calls[5],
            remove_address=remove_calls[2],
        )
        remove_find = remove_calls[1]
        if remove_find != internals.find_address:
            raise RuntimeError("UnitAddAbility/UnitRemoveAbility 使用的内部查找函数不一致")
        if remove_calls[3] != internals.refresh_address:
            raise RuntimeError("UnitAddAbility/UnitRemoveAbility 使用的刷新函数不一致")
        regions = pm.regions()
        for name, address in (
            ("find", internals.find_address),
            ("begin", internals.begin_address),
            ("add", internals.add_address),
            ("end", internals.end_address),
            ("refresh", internals.refresh_address),
            ("remove", internals.remove_address),
        ):
            if not self._is_executable_image_address(regions, address):
                raise RuntimeError(f"内部 ability 函数 {name} 地址不可执行：0x{address:x}")
        return internals

    @classmethod
    def _native_helper_command_size(cls) -> int:
        return (
            cls.NATIVE_HELPER_HEADER_STRUCT.size
            + cls.NATIVE_HELPER_OP_STRUCT.size * cls.NATIVE_HELPER_MAX_OPS
        )

    def _native_helper_dll_path(self) -> Path:
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        candidates = (
            base / "tools" / "war3_native_helper.dll",
            base / "war3_native_helper.dll",
            Path(__file__).resolve().parent / "tools" / "war3_native_helper.dll",
        )
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise RuntimeError("缺少 native helper DLL：tools\\war3_native_helper.dll")

    def _native_helper_command_path(self) -> Path:
        return Path(tempfile.gettempdir()) / f"war3_reforged_native_{self.pid}.bin"

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
            raise RuntimeError(f"native helper 执行失败：status={status} last_error={last_error}")
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
        wait_ms = max(5000, min(300000, int(timeout_ms) + 5000))
        with self._native_helper_transaction(wait_ms=wait_ms):
            return self._run_native_helper_ops_locked(
                unit_address,
                ops,
                timeout_ms=timeout_ms,
            )

    @contextmanager
    def _native_helper_transaction(self, *, wait_ms: int = 300000) -> Iterator[None]:
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
            self.NATIVE_HELPER_OP_JASS_ABILITY_FIELD_GET,
            self.NATIVE_HELPER_OP_JASS_ABILITY_LEVEL_FIELD_GET,
            self.NATIVE_HELPER_OP_JASS_ABILITY_SCALAR_FIELD_SET,
            self.NATIVE_HELPER_OP_JASS_ABILITY_REAL_FIELD_SET,
            self.NATIVE_HELPER_OP_JASS_ABILITY_SCALAR_LEVEL_FIELD_SET,
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
        }
        if any(kind in unit_kinds for kind, _rawcode, _handler, _arg0, _arg1 in op_list) and not unit_address:
            raise RuntimeError("当前单位缺少运行时 unit 指针，不能调用 native helper")
        command_path = self._native_helper_command_path()
        command_path.write_bytes(self._pack_native_helper_command(unit_address, op_list))
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
            deadline = time.monotonic() + (timeout_ms / 1000.0)
            last_status = self.NATIVE_HELPER_STATUS_PENDING
            while time.monotonic() < deadline:
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
                    return self._parse_native_helper_results(data, len(op_list))
                if not sent:
                    time.sleep(0.02)
                    continue
                time.sleep(0.02)
            raise TimeoutError(f"native helper 执行超时：status={last_status}")
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
        self._discover_native_handlers_near_table(pm, self.ELEPHANT_NATIVE_NAMES)
        return {name: self._native_handlers[name] for name in names}

    def _elephant_selected_candidate(self, pm: ProcessMemory) -> UnitCandidate:
        candidate = self.locate_selected_unit_by_handle(pm, allow_deep_scan=True)
        candidate = self._candidate_with_selected_unit_type_id(pm, candidate)
        return candidate

    def _elephant_selected_handle(self, pm: ProcessMemory) -> int:
        handlers = self._elephant_handlers(
            pm,
            (
                "CreateGroup",
                "GetLocalPlayer",
                "GroupEnumUnitsSelected",
                "FirstOfGroup",
                "GetHandleId",
                "DestroyGroup",
            ),
        )
        results = self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_SELECTED_UNIT,
                    0,
                    handlers["CreateGroup"].handler_address,
                    0,
                    handlers["GetLocalPlayer"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_SELECTED_UNIT_ARG,
                    0,
                    handlers["GroupEnumUnitsSelected"].handler_address,
                    handlers["FirstOfGroup"].handler_address,
                    handlers["GetHandleId"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_SELECTED_UNIT_ARG,
                    0,
                    handlers["DestroyGroup"].handler_address,
                    0,
                    0,
                ),
            ),
        )
        unit_handle = int(results[0].result)
        if not unit_handle:
            raise RuntimeError("游戏当前没有可操作的选中单位")
        return unit_handle

    def _direct_selected_context(self) -> tuple[UnitCandidate, int]:
        for _attempt in range(3):
            with ProcessMemory(self.pid) as pm:
                candidate = self._elephant_selected_candidate(pm)
                unit_handle = self._elephant_selected_handle(pm)
            resolved_unit = self._resolve_jass_unit_handle(unit_handle)
            if resolved_unit == candidate.unit_address:
                return candidate, unit_handle
            time.sleep(0.02)
        raise RuntimeError("选中单位在操作期间发生变化，请重新执行")

    def _resolve_jass_unit_handle(self, unit_handle: int, *, allow_missing: bool = False) -> int:
        if not unit_handle:
            return 0
        with ProcessMemory(self.pid) as pm:
            resolver = self._discover_jass_unit_resolver(pm)
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
        with ProcessMemory(self.pid) as pm:
            self._remove_engine_ability_instance(pm, candidate, data_address)

    def prewarm_elephant_functions(self) -> int:
        with ProcessMemory(self.pid) as pm:
            handlers = self._discover_native_handlers_near_table(pm, self.ELEPHANT_NATIVE_NAMES)
        return len(handlers)

    def get_selected_hero_level(self) -> int:
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(pm, ("GetHeroLevel",))
        result = self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_INT_QUERY,
                0,
                handlers["GetHeroLevel"].handler_address,
                0,
                0,
            ),),
        )[0].result
        return int(result & 0xFFFFFFFF)

    def set_selected_hero_level(self, level: int) -> int:
        target = int(level)
        if not 1 <= target <= 100000:
            raise ValueError("英雄等级必须在 1 到 100000 之间")
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(
                pm,
                (
                    "SetHeroLevel",
                    "GetHeroLevel",
                    "UnitStripHeroLevel",
                    "SuspendHeroXP",
                    "IsSuspendedXP",
                ),
            )
        current = int(self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_INT_QUERY,
                0,
                handlers["GetHeroLevel"].handler_address,
                0,
                0,
            ),),
        )[0].result & 0xFFFFFFFF)
        if target > current:
            suspended = bool(self._run_native_helper_ops(
                unit_handle,
                ((
                    self.NATIVE_HELPER_OP_JASS_UNIT_INT_QUERY,
                    0,
                    handlers["IsSuspendedXP"].handler_address,
                    0,
                    0,
                ),),
            )[0].result & 1)
            if suspended:
                self._run_native_helper_ops(
                    unit_handle,
                    ((
                        self.NATIVE_HELPER_OP_JASS_UNIT_BOOL,
                        0,
                        handlers["SuspendHeroXP"].handler_address,
                        0,
                        0,
                    ),),
                )
            try:
                self._run_native_helper_ops(
                    unit_handle,
                    ((
                        self.NATIVE_HELPER_OP_JASS_UNIT_INT_BOOL,
                        target,
                        handlers["SetHeroLevel"].handler_address,
                        1,
                        0,
                    ),),
                )
            finally:
                if suspended:
                    self._run_native_helper_ops(
                        unit_handle,
                        ((
                            self.NATIVE_HELPER_OP_JASS_UNIT_BOOL,
                            1,
                            handlers["SuspendHeroXP"].handler_address,
                            0,
                            0,
                        ),),
                    )
        elif target < current:
            result = self._run_native_helper_ops(
                unit_handle,
                ((
                    self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE,
                    current - target,
                    handlers["UnitStripHeroLevel"].handler_address,
                    0,
                    0,
                ),),
            )[0].result
            if not result:
                raise RuntimeError("游戏拒绝降低英雄等级")
        actual = int(self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_INT_QUERY,
                0,
                handlers["GetHeroLevel"].handler_address,
                0,
                0,
            ),),
        )[0].result & 0xFFFFFFFF)
        if actual != target:
            raise RuntimeError(f"英雄等级写入后读回 {actual}，目标为 {target}")
        return actual

    def set_selected_unit_invulnerable(self, enabled: bool) -> None:
        self._run_elephant_unit_bool("SetUnitInvulnerable", enabled)

    def set_selected_hero_attributes(self, value: int) -> int:
        target = int(value)
        if not 0 <= target <= 1_000_000_000:
            raise ValueError("英雄属性必须在 0 到 1000000000 之间")
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(pm, ("SetHeroStr", "SetHeroAgi", "SetHeroInt"))
        self._run_native_helper_ops(
            unit_handle,
            tuple(
                (
                    self.NATIVE_HELPER_OP_JASS_UNIT_INT_BOOL,
                    target,
                    handlers[name].handler_address,
                    1,
                    0,
                )
                for name in ("SetHeroStr", "SetHeroAgi", "SetHeroInt")
            ),
        )
        return target

    def add_selected_hero_skill_points(self, amount: int = 1) -> int:
        delta = int(amount)
        if not 1 <= delta <= 1_000_000:
            raise ValueError("增加技能点数必须在 1 到 1000000 之间")
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handler = self._elephant_handlers(
                pm,
                ("UnitModifySkillPoints",),
            )["UnitModifySkillPoints"].handler_address
        result = int(self._run_native_helper_ops(
            unit_handle,
            ((self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE, delta, handler, 0, 0),),
        )[0].result)
        if not result:
            raise RuntimeError("游戏拒绝增加英雄技能点")
        return delta

    def is_selected_unit_invulnerable(self) -> bool:
        return bool(self._query_elephant_unit_int("BlzIsUnitInvulnerable"))

    def set_selected_unit_pathing(self, enabled: bool) -> None:
        self._run_elephant_unit_bool("SetUnitPathing", enabled)

    def set_selected_unit_paused(self, enabled: bool) -> None:
        self._run_elephant_unit_bool("PauseUnit", enabled)

    def is_selected_unit_paused(self) -> bool:
        return bool(self._query_elephant_unit_int("IsUnitPaused"))

    def _query_elephant_unit_int(self, native_name: str) -> int:
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(pm, (native_name,))
        return int(self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_INT_QUERY,
                0,
                handlers[native_name].handler_address,
                0,
                0,
            ),),
        )[0].result)

    def _run_elephant_unit_bool(self, native_name: str, enabled: bool) -> None:
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(pm, (native_name,))
        self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_BOOL,
                1 if enabled else 0,
                handlers[native_name].handler_address,
                0,
                0,
            ),),
        )

    def _run_elephant_unit_void(self, native_name: str) -> None:
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(pm, (native_name,))
        self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_VOID,
                0,
                handlers[native_name].handler_address,
                0,
                0,
            ),),
        )

    def reset_selected_unit_cooldown(self) -> None:
        self._run_elephant_unit_void("UnitResetCooldown")

    def kill_selected_unit(self) -> None:
        self._run_elephant_unit_void("KillUnit")

    def remove_selected_unit(self) -> None:
        self._run_elephant_unit_void("RemoveUnit")

    def explode_selected_unit(self) -> None:
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(pm, ("SetUnitExploded", "KillUnit"))
        self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_EXPLODE_UNIT,
                0,
                handlers["SetUnitExploded"].handler_address,
                handlers["KillUnit"].handler_address,
                0,
            ),),
        )

    def set_selected_unit_scale(self, scale: float) -> float:
        target = float(scale)
        if not 0.01 <= target <= 100.0:
            raise ValueError("单位大小必须在 0.01 到 100 之间")
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(pm, ("SetUnitScale",))
        self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_SCALE,
                self._float_bits(target),
                handlers["SetUnitScale"].handler_address,
                0,
                0,
            ),),
        )
        return target

    def query_mouse_world_position(self) -> tuple[float, float]:
        packed = int(self._run_native_helper_ops(
            0,
            ((
                self.NATIVE_HELPER_OP_QUERY_WORLD_POINT,
                0,
                0,
                0,
                0,
            ),),
        )[0].result)
        x = self._float_from_bits(packed)
        y = self._float_from_bits(packed >> 32)
        if not math.isfinite(x) or not math.isfinite(y):
            raise RuntimeError("游戏返回的鼠标世界坐标无效")
        if abs(x) > 1_000_000.0 or abs(y) > 1_000_000.0:
            raise RuntimeError(f"游戏返回的鼠标世界坐标超出范围：({x:g}, {y:g})")
        return x, y

    def set_selected_unit_position(self, x: float, y: float) -> tuple[float, float]:
        target_x = float(x)
        target_y = float(y)
        if not math.isfinite(target_x) or not math.isfinite(target_y):
            raise ValueError("单位坐标必须是有限数值")
        if abs(target_x) > 1_000_000.0 or abs(target_y) > 1_000_000.0:
            raise ValueError("单位坐标超出允许范围")
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handler = self._elephant_handlers(pm, ("SetUnitPosition",))[
                "SetUnitPosition"
            ].handler_address
        self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_SET_UNIT_POSITION,
                self._float_bits(target_x),
                handler,
                self._float_bits(target_y),
                0,
            ),),
        )
        return target_x, target_y

    def move_selected_unit_to_mouse(self) -> tuple[float, float]:
        x, y = self.query_mouse_world_position()
        return self.set_selected_unit_position(x, y)

    def _run_direct_selected_ability(
        self,
        rawcode: int | str,
        op_kind: int,
        vtable_offset: int,
        arg1: int,
    ) -> int:
        with self._native_helper_transaction():
            return self._run_direct_selected_ability_locked(
                rawcode,
                op_kind,
                vtable_offset,
                arg1,
            )

    def _run_direct_selected_ability_locked(
        self,
        rawcode: int | str,
        op_kind: int,
        vtable_offset: int,
        arg1: int,
    ) -> int:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if not ability_rawcode:
            raise ValueError("技能 ID 无效")
        added = False
        candidate: UnitCandidate | None = None
        ability_data = 0
        try:
            candidate, unit_handle = self._direct_selected_context()
            with ProcessMemory(self.pid) as pm:
                get_level = self._elephant_handlers(
                    pm,
                    ("GetUnitAbilityLevel",),
                )["GetUnitAbilityLevel"].handler_address
            level = int(self._run_native_helper_ops(
                unit_handle,
                ((
                    self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE_LEVEL,
                    ability_rawcode,
                    get_level,
                    0,
                    0,
                ),),
            )[0].result)
            if not level:
                with ProcessMemory(self.pid) as pm:
                    created_instance, added = self._create_engine_ability_instance(
                        pm,
                        candidate,
                        ability_rawcode,
                        require_wrapper=False,
                    )
                    ability_data = created_instance.data_address
            with ProcessMemory(self.pid) as pm:
                assert candidate is not None
                ability_data = ability_data or self._find_engine_ability_data(
                    pm,
                    candidate,
                    ability_rawcode,
                )
                if not ability_data:
                    raise RuntimeError(
                        f"找不到 {format_rawcode(ability_rawcode)} 的运行时技能实例"
                    )
                ability_vtable = pm.read_u64(ability_data)
                direct_handler = pm.read_u64(ability_vtable + int(vtable_offset))
                if not self._is_executable_image_address(pm.regions(), direct_handler):
                    raise RuntimeError("技能直接效果回调不在游戏可执行代码段")
                target_unit = candidate.unit_address
            return int(self._run_native_helper_ops(
                target_unit,
                ((
                    op_kind,
                    ability_rawcode,
                    direct_handler,
                    ability_data,
                    arg1,
                ),),
            )[0].result)
        finally:
            if added and candidate is not None and ability_data:
                self._remove_captured_engine_ability_instance(
                    candidate,
                    unit_handle,
                    ability_data,
                )

    def apply_direct_ability_to_selected_unit(self, rawcode: int | str) -> int:
        return self._run_direct_selected_ability(
            rawcode,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_TARGET,
            0xA70,
            0,
        )

    def apply_direct_immediate_ability(self, rawcode: int | str) -> int:
        return self._run_direct_selected_ability(
            rawcode,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_IMMEDIATE,
            0x998,
            0,
        )

    def apply_direct_noarg_derived_ability(self, rawcode: int | str) -> int:
        return self._run_direct_selected_ability(
            rawcode,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_NOARG_DERIVED,
            0xA78,
            0,
        )

    def _discover_jass_unit_resolver(self, pm: ProcessMemory) -> int:
        if self._jass_unit_resolver_address:
            if self._is_executable_image_address(pm.regions(), self._jass_unit_resolver_address):
                return self._jass_unit_resolver_address
            self._jass_unit_resolver_address = 0
        add_handler = self._elephant_handlers(pm, ("UnitAddAbility",))["UnitAddAbility"].handler_address
        calls = self._rel32_calls_in_function(pm, add_handler)
        if len(calls) < 2:
            raise RuntimeError("UnitAddAbility 未暴露可验证的单位句柄解析函数")
        resolver = calls[0]
        if not self._is_executable_image_address(pm.regions(), resolver):
            raise RuntimeError("单位句柄解析函数不在游戏可执行代码段")
        self._jass_unit_resolver_address = resolver
        return resolver

    def _discover_buff_data_constructor(self, pm: ProcessMemory, effect_handler: int) -> int:
        if self._buff_data_constructor_address:
            if self._is_executable_image_address(pm.regions(), self._buff_data_constructor_address):
                return self._buff_data_constructor_address
            self._buff_data_constructor_address = 0
        signature = b"\xc7\x41\x20\xff\xff\xff\xff"
        for address in self._rel32_calls_in_function(pm, effect_handler, max_bytes=0x500):
            try:
                code = pm.read(address, 0x180)
            except OSError:
                continue
            if signature not in code[:0x40]:
                continue
            if not self._is_executable_image_address(pm.regions(), address):
                continue
            self._buff_data_constructor_address = address
            return address
        raise RuntimeError("未能从技能效果函数中定位 SBuffData 构造函数")

    def apply_direct_roar_buff_to_selected_unit(self, rawcode: int | str) -> int:
        with self._native_helper_transaction():
            return self._apply_direct_roar_buff_to_selected_unit_locked(rawcode)

    def _apply_direct_roar_buff_to_selected_unit_locked(self, rawcode: int | str) -> int:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if not ability_rawcode:
            raise ValueError("技能 ID 无效")
        added = False
        candidate: UnitCandidate | None = None
        ability_data = 0
        try:
            candidate, unit_handle = self._direct_selected_context()
            with ProcessMemory(self.pid) as pm:
                get_level = self._elephant_handlers(
                    pm,
                    ("GetUnitAbilityLevel",),
                )["GetUnitAbilityLevel"].handler_address
            level = int(self._run_native_helper_ops(
                unit_handle,
                ((
                    self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE_LEVEL,
                    ability_rawcode,
                    get_level,
                    0,
                    0,
                ),),
            )[0].result)
            if not level:
                with ProcessMemory(self.pid) as pm:
                    created_instance, added = self._create_engine_ability_instance(
                        pm,
                        candidate,
                        ability_rawcode,
                        require_wrapper=False,
                    )
                    ability_data = created_instance.data_address
            with ProcessMemory(self.pid) as pm:
                assert candidate is not None
                ability_data = ability_data or self._find_engine_ability_data(
                    pm,
                    candidate,
                    ability_rawcode,
                )
                if not ability_data:
                    raise RuntimeError(
                        f"找不到 {format_rawcode(ability_rawcode)} 的运行时技能实例"
                    )
                ability_vtable = pm.read_u64(ability_data)
                effect_handler = pm.read_u64(ability_vtable + 0x998)
                buff_handler = pm.read_u64(ability_vtable + 0xA00)
                constructor = self._discover_buff_data_constructor(pm, effect_handler)
                regions = pm.regions()
                for label, address in (("AddBuff", buff_handler), ("SBuffData", constructor)):
                    if not self._is_executable_image_address(regions, address):
                        raise RuntimeError(f"{label} 回调不在游戏可执行代码段")
                target_unit = candidate.unit_address
            return int(self._run_native_helper_ops(
                target_unit,
                ((
                    self.NATIVE_HELPER_OP_DIRECT_ABILITY_BUFF,
                    ability_rawcode,
                    buff_handler,
                    ability_data,
                    constructor,
                ),),
            )[0].result)
        finally:
            if added and candidate is not None and ability_data:
                self._remove_captured_engine_ability_instance(
                    candidate,
                    unit_handle,
                    ability_data,
                )

    def _run_direct_ability_over_enemy_units(
        self,
        rawcode: int | str,
        mode: str,
        *,
        success_limit: int = 0,
    ) -> tuple[int, int]:
        with self._native_helper_transaction():
            return self._run_direct_ability_over_enemy_units_locked(
                rawcode,
                mode,
                success_limit=success_limit,
            )

    def _run_direct_ability_over_enemy_units_locked(
        self,
        rawcode: int | str,
        mode: str,
        *,
        success_limit: int = 0,
    ) -> tuple[int, int]:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        mode_values = {"target": (0, 0xA70), "point": (1, 0xA58)}
        if mode not in mode_values:
            raise ValueError(f"不支持的全图直接效果类型：{mode}")
        target_limit = int(success_limit)
        if not 0 <= target_limit <= 0xFFFF:
            raise ValueError("成功目标上限必须在 0 到 65535 之间")
        mode_value, vtable_offset = mode_values[mode]
        added = False
        candidate: UnitCandidate | None = None
        ability_data = 0
        try:
            candidate, unit_handle = self._direct_selected_context()
            with ProcessMemory(self.pid) as pm:
                handlers = self._elephant_handlers(
                    pm,
                    (
                        "GetUnitAbilityLevel",
                        "GetOwningPlayer",
                        "CreateGroup",
                        "GroupEnumUnitsOfPlayer",
                        "FirstOfGroup",
                        "GroupRemoveUnit",
                        "DestroyGroup",
                        "Player",
                        "GetUnitTypeId",
                        "GetWidgetLife",
                        "GetUnitX",
                        "GetUnitY",
                        "IsPlayerEnemy",
                    ),
                )
                resolver = self._discover_jass_unit_resolver(pm)
            level = int(self._run_native_helper_ops(
                unit_handle,
                ((
                    self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE_LEVEL,
                    ability_rawcode,
                    handlers["GetUnitAbilityLevel"].handler_address,
                    0,
                    0,
                ),),
            )[0].result)
            if not level:
                with ProcessMemory(self.pid) as pm:
                    created_instance, added = self._create_engine_ability_instance(
                        pm,
                        candidate,
                        ability_rawcode,
                        require_wrapper=False,
                    )
                    ability_data = created_instance.data_address
            with ProcessMemory(self.pid) as pm:
                assert candidate is not None
                ability_data = ability_data or self._find_engine_ability_data(
                    pm,
                    candidate,
                    ability_rawcode,
                )
                if not ability_data:
                    raise RuntimeError(
                        f"找不到 {format_rawcode(ability_rawcode)} 的运行时技能实例"
                    )
                ability_vtable = pm.read_u64(ability_data)
                direct_handler = pm.read_u64(ability_vtable + vtable_offset)
                if not self._is_executable_image_address(pm.regions(), direct_handler):
                    raise RuntimeError("技能直接效果回调不在游戏可执行代码段")
            flags = mode_value | (target_limit << 16)
            result = self._run_native_helper_ops(
                unit_handle,
                (
                    (
                        self.NATIVE_HELPER_OP_DIRECT_ABILITY_ENUM,
                        ability_rawcode,
                        direct_handler,
                        ability_data,
                        flags,
                    ),
                    (
                        self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                        0,
                        handlers["GetOwningPlayer"].handler_address,
                        handlers["CreateGroup"].handler_address,
                        handlers["GroupEnumUnitsOfPlayer"].handler_address,
                    ),
                    (
                        self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                        0,
                        handlers["FirstOfGroup"].handler_address,
                        handlers["GroupRemoveUnit"].handler_address,
                        handlers["DestroyGroup"].handler_address,
                    ),
                    (
                        self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                        0,
                        handlers["Player"].handler_address,
                        handlers["GetUnitTypeId"].handler_address,
                        handlers["GetWidgetLife"].handler_address,
                    ),
                    (
                        self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                        0,
                        handlers["GetUnitX"].handler_address,
                        handlers["GetUnitY"].handler_address,
                        handlers["IsPlayerEnemy"].handler_address,
                    ),
                    (
                        self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                        vtable_offset,
                        resolver,
                        110000,
                        0,
                    ),
                ),
                timeout_ms=120000,
            )[0]
            packed = int(result.result)
            attempts = (packed >> 32) & 0xFFFFFFFF
            successes = packed & 0xFFFFFFFF
            if len(result.extra_results) != successes:
                raise RuntimeError(
                    f"全图技能返回的目标数量异常：{len(result.extra_results)}!={successes}"
                )
            return attempts, successes
        finally:
            if added and candidate is not None and ability_data:
                self._remove_captured_engine_ability_instance(
                    candidate,
                    unit_handle,
                    ability_data,
                )

    def get_selected_unit_position(self) -> tuple[float, float]:
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(pm, ("GetUnitX", "GetUnitY"))
        results = self._run_native_helper_ops(
            unit_handle,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_UNIT_INT_QUERY,
                    0,
                    handlers["GetUnitX"].handler_address,
                    0,
                    0,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_UNIT_INT_QUERY,
                    0,
                    handlers["GetUnitY"].handler_address,
                    0,
                    0,
                ),
            ),
        )
        return self._float_from_bits(results[0].result), self._float_from_bits(results[1].result)

    def apply_direct_point_ability(
        self,
        rawcode: int | str,
        x: float | None = None,
        y: float | None = None,
    ) -> int:
        if x is None or y is None:
            x, y = self.get_selected_unit_position()
        target_x = float(x)
        target_y = float(y)
        if not math.isfinite(target_x) or not math.isfinite(target_y):
            raise ValueError("技能目标坐标必须是有限数值")
        packed = self._float_bits(target_x) | (self._float_bits(target_y) << 32)
        return self._run_direct_selected_ability(
            rawcode,
            self.NATIVE_HELPER_OP_DIRECT_ABILITY_POINT,
            0xA58,
            packed,
        )

    def enable_selected_toggle_ability(
        self,
        rawcode: int | str,
        order_id: int,
    ) -> int:
        with self._native_helper_transaction():
            return self._enable_selected_toggle_ability_locked(rawcode, order_id)

    def _enable_selected_toggle_ability_locked(
        self,
        rawcode: int | str,
        order_id: int,
    ) -> int:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if not ability_rawcode:
            raise ValueError("技能 ID 无效")
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(
                pm,
                (
                    "GetUnitAbilityLevel",
                    "UnitAddAbility",
                    "BlzUnitHideAbility",
                    "IssueImmediateOrderById",
                ),
            )
        level = int(self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE_LEVEL,
                ability_rawcode,
                handlers["GetUnitAbilityLevel"].handler_address,
                0,
                0,
            ),),
        )[0].result)
        toggle_key = (unit_handle, ability_rawcode)
        if level and toggle_key in self._hidden_toggle_abilities:
            return 1
        added = not level
        if added:
            add_result = int(self._run_native_helper_ops(
                unit_handle,
                ((
                    self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE,
                    ability_rawcode,
                    handlers["UnitAddAbility"].handler_address,
                    0,
                    0,
                ),),
            )[0].result)
            if not add_result:
                raise RuntimeError(f"游戏未能添加 {format_rawcode(ability_rawcode)}")
        if added:
            self._run_native_helper_ops(
                unit_handle,
                ((
                    self.NATIVE_HELPER_OP_JASS_UNIT_INT_BOOL,
                    ability_rawcode,
                    handlers["BlzUnitHideAbility"].handler_address,
                    0,
                    0,
                ),),
            )
        issued = int(self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE,
                int(order_id),
                handlers["IssueImmediateOrderById"].handler_address,
                0,
                0,
            ),),
        )[0].result)
        if added:
            self._run_native_helper_ops(
                unit_handle,
                ((
                    self.NATIVE_HELPER_OP_JASS_UNIT_INT_BOOL,
                    ability_rawcode,
                    handlers["BlzUnitHideAbility"].handler_address,
                    1,
                    0,
                ),),
            )
            if issued:
                self._hidden_toggle_abilities.add(toggle_key)
        return issued

    def _run_selected_ability_effect(
        self,
        rawcode: int | str,
        effect_kind: str,
        *,
        passes: int = 1,
        area: float | None = None,
        hold_seconds: float = 0.0,
        point: tuple[float, float] | None = None,
    ) -> tuple[int, int]:
        with self._native_helper_transaction():
            return self._run_selected_ability_effect_locked(
                rawcode,
                effect_kind,
                passes=passes,
                area=area,
                hold_seconds=hold_seconds,
                point=point,
            )

    def _run_selected_ability_effect_locked(
        self,
        rawcode: int | str,
        effect_kind: str,
        *,
        passes: int = 1,
        area: float | None = None,
        hold_seconds: float = 0.0,
        point: tuple[float, float] | None = None,
    ) -> tuple[int, int]:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        effect_kinds = {
            "immediate": (self.NATIVE_HELPER_OP_DIRECT_ABILITY_IMMEDIATE, 0x998),
            "point": (self.NATIVE_HELPER_OP_DIRECT_ABILITY_POINT, 0xA58),
            "noarg": (self.NATIVE_HELPER_OP_DIRECT_ABILITY_NOARG_DERIVED, 0xA78),
        }
        if effect_kind not in effect_kinds:
            raise ValueError(f"不支持的技能直接效果类型：{effect_kind}")
        pass_count = int(passes)
        if not 1 <= pass_count <= 255:
            raise ValueError("技能执行次数必须在 1 到 255 之间")
        effect_op, vtable_offset = effect_kinds[effect_kind]
        hold_duration = float(hold_seconds)
        if not 0.0 <= hold_duration <= 120.0:
            raise ValueError("技能效果保持时间必须在 0 到 120 秒之间")
        if area is not None:
            area = float(area)
            if not math.isfinite(area) or not 1.0 <= area <= 1000000.0:
                raise ValueError("技能作用范围无效")
        if point is not None:
            x, y = map(float, point)
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError("技能目标坐标必须是有限数值")
        elif effect_kind == "point":
            x, y = self.get_selected_unit_position()
        else:
            x = y = 0.0

        added = False
        pending_key: tuple[int, int] | None = None
        ability_handle = 0
        original_area_bits: int | None = None
        area_field = int.from_bytes(b"aare", "big")
        area_level = 0
        unit_handle = 0
        remove_handler = 0
        get_area_handler = 0
        set_area_handler = 0
        candidate: UnitCandidate | None = None
        ability_data = 0
        try:
            candidate, unit_handle = self._direct_selected_context()
            with ProcessMemory(self.pid) as pm:
                handlers = self._elephant_handlers(
                    pm,
                    (
                        "GetUnitAbilityLevel",
                        "UnitRemoveAbility",
                        "BlzGetUnitAbility",
                        "BlzGetAbilityRealLevelField",
                        "BlzSetAbilityRealLevelField",
                        "BlzUnitHideAbility",
                        "IssueImmediateOrderById",
                    ),
                )
            if hold_duration:
                pending_key = (unit_handle, ability_rawcode)
                with self._pending_direct_effects_lock:
                    if pending_key in self._pending_direct_effects:
                        raise RuntimeError(
                            f"{format_rawcode(ability_rawcode)} 的上一次效果仍在持续"
                        )
                    self._pending_direct_effects.add(pending_key)
            level = int(self._run_native_helper_ops(
                unit_handle,
                ((
                    self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE_LEVEL,
                    ability_rawcode,
                    handlers["GetUnitAbilityLevel"].handler_address,
                    0,
                    0,
                ),),
            )[0].result)
            if not level:
                with ProcessMemory(self.pid) as pm:
                    created_instance, added = self._create_engine_ability_instance(
                        pm,
                        candidate,
                        ability_rawcode,
                        require_wrapper=False,
                    )
                    ability_data = created_instance.data_address
                level = 1
            area_level = max(0, level - 1)
            remove_handler = handlers["UnitRemoveAbility"].handler_address
            get_area_handler = handlers["BlzGetAbilityRealLevelField"].handler_address
            set_area_handler = handlers["BlzSetAbilityRealLevelField"].handler_address
            ability_handle = int(self._run_native_helper_ops(
                unit_handle,
                ((
                    self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE,
                    ability_rawcode,
                    handlers["BlzGetUnitAbility"].handler_address,
                    0,
                    0,
                ),),
            )[0].result)
            if not ability_handle:
                raise RuntimeError(
                    f"游戏未返回 {format_rawcode(ability_rawcode)} 的 ability handle"
                )
            if area is not None:
                original_area_bits = int(self._run_native_helper_ops(
                    ability_handle,
                    ((
                        self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE_LEVEL,
                        area_field,
                        handlers["BlzGetAbilityRealLevelField"].handler_address,
                        area_level,
                        0,
                    ),),
                )[0].result) & 0xFFFFFFFF
                set_result = int(self._run_native_helper_ops(
                    ability_handle,
                    ((
                        self.NATIVE_HELPER_OP_JASS_ABILITY_REAL_LEVEL_FIELD_SET,
                        area_field,
                        set_area_handler,
                        area_level,
                        self._float_bits(area),
                    ),),
                )[0].result)
                if not set_result:
                    raise RuntimeError("游戏拒绝临时放大技能作用范围")
                actual_bits = int(self._run_native_helper_ops(
                    ability_handle,
                    ((
                        self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE_LEVEL,
                        area_field,
                        handlers["BlzGetAbilityRealLevelField"].handler_address,
                        area_level,
                        0,
                    ),),
                )[0].result) & 0xFFFFFFFF
                actual_area = self._float_from_bits(actual_bits)
                if not math.isfinite(actual_area) or actual_area < area * 0.9:
                    raise RuntimeError(f"技能作用范围写入未生效：{actual_area:g}")
            if added and hold_duration:
                self._run_native_helper_ops(
                    unit_handle,
                    ((
                        self.NATIVE_HELPER_OP_JASS_UNIT_INT_BOOL,
                        ability_rawcode,
                        handlers["BlzUnitHideAbility"].handler_address,
                        1,
                        0,
                    ),),
                )
            with ProcessMemory(self.pid) as pm:
                assert candidate is not None
                ability_data = ability_data or self._find_engine_ability_data(
                    pm,
                    candidate,
                    ability_rawcode,
                )
                if not ability_data:
                    raise RuntimeError(
                        f"找不到 {format_rawcode(ability_rawcode)} 的运行时技能实例"
                    )
                ability_vtable = pm.read_u64(ability_data)
                direct_handler = pm.read_u64(ability_vtable + vtable_offset)
                if not self._is_executable_image_address(pm.regions(), direct_handler):
                    raise RuntimeError("技能直接效果回调不在游戏可执行代码段")
                target_unit = candidate.unit_address
            arg1 = self._float_bits(x) | (self._float_bits(y) << 32) if effect_kind == "point" else 0
            succeeded = 0
            for _ in range(pass_count):
                result = self._run_native_helper_ops(
                    target_unit,
                    ((
                        effect_op,
                        ability_rawcode,
                        direct_handler,
                        ability_data,
                        arg1,
                    ),),
                )[0]
                succeeded += 1 if result.result else 0
            if hold_duration:
                time.sleep(hold_duration)
                stop_result = 0
                for stop_attempt in range(3):
                    stop_result = int(self._run_native_helper_ops(
                        unit_handle,
                        ((
                            self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE,
                            851972,
                            handlers["IssueImmediateOrderById"].handler_address,
                            0,
                            0,
                        ),),
                        timeout_ms=10000,
                    )[0].result)
                    if stop_result:
                        break
                    if stop_attempt < 2:
                        time.sleep(0.05 * (stop_attempt + 1))
                if not stop_result:
                    raise RuntimeError("游戏连续 3 次拒绝停止持续技能效果")
            return pass_count, succeeded
        finally:
            active_error = sys.exc_info()[1]
            cleanup_errors: list[str] = []
            if (
                original_area_bits is not None
                and ability_handle
                and get_area_handler
                and set_area_handler
            ):
                try:
                    restored = int(self._run_native_helper_ops(
                        ability_handle,
                        ((
                            self.NATIVE_HELPER_OP_JASS_ABILITY_REAL_LEVEL_FIELD_SET,
                            area_field,
                            set_area_handler,
                            area_level,
                            original_area_bits,
                        ),),
                        timeout_ms=10000,
                    )[0].result)
                    if not restored:
                        raise RuntimeError("游戏拒绝恢复原始作用范围")
                    restored_bits = int(self._run_native_helper_ops(
                        ability_handle,
                        ((
                            self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE_LEVEL,
                            area_field,
                            get_area_handler,
                            area_level,
                            0,
                        ),),
                        timeout_ms=10000,
                    )[0].result) & 0xFFFFFFFF
                    if restored_bits != original_area_bits:
                        raise RuntimeError(
                            "作用范围恢复校验失败："
                            f"0x{restored_bits:08x}!=0x{original_area_bits:08x}"
                        )
                except Exception as exc:
                    cleanup_errors.append(f"恢复作用范围失败：{exc}")
            if added and candidate is not None and ability_data:
                try:
                    self._remove_captured_engine_ability_instance(
                        candidate,
                        unit_handle,
                        ability_data,
                    )
                except Exception as exc:
                    cleanup_errors.append(f"删除临时技能失败：{exc}")
            if pending_key is not None:
                with self._pending_direct_effects_lock:
                    self._pending_direct_effects.discard(pending_key)
            if cleanup_errors:
                cleanup_message = "；".join(cleanup_errors)
                if active_error is not None:
                    raise RuntimeError(
                        f"{active_error}；清理失败：{cleanup_message}"
                    ) from active_error
                raise RuntimeError(cleanup_message)

    def cast_ability_with_runtime_dummy(
        self,
        rawcode: int | str,
        order_id: int,
        cast_type: str,
        *,
        global_scope: bool = False,
        enemy_owner: bool = False,
        self_cast: bool = False,
        remove_self_ability: bool = False,
        point_geometry: str = "target",
        level: int = 1,
        passes: int = 1,
        success_limit: int = 0,
        mana: float = 100000.0,
        cleanup_duration: float = 1.5,
    ) -> tuple[int, int]:
        raise OSError(ERROR_NOT_SUPPORTED, "运行时假单位施法路径已禁用")

    def apply_standard_debuffs_to_selected_unit(self) -> tuple[int, int]:
        target_abilities = ("Acrs", "Aply", "Aslo", "Acri", "Afae", "ANso", "AEer", "ANdo")
        attempted = len(target_abilities) + 1
        succeeded = sum(
            1 if self.apply_direct_ability_to_selected_unit(ability) else 0
            for ability in target_abilities
        )
        succeeded += 1 if self.apply_direct_roar_buff_to_selected_unit("ANht") else 0
        return attempted, succeeded

    def apply_standard_buffs_to_selected_unit(self) -> tuple[int, int]:
        target_abilities = ("Aams", "Ainf", "Ablo", "Auhf", "Afzy", "Alsh", "Arej", "Aivs", "ACfa")
        attempted = len(target_abilities)
        succeeded = sum(
            1 if self.apply_direct_ability_to_selected_unit(ability) else 0
            for ability in target_abilities
        )
        for ability in ("Aroa", "Absk"):
            attempted += 1
            succeeded += 1 if self.apply_direct_immediate_ability(ability) else 0
        attempted += 1
        succeeded += 1 if self.apply_direct_point_ability("Ahwd") else 0
        channel_attempted, channel_succeeded = self._run_selected_ability_effect(
            "AEtq",
            "immediate",
            hold_seconds=12.0,
        )
        attempted += channel_attempted
        succeeded += channel_succeeded
        attempted += 1
        succeeded += 1 if self.enable_selected_toggle_ability("ANms", 852589) else 0
        attempted += 1
        succeeded += 1 if self.apply_direct_noarg_derived_ability("AIsa") else 0
        return attempted, succeeded

    def cast_fullscreen_swarm(self, *, success_limit: int = 0) -> tuple[int, int]:
        entries = ("ACca", "ACcv", "AOsh")
        attempted = succeeded = 0
        for ability in entries:
            current_attempted, current_succeeded = self._run_direct_ability_over_enemy_units(
                ability,
                "point",
                success_limit=success_limit,
            )
            attempted += current_attempted
            succeeded += current_succeeded
        return attempted, succeeded

    def cast_fullscreen_clap(self, *, success_limit: int = 0) -> tuple[int, int]:
        entries = ("AHtc", "AOws")
        attempted = succeeded = 0
        for ability in entries:
            current_attempted, current_succeeded = self._run_selected_ability_effect(
                ability,
                "noarg",
                area=100000.0,
            )
            attempted += current_attempted
            succeeded += current_succeeded
        return attempted, succeeded

    def cast_fullscreen_monsoon(self, *, success_limit: int = 0) -> tuple[int, int]:
        return self._run_selected_ability_effect(
            "ANmo",
            "point",
            area=100000.0,
            hold_seconds=12.0,
        )

    def cast_fullscreen_starfall(self, *, success_limit: int = 0) -> tuple[int, int]:
        return self._run_selected_ability_effect(
            "AEsb",
            "immediate",
            area=100000.0,
            hold_seconds=12.0,
        )

    def cast_fullscreen_forked_lightning(self, *, success_limit: int = 0) -> tuple[int, int]:
        return self._run_direct_ability_over_enemy_units(
            "ACfl",
            "target",
            success_limit=success_limit,
        )

    def cast_fullscreen_auto_effect(self, *, success_limit: int = 0) -> tuple[int, int]:
        passes = int(success_limit) if success_limit else 5
        return self._run_selected_ability_effect(
            "AEfk",
            "noarg",
            passes=passes,
            area=100000.0,
        )

    def create_all_loaded_items(
        self,
        limit: int = 0,
        *,
        dry_run: bool = False,
    ) -> tuple[int, int, tuple[int, ...]]:
        item_limit = int(limit)
        if not 0 <= item_limit <= 100000:
            raise ValueError("创建物品测试上限必须在 0 到 100000 之间")
        with ProcessMemory(self.pid) as pm:
            handlers = self._elephant_handlers(pm, ("ChooseRandomItem", "CreateItem"))
        encoded_limit = item_limit | (0x80000000 if dry_run else 0)
        result = self._run_native_helper_ops(
            0,
            ((
                self.NATIVE_HELPER_OP_CREATE_ALL_ITEMS,
                encoded_limit,
                handlers["ChooseRandomItem"].handler_address,
                handlers["CreateItem"].handler_address,
                0,
            ),),
            timeout_ms=120000,
        )[0]
        packed = int(result.result)
        created = packed & 0xFFFFFFFF
        total = (packed >> 32) & 0xFFFFFFFF
        if not total:
            raise RuntimeError("运行时物品数据库为空")
        handles = tuple(int(handle) for handle in result.extra_results if handle)
        if not dry_run and len(handles) != created:
            raise RuntimeError(
                f"物品创建返回 {created} 个，但句柄列表有 {len(handles)} 个"
            )
        return total, created, handles

    def remove_item_handle(self, item_handle: int) -> None:
        self.remove_item_handles((item_handle,))

    def remove_item_handles(self, item_handles: Iterable[int]) -> int:
        handles = tuple(int(handle) for handle in item_handles if int(handle))
        if not handles:
            return 0
        with ProcessMemory(self.pid) as pm:
            handler = self._elephant_handlers(pm, ("RemoveItem",))["RemoveItem"].handler_address
        removed = 0
        for start in range(0, len(handles), 47):
            batch = handles[start : start + 47]
            first = batch[0]
            second = batch[1] if len(batch) > 1 else 0
            ops: list[tuple[int, int, int, int, int]] = [(
                self.NATIVE_HELPER_OP_REMOVE_ITEM_HANDLES,
                len(batch),
                handler,
                first,
                second,
            )]
            remaining = batch[2:]
            for offset in range(0, len(remaining), 3):
                triple = remaining[offset : offset + 3]
                ops.append((
                    self.NATIVE_HELPER_OP_REMOVE_ITEM_HANDLES_ARG,
                    0,
                    triple[0],
                    triple[1] if len(triple) > 1 else 0,
                    triple[2] if len(triple) > 2 else 0,
                ))
            removed += int(self._run_native_helper_ops(0, tuple(ops))[0].result)
        return removed

    def take_selected_unit_control(self) -> int:
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(pm, ("GetLocalPlayer", "SetUnitOwner"))
        return self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_TAKE_OWNERSHIP,
                0,
                handlers["GetLocalPlayer"].handler_address,
                handlers["SetUnitOwner"].handler_address,
                0,
            ),),
        )[0].result

    def create_local_unit(
        self,
        rawcode: int | str | None = None,
        position: tuple[float, float] | None = None,
    ) -> tuple[int, int]:
        x, y = self.query_mouse_world_position() if position is None else position
        with ProcessMemory(self.pid) as pm:
            candidate = self._elephant_selected_candidate(pm)
            unit_rawcode = (
                candidate.unit_type_id
                if rawcode is None
                else int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
            )
            if not unit_rawcode:
                raise ValueError("没有可用于创建单位的有效 ID")
            handlers = self._elephant_handlers(pm, ("GetLocalPlayer", "CreateUnit"))
        coordinates = struct.unpack("<Q", struct.pack("<ff", float(x), float(y)))[0]
        result = self._run_native_helper_ops(
            0,
            ((
                self.NATIVE_HELPER_OP_JASS_CREATE_LOCAL_UNIT,
                unit_rawcode,
                handlers["GetLocalPlayer"].handler_address,
                handlers["CreateUnit"].handler_address,
                coordinates,
            ),),
        )[0].result
        if not result:
            raise RuntimeError(f"游戏未能创建单位 {format_rawcode(unit_rawcode)}")
        return unit_rawcode, result

    def create_local_units(self, count: int, rawcode: int | str | None = None) -> tuple[int, int]:
        total = int(count)
        if not 1 <= total <= 100:
            raise ValueError("批量复制数量必须在 1 到 100 之间")
        position = self.query_mouse_world_position()
        created = 0
        unit_rawcode = 0
        for _ in range(total):
            unit_rawcode, _handle = self.create_local_unit(rawcode, position)
            created += 1
        return unit_rawcode, created

    def add_item_to_selected_unit(self, rawcode: int | str) -> int:
        item_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if not item_rawcode:
            raise ValueError("物品 ID 无效")
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(pm, ("UnitAddItemById",))
        result = self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE,
                item_rawcode,
                handlers["UnitAddItemById"].handler_address,
                0,
                0,
            ),),
        )[0].result
        if not result:
            raise RuntimeError(f"游戏未能添加物品 {format_rawcode(item_rawcode)}")
        return result

    def clear_selected_unit_inventory(self) -> int:
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(pm, ("UnitItemInSlot", "RemoveItem"))
        return int(self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_CLEAR_INVENTORY,
                0,
                handlers["UnitItemInSlot"].handler_address,
                handlers["RemoveItem"].handler_address,
                0,
            ),),
        )[0].result)

    def set_selected_inventory_charges(self, charges: int) -> int:
        target = int(charges)
        if not 1 <= target <= 1_000_000_000:
            raise ValueError("物品数量必须在 1 到 1000000000 之间")
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(pm, ("UnitItemInSlot", "SetItemCharges"))
        return int(self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_SET_INVENTORY_CHARGES,
                target,
                handlers["UnitItemInSlot"].handler_address,
                handlers["SetItemCharges"].handler_address,
                0,
            ),),
        )[0].result)

    def duplicate_selected_inventory_items(self) -> int:
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(
                pm,
                ("UnitItemInSlot", "GetItemTypeId", "UnitAddItemById"),
            )
        return int(self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_DUPLICATE_INVENTORY,
                0,
                handlers["UnitItemInSlot"].handler_address,
                handlers["GetItemTypeId"].handler_address,
                handlers["UnitAddItemById"].handler_address,
            ),),
        )[0].result)

    def drop_selected_inventory_items(self) -> int:
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(pm, ("UnitItemInSlot", "UnitRemoveItem"))
        return int(self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_DROP_INVENTORY,
                0,
                handlers["UnitItemInSlot"].handler_address,
                handlers["UnitRemoveItem"].handler_address,
                0,
            ),),
        )[0].result)

    def _run_selected_ability_rawcode(self, native_name: str, rawcode: int | str) -> int:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if not ability_rawcode:
            raise ValueError("技能 ID 无效")
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(pm, (native_name,))
        result = self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE,
                ability_rawcode,
                handlers[native_name].handler_address,
                0,
                0,
            ),),
        )[0].result
        return int(result)

    def add_ability_to_selected_unit(self, rawcode: int | str) -> None:
        if not self._run_selected_ability_rawcode("UnitAddAbility", rawcode):
            raise RuntimeError("游戏拒绝添加该技能；目标可能已拥有此技能或地图中没有该对象")

    def remove_ability_from_selected_unit(self, rawcode: int | str) -> None:
        if not self._run_selected_ability_rawcode("UnitRemoveAbility", rawcode):
            raise RuntimeError("游戏拒绝删除该技能；目标可能没有此技能")

    def add_abilities_to_selected_unit(self, rawcodes: Iterable[int | str]) -> int:
        ability_ids = tuple(
            int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
            for rawcode in rawcodes
        )
        if not ability_ids or any(not rawcode for rawcode in ability_ids):
            raise ValueError("技能 ID 列表无效")
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handler = self._elephant_handlers(pm, ("UnitAddAbility",))["UnitAddAbility"].handler_address
        added = 0
        for start in range(0, len(ability_ids), self.NATIVE_HELPER_MAX_OPS):
            results = self._run_native_helper_ops(
                unit_handle,
                tuple(
                    (self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE, rawcode, handler, 0, 0)
                    for rawcode in ability_ids[start : start + self.NATIVE_HELPER_MAX_OPS]
                ),
            )
            added += sum(bool(result.result) for result in results)
        return added

    def add_ability_bundle_to_selected_unit(
        self,
        entries: Iterable[tuple[int | str, int | None]],
    ) -> tuple[int, int]:
        bundle = tuple(
            (
                int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF,
                None if level is None else int(level),
            )
            for rawcode, level in entries
        )
        if not bundle or any(not rawcode for rawcode, _level in bundle):
            raise ValueError("技能组合无效")
        if any(level is not None and not 1 <= level <= 100000 for _rawcode, level in bundle):
            raise ValueError("技能组合等级必须在 1 到 100000 之间")
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(pm, ("UnitAddAbility", "SetUnitAbilityLevel"))
        add_handler = handlers["UnitAddAbility"].handler_address
        level_handler = handlers["SetUnitAbilityLevel"].handler_address
        ops: list[tuple[int, int, int, int, int]] = []
        for rawcode, level in bundle:
            ops.append((self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE, rawcode, add_handler, 0, 0))
            if level is not None:
                ops.append((
                    self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE_LEVEL,
                    rawcode,
                    level_handler,
                    level,
                    0,
                ))
        added = 0
        for start in range(0, len(ops), self.NATIVE_HELPER_MAX_OPS):
            results = self._run_native_helper_ops(
                unit_handle,
                tuple(ops[start : start + self.NATIVE_HELPER_MAX_OPS]),
            )
            added += sum(
                bool(result.result)
                for result in results
                if result.kind == self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE
            )
        return added, len(bundle)

    def replace_selected_inventory_items(
        self,
        slot_items: Iterable[tuple[int, int | str]],
    ) -> int:
        replacements = tuple(
            (
                int(slot),
                int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF,
            )
            for slot, rawcode in slot_items
        )
        if not replacements:
            raise ValueError("物品组合为空")
        if any(not 0 <= slot < 6 or not rawcode for slot, rawcode in replacements):
            raise ValueError("物品槽位或物品 ID 无效")
        if len({slot for slot, _rawcode in replacements}) != len(replacements):
            raise ValueError("物品组合包含重复槽位")
        with ProcessMemory(self.pid) as pm:
            candidate = self._elephant_selected_candidate(pm)
            for slot, rawcode in replacements:
                self._set_inventory_slot_item_via_native_handler(
                    pm,
                    candidate,
                    slot,
                    rawcode,
                )
        return len(replacements)

    def reset_selected_unit_ability(self, rawcode: int | str) -> None:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if not ability_rawcode:
            raise ValueError("技能 ID 无效")
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(pm, ("UnitRemoveAbility", "UnitAddAbility"))
        results = self._run_native_helper_ops(
            unit_handle,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE,
                    ability_rawcode,
                    handlers["UnitRemoveAbility"].handler_address,
                    0,
                    0,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE,
                    ability_rawcode,
                    handlers["UnitAddAbility"].handler_address,
                    0,
                    0,
                ),
            ),
        )
        if not results[1].result:
            raise RuntimeError("游戏拒绝重置该技能；地图中可能没有该对象")

    def remove_all_selected_unit_abilities(self) -> int:
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(
                pm,
                ("BlzGetUnitAbilityByIndex", "BlzGetAbilityId", "UnitRemoveAbility"),
            )
        return int(self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_REMOVE_ALL_ABILITIES,
                0,
                handlers["BlzGetUnitAbilityByIndex"].handler_address,
                handlers["BlzGetAbilityId"].handler_address,
                handlers["UnitRemoveAbility"].handler_address,
            ),),
        )[0].result)

    def set_selected_unit_ability_level(self, rawcode: int | str, level: int) -> int:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        target_level = int(level)
        if not ability_rawcode or not 1 <= target_level <= 100000:
            raise ValueError("请提供有效技能 ID，等级必须在 1 到 100000 之间")
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(pm, ("SetUnitAbilityLevel", "GetUnitAbilityLevel"))
        self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE_LEVEL,
                ability_rawcode,
                handlers["SetUnitAbilityLevel"].handler_address,
                target_level,
                0,
            ),),
        )
        actual = int(self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE,
                ability_rawcode,
                handlers["GetUnitAbilityLevel"].handler_address,
                0,
                0,
            ),),
        )[0].result & 0xFFFFFFFF)
        if actual != target_level:
            raise RuntimeError(f"技能等级写入后读回 {actual}，目标为 {target_level}")
        return actual

    @staticmethod
    def _ability_field_rawcode_text(rawcode: int) -> str:
        try:
            return int(rawcode).to_bytes(4, "big").decode("ascii")
        except (OverflowError, UnicodeDecodeError):
            return format_rawcode(int(rawcode))

    def _ability_effect_class_for_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        ability_rawcode: int,
    ) -> tuple[int, bool, str]:
        try:
            ability_data = self._find_engine_ability_data(
                pm,
                candidate,
                ability_rawcode,
            )
            if not ability_data:
                return ability_rawcode, False, "找不到运行时技能数据对象"
            instance = self._ability_instance_from_data_for_candidate(
                pm,
                candidate,
                ability_data,
                ability_rawcode,
            )
            if instance is None:
                return ability_rawcode, False, "找不到运行时技能包装器"
            if not instance.class_rawcode:
                return ability_rawcode, False, "运行时技能没有可验证的效果类"
            return instance.class_rawcode, True, ""
        except (OSError, RuntimeError) as exc:
            return ability_rawcode, False, str(exc)

    def _selected_ability_field_context_locked(
        self,
        rawcode: int | str,
        level: int,
    ) -> SelectedAbilityFieldContext:
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        level_number = int(level)
        if not ability_rawcode or not 1 <= level_number <= 1000:
            raise ValueError("请提供有效技能 ID，字段等级必须在 1 到 1000 之间")
        candidate, unit_handle = self._direct_selected_context()
        with ProcessMemory(self.pid) as pm:
            handlers = self._discover_native_handlers_near_table(
                pm,
                self.ABILITY_FIELD_NATIVE_NAMES,
            )
        ability_handle = int(self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE,
                ability_rawcode,
                handlers["BlzGetUnitAbility"].handler_address,
                0,
                0,
            ),),
        )[0].result)
        if not ability_handle:
            raise RuntimeError(
                f"当前选中单位没有 {format_rawcode(ability_rawcode)} 的运行时技能实例"
            )
        actual_rawcode = int(self._run_native_helper_ops(
            ability_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_INT_QUERY,
                0,
                handlers["BlzGetAbilityId"].handler_address,
                0,
                0,
            ),),
        )[0].result) & 0xFFFFFFFF
        if actual_rawcode != ability_rawcode:
            raise RuntimeError(
                "技能实例在解析期间发生变化："
                f"{format_rawcode(actual_rawcode)}!={format_rawcode(ability_rawcode)}"
            )
        current_level = int(self._run_native_helper_ops(
            unit_handle,
            ((
                self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE_LEVEL,
                ability_rawcode,
                handlers["GetUnitAbilityLevel"].handler_address,
                0,
                0,
            ),),
        )[0].result)
        with ProcessMemory(self.pid) as pm:
            effect_class, effect_class_verified, effect_class_note = (
                self._ability_effect_class_for_candidate(
                    pm,
                    candidate,
                    ability_rawcode,
                )
            )
        return SelectedAbilityFieldContext(
            candidate=candidate,
            unit_handle=unit_handle,
            ability_handle=ability_handle,
            ability_rawcode=ability_rawcode,
            effect_class=effect_class,
            effect_class_verified=effect_class_verified,
            effect_class_note=effect_class_note,
            current_level=current_level,
            handlers=handlers,
        )

    def _ability_field_get_op(
        self,
        spec: AbilityFieldSpec,
        handlers: dict[str, NativeHandler],
        level_index: int,
    ) -> tuple[int, int, int, int, int]:
        handler_name = self.ABILITY_FIELD_GETTER_NAMES[(spec.value_kind, spec.scope)]
        op_kind = (
            self.NATIVE_HELPER_OP_JASS_ABILITY_LEVEL_FIELD_GET
            if spec.scope == "level"
            else self.NATIVE_HELPER_OP_JASS_ABILITY_FIELD_GET
        )
        return (
            op_kind,
            spec.field_id,
            handlers[handler_name].handler_address,
            level_index if spec.scope == "level" else 0,
            0,
        )

    def _decode_ability_field_value(
        self,
        spec: AbilityFieldSpec,
        raw_value: int,
    ) -> bool | int | float:
        if spec.value_kind == "boolean":
            return bool(int(raw_value) & 1)
        if spec.value_kind == "integer":
            return ctypes.c_int32(int(raw_value) & 0xFFFFFFFF).value
        return self._float_from_bits(raw_value)

    def _read_single_ability_field_locked(
        self,
        ability_handle: int,
        handlers: dict[str, NativeHandler],
        spec: AbilityFieldSpec,
        level_index: int,
    ) -> bool | int | float:
        result = self._run_native_helper_ops(
            ability_handle,
            (self._ability_field_get_op(spec, handlers, level_index),),
        )[0]
        return self._decode_ability_field_value(spec, result.result)

    def read_selected_ability_fields(
        self,
        rawcode: int | str,
        level: int,
    ) -> AbilityFieldSnapshot:
        level_number = int(level)
        level_index = level_number - 1
        with self._native_helper_transaction():
            context = self._selected_ability_field_context_locked(rawcode, level_number)
            effect_text = self._ability_field_rawcode_text(context.effect_class)
            specs = ability_fields_for_effect_class(effect_text)
            values_by_key: dict[tuple[str, str, str], AbilityFieldValue] = {}
            supported = [
                spec
                for spec in specs
                if spec.runtime_supported
                and (context.effect_class_verified or not spec.use_specific)
            ]
            for start in range(0, len(supported), self.NATIVE_HELPER_MAX_OPS):
                batch = supported[start : start + self.NATIVE_HELPER_MAX_OPS]
                try:
                    results = self._run_native_helper_ops(
                        context.ability_handle,
                        tuple(
                            self._ability_field_get_op(
                                spec,
                                context.handlers,
                                level_index,
                            )
                            for spec in batch
                        ),
                    )
                except TimeoutError:
                    raise
                except RuntimeError as exc:
                    for spec in batch:
                        values_by_key[(spec.rawcode, spec.value_kind, spec.scope)] = (
                            AbilityFieldValue(spec, None, "读取失败", str(exc))
                        )
                    continue
                for spec, result in zip(batch, results):
                    value = self._decode_ability_field_value(spec, result.result)
                    if spec.value_kind == "real" and not math.isfinite(float(value)):
                        field_value = AbilityFieldValue(
                            spec,
                            None,
                            "读取异常",
                            "游戏返回了非有限浮点值",
                        )
                    else:
                        field_value = AbilityFieldValue(
                            spec,
                            value,
                            "可尝试" if spec.writable else "只读",
                        )
                    values_by_key[(spec.rawcode, spec.value_kind, spec.scope)] = field_value
            fields: list[AbilityFieldValue] = []
            for spec in specs:
                key = (spec.rawcode, spec.value_kind, spec.scope)
                field_value = values_by_key.get(key)
                if field_value is None:
                    if not context.effect_class_verified and spec.use_specific:
                        field_value = AbilityFieldValue(
                            spec,
                            None,
                            "未确认",
                            context.effect_class_note or "运行时效果类未解析",
                        )
                    else:
                        reason = (
                            "字符串字段的 JASS 句柄 ABI 尚未开放"
                            if spec.value_kind == "string"
                            else "等级数组字段需要单独的数组索引"
                        )
                        field_value = AbilityFieldValue(spec, None, "未开放", reason)
                fields.append(field_value)
        return AbilityFieldSnapshot(
            ability_rawcode=context.ability_rawcode,
            effect_class=context.effect_class,
            current_level=context.current_level,
            requested_level=level_number,
            fields=tuple(fields),
            unit_identity=context.unit_identity,
            effect_class_verified=context.effect_class_verified,
            effect_class_note=context.effect_class_note,
        )

    @staticmethod
    def _coerce_ability_field_value(
        spec: AbilityFieldSpec,
        value: bool | int | float | str,
    ) -> bool | int | float:
        if spec.value_kind == "boolean":
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"1", "true", "yes", "on", "是"}:
                    return True
                if normalized in {"0", "false", "no", "off", "否"}:
                    return False
                raise ValueError("布尔字段请输入 true/false 或 1/0")
            return bool(value)
        if spec.value_kind == "integer":
            parsed = int(value.strip(), 0) if isinstance(value, str) else int(value)
            if not -(1 << 31) <= parsed <= 0xFFFFFFFF:
                raise ValueError("整数字段必须在 -2147483648 到 4294967295 之间")
            return ctypes.c_int32(parsed & 0xFFFFFFFF).value
        parsed = float(value)
        if not math.isfinite(parsed) or not -100_000_000.0 <= parsed <= 100_000_000.0:
            raise ValueError("实数字段必须是 -100000000 到 100000000 之间的有限数值")
        return parsed

    def _ability_field_set_op(
        self,
        spec: AbilityFieldSpec,
        handlers: dict[str, NativeHandler],
        level_index: int,
        value: bool | int | float,
    ) -> tuple[int, int, int, int, int]:
        handler_name = self.ABILITY_FIELD_SETTER_NAMES[(spec.value_kind, spec.scope)]
        handler = handlers[handler_name].handler_address
        if spec.value_kind == "real":
            bits = self._float_bits(float(value))
            if spec.scope == "level":
                return (
                    self.NATIVE_HELPER_OP_JASS_ABILITY_REAL_LEVEL_FIELD_SET,
                    spec.field_id,
                    handler,
                    level_index,
                    bits,
                )
            return (
                self.NATIVE_HELPER_OP_JASS_ABILITY_REAL_FIELD_SET,
                spec.field_id,
                handler,
                bits,
                0,
            )
        bits = int(bool(value)) if spec.value_kind == "boolean" else int(value) & 0xFFFFFFFF
        if spec.scope == "level":
            return (
                self.NATIVE_HELPER_OP_JASS_ABILITY_SCALAR_LEVEL_FIELD_SET,
                spec.field_id,
                handler,
                level_index,
                bits,
            )
        return (
            self.NATIVE_HELPER_OP_JASS_ABILITY_SCALAR_FIELD_SET,
            spec.field_id,
            handler,
            bits,
            0,
        )

    def _ability_field_values_equal(
        self,
        spec: AbilityFieldSpec,
        actual: bool | int | float,
        target: bool | int | float,
    ) -> bool:
        if spec.value_kind == "real":
            return self._float_bits(float(actual)) == self._float_bits(float(target))
        return actual == target

    def set_selected_ability_field(
        self,
        rawcode: int | str,
        level: int,
        spec: AbilityFieldSpec,
        value: bool | int | float | str,
        expected_snapshot: AbilityFieldSnapshot | None = None,
    ) -> AbilityFieldValue:
        if self._ability_field_write_disabled:
            raise RuntimeError("上一次技能字段回滚无法确认，请重新连接游戏后再写入")
        if not spec.runtime_supported or not spec.writable:
            raise ValueError("该字段当前未开放运行时写入")
        level_number = int(level)
        ability_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        if expected_snapshot is not None:
            if ability_rawcode != expected_snapshot.ability_rawcode:
                raise RuntimeError("技能 ID 已变化，请重新读取字段")
            if level_number != expected_snapshot.requested_level:
                raise RuntimeError("字段等级已变化，请重新读取字段")
        target = self._coerce_ability_field_value(spec, value)
        level_index = level_number - 1
        with self._native_helper_transaction():
            context = self._selected_ability_field_context_locked(
                ability_rawcode,
                level_number,
            )
            if expected_snapshot is not None:
                if (
                    any(expected_snapshot.unit_identity)
                    and context.unit_identity != expected_snapshot.unit_identity
                ):
                    raise RuntimeError("当前选中单位已变化，请重新读取字段")
                if context.current_level != expected_snapshot.current_level:
                    raise RuntimeError("技能当前等级已变化，请重新读取字段")
                if (
                    context.effect_class != expected_snapshot.effect_class
                    or context.effect_class_verified
                    != expected_snapshot.effect_class_verified
                ):
                    raise RuntimeError("当前技能效果类已经变化，请重新读取字段")
            if spec.use_specific and not context.effect_class_verified:
                raise RuntimeError(
                    "运行时效果类未确认，不能写入效果类专用字段："
                    f"{context.effect_class_note or '请重新读取'}"
                )
            applicable = {
                (field.rawcode, field.value_kind, field.scope)
                for field in ability_fields_for_effect_class(
                    self._ability_field_rawcode_text(context.effect_class)
                )
            }
            key = (spec.rawcode, spec.value_kind, spec.scope)
            if key not in applicable or ABILITY_FIELD_BY_KEY.get(key) != spec:
                raise RuntimeError("当前技能效果类已经变化，请重新读取字段")
            original = self._read_single_ability_field_locked(
                context.ability_handle,
                context.handlers,
                spec,
                level_index,
            )

            def write_field(field_value: bool | int | float) -> bool:
                result = self._run_native_helper_ops(
                    context.ability_handle,
                    (self._ability_field_set_op(
                        spec,
                        context.handlers,
                        level_index,
                        field_value,
                    ),),
                )[0]
                return bool(result.result)

            try:
                if not write_field(target):
                    raise RuntimeError("游戏拒绝写入该技能字段")
                actual = self._read_single_ability_field_locked(
                    context.ability_handle,
                    context.handlers,
                    spec,
                    level_index,
                )
                if not self._ability_field_values_equal(spec, actual, target):
                    raise RuntimeError(
                        f"字段写入后读回不一致：{actual!s}!={target!s}"
                    )
            except Exception as exc:
                rollback_ok = False
                try:
                    write_field(original)
                    restored = self._read_single_ability_field_locked(
                        context.ability_handle,
                        context.handlers,
                        spec,
                        level_index,
                    )
                    rollback_ok = self._ability_field_values_equal(
                        spec,
                        restored,
                        original,
                    )
                except Exception:
                    rollback_ok = False
                if not rollback_ok:
                    self._ability_field_write_disabled = True
                    raise RuntimeError(f"{exc}；原始字段恢复无法确认") from exc
                raise
        return AbilityFieldValue(spec, actual, "已验证")

    def set_local_player_tech(self, rawcode: int | str, level: int) -> int:
        tech_rawcode = int(self._coerce_memory_value("rawcode", rawcode)) & 0xFFFFFFFF
        target_level = int(level)
        if not tech_rawcode or not 0 <= target_level <= 100000:
            raise ValueError("请提供有效科技 ID，等级必须在 0 到 100000 之间")
        with ProcessMemory(self.pid) as pm:
            handlers = self._elephant_handlers(
                pm,
                ("GetLocalPlayer", "SetPlayerTechMaxAllowed", "SetPlayerTechResearched"),
            )
        self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_SET_LOCAL_TECH,
                    tech_rawcode,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["SetPlayerTechMaxAllowed"].handler_address,
                    target_level,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_SET_LOCAL_TECH,
                    tech_rawcode,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["SetPlayerTechResearched"].handler_address,
                    target_level,
                ),
            ),
        )
        return target_level

    def set_local_player_xp_rate(self, rate: float) -> float:
        target = float(rate)
        if not 0.0 <= target <= 10000.0:
            raise ValueError("经验倍率必须在 0 到 10000 之间")
        with ProcessMemory(self.pid) as pm:
            handlers = self._elephant_handlers(pm, ("GetLocalPlayer", "SetPlayerHandicapXP"))
        self._run_native_helper_ops(
            0,
            ((
                self.NATIVE_HELPER_OP_JASS_SET_LOCAL_XP_RATE,
                self._float_bits(target),
                handlers["GetLocalPlayer"].handler_address,
                handlers["SetPlayerHandicapXP"].handler_address,
                0,
            ),),
        )
        return target

    def get_map_fog_state(self) -> tuple[bool, bool]:
        with ProcessMemory(self.pid) as pm:
            handlers = self._elephant_handlers(pm, ("IsFogEnabled", "IsFogMaskEnabled"))
        results = self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_WORLD_INT_QUERY,
                    0,
                    handlers["IsFogEnabled"].handler_address,
                    0,
                    0,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_WORLD_INT_QUERY,
                    0,
                    handlers["IsFogMaskEnabled"].handler_address,
                    0,
                    0,
                ),
            ),
        )
        return bool(results[0].result), bool(results[1].result)

    def set_map_revealed(self, revealed: bool) -> None:
        with ProcessMemory(self.pid) as pm:
            handlers = self._elephant_handlers(pm, ("FogEnable", "FogMaskEnable"))
        fog_enabled = 0 if revealed else 1
        self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_FOG_BOOL,
                    fog_enabled,
                    handlers["FogEnable"].handler_address,
                    0,
                    0,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_FOG_BOOL,
                    fog_enabled,
                    handlers["FogMaskEnable"].handler_address,
                    0,
                    0,
                ),
            ),
        )

    def set_game_paused(self, paused: bool) -> None:
        with ProcessMemory(self.pid) as pm:
            handlers = self._elephant_handlers(pm, ("PauseGame",))
        self._run_native_helper_ops(
            0,
            ((
                self.NATIVE_HELPER_OP_JASS_WORLD_BOOL,
                1 if paused else 0,
                handlers["PauseGame"].handler_address,
                0,
                0,
            ),),
        )

    def end_current_game(self, show_score_screen: bool = True) -> None:
        with ProcessMemory(self.pid) as pm:
            handlers = self._elephant_handlers(pm, ("EndGame",))
        self._run_native_helper_ops(
            0,
            ((
                self.NATIVE_HELPER_OP_JASS_WORLD_BOOL,
                1 if show_score_screen else 0,
                handlers["EndGame"].handler_address,
                0,
                0,
            ),),
        )

    def set_peace_mode(self, enabled: bool) -> int:
        with ProcessMemory(self.pid) as pm:
            handlers = self._elephant_handlers(pm, ("Player", "SetPlayerAlliance"))
        return int(self._run_native_helper_ops(
            0,
            ((
                self.NATIVE_HELPER_OP_JASS_PEACE_MODE,
                1 if enabled else 0,
                handlers["Player"].handler_address,
                handlers["SetPlayerAlliance"].handler_address,
                0,
            ),),
        )[0].result)

    def kill_selected_owner_units(self) -> int:
        with ProcessMemory(self.pid) as pm:
            unit_handle = self._elephant_selected_handle(pm)
            handlers = self._elephant_handlers(
                pm,
                (
                    "GetOwningPlayer",
                    "CreateGroup",
                    "GroupEnumUnitsOfPlayer",
                    "FirstOfGroup",
                    "GroupRemoveUnit",
                    "KillUnit",
                    "DestroyGroup",
                ),
            )
        return int(self._run_native_helper_ops(
            unit_handle,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_KILL_OWNER_UNITS,
                    0,
                    handlers["GetOwningPlayer"].handler_address,
                    handlers["CreateGroup"].handler_address,
                    handlers["GroupEnumUnitsOfPlayer"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handlers["FirstOfGroup"].handler_address,
                    handlers["GroupRemoveUnit"].handler_address,
                    handlers["KillUnit"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_MULTI_ARG,
                    0,
                    handlers["DestroyGroup"].handler_address,
                    0,
                    0,
                ),
            ),
            timeout_ms=3000,
        )[0].result)

    @staticmethod
    def _scan_bytes_private_between(
        pm: ProcessMemory,
        pattern: bytes,
        start_address: int,
        end_address: int,
    ) -> list[int]:
        if not pattern or end_address <= start_address:
            return []
        hits: list[int] = []
        tail_len = max(0, len(pattern) - 1)
        for region in pm.regions():
            if region.typ != MEM_PRIVATE:
                continue
            start = max(region.base, start_address)
            end = min(region.base + region.size, end_address)
            if end <= start:
                continue
            offset = start - region.base
            limit = end - region.base
            tail = b""
            while offset < limit:
                size = min(4 * 1024 * 1024, limit - offset)
                try:
                    data = tail + pm.read(region.base + offset, size)
                except OSError:
                    offset += size
                    tail = b""
                    continue
                base = region.base + offset - len(tail)
                search = 0
                while True:
                    index = data.find(pattern, search)
                    if index < 0:
                        break
                    address = base + index
                    if start_address <= address < end_address:
                        hits.append(address)
                    search = index + 1
                tail = data[-tail_len:] if tail_len else b""
                offset += size
        return hits

    def _ability_instance_from_data_for_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        data_address: int,
        rawcode: int,
    ) -> AbilityInstance | None:
        if self._ability_data_instance_for_candidate(
            pm,
            candidate,
            data_address,
            rawcode,
        ) is None:
            return None
        component_rawcodes = {tag >> 32 for tag in self.COMPONENT_TAGS.values()}
        cache_key = (candidate.handle, data_address, rawcode)
        cached = self._ability_instance_by_data.get(cache_key)
        if cached is not None:
            refreshed = self._ability_instance_from_wrapper(
                pm,
                candidate,
                cached.wrapper_address,
                component_rawcodes,
            )
            if (
                refreshed is not None
                and refreshed.data_address == data_address
                and refreshed.rawcode == rawcode
            ):
                return replace(refreshed, slot=cached.slot)
            self._ability_instance_by_data.pop(cache_key, None)

        data_pattern = struct.pack("<Q", data_address)
        near_start = max(0, candidate.owner_address - 0x05000000)
        near_end = candidate.owner_address + 0x00800000
        near_refs = self._scan_bytes_private_between(pm, data_pattern, near_start, near_end)
        all_refs = near_refs or pm.scan_bytes_private(data_pattern, max_region_size=8 * 1024 * 1024)
        for data_ref in all_refs:
            wrapper = data_ref - 0x90
            instance = self._ability_instance_from_wrapper(pm, candidate, wrapper, component_rawcodes)
            if instance is None:
                continue
            if instance.data_address == data_address and instance.rawcode == rawcode:
                self._ability_instance_by_data[cache_key] = instance
                return instance
        return None

    def _ability_data_instance_for_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        data_address: int,
        rawcode: int,
    ) -> AbilityInstance | None:
        if not self._sane_heap_ptr(data_address):
            return None
        try:
            data_vtable = pm.read_u64(data_address)
            unit_address = pm.read_u64(data_address + 0x68)
            data_rawcode = pm.read_u32(data_address + 0x70)
            mirror_rawcode = pm.read_u32(data_address + 0x78)
            data_cache_pointer = pm.read_u64(data_address + 0xA0)
        except OSError:
            return None
        if not self._looks_like_vtable(data_vtable):
            return None
        if unit_address != candidate.unit_address:
            return None
        if data_rawcode != rawcode or mirror_rawcode != rawcode:
            return None
        return AbilityInstance(
            slot=0,
            wrapper_address=0,
            data_address=data_address,
            wrapper_vtable=0,
            data_vtable=data_vtable,
            wrapper_tag_address=0,
            wrapper_tag=0,
            handle=0,
            class_rawcode=rawcode,
            rawcode=rawcode,
            rawcode_address=data_address + 0x70,
            mirror_rawcode_address=data_address + 0x78,
            data_cache_address=data_address + 0xA0,
            data_cache_pointer=(
                data_cache_pointer if self._sane_heap_ptr(data_cache_pointer) else 0
            ),
        )

    def _create_engine_ability_instance(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        rawcode: int,
        *,
        refresh_after_add: bool = True,
        require_wrapper: bool = True,
    ) -> tuple[AbilityInstance, bool]:
        if not candidate.unit_address:
            raise RuntimeError("当前单位缺少运行时 unit 指针，不能从资源创建技能模板")
        internals = self._discover_native_ability_internals(pm)
        existing_data = self._find_engine_ability_data(pm, candidate, rawcode)
        if existing_data:
            instance = (
                self._ability_instance_from_data_for_candidate(
                    pm,
                    candidate,
                    existing_data,
                    rawcode,
                )
                if require_wrapper
                else self._ability_data_instance_for_candidate(
                    pm,
                    candidate,
                    existing_data,
                    rawcode,
                )
            )
            if instance is not None:
                return instance, False
            raise RuntimeError(
                f"当前单位已存在 {format_rawcode(rawcode)}，但无法安全映射到运行时实例"
            )
        results = self._run_native_helper_ops(
            candidate.unit_address,
            (
                (self.NATIVE_HELPER_OP_INTERNAL_ABILITY_BEGIN, 0, internals.begin_address, 0, 0),
                (self.NATIVE_HELPER_OP_INTERNAL_ABILITY_ADD, rawcode, internals.add_address, 0, 0),
                (self.NATIVE_HELPER_OP_INTERNAL_ABILITY_END, 0, internals.end_address, 0, 0),
            ),
        )
        data_address = results[1].result if len(results) >= 2 else 0
        if not data_address:
            raise RuntimeError(f"引擎未能从资源创建 {format_rawcode(rawcode)} 运行时技能实例")
        if refresh_after_add:
            self._run_native_helper_ops(
                candidate.unit_address,
                (
                    (
                        self.NATIVE_HELPER_OP_INTERNAL_ABILITY_REFRESH,
                        0,
                        internals.refresh_address,
                        0,
                        0,
                    ),
                ),
            )
        instance: AbilityInstance | None = None
        for lookup_delay in (0.05, 0.10):
            time.sleep(lookup_delay)
            if require_wrapper:
                pm.regions(force_refresh=True)
                instance = self._ability_instance_from_data_for_candidate(
                    pm,
                    candidate,
                    data_address,
                    rawcode,
                )
            elif self._find_engine_ability_data(pm, candidate, rawcode) == data_address:
                instance = self._ability_data_instance_for_candidate(
                    pm,
                    candidate,
                    data_address,
                    rawcode,
                )
            if instance is not None:
                break
        if instance is None:
            current_instances = self._ability_instances_from_candidate(
                pm,
                candidate,
                required_rawcodes={rawcode},
                allow_global_scan=True,
            )
            if len(current_instances) == 1:
                instance = current_instances[0]
        if instance is None:
            create_error = (
                f"引擎创建了 {format_rawcode(rawcode)}，"
                "但未能反查到当前单位上的运行时实例"
            )
            try:
                self._remove_engine_ability_instance(pm, candidate, data_address)
            except Exception as cleanup_exc:
                raise RuntimeError(
                    f"{create_error}；回滚创建实例失败：{cleanup_exc}"
                ) from cleanup_exc
            raise RuntimeError(create_error)
        return instance, True

    def _temporary_engine_ability_template(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        rawcode: int,
    ) -> tuple[dict[str, object], str]:
        instance, created = self._create_engine_ability_instance(
            pm,
            candidate,
            rawcode,
            refresh_after_add=False,
        )
        try:
            template = self._ability_runtime_template_from_instance(pm, instance)
            source = (
                f"engine-created wrapper=0x{instance.wrapper_address:x} "
                f"class={instance.class_text}"
            )
        finally:
            if created:
                self._remove_engine_ability_instance(pm, candidate, instance.data_address)
        return template, source

    def _replace_engine_ability_instance(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        old_instance: AbilityInstance,
        new_rawcode: int,
    ) -> AbilityInstance:
        new_instance, created = self._create_engine_ability_instance(
            pm,
            candidate,
            new_rawcode,
            refresh_after_add=False,
        )
        if not created:
            raise RuntimeError(
                f"当前单位已存在 {format_rawcode(new_rawcode)}，不能作为新的替换实例"
            )
        if new_instance.data_address == old_instance.data_address:
            raise RuntimeError(
                f"引擎返回的新技能实例与旧实例相同：0x{new_instance.data_address:x}"
            )
        try:
            self._remove_engine_ability_instance(pm, candidate, old_instance.data_address)
        except Exception:
            try:
                self._remove_engine_ability_instance(pm, candidate, new_instance.data_address)
            except Exception:
                pass
            raise

        time.sleep(0.05)
        active_data = self._find_engine_ability_data(pm, candidate, new_rawcode)
        if not active_data:
            raise RuntimeError(f"引擎替换后找不到 {format_rawcode(new_rawcode)} 运行时实例")
        final_instance = self._ability_instance_from_data_for_candidate(
            pm,
            candidate,
            active_data,
            new_rawcode,
        )
        if final_instance is None:
            current_instances = self._ability_instances_from_candidate(
                pm,
                candidate,
                required_rawcodes={new_rawcode},
                allow_global_scan=True,
            )
            if len(current_instances) == 1:
                final_instance = current_instances[0]
        if final_instance is None:
            raise RuntimeError(
                f"引擎替换了 {format_rawcode(new_rawcode)}，但未能反查到当前单位上的运行时实例"
            )
        return replace(final_instance, slot=old_instance.slot)

    def _find_engine_ability_data(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        rawcode: int,
    ) -> int:
        internals = self._discover_native_ability_internals(pm)
        results = self._run_native_helper_ops(
            candidate.unit_address,
            (
                (self.NATIVE_HELPER_OP_INTERNAL_ABILITY_FIND, rawcode, internals.find_address, 0, 0),
            ),
        )
        return results[0].result if results else 0

    def _remove_engine_ability_instance(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        data_address: int,
    ) -> None:
        if not data_address:
            return
        try:
            rawcode = pm.read_u32(data_address + 0x70)
        except OSError as exc:
            raise RuntimeError(
                f"临时 ability 实例已不可读，停止内部删除：0x{data_address:x}"
            ) from exc
        if not rawcode:
            raise RuntimeError(f"临时 ability 实例 rawcode 无效：0x{data_address:x}")
        internals = self._discover_native_ability_internals(pm)
        self._run_native_helper_ops(
            candidate.unit_address,
            (
                (
                    self.NATIVE_HELPER_OP_INTERNAL_ABILITY_REMOVE,
                    rawcode,
                    internals.remove_address,
                    data_address,
                    internals.find_address,
                ),
                (
                    self.NATIVE_HELPER_OP_INTERNAL_ABILITY_REFRESH,
                    0,
                    internals.refresh_address,
                    0,
                    0,
                ),
            ),
        )
        time.sleep(0.05)
        found = self._find_engine_ability_data(pm, candidate, rawcode)
        if found == data_address:
            raise RuntimeError(f"临时 ability 实例仍挂在当前单位上：0x{data_address:x}")

    def _discover_native_hero_int_internals(self, pm: ProcessMemory) -> tuple[int, int]:
        if self._native_hero_int_set_address and self._native_hero_int_get_address:
            regions = pm.regions()
            if (
                self._is_executable_image_address(regions, self._native_hero_int_set_address)
                and self._is_executable_image_address(regions, self._native_hero_int_get_address)
            ):
                return self._native_hero_int_set_address, self._native_hero_int_get_address

        wanted = {"SetHeroInt", "GetHeroInt"}
        handlers = {
            name: self._native_handlers[name]
            for name in wanted
            if name in self._native_handlers
        }
        if set(handlers) != wanted:
            regions = pm.regions()
            table_region = self._find_native_table_region(pm, regions)
            nearby_regions = [
                region
                for region in regions
                if region.typ == MEM_PRIVATE
                and region.size <= 0x40000
                and region.base < 0x700000000000
                and abs(region.base - table_region.base) <= 0x200000
            ]
            nearby_regions.sort(key=lambda region: (abs(region.base - table_region.base), -region.base))
            for region in nearby_regions:
                missing = wanted.difference(handlers)
                if not missing:
                    break
                try:
                    blob = self._native_table_blob_for_region(pm, region)
                except OSError:
                    continue
                handlers.update(
                    self._find_native_handlers_in_table_blob(
                        pm,
                        regions,
                        blob,
                        region.base,
                        missing,
                    )
                )
            self._native_handlers.update(handlers)
        if set(handlers) != wanted:
            handlers = self._discover_native_handlers(pm, wanted)
        set_calls = self._rel32_calls_in_function(pm, handlers["SetHeroInt"].handler_address, max_bytes=0x80)
        get_jumps = self._rel32_jumps_in_function(pm, handlers["GetHeroInt"].handler_address, max_bytes=0x80)
        if len(set_calls) < 3:
            raise RuntimeError("未能从 SetHeroInt handler 定位内部智力写入函数")
        if not get_jumps:
            raise RuntimeError("未能从 GetHeroInt handler 定位内部智力读取函数")

        set_address = set_calls[-1]
        get_address = get_jumps[-1]
        regions = pm.regions()
        if not self._is_executable_image_address(regions, set_address):
            raise RuntimeError(f"内部智力写入函数地址不可执行：0x{set_address:x}")
        if not self._is_executable_image_address(regions, get_address):
            raise RuntimeError(f"内部智力读取函数地址不可执行：0x{get_address:x}")
        self._native_hero_int_set_address = set_address
        self._native_hero_int_get_address = get_address
        return set_address, get_address

    @staticmethod
    def _native_result_i32(result: int) -> int:
        value = result & 0xFFFFFFFF
        if value & 0x80000000:
            value -= 0x100000000
        return value

    def _get_hero_intelligence_via_native_internal(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        include_bonus: bool,
    ) -> int:
        _set_address, get_address = self._discover_native_hero_int_internals(pm)
        results = self._run_native_helper_ops(
            candidate.unit_address,
            (
                (
                    self.NATIVE_HELPER_OP_GET_HERO_INT,
                    0,
                    get_address,
                    1 if include_bonus else 0,
                    0,
                ),
            ),
        )
        return self._native_result_i32(results[0].result)

    def _get_hero_intelligence_pair_via_native_internal(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
    ) -> tuple[int, int]:
        _set_address, get_address = self._discover_native_hero_int_internals(pm)
        results = self._run_native_helper_ops(
            candidate.unit_address,
            (
                (self.NATIVE_HELPER_OP_GET_HERO_INT, 0, get_address, 0, 0),
                (self.NATIVE_HELPER_OP_GET_HERO_INT, 0, get_address, 1, 0),
            ),
        )
        return self._native_result_i32(results[0].result), self._native_result_i32(results[1].result)

    def _discover_jass_unit_resolver_win10(self, pm: ProcessMemory) -> int:
        if self._jass_unit_resolver_address:
            if self._is_executable_image_address(pm.regions(), self._jass_unit_resolver_address):
                return self._jass_unit_resolver_address
            self._jass_unit_resolver_address = 0
        handler = self._discover_native_handlers(pm, ("UnitAddAbility",))["UnitAddAbility"]
        calls = self._rel32_calls_in_function(pm, handler.handler_address)
        if len(calls) < 2:
            raise RuntimeError("备用读取未能从 UnitAddAbility 定位单位句柄解析函数")
        resolver = calls[0]
        if not self._is_executable_image_address(pm.regions(), resolver):
            raise RuntimeError("备用读取的单位句柄解析函数不在游戏可执行代码段")
        self._jass_unit_resolver_address = resolver
        return resolver

    def _resolve_jass_unit_handle_win10(
        self,
        pm: ProcessMemory,
        unit_handle: int,
        *,
        allow_missing: bool = False,
    ) -> int:
        if not unit_handle:
            return 0
        resolver = self._discover_jass_unit_resolver_win10(pm)
        try:
            return int(
                self._run_native_helper_ops(
                    unit_handle,
                    ((self.NATIVE_HELPER_OP_JASS_UNIT_RESOLVE, 0, resolver, 0, 0),),
                )[0].result
            )
        except RuntimeError as exc:
            if allow_missing and (
                f"error={ERROR_NOT_FOUND}" in str(exc)
                or f"last_error={ERROR_NOT_FOUND}" in str(exc)
            ):
                return 0
            raise

    def _get_hero_intelligence_pair_via_jass_win10(
        self,
        pm: ProcessMemory,
        unit_handle: int,
    ) -> tuple[int, int]:
        handlers = self._discover_native_handlers(pm, ("GetHeroInt",))
        get_handler = handlers["GetHeroInt"].handler_address
        results = self._run_native_helper_ops(
            unit_handle,
            (
                (self.NATIVE_HELPER_OP_GET_HERO_INT, 0, get_handler, 0, 0),
                (self.NATIVE_HELPER_OP_GET_HERO_INT, 0, get_handler, 1, 0),
            ),
        )
        return self._native_result_i32(results[0].result), self._native_result_i32(results[1].result)

    def _current_jass_unit_handle_win10(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        diagnostics: Win10ReadLogger,
    ) -> int:
        unit_handle, handle_id, player_handle = self._read_jass_selected_unit_raw_win10(pm)
        resolved_unit = self._resolve_jass_unit_handle_win10(
            pm,
            unit_handle,
            allow_missing=True,
        )
        diagnostics.log(
            "backup_current_selection_check",
            jass_handle=f"0x{unit_handle:x}",
            handle_id=f"0x{handle_id:x}",
            player=f"0x{player_handle:x}",
            resolved_unit=f"0x{resolved_unit:x}",
            expected_unit=f"0x{candidate.unit_address:x}",
        )
        if not resolved_unit or resolved_unit != candidate.unit_address:
            raise RuntimeError("当前选择已经变化，请重新点击备用读取后再写入")
        return unit_handle

    def _replace_win10_intelligence_field(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        fields: list[UnitMemoryField],
        diagnostics: Win10ReadLogger,
    ) -> list[UnitMemoryField]:
        index = next(
            (index for index, field in enumerate(fields) if field.key == "intelligence_total"),
            None,
        )
        if index is None:
            return fields
        field = fields[index]
        try:
            unit_handle = self._current_jass_unit_handle_win10(pm, candidate, diagnostics)
            base_value, total_value = self._get_hero_intelligence_pair_via_jass_win10(
                pm,
                unit_handle,
            )
        except Exception as exc:
            diagnostics.log("backup_intelligence_read_fallback", exception=repr(exc))
            return fields
        updated = list(fields)
        updated[index] = replace(
            field,
            value_type="i32",
            value=total_value,
            note=(
                "备用读取通过 JASS GetHeroInt 获取真实总智力；"
                f"基础智力={base_value}"
            ),
        )
        diagnostics.log(
            "backup_intelligence_read",
            base=base_value,
            total=total_value,
            unit=f"0x{candidate.unit_address:x}",
        )
        return updated

    def _write_hero_intelligence_field_win10(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        field: UnitMemoryField,
        value: int | float | str,
        diagnostics: Win10ReadLogger,
    ) -> UnitMemoryField:
        target_total = self._coerce_hero_intelligence_target(value)
        unit_handle = self._current_jass_unit_handle_win10(pm, candidate, diagnostics)
        handlers = self._discover_native_handlers(pm, ("SetHeroInt", "GetHeroInt"))
        set_handler = handlers["SetHeroInt"].handler_address
        current_base, current_total = self._get_hero_intelligence_pair_via_jass_win10(
            pm,
            unit_handle,
        )
        current_bonus = current_total - current_base
        target_base = target_total - current_bonus
        if target_base < 0:
            raise ValueError(f"目标智力低于当前加成 {current_bonus}，无法保持加成并写成该总值")

        def set_base(base_value: int) -> None:
            self._run_native_helper_ops(
                unit_handle,
                (
                    (
                        self.NATIVE_HELPER_OP_JASS_UNIT_INT_BOOL,
                        base_value & 0xFFFFFFFF,
                        set_handler,
                        1,
                        0,
                    ),
                ),
            )

        set_base(target_base)
        time.sleep(0.05)
        final_base, final_total = self._get_hero_intelligence_pair_via_jass_win10(
            pm,
            unit_handle,
        )
        if final_total != target_total:
            corrected_base = final_base + (target_total - final_total)
            if corrected_base < 0:
                raise RuntimeError(
                    f"备用 SetHeroInt 写入后总智力={final_total}，无法修正到目标 {target_total}"
                )
            set_base(corrected_base)
            time.sleep(0.05)
            final_base, final_total = self._get_hero_intelligence_pair_via_jass_win10(
                pm,
                unit_handle,
            )
        if final_total != target_total:
            raise RuntimeError(f"备用 SetHeroInt 写入后总智力={final_total}，目标={target_total}")
        diagnostics.log(
            "backup_intelligence_write",
            current_base=current_base,
            current_total=current_total,
            target_total=target_total,
            final_base=final_base,
            final_total=final_total,
            bonus=current_bonus,
        )
        return replace(
            field,
            value_type="i32",
            value=final_total,
            note=(
                f"备用 JASS SetHeroInt 已写入；总智力 {current_total}->{final_total}，"
                f"基础智力 {current_base}->{final_base}，当前加成 {current_bonus}"
            ),
        )

    @staticmethod
    def _coerce_hero_intelligence_target(value: int | float | str) -> int:
        try:
            numeric = float(str(value).strip()) if isinstance(value, str) else float(value)
        except ValueError as exc:
            raise ValueError("目标智力必须是整数") from exc
        if not math.isfinite(numeric) or numeric != int(numeric):
            raise ValueError("目标智力必须是整数")
        target = int(numeric)
        if not 0 <= target <= 1000000:
            raise ValueError("目标智力必须在 0 到 1000000 之间")
        return target

    def _write_hero_intelligence_field(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        field: UnitMemoryField,
        value: int | float | str,
    ) -> UnitMemoryField:
        if not candidate.unit_address:
            raise RuntimeError("当前单位缺少运行时 unit 指针，不能调用内部 SetHeroInt")
        target_total = self._coerce_hero_intelligence_target(value)
        set_address, _get_address = self._discover_native_hero_int_internals(pm)
        current_base, current_total = self._get_hero_intelligence_pair_via_native_internal(pm, candidate)
        current_bonus = current_total - current_base
        target_base = target_total - current_bonus
        if target_base < 0:
            raise ValueError(f"目标智力低于当前加成 {current_bonus}，无法保持加成并写成该总值")

        def set_base(base_value: int) -> None:
            self._run_native_helper_ops(
                candidate.unit_address,
                (
                    (
                        self.NATIVE_HELPER_OP_SET_HERO_INT,
                        base_value & 0xFFFFFFFF,
                        set_address,
                        1,
                        0,
                    ),
                ),
            )

        set_base(target_base)
        time.sleep(0.05)
        final_base, final_total = self._get_hero_intelligence_pair_via_native_internal(pm, candidate)
        if final_total != target_total:
            corrected_base = final_base + (target_total - final_total)
            if corrected_base < 0:
                raise RuntimeError(
                    f"内部 SetHeroInt 写入后总智力={final_total}，无法修正到目标 {target_total}"
                )
            set_base(corrected_base)
            time.sleep(0.05)
            final_base, final_total = self._get_hero_intelligence_pair_via_native_internal(pm, candidate)
        if final_total != target_total:
            raise RuntimeError(f"内部 SetHeroInt 写入后总智力={final_total}，目标={target_total}")

        return UnitMemoryField(
            key=field.key,
            label=field.label,
            value_type=field.value_type,
            value=float(final_total) if field.value_type == "f32" else final_total,
            address=field.address,
            category=field.category,
            write_address=field.write_address,
            write_type=field.write_type,
            write_base=field.write_base,
            note=(
                f"内部 SetHeroInt 已写入；总智力 {current_total}->{final_total}，"
                f"基础智力 {current_base}->{final_base}，当前加成 {current_bonus}"
            ),
            extra_writes=field.extra_writes,
        )

    def _set_item_charges_via_native_handler(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        item: InventoryItem,
        charges: int,
    ) -> None:
        if not candidate.unit_address:
            raise RuntimeError("当前单位缺少运行时 unit 指针，不能调用物品数量 native handler")
        if not item.item_address:
            raise RuntimeError(f"物品槽{item.slot}缺少 item 对象地址，不能调用物品数量 native handler")
        handlers = self._discover_native_handlers(pm, ("SetItemCharges",))
        set_charges_handler = handlers["SetItemCharges"].handler_address
        jumps = self._rel32_jumps_in_function(pm, set_charges_handler)
        notify_candidates = {
            target
            for target in jumps
            if jumps.count(target) >= 2
        }
        if len(notify_candidates) != 1:
            raise RuntimeError("未能从 SetItemCharges handler 中唯一定位物品数量通知函数")
        notify_handler = next(iter(notify_candidates))
        self._run_native_helper_ops(
            candidate.unit_address,
            (
                (
                    self.NATIVE_HELPER_OP_SET_ITEM_CHARGES,
                    0,
                    notify_handler,
                    item.item_address,
                    charges & 0xFFFFFFFF,
                ),
            ),
        )

    def _set_inventory_slot_item_via_native_handler(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        slot_index: int,
        rawcode: int,
    ) -> tuple[int, int, int]:
        if not candidate.unit_address:
            raise RuntimeError("当前单位缺少运行时 unit 指针，不能调用物品 native handler")
        handlers = self._discover_native_handlers(
            pm,
            (
                "UnitAddItem",
                "UnitAddItemById",
                "UnitItemInSlot",
                "UnitRemoveItem",
            ),
        )
        item_in_slot_calls = self._rel32_calls_in_function(
            pm,
            handlers["UnitItemInSlot"].handler_address,
            max_bytes=0x80,
        )
        add_item_calls = self._rel32_calls_in_function(
            pm,
            handlers["UnitAddItem"].handler_address,
            max_bytes=0x180,
        )
        add_by_id_calls = self._rel32_calls_in_function(
            pm,
            handlers["UnitAddItemById"].handler_address,
            max_bytes=0x120,
        )
        remove_item_calls = self._rel32_calls_in_function(
            pm,
            handlers["UnitRemoveItem"].handler_address,
            max_bytes=0x80,
        )
        if len(item_in_slot_calls) < 3 or len(add_item_calls) < 10 or len(add_by_id_calls) < 8 or len(remove_item_calls) < 4:
            raise RuntimeError("未能从物品 native handler 中定位内部物品栏函数")
        item_in_slot_internal = item_in_slot_calls[2]
        add_first_slot_internal = add_item_calls[9]
        add_exact_slot_internal = add_first_slot_internal + 0x90
        create_item_internal = add_by_id_calls[2]
        remove_item_internal = remove_item_calls[3]
        regions = pm.regions()
        for name, address in (
            ("item_in_slot", item_in_slot_internal),
            ("create_item", create_item_internal),
            ("add_exact_slot", add_exact_slot_internal),
            ("remove_item", remove_item_internal),
        ):
            if not self._is_executable_image_address(regions, address):
                raise RuntimeError(f"内部物品栏函数 {name} 地址不可执行：0x{address:x}")
        results = self._run_native_helper_ops(
            candidate.unit_address,
            (
                (
                    self.NATIVE_HELPER_OP_REMOVE_ITEM_SLOT,
                    slot_index,
                    item_in_slot_internal,
                    remove_item_internal,
                    0,
                ),
                (
                    self.NATIVE_HELPER_OP_ADD_ITEM_TO_SLOT_BY_ID,
                    rawcode,
                    create_item_internal,
                    add_exact_slot_internal,
                    slot_index,
                ),
                (
                    self.NATIVE_HELPER_OP_GET_ITEM_TYPE_IN_SLOT,
                    slot_index,
                    item_in_slot_internal,
                    0,
                    0,
                ),
            ),
            timeout_ms=1500,
        )
        removed_handle = results[0].result
        added_item = results[1].result
        final_rawcode = results[2].result & 0xFFFFFFFF
        if final_rawcode != rawcode:
            raise RuntimeError(
                f"内部 UnitAddItemToSlot 写入后 native 读回 "
                f"{format_rawcode(final_rawcode) if final_rawcode else '空'}，"
                f"不是 {format_rawcode(rawcode)}；新 item=0x{added_item:x}"
            )
        return removed_handle, added_item, final_rawcode

    def _iter_resource_properties(
        self,
        pm: ProcessMemory,
        tag_addresses: Iterable[int] | None = None,
    ) -> Iterable[ResourceProperty]:
        if tag_addresses is None:
            tag = struct.pack("<Q", self.RESOURCE_PROP_TAG)
            tag_addresses = pm.scan_bytes_private(tag, max_region_size=1024 * 1024)
        for tag_address in tag_addresses:
            base = tag_address - 0x28
            try:
                value64 = pm.read_u64(base)
                kind_a = pm.read_i32(base + 0x30)
                kind_b = pm.read_i32(base + 0x34)
                owner_key = pm.read_u64(base + 0x60)
            except OSError:
                continue
            if kind_a != kind_b:
                continue
            if not 0 <= kind_a <= 0x1000:
                continue
            if value64 > 0x7FFFFFFF:
                continue
            if not self._sane_heap_ptr(owner_key):
                owner_key = 0
            yield ResourceProperty(kind_a, base, int(value64), owner_key)

    @staticmethod
    def _resource_food_cap(
        used_prop: ResourceProperty | None,
        cap_prop: ResourceProperty | None,
        limit_prop: ResourceProperty | None,
    ) -> tuple[ResourceProperty | None, ResourceProperty | None]:
        del used_prop
        return cap_prop, limit_prop

    def _resource_cache_candidates_from_group(
        self,
        group: dict[int, ResourceProperty],
        current_gold: int | None = None,
        current_lumber: int | None = None,
        current_food: int | None = None,
        current_food_cap: int | None = None,
    ) -> list[tuple[int, ResourceCache]]:
        candidates: list[tuple[int, ResourceCache]] = []
        for start_kind in sorted({kind - 2 for kind in group}):
            header_prop = group.get(start_kind)
            player_prop = group.get(start_kind + 1)
            if header_prop is None or player_prop is None:
                continue
            if not 0 <= header_prop.value <= 32 or not 0 <= player_prop.value <= 16:
                continue
            gold_prop = group.get(start_kind + 2)
            lumber_prop = group.get(start_kind + 3)
            if gold_prop is None or lumber_prop is None:
                continue
            gold = gold_prop.value // 10
            lumber = lumber_prop.value // 10
            if not 0 <= gold <= 10_000_000 or not 0 <= lumber <= 10_000_000:
                continue
            if current_gold is not None and gold != int(current_gold):
                continue
            if current_lumber is not None and lumber != int(current_lumber):
                continue

            cap_prop = group.get(start_kind + 5)
            used_prop = group.get(start_kind + 6)
            limit_prop = group.get(start_kind + 7)
            cap_choice, limit_choice = self._resource_food_cap(used_prop, cap_prop, limit_prop)
            food_used = used_prop.value if used_prop is not None else 0
            food_cap = cap_choice.value if cap_choice is not None else 0
            food_limit = limit_choice.value if isinstance(limit_choice, ResourceProperty) else 0
            if current_food is not None and food_used != int(current_food):
                continue
            if current_food_cap is not None and food_cap != int(current_food_cap):
                continue

            score = 100
            if current_gold is not None:
                score += 10_000
            if current_lumber is not None:
                score += 10_000
            if current_food is not None:
                score += 5_000
            if current_food_cap is not None:
                score += 5_000
            if gold > 0:
                score += 80
            else:
                score -= 50
            if lumber > 0:
                score += 80
            else:
                score -= 50
            if gold > 0 and lumber > 0:
                score += 140
            if used_prop is not None and cap_choice is not None and 0 <= food_used <= food_cap <= 1000 and food_cap > 0:
                score += 500
            elif current_food is None and current_food_cap is None:
                score -= 180
            if cap_prop is not None:
                score += 80
            if limit_prop is not None:
                score += 40
            score += min(gold + lumber, 20_000) // 200

            cache = ResourceCache(
                gold_prop.address,
                lumber_prop.address,
                gold,
                lumber,
                used_prop.address if used_prop is not None else 0,
                cap_choice.address if cap_choice is not None else 0,
                limit_choice.address if isinstance(limit_choice, ResourceProperty) else 0,
                food_used,
                food_cap,
                food_limit,
                start_kind,
                f"prop^glf owner=0x{gold_prop.owner_key:x} start_kind=0x{start_kind:x}",
                gold_prop.owner_key,
                header_prop.value,
                player_prop.value,
                score,
            )
            candidates.append((score, cache))
        return candidates

    def _resource_cache_from_group(
        self,
        group: dict[int, ResourceProperty],
        current_gold: int | None = None,
        current_lumber: int | None = None,
        current_food: int | None = None,
        current_food_cap: int | None = None,
    ) -> tuple[int, ResourceCache] | None:
        best: tuple[int, ResourceCache] | None = None
        for candidate in self._resource_cache_candidates_from_group(
            group, current_gold, current_lumber, current_food, current_food_cap
        ):
            if best is None or candidate[0] > best[0]:
                best = candidate
        return best

    def _resource_property_groups(
        self,
        pm: ProcessMemory,
        warm_unit_owner_index: bool = False,
    ) -> dict[int, dict[int, ResourceProperty]]:
        resource_tag_addresses: Iterable[int] | None = None
        if warm_unit_owner_index:
            resource_tag = struct.pack("<Q", self.RESOURCE_PROP_TAG)
            unit_owner_tag = struct.pack("<Q", self.UNIT_OWNER_TAG)
            tag_hits = pm.scan_bytes_private_many(
                (resource_tag, unit_owner_tag),
                max_region_size=1024 * 1024,
            )
            resource_tag_addresses = tag_hits[resource_tag]
            self._unit_owner_index = self._unit_owner_index_from_tag_addresses(
                pm,
                tag_hits[unit_owner_tag],
            )
        groups: dict[int, dict[int, ResourceProperty]] = {}
        for prop in self._iter_resource_properties(pm, resource_tag_addresses):
            owner_group = groups.setdefault(prop.owner_key, {})
            current = owner_group.get(prop.kind)
            if current is None or prop.address > current.address:
                owner_group[prop.kind] = prop
        return groups

    def _read_local_player_resources_via_native(self, pm: ProcessMemory) -> LocalPlayerResources:
        handlers = self._discover_native_handlers(pm, ("GetLocalPlayer", "GetPlayerId", "GetPlayerState"))
        get_local_player = handlers["GetLocalPlayer"].handler_address
        get_player_id = handlers["GetPlayerId"].handler_address
        get_player_state = handlers["GetPlayerState"].handler_address
        states = (0xFFFFFFFF, 1, 2, 5, 4)
        results = self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_QUERY,
                    state,
                    get_local_player,
                    get_player_id,
                    get_player_state,
                )
                for state in states
            ),
        )
        values = [self._native_result_i32(result.result) for result in results]
        snapshot = LocalPlayerResources(*values)
        if not 0 <= snapshot.player_id < 28:
            raise RuntimeError(f"GetPlayerId 返回异常玩家槽：{snapshot.player_id}")
        if not 0 <= snapshot.gold <= 10_000_000 or not 0 <= snapshot.lumber <= 10_000_000:
            raise RuntimeError("GetPlayerState 返回的金币/木材超出合理范围")
        if not 0 <= snapshot.food_used <= 10_000 or not 0 <= snapshot.food_cap <= 10_000:
            raise RuntimeError("GetPlayerState 返回的人口数值超出合理范围")
        return snapshot

    def _set_local_player_food_cap_via_native(self, pm: ProcessMemory, target_food_cap: int) -> None:
        handlers = self._discover_native_handlers(
            pm,
            ("GetLocalPlayer", "GetPlayerId", "GetPlayerState", "SetPlayerState"),
        )
        results = self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_SET,
                    4,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["SetPlayerState"].handler_address,
                    int(target_food_cap),
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_QUERY,
                    4,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["GetPlayerId"].handler_address,
                    handlers["GetPlayerState"].handler_address,
                ),
            ),
        )
        actual_food_cap = self._native_result_i32(results[1].result)
        if actual_food_cap != int(target_food_cap):
            raise RuntimeError(
                f"SetPlayerState 写入人口上限后读回 {actual_food_cap}，不是 {target_food_cap}"
            )

    def _set_local_player_food_used_via_native(self, pm: ProcessMemory, target_food_used: int) -> None:
        handlers = self._discover_native_handlers(
            pm,
            ("GetLocalPlayer", "GetPlayerId", "GetPlayerState", "SetPlayerState"),
        )
        results = self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_SET,
                    5,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["SetPlayerState"].handler_address,
                    int(target_food_used),
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_LOCAL_PLAYER_QUERY,
                    5,
                    handlers["GetLocalPlayer"].handler_address,
                    handlers["GetPlayerId"].handler_address,
                    handlers["GetPlayerState"].handler_address,
                ),
            ),
        )
        actual_food_used = self._native_result_i32(results[1].result)
        if actual_food_used != int(target_food_used):
            raise RuntimeError(
                f"SetPlayerState 写入当前人口后读回 {actual_food_used}，不是 {target_food_used}"
            )

    @staticmethod
    def _resource_cache_matches_local_snapshot(
        cache: ResourceCache,
        snapshot: LocalPlayerResources,
    ) -> bool:
        if cache.gold != snapshot.gold or cache.lumber != snapshot.lumber:
            return False
        if cache.food_used_address and cache.food_used != snapshot.food_used:
            return False
        if cache.food_cap_address and cache.food_cap != snapshot.food_cap:
            return False
        return True

    def validate_local_player_resource_cache(self, cache: ResourceCache) -> ResourceCache:
        with ProcessMemory(self.pid) as pm:
            for _attempt in range(3):
                snapshot = self._read_local_player_resources_via_native(pm)
                expected_start_kind = 1 + snapshot.player_id * 0x28
                if cache.block_start_kind != expected_start_kind:
                    break
                try:
                    current = self._read_resource_cache_addresses(pm, cache)
                except (OSError, RuntimeError):
                    continue
                if self._resource_cache_matches_local_snapshot(current, snapshot):
                    return current
        raise RuntimeError("缓存资源地址与本地玩家 GetPlayerState 不一致")

    def locate_local_player_resource_cache(
        self,
        caches: list[ResourceCache] | None = None,
    ) -> ResourceCache:
        if caches is None:
            caches = self.list_resource_caches()
        if not caches:
            raise RuntimeError("未找到可用于匹配本地玩家的资源组")

        with ProcessMemory(self.pid) as pm:
            for _attempt in range(4):
                snapshot = self._read_local_player_resources_via_native(pm)
                expected_start_kind = 1 + snapshot.player_id * 0x28
                candidate_pool = list(caches)
                candidate_pool.extend(self._resource_candidates_by_start.get(expected_start_kind, ()))
                unique_pool = {
                    (cache.gold_address, cache.lumber_address): cache
                    for cache in candidate_pool
                }
                current_caches: list[ResourceCache] = []
                for cache in unique_pool.values():
                    try:
                        current_caches.append(self._read_resource_cache_addresses(pm, cache))
                    except (OSError, RuntimeError):
                        continue

                slot_matches = [
                    cache
                    for cache in current_caches
                    if cache.block_start_kind == expected_start_kind
                    and self._resource_cache_matches_local_snapshot(cache, snapshot)
                ]
                if len(slot_matches) == 1:
                    match = slot_matches[0]
                    self._remember_selection_player_from_resource_owner(
                        pm,
                        match.owner_key,
                        current_caches,
                    )
                    return replace(match, source=match.source + f" local_player={snapshot.player_id}")

        raise RuntimeError("无法按玩家槽唯一匹配本地玩家资源组；已拒绝自动选择，避免修改其他阵营")

    def list_resource_caches(
        self,
        current_gold: int | None = None,
        current_lumber: int | None = None,
        current_food: int | None = None,
        current_food_cap: int | None = None,
    ) -> list[ResourceCache]:
        with ProcessMemory(self.pid) as pm:
            groups = self._resource_property_groups(pm, warm_unit_owner_index=True)
            candidates_by_start: dict[int, list[ResourceCache]] = {}
            found: list[ResourceCache] = []
            seen: set[tuple[int, int]] = set()
            for group in groups.values():
                candidates = self._resource_cache_candidates_from_group(
                    group, current_gold, current_lumber, current_food, current_food_cap
                )
                if not candidates:
                    continue
                for _candidate_score, candidate_cache in candidates:
                    candidates_by_start.setdefault(candidate_cache.block_start_kind, []).append(candidate_cache)
                player_slot_candidates = [
                    candidate
                    for candidate in candidates
                    if candidate[1].block_start_kind >= 1
                    and (candidate[1].block_start_kind - 1) % 0x28 == 0
                ]
                if not player_slot_candidates:
                    continue
                candidate = max(player_slot_candidates, key=lambda item: item[0])
                _score, cache = candidate
                key = (cache.gold_address, cache.lumber_address)
                if key in seen:
                    continue
                seen.add(key)
                found.append(cache)
            self._resource_candidates_by_start = candidates_by_start
            return sorted(found, key=lambda cache: (cache.block_start_kind, cache.owner_key))

    def _read_resource_cache_addresses(self, pm: ProcessMemory, cache: ResourceCache) -> ResourceCache:
        gold10 = pm.read_i32(cache.gold_address)
        lumber10 = pm.read_i32(cache.lumber_address)
        gold = gold10 // 10
        lumber = lumber10 // 10
        if not 0 <= gold <= 10_000_000 or not 0 <= lumber <= 10_000_000:
            raise RuntimeError("资源地址校验失败：金币/木材数值超出合理范围，请重新读取资源组")
        food_used = pm.read_i32(cache.food_used_address) if cache.food_used_address else 0
        food_cap = pm.read_i32(cache.food_cap_address) if cache.food_cap_address else 0
        food_limit = pm.read_i32(cache.food_limit_address) if cache.food_limit_address else 0
        return replace(cache, gold=gold, lumber=lumber, food_used=food_used, food_cap=food_cap, food_limit=food_limit)

    def read_resource_cache_addresses(self, cache: ResourceCache) -> ResourceCache:
        with ProcessMemory(self.pid) as pm:
            return self._read_resource_cache_addresses(pm, cache)

    def write_resource_cache(
        self,
        cache: ResourceCache,
        target_gold: int | None = None,
        target_lumber: int | None = None,
        target_food_used: int | None = None,
        target_food_cap: int | None = None,
        sync_local_food_used: bool = False,
        sync_local_food_cap: bool = False,
    ) -> ResourceCache:
        if (
            target_gold is None
            and target_lumber is None
            and target_food_used is None
            and target_food_cap is None
        ):
            raise ValueError("至少填写一个目标资源值")
        with ProcessMemory(self.pid, write=True) as pm:
            current = self._read_resource_cache_addresses(pm, cache)
            if target_gold is not None:
                if not 0 <= int(target_gold) <= 10_000_000:
                    raise ValueError("目标金币必须在 0 到 10000000 之间")
                pm.write_i32(current.gold_address, int(target_gold) * 10)
            if target_lumber is not None:
                if not 0 <= int(target_lumber) <= 10_000_000:
                    raise ValueError("目标木材必须在 0 到 10000000 之间")
                pm.write_i32(current.lumber_address, int(target_lumber) * 10)
            if target_food_used is not None:
                if not current.food_used_address:
                    raise RuntimeError("所选资源组没有可写的人口占用字段")
                if not 0 <= int(target_food_used) <= 1000:
                    raise ValueError("目标人口占用必须在 0 到 1000 之间")
                if sync_local_food_used:
                    self._set_local_player_food_used_via_native(pm, int(target_food_used))
                else:
                    pm.write_i32(current.food_used_address, int(target_food_used))
            if target_food_cap is not None:
                if not current.food_cap_address:
                    raise RuntimeError("所选资源组没有可写的人口上限字段")
                if not 0 <= int(target_food_cap) <= 1000:
                    raise ValueError("目标人口上限必须在 0 到 1000 之间")
                if sync_local_food_cap:
                    self._set_local_player_food_cap_via_native(pm, int(target_food_cap))
                else:
                    pm.write_i32(current.food_cap_address, int(target_food_cap))
            return self._read_resource_cache_addresses(pm, current)

    def locate_resource_cache(
        self,
        current_gold: int | None = None,
        current_lumber: int | None = None,
        current_food: int | None = None,
        current_food_cap: int | None = None,
        pm: ProcessMemory | None = None,
    ) -> ResourceCache | None:
        close_pm = False
        if pm is None:
            pm = ProcessMemory(self.pid)
            close_pm = True
        try:
            groups = self._resource_property_groups(pm)
            best: tuple[int, ResourceCache] | None = None
            for group in groups.values():
                candidate = self._resource_cache_from_group(
                    group, current_gold, current_lumber, current_food, current_food_cap
                )
                if candidate is not None and (best is None or candidate[0] > best[0]):
                    best = candidate
            if best is not None:
                return best[1]

            if current_gold is None or current_lumber is None:
                return None
            gold10 = int(current_gold) * 10
            lumber10 = int(current_lumber) * 10
            for address, _protect, typ in pm.scan_i32(gold10):
                if typ != MEM_PRIVATE:
                    continue
                for delta in (0xE0, -0xE0):
                    other = address + delta
                    try:
                        if pm.read_i32(other) == lumber10:
                            gaddr, laddr = (address, other) if delta > 0 else (other, address)
                            return ResourceCache(
                                gaddr,
                                laddr,
                                int(current_gold),
                                int(current_lumber),
                                source="calibrated i32 scan",
                            )
                    except OSError:
                        pass
            return None
        finally:
            if close_pm:
                pm.close()

    def read_resource_cache(
        self,
        current_gold: int | None = None,
        current_lumber: int | None = None,
        current_food: int | None = None,
        current_food_cap: int | None = None,
    ) -> ResourceCache:
        with ProcessMemory(self.pid) as pm:
            found = self.locate_resource_cache(current_gold, current_lumber, current_food, current_food_cap, pm)
            if found:
                return found
            for gold_addr, lumber_addr in self.KNOWN_RESOURCE_PAIRS:
                try:
                    gold10 = pm.read_i32(gold_addr)
                    lumber10 = pm.read_i32(lumber_addr)
                except OSError:
                    continue
                if (
                    gold10 % 10 == 0
                    and lumber10 % 10 == 0
                    and 0 <= gold10 <= 100000000
                    and 0 <= lumber10 <= 100000000
                ):
                    return ResourceCache(gold_addr, lumber_addr, gold10 // 10, lumber10 // 10, source="known fixed pair")
        raise RuntimeError("无法读取资源缓存；请在当前资源栏输入当前金币/木材后重新校准")

    def read_resources(
        self,
        current_gold: int | None = None,
        current_lumber: int | None = None,
        current_food: int | None = None,
        current_food_cap: int | None = None,
    ) -> tuple[int, int]:
        cache = self.read_resource_cache(current_gold, current_lumber, current_food, current_food_cap)
        return cache.gold, cache.lumber

    def set_gold(self, target: int, current_gold: int | None = None, current_lumber: int | None = None) -> int:
        cache = self.read_resource_cache(current_gold, current_lumber)
        delta = int(target) - cache.gold
        if delta:
            with ProcessMemory(self.pid, write=True) as pm:
                pm.write_i32(cache.gold_address, int(target) * 10)
        return delta

    def set_lumber(self, target: int, current_gold: int | None = None, current_lumber: int | None = None) -> int:
        cache = self.read_resource_cache(current_gold, current_lumber)
        delta = int(target) - cache.lumber
        if delta:
            with ProcessMemory(self.pid, write=True) as pm:
                pm.write_i32(cache.lumber_address, int(target) * 10)
        return delta

    def add_gold(self, amount: int) -> None:
        if not amount:
            return
        cache = self.read_resource_cache()
        with ProcessMemory(self.pid, write=True) as pm:
            pm.write_i32(cache.gold_address, (cache.gold + int(amount)) * 10)

    def add_lumber(self, amount: int) -> None:
        if not amount:
            return
        cache = self.read_resource_cache()
        with ProcessMemory(self.pid, write=True) as pm:
            pm.write_i32(cache.lumber_address, (cache.lumber + int(amount)) * 10)

    def add_gold_and_lumber(self, amount: int) -> None:
        if not amount:
            return
        cache = self.read_resource_cache()
        with ProcessMemory(self.pid, write=True) as pm:
            pm.write_i32(cache.gold_address, (cache.gold + int(amount)) * 10)
            pm.write_i32(cache.lumber_address, (cache.lumber + int(amount)) * 10)

    def set_food(
        self,
        target_used: int | None = None,
        target_cap: int | None = None,
        current_gold: int | None = None,
        current_lumber: int | None = None,
        current_food: int | None = None,
        current_food_cap: int | None = None,
    ) -> ResourceCache:
        cache = self.read_resource_cache(current_gold, current_lumber, current_food, current_food_cap)
        with ProcessMemory(self.pid, write=True) as pm:
            if target_used is not None:
                if not cache.food_used_address:
                    raise RuntimeError("当前资源块没有可写的人口占用字段")
                pm.write_i32(cache.food_used_address, int(target_used))
            if target_cap is not None:
                if not cache.food_cap_address:
                    raise RuntimeError("当前资源块没有可写的人口上限字段")
                if not 0 <= int(target_cap) <= 1000:
                    raise ValueError("目标人口上限必须在 0 到 1000 之间")
                pm.write_i32(cache.food_cap_address, int(target_cap))
        return self.read_resource_cache(current_gold, current_lumber)

    @staticmethod
    def _looks_like_unit_handle(value: int) -> bool:
        low = value & 0xFFFFFFFF
        high = (value >> 32) & 0xFFFFFFFF
        return (
            0x100 <= low <= 0x0FFFFFFF
            and 0x100 <= high <= 0x0FFFFFFF
            and abs(high - low) <= 0x01000000
        )

    @staticmethod
    def _looks_like_vtable(value: int) -> bool:
        return 0x700000000000 <= value <= 0x7FFFFFFFFFFF

    def _iter_owner_property_list(self, pm: ProcessMemory, owner: int) -> Iterable[int]:
        for list_offset, size_offset in ((0xA0, 0xA8), (0xB0, 0xB8)):
            try:
                list_address = pm.read_u64(owner + list_offset)
                size_bytes = pm.read_u64(owner + size_offset)
            except OSError:
                continue
            if not self._sane_heap_ptr(list_address):
                continue
            if not 0 < size_bytes <= 0x400:
                size_bytes = 0x100
            for entry_offset in range(0, int(size_bytes), 8):
                try:
                    prop = pm.read_u64(list_address + entry_offset)
                except OSError:
                    continue
                if self._sane_heap_ptr(prop):
                    yield prop

    def _property_from_owner(self, pm: ProcessMemory, owner: int, kind: int) -> int | None:
        seen: set[int] = set()
        for prop in self._iter_owner_property_list(pm, owner):
            if prop in seen:
                continue
            seen.add(prop)
            try:
                if pm.read_u64(prop + 0x18) != self.PROP_TAG:
                    continue
                if pm.read_u64(prop + 0x50) != owner:
                    continue
                prop_kind = (pm.read_u64(prop + 0x78) >> 32) & 0xFFFFFFFF
            except OSError:
                continue
            if prop_kind == kind:
                return prop
        return None

    def _position_property_from_owner(self, pm: ProcessMemory, owner: int) -> int | None:
        seen: set[int] = set()
        for prop in self._iter_owner_property_list(pm, owner):
            if prop in seen:
                continue
            seen.add(prop)
            try:
                if pm.read_u64(prop + 0x18) != self.POSITION_PROP_TAG:
                    continue
                if pm.read_u64(prop + 0x50) != owner:
                    continue
            except OSError:
                continue
            return prop
        return None

    def _unit_object_from_owner(self, pm: ProcessMemory, owner: int, handle: int) -> int:
        try:
            unit = pm.read_u64(owner + 0x90)
        except OSError:
            return 0
        if not self._sane_heap_ptr(unit):
            return 0
        try:
            if handle and pm.read_u64(unit + 0x18) != handle:
                return 0
        except OSError:
            return 0
        return unit

    @staticmethod
    def _valid_current_limit(current: float, limit: float) -> bool:
        return (
            math.isfinite(current)
            and math.isfinite(limit)
            and -1000000.0 <= current <= 10000000.0
            and 0.0 <= limit <= 10000000.0
        )

    def _candidate_from_owner(
        self,
        pm: ProcessMemory,
        owner: int,
        score: int,
        note: str,
        handle: int = 0,
        selection_source: str = "",
        selection_slot_address: int = 0,
    ) -> UnitCandidate | None:
        hp_prop = self._property_from_owner(pm, owner, 1)
        if hp_prop is None:
            return None
        hp_current_address = hp_prop + self.SELECTED_HP_VALUE_OFFSET
        hp_regen_address = hp_current_address + 0x04
        hp_max_address = hp_current_address + 0x10
        try:
            hp_current = pm.read_f32(hp_current_address)
            hp_limit = pm.read_f32(hp_max_address)
        except OSError:
            return None
        if not self._valid_current_limit(hp_current, hp_limit):
            return None

        mp_current_address = 0
        mp_regen_address = 0
        mp_max_address = 0
        mp_prop = self._property_from_owner(pm, owner, 2)
        if mp_prop is not None:
            candidate_current = mp_prop + self.SELECTED_HP_VALUE_OFFSET
            candidate_max = candidate_current + 0x10
            try:
                mp_current = pm.read_f32(candidate_current)
                mp_limit = pm.read_f32(candidate_max)
            except OSError:
                mp_current = math.nan
                mp_limit = math.nan
            if self._valid_current_limit(mp_current, mp_limit):
                mp_current_address = candidate_current
                mp_regen_address = candidate_current + 0x04
                mp_max_address = candidate_max

        suffix = f" owner=0x{owner:x} hp_kind=1"
        if mp_current_address:
            suffix += " mp_kind=2"
        else:
            suffix += " mp_kind=missing"
        position_property = self._position_property_from_owner(pm, owner) or 0
        x_address = position_property + 0xD0 if position_property else 0
        y_address = position_property + 0xD4 if position_property else 0
        if position_property:
            suffix += " pos=prop^ucp"
        unit_address = self._unit_object_from_owner(pm, owner, handle)
        if unit_address:
            suffix += f" unit=0x{unit_address:x}"
        return UnitCandidate(
            base=hp_prop,
            score=score,
            hp_current_address=hp_current_address,
            hp_max_address=hp_max_address,
            mp_current_address=mp_current_address,
            mp_max_address=mp_max_address,
            note=note + suffix,
            hp_regen_address=hp_regen_address,
            mp_regen_address=mp_regen_address,
            owner_address=owner,
            handle=handle,
            unit_address=unit_address,
            x_address=x_address,
            y_address=y_address,
            position_property_address=position_property,
            selection_source=selection_source,
            selection_slot_address=selection_slot_address,
        )

    def _unit_owner_index_from_tag_addresses(
        self,
        pm: ProcessMemory,
        tag_addresses: Iterable[int],
    ) -> dict[int, int]:
        index: dict[int, int] = {}
        for tag_address in tag_addresses:
            owner = tag_address - 0x18
            try:
                vtable = pm.read_u64(owner)
                handle = pm.read_u64(owner + 0x20)
                list_address = pm.read_u64(owner + 0xA0)
            except OSError:
                continue
            if not self._looks_like_vtable(vtable):
                continue
            if not self._looks_like_unit_handle(handle):
                continue
            if not self._sane_heap_ptr(list_address):
                continue
            if self._property_from_owner(pm, owner, 1) is None:
                continue
            index[handle] = owner
        return index

    def _build_unit_owner_index(self, pm: ProcessMemory) -> dict[int, int]:
        tag = struct.pack("<Q", self.UNIT_OWNER_TAG)
        tag_addresses = pm.scan_bytes_private(tag, max_region_size=1024 * 1024)
        index = self._unit_owner_index_from_tag_addresses(pm, tag_addresses)
        self._unit_owner_index = index
        return index

    def _owner_for_handle(self, pm: ProcessMemory, handle: int) -> int | None:
        index = self._unit_owner_index
        owner = index.get(handle)
        if owner is not None:
            try:
                if pm.read_u64(owner + 0x20) == handle and self._property_from_owner(pm, owner, 1):
                    return owner
            except OSError:
                pass
        index = self._build_unit_owner_index(pm)
        return index.get(handle)

    def _owner_for_unit_pointer(self, pm: ProcessMemory, unit: int, handle: int) -> int | None:
        if not self._sane_heap_ptr(unit) or not self._looks_like_unit_handle(handle):
            return None

        indexed = self._unit_owner_index.get(handle)
        if indexed is not None:
            try:
                if pm.read_u64(indexed + 0x20) == handle and pm.read_u64(indexed + 0x90) == unit:
                    return indexed
            except OSError:
                pass

        pattern = struct.pack("<Q", unit)
        start_address = unit - self.UNIT_OWNER_POINTER_SEARCH_RADIUS
        end_address = unit + self.UNIT_OWNER_POINTER_SEARCH_RADIUS
        for region in pm.regions():
            if region.typ != MEM_PRIVATE or region.size > 1024 * 1024:
                continue
            if region.base + region.size < start_address or region.base > end_address:
                continue
            try:
                data = pm.read(region.base, region.size)
            except OSError:
                continue
            start = 0
            while True:
                hit = data.find(pattern, start)
                if hit < 0:
                    break
                owner = region.base + hit - 0x90
                try:
                    if (
                        self._looks_like_vtable(pm.read_u64(owner))
                        and pm.read_u64(owner + 0x18) == self.UNIT_OWNER_TAG
                        and pm.read_u64(owner + 0x20) == handle
                        and pm.read_u64(owner + 0x90) == unit
                        and self._property_from_owner(pm, owner, 1) is not None
                    ):
                        self._unit_owner_index[handle] = owner
                        return owner
                except OSError:
                    pass
                start = hit + 1
        return None

    def _owner_for_unit_pointer_win10(
        self,
        pm: ProcessMemory,
        unit: int,
        handle: int,
    ) -> int | None:
        owner = self._owner_for_unit_pointer(pm, unit, handle)
        if owner is not None:
            return owner

        pattern = struct.pack("<Q", unit)
        start_address = unit - self.UNIT_OWNER_POINTER_SEARCH_RADIUS
        end_address = unit + self.UNIT_OWNER_POINTER_SEARCH_RADIUS
        for region in pm.regions():
            if region.typ != MEM_PRIVATE or region.size > 64 * 1024 * 1024:
                continue
            if region.base + region.size < start_address or region.base > end_address:
                continue
            for block_address, data in self._iter_readable_blocks_win10(
                pm,
                region.base,
                region.size,
            ):
                start = 0
                while True:
                    hit = data.find(pattern, start)
                    if hit < 0:
                        break
                    candidate_owner = block_address + hit - 0x90
                    try:
                        if (
                            self._looks_like_vtable(pm.read_u64(candidate_owner))
                            and pm.read_u64(candidate_owner + 0x18) == self.UNIT_OWNER_TAG
                            and pm.read_u64(candidate_owner + 0x20) == handle
                            and pm.read_u64(candidate_owner + 0x90) == unit
                            and self._property_from_owner(pm, candidate_owner, 1) is not None
                        ):
                            self._unit_owner_index[handle] = candidate_owner
                            return candidate_owner
                    except OSError:
                        pass
                    start = hit + 1

        tag_addresses = self._scan_bytes_private_win10(
            pm,
            struct.pack("<Q", self.UNIT_OWNER_TAG),
        )
        broad_index = self._unit_owner_index_from_tag_addresses(pm, tag_addresses)
        self._unit_owner_index.update(broad_index)
        owner = broad_index.get(handle)
        if owner is None:
            return None
        try:
            if pm.read_u64(owner + 0x90) != unit:
                return None
        except OSError:
            return None
        return owner

    def _build_unit_object_index(self, pm: ProcessMemory, force_refresh: bool = False) -> dict[int, tuple[int, int]]:
        unit_index: dict[int, tuple[int, int]] = {}
        owners = self._build_unit_owner_index(pm) if force_refresh or not self._unit_owner_index else self._unit_owner_index
        for handle, owner in owners.items():
            unit = self._unit_object_from_owner(pm, owner, handle)
            if unit:
                unit_index[unit] = (handle, owner)
        if not unit_index and self._unit_owner_index and not force_refresh:
            return self._build_unit_object_index(pm, force_refresh=True)
        return unit_index

    def _score_selected_handle_address(self, pm: ProcessMemory, address: int, handle: int, owner: int) -> int:
        if owner <= address < owner + 0x200:
            return -1000
        score = 0
        if 0x8000000000 <= address <= 0xFFFFFFFFFF:
            score += 120
        try:
            if pm.read_u64(address + 0x5F) == handle:
                score += 35
            if pm.read_u64(address + 0x6D) == handle:
                score += 35
        except OSError:
            pass
        if address % 4 == 0:
            score += 5
        return score

    def _remember_selected_handle_addresses(self, pm: ProcessMemory, handle: int, owner: int) -> None:
        pattern = struct.pack("<Q", handle)
        scored: list[tuple[int, int]] = []

        def collect_from_regions(regions: list[Region]) -> None:
            for region in regions:
                try:
                    data = pm.read(region.base, region.size)
                except OSError:
                    continue
                start = 0
                while True:
                    offset = data.find(pattern, start)
                    if offset < 0:
                        break
                    address = region.base + offset
                    score = self._score_selected_handle_address(pm, address, handle, owner)
                    if score > 0:
                        scored.append((score, address))
                    start = offset + 1

        collect_from_regions(self._selection_state_regions(pm, preferred_only=True))
        if not scored:
            collect_from_regions(self._selection_state_regions(pm, preferred_only=False))
        scored.sort(reverse=True)
        for score, address in scored[:8]:
            if score <= 0:
                continue
            if address in self._selected_handle_addresses:
                self._selected_handle_addresses.remove(address)
            self._selected_handle_addresses.insert(0, address)

    def _selection_state_regions(self, pm: ProcessMemory, preferred_only: bool = True) -> list[Region]:
        regions: list[Region] = []
        for region in pm.regions():
            if region.typ != MEM_PRIVATE or region.size > 4 * 1024 * 1024:
                continue
            if not (0x8000000000 <= region.base <= 0xFFFFFFFFFF):
                continue
            if preferred_only and (region.base & 0xFFFFF) != self.SELECTION_STATE_REGION_LOW20:
                continue
            regions.append(region)
        return regions

    def _known_selected_handle_address_candidates(self, pm: ProcessMemory) -> list[int]:
        candidates: list[int] = []
        seen: set[int] = set()

        def add(address: int) -> None:
            if address not in seen:
                seen.add(address)
                candidates.append(address)

        for address in self.KNOWN_SELECTED_HANDLE_ADDRESSES:
            add(address)

        for region in self._selection_state_regions(pm, preferred_only=True):
            for offset in self.KNOWN_SELECTED_REGION_OFFSETS:
                if 0 <= offset <= region.size - 8:
                    add(region.base + offset)
        return candidates

    def _known_selected_unit_pointer_address_candidates(self, pm: ProcessMemory) -> list[int]:
        candidates: list[int] = []
        seen: set[int] = set()

        def add(address: int) -> None:
            if address not in seen:
                seen.add(address)
                candidates.append(address)

        for address in self.KNOWN_SELECTED_UNIT_POINTER_ADDRESSES:
            add(address)

        for region in self._selection_state_regions(pm, preferred_only=True):
            for offset in self.KNOWN_SELECTED_UNIT_POINTER_REGION_OFFSETS:
                if 0 <= offset <= region.size - 8:
                    add(region.base + offset)
        return candidates

    def _discover_selected_handle_addresses(self, pm: ProcessMemory) -> list[int]:
        owners = self._unit_owner_index or self._build_unit_owner_index(pm)
        if not owners:
            return []

        def scan_regions(regions: list[Region]) -> list[tuple[int, int]]:
            scored: list[tuple[int, int]] = []
            for region in regions:
                try:
                    data = pm.read(region.base, region.size)
                except OSError:
                    continue
                for offset in range(0, max(0, len(data) - 7), 4):
                    handle = struct.unpack_from("<Q", data, offset)[0]
                    owner = owners.get(handle)
                    if owner is None:
                        continue
                    address = region.base + offset
                    score = self._score_selected_handle_address(pm, address, handle, owner)
                    if score > 0:
                        scored.append((score, address))
            return scored

        scored = scan_regions(self._selection_state_regions(pm, preferred_only=True))
        if not scored:
            scored = scan_regions(self._selection_state_regions(pm, preferred_only=False))
        scored.sort(reverse=True)
        addresses: list[int] = []
        for _score, address in scored[:8]:
            if address not in addresses:
                addresses.append(address)
        return addresses

    def _locate_selected_unit_by_unit_pointer(self, pm: ProcessMemory) -> UnitCandidate | None:
        unit_index = self._build_unit_object_index(pm, force_refresh=True)
        if not unit_index:
            return None

        def scan_regions(regions: list[Region]) -> dict[int, list[int]]:
            matches: dict[int, list[int]] = {}
            for region in regions:
                try:
                    data = pm.read(region.base, region.size)
                except OSError:
                    continue
                for offset in range(0, max(0, len(data) - 7), 8):
                    unit = struct.unpack_from("<Q", data, offset)[0]
                    if unit in unit_index:
                        matches.setdefault(unit, []).append(region.base + offset)
            return matches

        matches = scan_regions(self._selection_state_regions(pm, preferred_only=True))
        if not matches:
            matches = scan_regions(self._selection_state_regions(pm, preferred_only=False))
        if not matches:
            return None

        ranked = sorted(
            matches.items(),
            key=lambda item: (len(item[1]), -min(item[1])),
            reverse=True,
        )
        best_unit, best_addresses = ranked[0]
        best_count = len(best_addresses)
        if len(ranked) > 1 and len(ranked[1][1]) == best_count:
            return None
        if best_count < 2 and len(ranked) > 1:
            return None

        handle, owner = unit_index[best_unit]
        slot_address = min(best_addresses)
        candidate = self._candidate_from_owner(
            pm,
            owner,
            880 + min(best_count, 20) * 5,
            f"selected_unit_ptr=0x{best_unit:x} refs={best_count} slot=0x{slot_address:x}",
            handle,
            "memory",
            slot_address,
        )
        if candidate is None or candidate.unit_address != best_unit:
            return None
        return candidate

    def _selection_unit_pointer_groups(
        self,
        pm: ProcessMemory,
    ) -> list[tuple[tuple[int, int], list[int], int]]:
        unit_index = self._build_unit_object_index(pm, force_refresh=True)
        if not unit_index:
            return []
        regions = pm.regions()
        known_offsets = set(self.KNOWN_SELECTED_UNIT_POINTER_REGION_OFFSETS)
        groups: dict[tuple[int, int], list[int]] = {}

        def add_pointer(address: int, unit: int) -> None:
            if unit not in unit_index:
                return
            region = self._region_for_address(regions, address)
            region_base = region.base if region is not None else address & ~0xFFFFF
            groups.setdefault((region_base, unit), []).append(address)

        for address in self._known_selected_unit_pointer_address_candidates(pm):
            try:
                add_pointer(address, pm.read_u64(address))
            except OSError:
                continue

        for region in self._selection_state_regions(pm, preferred_only=True):
            try:
                data = pm.read(region.base, region.size)
            except OSError:
                continue
            for offset in range(0, max(0, len(data) - 7), 8):
                unit = struct.unpack_from("<Q", data, offset)[0]
                if unit in unit_index:
                    add_pointer(region.base + offset, unit)

        if not groups:
            return []

        ranked: list[tuple[tuple[int, int], list[int], int]] = []
        for key, addresses in groups.items():
            region_base, _unit = key
            unique_addresses = sorted(set(addresses))
            known_hits = sum(1 for address in unique_addresses if (address - region_base) in known_offsets)
            ranked.append((key, unique_addresses, known_hits))
        ranked.sort(
            key=lambda item: (item[2], len(item[1]), -item[0][0], -min(item[1])),
            reverse=True,
        )
        return ranked

    def _locate_selected_unit_by_known_unit_pointer(self, pm: ProcessMemory) -> UnitCandidate | None:
        unit_index = self._build_unit_object_index(pm, force_refresh=True)
        if not unit_index:
            return None

        ranked = self._selection_unit_pointer_groups(pm)
        if not ranked:
            return None
        (region_base, unit), unique_addresses, known_hits = ranked[0]
        if known_hits < 2:
            return None
        if len(ranked) > 1 and ranked[1][2] == known_hits and len(ranked[1][1]) == len(unique_addresses) and ranked[1][0][1] != unit:
            return None

        handle, owner = unit_index[unit]
        slot_address = min(unique_addresses)
        candidate = self._candidate_from_owner(
            pm,
            owner,
            870 + known_hits * 20 + min(len(unique_addresses), 20) * 5,
            (
                f"selected_unit_slot=0x{unit:x} region=0x{region_base:x} "
                f"refs={len(unique_addresses)} known={known_hits} slot=0x{slot_address:x}"
            ),
            handle,
            "memory",
            slot_address,
        )
        if candidate is not None and candidate.unit_address == unit:
            return candidate
        return None

    def _selection_unit_pointer_groups_win10(
        self,
        pm: Win10ProcessMemory,
        diagnostics: Win10ReadLogger,
    ) -> tuple[
        list[tuple[tuple[int, int], list[int], int]],
        dict[int, tuple[int, int]],
    ]:
        unit_index = self._build_unit_object_index(pm, force_refresh=False)
        if not unit_index:
            diagnostics.log("selection_unit_pointer_groups_win10", unit_index=0)
            return [], {}
        regions = pm.regions()
        known_offsets = set(self.KNOWN_SELECTED_UNIT_POINTER_REGION_OFFSETS)
        groups: dict[tuple[int, int], list[int]] = {}
        known_total = 0
        known_skipped = 0
        known_read_errors = 0

        def add_pointer(address: int, unit: int) -> None:
            if unit not in unit_index:
                return
            region = self._region_for_address(regions, address)
            region_base = region.base if region is not None else address & ~0xFFFFF
            groups.setdefault((region_base, unit), []).append(address)

        for address in self._known_selected_unit_pointer_address_candidates(pm):
            known_total += 1
            if not pm.is_readable_range(address, 8):
                known_skipped += 1
                continue
            try:
                add_pointer(address, pm.read_u64(address))
            except OSError:
                known_read_errors += 1

        selection_regions = self._selection_state_regions(pm, preferred_only=True)
        for region in selection_regions:
            try:
                data = pm.read(region.base, region.size)
            except OSError:
                continue
            for offset in range(0, max(0, len(data) - 7), 8):
                unit = struct.unpack_from("<Q", data, offset)[0]
                if unit in unit_index:
                    add_pointer(region.base + offset, unit)

        ranked: list[tuple[tuple[int, int], list[int], int]] = []
        for key, addresses in groups.items():
            region_base, _unit = key
            unique_addresses = sorted(set(addresses))
            known_hits = sum(1 for address in unique_addresses if (address - region_base) in known_offsets)
            ranked.append((key, unique_addresses, known_hits))
        ranked.sort(
            key=lambda item: (item[2], len(item[1]), -item[0][0], -min(item[1])),
            reverse=True,
        )
        diagnostics.log(
            "selection_unit_pointer_groups_win10",
            unit_index=len(unit_index),
            known_total=known_total,
            known_skipped=known_skipped,
            known_read_errors=known_read_errors,
            selection_regions=len(selection_regions),
            groups=len(ranked),
        )
        return ranked, unit_index

    def _locate_selected_unit_by_known_unit_pointer_win10(
        self,
        pm: Win10ProcessMemory,
        diagnostics: Win10ReadLogger,
    ) -> UnitCandidate | None:
        ranked, unit_index = self._selection_unit_pointer_groups_win10(pm, diagnostics)
        if not ranked:
            return None
        (region_base, unit), unique_addresses, known_hits = ranked[0]
        if known_hits < 2:
            return None
        if (
            len(ranked) > 1
            and ranked[1][2] == known_hits
            and len(ranked[1][1]) == len(unique_addresses)
            and ranked[1][0][1] != unit
        ):
            return None
        handle, owner = unit_index[unit]
        slot_address = min(unique_addresses)
        candidate = self._candidate_from_owner(
            pm,
            owner,
            870 + known_hits * 20 + min(len(unique_addresses), 20) * 5,
            (
                f"selected_unit_slot=0x{unit:x} region=0x{region_base:x} "
                f"refs={len(unique_addresses)} known={known_hits} slot=0x{slot_address:x}"
            ),
            handle,
            "win10",
            slot_address,
        )
        if candidate is not None and candidate.unit_address == unit:
            return candidate
        return None

    def _selection_manager_unit_slots(
        self,
        pm: ProcessMemory,
        list_base: int,
    ) -> list[tuple[int, int]]:
        try:
            root = pm.read_u64(list_base + 0x18)
            count = pm.read_u32(list_base + 0x20)
        except OSError:
            return []
        if not 0 < count <= self.SELECTION_MANAGER_MAX_UNITS:
            return []
        if (root & 1) or not self._sane_heap_ptr(root):
            return []

        out: list[tuple[int, int]] = []
        node = root
        seen: set[int] = set()
        for _index in range(int(count)):
            if (node & 1) or not self._sane_heap_ptr(node) or node in seen:
                break
            seen.add(node)
            try:
                next_node = pm.read_u64(node + 0x08)
                unit = pm.read_u64(node + 0x10)
            except OSError:
                break
            if self._sane_heap_ptr(unit):
                out.append((unit, node + 0x10))
            node = next_node
        return out

    def _remember_selection_player_from_resource_owner(
        self,
        pm: ProcessMemory,
        resource_owner: int,
        resource_caches: Iterable[ResourceCache],
    ) -> None:
        if not self._sane_heap_ptr(resource_owner):
            return
        players_by_owner: dict[int, int] = {}
        for cache in resource_caches:
            owner = cache.owner_key
            if not self._sane_heap_ptr(owner) or owner in players_by_owner:
                continue
            try:
                player = pm.read_u64(owner + 0x90)
                vtable = pm.read_u64(player)
                selection_manager = pm.read_u64(player + self._selection_manager_offset)
            except OSError:
                continue
            if not self._looks_like_vtable(vtable) or not self._sane_heap_ptr(selection_manager):
                continue
            players_by_owner[owner] = player
        player = players_by_owner.get(resource_owner, 0)
        if not player or len(players_by_owner) < 2:
            return
        if len(set(players_by_owner.values())) != len(players_by_owner):
            return
        if player in self._selection_player_candidates:
            self._selection_player_candidates.remove(player)
        self._selection_player_candidates.insert(0, player)

    def _selection_player_pointer_candidates(self, pm: ProcessMemory, discover: bool = True) -> list[int]:
        candidates: list[int] = []
        seen: set[int] = set()

        def add(value: int) -> None:
            if value in seen or not self._sane_heap_ptr(value):
                return
            seen.add(value)
            candidates.append(value)

        for value in self._selection_player_candidates:
            add(value)
        if not discover:
            return candidates

        discovered_from_player_components = False
        tag = struct.pack("<Q", self.PLAYER_COMPONENT_TAG)
        for tag_address in pm.scan_bytes_private(tag, max_region_size=1024 * 1024):
            owner = tag_address - 0x18
            for offset in (0x90, 0x88):
                try:
                    value = pm.read_u64(owner + offset)
                    vtable = pm.read_u64(value)
                    selection_manager = pm.read_u64(value + self._selection_manager_offset)
                except OSError:
                    continue
                if not self._looks_like_vtable(vtable):
                    continue
                if not self._sane_heap_ptr(selection_manager):
                    continue
                discovered_from_player_components = True
                add(value)
        if discovered_from_player_components:
            return candidates

        try:
            resource_owner_groups = self._resource_property_groups(pm)
        except OSError:
            resource_owner_groups = {}
        for owner in resource_owner_groups:
            if not self._sane_heap_ptr(owner):
                continue
            for offset in range(0, 0x220, 8):
                try:
                    value = pm.read_u64(owner + offset)
                    vtable = pm.read_u64(value)
                    selection_manager = pm.read_u64(value + self._selection_manager_offset)
                except OSError:
                    continue
                if not self._looks_like_vtable(vtable):
                    continue
                if not self._sane_heap_ptr(selection_manager):
                    continue
                add(value)
        return candidates

    def _selection_player_pointer_candidates_win10(
        self,
        pm: Win10ProcessMemory,
        diagnostics: Win10ReadLogger,
        *,
        discover: bool,
        scan_components: bool,
    ) -> list[int]:
        candidates: list[int] = []
        seen: set[int] = set()
        stats = {
            "cached_inputs": 0,
            "resource_owners": 0,
            "component_tags": 0,
            "pointer_values": 0,
            "duplicate_values": 0,
            "rejected_unsane": 0,
            "rejected_unreadable": 0,
            "rejected_vtable": 0,
            "rejected_manager": 0,
            "read_errors": 0,
            "accepted": 0,
        }

        def remember(value: int) -> None:
            if value in self._selection_player_candidates:
                self._selection_player_candidates.remove(value)
            self._selection_player_candidates.append(value)

        def add(value: int, source: str) -> None:
            stats["pointer_values"] += 1
            if value in seen:
                stats["duplicate_values"] += 1
                return
            seen.add(value)
            if not self._sane_heap_ptr(value):
                stats["rejected_unsane"] += 1
                return
            manager_field = value + self._selection_manager_offset
            if not pm.is_readable_range(value, 8) or not pm.is_readable_range(manager_field, 8):
                stats["rejected_unreadable"] += 1
                return
            try:
                vtable = pm.read_u64(value)
                selection_manager = pm.read_u64(manager_field)
            except OSError:
                stats["read_errors"] += 1
                return
            if not self._looks_like_vtable(vtable):
                stats["rejected_vtable"] += 1
                return
            if not self._sane_heap_ptr(selection_manager):
                stats["rejected_manager"] += 1
                return
            if not any(
                pm.is_readable_range(selection_manager + list_offset + 0x18, 0x0C)
                for list_offset in self._selection_list_offsets
            ):
                stats["rejected_unreadable"] += 1
                return
            candidates.append(value)
            stats["accepted"] += 1
            remember(value)
            diagnostics.log(
                "selection_player_candidate_accepted",
                source=source,
                player=f"0x{value:x}",
                manager=f"0x{selection_manager:x}",
            )

        for value in list(self._selection_player_candidates):
            stats["cached_inputs"] += 1
            add(value, "cached")

        if discover:
            resource_owners: list[int] = []
            resource_owner_seen: set[int] = set()
            for caches in self._resource_candidates_by_start.values():
                for cache in caches:
                    owner = int(cache.owner_key)
                    if owner in resource_owner_seen or not self._sane_heap_ptr(owner):
                        continue
                    resource_owner_seen.add(owner)
                    resource_owners.append(owner)
            stats["resource_owners"] = len(resource_owners)
            for owner in resource_owners:
                for offset in (0x90, 0x88):
                    pointer_address = owner + offset
                    if not pm.is_readable_range(pointer_address, 8):
                        stats["rejected_unreadable"] += 1
                        continue
                    try:
                        value = pm.read_u64(pointer_address)
                    except OSError:
                        stats["read_errors"] += 1
                        continue
                    add(value, f"resource_owner+0x{offset:x}")

        if discover and scan_components:
            tag = struct.pack("<Q", self.PLAYER_COMPONENT_TAG)
            tag_addresses = self._scan_bytes_private_win10(
                pm,
                tag,
                max_region_size=1024 * 1024,
            )
            stats["component_tags"] = len(tag_addresses)
            for tag_address in tag_addresses:
                owner = tag_address - 0x18
                if not self._sane_heap_ptr(owner) or not pm.is_readable_range(owner, 8):
                    stats["rejected_unreadable"] += 1
                    continue
                try:
                    owner_vtable = pm.read_u64(owner)
                except OSError:
                    stats["read_errors"] += 1
                    continue
                if not self._looks_like_vtable(owner_vtable):
                    stats["rejected_vtable"] += 1
                    continue
                for offset in (0x90, 0x88):
                    pointer_address = owner + offset
                    if not pm.is_readable_range(pointer_address, 8):
                        stats["rejected_unreadable"] += 1
                        continue
                    try:
                        value = pm.read_u64(pointer_address)
                    except OSError:
                        stats["read_errors"] += 1
                        continue
                    add(value, f"player_component+0x{offset:x}")

        diagnostics.log(
            "selection_player_candidates_win10",
            discover=discover,
            scan_components=scan_components,
            stats=stats,
            candidates=[f"0x{value:x}" for value in candidates],
        )
        return candidates

    def _candidate_from_selected_unit_pointer_win10(
        self,
        pm: Win10ProcessMemory,
        unit: int,
        note: str,
        score: int,
        selection_slot_address: int,
    ) -> UnitCandidate | None:
        if not self._sane_heap_ptr(unit) or not pm.is_readable_range(unit + 0x18, 8):
            return None
        try:
            handle = pm.read_u64(unit + 0x18)
        except OSError:
            return None
        if not self._looks_like_unit_handle(handle):
            return None
        owner = self._owner_for_unit_pointer_win10(pm, unit, handle)
        if owner is None:
            owner = self._owner_for_handle(pm, handle)
        if owner is None:
            return None
        return self._candidate_from_identity(
            pm,
            handle,
            owner,
            unit,
            note,
            score,
            selection_slot_address,
        )

    def _candidate_from_selection_player_win10(
        self,
        pm: Win10ProcessMemory,
        player: int,
    ) -> UnitCandidate | None:
        manager_field = player + self._selection_manager_offset
        if not pm.is_readable_range(manager_field, 8):
            return None
        try:
            selection_manager = pm.read_u64(manager_field)
        except OSError:
            return None
        if not self._sane_heap_ptr(selection_manager):
            return None

        for list_offset in self._selection_list_offsets:
            list_base = selection_manager + list_offset
            if not pm.is_readable_range(list_base + 0x18, 0x0C):
                continue
            for unit, slot_address in self._selection_manager_unit_slots(pm, list_base):
                candidate = self._candidate_from_selected_unit_pointer_win10(
                    pm,
                    unit,
                    (
                        f"selected_unit_slot=0x{unit:x} via=selection_manager "
                        f"player=0x{player:x} manager=0x{selection_manager:x} list=0x{list_base:x}"
                    ),
                    990 if list_offset == 0 else 980,
                    slot_address,
                )
                if candidate is None:
                    continue
                if player in self._selection_player_candidates:
                    self._selection_player_candidates.remove(player)
                self._selection_player_candidates.insert(0, player)
                return replace(candidate, selection_source="win10")
        return None

    def _locate_selected_unit_by_selection_manager_win10(
        self,
        pm: Win10ProcessMemory,
        diagnostics: Win10ReadLogger,
        *,
        discover: bool,
    ) -> UnitCandidate | None:
        cached_players = self._selection_player_pointer_candidates_win10(
            pm,
            diagnostics,
            discover=False,
            scan_components=False,
        )
        for player in cached_players:
            candidate = self._candidate_from_selection_player_win10(pm, player)
            if candidate is not None:
                return candidate
        if not discover:
            return None

        resource_players = self._selection_player_pointer_candidates_win10(
            pm,
            diagnostics,
            discover=True,
            scan_components=False,
        )
        cached_set = set(cached_players)
        for player in resource_players:
            if player in cached_set:
                continue
            candidate = self._candidate_from_selection_player_win10(pm, player)
            if candidate is not None:
                return candidate

        component_players = self._selection_player_pointer_candidates_win10(
            pm,
            diagnostics,
            discover=True,
            scan_components=True,
        )
        tried = set(resource_players)
        for player in component_players:
            if player in tried:
                continue
            candidate = self._candidate_from_selection_player_win10(pm, player)
            if candidate is not None:
                return candidate
        return None

    def _candidate_from_selected_unit_pointer(
        self,
        pm: ProcessMemory,
        unit: int,
        note: str,
        score: int,
        selection_slot_address: int,
    ) -> UnitCandidate | None:
        if not self._sane_heap_ptr(unit):
            return None
        try:
            handle = pm.read_u64(unit + 0x18)
        except OSError:
            return None
        if not self._looks_like_unit_handle(handle):
            return None
        owner = self._owner_for_unit_pointer(pm, unit, handle) or self._owner_for_handle(pm, handle)
        if owner is None:
            return None
        return self._candidate_from_identity(pm, handle, owner, unit, note, score, selection_slot_address)

    def _candidate_from_selection_player(self, pm: ProcessMemory, player: int) -> UnitCandidate | None:
        try:
            selection_manager = pm.read_u64(player + self._selection_manager_offset)
        except OSError:
            return None
        if not self._sane_heap_ptr(selection_manager):
            return None

        for list_offset in self._selection_list_offsets:
            list_base = selection_manager + list_offset
            for unit, slot_address in self._selection_manager_unit_slots(pm, list_base):
                candidate = self._candidate_from_selected_unit_pointer(
                    pm,
                    unit,
                    (
                        f"selected_unit_slot=0x{unit:x} via=selection_manager "
                        f"player=0x{player:x} manager=0x{selection_manager:x} list=0x{list_base:x}"
                    ),
                    990 if list_offset == 0 else 980,
                    slot_address,
                )
                if candidate is None:
                    continue
                if player in self._selection_player_candidates:
                    self._selection_player_candidates.remove(player)
                self._selection_player_candidates.insert(0, player)
                return candidate
        return None

    def _locate_selected_unit_by_player_component_scan(self, pm: ProcessMemory) -> UnitCandidate | None:
        tag = struct.pack("<Q", self.PLAYER_COMPONENT_TAG)
        seen: set[int] = set()
        regions = sorted(pm.regions(), key=lambda region: region.base, reverse=True)
        for region in regions:
            if region.typ != MEM_PRIVATE or region.size > 1024 * 1024:
                continue
            if region.base >= 0x700000000000:
                continue
            try:
                data = pm.read(region.base, region.size)
            except OSError:
                continue
            start = 0
            while True:
                offset = data.find(tag, start)
                if offset < 0:
                    break
                owner = region.base + offset - 0x18
                for player_offset in (0x90, 0x88):
                    try:
                        player = pm.read_u64(owner + player_offset)
                        vtable = pm.read_u64(player)
                    except OSError:
                        continue
                    if player in seen or not self._looks_like_vtable(vtable):
                        continue
                    seen.add(player)
                    candidate = self._candidate_from_selection_player(pm, player)
                    if candidate is not None:
                        return candidate
                start = offset + 1
        return None

    @staticmethod
    def _selection_manager_offsets_from_code(code: bytes) -> list[int]:
        offsets: list[int] = []
        for index in range(0, max(0, len(code) - 6)):
            if code[index : index + 2] != b"\x48\x8b":
                continue
            # mov r64, qword ptr [rax + disp32], used after player-handle resolver.
            if code[index + 2] not in {0x88, 0x98}:
                continue
            disp = struct.unpack_from("<I", code, index + 3)[0]
            if 0x40 <= disp <= 0x800 and disp not in offsets:
                offsets.append(disp)
        return offsets

    @staticmethod
    def _selection_list_offsets_from_code(code: bytes) -> list[int]:
        offsets: list[int] = [0]
        for index in range(0, max(0, len(code) - 6)):
            # add rcx, disp32
            if code[index : index + 3] != b"\x48\x81\xc1":
                continue
            disp = struct.unpack_from("<I", code, index + 3)[0]
            if 0 < disp <= 0x1000 and disp not in offsets:
                offsets.append(disp)
        return offsets

    def _discover_native_selection_layout(self, pm: ProcessMemory) -> tuple[int, int, int, dict[str, NativeHandler]]:
        handlers = self._discover_native_handlers(pm, self.NATIVE_SELECTION_HANDLER_NAMES)
        manager_votes: dict[int, int] = {}
        for handler in handlers.values():
            try:
                code = pm.read(handler.handler_address, 0x240)
            except OSError:
                continue
            for offset in self._selection_manager_offsets_from_code(code):
                manager_votes[offset] = manager_votes.get(offset, 0) + 1
        if not manager_votes:
            raise RuntimeError("native selection handler 中没有找到 CPlayer selection manager 偏移")
        selection_manager_offset = max(
            manager_votes,
            key=lambda offset: (manager_votes[offset], offset == self.CPLAYER_SELECTION_MANAGER_OFFSET),
        )

        list_offsets: list[int] = [0]
        for call in self._rel32_calls_in_function(pm, handlers["IsUnitSelected"].handler_address, max_bytes=0x120):
            try:
                code = pm.read(call, 0x80)
            except OSError:
                continue
            for offset in self._selection_list_offsets_from_code(code):
                if offset not in list_offsets:
                    list_offsets.append(offset)
            for jump in self._rel32_jumps_in_function(pm, call, max_bytes=0x80):
                try:
                    jump_code = pm.read(jump, 0x80)
                except OSError:
                    continue
                for offset in self._selection_list_offsets_from_code(jump_code):
                    if offset not in list_offsets:
                        list_offsets.append(offset)
        alternate = self.SELECTION_MANAGER_ALT_LIST_OFFSET
        if alternate not in list_offsets:
            alternate = next((offset for offset in list_offsets if offset), self.SELECTION_MANAGER_ALT_LIST_OFFSET)
        return selection_manager_offset, 0, alternate, handlers

    def _prepare_win10_selection_layout(
        self,
        pm: Win10ProcessMemory,
        diagnostics: Win10ReadLogger,
    ) -> bool:
        started = time.perf_counter()
        previous_manager = self._selection_manager_offset
        previous_lists = tuple(self._selection_list_offsets)
        try:
            manager_offset, primary_offset, alternate_offset, handlers = (
                self._discover_native_selection_layout(pm)
            )
        except Exception as exc:
            diagnostics.log(
                "win10_selection_layout_failure",
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
                previous_manager=f"0x{previous_manager:x}",
                previous_lists=[f"0x{offset:x}" for offset in previous_lists],
                exception=repr(exc),
            )
            return False
        self._selection_manager_offset = manager_offset
        self._selection_list_offsets = tuple(
            dict.fromkeys((primary_offset, alternate_offset))
        )
        diagnostics.log(
            "win10_selection_layout",
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            previous_manager=f"0x{previous_manager:x}",
            manager=f"0x{manager_offset:x}",
            previous_lists=[f"0x{offset:x}" for offset in previous_lists],
            lists=[f"0x{offset:x}" for offset in self._selection_list_offsets],
            handlers={
                name: f"0x{handler.handler_address:x}"
                for name, handler in handlers.items()
            },
        )
        return True

    def _locate_selected_unit_by_selection_manager(self, pm: ProcessMemory) -> UnitCandidate | None:
        for player in self._selection_player_pointer_candidates(pm, discover=False):
            candidate = self._candidate_from_selection_player(pm, player)
            if candidate is not None:
                return candidate
        candidate = self._locate_selected_unit_by_player_component_scan(pm)
        if candidate is not None:
            return candidate
        for player in self._selection_player_pointer_candidates(pm, discover=True):
            candidate = self._candidate_from_selection_player(pm, player)
            if candidate is not None:
                return candidate
        return None

    def probe_native_selection_manager(self) -> NativeSelectionProbeResult:
        with ProcessMemory(self.pid) as pm:
            manager_offset, primary_offset, alternate_offset, handlers = self._discover_native_selection_layout(pm)
            self._selection_manager_offset = manager_offset
            self._selection_list_offsets = tuple(dict.fromkeys((primary_offset, alternate_offset)))
            candidate = self._locate_selected_unit_by_selection_manager(pm)
            fallback_note = ""
            if candidate is None:
                try:
                    candidate = self.locate_selected_unit_by_handle(pm, allow_deep_scan=True)
                    fallback_note = " fallback=normal_locator"
                except Exception:
                    candidate = None
            note = (
                f"native_disasm manager_offset=0x{manager_offset:x} "
                f"list_offsets={','.join('0x%x' % offset for offset in self._selection_list_offsets)}"
                f"{fallback_note}"
            )
            return NativeSelectionProbeResult(
                manager_offset,
                primary_offset,
                alternate_offset,
                handlers["IsUnitSelected"].handler_address,
                handlers.get("GroupEnumUnitsSelected", NativeHandler("GroupEnumUnitsSelected", 0, 0)).handler_address,
                candidate,
                note,
            )

    def prewarm_selected_unit_cache(self) -> UnitCandidate:
        with ProcessMemory(self.pid) as pm:
            try:
                candidate = self.locate_selected_unit_by_handle(pm, allow_deep_scan=True)
            except Exception as first_error:
                try:
                    manager_offset, primary_offset, alternate_offset, _handlers = self._discover_native_selection_layout(pm)
                    self._selection_manager_offset = manager_offset
                    self._selection_list_offsets = tuple(dict.fromkeys((primary_offset, alternate_offset)))
                    candidate = self.locate_selected_unit_by_handle(pm, allow_deep_scan=True)
                except Exception:
                    raise first_error
            else:
                self._unit_fields_from_candidate(pm, candidate)
                return candidate
            self._unit_fields_from_candidate(pm, candidate)
            return candidate

    def _locate_selected_unit_by_panel(self, pm: ProcessMemory) -> UnitCandidate:
        raise RuntimeError("OCR/面板数值定位已禁用；当前选中单位只能通过内存 selected-handle 定位")

    def _read_jass_selected_unit_raw(self, pm: ProcessMemory) -> tuple[int, int, int]:
        handlers = self._discover_native_handlers(pm, self.JASS_SELECTION_NATIVE_NAMES)
        results = self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_SELECTED_UNIT,
                    0,
                    handlers["CreateGroup"].handler_address,
                    handlers["SyncSelections"].handler_address,
                    handlers["GetLocalPlayer"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_SELECTED_UNIT_ARG,
                    0,
                    handlers["GroupEnumUnitsSelected"].handler_address,
                    handlers["FirstOfGroup"].handler_address,
                    handlers["GetHandleId"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_SELECTED_UNIT_ARG,
                    0,
                    handlers["DestroyGroup"].handler_address,
                    0,
                    0,
                ),
            ),
            timeout_ms=1000,
        )
        unit_handle = results[0].result
        handle_id = results[1].result & 0xFFFFFFFF
        player_handle = results[2].result
        return unit_handle, handle_id, player_handle

    def _read_jass_selected_unit_raw_win10(
        self,
        pm: ProcessMemory,
    ) -> tuple[int, int, int]:
        handlers = self._discover_native_handlers(pm, self.WIN10_SELECTION_NATIVE_NAMES)
        results = self._run_native_helper_ops(
            0,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_SELECTED_UNIT,
                    0,
                    handlers["CreateGroup"].handler_address,
                    0,
                    handlers["GetLocalPlayer"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_SELECTED_UNIT_ARG,
                    0,
                    handlers["GroupEnumUnitsSelected"].handler_address,
                    handlers["FirstOfGroup"].handler_address,
                    handlers["GetHandleId"].handler_address,
                ),
                (
                    self.NATIVE_HELPER_OP_JASS_SELECTED_UNIT_ARG,
                    0,
                    handlers["DestroyGroup"].handler_address,
                    0,
                    0,
                ),
            ),
            timeout_ms=1000,
        )
        return results[0].result, results[1].result & 0xFFFFFFFF, results[2].result

    def _is_jass_unit_selected_win10(
        self,
        pm: ProcessMemory,
        unit_handle: int,
        player_handle: int,
    ) -> bool:
        handlers = self._discover_native_handlers(pm, ("IsUnitSelected",))
        result = self._run_native_helper_ops(
            unit_handle,
            (
                (
                    self.NATIVE_HELPER_OP_JASS_UNIT_RAWCODE,
                    player_handle & 0xFFFFFFFF,
                    handlers["IsUnitSelected"].handler_address,
                    0,
                    0,
                ),
            ),
        )[0].result
        return bool(result & 0xFFFFFFFF)

    def _read_selected_unit_type_id(self, pm: ProcessMemory, candidate: UnitCandidate) -> int:
        if not candidate.unit_address:
            return 0
        primary = pm.read_u32(candidate.unit_address + 0x70)
        mirror = pm.read_u32(candidate.unit_address + 0x178)
        if primary != mirror or not self._looks_like_item_rawcode(primary):
            return 0
        return primary

    def _candidate_with_selected_unit_type_id(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
    ) -> UnitCandidate:
        try:
            unit_type_id = self._read_selected_unit_type_id(pm, candidate)
        except (OSError, RuntimeError):
            return candidate
        if not unit_type_id:
            return candidate
        return replace(candidate, unit_type_id=unit_type_id)

    def _candidate_from_jass_selection_result(
        self,
        pm: ProcessMemory,
        unit_value: int,
        handle_id: int,
        player_handle: int,
    ) -> UnitCandidate | None:
        note = f"jass_selected unit=0x{unit_value:x} handle_id=0x{handle_id:x} player=0x{player_handle:x}"
        unit_index = self._build_unit_object_index(pm, force_refresh=True)
        entry = unit_index.get(unit_value)
        if entry is not None:
            handle, owner = entry
            candidate = self._candidate_from_owner(pm, owner, 980, note + " mode=unit_ptr", handle, "jass", 0)
            if candidate is not None and candidate.unit_address == unit_value:
                return candidate

        if self._looks_like_unit_handle(unit_value):
            owner = self._owner_for_handle(pm, unit_value)
            if owner is not None:
                candidate = self._candidate_from_owner(pm, owner, 970, note + " mode=unit_handle", unit_value, "jass", 0)
                if candidate is not None:
                    return candidate

        if self._sane_heap_ptr(unit_value):
            try:
                nested_handle = pm.read_u64(unit_value + 0x18)
            except OSError:
                nested_handle = 0
            if self._looks_like_unit_handle(nested_handle):
                owner = self._owner_for_handle(pm, nested_handle)
                if owner is not None:
                    candidate = self._candidate_from_owner(
                        pm,
                        owner,
                        960,
                        note + f" mode=handle_at_unit+0x18 nested=0x{nested_handle:x}",
                        nested_handle,
                        "jass",
                        0,
                    )
                    if candidate is not None and candidate.unit_address == unit_value:
                        return candidate

        if handle_id:
            matches: list[UnitCandidate] = []
            for handle, owner in (self._unit_owner_index or self._build_unit_owner_index(pm)).items():
                low = handle & 0xFFFFFFFF
                high = (handle >> 32) & 0xFFFFFFFF
                if handle_id not in {low, high}:
                    continue
                candidate = self._candidate_from_owner(
                    pm,
                    owner,
                    940,
                    note + f" mode=handle_id_match full_handle=0x{handle:x}",
                    handle,
                    "jass",
                    0,
                )
                if candidate is not None:
                    matches.append(candidate)
            unique_by_unit = {candidate.unit_address: candidate for candidate in matches if candidate.unit_address}
            if len(unique_by_unit) == 1:
                return next(iter(unique_by_unit.values()))
        return None

    def _candidate_from_jass_selection_result_win10(
        self,
        pm: ProcessMemory,
        unit_value: int,
        handle_id: int,
        player_handle: int,
    ) -> UnitCandidate | None:
        note = (
            f"win10_jass_selected unit=0x{unit_value:x} "
            f"handle_id=0x{handle_id:x} player=0x{player_handle:x}"
        )

        def candidate_for(handle: int, owner: int, expected_unit: int = 0) -> UnitCandidate | None:
            candidate = self._candidate_from_owner(
                pm,
                owner,
                1000,
                note,
                handle,
                "win10_jass",
                0,
            )
            if candidate is None:
                return None
            if expected_unit and candidate.unit_address != expected_unit:
                return None
            return candidate

        owner = self._unit_owner_index.get(unit_value)
        if owner is not None:
            candidate = candidate_for(unit_value, owner)
            if candidate is not None:
                return candidate

        if self._sane_heap_ptr(unit_value):
            try:
                nested_handle = pm.read_u64(unit_value + 0x18)
            except OSError:
                nested_handle = 0
            owner = self._unit_owner_index.get(nested_handle)
            if (
                owner is None
                and isinstance(pm, Win10ProcessMemory)
                and self._looks_like_unit_handle(nested_handle)
            ):
                owner = self._owner_for_unit_pointer_win10(
                    pm,
                    unit_value,
                    nested_handle,
                )
            if owner is not None:
                candidate = candidate_for(nested_handle, owner, unit_value)
                if candidate is not None:
                    return candidate

        if handle_id:
            matches: dict[int, UnitCandidate] = {}
            for handle, candidate_owner in self._unit_owner_index.items():
                low = handle & 0xFFFFFFFF
                high = (handle >> 32) & 0xFFFFFFFF
                if handle_id not in {low, high}:
                    continue
                candidate = candidate_for(handle, candidate_owner)
                if candidate is not None and candidate.unit_address:
                    matches[candidate.unit_address] = candidate
            if len(matches) == 1:
                return next(iter(matches.values()))
        return None

    def locate_selected_unit_by_jass_native_win10(
        self,
        pm: ProcessMemory,
        diagnostics: Win10ReadLogger,
    ) -> UnitCandidate:
        started = time.perf_counter()
        self._last_win10_jass_unit_handle = 0
        self._last_win10_jass_player_handle = 0
        self._last_win10_jass_handle_id = 0
        unit_value, handle_id, player_handle = self._read_jass_selected_unit_raw_win10(pm)
        diagnostics.log(
            "win10_jass_selection_raw",
            elapsed_ms=(time.perf_counter() - started) * 1000.0,
            unit=f"0x{unit_value:x}",
            handle_id=f"0x{handle_id:x}",
            player=f"0x{player_handle:x}",
        )
        if not unit_value and not handle_id:
            raise RuntimeError("JASS 当前选择为空")
        resolved_unit = self._resolve_jass_unit_handle_win10(
            pm,
            unit_value,
            allow_missing=True,
        )
        diagnostics.log(
            "win10_jass_selection_resolved",
            jass_handle=f"0x{unit_value:x}",
            unit=f"0x{resolved_unit:x}",
        )
        if not resolved_unit:
            raise RuntimeError(
                f"JASS 当前选择句柄无法解析：0x{unit_value:x}"
            )
        if not self._is_jass_unit_selected_win10(pm, unit_value, player_handle):
            raise RuntimeError(
                "JASS 返回的单位已不在当前单选中，拒绝复用历史单位："
                f"handle=0x{unit_value:x} unit=0x{resolved_unit:x}"
            )
        candidate = self._candidate_from_jass_selection_result_win10(
            pm,
            resolved_unit,
            handle_id,
            player_handle,
        )
        if candidate is None:
            raise RuntimeError(
                "JASS 已取得当前选择，但无法映射到可信单位对象："
                f"handle=0x{unit_value:x} unit=0x{resolved_unit:x} "
                f"handle_id=0x{handle_id:x}"
            )
        self._last_win10_jass_unit_handle = unit_value
        self._last_win10_jass_player_handle = player_handle
        self._last_win10_jass_handle_id = handle_id
        diagnostics.log(
            "selection_candidate_found",
            route="jass_no_sync_verified",
            handle=f"0x{candidate.handle:x}",
            owner=f"0x{candidate.owner_address:x}",
            unit=f"0x{candidate.unit_address:x}",
            note=candidate.note,
        )
        return candidate

    def probe_jass_selected_unit(self) -> JassSelectionProbeResult:
        with ProcessMemory(self.pid) as pm:
            unit_handle, handle_id, player_handle = self._read_jass_selected_unit_raw(pm)
            candidate = self._candidate_from_jass_selection_result(pm, unit_handle, handle_id, player_handle)
            note = "mapped" if candidate is not None else "raw_only"
            return JassSelectionProbeResult(unit_handle, handle_id, player_handle, candidate, note)

    def locate_selected_unit_by_jass_native(self, pm: ProcessMemory | None = None) -> UnitCandidate:
        close_pm = False
        if pm is None:
            pm = ProcessMemory(self.pid)
            close_pm = True
        try:
            unit_handle, handle_id, player_handle = self._read_jass_selected_unit_raw(pm)
            if not unit_handle and not handle_id:
                raise RuntimeError("JASS selection native 没有返回选中单位")
            candidate = self._candidate_from_jass_selection_result(pm, unit_handle, handle_id, player_handle)
            if candidate is None:
                raise RuntimeError(
                    "JASS selection native 返回了单位，但无法映射到当前内存单位结构："
                    f"unit=0x{unit_handle:x} handle_id=0x{handle_id:x} player=0x{player_handle:x}"
                )
            return candidate
        finally:
            if close_pm:
                pm.close()

    def locate_selected_unit_by_handle(
        self,
        pm: ProcessMemory | None = None,
        allow_panel_fallback: bool = False,
        allow_deep_scan: bool = False,
    ) -> UnitCandidate:
        close_pm = False
        if pm is None:
            pm = ProcessMemory(self.pid)
            close_pm = True
        try:
            last_error: str | None = None
            tried: set[int] = set()

            def try_slot(address: int, min_score: int = 0) -> UnitCandidate | None:
                nonlocal last_error
                tried.add(address)
                try:
                    handle = pm.read_u64(address)
                except OSError as exc:
                    last_error = str(exc)
                    return None
                if not self._looks_like_unit_handle(handle):
                    last_error = f"0x{address:x} 不是单位 handle"
                    return None
                owner = self._owner_for_handle(pm, handle)
                if owner is None:
                    last_error = f"0x{handle:x} 没有匹配单位对象"
                    return None
                score = self._score_selected_handle_address(pm, address, handle, owner)
                if score < min_score:
                    last_error = f"0x{address:x} 像历史选择槽，不是当前选择槽"
                    return None
                candidate = self._candidate_from_owner(
                    pm,
                    owner,
                    900 + score,
                    f"selected_handle=0x{handle:x} slot=0x{address:x}",
                    handle,
                    "memory",
                    address,
                )
                if candidate is None:
                    last_error = f"0x{handle:x} 没有生命属性"
                    return None
                if address in self._selected_handle_addresses:
                    self._selected_handle_addresses.remove(address)
                self._selected_handle_addresses.insert(0, address)
                return candidate

            retry_delays = (0.0, 0.08, 0.20, 0.45, 0.90, 1.60) if allow_deep_scan else (0.0,)
            for delay in retry_delays:
                if delay:
                    time.sleep(delay)
                tried.clear()
                selection_manager_candidate = self._locate_selected_unit_by_selection_manager(pm)
                if selection_manager_candidate is not None:
                    return selection_manager_candidate
                unit_pointer_candidate = self._locate_selected_unit_by_known_unit_pointer(pm)
                if unit_pointer_candidate is not None:
                    return unit_pointer_candidate
                for address in self._known_selected_handle_address_candidates(pm):
                    candidate = try_slot(address, min_score=120 if allow_deep_scan else 0)
                    if candidate is not None:
                        return candidate
                for address in list(dict.fromkeys(self._selected_handle_addresses)):
                    if address in tried:
                        continue
                    candidate = try_slot(address, min_score=120 if allow_deep_scan else 0)
                    if candidate is not None:
                        return candidate
            if allow_deep_scan:
                # Last resort only. Reforged can leave old selection handles in
                # this state block after switching units, so fixed slots above are
                # trusted before broad handle discovery.
                for address in self._discover_selected_handle_addresses(pm):
                    if address in tried:
                        continue
                    candidate = try_slot(address, min_score=120)
                    if candidate is not None:
                        return candidate
            detail = f"；最后错误：{last_error}" if last_error else ""
            raise RuntimeError(f"没有找到当前选中单位 handle，请在游戏里左键选中一个单位后重试{detail}")
        finally:
            if close_pm:
                pm.close()

    def locate_selected_unit_win10(
        self,
        pm: ProcessMemory | None = None,
        diagnostics: Win10ReadLogger | None = None,
    ) -> UnitCandidate:
        close_pm = False
        close_diagnostics = False
        if diagnostics is None and isinstance(pm, Win10ProcessMemory):
            diagnostics = pm.diagnostics
        if pm is None:
            if diagnostics is None:
                diagnostics = Win10ReadLogger(self.pid)
                close_diagnostics = True
            pm = Win10ProcessMemory(self.pid, diagnostics)
            close_pm = True

        def log(event: str, **values: object) -> None:
            if diagnostics is not None:
                diagnostics.log(event, **values)

        try:
            last_error: str | None = None
            tried: set[int] = set()

            def try_slot(address: int, min_score: int = 0) -> UnitCandidate | None:
                nonlocal last_error
                tried.add(address)
                if isinstance(pm, Win10ProcessMemory) and not pm.is_readable_range(address, 8):
                    log(
                        "selection_slot_skipped_unreadable",
                        address=f"0x{address:x}",
                    )
                    return None
                try:
                    handle = pm.read_u64(address)
                except OSError as exc:
                    last_error = str(exc)
                    log(
                        "selection_slot_read_error",
                        address=f"0x{address:x}",
                        exception=repr(exc),
                    )
                    return None
                if not self._looks_like_unit_handle(handle):
                    last_error = f"0x{address:x} 不是单位 handle"
                    log(
                        "selection_slot_invalid_handle",
                        address=f"0x{address:x}",
                        value=f"0x{handle:x}",
                    )
                    return None
                owner = self._owner_for_handle(pm, handle)
                if owner is None:
                    last_error = f"0x{handle:x} 没有匹配单位对象"
                    log(
                        "selection_slot_owner_missing",
                        address=f"0x{address:x}",
                        handle=f"0x{handle:x}",
                    )
                    return None
                score = self._score_selected_handle_address(pm, address, handle, owner)
                if score < min_score:
                    last_error = f"0x{address:x} 像历史选择槽，不是当前选择槽"
                    log(
                        "selection_slot_score_rejected",
                        address=f"0x{address:x}",
                        handle=f"0x{handle:x}",
                        owner=f"0x{owner:x}",
                        score=score,
                        min_score=min_score,
                    )
                    return None
                candidate = self._candidate_from_owner(
                    pm,
                    owner,
                    900 + score,
                    f"selected_handle=0x{handle:x} slot=0x{address:x}",
                    handle,
                    "win10",
                    address,
                )
                if candidate is None:
                    last_error = f"0x{handle:x} 没有生命属性"
                    log(
                        "selection_slot_candidate_invalid",
                        address=f"0x{address:x}",
                        handle=f"0x{handle:x}",
                        owner=f"0x{owner:x}",
                    )
                    return None
                if address in self._selected_handle_addresses:
                    self._selected_handle_addresses.remove(address)
                self._selected_handle_addresses.insert(0, address)
                log(
                    "selection_candidate_found",
                    route="handle_slot",
                    address=f"0x{address:x}",
                    handle=f"0x{handle:x}",
                    owner=f"0x{owner:x}",
                    unit=f"0x{candidate.unit_address:x}",
                    score=score,
                )
                return candidate

            retry_delays = (0.0, 0.08, 0.20)
            for attempt, delay in enumerate(retry_delays, start=1):
                if delay:
                    time.sleep(delay)
                tried.clear()
                log(
                    "selection_attempt_begin",
                    attempt=attempt,
                    delay=delay,
                    discover_players=attempt == 1,
                )

                try:
                    selection_manager_candidate = self._locate_selected_unit_by_selection_manager_win10(
                        pm,
                        diagnostics,
                        discover=attempt == 1,
                    )
                except Exception as exc:
                    selection_manager_candidate = None
                    last_error = str(exc)
                    log(
                        "selection_manager_error",
                        attempt=attempt,
                        exception=repr(exc),
                    )
                if selection_manager_candidate is not None:
                    log(
                        "selection_candidate_found",
                        route="selection_manager",
                        handle=f"0x{selection_manager_candidate.handle:x}",
                        owner=f"0x{selection_manager_candidate.owner_address:x}",
                        unit=f"0x{selection_manager_candidate.unit_address:x}",
                        note=selection_manager_candidate.note,
                    )
                    return selection_manager_candidate
                log("selection_manager_miss", attempt=attempt)

                if attempt == 1:
                    try:
                        unit_pointer_candidate = self._locate_selected_unit_by_known_unit_pointer_win10(
                            pm,
                            diagnostics,
                        )
                    except Exception as exc:
                        unit_pointer_candidate = None
                        last_error = str(exc)
                        log(
                            "known_unit_pointer_error",
                            attempt=attempt,
                            exception=repr(exc),
                        )
                    if unit_pointer_candidate is not None:
                        log(
                            "selection_candidate_found",
                            route="known_unit_pointer",
                            handle=f"0x{unit_pointer_candidate.handle:x}",
                            owner=f"0x{unit_pointer_candidate.owner_address:x}",
                            unit=f"0x{unit_pointer_candidate.unit_address:x}",
                            note=unit_pointer_candidate.note,
                        )
                        return unit_pointer_candidate
                    log("known_unit_pointer_miss", attempt=attempt)

                try:
                    known_addresses = self._known_selected_handle_address_candidates(pm)
                except Exception as exc:
                    known_addresses = []
                    last_error = str(exc)
                    log(
                        "known_selection_slots_error",
                        attempt=attempt,
                        exception=repr(exc),
                    )
                log(
                    "known_selection_slots",
                    attempt=attempt,
                    count=len(known_addresses),
                    readable_count=sum(
                        1
                        for address in known_addresses
                        if not isinstance(pm, Win10ProcessMemory)
                        or pm.is_readable_range(address, 8)
                    ),
                    addresses=[f"0x{address:x}" for address in known_addresses],
                )
                for address in known_addresses:
                    candidate = try_slot(
                        address,
                        min_score=self.WIN10_STRONG_SELECTION_SCORE,
                    )
                    if candidate is not None:
                        return candidate

                cached_addresses = list(dict.fromkeys(self._selected_handle_addresses))
                log(
                    "cached_selection_slots",
                    attempt=attempt,
                    count=len(cached_addresses),
                    addresses=[f"0x{address:x}" for address in cached_addresses],
                )
                for address in cached_addresses:
                    if address in tried:
                        continue
                    candidate = try_slot(
                        address,
                        min_score=self.WIN10_STRONG_SELECTION_SCORE,
                    )
                    if candidate is not None:
                        return candidate

            try:
                discovered_addresses = self._discover_selected_handle_addresses(pm)
            except Exception as exc:
                discovered_addresses = []
                last_error = str(exc)
                log("deep_selection_slots_error", exception=repr(exc))
            log(
                "deep_selection_slots",
                count=len(discovered_addresses),
                addresses=[f"0x{address:x}" for address in discovered_addresses],
            )
            for address in discovered_addresses:
                if address in tried:
                    continue
                candidate = try_slot(
                    address,
                    min_score=self.WIN10_STRONG_SELECTION_SCORE,
                )
                if candidate is not None:
                    return candidate
            detail = f"；最后错误：{last_error}" if last_error else ""
            log("selection_failed", last_error=last_error, tried=len(tried))
            raise RuntimeError(
                f"没有找到当前选中单位 handle，请在游戏里左键选中一个单位后重试{detail}"
            )
        finally:
            if close_pm:
                pm.close()
            if close_diagnostics and diagnostics is not None:
                diagnostics.close()

    def locate_selected_unit(
        self,
        current_hp: float,
        current_mp: float | None = None,
        max_hp: float | None = None,
        max_mp: float | None = None,
    ) -> UnitCandidate:
        # Keep the legacy signature for old CLI callers, but never infer identity
        # from HP/MP/stat values. Identical units and changing hero stats must
        # still resolve through the live selected-unit handle.
        return self.locate_selected_unit_by_handle(allow_panel_fallback=False)

    def _candidate_from_identity(
        self,
        pm: ProcessMemory,
        handle: int,
        owner: int,
        unit: int,
        note: str,
        score: int = 0,
        selection_slot_address: int = 0,
    ) -> UnitCandidate | None:
        try:
            if pm.read_u64(owner + 0x20) != handle:
                return None
            if pm.read_u64(owner + 0x90) != unit:
                return None
            if pm.read_u64(unit + 0x18) != handle:
                return None
        except OSError:
            return None
        candidate = self._candidate_from_owner(pm, owner, score, note, handle, "memory", selection_slot_address)
        if candidate is None or candidate.unit_address != unit:
            return None
        return candidate

    def _selection_summary_from_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        refs: int,
        known_hits: int,
        region_base: int,
        components: dict[str, tuple[int, int]] | None = None,
        include_inventory: bool = True,
        include_abilities: bool = True,
    ) -> UnitSelectionSummary:
        panel = self._panel_from_candidate(pm, candidate)
        position = self._position_from_candidate(pm, candidate)
        components = components if components is not None else self._selected_components(pm, candidate.owner_address)
        inventory: list[str] = []
        if include_inventory:
            for item in self._inventory_items_from_candidate(pm, candidate, components):
                if item.rawcode:
                    inventory.append(f"{item.slot}:{item.rawcode_text}")
        ability_count = len(self._ability_instances_from_candidate(pm, candidate)) if include_abilities else 0
        return UnitSelectionSummary(
            candidate=candidate,
            refs=refs,
            known_hits=known_hits,
            region_base=region_base,
            hp_text=panel.hp_text,
            mp_text=panel.mp_text,
            position=position,
            components=tuple(sorted(components)),
            inventory=tuple(inventory),
            ability_count=ability_count,
            hero="hero" in components,
        )

    def selection_summary_from_identity(
        self,
        handle: int,
        owner: int,
        unit: int,
        note: str = "",
    ) -> UnitSelectionSummary:
        with ProcessMemory(self.pid) as pm:
            candidate = self._candidate_from_identity(
                pm,
                handle,
                owner,
                unit,
                note or f"remembered_identity=0x{handle:x},0x{owner:x},0x{unit:x}",
                860,
            )
            if candidate is None:
                raise RuntimeError("候选单位已经失效，请重新读取候选列表")
            return self._selection_summary_from_candidate(pm, candidate, refs=0, known_hits=2, region_base=0)

    @staticmethod
    def _selection_summary_priority(summary: UnitSelectionSummary) -> tuple[int, int, int, int, int]:
        note = summary.candidate.note
        if note.startswith("remembered_identity=") or note.startswith("manual_candidate"):
            base = 100000
        elif note.startswith("selected_handle=") or note.startswith("selected_unit_slot=") or summary.known_hits >= 2:
            base = 90000
        elif note.startswith("global_unit_scan"):
            base = 20000
        else:
            base = 30000
        if summary.hero:
            base += 30000
        if "inventory" in summary.components:
            base += 10000
        if "move" in summary.components:
            base += 500
        return (
            base,
            len(summary.inventory),
            summary.known_hits,
            summary.refs,
            summary.candidate.score,
        )

    def list_selection_candidates(
        self,
        limit: int = 80,
        extra_identities: Iterable[tuple[int, int, int]] | None = None,
    ) -> list[UnitSelectionSummary]:
        with ProcessMemory(self.pid) as pm:
            unit_index = self._build_unit_object_index(pm, force_refresh=True)
            summary_by_unit: dict[int, UnitSelectionSummary] = {}

            def append_summary(summary: UnitSelectionSummary) -> None:
                existing = summary_by_unit.get(summary.candidate.unit_address)
                if existing is None or self._selection_summary_priority(summary) > self._selection_summary_priority(existing):
                    summary_by_unit[summary.candidate.unit_address] = summary

            def append_candidate(
                candidate: UnitCandidate,
                refs: int,
                known_hits: int,
                region_base: int,
                components: dict[str, tuple[int, int]] | None = None,
                include_inventory: bool = True,
                include_abilities: bool = True,
            ) -> None:
                if not candidate.unit_address:
                    return
                append_summary(
                    self._selection_summary_from_candidate(
                        pm,
                        candidate,
                        refs,
                        known_hits,
                        region_base,
                        components,
                        include_inventory,
                        include_abilities,
                    )
                )

            if extra_identities is not None:
                for handle, owner, unit in extra_identities:
                    candidate = self._candidate_from_identity(
                        pm,
                        handle,
                        owner,
                        unit,
                        f"remembered_identity=0x{handle:x},0x{owner:x},0x{unit:x}",
                        860,
                    )
                    if candidate is not None:
                        append_candidate(candidate, 0, 2, 0)

            try:
                strong_candidate = self.locate_selected_unit_by_handle(pm, allow_deep_scan=False)
            except Exception:
                strong_candidate = None
            if strong_candidate is not None:
                append_candidate(
                    strong_candidate,
                    1,
                    2 if strong_candidate.note.startswith("selected_handle=") else 0,
                    0,
                )

            for (region_base, unit), addresses, known_hits in self._selection_unit_pointer_groups(pm):
                entry = unit_index.get(unit)
                if entry is None:
                    continue
                handle, owner = entry
                candidate = self._candidate_from_identity(
                    pm,
                    handle,
                    owner,
                    unit,
                    (
                        f"selection_candidate=0x{unit:x} region=0x{region_base:x} "
                        f"refs={len(addresses)} known={known_hits} slot=0x{min(addresses):x}"
                    ),
                    800 + known_hits * 20 + min(len(addresses), 20) * 5,
                    min(addresses),
                )
                if candidate is not None:
                    append_candidate(candidate, len(addresses), known_hits, region_base)

            owners = self._build_unit_owner_index(pm)
            components_by_owner = self._component_map_for_owners(pm, set(owners.values()))
            for handle, owner in owners.items():
                candidate = self._candidate_from_owner(
                    pm,
                    owner,
                    500,
                    f"global_unit_scan handle=0x{handle:x}",
                    handle,
                    "scan",
                    0,
                )
                if candidate is not None and candidate.unit_address:
                    components = components_by_owner.get(owner, {})
                    append_candidate(
                        candidate,
                        0,
                        0,
                        0,
                        components=components,
                        include_inventory=False,
                        include_abilities=False,
                    )

            summaries = sorted(
                summary_by_unit.values(),
                key=self._selection_summary_priority,
                reverse=True,
            )
            final: list[UnitSelectionSummary] = []
            for summary in summaries[:limit]:
                if summary.candidate.note.startswith("global_unit_scan") and (
                    summary.hero or "inventory" in summary.components
                ):
                    final.append(
                        self._selection_summary_from_candidate(
                            pm,
                            summary.candidate,
                            summary.refs,
                            summary.known_hits,
                            summary.region_base,
                            components=components_by_owner.get(summary.candidate.owner_address),
                            include_inventory=True,
                            include_abilities=False,
                        )
                    )
                else:
                    final.append(summary)
            return final

    def selection_candidate_line(self, summary: UnitSelectionSummary, index: int) -> str:
        pos = summary.position
        pos_text = f" x={pos[0]:.1f} y={pos[1]:.1f}" if pos is not None else ""
        components = ",".join(summary.components) if summary.components else "-"
        inventory = ",".join(summary.inventory) if summary.inventory else "-"
        confidence = selection_confidence_text(summary)
        return (
            f"#{index} [{confidence}] hp={summary.hp_text} mp={summary.mp_text}{pos_text} "
            f"refs={summary.refs} known={summary.known_hits} "
            f"handle=0x{summary.candidate.handle:x} owner=0x{summary.candidate.owner_address:x} "
            f"unit=0x{summary.candidate.unit_address:x} components={components} "
            f"abilities={summary.ability_count} inventory={inventory} note={summary.candidate.note}"
        )

    @staticmethod
    def _sane_heap_ptr(value: int) -> bool:
        return 0x100000000 <= value <= 0x7FFFFFFFFFFF

    def _panel_from_candidate(self, pm: ProcessMemory, candidate: UnitCandidate) -> VisibleUnitPanel:
        actual_hp = int(round(pm.read_f32(candidate.hp_current_address)))
        actual_hp_max = int(round(pm.read_f32(candidate.hp_max_address)))
        actual_mp = 0
        actual_mp_max = 0
        if candidate.mp_current_address and candidate.mp_max_address:
            actual_mp = int(round(pm.read_f32(candidate.mp_current_address)))
            actual_mp_max = int(round(pm.read_f32(candidate.mp_max_address)))
        return VisibleUnitPanel(
            actual_hp,
            actual_hp_max,
            actual_mp,
            actual_mp_max,
            f"{actual_hp}/{actual_hp_max}",
            f"{actual_mp}/{actual_mp_max}",
        )

    def _position_from_candidate(self, pm: ProcessMemory, candidate: UnitCandidate) -> tuple[float, float] | None:
        if not candidate.x_address or not candidate.y_address:
            return None
        return pm.read_f32(candidate.x_address), pm.read_f32(candidate.y_address)

    @staticmethod
    def _read_memory_value(pm: ProcessMemory, address: int, value_type: str) -> int | float:
        if value_type == "f32":
            return pm.read_f32(address)
        if value_type == "i32":
            return pm.read_i32(address)
        if value_type in {"u64", "ptr"}:
            return pm.read_u64(address)
        if value_type in {"u32", "rawcode"}:
            return pm.read_u32(address)
        raise ValueError(f"不支持的字段类型：{value_type}")

    @staticmethod
    def _coerce_memory_value(value_type: str, value: int | float | str) -> int | float:
        if value_type == "f32":
            return float(str(value).strip()) if isinstance(value, str) else float(value)
        if value_type in {"i32", "u32"}:
            if isinstance(value, str):
                return int(value.strip(), 0)
            return int(value)
        if value_type in {"u64", "ptr"}:
            if isinstance(value, str):
                return int(value.strip(), 0)
            return int(value)
        if value_type == "rawcode":
            if isinstance(value, str):
                text = value.strip()
                if len(text) == 4 and not text.lower().startswith("0x"):
                    return struct.unpack(">I", text.encode("ascii"))[0]
                return int(text, 0)
            return int(value)
        raise ValueError(f"不支持的字段类型：{value_type}")

    @classmethod
    def _write_memory_value(
        cls,
        pm: ProcessMemory,
        address: int,
        value_type: str,
        value: int | float | str,
    ) -> None:
        coerced = cls._coerce_memory_value(value_type, value)
        if value_type == "f32":
            pm.write_f32(address, float(coerced))
            return
        if value_type == "i32":
            pm.write_i32(address, int(coerced))
            return
        if value_type in {"u32", "rawcode"}:
            pm.write_u32(address, int(coerced))
            return
        if value_type in {"u64", "ptr"}:
            data = struct.pack("<Q", int(coerced))
            written = ctypes.c_size_t()
            ok = kernel32.WriteProcessMemory(
                pm.handle, ctypes.c_void_p(address), data, len(data), ctypes.byref(written)
            )
            if not ok or written.value != len(data):
                raise ctypes.WinError(ctypes.get_last_error())
            return
        raise ValueError(f"不支持的字段类型：{value_type}")

    def _iter_owner_component_wrappers(
        self,
        pm: ProcessMemory,
        owner: int,
    ) -> Iterable[tuple[str, int, int]]:
        start = owner - self.COMPONENT_WRAPPER_SCAN_BACK
        end = owner + self.COMPONENT_WRAPPER_SCAN_FORWARD
        for region in pm.regions():
            region_start = max(start, region.base)
            region_end = min(end, region.base + region.size)
            if region_end <= region_start:
                continue
            try:
                block = pm.read(region_start, region_end - region_start)
            except OSError:
                continue
            for tag, name in self.COMPONENT_NAMES.items():
                pattern = struct.pack("<Q", tag)
                search = 0
                while True:
                    index = block.find(pattern, search)
                    if index < 0:
                        break
                    search = index + 1
                    wrapper = region_start + index - 0x18
                    if wrapper < start or wrapper >= end:
                        continue
                    try:
                        vtable = pm.read_u64(wrapper)
                        wrapper_owner = pm.read_u64(wrapper + 0x50)
                        data = pm.read_u64(wrapper + 0x90)
                    except OSError:
                        continue
                    if wrapper_owner != owner:
                        continue
                    if not self._looks_like_vtable(vtable) or not self._sane_heap_ptr(data):
                        continue
                    try:
                        data_vtable = pm.read_u64(data)
                    except OSError:
                        continue
                    if not self._looks_like_vtable(data_vtable):
                        continue
                    yield name, wrapper, data

    def _components_from_unit_object(
        self,
        pm: ProcessMemory,
        owner: int,
    ) -> dict[str, tuple[int, int]]:
        identity = self._owner_component_identity(pm, owner)
        if identity is None:
            return {}
        _owner, _handle, unit = identity

        components: dict[str, tuple[int, int]] = {}
        for name, offset in self.UNIT_COMPONENT_DATA_OFFSETS.items():
            try:
                data = pm.read_u64(unit + offset)
                data_vtable = pm.read_u64(data) if self._sane_heap_ptr(data) else 0
            except OSError:
                continue
            if self._looks_like_vtable(data_vtable):
                components[name] = (0, data)
        return components

    def _unit_component_layout_matches_process(self, pm: ProcessMemory) -> bool:
        if self._unit_component_layout_confirmed:
            return True
        found_names: set[str] = set()
        for owner in self._unit_owner_index.values():
            direct = self._components_from_unit_object(pm, owner)
            if not direct:
                continue
            wrappers = {
                name: (wrapper, data)
                for name, wrapper, data in self._iter_owner_component_wrappers(pm, owner)
            }
            for name, (_wrapper, data) in direct.items():
                if wrappers.get(name, (0, 0))[1] == data:
                    found_names.add(name)
            if len(found_names) >= 2:
                self._unit_component_layout_confirmed = True
                return True
        return False

    def _owner_component_identity(
        self,
        pm: ProcessMemory,
        owner: int,
    ) -> tuple[int, int, int] | None:
        try:
            if pm.read_u64(owner + 0x18) != self.UNIT_OWNER_TAG:
                return None
            handle = pm.read_u64(owner + 0x20)
            unit = pm.read_u64(owner + 0x90)
            if not self._sane_heap_ptr(unit) or pm.read_u64(unit + 0x18) != handle:
                return None
        except OSError:
            return None
        return owner, handle, unit

    def _selected_components(self, pm: ProcessMemory, owner: int) -> dict[str, tuple[int, int]]:
        if not owner:
            return {}
        components: dict[str, tuple[int, int]] = {}
        cache_key = self._owner_component_identity(pm, owner)
        if cache_key is None:
            return {}
        cached = self._selected_components_cache.get(cache_key)
        if cached is not None:
            if cached:
                valid = self._validated_owner_components(pm, owner, cached)
                if len(valid) == len(cached):
                    return dict(valid)
            self._selected_components_cache.pop(cache_key, None)

        direct = self._components_from_unit_object(pm, owner)
        wrapper_components: dict[str, tuple[int, int]] = {}
        for name, wrapper, data in self._iter_owner_component_wrappers(pm, owner):
            wrapper_components.setdefault(name, (wrapper, data))

        direct_is_fully_verified = bool(direct) and all(
            wrapper_components.get(name, (0, 0))[1] == data
            for name, (_wrapper, data) in direct.items()
        )
        if direct_is_fully_verified and set(wrapper_components) == set(direct):
            components.update(wrapper_components)
            self._selected_components_cache[cache_key] = dict(components)
            return components

        if not direct and not wrapper_components and self._unit_component_layout_matches_process(pm):
            return {}

        if self._component_index_cache is None or (
            owner not in self._component_index_cache
            and owner not in self._component_index_misses
        ):
            self._rebuild_component_index(pm)
            if owner not in self._component_index_cache:
                self._component_index_misses.add(owner)
        indexed_source = self._component_index_cache.get(owner, {})
        indexed = self._validated_owner_components(
            pm,
            owner,
            indexed_source,
        )
        if len(indexed) != len(indexed_source):
            self._rebuild_component_index(pm)
            indexed = self._validated_owner_components(
                pm,
                owner,
                self._component_index_cache.get(owner, {}),
            )
        components.update(indexed)
        if components:
            self._selected_components_cache[cache_key] = dict(components)
        else:
            self._selected_components_cache.pop(cache_key, None)
        return components

    def _validated_owner_components(
        self,
        pm: ProcessMemory,
        owner: int,
        components: dict[str, tuple[int, int]],
    ) -> dict[str, tuple[int, int]]:
        valid: dict[str, tuple[int, int]] = {}
        unit_components = self._components_from_unit_object(pm, owner)
        for name, (wrapper, data) in components.items():
            if not wrapper:
                if unit_components.get(name) == (0, data):
                    valid[name] = (wrapper, data)
                continue
            try:
                vtable = pm.read_u64(wrapper)
                tag = pm.read_u64(wrapper + 0x18)
                wrapper_owner = pm.read_u64(wrapper + 0x50)
                wrapper_data = pm.read_u64(wrapper + 0x90)
                data_vtable = pm.read_u64(data)
            except OSError:
                continue
            if (
                self.COMPONENT_NAMES.get(tag) == name
                and wrapper_owner == owner
                and wrapper_data == data
                and self._looks_like_vtable(vtable)
                and self._looks_like_vtable(data_vtable)
            ):
                valid[name] = (wrapper, data)
        return valid

    def _scan_component_index(
        self,
        pm: ProcessMemory,
    ) -> dict[int, dict[str, tuple[int, int]]]:
        components_by_owner: dict[int, dict[str, tuple[int, int]]] = {}
        patterns = tuple(
            (struct.pack("<Q", tag), tag, name)
            for tag, name in self.COMPONENT_NAMES.items()
        )
        tail_len = 7
        for region in pm.regions():
            if region.typ != MEM_PRIVATE or region.size > 16 * 1024 * 1024:
                continue
            offset = 0
            tail = b""
            while offset < region.size:
                size = min(4 * 1024 * 1024, region.size - offset)
                try:
                    block = tail + pm.read(region.base + offset, size)
                except OSError:
                    offset += size
                    tail = b""
                    continue
                block_base = region.base + offset - len(tail)
                for pattern, expected_tag, name in patterns:
                    search = 0
                    while True:
                        index = block.find(pattern, search)
                        if index < 0:
                            break
                        search = index + 1
                        tag_address = block_base + index
                        if tag_address < region.base:
                            continue
                        wrapper = tag_address - 0x18
                        try:
                            vtable = pm.read_u64(wrapper)
                            tag = pm.read_u64(wrapper + 0x18)
                            owner = pm.read_u64(wrapper + 0x50)
                            data = pm.read_u64(wrapper + 0x90)
                        except OSError:
                            continue
                        if tag != expected_tag or not self._sane_heap_ptr(owner):
                            continue
                        if not self._looks_like_vtable(vtable) or not self._sane_heap_ptr(data):
                            continue
                        try:
                            data_vtable = pm.read_u64(data)
                        except OSError:
                            continue
                        if not self._looks_like_vtable(data_vtable):
                            continue
                        components_by_owner.setdefault(owner, {}).setdefault(name, (wrapper, data))
                tail = block[-tail_len:]
                offset += size
        return components_by_owner

    def _rebuild_component_index(self, pm: ProcessMemory) -> None:
        self._component_index_cache = self._scan_component_index(pm)
        known_owners = set(self._unit_owner_index.values())
        self._component_index_misses = known_owners.difference(self._component_index_cache)

    def _component_map_for_owners(
        self,
        pm: ProcessMemory,
        owners: set[int],
    ) -> dict[int, dict[str, tuple[int, int]]]:
        components_by_owner: dict[int, dict[str, tuple[int, int]]] = {}
        if not owners:
            return components_by_owner
        if self._component_index_cache is None:
            self._rebuild_component_index(pm)
        for owner in owners:
            components = self._validated_owner_components(
                pm,
                owner,
                self._component_index_cache.get(owner, {}),
            )
            if components:
                components_by_owner[owner] = components
        return components_by_owner

    def _append_unit_field(
        self,
        pm: ProcessMemory,
        fields: list[UnitMemoryField],
        key: str,
        label: str,
        value_type: str,
        address: int,
        category: str,
        writable: bool = True,
        note: str = "",
        extra_writes: tuple[tuple[int, str], ...] = (),
    ) -> None:
        if not address:
            return
        try:
            value = self._read_memory_value(pm, address, value_type)
        except OSError:
            return
        if isinstance(value, float):
            if not math.isfinite(value) or abs(value) > 100000000.0:
                return
        fields.append(
            UnitMemoryField(
                key=key,
                label=label,
                value_type=value_type,
                value=value,
                address=address,
                category=category,
                write_address=address if writable else 0,
                write_type=value_type if writable else "",
                note=note,
                extra_writes=extra_writes if writable else (),
            )
        )

    def _append_attack_fields(
        self,
        pm: ProcessMemory,
        fields: list[UnitMemoryField],
        key_prefix: str,
        label_prefix: str,
        data: int,
    ) -> None:
        damage_note = "运行时攻击组件字段；用于实际选中单位，面板黄字可能有缓存"
        timing_note = "运行时攻击组件字段；已按当前选中单位链读写验证"
        candidate_note = "经典版字段候选；当前样本稳定，但语义仍以游戏内效果为准"
        readonly_candidate_note = "经典版字段候选；只读展示，未开放写入"
        self._append_unit_field(pm, fields, f"{key_prefix}_multiplier", f"{label_prefix}倍率/骰面", "i32", data + 0xF8, "攻击", note=damage_note)
        self._append_unit_field(pm, fields, f"{key_prefix}_multiplier_cache", f"{label_prefix}倍率缓存", "i32", data + 0xFC, "攻击", note=damage_note)
        self._append_unit_field(pm, fields, f"{key_prefix}_dice", f"{label_prefix}骰子", "i32", data + 0x100, "攻击", note=damage_note)
        self._append_unit_field(pm, fields, f"{key_prefix}_base1", f"{label_prefix}基础1(当前)", "i32", data + 0x104, "攻击", note=damage_note)
        self._append_unit_field(pm, fields, f"{key_prefix}_base2", f"{label_prefix}基础2(当前)", "i32", data + 0x108, "攻击", note=damage_note)
        self._append_unit_field(pm, fields, f"{key_prefix}_dice_cache", f"{label_prefix}骰子缓存", "i32", data + 0x10C, "攻击", note=damage_note)
        self._append_unit_field(pm, fields, f"{key_prefix}_internal_bonus1", f"{label_prefix}内部加成槽1", "i32", data + 0x110, "攻击", note=damage_note)
        self._append_unit_field(pm, fields, f"{key_prefix}_internal_bonus2", f"{label_prefix}内部加成槽2", "i32", data + 0x114, "攻击", note=damage_note)
        self._append_unit_field(pm, fields, f"{key_prefix}_sound", f"{label_prefix}攻击音效码", "i32", data + 0x118, "攻击", note=damage_note)
        self._append_unit_field(pm, fields, f"{key_prefix}_damage_loss_factor", f"{label_prefix}丢失因子(候选只读)", "f32", data + 0x11C, "攻击", writable=False, note=readonly_candidate_note)
        self._append_unit_field(pm, fields, f"{key_prefix}_type", f"{label_prefix}种类", "i32", data + 0x16C, "攻击")
        self._append_unit_field(pm, fields, f"{key_prefix}_max_targets", f"{label_prefix}最大目标数(候选)", "i32", data + 0x178, "攻击", note=candidate_note)
        self._append_unit_field(pm, fields, f"{key_prefix}_interval", f"{label_prefix}间隔/冷却", "f32", data + 0x200, "攻击", note=timing_note)
        self._append_unit_field(pm, fields, f"{key_prefix}_first_delay", f"{label_prefix}首次延时", "f32", data + 0x228, "攻击", note=timing_note)
        self._append_unit_field(pm, fields, f"{key_prefix}_acquire_range", f"{label_prefix}主动攻击范围", "f32", data + 0x370, "攻击", note=timing_note)
        self._append_unit_field(pm, fields, f"{key_prefix}_projectile_speed", f"{label_prefix}投射物速度", "f32", data + 0x398, "攻击", note=timing_note)
        self._append_unit_field(pm, fields, f"{key_prefix}_range", f"{label_prefix}范围", "f32", data + 0x3A8, "攻击", note=timing_note)
        self._append_unit_field(pm, fields, f"{key_prefix}_range_buffer", f"{label_prefix}范围缓冲", "f32", data + 0x3C0, "攻击", note=timing_note)

    @staticmethod
    def _looks_like_rawcode(value: int) -> bool:
        data = struct.pack(">I", value & 0xFFFFFFFF)
        return all(32 <= byte < 127 for byte in data) and any(65 <= byte <= 90 for byte in data)

    @staticmethod
    def _looks_like_item_rawcode(value: int) -> bool:
        data = struct.pack(">I", value & 0xFFFFFFFF)
        return all(
            48 <= byte <= 57 or 65 <= byte <= 90 or 97 <= byte <= 122
            for byte in data
        )

    def _ability_instance_from_wrapper(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        wrapper: int,
        component_rawcodes: set[int],
    ) -> AbilityInstance | None:
        try:
            vtable = pm.read_u64(wrapper)
            tag = pm.read_u64(wrapper + 0x18)
            wrapper_owner = pm.read_u64(wrapper + 0x50)
            data = pm.read_u64(wrapper + 0x90)
        except OSError:
            return None
        if wrapper_owner != candidate.owner_address:
            return None
        if not self._looks_like_vtable(vtable) or not self._sane_heap_ptr(data):
            return None
        class_rawcode = (tag >> 32) & 0xFFFFFFFF
        if class_rawcode in component_rawcodes:
            return None
        if not self._looks_like_rawcode(class_rawcode):
            return None
        try:
            data_vtable = pm.read_u64(data)
            unit = pm.read_u64(data + 0x68)
            rawcode = pm.read_u32(data + 0x70)
            mirror_rawcode = pm.read_u32(data + 0x78)
            handle = pm.read_u64(wrapper + 0x20)
            data_cache_pointer = pm.read_u64(data + 0xA0)
        except OSError:
            return None
        if not self._looks_like_vtable(data_vtable):
            return None
        if unit != candidate.unit_address:
            return None
        if rawcode != mirror_rawcode or not self._looks_like_rawcode(rawcode):
            return None
        return AbilityInstance(
            slot=0,
            wrapper_address=wrapper,
            data_address=data,
            wrapper_vtable=vtable,
            data_vtable=data_vtable,
            wrapper_tag_address=wrapper + 0x18,
            wrapper_tag=tag,
            handle=handle,
            class_rawcode=class_rawcode,
            rawcode=rawcode,
            rawcode_address=data + 0x70,
            mirror_rawcode_address=data + 0x78,
            data_cache_address=data + 0xA0,
            data_cache_pointer=data_cache_pointer if self._sane_heap_ptr(data_cache_pointer) else 0,
        )

    def _global_ability_instances_from_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        component_rawcodes: set[int],
        required_rawcodes: set[int] | None,
        seen_wrappers: set[int],
    ) -> list[AbilityInstance]:
        if not candidate.owner_address:
            return []
        rawcode_filter = {
            rawcode & 0xFFFFFFFF
            for rawcode in (required_rawcodes or set())
            if rawcode and self._looks_like_rawcode(rawcode)
        }
        instances: list[AbilityInstance] = []
        owner_pattern = struct.pack("<Q", candidate.owner_address)
        for owner_ref in pm.scan_bytes_private(owner_pattern, max_region_size=16 * 1024 * 1024):
            wrapper = owner_ref - 0x50
            if wrapper in seen_wrappers:
                continue
            instance = self._ability_instance_from_wrapper(pm, candidate, wrapper, component_rawcodes)
            if instance is None:
                continue
            if rawcode_filter and instance.rawcode not in rawcode_filter:
                continue
            seen_wrappers.add(wrapper)
            instances.append(instance)
        return instances

    def _validated_cached_ability_instances(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        key: tuple[int, int, int, bool],
    ) -> list[AbilityInstance] | None:
        cached = self._ability_instances_cache.get(key)
        if cached is None:
            return None
        for instance in cached:
            try:
                if pm.read_u64(instance.wrapper_address + 0x50) != candidate.owner_address:
                    return None
                if pm.read_u64(instance.wrapper_address + 0x90) != instance.data_address:
                    return None
                if pm.read_u64(instance.data_address + 0x68) != candidate.unit_address:
                    return None
                if pm.read_u32(instance.data_address + 0x70) != instance.rawcode:
                    return None
                if pm.read_u32(instance.data_address + 0x78) != instance.rawcode:
                    return None
            except OSError:
                return None
        return list(cached)

    def _near_ability_instances_from_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        component_rawcodes: set[int],
    ) -> tuple[list[AbilityInstance], set[int]]:
        start = candidate.owner_address - self.ABILITY_WRAPPER_SCAN_BACK
        end = candidate.owner_address + self.ABILITY_WRAPPER_SCAN_FORWARD
        instances: list[AbilityInstance] = []
        seen_wrappers: set[int] = set()
        for region in pm.regions():
            region_start = max(start, region.base)
            region_end = min(end, region.base + region.size)
            if region_end - region_start < 0x98:
                continue
            try:
                data = pm.read(region_start, region_end - region_start)
            except OSError:
                continue
            first = (8 - ((region_start - candidate.owner_address) & 7)) & 7
            for offset in range(first, len(data) - 0x97, 8):
                wrapper = region_start + offset
                try:
                    vtable = struct.unpack_from("<Q", data, offset)[0]
                    tag = struct.unpack_from("<Q", data, offset + 0x18)[0]
                    owner = struct.unpack_from("<Q", data, offset + 0x50)[0]
                    ability_data = struct.unpack_from("<Q", data, offset + 0x90)[0]
                except struct.error:
                    continue
                if owner != candidate.owner_address:
                    continue
                if not self._looks_like_vtable(vtable) or not self._sane_heap_ptr(ability_data):
                    continue
                class_rawcode = (tag >> 32) & 0xFFFFFFFF
                if class_rawcode in component_rawcodes or not self._looks_like_rawcode(class_rawcode):
                    continue
                instance = self._ability_instance_from_wrapper(pm, candidate, wrapper, component_rawcodes)
                if instance is None:
                    continue
                seen_wrappers.add(wrapper)
                instances.append(instance)
        return instances, seen_wrappers

    def _ability_instances_from_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        required_rawcodes: set[int] | None = None,
        allow_global_scan: bool = False,
    ) -> list[AbilityInstance]:
        if not candidate.owner_address or not candidate.unit_address:
            return []
        cache_key = (candidate.handle, candidate.owner_address, candidate.unit_address, bool(allow_global_scan))
        if required_rawcodes is None:
            cached = self._validated_cached_ability_instances(pm, candidate, cache_key)
            if cached is not None:
                return cached
        component_rawcodes = {tag >> 32 for tag in self.COMPONENT_TAGS.values()}
        instances, seen_wrappers = self._near_ability_instances_from_candidate(pm, candidate, component_rawcodes)
        if allow_global_scan:
            instances.extend(
                self._global_ability_instances_from_candidate(
                    pm,
                    candidate,
                    component_rawcodes,
                    required_rawcodes,
                    seen_wrappers,
                )
            )
        instances.sort(key=lambda instance: (instance.handle, instance.wrapper_address))
        instances = [
            replace(instance, slot=index + 1)
            for index, instance in enumerate(instances)
        ]
        if required_rawcodes is None:
            self._ability_instances_cache[cache_key] = list(instances)
        return instances

    def _inventory_record_address(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        inventory_data: int,
    ) -> int:
        if not inventory_data or not candidate.unit_address:
            return 0
        for offset in range(0, 0x4000, 0x210):
            record = inventory_data + offset
            try:
                if (
                    pm.read_u64(record + 0x68) == candidate.unit_address
                    and pm.read_u32(record + 0x70) == 0x41496E76
                ):
                    return record
            except OSError:
                continue
        return 0

    def _item_object_from_handle(self, pm: ProcessMemory, owner: int, handle: int) -> int:
        if not handle or handle == 0xFFFFFFFFFFFFFFFF:
            return 0
        if owner:
            for offset in range(-0x8000, 0x8000, 8):
                wrapper = owner + offset
                try:
                    if pm.read_u64(wrapper + 0x18) != self.ITEM_OWNER_TAG:
                        continue
                    if pm.read_u64(wrapper + 0x20) != handle:
                        continue
                    item = pm.read_u64(wrapper + 0x90)
                    if (
                        self._sane_heap_ptr(item)
                        and self._looks_like_vtable(pm.read_u64(item))
                        and pm.read_u64(item + 0x18) == handle
                    ):
                        return item
                except OSError:
                    continue

        for address in pm.scan_bytes_private(struct.pack("<Q", handle), max_region_size=1024 * 1024):
            item = address - 0x18
            try:
                if self._looks_like_vtable(pm.read_u64(item)) and pm.read_u64(item + 0x18) == handle:
                    return item
            except OSError:
                continue
        return 0

    def _item_objects_from_handles(
        self,
        pm: ProcessMemory,
        handles: Iterable[int],
        owner: int = 0,
    ) -> dict[int, int]:
        wanted = {
            int(handle)
            for handle in handles
            if int(handle) and int(handle) != 0xFFFFFFFFFFFFFFFF
        }
        if not wanted:
            return {}
        found: dict[int, int] = {}
        for handle in list(wanted):
            item = self._item_object_cache.get(handle, 0)
            if not item:
                continue
            try:
                if self._looks_like_vtable(pm.read_u64(item)) and pm.read_u64(item + 0x18) == handle:
                    found[handle] = item
                else:
                    self._item_object_cache.pop(handle, None)
            except OSError:
                self._item_object_cache.pop(handle, None)
        missing = wanted.difference(found)
        if not missing:
            return found
        if owner:
            start = owner - 0x8000
            end = owner + 0x8000
            for region in pm.regions():
                if not missing:
                    break
                region_start = max(start, region.base)
                region_end = min(end, region.base + region.size)
                if region_end - region_start < 0x98:
                    continue
                try:
                    data = pm.read(region_start, region_end - region_start)
                except OSError:
                    continue
                first = (8 - ((region_start - owner) & 7)) & 7
                for offset in range(first, len(data) - 0x97, 8):
                    if not missing:
                        break
                    try:
                        tag = struct.unpack_from("<Q", data, offset + 0x18)[0]
                        handle = struct.unpack_from("<Q", data, offset + 0x20)[0]
                        item = struct.unpack_from("<Q", data, offset + 0x90)[0]
                    except struct.error:
                        continue
                    if tag != self.ITEM_OWNER_TAG or handle not in missing:
                        continue
                    try:
                        if (
                            self._sane_heap_ptr(item)
                            and self._looks_like_vtable(pm.read_u64(item))
                            and pm.read_u64(item + 0x18) == handle
                        ):
                            found[handle] = item
                            self._item_object_cache[handle] = item
                            missing.remove(handle)
                    except OSError:
                        continue
        if not missing:
            return found
        patterns = {struct.pack("<Q", handle): handle for handle in missing}
        tail_len = 7
        for region in pm.regions():
            if len(found) == len(wanted):
                break
            if region.typ != MEM_PRIVATE or region.size > 1024 * 1024:
                continue
            offset = 0
            tail = b""
            while offset < region.size and len(found) < len(wanted):
                size = min(4 * 1024 * 1024, region.size - offset)
                try:
                    data = tail + pm.read(region.base + offset, size)
                except OSError:
                    offset += size
                    tail = b""
                    continue
                base = region.base + offset - len(tail)
                for pattern, handle in patterns.items():
                    if handle in found:
                        continue
                    start = 0
                    while True:
                        idx = data.find(pattern, start)
                        if idx < 0:
                            break
                        address = base + idx
                        if address >= region.base:
                            item = address - 0x18
                            try:
                                if (
                                    self._looks_like_vtable(pm.read_u64(item))
                                    and pm.read_u64(item + 0x18) == handle
                                ):
                                    found[handle] = item
                                    self._item_object_cache[handle] = item
                                    break
                            except OSError:
                                pass
                        start = idx + 1
                tail = data[-tail_len:]
                offset += size
        return found

    def _inventory_items_from_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        components: dict[str, tuple[int, int]] | None = None,
    ) -> list[InventoryItem]:
        components = components if components is not None else self._selected_components(pm, candidate.owner_address)
        inventory = components.get("inventory")
        if inventory is None:
            return []
        _wrapper, data = inventory
        record = self._inventory_record_address(pm, candidate, data)
        if not record:
            return []

        items: list[InventoryItem] = []
        slot_handles: list[tuple[int, int, int]] = []
        for index in range(6):
            handle_address = record + 0xD4 + index * 0x0C
            try:
                handle = pm.read_u64(handle_address)
            except OSError:
                handle = 0
            slot_handles.append((index, handle_address, handle))
        item_by_handle = self._item_objects_from_handles(
            pm,
            (handle for _index, _address, handle in slot_handles),
            candidate.owner_address,
        )
        for index, handle_address, handle in slot_handles:
            item_address = item_by_handle.get(handle, 0)
            rawcode = 0
            rawcode_address = 0
            mirror_rawcode = 0
            mirror_rawcode_address = 0
            ability_rawcode = 0
            ability_rawcode_address = 0
            charges = 0
            charges_address = 0
            if item_address:
                rawcode_address = item_address + 0x70
                try:
                    rawcode = pm.read_u32(rawcode_address)
                except OSError:
                    rawcode = 0
                    rawcode_address = 0
                mirror_rawcode_address = item_address + 0x178
                try:
                    mirror_rawcode = pm.read_u32(mirror_rawcode_address)
                    if not self._looks_like_rawcode(mirror_rawcode):
                        mirror_rawcode = 0
                        mirror_rawcode_address = 0
                except OSError:
                    mirror_rawcode = 0
                    mirror_rawcode_address = 0
                ability_rawcode_address = item_address + 0x1B8
                try:
                    ability_rawcode = pm.read_u32(ability_rawcode_address)
                    if not self._looks_like_rawcode(ability_rawcode):
                        ability_rawcode = 0
                        ability_rawcode_address = 0
                except OSError:
                    ability_rawcode = 0
                    ability_rawcode_address = 0
                charges_address = item_address + self.ITEM_CHARGES_OFFSET
                try:
                    charges = pm.read_i32(charges_address)
                    if not 0 <= charges <= 999:
                        charges = 0
                        charges_address = 0
                except OSError:
                    charges = 0
                    charges_address = 0
            items.append(
                InventoryItem(
                    slot=index + 1,
                    handle=handle,
                    handle_address=handle_address,
                    item_address=item_address,
                    rawcode=rawcode,
                    rawcode_address=rawcode_address,
                    mirror_rawcode=mirror_rawcode,
                    mirror_rawcode_address=mirror_rawcode_address,
                    ability_rawcode=ability_rawcode,
                    ability_rawcode_address=ability_rawcode_address,
                    charges=charges,
                    charges_address=charges_address,
                )
            )
        return items

    def _unit_fields_from_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
    ) -> list[UnitMemoryField]:
        fields: list[UnitMemoryField] = []
        self._append_unit_field(pm, fields, "hp_max", "HP-最大值", "f32", candidate.hp_max_address, "基础")
        self._append_unit_field(pm, fields, "hp_current", "HP-当前值", "f32", candidate.hp_current_address, "基础")
        self._append_unit_field(pm, fields, "hp_regen", "HP-回复率", "f32", candidate.hp_regen_address, "基础")
        self._append_unit_field(pm, fields, "mp_max", "MP-最大值", "f32", candidate.mp_max_address, "基础")
        self._append_unit_field(pm, fields, "mp_current", "MP-当前值", "f32", candidate.mp_current_address, "基础")
        self._append_unit_field(pm, fields, "mp_regen", "MP-回复率", "f32", candidate.mp_regen_address, "基础")
        self._append_unit_field(pm, fields, "x", "坐标-X", "f32", candidate.x_address, "坐标")
        self._append_unit_field(pm, fields, "y", "坐标-Y", "f32", candidate.y_address, "坐标")

        components = self._selected_components(pm, candidate.owner_address)
        move = components.get("move")
        if move is not None:
            _wrapper, data = move
            self._append_unit_field(pm, fields, "move_speed", "移动速度", "f32", data + 0xD8, "移动")

        if candidate.unit_address:
            self._append_unit_field(pm, fields, "armor", "护甲", "f32", candidate.unit_address + 0x2E8, "防御")
            self._append_unit_field(pm, fields, "armor_type", "护甲类型", "i32", candidate.unit_address + 0x2F0, "防御")

        ability_instances: list[AbilityInstance] = []

        hero_skill_config_rawcodes: list[int] = []
        hero = components.get("hero")
        if hero is not None:
            _wrapper, data = hero
            self._append_unit_field(pm, fields, "xp", "经验值", "i32", data + 0x100, "英雄")
            self._append_unit_field(pm, fields, "skill_points", "技能点", "i32", data + 0x104, "英雄")
            self._append_unit_field(pm, fields, "base_strength", "力量(基础)", "i32", data + 0x108, "英雄")
            try:
                base_intelligence, total_intelligence = self._get_hero_intelligence_pair_via_native_internal(pm, candidate)
                fields.append(
                    UnitMemoryField(
                        key="intelligence_total",
                        label="智力(当前总值)",
                        value_type="i32",
                        value=total_intelligence,
                        address=data + 0x118,
                        category="英雄",
                        write_address=data + 0x118,
                        write_type="i32",
                        note=(
                            "内部 GetHeroInt 真实总智力；写入通过内部 SetHeroInt；"
                            f"基础智力={base_intelligence}"
                        ),
                    )
                )
            except Exception as exc:
                self._append_unit_field(
                    pm,
                    fields,
                    "intelligence_total",
                    "智力(当前总值候选)",
                    "f32",
                    data + 0x118,
                    "英雄",
                    note=f"内部 GetHeroInt 读取失败，暂用旧缓存候选：{exc}",
                )
            self._append_unit_field(pm, fields, "base_agility", "敏捷(基础)", "i32", data + 0x130, "英雄")
            growth_note = "英雄组件成长值，不是面板装备/光环加成"
            self._append_unit_field(pm, fields, "strength_growth", "力量成长/级", "f32", data + 0x188, "英雄", note=growth_note)
            self._append_unit_field(pm, fields, "intelligence_growth", "智力成长/级", "f32", data + 0x198, "英雄", note=growth_note)
            self._append_unit_field(pm, fields, "agility_growth", "敏捷成长/级", "f32", data + 0x1A8, "英雄", note=growth_note)
            skill_name_note = "英雄技能栏 rawcode；写入已学技能时会使用现有运行时模板同步实例并刷新命令卡"
            skill_cache_note = "旧版候选/运行时缓存；单改这里通常不改变已学技能效果"
            for index in range(self.HERO_SKILL_SLOT_COUNT):
                config_address = data + 0x204 + index * 4
                try:
                    current_config_rawcode = pm.read_u32(config_address)
                except OSError:
                    current_config_rawcode = 0
                hero_skill_config_rawcodes.append(current_config_rawcode)
            ability_instances = self._ability_instances_from_candidate(
                pm,
                candidate,
            )
            for index in range(self.HERO_SKILL_SLOT_COUNT):
                number = index + 1
                config_address = data + 0x204 + index * 4
                cache_address = data + 0x1BC + index * 4
                extra_writes = [(cache_address, "rawcode")]
                self._append_unit_field(
                    pm,
                    fields,
                    f"skill{number}_name",
                    f"技能{number}名称",
                    "rawcode",
                    config_address,
                    "技能",
                    note=skill_name_note,
                    extra_writes=tuple(extra_writes),
                )
                self._append_unit_field(
                    pm,
                    fields,
                    f"skill{number}_cache_rawcode",
                    f"技能{number}缓存rawcode",
                    "rawcode",
                    cache_address,
                    "技能",
                    writable=False,
                    note=skill_cache_note,
                )
                self._append_unit_field(
                    pm,
                    fields,
                    f"skill{number}_learnable",
                    f"技能{number}可学",
                    "i32",
                    data + 0x1D4 + index * 4,
                    "技能",
                    note="英雄组件技能等级/可学数组",
                )
                self._append_unit_field(
                    pm,
                    fields,
                    f"skill{number}_requirement",
                    f"技能{number}要求",
                    "i32",
                    data + 0x1EC + index * 4,
                    "技能",
                    note="英雄组件技能需求数组",
                )

        if hero_skill_config_rawcodes:
            skill_instance_by_index = self._map_hero_skill_instances(
                hero_skill_config_rawcodes,
                ability_instances,
            )
            used_instance_wrappers = {
                instance.wrapper_address
                for instance in skill_instance_by_index.values()
            }
            for index, rawcode in enumerate(hero_skill_config_rawcodes):
                if not rawcode:
                    continue
                instance = skill_instance_by_index.get(index)
                if instance is None:
                    continue
                number = index + 1
                mirror = (
                    ((instance.mirror_rawcode_address, "rawcode"),)
                    if instance.mirror_rawcode_address
                    else ()
                )
                fields.append(
                    UnitMemoryField(
                        key=f"skill{number}_instance_rawcode",
                        label=f"技能{number}实例rawcode",
                        value_type="rawcode",
                        value=instance.rawcode,
                        address=instance.rawcode_address,
                        category="技能",
                        write_address=0,
                        write_type="",
                        note=(
                            f"class={instance.class_text} wrapper=0x{instance.wrapper_address:x}; "
                            "只读：运行时能力实例 ID，单改这里不会改变技能效果"
                        ),
                        extra_writes=(),
                    )
                )
                fields.append(
                    UnitMemoryField(
                        key=f"skill{number}_effect_class",
                        label=f"技能{number}效果类",
                        value_type="rawcode",
                        value=instance.class_rawcode,
                        address=instance.wrapper_tag_address,
                        category="技能",
                        write_address=0,
                        write_type="",
                        note=(
                            f"wrapper=0x{instance.wrapper_address:x} handle=0x{instance.handle:x}; "
                            "只读：运行时能力类决定已存在技能效果，单改 rawcode 不会改这里"
                        ),
                    )
                )
                fields.append(
                    UnitMemoryField(
                        key=f"skill{number}_data_vtable",
                        label=f"技能{number}数据vtable",
                        value_type="ptr",
                        value=instance.data_vtable,
                        address=instance.data_address,
                        category="技能",
                        write_address=0,
                        write_type="",
                        note="只读：能力实例数据对象虚表；不同效果类通常不同",
                    )
                )
                fields.append(
                    UnitMemoryField(
                        key=f"skill{number}_data_cache",
                        label=f"技能{number}数据缓存",
                        value_type="ptr",
                        value=instance.data_cache_pointer,
                        address=instance.data_cache_address,
                        category="技能",
                        write_address=0,
                        write_type="",
                        note="只读：疑似 AbilDataCacheNode 指针；实际技能数据不只由 rawcode/cache 字段决定",
                    )
                )
        else:
            used_instance_wrappers = set()

        for instance in ability_instances:
            if instance.wrapper_address in used_instance_wrappers:
                continue
            mirror = (
                ((instance.mirror_rawcode_address, "rawcode"),)
                if instance.mirror_rawcode_address
                else ()
            )
            fields.append(
                UnitMemoryField(
                    key=f"ability_{instance.slot:02d}_rawcode",
                    label=f"能力{instance.slot:02d} rawcode",
                    value_type="rawcode",
                    value=instance.rawcode,
                    address=instance.rawcode_address,
                    category="能力实例",
                    write_address=0,
                    write_type="",
                    note=(
                        f"class={instance.class_text} wrapper=0x{instance.wrapper_address:x}; "
                        "只读：实际挂在单位上的能力实例 ID，单改这里不会改变效果"
                    ),
                    extra_writes=(),
                )
            )
            fields.append(
                UnitMemoryField(
                    key=f"ability_{instance.slot:02d}_effect_class",
                    label=f"能力{instance.slot:02d}效果类",
                    value_type="rawcode",
                    value=instance.class_rawcode,
                    address=instance.wrapper_tag_address,
                    category="能力实例",
                    write_address=0,
                    write_type="",
                    note=(
                        f"wrapper=0x{instance.wrapper_address:x} handle=0x{instance.handle:x}; "
                        "只读：运行时能力类决定已存在能力效果"
                    ),
                )
            )
            fields.append(
                UnitMemoryField(
                    key=f"ability_{instance.slot:02d}_data_vtable",
                    label=f"能力{instance.slot:02d}数据vtable",
                    value_type="ptr",
                    value=instance.data_vtable,
                    address=instance.data_address,
                    category="能力实例",
                    write_address=0,
                    write_type="",
                    note="只读：能力实例数据对象虚表；不同效果类通常不同",
                )
            )
            fields.append(
                UnitMemoryField(
                    key=f"ability_{instance.slot:02d}_data_cache",
                    label=f"能力{instance.slot:02d}数据缓存",
                    value_type="ptr",
                    value=instance.data_cache_pointer,
                    address=instance.data_cache_address,
                    category="能力实例",
                    write_address=0,
                    write_type="",
                    note="只读：疑似 AbilDataCacheNode 指针",
                )
            )

        attack = components.get("attack")
        if attack is not None:
            _wrapper, data = attack
            self._append_attack_fields(pm, fields, "attack1", "攻击1", data)
            try:
                attack2_data = data + 0x638
                if self._looks_like_vtable(pm.read_u64(attack2_data)) and pm.read_i32(attack2_data + 0x08) == pm.read_i32(data + 0x08):
                    self._append_attack_fields(pm, fields, "attack2", "攻击2", attack2_data)
            except OSError:
                pass

        for item in self._inventory_items_from_candidate(pm, candidate, components):
            if item.rawcode:
                fields.append(
                    UnitMemoryField(
                        key=f"inventory_slot_{item.slot}",
                        label=f"物品槽{item.slot}",
                        value_type="rawcode",
                        value=item.rawcode,
                        address=item.rawcode_address,
                        category="物品栏",
                        write_address=item.rawcode_address,
                        write_type="rawcode",
                        note=(
                            f"handle=0x{item.handle:x} item=0x{item.item_address:x}; "
                            f"mirror=0x{item.mirror_rawcode_address:x} ability={format_rawcode(item.ability_rawcode) if item.ability_rawcode else '0'}; "
                            "写入时通过内部物品栏函数创建/替换本槽 item，不交换其他物品槽"
                        ),
                    )
                )
            else:
                note = "空" if not item.handle else f"未解析 item 对象；handle=0x{item.handle:x}"
                fields.append(
                    UnitMemoryField(
                        key=f"inventory_slot_{item.slot}",
                        label=f"物品槽{item.slot}",
                        value_type="rawcode",
                        value=0,
                        address=item.handle_address,
                        category="物品栏",
                        write_address=item.handle_address,
                        write_type="rawcode",
                        note=note + "；写入时通过内部物品栏函数在本槽创建物品",
                    )
                )
            fields.append(
                UnitMemoryField(
                    key=f"inventory_slot_{item.slot}_charges",
                    label=f"物品槽{item.slot}数量",
                    value_type="i32",
                    value=item.charges,
                    address=item.charges_address or item.handle_address,
                    category="物品栏",
                    write_address=item.charges_address,
                    write_type="i32" if item.charges_address else "",
                    note=(
                        f"item charges offset=0x{self.ITEM_CHARGES_OFFSET:x}"
                        if item.charges_address
                        else "空槽或未解析 item 对象"
                    ),
                )
            )
        return fields

    def read_selected_unit_fields(self) -> tuple[VisibleUnitPanel, UnitCandidate, list[UnitMemoryField]]:
        with ProcessMemory(self.pid) as pm:
            candidate = self.locate_selected_unit_by_handle(pm, allow_deep_scan=True)
            candidate = self._candidate_with_selected_unit_type_id(pm, candidate)
            panel = self._panel_from_candidate(pm, candidate)
            return panel, candidate, self._unit_fields_from_candidate(pm, candidate)

    def _recover_win10_native_handlers(
        self,
        isolated: "War3Trainer",
        pm: ProcessMemory,
        diagnostics: Win10ReadLogger,
    ) -> tuple[int, tuple[str, ...]]:
        wanted = set(self.WIN10_COMPAT_NATIVE_NAMES)
        isolated._native_handlers.update(
            {
                name: handler
                for name, handler in self._native_handlers.items()
                if name in wanted
            }
        )
        discovery_error = ""
        try:
            isolated._discover_native_handlers_near_table_win10(pm, wanted)
        except Exception as exc:
            discovery_error = repr(exc)

        regions = pm.regions(force_refresh=True)
        validated: dict[str, NativeHandler] = {}
        for name in sorted(wanted):
            handler = isolated._native_handlers.get(name)
            if handler is None or handler.name != name:
                continue
            record_region = self._region_for_address(regions, handler.record_address)
            if record_region is None or record_region.typ != MEM_PRIVATE:
                continue
            if not self._is_executable_image_address(regions, handler.handler_address):
                continue
            try:
                size = pm.read_u64(handler.record_address + 8)
            except OSError:
                continue
            if size != len(name):
                continue
            validated[name] = handler

        shared_before = set(self._native_handlers)
        for name, handler in validated.items():
            self._native_handlers.setdefault(name, handler)

        profile_names = set(self.NATIVE_RECORD_PROFILE_EXTERNALS)
        missing_profile = tuple(sorted(profile_names.difference(validated)))
        recovered_profile = len(profile_names) - len(missing_profile)
        self._last_win10_native_recovered = recovered_profile
        self._last_win10_native_missing = missing_profile
        diagnostics.log(
            "win10_native_recovery",
            requested=len(wanted),
            validated=len(validated),
            shared_added=len(set(self._native_handlers).difference(shared_before)),
            profile_recovered=recovered_profile,
            profile_total=len(profile_names),
            profile_missing=list(missing_profile),
            all_missing=sorted(wanted.difference(validated)),
            discovery_error=discovery_error,
        )
        return recovered_profile, missing_profile

    @contextmanager
    def _win10_memory_operation(
        self,
        operation: str,
        *,
        write: bool = False,
    ) -> Iterator[tuple[Win10ReadLogger, Win10ProcessMemory]]:
        diagnostics = Win10ReadLogger(self.pid)
        self._last_win10_log_path = str(diagnostics.latest_path)
        diagnostics.log("win10_operation_begin", operation=operation, write=write)
        try:
            with Win10ProcessMemory(self.pid, diagnostics, write=write) as pm:
                yield diagnostics, pm
            diagnostics.log("win10_operation_success", operation=operation)
        except Exception as exc:
            diagnostics.log_traceback("win10_operation_failure", exc)
            raise
        finally:
            diagnostics.close()

    def _win10_session_for_identity(
        self,
        handle: int,
        owner: int,
        unit: int,
    ) -> "War3Trainer":
        identity = (int(handle), int(owner), int(unit))
        isolated = self._win10_session_trainer
        if (
            isolated is None
            or isolated.pid != self.pid
            or self._win10_session_identity != identity
        ):
            isolated = War3Trainer(self.pid)
            self._win10_session_trainer = isolated
            self._win10_session_identity = identity
        self._seed_win10_isolated_state(isolated)
        return isolated

    def _seed_win10_isolated_state(self, isolated: "War3Trainer") -> dict[str, int]:
        owner_index = dict(self._unit_owner_index)
        owner_index.update(isolated._unit_owner_index)
        isolated._unit_owner_index = owner_index
        isolated._selection_player_candidates = list(
            dict.fromkeys(
                [
                    *isolated._selection_player_candidates,
                    *self._selection_player_candidates,
                ]
            )
        )
        # A discovered handle slot can remain readable after the selection changes.
        # Reusing it pins later reads to the first unit seen in this session.
        isolated._selected_handle_addresses = list(self.KNOWN_SELECTED_HANDLE_ADDRESSES)
        resource_candidates = {
            start: list(caches)
            for start, caches in self._resource_candidates_by_start.items()
        }
        for start, caches in isolated._resource_candidates_by_start.items():
            resource_candidates[start] = list(
                dict.fromkeys([*resource_candidates.get(start, []), *caches])
            )
        isolated._resource_candidates_by_start = resource_candidates

        component_index: dict[int, dict[str, tuple[int, int]]] = {}
        if self._component_index_cache is not None:
            component_index.update(
                {
                    owner: dict(components)
                    for owner, components in self._component_index_cache.items()
                }
            )
        if isolated._component_index_cache is not None:
            for owner, components in isolated._component_index_cache.items():
                component_index.setdefault(owner, {}).update(components)
        isolated._component_index_cache = component_index or None

        selected_components_cache = {
            key: dict(components)
            for key, components in self._selected_components_cache.items()
        }
        for key, components in isolated._selected_components_cache.items():
            selected_components_cache[key] = dict(components)
        isolated._selected_components_cache = selected_components_cache
        isolated._unit_component_layout_confirmed = bool(
            self._unit_component_layout_confirmed
            or isolated._unit_component_layout_confirmed
        )

        isolated._selection_manager_offset = self._selection_manager_offset
        isolated._selection_list_offsets = tuple(self._selection_list_offsets)
        isolated._native_handlers.update(self._native_handlers)
        return {
            "owner_cache": len(isolated._unit_owner_index),
            "selection_player_candidates": len(isolated._selection_player_candidates),
            "selected_handle_addresses": len(isolated._selected_handle_addresses),
            "resource_candidate_groups": len(isolated._resource_candidates_by_start),
            "component_index": len(isolated._component_index_cache or {}),
            "selected_component_cache": len(isolated._selected_components_cache),
            "native_handlers": len(isolated._native_handlers),
        }

    @staticmethod
    def _win10_candidate_from_identity(
        isolated: "War3Trainer",
        pm: ProcessMemory,
        handle: int,
        owner: int,
        unit: int,
    ) -> UnitCandidate:
        candidate = isolated._candidate_from_identity(
            pm,
            handle,
            owner,
            unit,
            f"win10_candidate handle=0x{handle:x} owner=0x{owner:x} unit=0x{unit:x}",
            900,
        )
        if candidate is None:
            raise RuntimeError("备用读取的单位身份已经失效，请重新点击备用读取")
        return candidate

    def read_selected_unit_fields_win10(
        self,
    ) -> tuple[VisibleUnitPanel, UnitCandidate, list[UnitMemoryField]]:
        diagnostics = Win10ReadLogger(self.pid)
        self._last_win10_log_path = str(diagnostics.latest_path)
        self._last_win10_native_recovered = 0
        self._last_win10_native_missing = ()
        diagnostics.log(
            "win10_read_begin",
            compat_revision=WIN10_COMPAT_REVISION,
            hwnd=f"0x{self.hwnd:x}",
            shared_native_handlers_before=len(self._native_handlers),
            shared_native_handler_names=sorted(self._native_handlers),
            shared_owner_cache_before=len(self._unit_owner_index),
            shared_selection_player_candidates_before=len(self._selection_player_candidates),
            shared_selected_handle_addresses_before=len(self._selected_handle_addresses),
            shared_resource_candidate_groups_before=len(self._resource_candidates_by_start),
            shared_component_cache_before=(
                len(self._component_index_cache)
                if self._component_index_cache is not None
                else None
            ),
        )
        try:
            isolated = self._win10_session_trainer
            reused_isolated = isolated is not None and isolated.pid == self.pid
            if not reused_isolated:
                isolated = War3Trainer(self.pid)
            seeded_state = self._seed_win10_isolated_state(isolated)
            diagnostics.log(
                "isolated_trainer_created",
                trainer_id=id(isolated),
                reused=reused_isolated,
                **seeded_state,
            )
            with Win10ProcessMemory(self.pid, diagnostics) as pm:
                with diagnostics.stage("initial_region_snapshot"):
                    pm.regions(force_refresh=True)
                with diagnostics.stage("recover_compat_native_handlers"):
                    native_recovered, native_missing = self._recover_win10_native_handlers(
                        isolated,
                        pm,
                        diagnostics,
                    )
                candidate: UnitCandidate | None = None
                try:
                    with diagnostics.stage("locate_selected_unit_jass"):
                        candidate = isolated.locate_selected_unit_by_jass_native_win10(
                            pm,
                            diagnostics,
                        )
                except Exception as exc:
                    diagnostics.log(
                        "win10_jass_selection_fallback",
                        exception=repr(exc),
                    )
                if candidate is None:
                    with diagnostics.stage("prepare_selection_layout"):
                        isolated._prepare_win10_selection_layout(pm, diagnostics)
                    with diagnostics.stage("locate_selected_unit_memory"):
                        candidate = isolated._locate_selected_unit_by_selection_manager_win10(
                            pm,
                            diagnostics,
                            discover=True,
                        )
                    if candidate is None:
                        raise RuntimeError(
                            "实时 JASS 选择和 selection manager 都没有定位到当前单选单位；"
                            "历史 handle 槽已禁用，请重新单击目标后重试"
                        )
                    candidate = replace(candidate, selection_source="win10_manager")
                    diagnostics.log(
                        "selection_candidate_found",
                        route="selection_manager_only",
                        handle=f"0x{candidate.handle:x}",
                        owner=f"0x{candidate.owner_address:x}",
                        unit=f"0x{candidate.unit_address:x}",
                        note=candidate.note,
                    )
                diagnostics.log(
                    "candidate_identity",
                    handle=f"0x{candidate.handle:x}",
                    owner=f"0x{candidate.owner_address:x}",
                    unit=f"0x{candidate.unit_address:x}",
                    selection_source=candidate.selection_source,
                    selection_slot=f"0x{candidate.selection_slot_address:x}",
                    note=candidate.note,
                )
                with diagnostics.stage("read_unit_type"):
                    candidate = isolated._candidate_with_selected_unit_type_id(pm, candidate)
                with diagnostics.stage("read_panel"):
                    panel = isolated._panel_from_candidate(pm, candidate)
                diagnostics.log(
                    "panel_values",
                    hp_text=panel.hp_text,
                    mp_text=panel.mp_text,
                    current_hp=panel.current_hp,
                    max_hp=panel.max_hp,
                    current_mp=panel.current_mp,
                    max_mp=panel.max_mp,
                    unit_type_id=(
                        format_rawcode(candidate.unit_type_id)
                        if candidate.unit_type_id
                        else ""
                    ),
                )
                with diagnostics.stage("read_all_fields"):
                    fields = isolated._unit_fields_from_candidate(pm, candidate)
                    fields = isolated._replace_win10_intelligence_field(
                        pm,
                        candidate,
                        fields,
                        diagnostics,
                    )

                fields_by_category: dict[str, int] = {}
                for field in fields:
                    fields_by_category[field.category] = fields_by_category.get(field.category, 0) + 1
                    diagnostics.log(
                        "field",
                        key=field.key,
                        label=field.label,
                        category=field.category,
                        value_type=field.value_type,
                        value=field.value,
                        address=f"0x{field.address:x}",
                        write_address=f"0x{field.write_address:x}",
                        write_type=field.write_type,
                        extra_writes=field.extra_writes,
                        note=field.note,
                    )
                diagnostics.log(
                    "field_summary",
                    total=len(fields),
                    by_category=fields_by_category,
                    owner_cache=len(isolated._unit_owner_index),
                    component_index=(
                        len(isolated._component_index_cache)
                        if isolated._component_index_cache is not None
                        else None
                    ),
                    component_misses=len(isolated._component_index_misses),
                    selected_component_cache=len(isolated._selected_components_cache),
                )
                self._win10_session_trainer = isolated
                self._win10_session_identity = (
                    candidate.handle,
                    candidate.owner_address,
                    candidate.unit_address,
                )
                diagnostics.log(
                    "shared_state_after_win10",
                    shared_native_handlers_after=len(self._native_handlers),
                    shared_owner_cache_after=len(self._unit_owner_index),
                    shared_component_cache_after=(
                        len(self._component_index_cache)
                        if self._component_index_cache is not None
                        else None
                    ),
                    compat_native_recovered=native_recovered,
                    compat_native_missing=list(native_missing),
                )
                diagnostics.log(
                    "win10_read_success",
                    field_count=len(fields),
                    compat_native_recovered=native_recovered,
                    compat_native_missing=len(native_missing),
                )
                return panel, candidate, fields
        except Exception as exc:
            diagnostics.log_traceback("win10_read_failure", exc)
            raise RuntimeError(
                f"{exc}；完整诊断日志：{diagnostics.latest_path}"
            ) from exc
        finally:
            diagnostics.log(
                "shared_state_final",
                shared_native_handlers=len(self._native_handlers),
                shared_owner_cache=len(self._unit_owner_index),
                shared_component_cache=(
                    len(self._component_index_cache)
                    if self._component_index_cache is not None
                    else None
                ),
            )
            diagnostics.close()

    def read_unit_fields_by_identity(
        self,
        handle: int,
        owner: int,
        unit: int,
    ) -> tuple[VisibleUnitPanel, UnitCandidate, list[UnitMemoryField]]:
        with ProcessMemory(self.pid) as pm:
            candidate = self._candidate_from_identity(
                pm,
                handle,
                owner,
                unit,
                f"manual_candidate handle=0x{handle:x} owner=0x{owner:x} unit=0x{unit:x}",
                850,
            )
            if candidate is None:
                raise RuntimeError("候选单位已经失效，请重新读取候选列表")
            candidate = self._candidate_with_selected_unit_type_id(pm, candidate)
            panel = self._panel_from_candidate(pm, candidate)
            return panel, candidate, self._unit_fields_from_candidate(pm, candidate)

    def read_unit_fields_by_identity_win10(
        self,
        handle: int,
        owner: int,
        unit: int,
    ) -> tuple[VisibleUnitPanel, UnitCandidate, list[UnitMemoryField]]:
        with self._win10_memory_operation("read_unit_fields_by_identity") as (diagnostics, pm):
            isolated = self._win10_session_for_identity(handle, owner, unit)
            candidate = self._win10_candidate_from_identity(
                isolated,
                pm,
                handle,
                owner,
                unit,
            )
            candidate = isolated._candidate_with_selected_unit_type_id(pm, candidate)
            panel = isolated._panel_from_candidate(pm, candidate)
            fields = isolated._unit_fields_from_candidate(pm, candidate)
            fields = isolated._replace_win10_intelligence_field(
                pm,
                candidate,
                fields,
                diagnostics,
            )
            diagnostics.log(
                "win10_identity_read",
                handle=f"0x{handle:x}",
                owner=f"0x{owner:x}",
                unit=f"0x{unit:x}",
                field_count=len(fields),
            )
            return panel, candidate, fields

    def _skill_index_from_field_key(self, key: str) -> int | None:
        if not key.startswith("skill") or not key.endswith("_name"):
            return None
        slot_text = key[len("skill") : -len("_name")]
        if not slot_text.isdigit():
            return None
        index = int(slot_text) - 1
        if not 0 <= index < self.HERO_SKILL_SLOT_COUNT:
            return None
        return index

    def _map_hero_skill_instances(
        self,
        configs: list[int],
        ability_instances: list[AbilityInstance],
    ) -> dict[int, AbilityInstance]:
        ordered_instances = sorted(
            ability_instances,
            key=lambda instance: (instance.handle, instance.wrapper_address),
        )
        skill_candidates = [
            instance
            for instance in ordered_instances
            if ((instance.rawcode >> 24) & 0xFF) != ord("B")
            and ((instance.class_rawcode >> 24) & 0xFF) != ord("B")
        ]
        mapped: dict[int, AbilityInstance] = {}
        used_wrappers: set[int] = set()
        for index, rawcode in enumerate(configs):
            if not rawcode:
                continue
            for instance in skill_candidates:
                if instance.wrapper_address in used_wrappers:
                    continue
                if instance.rawcode != rawcode:
                    continue
                mapped[index] = instance
                used_wrappers.add(instance.wrapper_address)
                break

        missing_indices = [
            index
            for index, rawcode in enumerate(configs)
            if rawcode and index not in mapped
        ]
        if not missing_indices:
            return mapped

        nonzero_indices = [
            index
            for index, rawcode in enumerate(configs)
            if rawcode
        ]
        nonzero_config_count = sum(1 for rawcode in configs if rawcode)
        candidate_position_by_wrapper = {
            instance.wrapper_address: position
            for position, instance in enumerate(skill_candidates)
        }
        rank_by_index = {
            index: rank
            for rank, index in enumerate(nonzero_indices)
        }
        start_positions = {
            candidate_position_by_wrapper[instance.wrapper_address] - rank_by_index[index]
            for index, instance in mapped.items()
            if instance.wrapper_address in candidate_position_by_wrapper
        }
        if len(start_positions) == 1:
            start = next(iter(start_positions))
            end = start + nonzero_config_count
            if 0 <= start and end <= len(skill_candidates):
                window = skill_candidates[start:end]
                anchors_match = all(
                    mapped[index].wrapper_address == window[rank_by_index[index]].wrapper_address
                    for index in mapped
                    if index in rank_by_index
                )
                if anchors_match:
                    for index in missing_indices:
                        instance = window[rank_by_index[index]]
                        if instance.wrapper_address not in used_wrappers:
                            mapped[index] = instance
                            used_wrappers.add(instance.wrapper_address)
                    return mapped

        remaining_instances = [
            instance
            for instance in skill_candidates
            if instance.wrapper_address not in used_wrappers
        ]
        if len(skill_candidates) != nonzero_config_count:
            return mapped
        if len(remaining_instances) != len(missing_indices):
            return mapped

        for index, instance in zip(missing_indices, remaining_instances):
            mapped[index] = instance
        return mapped

    def _hero_skill_instance_map(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        hero_data: int,
    ) -> tuple[list[int], dict[int, AbilityInstance], list[AbilityInstance]]:
        configs: list[int] = []
        for index in range(self.HERO_SKILL_SLOT_COUNT):
            try:
                configs.append(pm.read_u32(hero_data + 0x204 + index * 4))
            except OSError:
                configs.append(0)
        ability_instances = self._ability_instances_from_candidate(
            pm,
            candidate,
            allow_global_scan=True,
        )
        mapped = self._map_hero_skill_instances(configs, ability_instances)
        return configs, mapped, ability_instances

    def _hero_skill_instance_map_for_write(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        configs: list[int],
    ) -> tuple[dict[int, AbilityInstance], list[AbilityInstance]]:
        mapped: dict[int, AbilityInstance] = {}
        instances: list[AbilityInstance] = []
        seen_data: set[int] = set()
        for index, rawcode in enumerate(configs):
            if not rawcode:
                continue
            data_address = self._find_engine_ability_data(pm, candidate, rawcode)
            if not data_address or data_address in seen_data:
                continue
            seen_data.add(data_address)
            instance = self._ability_instance_from_data_for_candidate(
                pm,
                candidate,
                data_address,
                rawcode,
            )
            if instance is None:
                continue
            instance = replace(instance, slot=index + 1)
            mapped[index] = instance
            instances.append(instance)
        return mapped, instances

    def _ability_runtime_template_from_instance(
        self,
        pm: ProcessMemory,
        instance: AbilityInstance,
    ) -> dict[str, object]:
        return {
            "class_rawcode": instance.class_rawcode,
            "fields": {
                offset: pm.read(instance.data_address + offset, 8)
                for offset in self.ABILITY_RUNTIME_TEMPLATE_QWORD_OFFSETS
            },
        }

    def _write_ability_runtime_template(
        self,
        pm: ProcessMemory,
        instance: AbilityInstance,
        rawcode: int,
        template: dict[str, object],
    ) -> int:
        class_rawcode = int(template.get("class_rawcode", rawcode)) & 0xFFFFFFFF
        fields = template.get("fields")
        if not isinstance(fields, dict):
            raise RuntimeError("技能运行时模板缺少字段快照")
        for offset in self.ABILITY_RUNTIME_TEMPLATE_QWORD_OFFSETS:
            data = fields.get(offset)
            if not isinstance(data, (bytes, bytearray)) or len(data) != 8:
                raise RuntimeError(f"技能运行时模板字段 0x{offset:x} 无效")
            pm.write_bytes(instance.data_address + offset, bytes(data))
        pm.write_u32(instance.rawcode_address, rawcode)
        if instance.mirror_rawcode_address:
            pm.write_u32(instance.mirror_rawcode_address, rawcode)
        old_tag = pm.read_u64(instance.wrapper_tag_address)
        pm.write_bytes(
            instance.wrapper_tag_address,
            struct.pack("<Q", ((class_rawcode & 0xFFFFFFFF) << 32) | (old_tag & 0xFFFFFFFF)),
        )
        return class_rawcode

    def _ability_template_source_is_live(
        self,
        pm: ProcessMemory,
        owner: int,
        unit: int,
    ) -> bool:
        if not self._sane_heap_ptr(owner) or not self._sane_heap_ptr(unit):
            return False
        source = self._candidate_from_owner(pm, owner, 0, "ability_template_source")
        if source is None or source.unit_address != unit:
            return False
        try:
            current_hp = pm.read_f32(source.hp_current_address)
            max_hp = pm.read_f32(source.hp_max_address)
        except OSError:
            return False
        return self._valid_current_limit(current_hp, max_hp) and current_hp > 0.0 and max_hp > 0.0

    def _ability_template_source_candidate(
        self,
        pm: ProcessMemory,
        owner: int,
        unit: int,
    ) -> UnitCandidate | None:
        if not self._sane_heap_ptr(owner) or not self._sane_heap_ptr(unit):
            return None
        source = self._candidate_from_owner(pm, owner, 0, "ability_template_source")
        if source is None or source.unit_address != unit:
            return None
        try:
            current_hp = pm.read_f32(source.hp_current_address)
            max_hp = pm.read_f32(source.hp_max_address)
        except OSError:
            return None
        if not (self._valid_current_limit(current_hp, max_hp) and current_hp > 0.0 and max_hp > 0.0):
            return None
        return source

    def _find_ability_runtime_template(
        self,
        pm: ProcessMemory,
        rawcode: int,
        *,
        excluded_wrappers: set[int] | None = None,
        excluded_data: set[int] | None = None,
    ) -> AbilityInstance | None:
        excluded_wrappers = excluded_wrappers or set()
        excluded_data = excluded_data or set()
        component_rawcodes = {tag >> 32 for tag in self.COMPONENT_TAGS.values()}
        seen_data: set[int] = set()
        seen_wrappers: set[int] = set()
        rawcode_pattern = struct.pack("<I", rawcode & 0xFFFFFFFF)
        for rawcode_address in pm.scan_bytes_private(rawcode_pattern, max_region_size=8 * 1024 * 1024):
            data = rawcode_address - 0x70
            if data in seen_data or data in excluded_data:
                continue
            seen_data.add(data)
            try:
                data_vtable = pm.read_u64(data)
                unit = pm.read_u64(data + 0x68)
                data_rawcode = pm.read_u32(data + 0x70)
                mirror_rawcode = pm.read_u32(data + 0x78)
                data_cache_pointer = pm.read_u64(data + 0xA0)
            except OSError:
                continue
            if data_rawcode != rawcode or mirror_rawcode != rawcode:
                continue
            if not self._looks_like_vtable(data_vtable) or not self._sane_heap_ptr(unit):
                continue
            for data_ref in pm.scan_bytes_private(struct.pack("<Q", data), max_region_size=8 * 1024 * 1024):
                wrapper = data_ref - 0x90
                if wrapper in seen_wrappers or wrapper in excluded_wrappers:
                    continue
                seen_wrappers.add(wrapper)
                try:
                    wrapper_vtable = pm.read_u64(wrapper)
                    tag = pm.read_u64(wrapper + 0x18)
                    owner = pm.read_u64(wrapper + 0x50)
                    wrapper_data = pm.read_u64(wrapper + 0x90)
                    handle = pm.read_u64(wrapper + 0x20)
                except OSError:
                    continue
                if wrapper_data != data:
                    continue
                if not self._looks_like_vtable(wrapper_vtable) or not self._sane_heap_ptr(owner):
                    continue
                source_candidate = self._ability_template_source_candidate(pm, owner, unit)
                if source_candidate is None:
                    continue
                if self._find_engine_ability_data(pm, source_candidate, rawcode) != data:
                    continue
                class_rawcode = (tag >> 32) & 0xFFFFFFFF
                if class_rawcode in component_rawcodes or not self._looks_like_rawcode(class_rawcode):
                    continue
                return AbilityInstance(
                    slot=0,
                    wrapper_address=wrapper,
                    data_address=data,
                    wrapper_vtable=wrapper_vtable,
                    data_vtable=data_vtable,
                    wrapper_tag_address=wrapper + 0x18,
                    wrapper_tag=tag,
                    handle=handle,
                    class_rawcode=class_rawcode,
                    rawcode=rawcode,
                    rawcode_address=data + 0x70,
                    mirror_rawcode_address=data + 0x78,
                    data_cache_address=data + 0xA0,
                    data_cache_pointer=data_cache_pointer if self._sane_heap_ptr(data_cache_pointer) else 0,
                )
        return None

    def _write_hero_skill_name_field(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        field: UnitMemoryField,
        value: int | float | str,
    ) -> UnitMemoryField:
        index = self._skill_index_from_field_key(field.key)
        if index is None:
            raise RuntimeError(f"不是英雄技能名称字段：{field.key}")
        new_rawcode = int(self._coerce_memory_value("rawcode", value)) & 0xFFFFFFFF
        if not self._looks_like_rawcode(new_rawcode):
            raise ValueError(f"技能 rawcode 无效：{format_rawcode(new_rawcode)}")
        components = self._selected_components(pm, candidate.owner_address)
        hero = components.get("hero")
        if hero is None:
            raise RuntimeError("当前选中单位没有英雄组件，不能写入英雄技能")
        _hero_wrapper, hero_data = hero
        config_address = hero_data + 0x204 + index * 4
        cache_address = hero_data + 0x1BC + index * 4
        configs: list[int] = []
        for slot_index in range(self.HERO_SKILL_SLOT_COUNT):
            try:
                configs.append(pm.read_u32(hero_data + 0x204 + slot_index * 4))
            except OSError:
                configs.append(0)
        old_rawcode = configs[index] if index < len(configs) else 0
        instance = None
        if old_rawcode:
            data_address = self._find_engine_ability_data(pm, candidate, old_rawcode)
            if data_address:
                instance = self._ability_instance_from_data_for_candidate(
                    pm,
                    candidate,
                    data_address,
                    old_rawcode,
                )
                if instance is not None:
                    instance = replace(instance, slot=index + 1)
        ability_instances = [instance] if instance is not None else []
        runtime_needs_update = instance is not None and instance.rawcode != new_rawcode
        needs_runtime_replacement = old_rawcode != new_rawcode or runtime_needs_update
        if needs_runtime_replacement:
            if not old_rawcode:
                raise RuntimeError(
                    f"技能{index + 1}当前没有已学技能 rawcode，"
                    "没有可替换的运行时 ability 实例；为避免命令卡空格，本次不写入。"
                )
            source_ability_rawcode = instance.rawcode if instance is not None else old_rawcode
            source_skill_slots = [
                other_index + 1
                for other_index, rawcode in enumerate(configs)
                if rawcode == old_rawcode
            ]
            active_source_data = self._find_engine_ability_data(
                pm,
                candidate,
                source_ability_rawcode,
            )
            source_ability_slots = [
                other.slot
                for other in ability_instances
                if other.rawcode == source_ability_rawcode
                and (
                    (instance is not None and other.wrapper_address == instance.wrapper_address)
                    or (active_source_data and other.data_address == active_source_data)
                )
            ]
            if len(source_skill_slots) != 1 or len(source_ability_slots) != 1 or instance is None:
                details: list[str] = []
                if source_skill_slots:
                    details.append("技能栏" + ",".join(str(slot) for slot in source_skill_slots))
                if source_ability_slots:
                    details.append("能力实例" + ",".join(str(slot) for slot in source_ability_slots))
                raise RuntimeError(
                    f"技能{index + 1}当前 {format_rawcode(old_rawcode)} "
                    + ("同时出现在" + "；".join(details) if details else "没有匹配的运行时实例")
                    + "，无法唯一定位要替换的 ability 实例；为避免写错实例导致命令卡空格，本次不写入。"
                )
            duplicate_skill_slots = [
                other_index + 1
                for other_index, rawcode in enumerate(configs)
                if other_index != index and rawcode == new_rawcode
            ]
            duplicate_ability_slots = [
                other
                for other in ability_instances
                if (instance is None or other.wrapper_address != instance.wrapper_address)
                and other.rawcode == new_rawcode
            ]
            active_duplicate_data = self._find_engine_ability_data(pm, candidate, new_rawcode)
            duplicate_ability_slots = [
                other.slot
                for other in duplicate_ability_slots
                if active_duplicate_data and other.data_address == active_duplicate_data
            ]
            hidden_duplicate = (
                active_duplicate_data
                and not duplicate_ability_slots
                and (instance is None or active_duplicate_data != instance.data_address)
            )
            if duplicate_skill_slots or duplicate_ability_slots or hidden_duplicate:
                details: list[str] = []
                if duplicate_skill_slots:
                    details.append(
                        "技能栏" + ",".join(str(slot) for slot in duplicate_skill_slots)
                    )
                if duplicate_ability_slots:
                    details.append(
                        "能力实例" + ",".join(str(slot) for slot in duplicate_ability_slots)
                    )
                if hidden_duplicate:
                    details.append(f"隐藏运行时实例0x{active_duplicate_data:x}")
                raise RuntimeError(
                    f"{format_rawcode(new_rawcode)} 已存在于当前单位的" + "；".join(details) + "。"
                    "Warcraft III 的同 rawcode 已学技能不会生成第二个命令卡按钮，"
                    "强写会表现为目标格技能消失；请先把已有同名技能改成其它 rawcode。"
                )
        replacement_instance: AbilityInstance | None = None
        replacement_source = ""
        if instance is not None and needs_runtime_replacement:
            replacement_instance = self._replace_engine_ability_instance(
                pm,
                candidate,
                instance,
                new_rawcode,
            )
            replacement_source = (
                f"engine-replaced old_wrapper=0x{instance.wrapper_address:x} "
                f"new_wrapper=0x{replacement_instance.wrapper_address:x}"
            )

        pm.write_u32(config_address, new_rawcode)
        pm.write_u32(cache_address, new_rawcode)
        actions = [
            f"config/cache {format_rawcode(old_rawcode)}->{format_rawcode(new_rawcode)}",
        ]
        final_runtime_instance = replacement_instance or instance
        if instance is not None:
            if replacement_instance is not None:
                actions.append(
                    f"runtime {replacement_source} "
                    f"{instance.rawcode_text}->{format_rawcode(new_rawcode)} "
                    f"class={format_rawcode(replacement_instance.class_rawcode)}"
                )
            else:
                old_tag = pm.read_u64(instance.wrapper_tag_address)
                new_tag = ((new_rawcode & 0xFFFFFFFF) << 32) | (old_tag & 0xFFFFFFFF)
                pm.write_bytes(instance.wrapper_tag_address, struct.pack("<Q", new_tag))
                pm.write_u32(instance.rawcode_address, new_rawcode)
                if instance.mirror_rawcode_address:
                    pm.write_u32(instance.mirror_rawcode_address, new_rawcode)
                actions.append(
                    f"runtime wrapper=0x{instance.wrapper_address:x} "
                    f"{instance.rawcode_text}->{format_rawcode(new_rawcode)}"
                )
        else:
            actions.append("未找到已学 ability 实例，仅更新英雄技能栏配置")

        time.sleep(0.05)
        final_config = pm.read_u32(config_address)
        final_cache = pm.read_u32(cache_address)
        if final_config != new_rawcode or final_cache != new_rawcode:
            raise RuntimeError(
                f"技能{index + 1}写入后读回 config={format_rawcode(final_config)} "
                f"cache={format_rawcode(final_cache)}，不是 {format_rawcode(new_rawcode)}"
            )
        if final_runtime_instance is not None:
            final_rawcode = pm.read_u32(final_runtime_instance.rawcode_address)
            if final_rawcode != new_rawcode:
                raise RuntimeError(
                    f"技能{index + 1}运行时实例读回 {format_rawcode(final_rawcode)}，"
                    f"不是 {format_rawcode(new_rawcode)}"
                )

        if self._refresh_selected_hero_command_card():
            actions.append("已触发英雄选择刷新")
        else:
            actions.append("写入成功；如游戏命令卡未立即刷新，请重新选择该英雄")
        return UnitMemoryField(
            key=field.key,
            label=field.label,
            value_type="rawcode",
            value=final_config,
            address=config_address,
            category=field.category,
            write_address=config_address,
            write_type="rawcode",
            note="；".join(actions),
            extra_writes=((cache_address, "rawcode"),),
        )

    def _inventory_slot_index_from_field_key(self, key: str) -> int | None:
        prefix = "inventory_slot_"
        if not key.startswith(prefix) or key.endswith("_charges"):
            return None
        slot_text = key[len(prefix) :]
        if not slot_text.isdigit():
            return None
        index = int(slot_text) - 1
        if not 0 <= index < 6:
            return None
        return index

    def _inventory_slot_charges_index_from_field_key(self, key: str) -> int | None:
        prefix = "inventory_slot_"
        suffix = "_charges"
        if not key.startswith(prefix) or not key.endswith(suffix):
            return None
        slot_text = key[len(prefix) : -len(suffix)]
        if not slot_text.isdigit():
            return None
        index = int(slot_text) - 1
        if not 0 <= index < 6:
            return None
        return index

    def _inventory_slot_snapshot(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        slot_index: int,
    ) -> InventoryItem | None:
        for item in self._inventory_items_from_candidate(pm, candidate):
            if item.slot == slot_index + 1:
                return item
        return None

    def _write_inventory_slot_field(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        field: UnitMemoryField,
        value: int | float | str,
    ) -> UnitMemoryField:
        slot_index = self._inventory_slot_index_from_field_key(field.key)
        if slot_index is None:
            raise RuntimeError(f"不是物品槽字段：{field.key}")
        new_rawcode = int(self._coerce_memory_value("rawcode", value)) & 0xFFFFFFFF
        if not self._looks_like_item_rawcode(new_rawcode):
            raise ValueError(f"物品 rawcode 无效：{format_rawcode(new_rawcode)}")

        components = self._selected_components(pm, candidate.owner_address)
        if "inventory" not in components:
            raise RuntimeError("当前选中单位没有物品栏组件")

        items = self._inventory_items_from_candidate(pm, candidate, components)
        old_snapshot = next((item for item in items if item.slot == slot_index + 1), None)
        before_by_slot = {item.slot: item.rawcode for item in items}
        old_rawcode = old_snapshot.rawcode if old_snapshot is not None else 0
        actions: list[str] = []
        if old_rawcode == new_rawcode:
            actions.append("物品 rawcode 未变化")
        else:
            removed_handle, added_item, native_rawcode = self._set_inventory_slot_item_via_native_handler(
                pm,
                candidate,
                slot_index,
                new_rawcode,
            )
            self._item_object_cache.clear()
            actions.append(
                f"内部物品栏替换 {format_rawcode(old_rawcode) if old_rawcode else '空'}"
                f"->{format_rawcode(native_rawcode)} removed=0x{removed_handle:x} "
                f"new_item=0x{added_item:x}"
            )
            actions.append("未交换其他物品槽")

        final_snapshot: InventoryItem | None = None
        after_items: list[InventoryItem] = []
        for attempt in range(6):
            time.sleep(0.03 if attempt == 0 else 0.08)
            self._item_object_cache.clear()
            after_items = self._inventory_items_from_candidate(pm, candidate, components)
            final_snapshot = next((item for item in after_items if item.slot == slot_index + 1), None)
            if final_snapshot is not None and final_snapshot.rawcode == new_rawcode:
                break
        after_by_slot = {item.slot: item.rawcode for item in after_items}
        changed_other_slots = [
            slot
            for slot, before_rawcode in before_by_slot.items()
            if slot != slot_index + 1 and after_by_slot.get(slot, before_rawcode) != before_rawcode
        ]
        if changed_other_slots:
            raise RuntimeError(
                "物品写入影响了非目标槽：" + ", ".join(str(slot) for slot in changed_other_slots)
            )
        final_rawcode = final_snapshot.rawcode if final_snapshot is not None else 0
        final_handle = final_snapshot.handle if final_snapshot is not None else 0
        if final_rawcode != new_rawcode:
            raise RuntimeError(
                f"物品槽{slot_index + 1}写入后读回 {format_rawcode(final_rawcode) if final_rawcode else '空'}，"
                f"不是 {format_rawcode(new_rawcode)}"
            )
        final_address = field.address
        if final_snapshot is not None and final_snapshot.rawcode_address:
            final_address = final_snapshot.rawcode_address
        if final_snapshot is not None:
            note = (
                f"handle=0x{final_snapshot.handle:x} item=0x{final_snapshot.item_address:x}; "
                f"mirror=0x{final_snapshot.mirror_rawcode_address:x} "
                f"ability={format_rawcode(final_snapshot.ability_rawcode) if final_snapshot.ability_rawcode else '0'}; "
                "通过内部物品栏函数创建/替换本槽 item，未交换其他物品槽"
            )
        else:
            note = field.note
            if final_handle:
                handle_note = f"handle=0x{final_handle:x}"
                note = (note + "；" if note else "") + handle_note
        if actions:
            note = (note + "；" if note else "") + "；".join(actions)
        return UnitMemoryField(
            key=field.key,
            label=field.label,
            value_type="rawcode",
            value=final_rawcode,
            address=final_address,
            category=field.category,
            write_address=field.write_address,
            write_type=field.write_type,
            write_base=field.write_base,
            note=note,
            extra_writes=field.extra_writes,
        )

    def _write_inventory_slot_charges_field(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        field: UnitMemoryField,
        value: int | float | str,
    ) -> UnitMemoryField:
        slot_index = self._inventory_slot_charges_index_from_field_key(field.key)
        if slot_index is None:
            raise RuntimeError(f"不是物品数量字段：{field.key}")
        new_charges = int(self._coerce_memory_value("i32", value))
        if new_charges < 0:
            new_charges = 0
        if new_charges > 999:
            raise ValueError("物品数量不能超过 999")

        components = self._selected_components(pm, candidate.owner_address)
        if "inventory" not in components:
            raise RuntimeError("当前选中单位没有物品栏组件")
        snapshot = next(
            (
                item
                for item in self._inventory_items_from_candidate(pm, candidate, components)
                if item.slot == slot_index + 1
            ),
            None,
        )
        if snapshot is None or not snapshot.item_address or not snapshot.charges_address:
            raise RuntimeError(f"物品槽{slot_index + 1}为空或未解析 item 对象，不能写数量")

        old_charges = snapshot.charges
        old_flags = pm.read_u32(snapshot.item_address + self.ITEM_CHARGES_FLAG_OFFSET)
        self._set_item_charges_via_native_handler(pm, candidate, snapshot, new_charges)
        time.sleep(0.05)

        final_snapshot = next(
            (
                item
                for item in self._inventory_items_from_candidate(pm, candidate, components)
                if item.slot == slot_index + 1
            ),
            None,
        )
        final_charges = final_snapshot.charges if final_snapshot is not None else -1
        if final_charges != new_charges:
            raise RuntimeError(
                f"物品槽{slot_index + 1}数量写入后读回 {final_charges}，不是 {new_charges}"
            )
        if final_snapshot is not None and final_snapshot.item_address:
            final_flags = pm.read_u32(final_snapshot.item_address + self.ITEM_CHARGES_FLAG_OFFSET)
        else:
            final_flags = old_flags
        refresh_note = ""
        if "hero" in components:
            if self._refresh_selected_hero_command_card():
                refresh_note = "; 已触发英雄选择刷新"
            else:
                refresh_note = "; 写入成功，如物品栏未立即刷新请重新选择该英雄"
        return UnitMemoryField(
            key=field.key,
            label=field.label,
            value_type=field.value_type,
            value=final_charges,
            address=field.address,
            category=field.category,
            write_address=field.write_address,
            write_type=field.write_type,
            write_base=field.write_base,
            note=(
                f"SetItemCharges {old_charges}->{final_charges}; "
                f"item charges offset=0x{self.ITEM_CHARGES_OFFSET:x}; "
                f"flags 0x{old_flags:x}->0x{final_flags:x}"
                f"{refresh_note}"
            ),
            extra_writes=field.extra_writes,
        )

    def _write_unit_fields_to_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        specs: Iterable[MemoryWriteSpec],
    ) -> list[UnitMemoryField]:
        specs = list(specs)
        if not specs:
            return []
        written: list[UnitMemoryField] = []
        remaining_specs: list[MemoryWriteSpec] = []
        for spec in specs:
            direct_key = self.FIELD_KEY_ALIASES.get(spec.label, spec.label)
            if self._skill_index_from_field_key(direct_key) is not None:
                field = UnitMemoryField(
                    key=direct_key,
                    label=direct_key,
                    value_type="rawcode",
                    value=0,
                    address=0,
                    category="技能",
                    write_address=1,
                    write_type="rawcode",
                )
                written.append(self._write_hero_skill_name_field(pm, candidate, field, spec.value))
            else:
                remaining_specs.append(spec)
        if not remaining_specs:
            return written
        fields = self._unit_fields_from_candidate(pm, candidate)
        by_key = {field.key: field for field in fields}
        by_label = {field.label: field for field in fields}
        for spec in remaining_specs:
            field = (
                by_key.get(spec.label)
                or by_key.get(self.FIELD_KEY_ALIASES.get(spec.label, ""))
                or by_label.get(spec.label)
            )
            if field is None:
                raise RuntimeError(f"当前选中单位没有字段：{spec.label}")
            if not field.writable:
                raise RuntimeError(f"字段不可写：{field.label}")
            if field.key == "intelligence_total":
                written.append(self._write_hero_intelligence_field(pm, candidate, field, spec.value))
                continue
            if self._skill_index_from_field_key(field.key) is not None:
                written.append(self._write_hero_skill_name_field(pm, candidate, field, spec.value))
                continue
            if self._inventory_slot_charges_index_from_field_key(field.key) is not None:
                written.append(self._write_inventory_slot_charges_field(pm, candidate, field, spec.value))
                continue
            if self._inventory_slot_index_from_field_key(field.key) is not None:
                written.append(self._write_inventory_slot_field(pm, candidate, field, spec.value))
                continue
            self._write_memory_value(pm, field.write_address, field.write_type, spec.value)
            for extra_address, extra_type in field.extra_writes:
                self._write_memory_value(pm, extra_address, extra_type, spec.value)
            new_value = self._read_memory_value(pm, field.address, field.value_type)
            written.append(
                UnitMemoryField(
                    key=field.key,
                    label=field.label,
                    value_type=field.value_type,
                    value=new_value,
                    address=field.address,
                    category=field.category,
                    write_address=field.write_address,
                    write_type=field.write_type,
                    write_base=field.write_base,
                    note=field.note,
                    extra_writes=field.extra_writes,
                )
            )
        return written

    def write_selected_unit_fields(self, specs: Iterable[MemoryWriteSpec]) -> list[UnitMemoryField]:
        specs = list(specs)
        if not specs:
            return []
        with ProcessMemory(self.pid, write=True) as pm:
            candidate = self.locate_selected_unit_by_handle(pm, allow_deep_scan=True)
            return self._write_unit_fields_to_candidate(pm, candidate, specs)

    def write_selected_unit_field(self, key: str, value: int | float | str) -> UnitMemoryField:
        fields = self.write_selected_unit_fields([MemoryWriteSpec(key, 0, "", value)])
        return fields[0]

    def write_unit_field_by_identity(
        self,
        handle: int,
        owner: int,
        unit: int,
        key: str,
        value: int | float | str,
    ) -> UnitMemoryField:
        with ProcessMemory(self.pid, write=True) as pm:
            candidate = self._candidate_from_identity(
                pm,
                handle,
                owner,
                unit,
                f"manual_candidate handle=0x{handle:x} owner=0x{owner:x} unit=0x{unit:x}",
                850,
            )
            if candidate is None:
                raise RuntimeError("候选单位已经失效，请重新读取候选列表")
            return self._write_unit_fields_to_candidate(pm, candidate, [MemoryWriteSpec(key, 0, "", value)])[0]

    def write_unit_field_by_identity_win10(
        self,
        handle: int,
        owner: int,
        unit: int,
        key: str,
        value: int | float | str,
    ) -> UnitMemoryField:
        with self._win10_memory_operation(
            "write_unit_field_by_identity",
            write=True,
        ) as (diagnostics, pm):
            isolated = self._win10_session_for_identity(handle, owner, unit)
            candidate = self._win10_candidate_from_identity(
                isolated,
                pm,
                handle,
                owner,
                unit,
            )
            if key in {"int", "intelligence", "intelligence_total"}:
                if not {"SetHeroInt", "GetHeroInt"}.issubset(isolated._native_handlers):
                    isolated._recover_win10_native_handlers(isolated, pm, diagnostics)
                fields = isolated._unit_fields_from_candidate(pm, candidate)
                field = next(
                    (item for item in fields if item.key == "intelligence_total"),
                    None,
                )
                if field is None:
                    raise RuntimeError("当前备用读取单位没有可写的智力字段")
                field = isolated._write_hero_intelligence_field_win10(
                    pm,
                    candidate,
                    field,
                    value,
                    diagnostics,
                )
            else:
                field = isolated._write_unit_fields_to_candidate(
                    pm,
                    candidate,
                    [MemoryWriteSpec(key, 0, "", value)],
                )[0]
            diagnostics.log(
                "win10_identity_write",
                handle=f"0x{handle:x}",
                owner=f"0x{owner:x}",
                unit=f"0x{unit:x}",
                key=key,
                value=field.value,
                address=f"0x{field.address:x}",
                write_address=f"0x{field.write_address:x}",
            )
            return field

    def locate_current_selected_unit(self) -> tuple[VisibleUnitPanel, UnitCandidate]:
        with ProcessMemory(self.pid) as pm:
            candidate = self.locate_selected_unit_by_handle(pm, allow_deep_scan=True)
            candidate = self._candidate_with_selected_unit_type_id(pm, candidate)
            return self._panel_from_candidate(pm, candidate), candidate

    def _write_basic_unit_values_to_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        target_hp: float | None,
        target_mp: float | None,
        max_hp: float | None = None,
        max_mp: float | None = None,
        target_x: float | None = None,
        target_y: float | None = None,
        target_hp_regen: float | None = None,
        target_mp_regen: float | None = None,
    ) -> None:
        if max_hp is not None or target_hp is not None:
            try:
                old_max_hp = pm.read_f32(candidate.hp_max_address)
            except OSError:
                old_max_hp = float(target_hp) if target_hp is not None else 0.0
            target_max_hp = float(max_hp) if max_hp is not None else old_max_hp
            if target_hp is not None and float(target_hp) > target_max_hp:
                target_max_hp = float(target_hp)
            if target_max_hp > 0:
                pm.write_f32(candidate.hp_max_address, target_max_hp)
            if target_hp is not None:
                pm.write_f32(candidate.hp_current_address, float(target_hp))
        if max_mp is not None or target_mp is not None:
            if not candidate.mp_current_address or not candidate.mp_max_address:
                raise RuntimeError("当前单位没有可写的魔法属性")
            try:
                old_max_mp = pm.read_f32(candidate.mp_max_address)
            except OSError:
                old_max_mp = float(target_mp) if target_mp is not None else 0.0
            target_max_mp = float(max_mp) if max_mp is not None else old_max_mp
            if target_mp is not None and float(target_mp) > target_max_mp:
                target_max_mp = float(target_mp)
            if target_max_mp >= 0:
                pm.write_f32(candidate.mp_max_address, target_max_mp)
            if target_mp is not None:
                pm.write_f32(candidate.mp_current_address, float(target_mp))
        if target_hp_regen is not None:
            if not candidate.hp_regen_address:
                raise RuntimeError("当前单位没有可写的 HP 回复率属性")
            pm.write_f32(candidate.hp_regen_address, float(target_hp_regen))
        if target_mp_regen is not None:
            if not candidate.mp_regen_address:
                raise RuntimeError("当前单位没有可写的 MP 回复率属性")
            pm.write_f32(candidate.mp_regen_address, float(target_mp_regen))
        if target_x is not None:
            if not candidate.x_address:
                raise RuntimeError("当前单位没有可写的 X 坐标属性")
            pm.write_f32(candidate.x_address, float(target_x))
        if target_y is not None:
            if not candidate.y_address:
                raise RuntimeError("当前单位没有可写的 Y 坐标属性")
            pm.write_f32(candidate.y_address, float(target_y))

    def set_selected_unit(
        self,
        current_hp: float,
        current_mp: float | None,
        target_hp: float | None,
        target_mp: float | None,
        max_hp: float | None = None,
        max_mp: float | None = None,
        target_x: float | None = None,
        target_y: float | None = None,
        target_hp_regen: float | None = None,
        target_mp_regen: float | None = None,
    ) -> UnitCandidate:
        with ProcessMemory(self.pid, write=True) as pm:
            candidate = self.locate_selected_unit_by_handle(pm, allow_deep_scan=True)
            self._write_basic_unit_values_to_candidate(
                pm,
                candidate,
                target_hp,
                target_mp,
                max_hp,
                max_mp,
                target_x,
                target_y,
                target_hp_regen,
                target_mp_regen,
            )
        return candidate

    def set_unit_by_identity(
        self,
        handle: int,
        owner: int,
        unit: int,
        current_hp: float,
        current_mp: float | None,
        target_hp: float | None,
        target_mp: float | None,
        max_hp: float | None = None,
        max_mp: float | None = None,
        target_x: float | None = None,
        target_y: float | None = None,
        target_hp_regen: float | None = None,
        target_mp_regen: float | None = None,
    ) -> UnitCandidate:
        with ProcessMemory(self.pid, write=True) as pm:
            candidate = self._candidate_from_identity(
                pm,
                handle,
                owner,
                unit,
                f"manual_candidate handle=0x{handle:x} owner=0x{owner:x} unit=0x{unit:x}",
                850,
            )
            if candidate is None:
                raise RuntimeError("候选单位已经失效，请重新读取候选列表")
            self._write_basic_unit_values_to_candidate(
                pm,
                candidate,
                target_hp,
                target_mp,
                max_hp,
                max_mp,
                target_x,
                target_y,
                target_hp_regen,
                target_mp_regen,
            )
            return candidate

    def set_unit_by_identity_win10(
        self,
        handle: int,
        owner: int,
        unit: int,
        current_hp: float,
        current_mp: float | None,
        target_hp: float | None,
        target_mp: float | None,
        max_hp: float | None = None,
        max_mp: float | None = None,
        target_x: float | None = None,
        target_y: float | None = None,
        target_hp_regen: float | None = None,
        target_mp_regen: float | None = None,
    ) -> UnitCandidate:
        with self._win10_memory_operation(
            "set_unit_by_identity",
            write=True,
        ) as (diagnostics, pm):
            isolated = self._win10_session_for_identity(handle, owner, unit)
            candidate = self._win10_candidate_from_identity(
                isolated,
                pm,
                handle,
                owner,
                unit,
            )
            isolated._write_basic_unit_values_to_candidate(
                pm,
                candidate,
                target_hp,
                target_mp,
                max_hp,
                max_mp,
                target_x,
                target_y,
                target_hp_regen,
                target_mp_regen,
            )
            diagnostics.log(
                "win10_identity_basic_write",
                handle=f"0x{handle:x}",
                owner=f"0x{owner:x}",
                unit=f"0x{unit:x}",
                target_hp=target_hp,
                target_mp=target_mp,
                max_hp=max_hp,
                max_mp=max_mp,
                target_x=target_x,
                target_y=target_y,
                target_hp_regen=target_hp_regen,
                target_mp_regen=target_mp_regen,
            )
            return candidate


def close_float(a: float, b: float, tolerance: float = 0.01) -> bool:
    return math.isfinite(a) and abs(a - b) <= tolerance


def parse_int(text: str, name: str) -> int:
    try:
        return int(str(text).strip())
    except ValueError as exc:
        raise ValueError(f"{name} 必须是整数") from exc


def parse_float(text: str, name: str) -> float:
    try:
        return float(str(text).strip())
    except ValueError as exc:
        raise ValueError(f"{name} 必须是数字") from exc


def parse_unit_identity(text: str) -> tuple[int, int, int]:
    raw_parts = [part.strip() for part in text.replace(";", ",").split(",") if part.strip()]
    values: dict[str, int] = {}
    positional: list[int] = []
    for part in raw_parts:
        if "=" in part:
            key, value = part.split("=", 1)
            key = key.strip().lower()
            if key in {"h", "handle"}:
                key = "handle"
            elif key in {"o", "owner"}:
                key = "owner"
            elif key in {"u", "unit"}:
                key = "unit"
            else:
                raise ValueError(f"未知单位身份字段：{key}")
            values[key] = int(value.strip(), 0)
        else:
            positional.append(int(part, 0))
    if positional:
        if len(positional) != 3:
            raise ValueError("--unit-identity 位置格式应为 HANDLE,OWNER,UNIT")
        values.setdefault("handle", positional[0])
        values.setdefault("owner", positional[1])
        values.setdefault("unit", positional[2])
    missing = [key for key in ("handle", "owner", "unit") if key not in values]
    if missing:
        raise ValueError("--unit-identity 缺少：" + ",".join(missing))
    return values["handle"], values["owner"], values["unit"]


def run_gui() -> None:
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    root.title(f"魔兽争霸3重制版修改器 v{APP_VERSION}")
    root.geometry("1180x780")
    root.minsize(1040, 700)
    icon_path = (
        Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        / "assets"
        / "app_icon.png"
    )
    try:
        app_icon = tk.PhotoImage(file=str(icon_path))
        root.iconphoto(True, app_icon)
    except tk.TclError:
        app_icon = None

    status = tk.StringVar(value="正在连接 Warcraft III...")
    pid_var = tk.StringVar(value="")
    gold_current = tk.StringVar(value="")
    lumber_current = tk.StringVar(value="")
    food_current = tk.StringVar(value="")
    food_cap_current = tk.StringVar(value="")
    gold_target = tk.StringVar(value="")
    lumber_target = tk.StringVar(value="")
    food_used_target = tk.StringVar(value="")
    food_cap_target = tk.StringVar(value="")
    resource_delta = tk.StringVar(value="1000")
    hp_current = tk.StringVar(value="")
    hp_max_current = tk.StringVar(value="")
    hp_regen_current = tk.StringVar(value="")
    mp_current = tk.StringVar(value="")
    mp_max_current = tk.StringVar(value="")
    mp_regen_current = tk.StringVar(value="")
    hp_target = tk.StringVar(value="")
    mp_target = tk.StringVar(value="")
    hp_regen_target = tk.StringVar(value="")
    mp_regen_target = tk.StringVar(value="")
    x_current = tk.StringVar(value="")
    y_current = tk.StringVar(value="")
    unit_type_id_current = tk.StringVar(value="")
    x_target = tk.StringVar(value="")
    y_target = tk.StringVar(value="")
    unit_field_target = tk.StringVar(value="")
    elephant_hero_level = tk.StringVar(value="1")
    elephant_unit_scale = tk.StringVar(value="1.0")
    elephant_unit_rawcode = tk.StringVar(value="")
    elephant_item_rawcode = tk.StringVar(value="ckng")
    elephant_ability_rawcode = tk.StringVar(value="AOsh")
    elephant_ability_level = tk.StringVar(value="1")
    ability_field_rawcode = tk.StringVar(value="AHhb")
    ability_field_level = tk.StringVar(value="1")
    ability_field_filter = tk.StringVar(value="")
    ability_field_value = tk.StringVar(value="")
    ability_field_summary = tk.StringVar(value="尚未读取技能字段")
    ability_field_detail = tk.StringVar(value="")
    ability_field_show_zero = tk.BooleanVar(value=True)
    ability_field_show_unsupported = tk.BooleanVar(value=True)
    elephant_tech_rawcode = tk.StringVar(value="")
    elephant_tech_level = tk.StringVar(value="1")
    elephant_xp_rate = tk.StringVar(value="1.0")
    elephant_item_charges = tk.StringVar(value="999")
    elephant_resource_amount = tk.StringVar(value="100000")
    elephant_mass_clone_count = tk.StringVar(value="10")
    elephant_hero_attributes = tk.StringVar(value="20000")
    elephant_skill_points = tk.StringVar(value="1")
    elephant_reinforcement_rawcode = tk.StringVar(value="hcth")
    elephant_preset_item_rawcode = tk.StringVar(value="amrc")
    elephant_preset_tech_rawcode = tk.StringVar(value="Rost")
    elephant_reset_ability_rawcode = tk.StringVar(value="Apxf")
    elephant_auto_effect_count = tk.StringVar(value="5")
    elephant_hotkeys_enabled = tk.BooleanVar(value=False)
    elephant_hotkey_status = tk.StringVar(value="快捷键未启用")
    elephant_hotkey_checks = {
        spec.name: tk.BooleanVar(value=True)
        for spec in ELEPHANT_HOTKEY_SPECS
    }
    hotkey_manager = GlobalHotkeyManager()
    operation_lock = threading.RLock()
    operation_threads_lock = threading.Lock()
    operation_threads: set[threading.Thread] = set()

    state: dict[str, object] = {
        "trainer": None,
        "resource_caches": {},
        "resource_labels": {},
        "selected_resource_iid": "",
        "local_resource_iid": "",
        "unit_fields": {},
        "selected_unit_identity": None,
        "selected_unit_win10": False,
        "last_verified_unit_identity": None,
        "selection_candidates": {},
        "manual_unit_identity": None,
        "locks": {},
        "lock_busy": False,
        "active_operations": set(),
        "elephant_game_paused": False,
        "ability_field_snapshot": None,
        "ability_field_rows": {},
        "closing": False,
    }

    def start_operation_thread(target: Callable[[], None], name: str) -> None:
        def tracked_target() -> None:
            try:
                target()
            finally:
                with operation_threads_lock:
                    operation_threads.discard(threading.current_thread())

        thread = threading.Thread(target=tracked_target, name=name, daemon=False)
        with operation_threads_lock:
            operation_threads.add(thread)
        try:
            thread.start()
        except Exception:
            with operation_threads_lock:
                operation_threads.discard(thread)
            raise

    def active_operation_threads() -> tuple[threading.Thread, ...]:
        with operation_threads_lock:
            return tuple(thread for thread in operation_threads if thread.is_alive())

    def close_gui() -> None:
        if state.get("closing"):
            return
        state["closing"] = True
        hotkey_manager.stop()
        set_status("正在等待后台操作安全结束...")

        def finish_close() -> None:
            if active_operation_threads() or state.get("lock_busy"):
                root.after(100, finish_close)
                return
            root.destroy()

        finish_close()

    root.protocol("WM_DELETE_WINDOW", close_gui)

    def set_status(text: str) -> None:
        status.set(text)

    def call_async(
        fn: Callable[[], str | None],
        operation_key: str = "",
        busy_widget: ttk.Button | None = None,
        busy_text: str = "正在执行，请稍候...",
    ) -> None:
        if state.get("closing"):
            return
        active_operations = state.get("active_operations")
        assert isinstance(active_operations, set)
        if operation_key and operation_key in active_operations:
            return
        if operation_key:
            active_operations.add(operation_key)
        if busy_widget is not None:
            busy_widget.state(["disabled"])
        set_status(busy_text)

        def finish(result: str | None, exc: Exception | None) -> None:
            if operation_key:
                active_operations.discard(operation_key)
            if state.get("closing"):
                return
            if busy_widget is not None:
                busy_widget.state(["!disabled"])
            if exc is not None:
                messagebox.showerror("错误", str(exc))
                set_status(f"失败：{exc}")
            elif result:
                set_status(result)
            else:
                set_status("已完成")

        def worker() -> None:
            try:
                with operation_lock:
                    result = fn()
            except Exception as exc:
                root.after(0, finish, None, exc)
            else:
                root.after(0, finish, result, None)

        thread_name = f"war3-operation-{operation_key or 'anonymous'}"
        start_operation_thread(worker, thread_name)

    def trainer() -> War3Trainer:
        obj = state.get("trainer")
        if obj is None:
            obj = War3Trainer()
            state["trainer"] = obj
        else:
            assert isinstance(obj, War3Trainer)
            obj.refresh_window(allow_pid_change=True)
        root.after(0, pid_var.set, str(obj.pid))
        return obj

    def connect() -> str:
        state["trainer"] = War3Trainer()
        root.after(0, pid_var.set, str(state["trainer"].pid))
        return f"已连接 Warcraft III，PID {state['trainer'].pid}"

    def resource_iid(cache: ResourceCache) -> str:
        return f"{cache.gold_address:x}:{cache.lumber_address:x}"

    def resource_row_values(index: int, cache: ResourceCache) -> tuple[str, str, str, str, str, str, str]:
        food_text = f"{cache.food_used}/{cache.food_cap}" if cache.food_used_address or cache.food_cap_address else ""
        player_text = f"{index}"
        if cache.player_value or cache.header_value:
            player_text = f"{index} (h{cache.header_value}/p{cache.player_value})"
        return (
            player_text,
            str(cache.gold),
            str(cache.lumber),
            food_text,
            f"0x{cache.gold_address:x}",
            f"0x{cache.lumber_address:x}",
            cache.source,
        )

    def set_resource_entries(cache: ResourceCache, reset_targets: bool = True) -> None:
        gold_current.set(str(cache.gold))
        lumber_current.set(str(cache.lumber))
        food_current.set(str(cache.food_used) if cache.food_used_address else "")
        food_cap_current.set(str(cache.food_cap) if cache.food_cap_address else "")
        if reset_targets:
            gold_target.set(str(cache.gold))
            lumber_target.set(str(cache.lumber))
            food_used_target.set(str(cache.food_used) if cache.food_used_address else "")
            food_cap_target.set(str(cache.food_cap) if cache.food_cap_address else "")

    def populate_resource_caches(
        caches: list[ResourceCache],
        preferred_iid: str = "",
        local_iid: str = "",
    ) -> None:
        cache_map: dict[str, ResourceCache] = {}
        label_map: dict[str, str] = {}
        resource_tree.delete(*resource_tree.get_children())
        selected_iid = ""
        for index, cache in enumerate(caches, 1):
            iid = resource_iid(cache)
            cache_map[iid] = cache
            label_map[iid] = str(index)
            resource_tree.insert("", "end", iid=iid, values=resource_row_values(index, cache))
            if iid == preferred_iid:
                selected_iid = iid
        if not selected_iid and caches:
            selected_iid = resource_iid(caches[0])
        state["resource_caches"] = cache_map
        state["resource_labels"] = label_map
        state["selected_resource_iid"] = selected_iid
        state["local_resource_iid"] = local_iid
        if selected_iid:
            resource_tree.selection_set(selected_iid)
            resource_tree.focus(selected_iid)
            set_resource_entries(cache_map[selected_iid])

    def update_resource_cache_display(cache: ResourceCache) -> None:
        iid = resource_iid(cache)
        caches = state.get("resource_caches", {})
        labels = state.get("resource_labels", {})
        if not isinstance(caches, dict) or not isinstance(labels, dict):
            return
        caches[iid] = cache
        label = str(labels.get(iid, ""))
        index = int(label) if label.isdigit() else len(caches)
        if resource_tree.exists(iid):
            resource_tree.item(iid, values=resource_row_values(index, cache))
        state["selected_resource_iid"] = iid
        set_resource_entries(cache)

    def on_resource_select(_event=None) -> None:
        selection = resource_tree.selection()
        if not selection:
            return
        iid = str(selection[0])
        caches = state.get("resource_caches", {})
        if not isinstance(caches, dict):
            return
        cache = caches.get(iid)
        if not isinstance(cache, ResourceCache):
            return
        state["selected_resource_iid"] = iid
        set_resource_entries(cache)

    def selected_resource_cache() -> ResourceCache:
        caches = state.get("resource_caches", {})
        if not isinstance(caches, dict) or not caches:
            raise ValueError("请先点击“读取全部资源组”，并在表格里选择一个阵营/资源组")
        iid = str(state.get("selected_resource_iid", ""))
        cache = caches.get(iid)
        if not isinstance(cache, ResourceCache):
            raise ValueError("请先在资源组表格里选择要修改的阵营/资源组")
        return cache

    def selected_resource_label(cache: ResourceCache) -> str:
        labels = state.get("resource_labels", {})
        iid = resource_iid(cache)
        if isinstance(labels, dict) and iid in labels:
            return str(labels[iid])
        return f"0x{cache.gold_address:x}"

    def refresh_resources() -> str:
        t = trainer()
        caches = t.list_resource_caches()
        if not caches:
            cg = int(gold_current.get()) if gold_current.get().strip() else None
            cl = int(lumber_current.get()) if lumber_current.get().strip() else None
            cf = int(food_current.get()) if food_current.get().strip() else None
            cfc = int(food_cap_current.get()) if food_cap_current.get().strip() else None
            caches = [t.read_resource_cache(cg, cl, cf, cfc)]
        local_cache = t.locate_local_player_resource_cache(caches)
        local_iid = resource_iid(local_cache)
        caches = [cache for cache in caches if cache.owner_key != local_cache.owner_key]
        caches.append(local_cache)
        caches.sort(key=lambda cache: (cache.block_start_kind, cache.owner_key))
        root.after(0, populate_resource_caches, caches, local_iid, local_iid)
        return f"已读取 {len(caches)} 个资源组；已识别并选中本地玩家资源组"

    def set_resource(kind: str) -> str:
        t = trainer()
        cache = selected_resource_cache()
        label = selected_resource_label(cache)
        current = t.read_resource_cache_addresses(cache)
        if kind == "gold":
            target = parse_int(gold_target.get(), "目标金币")
            refreshed = t.write_resource_cache(current, target_gold=target)
            root.after(0, update_resource_cache_display, refreshed)
            return f"资源组 {label} 金币已写入：{current.gold} -> {refreshed.gold}"
        target = parse_int(lumber_target.get(), "目标木材")
        refreshed = t.write_resource_cache(current, target_lumber=target)
        root.after(0, update_resource_cache_display, refreshed)
        return f"资源组 {label} 木材已写入：{current.lumber} -> {refreshed.lumber}"

    def set_food_resource(kind: str) -> str:
        t = trainer()
        cache = selected_resource_cache()
        label = selected_resource_label(cache)
        current = t.read_resource_cache_addresses(cache)
        is_local_player = resource_iid(cache) == str(state.get("local_resource_iid", ""))
        if kind == "food_used":
            target = parse_int(food_used_target.get(), "目标当前人口")
            refreshed = t.write_resource_cache(
                current,
                target_food_used=target,
                sync_local_food_used=is_local_player,
            )
            message = f"当前人口已写入：{current.food_used} -> {refreshed.food_used}"
        elif kind == "food_cap":
            target = parse_int(food_cap_target.get(), "目标人口上限")
            refreshed = t.write_resource_cache(
                current,
                target_food_cap=target,
                sync_local_food_cap=is_local_player,
            )
            message = f"人口上限已写入：{current.food_cap} -> {refreshed.food_cap}"
        else:
            raise ValueError(f"未知人口字段：{kind}")
        root.after(0, update_resource_cache_display, refreshed)
        return f"资源组 {label} {message}；{refreshed.source}"

    def add_resource(kind: str) -> str:
        t = trainer()
        cache = selected_resource_cache()
        label = selected_resource_label(cache)
        amount = parse_int(resource_delta.get(), "增量")
        current = t.read_resource_cache_addresses(cache)
        if kind == "gold":
            refreshed = t.write_resource_cache(current, target_gold=current.gold + amount)
            root.after(0, update_resource_cache_display, refreshed)
            return f"资源组 {label} 金币已修改：{amount:+d} -> {refreshed.gold}"
        if kind == "lumber":
            refreshed = t.write_resource_cache(current, target_lumber=current.lumber + amount)
            root.after(0, update_resource_cache_display, refreshed)
            return f"资源组 {label} 木材已修改：{amount:+d} -> {refreshed.lumber}"
        refreshed = t.write_resource_cache(
            current,
            target_gold=current.gold + amount,
            target_lumber=current.lumber + amount,
        )
        root.after(0, update_resource_cache_display, refreshed)
        return f"资源组 {label} 金币/木材已修改：{amount:+d} -> {refreshed.gold}/{refreshed.lumber}"

    def populate_unit_fields(fields: list[UnitMemoryField]) -> None:
        state["unit_fields"] = {field.key: field for field in fields}
        unit_field_tree.delete(*unit_field_tree.get_children())
        for field in fields:
            unit_field_tree.insert(
                "",
                "end",
                iid=field.key,
                values=(
                    field.category,
                    field.label,
                    field.value_text(),
                    field.value_type,
                    f"0x{field.address:x}",
                    field.note,
                ),
            )

    def unit_identity(candidate: UnitCandidate) -> tuple[int, int, int]:
        return candidate.handle, candidate.owner_address, candidate.unit_address

    def current_manual_unit_identity() -> tuple[int, int, int] | None:
        identity = state.get("manual_unit_identity")
        if (
            isinstance(identity, tuple)
            and len(identity) == 3
            and all(isinstance(value, int) for value in identity)
        ):
            return identity
        return None

    def current_display_unit_identity() -> tuple[int, int, int] | None:
        identity = state.get("selected_unit_identity")
        if (
            isinstance(identity, tuple)
            and len(identity) == 3
            and all(isinstance(value, int) for value in identity)
        ):
            return identity
        return None

    def current_display_uses_win10() -> bool:
        return bool(state.get("selected_unit_win10"))

    def remembered_unit_identities() -> list[tuple[int, int, int]]:
        remembered: list[tuple[int, int, int]] = []
        for key in ("manual_unit_identity", "selected_unit_identity", "last_verified_unit_identity"):
            identity = state.get(key)
            if (
                isinstance(identity, tuple)
                and len(identity) == 3
                and all(isinstance(value, int) for value in identity)
                and identity not in remembered
            ):
                remembered.append(identity)
        return remembered

    def populate_selection_candidates(summaries: list[UnitSelectionSummary]) -> None:
        candidate_map: dict[str, UnitSelectionSummary] = {}
        candidate_tree.delete(*candidate_tree.get_children())
        preferred_identity = state.get("manual_unit_identity") or state.get("selected_unit_identity")
        selected_iid = ""
        for index, summary in enumerate(summaries, 1):
            iid = str(index)
            candidate_map[iid] = summary
            candidate = summary.candidate
            confidence = selection_confidence_text(summary)
            pos = summary.position
            pos_text = f"{pos[0]:.0f},{pos[1]:.0f}" if pos is not None else ""
            components = ",".join(summary.components) if summary.components else "-"
            inventory = ",".join(summary.inventory) if summary.inventory else "-"
            candidate_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    index,
                    confidence,
                    summary.hp_text,
                    summary.mp_text,
                    pos_text,
                    f"{summary.refs}/{summary.known_hits}",
                    components,
                    inventory,
                    f"0x{candidate.handle:x}",
                    f"0x{candidate.owner_address:x}",
                    f"0x{candidate.unit_address:x}",
                ),
            )
            if unit_identity(candidate) == preferred_identity:
                selected_iid = iid
            elif not selected_iid and summary.known_hits >= 2:
                selected_iid = iid
        state["selection_candidates"] = candidate_map
        if selected_iid:
            candidate_tree.selection_set(selected_iid)
            candidate_tree.focus(selected_iid)

    def selected_selection_candidate() -> UnitSelectionSummary:
        selection = candidate_tree.selection()
        if not selection:
            raise ValueError("请先在候选单位表选择一行")
        candidates = state.get("selection_candidates", {})
        if not isinstance(candidates, dict):
            raise ValueError("候选单位表尚未刷新")
        summary = candidates.get(str(selection[0]))
        if not isinstance(summary, UnitSelectionSummary):
            raise ValueError("候选单位表尚未刷新")
        return summary

    def refresh_unit_candidates() -> str:
        summaries = trainer().list_selection_candidates(extra_identities=remembered_unit_identities())
        root.after(0, populate_selection_candidates, summaries)
        return f"已列出 {len(summaries)} 个候选单位；慢速扫描结果请选择 HP/MP、坐标、组件和物品槽匹配的行"

    def populate_recovery_candidates(t: War3Trainer | None = None) -> None:
        remembered = remembered_unit_identities()
        try:
            summaries = (t or trainer()).list_selection_candidates(extra_identities=remembered or None)
        except Exception:
            return
        root.after(0, populate_selection_candidates, summaries)

    def populate_auto_selected_unit_readout(
        panel: VisibleUnitPanel,
        cand: UnitCandidate,
        fields: list[UnitMemoryField],
        force_targets: bool = False,
        win10_compat: bool = False,
    ) -> None:
        state["manual_unit_identity"] = None
        populate_selected_unit_readout(panel, cand, fields, force_targets, win10_compat)

    def populate_manual_candidate_readout(
        panel: VisibleUnitPanel,
        cand: UnitCandidate,
        fields: list[UnitMemoryField],
        force_targets: bool = False,
        win10_compat: bool = False,
    ) -> None:
        state["manual_unit_identity"] = unit_identity(cand)
        populate_selected_unit_readout(panel, cand, fields, force_targets, win10_compat)

    def read_selection_candidate_fields() -> str:
        summary = selected_selection_candidate()
        identity = unit_identity(summary.candidate)
        t = trainer()
        panel, cand, fields = t.read_unit_fields_by_identity(*identity)
        root.after(0, populate_manual_candidate_readout, panel, cand, fields, True)
        return (
            f"已读取所选候选：HP {panel.hp_text}，MP {panel.mp_text}；"
            f"owner=0x{cand.owner_address:x} handle=0x{cand.handle:x} unit=0x{cand.unit_address:x}"
        )

    def clear_selected_unit_readout() -> None:
        for var in (
            hp_current,
            hp_max_current,
            hp_regen_current,
            mp_current,
            mp_max_current,
            mp_regen_current,
            hp_target,
            mp_target,
            hp_regen_target,
            mp_regen_target,
            x_current,
            y_current,
            unit_type_id_current,
            x_target,
            y_target,
            unit_field_target,
        ):
            var.set("")
        state["selected_unit_identity"] = None
        state["selected_unit_win10"] = False
        state["manual_unit_identity"] = None
        state["unit_fields"] = {}
        try:
            unit_field_tree.delete(*unit_field_tree.get_children())
        except NameError:
            pass

    def populate_selected_unit_readout(
        panel: VisibleUnitPanel,
        cand: UnitCandidate,
        fields: list[UnitMemoryField],
        force_targets: bool = False,
        win10_compat: bool = False,
    ) -> None:
        field_by_key = {field.key: field for field in fields}
        identity = (cand.handle, cand.owner_address, cand.unit_address)
        reset_targets = force_targets or state.get("selected_unit_identity") != identity
        state["selected_unit_identity"] = identity
        state["selected_unit_win10"] = bool(win10_compat)
        state["last_verified_unit_identity"] = identity
        unit_type_id_current.set(format_rawcode(cand.unit_type_id) if cand.unit_type_id else "")

        hp_current.set(str(panel.current_hp))
        hp_max_current.set(str(panel.max_hp))
        mp_current.set(str(panel.current_mp))
        mp_max_current.set(str(panel.max_mp))

        hp_regen_field = field_by_key.get("hp_regen")
        mp_regen_field = field_by_key.get("mp_regen")
        hp_regen_current.set(hp_regen_field.value_text() if hp_regen_field is not None else "")
        mp_regen_current.set(mp_regen_field.value_text() if mp_regen_field is not None else "")

        x_field = field_by_key.get("x")
        y_field = field_by_key.get("y")
        if x_field is not None and y_field is not None:
            pos_x = float(x_field.value)
            pos_y = float(y_field.value)
            x_current.set(f"{pos_x:.3f}")
            y_current.set(f"{pos_y:.3f}")
            if reset_targets:
                x_target.set(f"{pos_x:.3f}")
                y_target.set(f"{pos_y:.3f}")
        else:
            x_current.set("")
            y_current.set("")
            if reset_targets:
                x_target.set("")
                y_target.set("")

        if reset_targets:
            hp_target.set(str(panel.current_hp))
            mp_target.set(str(panel.current_mp) if panel.max_mp or panel.current_mp else "")
            hp_regen_target.set(hp_regen_current.get())
            mp_regen_target.set(mp_regen_current.get())

        populate_unit_fields(fields)

    def read_unit_fields() -> str:
        try:
            t = trainer()
            panel, cand, fields = t.read_selected_unit_fields()
        except Exception as exc:
            populate_recovery_candidates(t if "t" in locals() else None)
            root.after(0, clear_selected_unit_readout)
            raise RuntimeError(f"{exc}；已尝试列出候选单位，请在候选表选择目标后点击“读取所选候选”") from exc
        root.after(0, populate_auto_selected_unit_readout, panel, cand, fields, True)
        return (
            f"选中单位字段：HP {panel.hp_text}，MP {panel.mp_text}；"
            f"source={cand.selection_source or 'unknown'} owner=0x{cand.owner_address:x} "
            f"handle=0x{cand.handle:x} unit=0x{cand.unit_address:x}"
        )

    def selected_unit_field() -> UnitMemoryField:
        selection = unit_field_tree.selection()
        if not selection:
            raise ValueError("请先在字段表选择一项")
        fields = state.get("unit_fields", {})
        if not isinstance(fields, dict):
            raise ValueError("字段表尚未刷新")
        field = fields.get(selection[0])
        if not isinstance(field, UnitMemoryField):
            raise ValueError("字段表尚未刷新")
        return field

    def set_advanced_unit_field() -> str:
        field = selected_unit_field()
        if not field.writable:
            raise ValueError("该字段不可写")
        value = unit_field_target.get().strip()
        if not value:
            raise ValueError("请填写目标值")
        t = trainer()
        target_identity = current_display_unit_identity()
        if target_identity is not None:
            if current_display_uses_win10():
                written = t.write_unit_field_by_identity_win10(*target_identity, field.key, value)
                panel, cand, fields = t.read_unit_fields_by_identity_win10(*target_identity)
                root.after(0, populate_manual_candidate_readout, panel, cand, fields, False, True)
            else:
                written = t.write_unit_field_by_identity(*target_identity, field.key, value)
                panel, cand, fields = t.read_unit_fields_by_identity(*target_identity)
                root.after(0, populate_manual_candidate_readout, panel, cand, fields, False)
        else:
            written = t.write_selected_unit_field(field.key, value)
            panel, cand, fields = t.read_selected_unit_fields()
            root.after(0, populate_auto_selected_unit_readout, panel, cand, fields, False)
        note = f"；{written.note}" if written.note else ""
        return f"{written.label} 已写入 {written.value_text()}{note}"

    def populate_locks() -> None:
        locks = state.get("locks", {})
        if not isinstance(locks, dict):
            return
        lock_tree.delete(*lock_tree.get_children())
        for lock_id, item in locks.items():
            if not isinstance(item, dict):
                continue
            lock_tree.insert(
                "",
                "end",
                iid=str(lock_id),
                values=(item.get("scope", ""), item.get("label", ""), item.get("value", "")),
            )

    def add_unit_lock() -> str:
        field = selected_unit_field()
        if not field.writable:
            raise ValueError("该字段不可锁定")
        value = unit_field_target.get().strip()
        if not value:
            raise ValueError("请填写锁定目标值")
        locks = state.get("locks", {})
        if not isinstance(locks, dict):
            locks = {}
            state["locks"] = locks
        locks[f"unit:{field.key}"] = {
            "scope": "选中单位",
            "kind": "unit",
            "key": field.key,
            "label": field.label,
            "value": value,
            "unit_identity": current_display_unit_identity(),
            "win10_compat": current_display_uses_win10(),
        }
        root.after(0, populate_locks)
        return f"已锁定选中单位字段：{field.label}={value}"

    def add_resource_lock(kind: str) -> str:
        cache = selected_resource_cache()
        group_label = selected_resource_label(cache)
        targets = {
            "gold": ("金币", gold_target.get().strip()),
            "lumber": ("木材", lumber_target.get().strip()),
            "food_used": ("当前人口", food_used_target.get().strip()),
            "food_cap": ("最大人口", food_cap_target.get().strip()),
        }
        label, value = targets[kind]
        if not value:
            raise ValueError(f"请先填写目标{label}")
        parse_int(value, f"目标{label}")
        locks = state.get("locks", {})
        if not isinstance(locks, dict):
            locks = {}
            state["locks"] = locks
        cache_iid = resource_iid(cache)
        is_local_player = cache_iid == str(state.get("local_resource_iid", ""))
        locks[f"resource:{cache_iid}:{kind}"] = {
            "scope": "本地玩家资源" if is_local_player else f"资源组 {group_label}",
            "kind": "resource",
            "key": kind,
            "resource_cache": cache,
            "resource_local_player": is_local_player,
            "label": f"{label}",
            "value": value,
        }
        root.after(0, populate_locks)
        return f"已锁定资源组 {group_label}：{label}={value}"

    def remove_selected_lock() -> str:
        selection = lock_tree.selection()
        if not selection:
            raise ValueError("请先选择要解锁的项目")
        locks = state.get("locks", {})
        if isinstance(locks, dict):
            for lock_id in selection:
                locks.pop(lock_id, None)
        root.after(0, populate_locks)
        return "已解锁所选项目"

    def apply_locks_once() -> None:
        locks = state.get("locks", {})
        if not isinstance(locks, dict) or not locks:
            return
        t = trainer()
        for item in list(locks.values()):
            if not isinstance(item, dict):
                continue
            kind = item.get("kind")
            key = str(item.get("key", ""))
            value = str(item.get("value", ""))
            if kind == "unit":
                identity = item.get("unit_identity")
                if (
                    isinstance(identity, tuple)
                    and len(identity) == 3
                    and all(isinstance(part, int) for part in identity)
                ):
                    if item.get("win10_compat"):
                        t.write_unit_field_by_identity_win10(*identity, key, value)
                    else:
                        t.write_unit_field_by_identity(*identity, key, value)
                else:
                    t.write_selected_unit_field(key, value)
                continue
            if kind != "resource":
                continue
            target = parse_int(value, str(item.get("label", "资源")))
            cache = item.get("resource_cache")
            if not isinstance(cache, ResourceCache):
                raise ValueError("锁定项缺少资源组地址，请删除后重新锁定")
            is_local_player = bool(item.get("resource_local_player"))

            def write_locked_resource(target_cache: ResourceCache) -> ResourceCache:
                if key == "gold":
                    return t.write_resource_cache(target_cache, target_gold=target)
                if key == "lumber":
                    return t.write_resource_cache(target_cache, target_lumber=target)
                if key == "food_used":
                    return t.write_resource_cache(
                        target_cache,
                        target_food_used=target,
                        sync_local_food_used=is_local_player,
                    )
                if key == "food_cap":
                    return t.write_resource_cache(
                        target_cache,
                        target_food_cap=target,
                        sync_local_food_cap=is_local_player,
                    )
                raise ValueError(f"未知资源锁定字段：{key}")

            if is_local_player:
                try:
                    cache = t.validate_local_player_resource_cache(cache)
                except (OSError, RuntimeError):
                    cache = t.locate_local_player_resource_cache()
            try:
                item["resource_cache"] = write_locked_resource(cache)
            except (OSError, RuntimeError):
                if not is_local_player:
                    raise
                cache = t.locate_local_player_resource_cache()
                item["resource_cache"] = write_locked_resource(cache)

    def lock_tick() -> None:
        if state.get("closing"):
            return
        locks = state.get("locks", {})
        if isinstance(locks, dict) and locks and not state.get("lock_busy"):
            state["lock_busy"] = True

            def worker() -> None:
                acquired = operation_lock.acquire(blocking=False)
                if not acquired:
                    state["lock_busy"] = False
                    return
                try:
                    apply_locks_once()
                    if not state.get("closing"):
                        root.after(0, set_status, f"锁定中：{len(locks)} 项")
                except Exception as exc:
                    if not state.get("closing"):
                        root.after(0, set_status, f"锁定失败：{exc}")
                finally:
                    operation_lock.release()
                    state["lock_busy"] = False

            start_operation_thread(worker, "war3-lock-tick")
        if not state.get("closing"):
            root.after(1500, lock_tick)

    def set_unit() -> str:
        t = trainer()
        hp_now = parse_float(hp_current.get(), "当前生命") if hp_current.get().strip() else 0.0
        mp_now = parse_float(mp_current.get(), "当前魔法") if mp_current.get().strip() else None
        hp_max_now = parse_float(hp_max_current.get(), "生命上限") if hp_max_current.get().strip() else None
        mp_max_now = parse_float(mp_max_current.get(), "魔法上限") if mp_max_current.get().strip() else None
        hp_new = parse_float(hp_target.get(), "目标生命") if hp_target.get().strip() else None
        mp_new = parse_float(mp_target.get(), "目标魔法") if mp_target.get().strip() else None
        hp_regen_new = parse_float(hp_regen_target.get(), "目标 HP 回复率") if hp_regen_target.get().strip() else None
        mp_regen_new = parse_float(mp_regen_target.get(), "目标 MP 回复率") if mp_regen_target.get().strip() else None
        x_new = parse_float(x_target.get(), "目标 X") if x_target.get().strip() else None
        y_new = parse_float(y_target.get(), "目标 Y") if y_target.get().strip() else None
        if hp_new is None and mp_new is None and hp_regen_new is None and mp_regen_new is None and x_new is None and y_new is None:
            raise ValueError("至少填写一个目标生命、魔法、回复率或坐标")
        target_identity = current_display_unit_identity()
        if target_identity is not None:
            if current_display_uses_win10():
                cand = t.set_unit_by_identity_win10(
                    *target_identity,
                    hp_now,
                    mp_now,
                    hp_new,
                    mp_new,
                    hp_max_now,
                    mp_max_now,
                    x_new,
                    y_new,
                    hp_regen_new,
                    mp_regen_new,
                )
                panel, cand_after, fields = t.read_unit_fields_by_identity_win10(*target_identity)
                root.after(
                    0,
                    populate_manual_candidate_readout,
                    panel,
                    cand_after,
                    fields,
                    True,
                    True,
                )
            else:
                cand = t.set_unit_by_identity(
                    *target_identity,
                    hp_now,
                    mp_now,
                    hp_new,
                    mp_new,
                    hp_max_now,
                    mp_max_now,
                    x_new,
                    y_new,
                    hp_regen_new,
                    mp_regen_new,
                )
                panel, cand_after, fields = t.read_unit_fields_by_identity(*target_identity)
                root.after(0, populate_manual_candidate_readout, panel, cand_after, fields, True)
            return (
                f"候选单位已写入；source={cand.selection_source or 'manual'} "
                f"base=0x{cand.base:x} unit=0x{cand.unit_address:x} {cand.note}"
            )
        cand = t.set_selected_unit(
            hp_now,
            mp_now,
            hp_new,
            mp_new,
            hp_max_now,
            mp_max_now,
            x_new,
            y_new,
            hp_regen_new,
            mp_regen_new,
        )
        panel, cand_after, fields = t.read_selected_unit_fields()
        root.after(0, populate_auto_selected_unit_readout, panel, cand_after, fields, True)
        return (
            f"选中单位已写入；source={cand.selection_source or 'unknown'} "
            f"base=0x{cand.base:x} unit=0x{cand.unit_address:x} {cand.note}"
        )

    def read_unit() -> str:
        started = time.perf_counter()
        try:
            t = trainer()
            panel, cand, fields = t.read_selected_unit_fields()
        except Exception as exc:
            populate_recovery_candidates(t if "t" in locals() else None)
            root.after(0, clear_selected_unit_readout)
            raise RuntimeError(f"{exc}；已尝试列出候选单位，请在候选表选择目标后点击“读取所选候选”") from exc
        root.after(0, populate_auto_selected_unit_readout, panel, cand, fields, True)
        elapsed_ms = (time.perf_counter() - started) * 1000
        return (
            f"选中单位：HP {panel.hp_text}，MP {panel.mp_text}；"
            f"source={cand.selection_source or 'unknown'} base=0x{cand.base:x} unit=0x{cand.unit_address:x}；"
            f"耗时 {elapsed_ms:.0f} ms"
        )

    def read_unit_win10() -> str:
        started = time.perf_counter()
        try:
            t = trainer()
            panel, cand, fields = t.read_selected_unit_fields_win10()
        except Exception as exc:
            root.after(0, clear_selected_unit_readout)
            raise RuntimeError(f"备用读取失败：{exc}") from exc
        root.after(0, populate_auto_selected_unit_readout, panel, cand, fields, True, True)
        elapsed_ms = (time.perf_counter() - started) * 1000
        log_path = getattr(t, "_last_win10_log_path", "")
        native_recovered = int(getattr(t, "_last_win10_native_recovered", 0))
        native_missing = tuple(getattr(t, "_last_win10_native_missing", ()))
        native_status = f"兼容 native {native_recovered}/{len(t.NATIVE_RECORD_PROFILE_EXTERNALS)}"
        if native_missing:
            native_status += f"，仍缺 {len(native_missing)}"
        return (
            f"备用读取 [{WIN10_COMPAT_REVISION}]：HP {panel.hp_text}，MP {panel.mp_text}；"
            f"source={cand.selection_source or 'backup'} unit=0x{cand.unit_address:x}；"
            f"{native_status}；耗时 {elapsed_ms:.0f} ms；日志：{log_path}"
        )

    def read_unit_native_selection() -> str:
        try:
            t = trainer()
            probe = t.probe_native_selection_manager()
            if probe.candidate is None:
                raise RuntimeError(f"native selection manager 已定位，但当前选择列表没有可映射单位；{probe.note}")
            with ProcessMemory(t.pid) as pm:
                candidate = t._candidate_with_selected_unit_type_id(pm, probe.candidate)
                panel = t._panel_from_candidate(pm, candidate)
                fields = t._unit_fields_from_candidate(pm, candidate)
        except Exception as exc:
            populate_recovery_candidates(t if "t" in locals() else None)
            root.after(0, clear_selected_unit_readout)
            raise RuntimeError(f"{exc}；已尝试列出候选单位，请在候选表选择目标后点击“读取所选候选”") from exc
        root.after(0, populate_auto_selected_unit_readout, panel, candidate, fields, True)
        return (
            f"Native定位：HP {panel.hp_text}，MP {panel.mp_text}；"
            f"offset=0x{probe.selection_manager_offset:x} "
            f"IsUnitSelected=0x{probe.is_unit_selected_handler:x} "
            f"unit=0x{candidate.unit_address:x}"
        )

    def prewarm_selection_cache() -> str:
        t = trainer()
        cand = t.prewarm_selected_unit_cache()
        return f"选择缓存已预热；unit=0x{cand.unit_address:x}"

    def elephant_prewarm() -> str:
        count = trainer().prewarm_elephant_functions()
        return f"大象功能已初始化：{count} 个 native 函数可用"

    def elephant_read_hero_level() -> str:
        level = trainer().get_selected_hero_level()
        root.after(0, elephant_hero_level.set, str(level))
        return f"当前英雄等级：{level}"

    def elephant_set_hero_level() -> str:
        target = parse_int(elephant_hero_level.get(), "英雄等级")
        actual = trainer().set_selected_hero_level(target)
        root.after(0, elephant_hero_level.set, str(actual))
        return f"英雄等级已设置为 {actual}"

    def elephant_set_scale() -> str:
        scale = parse_float(elephant_unit_scale.get(), "单位大小")
        actual = trainer().set_selected_unit_scale(scale)
        return f"单位大小已设置为 {actual:g}"

    def elephant_create_unit(copy_selected: bool) -> str:
        rawcode = None if copy_selected else elephant_unit_rawcode.get().strip()
        if not copy_selected and not rawcode:
            raise ValueError("请填写单位 ID")
        unit_rawcode, handle = trainer().create_local_unit(rawcode)
        return f"已创建 {format_rawcode(unit_rawcode)}；handle=0x{handle:x}"

    def elephant_add_item() -> str:
        rawcode = elephant_item_rawcode.get().strip()
        if not rawcode:
            raise ValueError("请填写物品 ID")
        handle = trainer().add_item_to_selected_unit(rawcode)
        return f"物品 {rawcode} 已添加；handle=0x{handle:x}"

    def elephant_clear_inventory() -> str:
        removed = trainer().clear_selected_unit_inventory()
        return f"背包已清空，共删除 {removed} 件物品"

    def elephant_add_ability() -> str:
        rawcode = elephant_ability_rawcode.get().strip()
        if not rawcode:
            raise ValueError("请填写技能 ID")
        trainer().add_ability_to_selected_unit(rawcode)
        return f"技能 {rawcode} 已添加"

    def elephant_remove_ability() -> str:
        rawcode = elephant_ability_rawcode.get().strip()
        if not rawcode:
            raise ValueError("请填写技能 ID")
        trainer().remove_ability_from_selected_unit(rawcode)
        return f"技能 {rawcode} 已删除"

    def elephant_set_ability_level() -> str:
        rawcode = elephant_ability_rawcode.get().strip()
        level = parse_int(elephant_ability_level.get(), "技能等级")
        actual = trainer().set_selected_unit_ability_level(rawcode, level)
        return f"技能 {rawcode} 等级已设置；native 返回 {actual}"

    def refresh_ability_field_tree() -> None:
        snapshot = state.get("ability_field_snapshot")
        rows: dict[str, AbilityFieldValue] = {}
        ability_field_tree.delete(*ability_field_tree.get_children())
        if not isinstance(snapshot, AbilityFieldSnapshot):
            state["ability_field_rows"] = rows
            return
        query = ability_field_filter.get().strip().lower()
        show_zero = ability_field_show_zero.get()
        show_unsupported = ability_field_show_unsupported.get()
        type_labels = {
            "boolean": "布尔",
            "integer": "整数",
            "real": "实数",
            "string": "字符串",
        }
        scope_labels = {
            "field": "全局",
            "level": "等级",
            "level_array": "等级数组",
        }
        for index, field_value in enumerate(snapshot.fields):
            spec = field_value.spec
            if not show_unsupported and field_value.status == "未开放":
                continue
            if (
                not show_zero
                and field_value.value is not None
                and (
                    field_value.value is False
                    or field_value.value == 0
                    or field_value.value == 0.0
                )
            ):
                continue
            searchable = " ".join(
                (
                    spec.rawcode,
                    spec.constant_name,
                    spec.field_name,
                    spec.category,
                    spec.metadata_type,
                    field_value.note,
                )
            ).lower()
            if query and query not in searchable:
                continue
            iid = f"ability-field-{index}"
            rows[iid] = field_value
            label = spec.constant_name
            if label.startswith("METADATA_"):
                label = spec.field_name or spec.display_name or label
            ability_field_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    spec.rawcode,
                    type_labels.get(spec.value_kind, spec.value_kind),
                    scope_labels.get(spec.scope, spec.scope),
                    label,
                    field_value.value_text(),
                    field_value.status,
                ),
            )
        state["ability_field_rows"] = rows

    def apply_ability_field_snapshot(snapshot: AbilityFieldSnapshot) -> None:
        state["ability_field_snapshot"] = snapshot
        effect_status = "" if snapshot.effect_class_verified else "（未确认）"
        effect_note = (
            f"；{snapshot.effect_class_note}"
            if not snapshot.effect_class_verified and snapshot.effect_class_note
            else ""
        )
        ability_field_summary.set(
            f"技能 {format_rawcode(snapshot.ability_rawcode)}；"
            f"效果类 {format_rawcode(snapshot.effect_class)}{effect_status}；"
            f"当前等级 {snapshot.current_level}；"
            f"字段等级 {snapshot.requested_level}；"
            f"候选 {len(snapshot.fields)} 项"
            f"{effect_note}"
        )
        ability_field_value.set("")
        ability_field_detail.set("")
        ability_field_write_button.state(["disabled"])
        refresh_ability_field_tree()

    def read_ability_field_snapshot() -> str:
        rawcode = ability_field_rawcode.get().strip()
        if not rawcode:
            raise ValueError("请填写技能 ID")
        level = parse_int(ability_field_level.get(), "字段等级")
        snapshot = trainer().read_selected_ability_fields(rawcode, level)
        root.after(0, apply_ability_field_snapshot, snapshot)
        readable = sum(field.value is not None for field in snapshot.fields)
        writable = sum(
            field.value is not None and field.spec.writable
            for field in snapshot.fields
        )
        return (
            f"已读取 {format_rawcode(snapshot.ability_rawcode)}："
            f"{readable} 项有值，{writable} 项可尝试写入"
        )

    def select_ability_field(_event: object | None = None) -> None:
        selected = ability_field_tree.selection()
        rows = state.get("ability_field_rows")
        field_value = (
            rows.get(selected[0])
            if selected and isinstance(rows, dict)
            else None
        )
        if not isinstance(field_value, AbilityFieldValue):
            ability_field_value.set("")
            ability_field_detail.set("")
            ability_field_write_button.state(["disabled"])
            return
        spec = field_value.spec
        ability_field_value.set(field_value.value_text())
        bounds = ""
        if spec.minimum is not None or spec.maximum is not None:
            bounds = f"；元数据范围 {spec.minimum!s} .. {spec.maximum!s}"
        specific = ""
        if spec.use_specific:
            specific = "；适用 " + ",".join(spec.use_specific)
        ability_field_detail.set(
            f"{spec.rawcode} | {spec.constant_name} | {spec.metadata_type or spec.value_kind}"
            f" | {spec.field_name or '-'}{bounds}{specific}"
            + (f"；{field_value.note}" if field_value.note else "")
        )
        if field_value.value is not None and spec.writable:
            ability_field_write_button.state(["!disabled"])
        else:
            ability_field_write_button.state(["disabled"])

    def write_selected_ability_field(
        snapshot: AbilityFieldSnapshot,
        rawcode: str,
        level: int,
        field_value: AbilityFieldValue,
        target_text: str,
    ) -> str:
        try:
            actual = trainer().set_selected_ability_field(
                rawcode,
                level,
                field_value.spec,
                target_text,
                expected_snapshot=snapshot,
            )
        except RuntimeError as exc:
            if (
                "游戏拒绝写入该技能字段" in str(exc)
                and "恢复无法确认" not in str(exc)
            ):
                rejected = replace(field_value, status="游戏拒绝", note=str(exc))
                key = (
                    field_value.spec.rawcode,
                    field_value.spec.value_kind,
                    field_value.spec.scope,
                )
                rejected_snapshot = replace(
                    snapshot,
                    fields=tuple(
                        rejected
                        if (item.spec.rawcode, item.spec.value_kind, item.spec.scope) == key
                        else item
                        for item in snapshot.fields
                    ),
                )
                root.after(
                    0,
                    lambda: (
                        apply_ability_field_snapshot(rejected_snapshot)
                        if state.get("ability_field_snapshot") is snapshot
                        else None
                    ),
                )
            raise
        key = (
            field_value.spec.rawcode,
            field_value.spec.value_kind,
            field_value.spec.scope,
        )
        updated_fields = tuple(
            actual
            if (item.spec.rawcode, item.spec.value_kind, item.spec.scope) == key
            else item
            for item in snapshot.fields
        )
        updated_snapshot = replace(snapshot, fields=updated_fields)
        root.after(
            0,
            lambda: (
                apply_ability_field_snapshot(updated_snapshot)
                if state.get("ability_field_snapshot") is snapshot
                else None
            ),
        )
        return (
            f"字段 {field_value.spec.rawcode} 已写入并读回："
            f"{actual.value_text()}"
        )

    def ability_field_write_clicked() -> None:
        snapshot = state.get("ability_field_snapshot")
        if not isinstance(snapshot, AbilityFieldSnapshot):
            messagebox.showerror("错误", "请先读取技能字段")
            return
        selected = ability_field_tree.selection()
        rows = state.get("ability_field_rows")
        field_value = (
            rows.get(selected[0])
            if selected and isinstance(rows, dict)
            else None
        )
        if not isinstance(field_value, AbilityFieldValue):
            messagebox.showerror("错误", "请先选择一个可写字段")
            return
        rawcode = ability_field_rawcode.get().strip()
        try:
            level = parse_int(ability_field_level.get(), "字段等级")
        except ValueError as exc:
            messagebox.showerror("错误", str(exc))
            return
        target_text = ability_field_value.get().strip()
        call_async(
            lambda: write_selected_ability_field(
                snapshot,
                rawcode,
                level,
                field_value,
                target_text,
            ),
            operation_key="ability-field-write",
            busy_text="正在写入并校验技能字段...",
        )

    def elephant_set_tech() -> str:
        rawcode = elephant_tech_rawcode.get().strip()
        if not rawcode:
            raise ValueError("请填写科技 ID")
        level = parse_int(elephant_tech_level.get(), "科技等级")
        actual = trainer().set_local_player_tech(rawcode, level)
        return f"科技 {rawcode} 已设置为 {actual} 级"

    def elephant_set_xp_rate() -> str:
        rate = parse_float(elephant_xp_rate.get(), "经验倍率")
        actual = trainer().set_local_player_xp_rate(rate)
        return f"本地玩家经验倍率已设置为 {actual:g}"

    def elephant_set_inventory_charges() -> str:
        charges = parse_int(elephant_item_charges.get(), "物品数量")
        changed = trainer().set_selected_inventory_charges(charges)
        return f"已将 {changed} 件背包物品的数量设为 {charges}"

    def elephant_duplicate_inventory() -> str:
        duplicated = trainer().duplicate_selected_inventory_items()
        return f"已复制 {duplicated} 件背包物品"

    def elephant_drop_inventory() -> str:
        dropped = trainer().drop_selected_inventory_items()
        return f"已丢弃 {dropped} 件背包物品"

    def elephant_add_resources() -> str:
        amount = parse_int(elephant_resource_amount.get(), "金币木材增量")
        trainer().add_gold_and_lumber(amount)
        return f"金币和木材已增加 {amount}"

    def elephant_mass_clone() -> str:
        count = parse_int(elephant_mass_clone_count.get(), "批量复制数量")
        rawcode, created = trainer().create_local_units(count)
        return f"已复制 {created} 个 {format_rawcode(rawcode)}"

    def elephant_set_hero_attributes() -> str:
        value = parse_int(elephant_hero_attributes.get(), "英雄属性")
        actual = trainer().set_selected_hero_attributes(value)
        return f"力量、敏捷、智力已设置为 {actual}"

    def elephant_add_skill_points() -> str:
        amount = parse_int(elephant_skill_points.get(), "增加技能点数")
        actual = trainer().add_selected_hero_skill_points(amount)
        return f"英雄技能点已增加 {actual}"

    def elephant_reset_ability() -> str:
        rawcode = elephant_reset_ability_rawcode.get().strip()
        if not rawcode:
            raise ValueError("请填写重置技能 ID")
        trainer().reset_selected_unit_ability(rawcode)
        return f"技能 {rawcode} 已重置"

    def elephant_remove_all_abilities() -> str:
        removed = trainer().remove_all_selected_unit_abilities()
        return f"已删除选中单位的 {removed} 个非基础技能"

    def elephant_move_to_mouse() -> str:
        x, y = trainer().move_selected_unit_to_mouse()
        return f"选中单位已移动到鼠标位置 ({x:g}, {y:g})"

    def elephant_add_standard_auras() -> str:
        entries = (
            ("AHab", 112),
            ("AHad", 112),
            ("AOr2", 112),
            ("AUau", 112),
            ("AUav", 112),
            ("AEar", 112),
            ("AEah", 112),
            ("Aabr", None),
            ("ACac", None),
        )
        added, total = trainer().add_ability_bundle_to_selected_unit(entries)
        return f"全光环已处理 {total} 项，新增 {added} 项"

    def elephant_add_standard_passives() -> str:
        entries = (
            ("AInv", None),
            ("AHbh", 112),
            ("AOcr", 112),
            ("Acdb", 112),
            ("ACce", None),
            ("ACes", None),
            ("ACrn", None),
            ("ACpv", None),
        )
        added, total = trainer().add_ability_bundle_to_selected_unit(entries)
        return f"全被动已处理 {total} 项，新增 {added} 项"

    def elephant_add_six_artifacts() -> str:
        trainer().add_abilities_to_selected_unit(("AInv",))
        count = trainer().replace_selected_inventory_items((
            (5, "nspi"),
            (4, "frhg"),
            (3, "crdt"),
            (2, "shdt"),
            (1, "srtl"),
            (0, "klmm"),
        ))
        return f"六神器已写入 {count} 个背包槽位"

    def elephant_create_all_items() -> str:
        total, created, _last_item = trainer().create_all_loaded_items()
        return f"已遍历 {total} 个运行时物品对象，成功创建 {created} 个"

    def elephant_apply_all_debuffs() -> str:
        attempted, succeeded = trainer().apply_standard_debuffs_to_selected_unit()
        if not succeeded:
            raise RuntimeError("游戏没有接受任何减益技能命令")
        return f"减益技能已执行 {succeeded}/{attempted} 次"

    def elephant_apply_all_buffs() -> str:
        attempted, succeeded = trainer().apply_standard_buffs_to_selected_unit()
        if not succeeded:
            raise RuntimeError("游戏没有接受任何增益技能命令")
        return f"增益技能已执行 {succeeded}/{attempted} 次"

    def elephant_fullscreen_cast(action: Callable[[], tuple[int, int]], label: str) -> str:
        attempted, succeeded = action()
        if not succeeded:
            raise RuntimeError(f"游戏没有接受{label}命令")
        return f"{label}已执行 {succeeded}/{attempted} 次"

    def elephant_fullscreen_auto() -> str:
        count = parse_int(elephant_auto_effect_count.get(), "自动特效次数")
        if not 1 <= count <= 255:
            raise ValueError("自动特效次数必须在 1 到 255 之间")
        return elephant_fullscreen_cast(
            lambda: trainer().cast_fullscreen_auto_effect(success_limit=count),
            "全屏自动特效攻击",
        )

    def elephant_create_reinforcement() -> str:
        rawcode = elephant_reinforcement_rawcode.get().strip()
        if not rawcode:
            raise ValueError("请填写增援单位 ID")
        unit_rawcode, handle = trainer().create_local_unit(rawcode)
        return f"已呼叫 {format_rawcode(unit_rawcode)}；handle=0x{handle:x}"

    def elephant_add_preset_item() -> str:
        rawcode = elephant_preset_item_rawcode.get().strip()
        if not rawcode:
            raise ValueError("请填写快捷物品 ID")
        handle = trainer().add_item_to_selected_unit(rawcode)
        return f"物品 {rawcode} 已添加；handle=0x{handle:x}"

    def elephant_set_preset_tech() -> str:
        rawcode = elephant_preset_tech_rawcode.get().strip()
        if not rawcode:
            raise ValueError("请填写快捷科技 ID")
        actual = trainer().set_local_player_tech(rawcode, 1)
        return f"科技 {rawcode} 已设置为 {actual} 级"

    def elephant_set_game_paused(paused: bool) -> str:
        trainer().set_game_paused(paused)
        state["elephant_game_paused"] = paused
        return "游戏已暂停" if paused else "游戏已恢复"

    def elephant_toggle_game_pause() -> str:
        return elephant_set_game_paused(not bool(state.get("elephant_game_paused")))

    def elephant_toggle_unit_pause() -> str:
        t = trainer()
        paused = not t.is_selected_unit_paused()
        t.set_selected_unit_paused(paused)
        return "选中单位已暂停" if paused else "选中单位已恢复"

    def elephant_kill_owner_units() -> str:
        killed = trainer().kill_selected_owner_units()
        return f"已击杀该单位所属玩家的 {killed} 个单位"

    def elephant_action(action: Callable[[], None], message: str) -> str:
        action()
        return message

    hotkey_callbacks: dict[str, Callable[[], str]] = {
        "hero_level": elephant_set_hero_level,
        "instant_move": elephant_move_to_mouse,
        "explode_unit": lambda: elephant_action(trainer().explode_selected_unit, "选中单位已爆炸"),
        "reveal_map": lambda: elephant_action(lambda: trainer().set_map_revealed(True), "全地图视野已开启"),
        "hide_map": lambda: elephant_action(lambda: trainer().set_map_revealed(False), "战争迷雾已恢复"),
        "invulnerable": lambda: elephant_action(
            lambda: trainer().set_selected_unit_invulnerable(True),
            "选中单位已设为无敌",
        ),
        "vulnerable": lambda: elephant_action(
            lambda: trainer().set_selected_unit_invulnerable(False),
            "选中单位已取消无敌",
        ),
        "reset_cooldown": lambda: elephant_action(
            trainer().reset_selected_unit_cooldown,
            "选中单位技能冷却已重置",
        ),
        "clone_to_self": lambda: elephant_create_unit(True),
        "duplicate_inventory": elephant_duplicate_inventory,
        "unit_scale": elephant_set_scale,
        "item_charges": elephant_set_inventory_charges,
        "drop_inventory": elephant_drop_inventory,
        "add_ability": elephant_add_ability,
        "clone_unit": lambda: elephant_create_unit(True),
        "take_control": lambda: elephant_action(trainer().take_selected_unit_control, "已取得选中单位控制权"),
        "add_resources": elephant_add_resources,
        "mass_clone": elephant_mass_clone,
        "ability_level": elephant_set_ability_level,
        "remove_ability": elephant_remove_ability,
        "all_auras": elephant_add_standard_auras,
        "all_passives": elephant_add_standard_passives,
        "six_artifacts": elephant_add_six_artifacts,
        "reinforcements": elephant_create_reinforcement,
        "preset_item": elephant_add_preset_item,
        "preset_tech": elephant_set_preset_tech,
        "create_all_items": elephant_create_all_items,
        "ignore_collision": lambda: elephant_action(
            lambda: trainer().set_selected_unit_pathing(False),
            "选中单位碰撞已关闭",
        ),
        "hero_attributes": elephant_set_hero_attributes,
        "skill_points": elephant_add_skill_points,
        "kill_owner_units": elephant_kill_owner_units,
        "xp_rate": elephant_set_xp_rate,
        "reset_ability": elephant_reset_ability,
        "all_debuffs": elephant_apply_all_debuffs,
        "all_buffs": elephant_apply_all_buffs,
        "fullscreen_swarm": lambda: elephant_fullscreen_cast(
            trainer().cast_fullscreen_swarm,
            "全屏腐臭蜂群",
        ),
        "fullscreen_clap": lambda: elephant_fullscreen_cast(
            trainer().cast_fullscreen_clap,
            "全屏雷霆一击",
        ),
        "fullscreen_monsoon": lambda: elephant_fullscreen_cast(
            trainer().cast_fullscreen_monsoon,
            "全屏季风",
        ),
        "fullscreen_starfall": lambda: elephant_fullscreen_cast(
            trainer().cast_fullscreen_starfall,
            "全屏群星陨落",
        ),
        "fullscreen_forked": lambda: elephant_fullscreen_cast(
            trainer().cast_fullscreen_forked_lightning,
            "全屏叉状闪电",
        ),
        "fullscreen_auto": elephant_fullscreen_auto,
        "toggle_unit_pause": elephant_toggle_unit_pause,
        "toggle_game_pause": elephant_toggle_game_pause,
        "end_game": lambda: elephant_action(lambda: trainer().end_current_game(True), "已结束当前游戏"),
        "remove_all_abilities": elephant_remove_all_abilities,
    }
    hotkey_specs_by_name = {spec.name: spec for spec in ELEPHANT_HOTKEY_SPECS}
    hotkey_dangerous = {
        "explode_unit",
        "drop_inventory",
        "kill_owner_units",
        "end_game",
        "remove_all_abilities",
    }
    for name, variable in elephant_hotkey_checks.items():
        variable.set(name in hotkey_callbacks and name not in hotkey_dangerous)

    def trigger_elephant_hotkey(name: str) -> None:
        callback = hotkey_callbacks.get(name)
        spec = hotkey_specs_by_name.get(name)
        if callback is None or spec is None:
            return
        call_async(
            callback,
            f"elephant:hotkey:{name}",
            busy_text=f"正在执行 {spec.label}...",
        )

    def on_global_hotkey(name: str) -> None:
        try:
            root.after(0, trigger_elephant_hotkey, name)
        except RuntimeError:
            pass

    def refresh_elephant_hotkeys() -> None:
        if not elephant_hotkeys_enabled.get():
            hotkey_manager.stop()
            elephant_hotkey_status.set("快捷键未启用")
            return
        enabled_specs = tuple(
            spec
            for spec in ELEPHANT_HOTKEY_SPECS
            if spec.name in hotkey_callbacks and elephant_hotkey_checks[spec.name].get()
        )
        errors = hotkey_manager.start(enabled_specs, on_global_hotkey)
        registered = len(hotkey_manager.registered_names)
        if errors:
            elephant_hotkey_status.set(f"已注册 {registered} 个，{len(errors)} 个按键冲突")
        else:
            elephant_hotkey_status.set(f"已注册 {registered} 个全局快捷键")
        set_status(elephant_hotkey_status.get())

    def set_all_elephant_hotkeys(enabled: bool) -> None:
        for name, variable in elephant_hotkey_checks.items():
            variable.set(bool(enabled and name in hotkey_callbacks))
        if elephant_hotkeys_enabled.get():
            refresh_elephant_hotkeys()

    def confirm_elephant_action(title: str, prompt: str, fn: Callable[[], str]) -> None:
        if messagebox.askyesno(title, prompt, parent=root):
            call_async(fn, f"elephant:{title}")

    outer = ttk.Frame(root, padding=12)
    outer.pack(fill="both", expand=True)
    top = ttk.Frame(outer)
    top.pack(fill="x")
    ttk.Button(top, text="连接/刷新进程", command=lambda: call_async(connect)).pack(side="left")
    ttk.Label(top, text="PID").pack(side="left", padx=(16, 4))
    ttk.Entry(top, textvariable=pid_var, width=10, state="readonly").pack(side="left")
    ttk.Label(top, textvariable=status).pack(side="right")

    notebook = ttk.Notebook(outer)
    notebook.pack(fill="both", expand=True, pady=(12, 8))

    res = ttk.Frame(notebook, padding=10)
    notebook.add(res, text="玩家资源")
    ttk.Button(res, text="读取全部资源组", command=lambda: call_async(refresh_resources)).grid(row=0, column=0, pady=(0, 8), sticky="w")

    resource_frame = ttk.Frame(res)
    resource_frame.grid(row=1, column=0, columnspan=7, sticky="nsew", pady=(0, 10))
    res.rowconfigure(1, weight=1)
    res.columnconfigure(6, weight=1)
    resource_columns = ("group", "gold", "lumber", "food", "gold_address", "lumber_address", "source")
    resource_tree = ttk.Treeview(resource_frame, columns=resource_columns, show="headings", height=10)
    resource_headings = {
        "group": ("资源组", 90),
        "gold": ("金币", 80),
        "lumber": ("木材", 80),
        "food": ("人口", 80),
        "gold_address": ("金币地址", 150),
        "lumber_address": ("木材地址", 150),
        "source": ("来源", 340),
    }
    for column, (heading, width) in resource_headings.items():
        resource_tree.heading(column, text=heading)
        resource_tree.column(column, width=width, anchor="w", stretch=(column == "source"))
    resource_scroll = ttk.Scrollbar(resource_frame, orient="vertical", command=resource_tree.yview)
    resource_tree.configure(yscrollcommand=resource_scroll.set)
    resource_tree.grid(row=0, column=0, sticky="nsew")
    resource_scroll.grid(row=0, column=1, sticky="ns")
    resource_frame.rowconfigure(0, weight=1)
    resource_frame.columnconfigure(0, weight=1)
    resource_tree.bind("<<TreeviewSelect>>", on_resource_select)

    ttk.Label(res, text="当前金币").grid(row=2, column=0, sticky="w")
    ttk.Entry(res, textvariable=gold_current, width=12, state="readonly").grid(row=2, column=1, sticky="w")
    ttk.Label(res, text="目标金币").grid(row=2, column=2, sticky="w", padx=(16, 0))
    ttk.Entry(res, textvariable=gold_target, width=12).grid(row=2, column=3, sticky="w")
    ttk.Button(res, text="设置金币", command=lambda: call_async(lambda: set_resource("gold"))).grid(row=2, column=4, padx=8)
    ttk.Button(res, text="锁定金币", command=lambda: call_async(lambda: add_resource_lock("gold"))).grid(row=2, column=5, padx=4)

    ttk.Label(res, text="当前木材").grid(row=3, column=0, sticky="w", pady=8)
    ttk.Entry(res, textvariable=lumber_current, width=12, state="readonly").grid(row=3, column=1, sticky="w")
    ttk.Label(res, text="目标木材").grid(row=3, column=2, sticky="w", padx=(16, 0))
    ttk.Entry(res, textvariable=lumber_target, width=12).grid(row=3, column=3, sticky="w")
    ttk.Button(res, text="设置木材", command=lambda: call_async(lambda: set_resource("lumber"))).grid(row=3, column=4, padx=8)
    ttk.Button(res, text="锁定木材", command=lambda: call_async(lambda: add_resource_lock("lumber"))).grid(row=3, column=5, padx=4)

    ttk.Label(res, text="当前人口").grid(row=4, column=0, sticky="w", pady=8)
    ttk.Entry(res, textvariable=food_current, width=12, state="readonly").grid(row=4, column=1, sticky="w")
    ttk.Label(res, text="人口上限").grid(row=4, column=2, sticky="w", padx=(16, 0))
    ttk.Entry(res, textvariable=food_cap_current, width=12, state="readonly").grid(row=4, column=3, sticky="w")
    ttk.Label(res, text="目标当前人口").grid(row=5, column=0, sticky="w", pady=8)
    ttk.Entry(res, textvariable=food_used_target, width=12).grid(row=5, column=1, sticky="w")
    ttk.Button(res, text="设置当前人口", command=lambda: call_async(lambda: set_food_resource("food_used"))).grid(row=5, column=2, padx=8)
    ttk.Button(res, text="锁定当前人口", command=lambda: call_async(lambda: add_resource_lock("food_used"))).grid(row=5, column=3, padx=4)

    ttk.Label(res, text="目标人口上限").grid(row=6, column=0, sticky="w", pady=8)
    ttk.Entry(res, textvariable=food_cap_target, width=12).grid(row=6, column=1, sticky="w")
    ttk.Button(res, text="设置人口上限", command=lambda: call_async(lambda: set_food_resource("food_cap"))).grid(row=6, column=2, padx=8)
    ttk.Button(res, text="锁定人口上限", command=lambda: call_async(lambda: add_resource_lock("food_cap"))).grid(row=6, column=3, padx=4)

    ttk.Label(res, text="增量").grid(row=7, column=0, sticky="w", pady=(12, 0))
    ttk.Entry(res, textvariable=resource_delta, width=12).grid(row=7, column=1, sticky="w", pady=(12, 0))
    ttk.Button(res, text="金币 +/-", command=lambda: call_async(lambda: add_resource("gold"))).grid(row=7, column=2, pady=(12, 0))
    ttk.Button(res, text="木材 +/-", command=lambda: call_async(lambda: add_resource("lumber"))).grid(row=7, column=3, pady=(12, 0))
    ttk.Button(res, text="金木一起 +/-", command=lambda: call_async(lambda: add_resource("both"))).grid(row=7, column=4, pady=(12, 0), padx=8)

    unit = ttk.Frame(notebook, padding=10)
    notebook.add(unit, text="选中单位")
    ttk.Label(unit, text="当前生命").grid(row=0, column=0, sticky="w")
    ttk.Entry(unit, textvariable=hp_current, width=12).grid(row=0, column=1, sticky="w")
    ttk.Label(unit, text="生命上限").grid(row=0, column=2, sticky="w", padx=(16, 0))
    ttk.Entry(unit, textvariable=hp_max_current, width=12).grid(row=0, column=3, sticky="w")
    ttk.Label(unit, text="目标生命").grid(row=0, column=4, sticky="w", padx=(16, 0))
    ttk.Entry(unit, textvariable=hp_target, width=12).grid(row=0, column=5, sticky="w")
    ttk.Label(unit, text="当前魔法").grid(row=1, column=0, sticky="w", pady=8)
    ttk.Entry(unit, textvariable=mp_current, width=12).grid(row=1, column=1, sticky="w")
    ttk.Label(unit, text="魔法上限").grid(row=1, column=2, sticky="w", padx=(16, 0))
    ttk.Entry(unit, textvariable=mp_max_current, width=12).grid(row=1, column=3, sticky="w")
    ttk.Label(unit, text="目标魔法").grid(row=1, column=4, sticky="w", padx=(16, 0))
    ttk.Entry(unit, textvariable=mp_target, width=12).grid(row=1, column=5, sticky="w")
    ttk.Label(unit, text="HP 回复率").grid(row=2, column=0, sticky="w", pady=8)
    ttk.Entry(unit, textvariable=hp_regen_current, width=12).grid(row=2, column=1, sticky="w")
    ttk.Label(unit, text="目标 HP 回复率").grid(row=2, column=2, sticky="w", padx=(16, 0))
    ttk.Entry(unit, textvariable=hp_regen_target, width=12).grid(row=2, column=3, sticky="w")
    ttk.Label(unit, text="MP 回复率").grid(row=3, column=0, sticky="w", pady=8)
    ttk.Entry(unit, textvariable=mp_regen_current, width=12).grid(row=3, column=1, sticky="w")
    ttk.Label(unit, text="目标 MP 回复率").grid(row=3, column=2, sticky="w", padx=(16, 0))
    ttk.Entry(unit, textvariable=mp_regen_target, width=12).grid(row=3, column=3, sticky="w")
    ttk.Label(unit, text="当前 X").grid(row=4, column=0, sticky="w", pady=8)
    ttk.Entry(unit, textvariable=x_current, width=12).grid(row=4, column=1, sticky="w")
    ttk.Label(unit, text="当前 Y").grid(row=4, column=2, sticky="w", padx=(16, 0))
    ttk.Entry(unit, textvariable=y_current, width=12).grid(row=4, column=3, sticky="w")
    ttk.Label(unit, text="单位 ID").grid(row=4, column=4, sticky="w", padx=(16, 0))
    ttk.Entry(unit, textvariable=unit_type_id_current, width=12, state="readonly").grid(row=4, column=5, sticky="w")
    ttk.Label(unit, text="目标 X").grid(row=5, column=0, sticky="w", pady=8)
    ttk.Entry(unit, textvariable=x_target, width=12).grid(row=5, column=1, sticky="w")
    ttk.Label(unit, text="目标 Y").grid(row=5, column=2, sticky="w", padx=(16, 0))
    ttk.Entry(unit, textvariable=y_target, width=12).grid(row=5, column=3, sticky="w")
    read_unit_button = ttk.Button(unit, text="读取当前选中单位")
    read_unit_button.configure(
        command=lambda: call_async(read_unit, "read_unit", read_unit_button)
    )
    read_unit_button.grid(row=6, column=0, pady=12, sticky="w")
    backup_read_button = ttk.Button(unit, text="备用读取")
    backup_read_button.configure(
        command=lambda: call_async(
            read_unit_win10,
            "backup_read",
            backup_read_button,
        )
    )
    backup_read_button.grid(row=6, column=1, pady=12, sticky="w")
    ttk.Button(unit, text="写入选中单位", command=lambda: call_async(set_unit)).grid(row=6, column=2, pady=12, sticky="w")
    ttk.Button(unit, text="刷新字段表", command=lambda: call_async(read_unit_fields)).grid(row=6, column=3, pady=12, sticky="w")
    ttk.Button(unit, text="列出候选单位", command=lambda: call_async(refresh_unit_candidates)).grid(row=6, column=4, pady=12, sticky="w")
    ttk.Button(unit, text="读取所选候选", command=lambda: call_async(read_selection_candidate_fields)).grid(row=6, column=5, pady=12, sticky="w")
    ttk.Button(unit, text="Native定位", command=lambda: call_async(read_unit_native_selection)).grid(row=6, column=6, pady=12, sticky="w")

    candidate_frame = ttk.Frame(unit)
    candidate_frame.grid(row=7, column=0, columnspan=7, sticky="nsew", pady=(0, 8))
    candidate_columns = (
        "index",
        "confidence",
        "hp",
        "mp",
        "position",
        "evidence",
        "components",
        "inventory",
        "handle",
        "owner",
        "unit",
    )
    candidate_tree = ttk.Treeview(candidate_frame, columns=candidate_columns, show="headings", height=5)
    for column, heading, width in (
        ("index", "#", 36),
        ("confidence", "可信度", 56),
        ("hp", "生命", 86),
        ("mp", "魔法", 86),
        ("position", "坐标", 90),
        ("evidence", "refs/known", 82),
        ("components", "组件", 170),
        ("inventory", "物品槽", 220),
        ("handle", "handle", 132),
        ("owner", "owner", 132),
        ("unit", "unit", 132),
    ):
        candidate_tree.heading(column, text=heading)
        candidate_tree.column(column, width=width, anchor="w", stretch=(column in {"components", "inventory"}))
    candidate_scroll = ttk.Scrollbar(candidate_frame, orient="vertical", command=candidate_tree.yview)
    candidate_tree.configure(yscrollcommand=candidate_scroll.set)
    candidate_tree.pack(side="left", fill="both", expand=True)
    candidate_scroll.pack(side="right", fill="y")
    candidate_tree.bind("<Double-1>", lambda _event: call_async(read_selection_candidate_fields))

    unit_field_frame = ttk.Frame(unit)
    unit_field_frame.grid(row=8, column=0, columnspan=7, sticky="nsew", pady=(4, 0))
    unit_field_columns = ("category", "label", "value", "type", "address", "note")
    unit_field_tree = ttk.Treeview(unit_field_frame, columns=unit_field_columns, show="headings", height=11)
    for column, heading, width in (
        ("category", "分类", 80),
        ("label", "字段", 190),
        ("value", "当前值", 110),
        ("type", "类型", 60),
        ("address", "地址", 150),
        ("note", "备注", 260),
    ):
        unit_field_tree.heading(column, text=heading)
        unit_field_tree.column(column, width=width, anchor="w")
    unit_field_scroll = ttk.Scrollbar(unit_field_frame, orient="vertical", command=unit_field_tree.yview)
    unit_field_tree.configure(yscrollcommand=unit_field_scroll.set)
    unit_field_tree.pack(side="left", fill="both", expand=True)
    unit_field_scroll.pack(side="right", fill="y")

    def on_unit_field_select(_event) -> None:
        try:
            field = selected_unit_field()
        except Exception:
            return
        if field.writable:
            unit_field_target.set(field.value_text())

    unit_field_tree.bind("<<TreeviewSelect>>", on_unit_field_select)

    ttk.Label(unit, text="字段目标值").grid(row=9, column=0, sticky="w", pady=(8, 0))
    ttk.Entry(unit, textvariable=unit_field_target, width=16).grid(row=9, column=1, sticky="w", pady=(8, 0))
    ttk.Button(unit, text="写入字段", command=lambda: call_async(set_advanced_unit_field)).grid(row=9, column=2, sticky="w", pady=(8, 0))
    ttk.Button(unit, text="锁定字段", command=lambda: call_async(add_unit_lock)).grid(row=9, column=3, sticky="w", pady=(8, 0))
    for col in range(7):
        unit.columnconfigure(col, weight=1 if col == 6 else 0)
    unit.rowconfigure(8, weight=1)

    locks_tab = ttk.Frame(notebook, padding=10)
    notebook.add(locks_tab, text="锁定列表")
    lock_tree = ttk.Treeview(locks_tab, columns=("scope", "label", "value"), show="headings", height=15)
    for column, heading, width in (
        ("scope", "类型", 110),
        ("label", "项目", 240),
        ("value", "锁定值", 140),
    ):
        lock_tree.heading(column, text=heading)
        lock_tree.column(column, width=width, anchor="w")
    lock_scroll = ttk.Scrollbar(locks_tab, orient="vertical", command=lock_tree.yview)
    lock_tree.configure(yscrollcommand=lock_scroll.set)
    lock_tree.grid(row=0, column=0, columnspan=3, sticky="nsew")
    lock_scroll.grid(row=0, column=3, sticky="ns")
    ttk.Button(locks_tab, text="立即执行一次", command=lambda: call_async(lambda: (apply_locks_once(), "锁定项已执行一次")[1])).grid(
        row=1, column=0, sticky="w", pady=(10, 0)
    )
    ttk.Button(locks_tab, text="解锁所选", command=lambda: call_async(remove_selected_lock)).grid(row=1, column=1, sticky="w", pady=(10, 0))
    locks_tab.columnconfigure(0, weight=1)
    locks_tab.rowconfigure(0, weight=1)

    ability_fields_tab = ttk.Frame(notebook, padding=10)
    notebook.add(ability_fields_tab, text="技能字段")
    ability_field_toolbar = ttk.Frame(ability_fields_tab)
    ability_field_toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    ttk.Label(ability_field_toolbar, text="技能 ID").grid(row=0, column=0, sticky="w")
    ttk.Entry(
        ability_field_toolbar,
        textvariable=ability_field_rawcode,
        width=10,
    ).grid(row=0, column=1, sticky="w", padx=(6, 16))
    ttk.Label(ability_field_toolbar, text="字段等级").grid(row=0, column=2, sticky="w")
    ttk.Entry(
        ability_field_toolbar,
        textvariable=ability_field_level,
        width=7,
    ).grid(row=0, column=3, sticky="w", padx=(6, 16))
    ability_field_read_button = ttk.Button(
        ability_field_toolbar,
        text="读取可修改字段",
        command=lambda: call_async(
            read_ability_field_snapshot,
            operation_key="ability-field-read",
            busy_widget=ability_field_read_button,
            busy_text="正在解析技能实例并读取字段...",
        ),
    )
    ability_field_read_button.grid(row=0, column=4, sticky="w")
    ttk.Label(ability_field_toolbar, text="筛选").grid(
        row=0,
        column=5,
        sticky="e",
        padx=(24, 6),
    )
    ability_field_filter_entry = ttk.Entry(
        ability_field_toolbar,
        textvariable=ability_field_filter,
        width=24,
    )
    ability_field_filter_entry.grid(row=0, column=6, sticky="ew")
    ability_field_filter_entry.bind(
        "<KeyRelease>",
        lambda _event: refresh_ability_field_tree(),
    )
    ttk.Checkbutton(
        ability_field_toolbar,
        text="显示零值",
        variable=ability_field_show_zero,
        command=refresh_ability_field_tree,
    ).grid(row=0, column=7, padx=(14, 0))
    ttk.Checkbutton(
        ability_field_toolbar,
        text="显示未开放",
        variable=ability_field_show_unsupported,
        command=refresh_ability_field_tree,
    ).grid(row=0, column=8, padx=(10, 0))
    ability_field_toolbar.columnconfigure(6, weight=1)

    ability_field_table_frame = ttk.Frame(ability_fields_tab)
    ability_field_table_frame.grid(row=1, column=0, sticky="nsew")
    ability_field_columns = ("field", "type", "scope", "name", "value", "status")
    ability_field_tree = ttk.Treeview(
        ability_field_table_frame,
        columns=ability_field_columns,
        show="headings",
        height=18,
        selectmode="browse",
    )
    for column, heading, width, stretch in (
        ("field", "字段", 72, False),
        ("type", "类型", 68, False),
        ("scope", "范围", 78, False),
        ("name", "字段名称", 480, True),
        ("value", "当前值", 130, False),
        ("status", "状态", 90, False),
    ):
        ability_field_tree.heading(column, text=heading)
        ability_field_tree.column(
            column,
            width=width,
            minwidth=width,
            anchor="w",
            stretch=stretch,
        )
    ability_field_scroll = ttk.Scrollbar(
        ability_field_table_frame,
        orient="vertical",
        command=ability_field_tree.yview,
    )
    ability_field_tree.configure(yscrollcommand=ability_field_scroll.set)
    ability_field_tree.grid(row=0, column=0, sticky="nsew")
    ability_field_scroll.grid(row=0, column=1, sticky="ns")
    ability_field_table_frame.rowconfigure(0, weight=1)
    ability_field_table_frame.columnconfigure(0, weight=1)
    ability_field_tree.bind("<<TreeviewSelect>>", select_ability_field)

    ability_field_editor = ttk.Frame(ability_fields_tab)
    ability_field_editor.grid(row=2, column=0, sticky="ew", pady=(10, 0))
    ttk.Label(ability_field_editor, text="新值").grid(row=0, column=0, sticky="w")
    ttk.Entry(
        ability_field_editor,
        textvariable=ability_field_value,
        width=28,
    ).grid(row=0, column=1, sticky="w", padx=(6, 10))
    ability_field_write_button = ttk.Button(
        ability_field_editor,
        text="写入选中字段",
        command=ability_field_write_clicked,
    )
    ability_field_write_button.grid(row=0, column=2, sticky="w")
    ability_field_write_button.state(["disabled"])
    ttk.Label(
        ability_field_editor,
        textvariable=ability_field_detail,
        anchor="w",
    ).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0))
    ability_field_editor.columnconfigure(2, weight=1)
    ttk.Label(
        ability_fields_tab,
        textvariable=ability_field_summary,
        anchor="w",
    ).grid(row=3, column=0, sticky="ew", pady=(8, 0))
    ability_fields_tab.rowconfigure(1, weight=1)
    ability_fields_tab.columnconfigure(0, weight=1)

    elephant_tab = ttk.Frame(notebook, padding=8)
    notebook.add(elephant_tab, text="大象功能")
    elephant_notebook = ttk.Notebook(elephant_tab)
    elephant_notebook.pack(fill="both", expand=True)
    elephant_controls_tab = ttk.Frame(elephant_notebook, padding=10)
    elephant_hotkeys_tab = ttk.Frame(elephant_notebook, padding=10)
    elephant_notebook.add(elephant_controls_tab, text="功能面板")
    elephant_notebook.add(elephant_hotkeys_tab, text="快捷键功能")
    ttk.Button(
        elephant_controls_tab,
        text="初始化/验证大象功能",
        command=lambda: call_async(elephant_prewarm, "elephant:prewarm"),
    ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

    world_frame = ttk.LabelFrame(elephant_controls_tab, text="地图与游戏", padding=10)
    world_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=(0, 8))
    ttk.Button(
        world_frame,
        text="开图",
        command=lambda: call_async(
            lambda: elephant_action(lambda: trainer().set_map_revealed(True), "全地图视野已开启")
        ),
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=3)
    ttk.Button(
        world_frame,
        text="关图",
        command=lambda: call_async(
            lambda: elephant_action(lambda: trainer().set_map_revealed(False), "战争迷雾已恢复")
        ),
    ).grid(row=0, column=1, sticky="ew", pady=3)
    ttk.Button(
        world_frame,
        text="暂停游戏",
        command=lambda: call_async(lambda: elephant_set_game_paused(True)),
    ).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=3)
    ttk.Button(
        world_frame,
        text="恢复游戏",
        command=lambda: call_async(lambda: elephant_set_game_paused(False)),
    ).grid(row=1, column=1, sticky="ew", pady=3)
    ttk.Button(
        world_frame,
        text="开启和平模式",
        command=lambda: confirm_elephant_action(
            "和平模式",
            "将全部玩家设置为互相结盟，确定继续？",
            lambda: f"和平模式已开启，共更新 {trainer().set_peace_mode(True)} 项联盟关系",
        ),
    ).grid(row=2, column=0, sticky="ew", padx=(0, 6), pady=3)
    ttk.Button(
        world_frame,
        text="关闭和平模式",
        command=lambda: confirm_elephant_action(
            "关闭和平",
            "这会取消全部玩家之间的被动联盟，确定继续？",
            lambda: f"和平模式已关闭，共更新 {trainer().set_peace_mode(False)} 项联盟关系",
        ),
    ).grid(row=2, column=1, sticky="ew", pady=3)
    ttk.Button(
        world_frame,
        text="结束当前游戏",
        command=lambda: confirm_elephant_action(
            "结束游戏",
            "当前对局会立即结束，确定继续？",
            lambda: elephant_action(lambda: trainer().end_current_game(True), "已结束当前游戏"),
        ),
    ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 3))
    world_frame.columnconfigure(0, weight=1)
    world_frame.columnconfigure(1, weight=1)

    hero_frame = ttk.LabelFrame(elephant_controls_tab, text="英雄与单位状态", padding=10)
    hero_frame.grid(row=1, column=1, sticky="nsew", padx=6, pady=(0, 8))
    ttk.Label(hero_frame, text="英雄等级").grid(row=0, column=0, sticky="w", pady=3)
    ttk.Entry(hero_frame, textvariable=elephant_hero_level, width=9).grid(row=0, column=1, sticky="w", pady=3)
    ttk.Button(hero_frame, text="读取", command=lambda: call_async(elephant_read_hero_level)).grid(row=0, column=2, padx=4, pady=3)
    ttk.Button(hero_frame, text="设置", command=lambda: call_async(elephant_set_hero_level)).grid(row=0, column=3, pady=3)
    ttk.Button(
        hero_frame,
        text="无敌",
        command=lambda: call_async(
            lambda: elephant_action(lambda: trainer().set_selected_unit_invulnerable(True), "选中单位已设为无敌")
        ),
    ).grid(row=1, column=0, sticky="ew", pady=3)
    ttk.Button(
        hero_frame,
        text="取消无敌",
        command=lambda: call_async(
            lambda: elephant_action(lambda: trainer().set_selected_unit_invulnerable(False), "选中单位已取消无敌")
        ),
    ).grid(row=1, column=1, columnspan=2, sticky="ew", padx=(6, 0), pady=3)
    ttk.Button(
        hero_frame,
        text="重置冷却",
        command=lambda: call_async(
            lambda: elephant_action(trainer().reset_selected_unit_cooldown, "选中单位技能冷却已重置")
        ),
    ).grid(row=2, column=0, columnspan=3, sticky="ew", pady=3)
    ttk.Button(
        hero_frame,
        text="关闭碰撞",
        command=lambda: call_async(
            lambda: elephant_action(lambda: trainer().set_selected_unit_pathing(False), "选中单位碰撞已关闭")
        ),
    ).grid(row=3, column=0, sticky="ew", pady=3)
    ttk.Button(
        hero_frame,
        text="开启碰撞",
        command=lambda: call_async(
            lambda: elephant_action(lambda: trainer().set_selected_unit_pathing(True), "选中单位碰撞已开启")
        ),
    ).grid(row=3, column=1, columnspan=2, sticky="ew", padx=(6, 0), pady=3)
    ttk.Button(
        hero_frame,
        text="暂停单位",
        command=lambda: call_async(
            lambda: elephant_action(lambda: trainer().set_selected_unit_paused(True), "选中单位已暂停")
        ),
    ).grid(row=4, column=0, sticky="ew", pady=3)
    ttk.Button(
        hero_frame,
        text="恢复单位",
        command=lambda: call_async(
            lambda: elephant_action(lambda: trainer().set_selected_unit_paused(False), "选中单位已恢复")
        ),
    ).grid(row=4, column=1, columnspan=2, sticky="ew", padx=(6, 0), pady=3)
    ttk.Label(hero_frame, text="单位大小").grid(row=5, column=0, sticky="w", pady=(8, 3))
    ttk.Entry(hero_frame, textvariable=elephant_unit_scale, width=9).grid(row=5, column=1, sticky="w", pady=(8, 3))
    ttk.Button(hero_frame, text="设置大小", command=lambda: call_async(elephant_set_scale)).grid(row=5, column=2, columnspan=2, sticky="ew", pady=(8, 3))

    target_frame = ttk.LabelFrame(elephant_controls_tab, text="目标单位", padding=10)
    target_frame.grid(row=1, column=2, sticky="nsew", padx=(6, 0), pady=(0, 8))
    ttk.Button(
        target_frame,
        text="获取控制权",
        command=lambda: call_async(
            lambda: f"已取得选中单位控制权；本地玩家 handle=0x{trainer().take_selected_unit_control():x}"
        ),
    ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=3)
    ttk.Button(
        target_frame,
        text="击杀单位",
        command=lambda: confirm_elephant_action(
            "击杀单位",
            "确定击杀当前选中单位？",
            lambda: elephant_action(trainer().kill_selected_unit, "选中单位已被击杀"),
        ),
    ).grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=3)
    ttk.Button(
        target_frame,
        text="爆炸单位",
        command=lambda: confirm_elephant_action(
            "爆炸单位",
            "确定让当前选中单位爆炸死亡？",
            lambda: elephant_action(trainer().explode_selected_unit, "选中单位已爆炸"),
        ),
    ).grid(row=1, column=1, sticky="ew", pady=3)
    ttk.Button(
        target_frame,
        text="删除单位",
        command=lambda: confirm_elephant_action(
            "删除单位",
            "单位会从地图中直接删除，确定继续？",
            lambda: elephant_action(trainer().remove_selected_unit, "选中单位已删除"),
        ),
    ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=3)
    ttk.Button(
        target_frame,
        text="秒杀所属玩家全部单位",
        command=lambda: confirm_elephant_action(
            "秒杀阵营",
            "该单位所属玩家的全部单位都会死亡，确定继续？",
            elephant_kill_owner_units,
        ),
    ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 3))
    target_frame.columnconfigure(0, weight=1)
    target_frame.columnconfigure(1, weight=1)

    create_frame = ttk.LabelFrame(elephant_controls_tab, text="创建与物品", padding=10)
    create_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 6), pady=(0, 8))
    ttk.Label(create_frame, text="单位 ID").grid(row=0, column=0, sticky="w", pady=3)
    ttk.Entry(create_frame, textvariable=elephant_unit_rawcode, width=10).grid(row=0, column=1, sticky="w", pady=3)
    ttk.Button(create_frame, text="创建单位", command=lambda: call_async(lambda: elephant_create_unit(False))).grid(row=0, column=2, padx=(6, 0), pady=3)
    ttk.Button(create_frame, text="复制选中单位给自己", command=lambda: call_async(lambda: elephant_create_unit(True))).grid(
        row=1, column=0, columnspan=3, sticky="ew", pady=3
    )
    ttk.Label(create_frame, text="物品 ID").grid(row=2, column=0, sticky="w", pady=(10, 3))
    ttk.Entry(create_frame, textvariable=elephant_item_rawcode, width=10).grid(row=2, column=1, sticky="w", pady=(10, 3))
    ttk.Button(create_frame, text="添加物品", command=lambda: call_async(elephant_add_item)).grid(row=2, column=2, padx=(6, 0), pady=(10, 3))
    ttk.Button(
        create_frame,
        text="清空背包",
        command=lambda: confirm_elephant_action(
            "清空背包",
            "当前选中单位背包内的物品会被删除，确定继续？",
            elephant_clear_inventory,
        ),
    ).grid(row=3, column=0, columnspan=3, sticky="ew", pady=3)

    ability_frame = ttk.LabelFrame(elephant_controls_tab, text="技能", padding=10)
    ability_frame.grid(row=2, column=1, sticky="nsew", padx=6, pady=(0, 8))
    ttk.Label(ability_frame, text="技能 ID").grid(row=0, column=0, sticky="w", pady=3)
    ttk.Entry(ability_frame, textvariable=elephant_ability_rawcode, width=10).grid(row=0, column=1, sticky="w", pady=3)
    ttk.Label(ability_frame, text="等级").grid(row=0, column=2, sticky="w", padx=(8, 0), pady=3)
    ttk.Entry(ability_frame, textvariable=elephant_ability_level, width=7).grid(row=0, column=3, sticky="w", pady=3)
    ttk.Button(ability_frame, text="添加技能", command=lambda: call_async(elephant_add_ability)).grid(row=1, column=0, columnspan=2, sticky="ew", pady=3)
    ttk.Button(ability_frame, text="删除技能", command=lambda: call_async(elephant_remove_ability)).grid(row=1, column=2, columnspan=2, sticky="ew", padx=(6, 0), pady=3)
    ttk.Button(ability_frame, text="设置技能等级", command=lambda: call_async(elephant_set_ability_level)).grid(
        row=2, column=0, columnspan=4, sticky="ew", pady=3
    )

    player_frame = ttk.LabelFrame(elephant_controls_tab, text="玩家科技与经验", padding=10)
    player_frame.grid(row=2, column=2, sticky="nsew", padx=(6, 0), pady=(0, 8))
    ttk.Label(player_frame, text="科技 ID").grid(row=0, column=0, sticky="w", pady=3)
    ttk.Entry(player_frame, textvariable=elephant_tech_rawcode, width=10).grid(row=0, column=1, sticky="w", pady=3)
    ttk.Label(player_frame, text="等级").grid(row=0, column=2, sticky="w", padx=(8, 0), pady=3)
    ttk.Entry(player_frame, textvariable=elephant_tech_level, width=7).grid(row=0, column=3, sticky="w", pady=3)
    ttk.Button(player_frame, text="设置科技", command=lambda: call_async(elephant_set_tech)).grid(
        row=1, column=0, columnspan=4, sticky="ew", pady=3
    )
    ttk.Label(player_frame, text="经验倍率").grid(row=2, column=0, sticky="w", pady=(10, 3))
    ttk.Entry(player_frame, textvariable=elephant_xp_rate, width=10).grid(row=2, column=1, sticky="w", pady=(10, 3))
    ttk.Button(player_frame, text="设置倍率", command=lambda: call_async(elephant_set_xp_rate)).grid(
        row=2, column=2, columnspan=2, sticky="ew", padx=(6, 0), pady=(10, 3)
    )

    for column in range(3):
        elephant_controls_tab.columnconfigure(column, weight=1, uniform="elephant")
    elephant_controls_tab.rowconfigure(1, weight=1)
    elephant_controls_tab.rowconfigure(2, weight=1)

    hotkey_toolbar = ttk.Frame(elephant_hotkeys_tab)
    hotkey_toolbar.pack(fill="x", pady=(0, 8))
    ttk.Checkbutton(
        hotkey_toolbar,
        text="启用全局快捷键",
        variable=elephant_hotkeys_enabled,
        command=refresh_elephant_hotkeys,
    ).pack(side="left")
    ttk.Button(
        hotkey_toolbar,
        text="全选可用",
        command=lambda: set_all_elephant_hotkeys(True),
    ).pack(side="left", padx=(12, 4))
    ttk.Button(
        hotkey_toolbar,
        text="清空",
        command=lambda: set_all_elephant_hotkeys(False),
    ).pack(side="left")
    ttk.Label(hotkey_toolbar, textvariable=elephant_hotkey_status).pack(side="right")

    hotkey_canvas = tk.Canvas(
        elephant_hotkeys_tab,
        borderwidth=0,
        highlightthickness=0,
        background=ttk.Style().lookup("TFrame", "background") or root.cget("background"),
    )
    hotkey_scroll = ttk.Scrollbar(elephant_hotkeys_tab, orient="vertical", command=hotkey_canvas.yview)
    hotkey_canvas.configure(yscrollcommand=hotkey_scroll.set)
    hotkey_canvas.pack(side="left", fill="both", expand=True)
    hotkey_scroll.pack(side="right", fill="y")
    hotkey_body = ttk.Frame(hotkey_canvas)
    hotkey_window = hotkey_canvas.create_window((0, 0), window=hotkey_body, anchor="nw")

    def resize_hotkey_body(event) -> None:
        hotkey_canvas.itemconfigure(hotkey_window, width=event.width)

    def update_hotkey_scrollregion(_event=None) -> None:
        hotkey_canvas.configure(scrollregion=hotkey_canvas.bbox("all"))

    hotkey_canvas.bind("<Configure>", resize_hotkey_body)
    hotkey_body.bind("<Configure>", update_hotkey_scrollregion)
    hotkey_parameter_vars = {
        "hero_level": elephant_hero_level,
        "unit_scale": elephant_unit_scale,
        "item_charges": elephant_item_charges,
        "add_ability": elephant_ability_rawcode,
        "add_resources": elephant_resource_amount,
        "mass_clone": elephant_mass_clone_count,
        "ability_level": elephant_ability_level,
        "remove_ability": elephant_ability_rawcode,
        "reinforcements": elephant_reinforcement_rawcode,
        "preset_item": elephant_preset_item_rawcode,
        "preset_tech": elephant_preset_tech_rawcode,
        "hero_attributes": elephant_hero_attributes,
        "skill_points": elephant_skill_points,
        "xp_rate": elephant_xp_rate,
        "reset_ability": elephant_reset_ability_rawcode,
        "fullscreen_auto": elephant_auto_effect_count,
    }
    hotkeys_per_column = 15
    for index, spec in enumerate(ELEPHANT_HOTKEY_SPECS):
        column = index // hotkeys_per_column
        row = index % hotkeys_per_column
        item = ttk.Frame(hotkey_body)
        item.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 12, 0), pady=2)
        check = ttk.Checkbutton(
            item,
            text=spec.label,
            variable=elephant_hotkey_checks[spec.name],
            command=refresh_elephant_hotkeys,
        )
        check.grid(row=0, column=0, sticky="w")
        parameter = hotkey_parameter_vars.get(spec.name)
        if parameter is not None:
            ttk.Entry(item, textvariable=parameter, width=8).grid(row=0, column=1, sticky="e", padx=(6, 0))
        item.columnconfigure(0, weight=1)
    for column in range(3):
        hotkey_body.columnconfigure(column, weight=1, uniform="elephant-hotkeys")

    ttk.Label(outer, textvariable=status, anchor="w", wraplength=1000).pack(fill="x", pady=(0, 2))

    def init() -> None:
        try:
            msg = connect()
            set_status(msg)
            try:
                refresh_resources()
            except Exception:
                pass
            root.after(
                300,
                lambda: call_async(prewarm_selection_cache, busy_text="正在预热，请稍候..."),
            )
        except Exception as exc:
            set_status(f"未连接：{exc}")

    root.after(100, init)
    root.after(1500, lock_tick)
    root.mainloop()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Warcraft III Reforged trainer")
    parser.add_argument("--pid", type=int, help="Warcraft III.exe PID")
    parser.add_argument("--status", action="store_true", help="Print process/resource status")
    parser.add_argument("--list-resources", action="store_true", help="Print all detected player/resource groups")
    parser.add_argument("--focus", action="store_true", help="Bring Warcraft III to foreground")
    parser.add_argument("--send-cheat", help="Send a raw Warcraft III cheat command")
    parser.add_argument("--add-gold", type=int)
    parser.add_argument("--add-lumber", type=int)
    parser.add_argument("--add-both", type=int, help="greedisgood delta")
    parser.add_argument("--set-gold", type=int)
    parser.add_argument("--set-lumber", type=int)
    parser.add_argument("--current-gold", type=int, help="Fallback current gold for cache calibration")
    parser.add_argument("--current-lumber", type=int, help="Fallback current lumber for cache calibration")
    parser.add_argument("--current-food", type=int, help="Fallback current food used for resource calibration")
    parser.add_argument("--current-food-cap", type=int, help="Fallback current food cap for resource calibration")
    parser.add_argument("--set-food-used", type=int)
    parser.add_argument("--set-food-cap", type=int)
    parser.add_argument("--current-hp", type=float)
    parser.add_argument("--current-mp", type=float)
    parser.add_argument("--current-hp-max", type=float)
    parser.add_argument("--current-mp-max", type=float)
    parser.add_argument("--set-hp", type=float)
    parser.add_argument("--set-mp", type=float)
    parser.add_argument("--set-hp-regen", type=float)
    parser.add_argument("--set-mp-regen", type=float)
    parser.add_argument("--set-x", type=float)
    parser.add_argument("--set-y", type=float)
    parser.add_argument("--read-selected", action="store_true", help="Read current selected unit through the selection handle")
    parser.add_argument("--read-selected-fields", action="store_true", help="Read all supported fields from the current selected unit")
    parser.add_argument("--list-selection-candidates", action="store_true", help="List plausible selected-unit candidates with full clues")
    parser.add_argument("--unit-identity", help="Manual candidate identity: HANDLE,OWNER,UNIT or handle=...,owner=...,unit=...")
    parser.add_argument("--verify-selection-locator", action="store_true", help="Verify selected-unit locator uses handle -> owner -> unit chain")
    parser.add_argument("--native-selection-probe", action="store_true", help="Locate selected unit through native-disassembled selection manager")
    parser.add_argument("--jass-selection-probe", action="store_true", help="Experiment: call JASS selection natives and print raw/mapped result")
    parser.add_argument("--jass-locate-selected", action="store_true", help="Experiment: locate current selected unit through JASS selection natives")
    parser.add_argument("--set-unit-field", action="append", default=[], metavar="KEY=VALUE", help="Write a supported selected-unit field by key")
    parser.add_argument("--set-xp", type=int)
    parser.add_argument("--set-skill-points", type=int)
    parser.add_argument("--set-base-str", type=int)
    parser.add_argument("--set-base-agi", type=int)
    parser.add_argument("--set-int", type=float)
    parser.add_argument("--set-intelligence", type=float)
    parser.add_argument("--set-add-str", type=float)
    parser.add_argument("--set-add-int", type=float)
    parser.add_argument("--set-add-agi", type=float)
    parser.add_argument("--set-move-speed", type=float)
    parser.add_argument("--set-defense", type=float)
    parser.add_argument("--set-armor", type=float)
    parser.add_argument("--set-armor-type", type=int)
    parser.add_argument("--set-attack-type", type=int)
    parser.add_argument("--set-attack-speed", type=float)
    parser.add_argument("--set-attack-damage-level", type=int)
    parser.add_argument("--set-attack-damage-item", type=int)
    parser.add_argument("--gui", action="store_true", help="Launch GUI even when CLI flags are present")
    return parser


def run_cli(args: argparse.Namespace) -> int:
    t = War3Trainer(args.pid)
    manual_identity = parse_unit_identity(args.unit_identity) if args.unit_identity else None
    print(f"Warcraft III PID={t.pid} HWND=0x{t.hwnd:x}")
    if args.focus:
        t.focus()
        print("focused Warcraft III")
    if args.status:
        try:
            cache = t.read_resource_cache(
                args.current_gold,
                args.current_lumber,
                args.current_food,
                args.current_food_cap,
            )
            food_text = ""
            if cache.food_used_address or cache.food_cap_address:
                food_text = (
                    f" food={cache.food_used}/{cache.food_cap}"
                    f" food_used_addr=0x{cache.food_used_address:x}"
                    f" food_cap_addr=0x{cache.food_cap_address:x}"
                )
            print(
                f"resources gold={cache.gold} lumber={cache.lumber}{food_text} "
                f"gold_addr=0x{cache.gold_address:x} lumber_addr=0x{cache.lumber_address:x} "
                f"source={cache.source}"
            )
        except Exception as exc:
            print(f"resources unavailable: {exc}")
    if args.list_resources:
        try:
            caches = t.list_resource_caches(
                args.current_gold,
                args.current_lumber,
                args.current_food,
                args.current_food_cap,
            )
            if not caches:
                print("resource_groups count=0")
            for index, cache in enumerate(caches, 1):
                food_text = ""
                if cache.food_used_address or cache.food_cap_address:
                    food_text = (
                        f" food={cache.food_used}/{cache.food_cap}"
                        f" food_used_addr=0x{cache.food_used_address:x}"
                        f" food_cap_addr=0x{cache.food_cap_address:x}"
                    )
                print(
                    f"resource_group index={index} gold={cache.gold} lumber={cache.lumber}{food_text} "
                    f"gold_addr=0x{cache.gold_address:x} lumber_addr=0x{cache.lumber_address:x} "
                    f"owner=0x{cache.owner_key:x} start_kind=0x{cache.block_start_kind:x} "
                    f"header={cache.header_value} player={cache.player_value} score={cache.score}"
                )
        except Exception as exc:
            print(f"resource_groups unavailable: {exc}")
    if args.send_cheat:
        t.send_cheat(args.send_cheat)
        print(f"sent cheat: {args.send_cheat}")
    if args.add_gold is not None:
        t.add_gold(args.add_gold)
        print(f"gold delta sent: {args.add_gold:+d}")
    if args.add_lumber is not None:
        t.add_lumber(args.add_lumber)
        print(f"lumber delta sent: {args.add_lumber:+d}")
    if args.add_both is not None:
        t.add_gold_and_lumber(args.add_both)
        print(f"gold/lumber delta sent: {args.add_both:+d}")
    if args.set_gold is not None:
        delta = t.set_gold(args.set_gold, args.current_gold, args.current_lumber)
        print(f"gold set delta={delta:+d}")
    if args.set_lumber is not None:
        delta = t.set_lumber(args.set_lumber, args.current_gold, args.current_lumber)
        print(f"lumber set delta={delta:+d}")
    if args.set_food_used is not None or args.set_food_cap is not None:
        cache = t.set_food(
            args.set_food_used,
            args.set_food_cap,
            args.current_gold,
            args.current_lumber,
            args.current_food,
            args.current_food_cap,
        )
        print(
            f"food written food={cache.food_used}/{cache.food_cap} "
            f"food_used_addr=0x{cache.food_used_address:x} food_cap_addr=0x{cache.food_cap_address:x} "
            f"source={cache.source}"
        )
    if args.read_selected:
        if manual_identity is not None:
            panel, cand, _fields = t.read_unit_fields_by_identity(*manual_identity)
        else:
            panel, cand = t.locate_current_selected_unit()
        pos_text = ""
        with ProcessMemory(t.pid) as pm:
            pos = t._position_from_candidate(pm, cand)
            regen_text = ""
            if cand.hp_regen_address:
                regen_text += f" hp_regen={pm.read_f32(cand.hp_regen_address):.6g}"
            if cand.mp_regen_address:
                regen_text += f" mp_regen={pm.read_f32(cand.mp_regen_address):.6g}"
        if pos is not None:
            pos_text = f" x={pos[0]:.3f} y={pos[1]:.3f}"
        print(
            f"selected memory hp={panel.hp_text} mp={panel.mp_text} "
            f"base=0x{cand.base:x} unit=0x{cand.unit_address:x} hp_cur=0x{cand.hp_current_address:x} "
            f"hp_max=0x{cand.hp_max_address:x} hp_regen_addr=0x{cand.hp_regen_address:x} "
            f"mp_cur=0x{cand.mp_current_address:x} mp_max=0x{cand.mp_max_address:x} "
            f"mp_regen_addr=0x{cand.mp_regen_address:x}{regen_text}{pos_text} "
            f"source={cand.selection_source or 'unknown'} note={cand.note}"
        )
    if args.read_selected_fields:
        if manual_identity is not None:
            panel, cand, fields = t.read_unit_fields_by_identity(*manual_identity)
        else:
            panel, cand, fields = t.read_selected_unit_fields()
        print(
            f"selected fields hp={panel.hp_text} mp={panel.mp_text} "
            f"owner=0x{cand.owner_address:x} handle=0x{cand.handle:x} "
            f"unit=0x{cand.unit_address:x} source={cand.selection_source or 'unknown'} note={cand.note}"
        )
        for field in fields:
            writable = "rw" if field.writable else "ro"
            note = f" note={field.note}" if field.note else ""
            print(
                f"{field.key} [{field.category}] {field.label}={field.value_text()} "
                f"type={field.value_type} addr=0x{field.address:x} {writable}{note}"
            )
    if args.list_selection_candidates:
        summaries = t.list_selection_candidates(
            extra_identities=[manual_identity] if manual_identity is not None else None
        )
        print(f"selection_candidates count={len(summaries)}")
        for index, summary in enumerate(summaries, 1):
            print(t.selection_candidate_line(summary, index))
    if args.verify_selection_locator:
        with ProcessMemory(t.pid) as pm:
            cand = t.locate_selected_unit_by_handle(pm, allow_deep_scan=True)
            owner_handle = pm.read_u64(cand.owner_address + 0x20) if cand.owner_address else 0
            unit_handle = pm.read_u64(cand.unit_address + 0x18) if cand.unit_address else 0
            status = (
                cand.handle != 0
                and owner_handle == cand.handle
                and unit_handle == cand.handle
                and cand.owner_address != 0
                and cand.unit_address != 0
                and cand.selection_source == "memory"
                and (cand.note.startswith("selected_handle=") or cand.note.startswith("selected_unit_slot="))
            )
        print(
            f"selection_locator={'OK' if status else 'FAILED'} "
            f"mode={cand.selection_source or 'unknown'} handle=0x{cand.handle:x} "
            f"owner=0x{cand.owner_address:x} owner_handle=0x{owner_handle:x} "
            f"unit=0x{cand.unit_address:x} unit_handle=0x{unit_handle:x} "
            f"slot=0x{cand.selection_slot_address:x} "
            f"slot_note={cand.note}"
        )
        if not status:
            raise RuntimeError("选中单位定位链验证失败")
    if args.native_selection_probe:
        probe = t.probe_native_selection_manager()
        mapped = "yes" if probe.candidate is not None else "no"
        detail = ""
        if probe.candidate is not None:
            detail = (
                f" handle=0x{probe.candidate.handle:x}"
                f" owner=0x{probe.candidate.owner_address:x}"
                f" unit=0x{probe.candidate.unit_address:x}"
                f" note={probe.candidate.note}"
            )
        print(
            f"native_selection offset=0x{probe.selection_manager_offset:x}"
            f" list=0x{probe.primary_list_offset:x}/0x{probe.alternate_list_offset:x}"
            f" is_unit_selected=0x{probe.is_unit_selected_handler:x}"
            f" group_enum=0x{probe.group_enum_selected_handler:x}"
            f" mapped={mapped}{detail}"
        )
    if args.jass_selection_probe:
        probe = t.probe_jass_selected_unit()
        mapped = "yes" if probe.candidate is not None else "no"
        detail = ""
        if probe.candidate is not None:
            detail = (
                f" handle=0x{probe.candidate.handle:x} owner=0x{probe.candidate.owner_address:x}"
                f" unit=0x{probe.candidate.unit_address:x} note={probe.candidate.note}"
            )
        print(
            f"jass_selection unit=0x{probe.unit_handle:x} handle_id=0x{probe.handle_id:x} "
            f"player=0x{probe.player_handle:x} mapped={mapped}{detail}"
        )
    if args.jass_locate_selected:
        cand = t.locate_selected_unit_by_jass_native()
        with ProcessMemory(t.pid) as pm:
            panel = t._panel_from_candidate(pm, cand)
            pos = t._position_from_candidate(pm, cand)
        pos_text = f" x={pos[0]:.3f} y={pos[1]:.3f}" if pos is not None else ""
        print(
            f"jass_selected hp={panel.hp_text} mp={panel.mp_text}{pos_text} "
            f"handle=0x{cand.handle:x} owner=0x{cand.owner_address:x} unit=0x{cand.unit_address:x} "
            f"note={cand.note}"
        )
    if (
        args.set_hp is not None
        or args.set_mp is not None
        or args.set_hp_regen is not None
        or args.set_mp_regen is not None
        or args.set_x is not None
        or args.set_y is not None
    ):
        if manual_identity is not None:
            panel, _cand, _fields = t.read_unit_fields_by_identity(*manual_identity)
            cand = t.set_unit_by_identity(
                *manual_identity,
                args.current_hp if args.current_hp is not None else panel.current_hp,
                args.current_mp if args.current_mp is not None else panel.current_mp,
                args.set_hp,
                args.set_mp,
                args.current_hp_max if args.current_hp_max is not None else panel.max_hp,
                args.current_mp_max if args.current_mp_max is not None else panel.max_mp,
                args.set_x,
                args.set_y,
                args.set_hp_regen,
                args.set_mp_regen,
            )
        elif args.current_hp is None:
            panel, cand = t.locate_current_selected_unit()
            cand = t.set_selected_unit(
                panel.current_hp,
                panel.current_mp,
                args.set_hp,
                args.set_mp,
                panel.max_hp,
                panel.max_mp,
                args.set_x,
                args.set_y,
                args.set_hp_regen,
                args.set_mp_regen,
            )
        else:
            cand = t.set_selected_unit(
                args.current_hp,
                args.current_mp,
                args.set_hp,
                args.set_mp,
                args.current_hp_max,
                args.current_mp_max,
                args.set_x,
                args.set_y,
                args.set_hp_regen,
                args.set_mp_regen,
            )
        pos_text = ""
        with ProcessMemory(t.pid) as pm:
            pos = t._position_from_candidate(pm, cand)
            regen_text = ""
            if cand.hp_regen_address:
                regen_text += f" hp_regen={pm.read_f32(cand.hp_regen_address):.6g}"
            if cand.mp_regen_address:
                regen_text += f" mp_regen={pm.read_f32(cand.mp_regen_address):.6g}"
        if pos is not None:
            pos_text = f" x={pos[0]:.3f} y={pos[1]:.3f}"
        print(
            "selected unit written "
            f"base=0x{cand.base:x} unit=0x{cand.unit_address:x} hp_cur=0x{cand.hp_current_address:x} "
            f"hp_max=0x{cand.hp_max_address:x} hp_regen_addr=0x{cand.hp_regen_address:x} "
            f"mp_cur=0x{cand.mp_current_address:x} mp_max=0x{cand.mp_max_address:x} "
            f"mp_regen_addr=0x{cand.mp_regen_address:x}{regen_text}{pos_text} "
            f"source={cand.selection_source or 'unknown'} note={cand.note}"
        )
    unit_specs: list[MemoryWriteSpec] = []
    for arg_name, field_key in t.CLI_UNIT_FIELD_KEYS.items():
        value = getattr(args, f"set_{arg_name}")
        if value is not None:
            unit_specs.append(MemoryWriteSpec(field_key, 0, "", value))
    for assignment in args.set_unit_field:
        if "=" not in assignment:
            raise ValueError("--set-unit-field 格式应为 KEY=VALUE")
        key, value = assignment.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError("--set-unit-field 缺少字段名")
        unit_specs.append(MemoryWriteSpec(key, 0, "", value))
    if unit_specs:
        if manual_identity is not None:
            written = [
                t.write_unit_field_by_identity(*manual_identity, spec.label, spec.value)
                for spec in unit_specs
            ]
        else:
            written = t.write_selected_unit_fields(unit_specs)
        for field in written:
            note = f" note={field.note}" if field.note else ""
            print(
                f"unit field written {field.key} {field.label}={field.value_text()} "
                f"type={field.value_type} addr=0x{field.address:x}{note}"
            )
    return 0


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    has_cli_action = any(
        [
            args.status,
            args.list_resources,
            args.focus,
            args.send_cheat,
            args.add_gold is not None,
            args.add_lumber is not None,
            args.add_both is not None,
            args.set_gold is not None,
            args.set_lumber is not None,
            args.set_food_used is not None,
            args.set_food_cap is not None,
            args.read_selected,
            args.read_selected_fields,
            args.list_selection_candidates,
            bool(args.unit_identity),
            args.verify_selection_locator,
            args.native_selection_probe,
            args.jass_selection_probe,
            args.jass_locate_selected,
            args.set_hp is not None,
            args.set_mp is not None,
            args.set_hp_regen is not None,
            args.set_mp_regen is not None,
            args.set_x is not None,
            args.set_y is not None,
            bool(args.set_unit_field),
            args.set_xp is not None,
            args.set_skill_points is not None,
            args.set_base_str is not None,
            args.set_base_agi is not None,
            args.set_int is not None,
            args.set_intelligence is not None,
            args.set_add_str is not None,
            args.set_add_int is not None,
            args.set_add_agi is not None,
            args.set_move_speed is not None,
            args.set_defense is not None,
            args.set_armor is not None,
            args.set_armor_type is not None,
            args.set_attack_type is not None,
            args.set_attack_speed is not None,
            args.set_attack_damage_level is not None,
            args.set_attack_damage_item is not None,
        ]
    )
    if args.gui or not has_cli_action:
        run_gui()
        return 0
    return run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())

