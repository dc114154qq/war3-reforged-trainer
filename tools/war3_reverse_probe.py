# -*- coding: utf-8 -*-
"""Small Warcraft III Reforged memory probe used while porting the trainer.

The script is intentionally separate from the trainer.  It reads live memory,
prints compact evidence, and only writes when a subcommand explicitly says so.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes
import json
import math
import struct
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008

MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
MEM_IMAGE = 0x1000000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100
READABLE_PROTECTS = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}

WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
MK_LBUTTON = 0x0001
SW_RESTORE = 9
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

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
class WindowInfo:
    hwnd: int
    pid: int
    title: str
    left: int
    top: int
    right: int
    bottom: int


class ProcessMemory:
    def __init__(self, pid: int, write: bool = False):
        access = PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        if write:
            access |= PROCESS_VM_WRITE | PROCESS_VM_OPERATION
        self.handle = kernel32.OpenProcess(access, False, pid)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self._regions: list[Region] | None = None

    def close(self) -> None:
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self) -> "ProcessMemory":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def regions(self) -> list[Region]:
        if self._regions is not None:
            return self._regions
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
                int(mbi.State) == MEM_COMMIT
                and not (protect & (PAGE_NOACCESS | PAGE_GUARD))
                and prot_low in READABLE_PROTECTS
            ):
                out.append(Region(int(mbi.BaseAddress), int(mbi.RegionSize), protect, int(mbi.Type)))
            addr = int(mbi.BaseAddress) + int(mbi.RegionSize)
        self._regions = out
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

    def scan_bytes(
        self,
        pattern: bytes,
        max_region_size: int = 256 * 1024 * 1024,
        region_types: set[int] | None = None,
    ) -> list[tuple[int, Region]]:
        hits: list[tuple[int, Region]] = []
        tail_len = max(0, len(pattern) - 1)
        for region in self.regions():
            if region_types is not None and region.typ not in region_types:
                continue
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
                        hits.append((address, region))
                    start = idx + 1
                tail = data[-tail_len:] if tail_len else b""
                offset += size
        return hits

    def scan_f32(self, value: float, region_types: set[int] | None = None) -> list[tuple[int, Region]]:
        return self.scan_bytes(struct.pack("<f", float(value)), region_types=region_types)

    def scan_i32(self, value: int, region_types: set[int] | None = None) -> list[tuple[int, Region]]:
        return self.scan_bytes(struct.pack("<i", int(value)), region_types=region_types)

    def scan_u64(self, value: int, region_types: set[int] | None = None) -> list[tuple[int, Region]]:
        return self.scan_bytes(struct.pack("<Q", int(value)), region_types=region_types)


def enum_war3_windows() -> list[WindowInfo]:
    windows: list[WindowInfo] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def enum_proc(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if buf.value != "Warcraft III":
            return True
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        windows.append(WindowInfo(int(hwnd), int(pid.value), buf.value, rect.left, rect.top, rect.right, rect.bottom))
        return True

    user32.EnumWindows(enum_proc, None)
    return windows


def find_war3(pid: int | None = None) -> WindowInfo:
    wins = enum_war3_windows()
    if pid is not None:
        wins = [w for w in wins if w.pid == pid]
    if not wins:
        raise RuntimeError("没有找到 Warcraft III 窗口")
    return wins[0]


def focus_window(hwnd: int) -> None:
    user32.ShowWindow(hwnd, SW_RESTORE)
    time.sleep(0.1)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.2)


def click_screen(hwnd: int, x: int, y: int) -> None:
    focus_window(hwnd)
    user32.SetCursorPos(int(x), int(y))
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.04)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(0.35)


def close_float(a: float, b: float, tolerance: float = 0.01) -> bool:
    return math.isfinite(a) and abs(a - b) <= tolerance


def printable_f32(value: float) -> str:
    if not math.isfinite(value) or abs(value) > 1e7:
        return "nan"
    return f"{value:.4g}"


def cmd_find_hp(args: argparse.Namespace) -> None:
    win = find_war3(args.pid)
    with ProcessMemory(win.pid) as pm:
        print(f"pid={win.pid} hwnd=0x{win.hwnd:x}")
        candidates = []
        for address, region in pm.scan_f32(args.hp, region_types={MEM_PRIVATE}):
            try:
                hp_max = pm.read_f32(address + 0x10)
            except OSError:
                continue
            if not close_float(hp_max, args.hp):
                continue
            mp_addr = 0
            mp_score = 0
            if args.mp is not None:
                for off in (0x100, 0xF0, 0xE0, 0x110, 0x120):
                    try:
                        mp_val = pm.read_f32(address + off)
                    except OSError:
                        continue
                    if close_float(mp_val, args.mp):
                        mp_addr = address + off
                        mp_score = 100 if off == 0x100 else 40
                        break
                if not mp_score:
                    continue
            candidates.append((100 + mp_score, address, mp_addr, region))
        candidates.sort(reverse=True)
        for score, address, mp_addr, region in candidates[: args.limit]:
            print(
                f"score={score} hp_base=0x{address:x} hp_max=0x{address+0x10:x} "
                f"mp=0x{mp_addr:x} region=0x{region.base:x}+0x{region.size:x}"
            )


def cmd_refs(args: argparse.Namespace) -> None:
    win = find_war3(args.pid)
    targets = [int(v, 0) for v in args.address]
    with ProcessMemory(win.pid) as pm:
        print(f"pid={win.pid} targets={','.join(hex(t) for t in targets)}")
        target_set = set(targets)
        hits_by_target: dict[int, list[tuple[int, Region]]] = {target: [] for target in targets}
        counts: Counter[int] = Counter()
        for region in pm.regions():
            if region.typ not in {MEM_PRIVATE, MEM_IMAGE}:
                continue
            try:
                data = pm.read(region.base, region.size)
            except OSError:
                continue
            for offset in range(0, len(data) - 7, 8):
                value = struct.unpack_from("<Q", data, offset)[0]
                if value not in target_set:
                    continue
                counts[value] += 1
                if len(hits_by_target[value]) < args.limit:
                    hits_by_target[value].append((region.base + offset, region))
        for target in targets:
            print(f"target=0x{target:x} qword_refs={counts[target]}")
            for address, region in hits_by_target[target]:
                print(f"  ref=0x{address:x} type=0x{region.typ:x} region=0x{region.base:x}+0x{region.size:x}")


def sane_ptr(value: int) -> bool:
    return 0x100000000 <= value <= 0x7FFFFFFFFFFF


def parse_coord(text: str) -> tuple[int, int]:
    try:
        x_text, y_text = text.split(",", 1)
        return int(x_text.strip()), int(y_text.strip())
    except Exception as exc:
        raise argparse.ArgumentTypeError("坐标格式应为 x,y") from exc


def parse_number_list(text: str | None) -> list[float]:
    if not text:
        return []
    out: list[float] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(float(part))
    return out


def snapshot_pointer_values(pm: ProcessMemory, max_region_size: int) -> dict[int, int]:
    """Return aligned private qword pointers from small readable heap regions."""
    out: dict[int, int] = {}
    for region in pm.regions():
        if region.typ != MEM_PRIVATE or region.size > max_region_size:
            continue
        try:
            data = pm.read(region.base, region.size)
        except OSError:
            continue
        limit = len(data) - 7
        for offset in range(0, limit, 8):
            value = struct.unpack_from("<Q", data, offset)[0]
            if sane_ptr(value):
                out[region.base + offset] = value
    return out


def read_target_blob(pm: ProcessMemory, address: int, size: int) -> bytes:
    try:
        return pm.read(address, size)
    except OSError:
        return b""


def ascii_fragments(data: bytes, min_len: int = 4) -> list[str]:
    parts: list[str] = []
    current = bytearray()
    for byte in data:
        if 32 <= byte < 127:
            current.append(byte)
        else:
            if len(current) >= min_len:
                parts.append(current.decode("ascii", "replace"))
            current.clear()
    if len(current) >= min_len:
        parts.append(current.decode("ascii", "replace"))
    return parts


NOISE_TOKENS = (
    "Replaceable",
    "Textures",
    "Command",
    "Buttons",
    "Button",
    ".blp",
    ".mdl",
    ".mdx",
    "UI\\",
    "war3mapImported",
    "Units\\",
    "Abilities\\",
)


def score_blob(data: bytes, values: list[float]) -> tuple[int, list[str], list[str]]:
    score = 0
    matches: list[str] = []
    if data:
        for wanted in values:
            packed_f = struct.pack("<f", float(wanted))
            packed_i = struct.pack("<i", int(wanted)) if float(wanted).is_integer() else None
            f_count = data.count(packed_f)
            i_count = data.count(packed_i) if packed_i else 0
            if f_count:
                score += min(20, 5 * f_count)
                matches.append(f"f32:{wanted:g}x{f_count}")
            if i_count:
                score += min(12, 3 * i_count)
                matches.append(f"i32:{int(wanted)}x{i_count}")
        ptr_count = 0
        for offset in range(0, len(data) - 7, 8):
            if sane_ptr(struct.unpack_from("<Q", data, offset)[0]):
                ptr_count += 1
        if ptr_count:
            score += min(8, ptr_count // 4)
    strings = ascii_fragments(data)
    joined = "\n".join(strings)
    noise = [token for token in NOISE_TOKENS if token in joined]
    if noise:
        score -= 40 + 10 * len(noise)
    return score, matches, noise


def summarize_pointer_target(
    pm: ProcessMemory,
    target: int,
    values: list[float],
    target_size: int,
) -> dict[str, object]:
    data = read_target_blob(pm, target, target_size)
    score, matches, noise = score_blob(data, values)
    strings = ascii_fragments(data)
    string_counts = Counter()
    for text in strings:
        for token in NOISE_TOKENS:
            if token in text:
                string_counts[token] += 1
    return {
        "target": target,
        "read": len(data),
        "score": score,
        "matches": matches[:24],
        "noise": noise,
        "strings": strings[:12],
        "noise_counts": dict(string_counts),
    }


def cmd_selection_diff(args: argparse.Namespace) -> None:
    win = find_war3(args.pid)
    a_values = parse_number_list(args.a_values)
    b_values = parse_number_list(args.b_values)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = args.pattern.upper()
    if any(ch not in "AB" for ch in pattern) or pattern.count("A") < 2 or pattern.count("B") < 2:
        raise RuntimeError("--pattern 至少需要两个 A 和两个 B，例如 ABAB")

    snapshots: list[tuple[str, dict[int, int]]] = []
    with ProcessMemory(win.pid) as pm:
        print(f"pid={win.pid} hwnd=0x{win.hwnd:x} pattern={pattern}", flush=True)
        for idx, label in enumerate(pattern, 1):
            coord = args.a if label == "A" else args.b
            click_screen(win.hwnd, coord[0], coord[1])
            time.sleep(args.settle)
            snap = snapshot_pointer_values(pm, args.max_region_size)
            snapshots.append((label, snap))
            print(f"snapshot {idx}/{len(pattern)} {label} pointers={len(snap)}", flush=True)

        common = set(snapshots[0][1])
        for _label, snap in snapshots[1:]:
            common &= set(snap)
        print(f"common_pointer_locations={len(common)}", flush=True)

        candidates: list[dict[str, object]] = []
        for location in common:
            a_seen = [snap[location] for label, snap in snapshots if label == "A"]
            b_seen = [snap[location] for label, snap in snapshots if label == "B"]
            if not a_seen or not b_seen:
                continue
            if len(set(a_seen)) != 1 or len(set(b_seen)) != 1:
                continue
            a_target = a_seen[0]
            b_target = b_seen[0]
            if a_target == b_target:
                continue
            a_summary = summarize_pointer_target(pm, a_target, a_values, args.target_size)
            b_summary = summarize_pointer_target(pm, b_target, b_values, args.target_size)
            score = int(a_summary["score"]) + int(b_summary["score"])
            # Stable selected-data pointers usually live in ordinary heaps, not executable images.
            try:
                around = pm.read(max(0, location - 0x20), 0x60)
            except OSError:
                around = b""
            loc_strings = ascii_fragments(around)
            if loc_strings:
                score -= 10
            candidates.append(
                {
                    "location": location,
                    "a_target": a_target,
                    "b_target": b_target,
                    "score": score,
                    "a_summary": a_summary,
                    "b_summary": b_summary,
                    "location_strings": loc_strings[:8],
                }
            )

    candidates.sort(key=lambda row: (int(row["score"]), -int(row["location"])), reverse=True)
    json_path = out_dir / "selection-diff-candidates.jsonl"
    text_path = out_dir / "selection-diff-candidates.txt"
    with json_path.open("w", encoding="utf-8") as f:
        for row in candidates:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    with text_path.open("w", encoding="utf-8") as f:
        for row in candidates[: args.limit]:
            f.write(
                "score={score:4d} loc=0x{location:x} A=0x{a_target:x} B=0x{b_target:x}\n".format(
                    score=int(row["score"]),
                    location=int(row["location"]),
                    a_target=int(row["a_target"]),
                    b_target=int(row["b_target"]),
                )
            )
            f.write(f"  A matches={row['a_summary']['matches']} noise={row['a_summary']['noise']}\n")
            f.write(f"  B matches={row['b_summary']['matches']} noise={row['b_summary']['noise']}\n")
            if row["a_summary"]["strings"] or row["b_summary"]["strings"]:
                f.write(f"  A strings={row['a_summary']['strings'][:4]}\n")
                f.write(f"  B strings={row['b_summary']['strings'][:4]}\n")
    print(f"candidates={len(candidates)}")
    print(f"wrote {text_path}")
    for row in candidates[: args.limit]:
        print(
            "score={score:4d} loc=0x{location:x} A=0x{a_target:x} B=0x{b_target:x} "
            "Am={am} Bm={bm} An={an} Bn={bn}".format(
                score=int(row["score"]),
                location=int(row["location"]),
                a_target=int(row["a_target"]),
                b_target=int(row["b_target"]),
                am=",".join(row["a_summary"]["matches"][:6]),
                bm=",".join(row["b_summary"]["matches"][:6]),
                an=",".join(row["a_summary"]["noise"][:4]),
                bn=",".join(row["b_summary"]["noise"][:4]),
            )
        )


def cmd_hero_struct(args: argparse.Namespace) -> None:
    win = find_war3(args.pid)
    with ProcessMemory(win.pid) as pm:
        print(f"pid={win.pid} scanning hero ability candidates")
        # Scan first on the CAbilityHero base-strength field, then validate the rest.
        hits = pm.scan_i32(args.strength, region_types={MEM_PRIVATE})
        ability_candidates: list[int] = []
        for address, _region in hits:
            ability = address - 0x108
            try:
                agi = pm.read_i32(ability + 0x130)
                add_str = pm.read_f32(ability + 0x188)
                add_int = pm.read_f32(ability + 0x198)
                add_agi = pm.read_f32(ability + 0x1A8)
                xp = pm.read_i32(ability + 0x100)
                skill_points = pm.read_i32(ability + 0x104)
            except OSError:
                continue
            if agi != args.agility:
                continue
            if not close_float(add_str, args.add_strength, 0.05):
                continue
            if not close_float(add_int, args.add_intelligence, 0.05):
                continue
            if not close_float(add_agi, args.add_agility, 0.05):
                continue
            ability_candidates.append(ability)
            print(
                f"ability=0x{ability:x} xp={xp} skill={skill_points} "
                f"base_str={args.strength} base_agi={agi} add=({add_str:.3g},{add_agi:.3g},{add_int:.3g})"
            )
        for ability in ability_candidates[: args.limit]:
            refs = pm.scan_u64(ability, region_types={MEM_PRIVATE})
            print(f"ability=0x{ability:x} refs={len(refs)}")
            for ref, region in refs[:12]:
                unit = ref - 0x5A8
                try:
                    armor = pm.read_f32(unit + 0x2E8)
                    armor_type = pm.read_i32(unit + 0x2F0)
                    move = pm.read_u64(unit + 0x5B0)
                    attack = pm.read_u64(unit + 0x5C0)
                    maybe_name = pm.read(unit + 0x3C4, 32)
                except OSError:
                    continue
                raw = maybe_name.split(b"\0", 1)[0]
                print(
                    f"  unit=0x{unit:x} ref=0x{ref:x} armor={printable_f32(armor)} "
                    f"armor_type={armor_type} move=0x{move:x} attack=0x{attack:x} name_raw={raw!r}"
                )


def cmd_dump(args: argparse.Namespace) -> None:
    win = find_war3(args.pid)
    base = int(args.address, 0)
    with ProcessMemory(win.pid) as pm:
        start = base - args.before
        data = pm.read(start, args.before + args.size)
        print(f"pid={win.pid} dump=0x{start:x}..0x{start+len(data):x}")
        for off in range(0, len(data) - 7, 8):
            address = start + off
            u64 = struct.unpack_from("<Q", data, off)[0]
            i32a = struct.unpack_from("<i", data, off)[0]
            i32b = struct.unpack_from("<i", data, off + 4)[0]
            f32a = struct.unpack_from("<f", data, off)[0]
            f32b = struct.unpack_from("<f", data, off + 4)[0]
            mark = "*" if address == base else " "
            print(
                f"{mark} 0x{address:013x} q=0x{u64:016x} "
                f"i=({i32a:10d},{i32b:10d}) f=({printable_f32(f32a):>8},{printable_f32(f32b):>8})"
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int)
    sub = parser.add_subparsers(dest="cmd", required=True)

    find_hp = sub.add_parser("find-hp")
    find_hp.add_argument("--hp", type=float, required=True)
    find_hp.add_argument("--mp", type=float)
    find_hp.add_argument("--limit", type=int, default=20)
    find_hp.set_defaults(func=cmd_find_hp)

    refs = sub.add_parser("refs")
    refs.add_argument("address", nargs="+")
    refs.add_argument("--limit", type=int, default=60)
    refs.set_defaults(func=cmd_refs)

    hero = sub.add_parser("hero-struct")
    hero.add_argument("--strength", type=int, required=True)
    hero.add_argument("--agility", type=int, required=True)
    hero.add_argument("--add-strength", type=float, required=True)
    hero.add_argument("--add-agility", type=float, required=True)
    hero.add_argument("--add-intelligence", type=float, required=True)
    hero.add_argument("--limit", type=int, default=20)
    hero.set_defaults(func=cmd_hero_struct)

    dump = sub.add_parser("dump")
    dump.add_argument("address")
    dump.add_argument("--before", type=int, default=0)
    dump.add_argument("--size", type=int, default=512)
    dump.set_defaults(func=cmd_dump)

    diff = sub.add_parser("selection-diff")
    diff.add_argument("--a", type=parse_coord, required=True, help="A 选中坐标，格式 x,y")
    diff.add_argument("--b", type=parse_coord, required=True, help="B 选中坐标，格式 x,y")
    diff.add_argument("--pattern", default="ABAB", help="采样顺序，默认 ABAB")
    diff.add_argument("--settle", type=float, default=0.35, help="点击后等待秒数")
    diff.add_argument("--max-region-size", type=lambda v: int(v, 0), default=0x30000)
    diff.add_argument("--target-size", type=lambda v: int(v, 0), default=0x1000)
    diff.add_argument("--a-values", help="A 目标内存里应出现的可见值，逗号分隔")
    diff.add_argument("--b-values", help="B 目标内存里应出现的可见值，逗号分隔")
    diff.add_argument("--out", default=r"D:\War3CodexWork\reforged-trainer\selection-diff-live")
    diff.add_argument("--limit", type=int, default=80)
    diff.set_defaults(func=cmd_selection_diff)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
