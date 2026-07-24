"""Reforged command-slot bridge using validated Warcraft native handlers."""

from __future__ import annotations

import ctypes
from bisect import bisect_right
import struct
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


if sys.platform != "win32":
    raise RuntimeError("The Warcraft native bridge requires Windows")


PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
MEM_IMAGE = 0x1000000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100
READABLE_PROTECTS = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}
EXECUTABLE_PROTECTS = {0x10, 0x20, 0x40, 0x80}
WH_CALLWNDPROC = 4
WM_NULL = 0x0000
SMTO_ABORTIFHUNG = 0x0002

HOTKEY_MAGIC = 0x4B485257
HOTKEY_VERSION = 3
STATUS_PENDING = 1
STATUS_OK = 2
MAX_OPS = 16
OP_CLICK_ORIGIN_FRAME = 1
OP_QUERY_COMMAND_CONTEXT = 2
OP_QUERY_SELECTION_CONTEXT = 3
OP_OVERRIDE_COMMAND_HOTKEY = 4
OP_REFRESH_COMMAND_BAR = 5

HOTKEY_FLAG_HERO_ONLY = 1
HOTKEY_FLAG_QUICK_CAST = 2
HOTKEY_FLAG_SAVE = 4

ORIGIN_FRAME_COMMAND_BUTTON = 1
ORIGIN_FRAME_ITEM_BUTTON = 7
ORIGIN_FRAME_PORTRAIT = 16

HEADER_STRUCT = struct.Struct("<IIIIQII")
OP_STRUCT = struct.Struct("<IIQQQQII")
COMMAND_SIZE = HEADER_STRUCT.size + OP_STRUCT.size * MAX_OPS

NATIVE_NAMES = (
    "ConvertOriginFrameType",
    "BlzGetOriginFrame",
    "BlzFrameClick",
    "CreateGroup",
    "GetLocalPlayer",
    "GroupEnumUnitsSelected",
    "FirstOfGroup",
    "DestroyGroup",
    "GetOwningPlayer",
    "GetPlayerId",
)


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

kernel32.OpenProcess.argtypes = (ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong)
kernel32.OpenProcess.restype = ctypes.c_void_p
kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
kernel32.CloseHandle.restype = ctypes.c_bool
kernel32.ReadProcessMemory.argtypes = (
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
)
kernel32.ReadProcessMemory.restype = ctypes.c_bool
kernel32.VirtualQueryEx.argtypes = (
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
)
kernel32.VirtualQueryEx.restype = ctypes.c_size_t
kernel32.LoadLibraryW.argtypes = (ctypes.c_wchar_p,)
kernel32.LoadLibraryW.restype = ctypes.c_void_p
kernel32.GetProcAddress.argtypes = (ctypes.c_void_p, ctypes.c_char_p)
kernel32.GetProcAddress.restype = ctypes.c_void_p
kernel32.FreeLibrary.argtypes = (ctypes.c_void_p,)
kernel32.FreeLibrary.restype = ctypes.c_bool
user32.GetWindowThreadProcessId.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong))
user32.GetWindowThreadProcessId.restype = ctypes.c_ulong
user32.SetWindowsHookExW.argtypes = (ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)
user32.SetWindowsHookExW.restype = ctypes.c_void_p
user32.UnhookWindowsHookEx.argtypes = (ctypes.c_void_p,)
user32.UnhookWindowsHookEx.restype = ctypes.c_bool
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


