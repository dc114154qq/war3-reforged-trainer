"""Bounded read-only probe for the 3.0 classic-style selection list."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from war3_reforged_trainer import ProcessMemory, War3Trainer  # noqa: E402


def main() -> None:
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    trainer = War3Trainer(pid)
    with ProcessMemory(trainer.pid) as memory:
        unit_index = trainer._build_unit_object_index(memory, force_refresh=True)
        reverse = {handle: (unit, owner) for unit, (handle, owner) in unit_index.items()}
        players = trainer._selection_player_pointer_candidates(memory, discover=True)
        candidates: list[dict[str, object]] = []
        seen: set[tuple[int, int, tuple[int, ...]]] = set()
        for player in players:
            for player_offset in range(0, 0x1000, 8):
                try:
                    container = memory.read_u64(player + player_offset)
                except OSError:
                    continue
                if not trainer._sane_heap_ptr(container):
                    continue
                for manager_offset in range(0, 0x600, 8):
                    manager = container + manager_offset
                    try:
                        root = memory.read_u64(manager + 0x18)
                        count = memory.read_u32(manager + 0x20)
                    except OSError:
                        continue
                    if not 0 < count <= trainer.SELECTED_BATCH_MAX_UNITS:
                        continue
                    if not trainer._sane_heap_ptr(root):
                        continue
                    node = root
                    units: list[int] = []
                    seen_nodes: set[int] = set()
                    for _ in range(count):
                        if node in seen_nodes or not trainer._sane_heap_ptr(node):
                            break
                        seen_nodes.add(node)
                        try:
                            next_node = memory.read_u64(node + 8)
                            unit = memory.read_u64(node + 0x10)
                        except OSError:
                            break
                        if unit in unit_index:
                            units.append(unit)
                        node = next_node
                    if len(units) < 2:
                        continue
                    key = (player, manager, tuple(units))
                    if key in seen:
                        continue
                    seen.add(key)
                    mapped = []
                    for unit in units:
                        handle, owner = unit_index[unit]
                        mapped.append({"unit": hex(unit), "handle": hex(handle), "owner": hex(owner)})
                    candidates.append({
                        "player": hex(player),
                        "player_offset": hex(player_offset),
                        "manager": hex(manager),
                        "manager_offset": hex(manager_offset),
                        "count": int(count),
                        "mapped_count": len(mapped),
                        "handles": [item["handle"] for item in mapped],
                    })
        groups: dict[tuple[str, ...], list[dict[str, object]]] = {}
        for item in candidates:
            groups.setdefault(tuple(item["handles"]), []).append(item)
        ranked = sorted(groups.items(), key=lambda item: (len(item[0]), len(item[1])), reverse=True)
        report = {
            "pid": trainer.pid,
            "read_only": True,
            "unit_index_count": len(unit_index),
            "player_count": len(players),
            "candidate_count": len(candidates),
            "unique_lists": len(groups),
            "ranked_lists": [
                {"count": len(handles), "occurrences": len(rows), "examples": rows[:3]}
                for handles, rows in ranked[:12]
            ],
        }
    output = ROOT / "analysis" / "native-bootstrap-24268" / "classic-selection-live.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
