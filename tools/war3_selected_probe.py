# -*- coding: utf-8 -*-
"""Read-only structure dump for the current Warcraft III Reforged selection."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from war3_reforged_trainer import ProcessMemory, War3Trainer, format_rawcode  # noqa: E402


def rawcode_or_hex(value: int) -> str:
    text = format_rawcode(value)
    return text if not text.startswith("0x") else f"0x{value:08x}"


def find_u64(blob: bytes, base: int, value: int) -> list[int]:
    pat = struct.pack("<Q", value & 0xFFFFFFFFFFFFFFFF)
    out: list[int] = []
    start = 0
    while True:
        idx = blob.find(pat, start)
        if idx < 0:
            return out
        out.append(base + idx)
        start = idx + 1


def dump_words(pm: ProcessMemory, base: int, size: int, *, label: str) -> None:
    data = pm.read(base, size)
    print(f"{label}=0x{base:x} size=0x{size:x}")
    for off in range(0, len(data) - 7, 8):
        q = struct.unpack_from("<Q", data, off)[0]
        lo = struct.unpack_from("<I", data, off)[0]
        hi = struct.unpack_from("<I", data, off + 4)[0]
        raw_lo = rawcode_or_hex(lo)
        raw_hi = rawcode_or_hex(hi)
        raw_note = ""
        if raw_lo != f"0x{lo:08x}" or raw_hi != f"0x{hi:08x}":
            raw_note = f" raw=({raw_lo},{raw_hi})"
        print(f"  +0x{off:03x} q=0x{q:016x} u32=(0x{lo:08x},0x{hi:08x}){raw_note}")


def dump_ability_object(pm: ProcessMemory, trainer: War3Trainer, base: int, *, label: str, size: int = 0x220) -> None:
    data = pm.read(base, size)
    print(f"{label}_object=0x{base:x} size=0x{size:x}")
    for off in range(0, len(data) - 7, 8):
        q = struct.unpack_from("<Q", data, off)[0]
        lo = struct.unpack_from("<I", data, off)[0]
        hi = struct.unpack_from("<I", data, off + 4)[0]
        notes: list[str] = []
        raw_lo = rawcode_or_hex(lo)
        raw_hi = rawcode_or_hex(hi)
        if raw_lo != f"0x{lo:08x}":
            notes.append(f"lo={raw_lo}")
        if raw_hi != f"0x{hi:08x}":
            notes.append(f"hi={raw_hi}")
        if trainer._sane_heap_ptr(q):
            try:
                ptr_head = pm.read(q, 0x80)
                ptr_words = []
                for ptr_off in range(0, 0x40, 4):
                    value = struct.unpack_from("<I", ptr_head, ptr_off)[0]
                    raw = rawcode_or_hex(value)
                    if raw != f"0x{value:08x}":
                        ptr_words.append(f"+0x{ptr_off:x}:{raw}")
                vt = struct.unpack_from("<Q", ptr_head, 0)[0]
                if trainer._looks_like_vtable(vt):
                    ptr_words.insert(0, f"vt=0x{vt:x}")
                if ptr_words:
                    notes.append("ptr[" + ",".join(ptr_words[:8]) + "]")
            except OSError:
                pass
        suffix = (" " + " ".join(notes)) if notes else ""
        print(f"  +0x{off:03x} q=0x{q:016x} u32=(0x{lo:08x},0x{hi:08x}){suffix}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int)
    parser.add_argument("--dump-hero", action="store_true")
    parser.add_argument("--dump-abilities", action="store_true")
    parser.add_argument("--dump-items", action="store_true")
    parser.add_argument("--pure-memory", action="store_true")
    args = parser.parse_args()

    trainer = War3Trainer(args.pid)
    with ProcessMemory(trainer.pid) as pm:
        candidate = trainer.locate_selected_unit_by_handle(pm, allow_deep_scan=True)
        components = trainer._selected_components(pm, candidate.owner_address)
        print(
            f"pid={trainer.pid} handle=0x{candidate.handle:x} "
            f"owner=0x{candidate.owner_address:x} unit=0x{candidate.unit_address:x}"
        )
        for name, (wrapper, data) in sorted(components.items()):
            print(f"component {name:9s} wrapper=0x{wrapper:x} data=0x{data:x}")

        hero = components.get("hero")
        if hero is not None:
            _hero_wrapper, hero_data = hero
            print(f"hero_data=0x{hero_data:x}")
            for idx in range(trainer.HERO_SKILL_SLOT_COUNT):
                cache_addr = hero_data + 0x1BC + idx * 4
                name_addr = hero_data + 0x204 + idx * 4
                cache = pm.read_u32(cache_addr)
                name = pm.read_u32(name_addr)
                print(
                    f"skill{idx + 1}: cache={format_rawcode(cache)} @0x{cache_addr:x} "
                    f"name={format_rawcode(name)} @0x{name_addr:x}"
                )

        abilities = trainer._ability_instances_from_candidate(pm, candidate)
        for ability in abilities:
            owner_off = ability.wrapper_address - candidate.owner_address
            try:
                cache_ptr = pm.read_u64(ability.data_address + 0xA0)
            except OSError:
                cache_ptr = 0
            print(
                f"ability{ability.slot:02d}: wrapper=0x{ability.wrapper_address:x} "
                f"owner+0x{owner_off:x} data=0x{ability.data_address:x} "
                f"handle=0x{ability.handle:x} class={ability.class_text} raw={ability.rawcode_text} "
                f"vt=0x{ability.data_vtable:x} cache=0x{cache_ptr:x}"
            )

        if hero is not None:
            _hero_wrapper, hero_data = hero
            hero_blob = pm.read(hero_data, 0x400)
            owner_blob = pm.read(candidate.owner_address, 0x10000)
            for ability in abilities:
                refs: list[str] = []
                for label, value in (
                    ("wrapper", ability.wrapper_address),
                    ("data", ability.data_address),
                    ("handle", ability.handle),
                ):
                    hero_refs = find_u64(hero_blob, hero_data, value)
                    owner_refs = find_u64(owner_blob, candidate.owner_address, value)
                    if hero_refs:
                        refs.append(label + ":hero@" + ",".join(f"0x{x - hero_data:x}" for x in hero_refs[:8]))
                    other_owner_refs = [x for x in owner_refs if x != ability.wrapper_address + 0x20]
                    if other_owner_refs:
                        refs.append(
                            label + ":owner@" + ",".join(f"0x{x - candidate.owner_address:x}" for x in other_owner_refs[:8])
                        )
                if refs:
                    print(f"ability{ability.slot:02d}_refs " + " ".join(refs))

        items = trainer._inventory_items_from_candidate(pm, candidate, components)
        for item in items:
            print(
                f"item_slot{item.slot}: handle=0x{item.handle:x} handle_addr=0x{item.handle_address:x} "
                f"item=0x{item.item_address:x} raw={item.rawcode_text or '0'} "
                f"raw_addr=0x{item.rawcode_address:x} charges={item.charges} "
                f"charges_addr=0x{item.charges_address:x}"
            )

        if args.dump_hero and hero is not None:
            dump_words(pm, hero[1], 0x280, label="hero_dump")
        if args.dump_abilities:
            for ability in abilities:
                if ability.slot <= 5:
                    dump_ability_object(pm, trainer, ability.data_address, label=f"ability{ability.slot:02d}")
        if args.dump_items:
            for item in items:
                if item.item_address:
                    dump_words(pm, item.item_address, 0x220, label=f"item{item.slot}_dump")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
