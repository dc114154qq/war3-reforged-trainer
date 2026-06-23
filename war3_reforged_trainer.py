# -*- coding: utf-8 -*-
"""Warcraft III Reforged local trainer.

This replaces the old 32-bit game.dll trainer path with verified Reforged routes:
- Warcraft cheat input through PostMessageW, avoiding IME/keyboard layout issues.
- Reforged 64-bit selected-unit handle -> unit owner -> property table memory path.
"""

from __future__ import annotations

import argparse
import ctypes
import math
import struct
import sys
import threading
import time
from dataclasses import dataclass, replace
from typing import Callable, Iterable


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
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
MEM_PRIVATE = 0x20000
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
VK_RETURN = 0x0D
SW_RESTORE = 9
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

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

    def close(self) -> None:
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self) -> "ProcessMemory":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def regions(self) -> list[Region]:
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
        return out

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

    def scan_i32(self, value: int) -> list[tuple[int, int, int]]:
        return self.scan_bytes(struct.pack("<i", int(value)))

    def scan_f32(self, value: float) -> list[tuple[int, int, int]]:
        return self.scan_bytes(struct.pack("<f", float(value)))


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
    HERO_SKILL_SLOT_COUNT = 5
    ITEM_CHARGES_OFFSET = 0x1C0
    SELECTED_HP_VALUE_OFFSET = 0xD0
    NATIVE_HANDLER_NAMES = (
        "UnitAddAbility",
        "UnitRemoveAbility",
        "SetUnitAbilityLevel",
        "GetUnitAbilityLevel",
        "UnitAddItem",
        "UnitAddItemToSlotById",
        "UnitItemInSlot",
        "UnitRemoveItem",
        "RemoveItem",
        "GetItemTypeId",
        "SetItemCharges",
        "GetUnitTypeId",
        "UnitInventorySize",
    )

    def __init__(self, pid: int | None = None):
        self.hwnd, self.pid = find_war3(pid)
        self._unit_owner_index: dict[int, int] = {}
        self._selected_handle_addresses = list(self.KNOWN_SELECTED_HANDLE_ADDRESSES)
        self._item_object_cache: dict[int, int] = {}
        self._native_handlers: dict[str, NativeHandler] = {}

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

    def focus(self) -> None:
        focus_window(self.hwnd)

    def send_cheat(self, text: str) -> None:
        post_cheat(self.hwnd, text)

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

    def _find_native_table_region(self, pm: ProcessMemory, regions: list[Region]) -> Region:
        pattern = b"UnitAddAbility\0"
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
            if ptr != hit or size != len("UnitAddAbility"):
                continue
            if self._is_executable_image_address(regions, handler):
                return region
        raise RuntimeError("未找到 Warcraft III native 函数表")

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
        blob = pm.read(table_region.base, table_region.size)
        found: dict[str, NativeHandler] = {}
        for offset in range(8, len(blob) - 24, 8):
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
        missing = wanted.difference(self._native_handlers)
        if missing:
            raise RuntimeError("未找到 native 函数：" + ", ".join(sorted(missing)))
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

    def _discover_native_ability_internals(self, pm: ProcessMemory) -> NativeAbilityInternals:
        handlers = self._discover_native_handlers(pm, ("UnitAddAbility", "UnitRemoveAbility"))
        add_handler = handlers["UnitAddAbility"].handler_address
        remove_handler = handlers["UnitRemoveAbility"].handler_address
        internals = NativeAbilityInternals(
            find_address=self._read_rel32_call(pm, add_handler + 0x33),
            begin_address=self._read_rel32_call(pm, add_handler + 0x45),
            add_address=self._read_rel32_call(pm, add_handler + 0x5F),
            end_address=self._read_rel32_call(pm, add_handler + 0x73),
            refresh_address=self._read_rel32_call(pm, add_handler + 0x7E),
            remove_address=self._read_rel32_call(pm, remove_handler + 0x43),
        )
        remove_find = self._read_rel32_call(pm, remove_handler + 0x33)
        if remove_find != internals.find_address:
            raise RuntimeError("UnitAddAbility/UnitRemoveAbility 使用的内部查找函数不一致")
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

    def _iter_resource_properties(self, pm: ProcessMemory) -> Iterable[ResourceProperty]:
        tag = struct.pack("<Q", self.RESOURCE_PROP_TAG)
        for tag_address in pm.scan_bytes_private(tag, max_region_size=1024 * 1024):
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
        if used_prop is None:
            return cap_prop or limit_prop, limit_prop
        if cap_prop is not None and used_prop.value <= cap_prop.value <= 1000:
            return cap_prop, limit_prop
        if limit_prop is not None and used_prop.value <= limit_prop.value <= 1000:
            return limit_prop, cap_prop
        return cap_prop or limit_prop, limit_prop

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
            if gold_prop.value % 10 or lumber_prop.value % 10:
                continue
            gold = gold_prop.value // 10
            lumber = lumber_prop.value // 10
            if not 0 <= gold <= 10_000_000 or not 0 <= lumber <= 10_000_000:
                continue
            if current_gold is not None and gold != int(current_gold):
                continue
            if current_lumber is not None and lumber != int(current_lumber):
                continue

            limit_prop = group.get(start_kind + 5)
            used_prop = group.get(start_kind + 6)
            cap_prop = group.get(start_kind + 7)
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

    def _resource_property_groups(self, pm: ProcessMemory) -> dict[int, dict[int, ResourceProperty]]:
        groups: dict[int, dict[int, ResourceProperty]] = {}
        for prop in self._iter_resource_properties(pm):
            owner_group = groups.setdefault(prop.owner_key, {})
            current = owner_group.get(prop.kind)
            if current is None or prop.address > current.address:
                owner_group[prop.kind] = prop
        return groups

    def list_resource_caches(
        self,
        current_gold: int | None = None,
        current_lumber: int | None = None,
        current_food: int | None = None,
        current_food_cap: int | None = None,
    ) -> list[ResourceCache]:
        with ProcessMemory(self.pid) as pm:
            groups = self._resource_property_groups(pm)
            found: list[ResourceCache] = []
            seen: set[tuple[int, int]] = set()
            for group in groups.values():
                candidate = self._resource_cache_from_group(
                    group, current_gold, current_lumber, current_food, current_food_cap
                )
                if candidate is None:
                    continue
                _score, cache = candidate
                key = (cache.gold_address, cache.lumber_address)
                if key in seen:
                    continue
                seen.add(key)
                found.append(cache)
            return sorted(found, key=lambda cache: (cache.block_start_kind, cache.owner_key))

    def _read_resource_cache_addresses(self, pm: ProcessMemory, cache: ResourceCache) -> ResourceCache:
        gold10 = pm.read_i32(cache.gold_address)
        lumber10 = pm.read_i32(cache.lumber_address)
        if gold10 % 10 or lumber10 % 10:
            raise RuntimeError("资源地址校验失败：金币/木材值不是游戏内部的 x10 格式，请重新读取资源组")
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
    ) -> ResourceCache:
        if target_gold is None and target_lumber is None and target_food_used is None and target_food_cap is None:
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
                pm.write_i32(current.food_used_address, int(target_food_used))
            if target_food_cap is not None:
                if not current.food_cap_address:
                    raise RuntimeError("所选资源组没有可写的人口上限字段")
                if not 0 <= int(target_food_cap) <= 1000:
                    raise ValueError("目标人口上限必须在 0 到 1000 之间")
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

    def _build_unit_owner_index(self, pm: ProcessMemory) -> dict[int, int]:
        index: dict[int, int] = {}
        tag = struct.pack("<Q", self.UNIT_OWNER_TAG)
        for tag_address in pm.scan_bytes_private(tag, max_region_size=1024 * 1024):
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

    def _locate_selected_unit_by_panel(self, pm: ProcessMemory) -> UnitCandidate:
        raise RuntimeError("OCR/面板数值定位已禁用；当前选中单位只能通过内存 selected-handle 定位")

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

    def list_selection_candidates(self, limit: int = 12) -> list[UnitSelectionSummary]:
        with ProcessMemory(self.pid) as pm:
            unit_index = self._build_unit_object_index(pm, force_refresh=True)
            summaries: list[UnitSelectionSummary] = []
            seen_units: set[int] = set()
            for (region_base, unit), addresses, known_hits in self._selection_unit_pointer_groups(pm):
                if unit in seen_units:
                    continue
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
                if candidate is None:
                    continue
                panel = self._panel_from_candidate(pm, candidate)
                position = self._position_from_candidate(pm, candidate)
                components = self._selected_components(pm, owner)
                inventory: list[str] = []
                for item in self._inventory_items_from_candidate(pm, candidate, components):
                    if item.rawcode:
                        inventory.append(f"{item.slot}:{item.rawcode_text}")
                ability_count = len(self._ability_instances_from_candidate(pm, candidate))
                summaries.append(
                    UnitSelectionSummary(
                        candidate=candidate,
                        refs=len(addresses),
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
                )
                seen_units.add(unit)
                if len(summaries) >= limit:
                    break
            return summaries

    def selection_candidate_line(self, summary: UnitSelectionSummary, index: int) -> str:
        pos = summary.position
        pos_text = f" x={pos[0]:.1f} y={pos[1]:.1f}" if pos is not None else ""
        components = ",".join(summary.components) if summary.components else "-"
        inventory = ",".join(summary.inventory) if summary.inventory else "-"
        confidence = "强" if summary.known_hits >= 2 else "候选"
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
        for offset in range(-0x8000, 0x1800, 8):
            wrapper = owner + offset
            try:
                vtable = pm.read_u64(wrapper)
                tag = pm.read_u64(wrapper + 0x18)
                wrapper_owner = pm.read_u64(wrapper + 0x50)
                data = pm.read_u64(wrapper + 0x90)
            except OSError:
                continue
            name = self.COMPONENT_NAMES.get(tag)
            if name is None:
                continue
            if wrapper_owner != owner:
                continue
            if not self._looks_like_vtable(vtable):
                continue
            if not self._sane_heap_ptr(data):
                continue
            try:
                data_vtable = pm.read_u64(data)
            except OSError:
                continue
            if not self._looks_like_vtable(data_vtable):
                continue
            yield name, wrapper, data

    def _selected_components(self, pm: ProcessMemory, owner: int) -> dict[str, tuple[int, int]]:
        components: dict[str, tuple[int, int]] = {}
        if not owner:
            return components
        for name, wrapper, data in self._iter_owner_component_wrappers(pm, owner):
            components.setdefault(name, (wrapper, data))
        return components

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

    def _ability_instances_from_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
    ) -> list[AbilityInstance]:
        if not candidate.owner_address or not candidate.unit_address:
            return []
        component_rawcodes = {tag >> 32 for tag in self.COMPONENT_TAGS.values()}
        instances: list[AbilityInstance] = []
        for offset in range(-0x8000, 0x10000, 8):
            wrapper = candidate.owner_address + offset
            try:
                vtable = pm.read_u64(wrapper)
                tag = pm.read_u64(wrapper + 0x18)
                wrapper_owner = pm.read_u64(wrapper + 0x50)
                data = pm.read_u64(wrapper + 0x90)
            except OSError:
                continue
            if wrapper_owner != candidate.owner_address:
                continue
            if not self._looks_like_vtable(vtable) or not self._sane_heap_ptr(data):
                continue
            class_rawcode = (tag >> 32) & 0xFFFFFFFF
            if class_rawcode in component_rawcodes:
                continue
            if not self._looks_like_rawcode(class_rawcode):
                continue
            try:
                data_vtable = pm.read_u64(data)
                unit = pm.read_u64(data + 0x68)
                rawcode = pm.read_u32(data + 0x70)
                mirror_rawcode = pm.read_u32(data + 0x78)
                handle = pm.read_u64(wrapper + 0x20)
                data_cache_pointer = pm.read_u64(data + 0xA0)
            except OSError:
                continue
            if not self._looks_like_vtable(data_vtable):
                continue
            if unit != candidate.unit_address:
                continue
            if rawcode != mirror_rawcode or not self._looks_like_rawcode(rawcode):
                continue
            instances.append(
                AbilityInstance(
                    slot=len(instances) + 1,
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
            )
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

    def _item_objects_from_handles(self, pm: ProcessMemory, handles: Iterable[int]) -> dict[int, int]:
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
        item_by_handle = self._item_objects_from_handles(pm, (handle for _index, _address, handle in slot_handles))
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

        ability_instances = self._ability_instances_from_candidate(pm, candidate)
        ability_by_rawcode: dict[int, list[AbilityInstance]] = {}
        for instance in ability_instances:
            ability_by_rawcode.setdefault(instance.rawcode, []).append(instance)

        hero_skill_config_rawcodes: list[int] = []
        hero = components.get("hero")
        if hero is not None:
            _wrapper, data = hero
            self._append_unit_field(pm, fields, "xp", "经验值", "i32", data + 0x100, "英雄")
            self._append_unit_field(pm, fields, "skill_points", "技能点", "i32", data + 0x104, "英雄")
            self._append_unit_field(pm, fields, "base_strength", "力量(基础)", "i32", data + 0x108, "英雄")
            self._append_unit_field(
                pm,
                fields,
                "intelligence_total",
                "智力(当前总值候选)",
                "f32",
                data + 0x118,
                "英雄",
                note="当前样本与面板白字+绿字总智力一致；Reforged 未在同组件内找到可验证的基础智力整数",
            )
            self._append_unit_field(pm, fields, "base_agility", "敏捷(基础)", "i32", data + 0x130, "英雄")
            growth_note = "英雄组件成长值，不是面板装备/光环加成"
            self._append_unit_field(pm, fields, "strength_growth", "力量成长/级", "f32", data + 0x188, "英雄", note=growth_note)
            self._append_unit_field(pm, fields, "intelligence_growth", "智力成长/级", "f32", data + 0x198, "英雄", note=growth_note)
            self._append_unit_field(pm, fields, "agility_growth", "敏捷成长/级", "f32", data + 0x1A8, "英雄", note=growth_note)
            skill_name_note = (
                "英雄技能栏 rawcode；只读展示。实际换技能必须走游戏 native add/remove/create 路径，"
                "不能复制已有 ability payload"
            )
            skill_cache_note = "旧版候选/运行时缓存；单改这里通常不改变已学技能效果"
            for index in range(self.HERO_SKILL_SLOT_COUNT):
                config_address = data + 0x204 + index * 4
                try:
                    current_config_rawcode = pm.read_u32(config_address)
                except OSError:
                    current_config_rawcode = 0
                hero_skill_config_rawcodes.append(current_config_rawcode)
            skill_instance_by_index: dict[int, AbilityInstance] = {}
            used_skill_instance_wrappers: set[int] = set()
            for index, rawcode in enumerate(hero_skill_config_rawcodes):
                if not rawcode:
                    continue
                for instance in ability_by_rawcode.get(rawcode, []):
                    if instance.wrapper_address in used_skill_instance_wrappers:
                        continue
                    skill_instance_by_index[index] = instance
                    used_skill_instance_wrappers.add(instance.wrapper_address)
                    break
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
                    writable=False,
                    note=skill_name_note,
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
            used_instance_wrappers: set[int] = set()
            skill_instance_by_index = {}
            for index, rawcode in enumerate(hero_skill_config_rawcodes):
                if not rawcode:
                    continue
                for instance in ability_by_rawcode.get(rawcode, []):
                    if instance.wrapper_address in used_instance_wrappers:
                        continue
                    skill_instance_by_index[index] = instance
                    used_instance_wrappers.add(instance.wrapper_address)
                    break
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
                            "写入时直接修改本槽 item 对象，不交换其他物品槽"
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
                        write_address=0,
                        write_type="",
                        note=note + "；空槽没有可直接改写的 item 对象",
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
            panel = self._panel_from_candidate(pm, candidate)
            return panel, candidate, self._unit_fields_from_candidate(pm, candidate)

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
            panel = self._panel_from_candidate(pm, candidate)
            return panel, candidate, self._unit_fields_from_candidate(pm, candidate)

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
        ability_instances = self._ability_instances_from_candidate(pm, candidate)
        ability_by_rawcode: dict[int, list[AbilityInstance]] = {}
        for instance in ability_instances:
            ability_by_rawcode.setdefault(instance.rawcode, []).append(instance)
        mapped: dict[int, AbilityInstance] = {}
        used_wrappers: set[int] = set()
        for index, rawcode in enumerate(configs):
            if not rawcode:
                continue
            for instance in ability_by_rawcode.get(rawcode, []):
                if instance.wrapper_address in used_wrappers:
                    continue
                mapped[index] = instance
                used_wrappers.add(instance.wrapper_address)
                break
        return configs, mapped, ability_instances

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
        raise RuntimeError(
            f"技能{index + 1}写入 {format_rawcode(new_rawcode)} 已禁用："
            "Reforged 的已学技能效果绑定在运行时 ability 实例/数据对象上，"
            "单写技能栏 rawcode 或复制已有实例 payload 已验证会导致技能消失或游戏崩溃；"
            "当前版本只读展示这些字段，等找到稳定的游戏线程内 ability 创建/替换路径后再开放写入"
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
        if old_snapshot is None or not old_snapshot.item_address or not old_snapshot.rawcode_address:
            raise RuntimeError(
                f"物品槽{slot_index + 1}为空或未解析 item 对象；"
                "当前实现只直接修改已有槽位对象，不用不安全 native 创建新物品"
            )
        old_rawcode = old_snapshot.rawcode if old_snapshot is not None else 0
        actions: list[str] = []
        if old_rawcode == new_rawcode:
            actions.append("物品 rawcode 未变化")
        else:
            template = next(
                (
                    item
                    for item in items
                    if item.slot != slot_index + 1 and item.rawcode == new_rawcode and item.item_address
                ),
                None,
            )
            if template is not None:
                for offset, size in (
                    (0x38, 4),
                    (0x58, 0x40),
                    (0x178, 4),
                    (0x1B8, 4),
                ):
                    pm.write_bytes(
                        old_snapshot.item_address + offset,
                        pm.read(template.item_address + offset, size),
                    )
                actions.append(f"从物品槽{template.slot}复制 {format_rawcode(new_rawcode)} 类型元数据")
            else:
                actions.append("未找到同 rawcode 物品模板，仅写本槽 item type rawcode/镜像")
            pm.write_u32(old_snapshot.rawcode_address, new_rawcode)
            if old_snapshot.mirror_rawcode_address:
                pm.write_u32(old_snapshot.mirror_rawcode_address, new_rawcode)
            actions.append("未交换其他物品槽")

        time.sleep(0.05)
        after_items = self._inventory_items_from_candidate(pm, candidate, components)
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
        final_snapshot = next((item for item in after_items if item.slot == slot_index + 1), None)
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
                "直接修改本槽 item 对象，未交换其他物品槽"
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

    def _write_unit_fields_to_candidate(
        self,
        pm: ProcessMemory,
        candidate: UnitCandidate,
        specs: Iterable[MemoryWriteSpec],
    ) -> list[UnitMemoryField]:
        specs = list(specs)
        if not specs:
            return []
        fields = self._unit_fields_from_candidate(pm, candidate)
        by_key = {field.key: field for field in fields}
        by_label = {field.label: field for field in fields}
        written: list[UnitMemoryField] = []
        for spec in specs:
            field = (
                by_key.get(spec.label)
                or by_key.get(self.FIELD_KEY_ALIASES.get(spec.label, ""))
                or by_label.get(spec.label)
            )
            if field is None:
                raise RuntimeError(f"当前选中单位没有字段：{spec.label}")
            if not field.writable:
                raise RuntimeError(f"字段不可写：{field.label}")
            if self._skill_index_from_field_key(field.key) is not None:
                written.append(self._write_hero_skill_name_field(pm, candidate, field, spec.value))
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

    def locate_current_selected_unit(self) -> tuple[VisibleUnitPanel, UnitCandidate]:
        with ProcessMemory(self.pid) as pm:
            candidate = self.locate_selected_unit_by_handle(pm, allow_deep_scan=True)
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
    root.title("魔兽争霸3重制版修改器")
    root.geometry("1180x780")
    root.minsize(1040, 700)

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
    x_target = tk.StringVar(value="")
    y_target = tk.StringVar(value="")
    unit_field_target = tk.StringVar(value="")
    operation_lock = threading.RLock()

    state: dict[str, object] = {
        "trainer": None,
        "resource_caches": {},
        "resource_labels": {},
        "selected_resource_iid": "",
        "unit_fields": {},
        "selected_unit_identity": None,
        "selection_candidates": {},
        "manual_unit_identity": None,
        "locks": {},
        "lock_busy": False,
    }

    def set_status(text: str) -> None:
        status.set(text)

    def call_async(fn: Callable[[], str | None]) -> None:
        set_status("正在执行，请稍候...")

        def worker() -> None:
            try:
                with operation_lock:
                    result = fn()
                if result:
                    root.after(0, set_status, result)
                else:
                    root.after(0, set_status, "已完成")
            except Exception as exc:
                root.after(0, lambda: messagebox.showerror("错误", str(exc)))
                root.after(0, set_status, f"失败：{exc}")

        threading.Thread(target=worker, daemon=True).start()

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

    def populate_resource_caches(caches: list[ResourceCache], preferred_iid: str = "") -> None:
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
        preferred_iid = str(state.get("selected_resource_iid", ""))
        caches = t.list_resource_caches()
        if not caches:
            cg = int(gold_current.get()) if gold_current.get().strip() else None
            cl = int(lumber_current.get()) if lumber_current.get().strip() else None
            cf = int(food_current.get()) if food_current.get().strip() else None
            cfc = int(food_cap_current.get()) if food_cap_current.get().strip() else None
            caches = [t.read_resource_cache(cg, cl, cf, cfc)]
        root.after(0, populate_resource_caches, caches, preferred_iid)
        return f"已读取 {len(caches)} 个资源组；请选择表格行后设置金币/木材/人口"

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

    def set_food_resource() -> str:
        t = trainer()
        cache = selected_resource_cache()
        label = selected_resource_label(cache)
        current = t.read_resource_cache_addresses(cache)
        target_used = parse_int(food_used_target.get(), "目标人口占用") if food_used_target.get().strip() else None
        target_cap = parse_int(food_cap_target.get(), "目标人口上限") if food_cap_target.get().strip() else None
        if target_used is None and target_cap is None:
            raise ValueError("至少填写一个目标人口占用或目标人口上限")
        refreshed = t.write_resource_cache(current, target_food_used=target_used, target_food_cap=target_cap)
        root.after(0, update_resource_cache_display, refreshed)
        return f"资源组 {label} 人口已写入：{refreshed.food_used}/{refreshed.food_cap}；{refreshed.source}"

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

    def populate_selection_candidates(summaries: list[UnitSelectionSummary]) -> None:
        candidate_map: dict[str, UnitSelectionSummary] = {}
        candidate_tree.delete(*candidate_tree.get_children())
        preferred_identity = state.get("manual_unit_identity") or state.get("selected_unit_identity")
        selected_iid = ""
        for index, summary in enumerate(summaries, 1):
            iid = str(index)
            candidate_map[iid] = summary
            candidate = summary.candidate
            confidence = "强" if summary.known_hits >= 2 else "候选"
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
        summaries = trainer().list_selection_candidates()
        root.after(0, populate_selection_candidates, summaries)
        return f"已列出 {len(summaries)} 个候选单位；自动定位弱时请选择带 hero/inventory/物品槽的行"

    def populate_auto_selected_unit_readout(
        panel: VisibleUnitPanel,
        cand: UnitCandidate,
        fields: list[UnitMemoryField],
        force_targets: bool = False,
    ) -> None:
        state["manual_unit_identity"] = None
        populate_selected_unit_readout(panel, cand, fields, force_targets)

    def populate_manual_candidate_readout(
        panel: VisibleUnitPanel,
        cand: UnitCandidate,
        fields: list[UnitMemoryField],
        force_targets: bool = False,
    ) -> None:
        state["manual_unit_identity"] = unit_identity(cand)
        populate_selected_unit_readout(panel, cand, fields, force_targets)

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
            x_target,
            y_target,
            unit_field_target,
        ):
            var.set("")
        state["selected_unit_identity"] = None
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
    ) -> None:
        field_by_key = {field.key: field for field in fields}
        identity = (cand.handle, cand.owner_address, cand.unit_address)
        reset_targets = force_targets or state.get("selected_unit_identity") != identity
        state["selected_unit_identity"] = identity

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
        except Exception:
            root.after(0, clear_selected_unit_readout)
            raise
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
        manual_identity = current_manual_unit_identity()
        if manual_identity is not None:
            written = t.write_unit_field_by_identity(*manual_identity, field.key, value)
            panel, cand, fields = t.read_unit_fields_by_identity(*manual_identity)
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
        locks[f"resource:{cache_iid}:{kind}"] = {
            "scope": f"资源组 {group_label}",
            "kind": "resource",
            "key": kind,
            "resource_cache": cache,
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
                t.write_selected_unit_field(key, value)
                continue
            if kind != "resource":
                continue
            target = parse_int(value, str(item.get("label", "资源")))
            cache = item.get("resource_cache")
            if not isinstance(cache, ResourceCache):
                raise ValueError("锁定项缺少资源组地址，请删除后重新锁定")
            if key == "gold":
                item["resource_cache"] = t.write_resource_cache(cache, target_gold=target)
            elif key == "lumber":
                item["resource_cache"] = t.write_resource_cache(cache, target_lumber=target)
            elif key == "food_used":
                item["resource_cache"] = t.write_resource_cache(cache, target_food_used=target)
            elif key == "food_cap":
                item["resource_cache"] = t.write_resource_cache(cache, target_food_cap=target)

    def lock_tick() -> None:
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
                    root.after(0, set_status, f"锁定中：{len(locks)} 项")
                except Exception as exc:
                    root.after(0, set_status, f"锁定失败：{exc}")
                finally:
                    operation_lock.release()
                    state["lock_busy"] = False

            threading.Thread(target=worker, daemon=True).start()
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
        manual_identity = current_manual_unit_identity()
        if manual_identity is not None:
            cand = t.set_unit_by_identity(
                *manual_identity,
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
            panel, cand_after, fields = t.read_unit_fields_by_identity(*manual_identity)
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
        try:
            t = trainer()
            panel, cand, fields = t.read_selected_unit_fields()
        except Exception:
            root.after(0, clear_selected_unit_readout)
            raise
        root.after(0, populate_auto_selected_unit_readout, panel, cand, fields, True)
        return (
            f"选中单位：HP {panel.hp_text}，MP {panel.mp_text}；"
            f"source={cand.selection_source or 'unknown'} base=0x{cand.base:x} unit=0x{cand.unit_address:x}"
        )

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
    resource_tree = ttk.Treeview(resource_frame, columns=resource_columns, show="headings", height=11)
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
    ttk.Label(res, text="目标人口/上限").grid(row=5, column=0, sticky="w", pady=8)
    ttk.Entry(res, textvariable=food_used_target, width=12).grid(row=5, column=1, sticky="w")
    ttk.Entry(res, textvariable=food_cap_target, width=12).grid(row=5, column=3, sticky="w")
    ttk.Button(res, text="设置人口", command=lambda: call_async(set_food_resource)).grid(row=5, column=4, padx=8)
    ttk.Button(res, text="锁定人口", command=lambda: call_async(lambda: add_resource_lock("food_used"))).grid(row=5, column=5, padx=4)
    ttk.Button(res, text="锁定上限", command=lambda: call_async(lambda: add_resource_lock("food_cap"))).grid(row=5, column=6, padx=4)

    ttk.Label(res, text="增量").grid(row=6, column=0, sticky="w", pady=(12, 0))
    ttk.Entry(res, textvariable=resource_delta, width=12).grid(row=6, column=1, sticky="w", pady=(12, 0))
    ttk.Button(res, text="金币 +/-", command=lambda: call_async(lambda: add_resource("gold"))).grid(row=6, column=2, pady=(12, 0))
    ttk.Button(res, text="木材 +/-", command=lambda: call_async(lambda: add_resource("lumber"))).grid(row=6, column=3, pady=(12, 0))
    ttk.Button(res, text="金木一起 +/-", command=lambda: call_async(lambda: add_resource("both"))).grid(row=6, column=4, pady=(12, 0), padx=8)

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
    ttk.Label(unit, text="目标 X").grid(row=5, column=0, sticky="w", pady=8)
    ttk.Entry(unit, textvariable=x_target, width=12).grid(row=5, column=1, sticky="w")
    ttk.Label(unit, text="目标 Y").grid(row=5, column=2, sticky="w", padx=(16, 0))
    ttk.Entry(unit, textvariable=y_target, width=12).grid(row=5, column=3, sticky="w")
    ttk.Button(unit, text="读取当前选中单位", command=lambda: call_async(read_unit)).grid(row=6, column=0, pady=12, sticky="w")
    ttk.Button(unit, text="写入选中单位", command=lambda: call_async(set_unit)).grid(row=6, column=1, pady=12, sticky="w")
    ttk.Button(unit, text="刷新字段表", command=lambda: call_async(read_unit_fields)).grid(row=6, column=2, pady=12, sticky="w")
    ttk.Button(unit, text="列出候选单位", command=lambda: call_async(refresh_unit_candidates)).grid(row=6, column=3, pady=12, sticky="w")
    ttk.Button(unit, text="读取所选候选", command=lambda: call_async(read_selection_candidate_fields)).grid(row=6, column=4, pady=12, sticky="w")

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

    ttk.Label(outer, textvariable=status, anchor="w", wraplength=1000).pack(fill="x", pady=(0, 2))

    def init() -> None:
        try:
            msg = connect()
            set_status(msg)
            try:
                refresh_resources()
            except Exception:
                pass
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
        summaries = t.list_selection_candidates()
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

