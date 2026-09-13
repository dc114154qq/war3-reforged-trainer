"""Inspect actual 3.0 native registration nodes through a sampled frame context.

Read-only research tool. Resolving a registered address does not validate its
calling convention, game-thread execution, or helper compatibility.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from war3_reforged_trainer import ProcessMemory, find_war3
from war3_object_registry import ObjectRegistry24268, _ptr
from war3_thread_context import GameThreadContext24268

WANTED = {"GetLocalPlayer", "GroupEnumUnitsSelected", "GetUnitState", "GetHeroStr",
          "UnitAddAbility", "CreateUnit", "UnitAddItemById", "GetPlayerState", "SetPlayerState"}


def ascii_string(memory, pointer, limit=256):
    if not _ptr(pointer):
        raise ValueError("Invalid native string pointer")
    data = bytearray()
    while len(data) < limit:
        address = pointer + len(data)
        chunk = memory.read(address, min(16, 4096 - (address & 4095), limit - len(data)))
        if not chunk:
            break
        if b"\0" in chunk:
            return (data + chunk.split(b"\0", 1)[0]).decode("ascii")
        data.extend(chunk)
    raise ValueError("Unterminated native string")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    hwnd, pid = find_war3(args.pid)
    with ProcessMemory(pid) as memory:
        registry = ObjectRegistry24268.attach(memory)
        reader = GameThreadContext24268(memory, registry.base, hwnd, pid)
        mode = reader.read_mode(memory)
        context5 = memory.read_u64(mode.tls + 0x38)
        if not _ptr(context5):
            raise ValueError("Native context is missing")
        table = context5 + 0x28
        head = memory.read_u64(table + 0x18)
        terminal = (table + 0x10) | 1
        node, seen, found, names = head, set(), {}, set()
        start = time.perf_counter()
        while node != terminal:
            if not _ptr(node) or node in seen or len(seen) >= 8192:
                raise ValueError("Invalid or cyclic native node list")
            seen.add(node)
            name = ascii_string(memory, memory.read_u64(node + 0x28))
            signature = ascii_string(memory, memory.read_u64(node + 0x40))
            handler = memory.read_u64(node + 0x30)
            if not name or name in names or not signature.startswith("(") or ")" not in signature:
                raise ValueError("Native registration has invalid or duplicate metadata")
            names.add(name)
            if name in WANTED:
                found[name] = {"name": name, "signature": signature, "node": hex(node),
                               "handler": hex(handler), "handler_rva": hex(handler - registry.base)}
            node = memory.read_u64(node + 0x20)
        if (memory.read_u64(table + 0x18) != head
                or memory.read_u64(mode.tls + 0x38) != context5):
            raise ValueError("Native context changed during traversal")
        report = {"pid": pid, "captured_utc": datetime.now(timezone.utc).isoformat(),
                  "game_base": hex(registry.base), "tls": hex(mode.tls),
                  "context5": hex(context5), "table": hex(table), "head": hex(head),
                  "terminal": hex(terminal), "count": len(seen), "found": found,
                  "missing": sorted(WANTED - found.keys()),
                  "elapsed_ms": (time.perf_counter() - start) * 1000,
                  "scope": "Read-only native node traversal. No calls; ABI and helper execution unverified."}
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