class MEMORY_BASIC_INFORMATION64(ctypes.Structure):
    _fields_ = (
        ("BaseAddress", ctypes.c_ulonglong),
        ("AllocationBase", ctypes.c_ulonglong),
        ("AllocationProtect", ctypes.c_ulong),
        ("__alignment1", ctypes.c_ulong),
        ("RegionSize", ctypes.c_ulonglong),
        ("State", ctypes.c_ulong),
        ("Protect", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
        ("__alignment2", ctypes.c_ulong),
    )


@dataclass(frozen=True)
class Region:
    base: int
    size: int
    protect: int
    typ: int


@dataclass(frozen=True)
class NativeHandler:
    name: str
    record_address: int
    handler_address: int


@dataclass(frozen=True)
class CommandBarInternals:
    game_ui_get: int
    command_bar_offset: int
    submenu_link_offset: int
    set_hotkey: int | None = None
    set_hotkey_hero_only: int | None = None
    set_hotkey_quick_cast: int | None = None
    save_hotkeys: int | None = None
    refresh_command_bar: int | None = None
    overriding_hotkey_enabled: int | None = None


@dataclass(frozen=True)
class CommandContext:
    submenu_active: bool


@dataclass(frozen=True)
class SelectionContext:
    has_selection: bool
    neutral_selected: bool
    owner_player_id: int | None


class ProcessMemory:
    def __init__(self, pid: int):
        self.handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, int(pid))
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self._regions: list[Region] | None = None

    def close(self) -> None:
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self) -> "ProcessMemory":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def regions(self) -> list[Region]:
        if self._regions is not None:
            return list(self._regions)
        result: list[Region] = []
        info = MEMORY_BASIC_INFORMATION64()
        address = 0
        while address < 0x7FFFFFFFFFFF:
            read = kernel32.VirtualQueryEx(
                self.handle,
                ctypes.c_void_p(address),
                ctypes.byref(info),
                ctypes.sizeof(info),
            )
            if not read:
                break
            protection = int(info.Protect)
            if (
                int(info.State) == MEM_COMMIT
                and not protection & (PAGE_NOACCESS | PAGE_GUARD)
                and protection & 0xFF in READABLE_PROTECTS
            ):
                result.append(Region(int(info.BaseAddress), int(info.RegionSize), protection, int(info.Type)))
            next_address = int(info.BaseAddress) + int(info.RegionSize)
            if next_address <= address:
                break
            address = next_address
        self._regions = result
        return list(result)

    def read(self, address: int, size: int) -> bytes:
        buffer = ctypes.create_string_buffer(size)
        read = ctypes.c_size_t()
        if not kernel32.ReadProcessMemory(
            self.handle,
            ctypes.c_void_p(address),
            buffer,
            size,
            ctypes.byref(read),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer.raw[: read.value]

    def read_u64(self, address: int) -> int:
        return struct.unpack("<Q", self.read(address, 8))[0]

    def scan_private(self, pattern: bytes, *, max_region_size: int = 4 * 1024 * 1024) -> list[int]:
        hits: list[int] = []
        overlap = max(0, len(pattern) - 1)
        for region in self.regions():
            if region.typ != MEM_PRIVATE or region.size > max_region_size:
                continue
            offset = 0
            tail = b""
            while offset < region.size:
                size = min(1024 * 1024, region.size - offset)
                try:
                    block = self.read(region.base + offset, size)
                except OSError:
                    offset += size
                    tail = b""
                    continue
                data = tail + block
                start = 0
                while True:
                    index = data.find(pattern, start)
                    if index < 0:
                        break
                    address = region.base + offset - len(tail) + index
                    if address >= region.base:
                        hits.append(address)
                    start = index + 1
                tail = data[-overlap:] if overlap else b""
                offset += size
        return hits


class NativeResolver:
    def __init__(self):
        self._cache: dict[tuple[int, str], NativeHandler] = {}

    @staticmethod
    def _region_for_address(regions: list[Region], address: int) -> Region | None:
        return next((region for region in regions if region.base <= address < region.base + region.size), None)

    @classmethod
    def _is_executable_address(cls, regions: list[Region], address: int) -> bool:
        region = cls._region_for_address(regions, address)
        return bool(region and region.protect & 0xFF in EXECUTABLE_PROTECTS)

    @staticmethod
    def _sane_pointer(value: int) -> bool:
        return 0x10000 <= value <= 0x7FFFFFFFFFFF

    def _decode_record_name(
        self,
        memory: ProcessMemory,
        blob: bytes,
        base: int,
        record_offset: int,
    ) -> str | None:
        if record_offset < 8 or record_offset + 24 > len(blob):
            return None
        pointer, size, capacity = struct.unpack_from("<QQQ", blob, record_offset)
        if not 0 < size < 128:
            return None
        record_address = base + record_offset
        inline_capacity = capacity & 0xFF
        try:
            if pointer == record_address + 0x18 and inline_capacity >= size:
                end = record_offset + 0x18 + int(size)
                if end > len(blob):
                    return None
                data = blob[record_offset + 0x18 : end]
            else:
                if not self._sane_pointer(pointer) or not size <= inline_capacity < 0x80:
                    return None
                data = memory.read(pointer, int(size))
            return data.decode("ascii")
        except (OSError, UnicodeDecodeError):
            return None

    def resolve(self, pid: int, names: Iterable[str] = NATIVE_NAMES) -> dict[str, NativeHandler]:
        wanted = set(names)
        cached = {name: self._cache[(pid, name)] for name in wanted if (pid, name) in self._cache}
        if wanted.issubset(cached):
            return cached
        with ProcessMemory(pid) as memory:
            regions = memory.regions()
            table_candidates: dict[tuple[int, int], Region] = {}
            for hit in memory.scan_private(b"UnitAddAbility\0", max_region_size=4 * 1024 * 1024):
                region = self._region_for_address(regions, hit)
                if region is None:
                    continue
                record = hit - 0x18
                try:
                    handler = memory.read_u64(record - 8)
                    pointer = memory.read_u64(record)
                    size = memory.read_u64(record + 8)
                except OSError:
                    continue
                if pointer == hit and size == len("UnitAddAbility") and self._is_executable_address(regions, handler):
                    table_candidates[(region.base, region.size)] = region
            if not table_candidates:
                raise RuntimeError("Warcraft III native table was not found")
            scan_ranges: list[tuple[int, int]] = []
            for anchor in sorted(table_candidates.values(), key=lambda value: value.base):
                start = max(0, anchor.base - 0x80000)
                end = anchor.base + anchor.size + 0x80000
                if scan_ranges and start <= scan_ranges[-1][1]:
                    previous_start, previous_end = scan_ranges[-1]
                    scan_ranges[-1] = (previous_start, max(previous_end, end))
                else:
                    scan_ranges.append((start, end))
            missing = wanted.difference(cached)
            wanted_lengths = {len(name) for name in missing}
            executable_ranges = sorted(
                (region.base, region.base + region.size)
                for region in regions
                if region.protect & 0xFF in EXECUTABLE_PROTECTS
            )
            executable_starts = [start for start, _end in executable_ranges]

            def is_executable(address: int) -> bool:
                index = bisect_right(executable_starts, address) - 1
                return index >= 0 and address < executable_ranges[index][1]

            for scan_start, scan_end in scan_ranges:
                for region in sorted(regions, key=lambda value: value.base):
                    if region.typ != MEM_PRIVATE:
                        continue
                    region_start = max(region.base, scan_start - 8)
                    region_end = min(region.base + region.size, scan_end)
                    if region_end - region_start < 32:
                        continue
                    try:
                        blob = memory.read(region_start, region_end - region_start)
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
                        name = self._decode_record_name(memory, blob, region_start, offset)
                        if name not in missing:
                            continue
                        native = NativeHandler(name, record, handler)
                        cached[name] = native
                        self._cache[(pid, name)] = native
                        missing.remove(name)
                        wanted_lengths = {len(value) for value in missing}
                        if not missing:
                            return cached
        missing = ", ".join(sorted(wanted.difference(cached)))
        raise RuntimeError(f"Warcraft III natives were not found: {missing}")


class CommandBarResolver:
    """Locates stable CGameUI/CCommandBar relationships without fixed addresses."""

    _POP_SUBMENU_PATTERN = (
        "40 53 48 83 EC 20 48 8B D9 48 8B 89 ?? ?? 00 00 "
        "F6 C1 01 75 ?? 48 85 C9 74 ?? 4C 8B 09"
    )
    _GAME_UI_WRAPPER_PATTERN = "33 D2 B1 01 E9 ?? ?? ?? ?? CC CC CC CC CC CC CC"
    _SET_HOTKEY_PATTERN = (
        "48 89 5C 24 10 48 89 6C 24 18 48 89 74 24 20 41 56 48 83 EC 20 "
        "8B F2 41 0F B6 E9 8B D9 45 8B F0 83 FA 04 73 ?? 83 FB 03 73 ??"
    )
    _SET_HERO_ONLY_PATTERN = (
        "48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 8B FA 41 0F B6 F0 "
        "8B D9 83 FA 04 73 ?? 83 FB 03 73 ?? E8 ?? ?? ?? ?? 4C 8D 14 5B "
        "48 8D 0C BF 4C 8B 48 08 4B 8B 44 D1 08 40 88 74 08 03"
    )
    _SET_QUICK_CAST_PATTERN = (
        "48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 8B FA 41 0F B6 F0 "
        "8B D9 83 FA 04 73 ?? 83 FB 03 73 ?? E8 ?? ?? ?? ?? 4C 8D 14 5B "
        "48 8D 0C BF 4C 8B 48 08 4B 8B 44 D1 08 40 88 74 08 02"
    )
    _SAVE_HOTKEYS_PATTERN = (
        "40 53 55 41 57 48 81 EC 50 01 00 00 48 8B 05 ?? ?? ?? ?? 48 33 C4 "
        "48 89 84 24 40 01 00 00 E8 ?? ?? ?? ?? 48 8B E8 E8 ?? ?? ?? ?? "
        "33 DB 4C 8B F8"
    )
    _REFRESH_COMMAND_BAR_PATTERN = (
        "40 57 48 83 EC ?? 48 8B F9 E8 ?? ?? ?? ?? 84 C0 0F 85"
    )
    _GET_HOTKEY_PATTERN = (
        "48 89 5C 24 08 48 89 74 24 10 57 48 83 EC 20 8B FA 49 8B F0 "
        "8B D9 83 FA 04 73 ?? 83 FB 03 73 ?? E8 ?? ?? ?? ??"
    )

    def __init__(self):
        self._cache: dict[int, CommandBarInternals] = {}

    @staticmethod
    def _compile_pattern(value: str) -> tuple[bytes, tuple[bool, ...]]:
        tokens = value.split()
        return (
            bytes(int(token, 16) if token != "??" else 0 for token in tokens),
            tuple(token != "??" for token in tokens),
        )

    @staticmethod
    def _scan_pattern(blob: bytes, pattern: bytes, mask: tuple[bool, ...]) -> list[int]:
        hits: list[int] = []
        cursor = 0
        while True:
            cursor = blob.find(pattern[:1], cursor)
            if cursor < 0:
                return hits
            if cursor + len(pattern) <= len(blob) and all(
                not mask[index] or blob[cursor + index] == pattern[index]
                for index in range(len(pattern))
            ):
                hits.append(cursor)
            cursor += 1

    @staticmethod
    def _rel32_target(instruction: int, displacement: int, instruction_size: int = 5) -> int:
        return instruction + instruction_size + displacement

    def resolve(self, pid: int, executable_anchor: int) -> CommandBarInternals:
        cached = self._cache.get(int(pid))
        if cached is not None:
            return cached
        pop_pattern, pop_mask = self._compile_pattern(self._POP_SUBMENU_PATTERN)
        wrapper_pattern, wrapper_mask = self._compile_pattern(self._GAME_UI_WRAPPER_PATTERN)
        with ProcessMemory(pid) as memory:
            regions = memory.regions()
            code_region = NativeResolver._region_for_address(regions, int(executable_anchor))
            if code_region is None or code_region.protect & 0xFF not in EXECUTABLE_PROTECTS:
                raise RuntimeError("Warcraft III executable image was not found")
            blob = memory.read(code_region.base, code_region.size)
        pop_hits = self._scan_pattern(blob, pop_pattern, pop_mask)
        wrapper_hits = self._scan_pattern(blob, wrapper_pattern, wrapper_mask)
        if len(pop_hits) != 1 or len(wrapper_hits) != 1:
            raise RuntimeError(
                "Warcraft III command-bar internals were not unique "
                f"(submenu={len(pop_hits)}, game_ui={len(wrapper_hits)})"
            )
        pop_offset = pop_hits[0]
        pop_address = code_region.base + pop_offset
        submenu_link_offset = struct.unpack_from("<I", blob, pop_offset + 12)[0]
        wrapper_offset = wrapper_hits[0]
        game_ui_get = self._rel32_target(
            code_region.base + wrapper_offset + 4,
            struct.unpack_from("<i", blob, wrapper_offset + 5)[0],
        )
        offsets: dict[int, int] = {}
        cursor = 0
        while True:
            cursor = blob.find(b"\xE8", cursor)
            if cursor < 0:
                break
            if cursor + 5 <= len(blob):
                target = self._rel32_target(
                    code_region.base + cursor,
                    struct.unpack_from("<i", blob, cursor + 1)[0],
                )
                previous = blob[cursor - 7 : cursor]
                if (
                    target == pop_address
                    and len(previous) == 7
                    and previous[:2] == b"\x48\x8B"
                    and previous[2] & 0xC0 == 0x80
                    and (previous[2] >> 3) & 7 == 1
                ):
                    displacement = struct.unpack_from("<i", previous, 3)[0]
                    offsets[displacement] = offsets.get(displacement, 0) + 1
            cursor += 1
        if not offsets:
            raise RuntimeError("Warcraft III command-bar field offset was not found")
        command_bar_offset, evidence_count = max(offsets.items(), key=lambda item: item[1])
        if evidence_count < 2 or not 0x100 <= command_bar_offset <= 0x2000:
            raise RuntimeError("Warcraft III command-bar field offset was not validated")
        if not 0x100 <= submenu_link_offset <= 0x1000:
            raise RuntimeError("Warcraft III submenu field offset was not validated")

        def unique_address(pattern_text: str) -> int | None:
            pattern, mask = self._compile_pattern(pattern_text)
            hits = self._scan_pattern(blob, pattern, mask)
            return code_region.base + hits[0] if len(hits) == 1 else None

        get_hotkey = unique_address(self._GET_HOTKEY_PATTERN)
        enabled_targets: dict[int, int] = {}
        if get_hotkey:
            for call_offset in range(len(blob) - 5):
                if blob[call_offset] != 0xE8:
                    continue
                target = self._rel32_target(
                    code_region.base + call_offset,
                    struct.unpack_from("<i", blob, call_offset + 1)[0],
                )
                if target != get_hotkey:
                    continue
                for compare_offset in range(call_offset + 5, min(call_offset + 80, len(blob) - 7)):
                    if blob[compare_offset : compare_offset + 2] != b"\x80\x3D" or blob[compare_offset + 6] != 0:
                        continue
                    enabled_address = self._rel32_target(
                        code_region.base + compare_offset,
                        struct.unpack_from("<i", blob, compare_offset + 2)[0],
                        instruction_size=7,
                    )
                    enabled_targets[enabled_address] = enabled_targets.get(enabled_address, 0) + 1
                    break
        overriding_hotkey_enabled = None
        if enabled_targets:
            candidate, evidence_count = max(enabled_targets.items(), key=lambda item: item[1])
            candidate_region = NativeResolver._region_for_address(regions, candidate)
            if evidence_count >= 2 and candidate_region is not None:
                overriding_hotkey_enabled = candidate

        internals = CommandBarInternals(
            game_ui_get=game_ui_get,
            command_bar_offset=command_bar_offset,
            submenu_link_offset=submenu_link_offset,
            set_hotkey=unique_address(self._SET_HOTKEY_PATTERN),
            set_hotkey_hero_only=unique_address(self._SET_HERO_ONLY_PATTERN),
            set_hotkey_quick_cast=unique_address(self._SET_QUICK_CAST_PATTERN),
            save_hotkeys=unique_address(self._SAVE_HOTKEYS_PATTERN),
            refresh_command_bar=unique_address(self._REFRESH_COMMAND_BAR_PATTERN),
            overriding_hotkey_enabled=overriding_hotkey_enabled,
        )
        self._cache[int(pid)] = internals
        return internals


class NativeFrameBridge:
    """Keeps one hook installed and sends fixed-size frame-click commands."""

    def __init__(self, helper_path: Path | None = None):
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        self.helper_path = helper_path or root / "tools" / "war3_hotkey_native_helper.dll"
        self.resolver = NativeResolver()
        self.command_bar_resolver = CommandBarResolver()
        self._lock = threading.RLock()
        self._pid = 0
        self._hwnd = 0
        self._module = 0
        self._hook = 0
        self._handlers: dict[str, NativeHandler] = {}
        self._command_bar: CommandBarInternals | None = None

    @property
    def ready(self) -> bool:
        return bool(self._hook and self._module and self._handlers)

    def close(self) -> None:
        with self._lock:
            if self._hook:
                user32.UnhookWindowsHookEx(ctypes.c_void_p(self._hook))
            if self._module:
                kernel32.FreeLibrary(ctypes.c_void_p(self._module))
            self._pid = 0
            self._hwnd = 0
            self._module = 0
            self._hook = 0
            self._handlers = {}
            self._command_bar = None

    def connect(self, hwnd: int, pid: int) -> None:
        with self._lock:
            if self.ready and self._hwnd == int(hwnd) and self._pid == int(pid):
                return
            self.close()
            if not self.helper_path.exists():
                raise RuntimeError(f"Native helper is missing: {self.helper_path}")
            handlers = self.resolver.resolve(int(pid))
            command_bar = self.command_bar_resolver.resolve(
                int(pid), handlers["ConvertOriginFrameType"].handler_address
            )
            module = int(kernel32.LoadLibraryW(str(self.helper_path)) or 0)
            if not module:
                raise ctypes.WinError(ctypes.get_last_error())
            hook = 0
            try:
                procedure = int(kernel32.GetProcAddress(ctypes.c_void_p(module), b"War3HotkeyHookProc") or 0)
                if not procedure:
                    raise ctypes.WinError(ctypes.get_last_error())
                actual_pid = ctypes.c_ulong()
                thread_id = int(user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(actual_pid)))
                if not thread_id or int(actual_pid.value) != int(pid):
                    raise RuntimeError("Warcraft III window thread is no longer valid")
                hook = int(user32.SetWindowsHookExW(
                    WH_CALLWNDPROC,
                    ctypes.c_void_p(procedure),
                    ctypes.c_void_p(module),
                    thread_id,
                ) or 0)
                if not hook:
                    raise ctypes.WinError(ctypes.get_last_error())
            except Exception:
                if hook:
                    user32.UnhookWindowsHookEx(ctypes.c_void_p(hook))
                kernel32.FreeLibrary(ctypes.c_void_p(module))
                raise
            self._pid = int(pid)
            self._hwnd = int(hwnd)
            self._module = module
            self._hook = hook
            self._handlers = handlers
            self._command_bar = command_bar

    def click_slot(self, hwnd: int, pid: int, group: str, slot_index: int, *, timeout_ms: int = 750) -> int:
        if group == "item":
            frame_type = ORIGIN_FRAME_ITEM_BUTTON
            max_index = 5
        elif group in {"ability", "spellbook", "shop"}:
            frame_type = ORIGIN_FRAME_COMMAND_BUTTON
            max_index = 11
        else:
            raise ValueError(f"Unsupported slot group: {group}")
        if not 0 <= int(slot_index) <= max_index:
            raise ValueError(f"Invalid {group} slot index: {slot_index}")
        return self.click_origin(hwnd, pid, frame_type, slot_index, timeout_ms=timeout_ms)

    def click_origin(
        self,
        hwnd: int,
        pid: int,
        frame_type: int,
        index: int,
        *,
        timeout_ms: int = 750,
    ) -> int:
        if not 0 <= int(frame_type) <= 64 or not 0 <= int(index) <= 63:
            raise ValueError(f"Invalid origin frame: type={frame_type} index={index}")
        with self._lock:
            self.connect(hwnd, pid)
            packed_slot = (int(index) << 16) | int(frame_type)
            operation = OP_STRUCT.pack(
                OP_CLICK_ORIGIN_FRAME,
                packed_slot,
                self._handlers["ConvertOriginFrameType"].handler_address,
                self._handlers["BlzGetOriginFrame"].handler_address,
                self._handlers["BlzFrameClick"].handler_address,
                0,
                0,
                0,
            )
            return self._dispatch(
                hwnd,
                pid,
                operation,
                expected_kind=OP_CLICK_ORIGIN_FRAME,
                operation_name="frame click",
                timeout_ms=timeout_ms,
            )

    def query_command_context(
        self,
        hwnd: int,
        pid: int,
        *,
        timeout_ms: int = 500,
    ) -> CommandContext:
        with self._lock:
            self.connect(hwnd, pid)
            if self._command_bar is None:
                raise RuntimeError("Warcraft III command-bar internals are unavailable")
            packed_offsets = (
                int(self._command_bar.submenu_link_offset) << 32
            ) | int(self._command_bar.command_bar_offset)
            operation = OP_STRUCT.pack(
                OP_QUERY_COMMAND_CONTEXT,
                0,
                self._command_bar.game_ui_get,
                packed_offsets,
                0,
                0,
                0,
                0,
            )
            result = self._dispatch(
                hwnd,
                pid,
                operation,
                expected_kind=OP_QUERY_COMMAND_CONTEXT,
                operation_name="command context query",
                timeout_ms=timeout_ms,
            )
            return CommandContext(submenu_active=bool(result & 1))

    def query_selection_context(
        self,
        hwnd: int,
        pid: int,
        *,
        timeout_ms: int = 500,
    ) -> SelectionContext:
        with self._lock:
            self.connect(hwnd, pid)
            operations = (
                OP_STRUCT.pack(
                    OP_QUERY_SELECTION_CONTEXT,
                    0,
                    self._handlers["CreateGroup"].handler_address,
                    0,
                    self._handlers["GetLocalPlayer"].handler_address,
                    0,
                    0,
                    0,
                ),
                OP_STRUCT.pack(
                    0,
                    0,
                    self._handlers["GroupEnumUnitsSelected"].handler_address,
                    self._handlers["FirstOfGroup"].handler_address,
                    self._handlers["DestroyGroup"].handler_address,
                    0,
                    0,
                    0,
                ),
                OP_STRUCT.pack(
                    0,
                    0,
                    self._handlers["GetOwningPlayer"].handler_address,
                    self._handlers["GetPlayerId"].handler_address,
                    0,
                    0,
                    0,
                    0,
                ),
            )
            result = self._dispatch(
                hwnd,
                pid,
                operations,
                expected_kind=OP_QUERY_SELECTION_CONTEXT,
                operation_name="selection context query",
                timeout_ms=timeout_ms,
            )
            owner_id = (result >> 32) & 0xFFFFFFFF
            if owner_id & 0x80000000:
                owner_id -= 0x100000000
            has_selection = bool(result & 1)
            return SelectionContext(
                has_selection=has_selection,
                neutral_selected=bool(result & 2),
                owner_player_id=owner_id if has_selection else None,
            )

    def override_command_hotkeys(
        self,
        hwnd: int,
        pid: int,
        hotkeys: Iterable[tuple[int, int, int, int]],
        *,
        timeout_ms: int = 1000,
    ) -> None:
        """Write, save, enable, and refresh the native 3x4 command-bar table."""
        with self._lock:
            self.connect(hwnd, pid)
            internals = self._command_bar
            if internals is None or not all((
                internals.set_hotkey,
                internals.set_hotkey_hero_only,
                internals.set_hotkey_quick_cast,
                internals.save_hotkeys,
                internals.refresh_command_bar,
                internals.overriding_hotkey_enabled,
            )):
                raise RuntimeError("Warcraft III native command hotkey functions were not uniquely resolved")
            values = tuple(hotkeys)
            if len(values) != 12:
                raise ValueError("Exactly 12 command hotkeys are required")
            operations = []
            for index, (row, column, key, meta) in enumerate(values):
                if not 0 <= row < 3 or not 0 <= column < 4 or not 0 <= key <= 255 or not 0 <= meta <= 255:
                    raise ValueError(f"Invalid command hotkey at index {index}")
                rawcode = row | (column << 8) | (key << 16) | (meta << 24)
                flags = HOTKEY_FLAG_SAVE if index == len(values) - 1 else 0
                operations.append(OP_STRUCT.pack(
                    OP_OVERRIDE_COMMAND_HOTKEY,
                    rawcode,
                    internals.set_hotkey,
                    internals.set_hotkey_quick_cast,
                    internals.set_hotkey_hero_only,
                    0,
                    0,
                    flags,
                ))
            operations.append(OP_STRUCT.pack(
                OP_REFRESH_COMMAND_BAR,
                internals.command_bar_offset,
                internals.game_ui_get,
                internals.refresh_command_bar,
                internals.overriding_hotkey_enabled,
                0,
                0,
                1,
            ))
            self._dispatch(
                hwnd,
                pid,
                tuple(operations),
                expected_kind=OP_OVERRIDE_COMMAND_HOTKEY,
                operation_name="native command hotkey override",
                timeout_ms=timeout_ms,
                reserved_handle=internals.save_hotkeys,
            )

    def set_command_hotkey_override_enabled(
        self,
        hwnd: int,
        pid: int,
        enabled: bool,
        *,
        timeout_ms: int = 750,
    ) -> None:
        with self._lock:
            self.connect(hwnd, pid)
            internals = self._command_bar
            if internals is None or not all((
                internals.game_ui_get,
                internals.refresh_command_bar,
                internals.overriding_hotkey_enabled,
            )):
                raise RuntimeError("Warcraft III command hotkey override flag was not resolved")
            operation = OP_STRUCT.pack(
                OP_REFRESH_COMMAND_BAR,
                internals.command_bar_offset,
                internals.game_ui_get,
                internals.refresh_command_bar,
                internals.overriding_hotkey_enabled,
                0,
                0,
                1 if enabled else 0,
            )
            self._dispatch(
                hwnd,
                pid,
                operation,
                expected_kind=OP_REFRESH_COMMAND_BAR,
                operation_name="command hotkey override toggle",
                timeout_ms=timeout_ms,
            )

    def _dispatch(
        self,
        hwnd: int,
        pid: int,
        operation: bytes | tuple[bytes, ...],
        *,
        expected_kind: int,
        operation_name: str,
        timeout_ms: int,
        reserved_handle: int = 0,
    ) -> int:
        operations = (operation,) if isinstance(operation, bytes) else tuple(operation)
        if not operations or len(operations) > MAX_OPS or any(len(item) != OP_STRUCT.size for item in operations):
            raise ValueError("Invalid native operation block")
        payload = HEADER_STRUCT.pack(
            HOTKEY_MAGIC,
            HOTKEY_VERSION,
            STATUS_PENDING,
            len(operations),
            int(reserved_handle),
            0,
            0,
        ) + b"".join(operations) + b"\0" * (OP_STRUCT.size * (MAX_OPS - len(operations)))
        command_path = Path(tempfile.gettempdir()) / f"war3_hotkey_native_{pid}.bin"
        deadline = time.perf_counter() + max(0.2, timeout_ms / 1000.0)
        while True:
            try:
                command_path.write_bytes(payload)
                break
            except PermissionError:
                if time.perf_counter() >= deadline:
                    raise TimeoutError(f"Native {operation_name} command file stayed busy")
                time.sleep(0.002)
        while time.perf_counter() < deadline:
            message_result = ctypes.c_void_p()
            user32.SendMessageTimeoutW(
                ctypes.c_void_p(hwnd),
                WM_NULL,
                None,
                None,
                SMTO_ABORTIFHUNG,
                100,
                ctypes.byref(message_result),
            )
            try:
                data = command_path.read_bytes()
            except PermissionError:
                time.sleep(0.002)
                continue
            if len(data) < COMMAND_SIZE:
                time.sleep(0.002)
                continue
            magic, version, status, count, _reserved, last_error, _extra = HEADER_STRUCT.unpack_from(data)
            if magic != HOTKEY_MAGIC or version != HOTKEY_VERSION or count != len(operations):
                raise RuntimeError("Native helper returned an incompatible command block")
            if status == STATUS_PENDING:
                time.sleep(0.002)
                continue
            kind, _rawcode, _handler, _arg0, _arg1, result, op_error, _reserved = OP_STRUCT.unpack_from(
                data, HEADER_STRUCT.size
            )
            if status != STATUS_OK or kind != expected_kind or last_error or op_error:
                raise RuntimeError(
                    f"Native {operation_name} failed: status={status} error={last_error or op_error}"
                )
            return int(result)
        raise TimeoutError(f"Native {operation_name} timed out")
