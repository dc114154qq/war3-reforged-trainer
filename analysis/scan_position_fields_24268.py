"""Read-only correlation of native world coordinates and indexed object fields."""
import argparse
import json
import math
import struct
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from war3_engine_24268 import Engine24268
from war3_object_registry import ObjectRegistry24268
from war3_reforged_trainer import ProcessMemory, War3Trainer
from war3_unit_action_protocol import ACTION_QUERY_POSITION


def f32(data, offset):
    return struct.unpack_from("<f", data, offset)[0]


def scan(memory, base, size, targets):
    if not base:
        return []
    hits = []
    for chunk_base in range(base, base + size, 0x1000):
        try:
            data = memory.read(chunk_base, min(0x1000, base + size - chunk_base))
        except OSError:
            continue
        for offset in range(0, len(data) - 4, 4):
            value = f32(data, offset)
            if not math.isfinite(value):
                continue
            for axis, target in targets.items():
                if abs(value - target) <= 0.01:
                    hits.append({"axis": axis, "address": hex(chunk_base + offset),
                                 "offset": hex(chunk_base + offset - base), "value": value})
    return hits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pid", type=int)
    parser.add_argument("hwnd", type=int)
    parser.add_argument("bridge", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = {"pid": args.pid, "hwnd": args.hwnd, "ok": False, "rows": []}
    with patch.object(War3Trainer, "_start_persistent_bootstrap"), \
            patch("war3_reforged_trainer.find_war3", return_value=(args.hwnd, args.pid)):
        trainer = War3Trainer(pid=args.pid)
    try:
        engine = Engine24268(args.pid, args.hwnd, ProcessMemory, image=args.bridge)
        native = engine.unit_action_batch(ACTION_QUERY_POSITION)
        native_rows = [
            {
                "handle": int(row["unit"]),
                "x": struct.unpack("<f", struct.pack("<I", int(row["actual_x_bits"])))[0],
                "y": struct.unpack("<f", struct.pack("<I", int(row["actual_y_bits"])))[0],
            }
            for row in native["rows"]
        ]
        with trainer._process_memory() as memory:
            registry = ObjectRegistry24268.attach(memory)
            selected = trainer._classic_selection_candidates(memory)
            report["classic_selection_count"] = len(selected)
            report["classic_handles"] = [hex(int(handle)) for _candidate, handle in selected]
            report["native_handles"] = [hex(row["handle"]) for row in native_rows]
            resolved_native = {}
            for row in native_rows:
                try:
                    resolved_native[hex(row["handle"])] = hex(registry.resolve_handle(memory, row["handle"]))
                except Exception as exc:
                    resolved_native[hex(row["handle"])] = type(exc).__name__
            report["native_registry_owners"] = resolved_native
            for index, (candidate, handle) in enumerate(selected):
                if index >= len(native_rows):
                    break
                target = native_rows[index]
                properties = trainer._owner_properties(memory, candidate.owner_address)
                bases = {
                    "unit": candidate.unit_address,
                    "owner": candidate.owner_address,
                    "position_property": candidate.position_property_address,
                    "position_prop_from_owner": properties.get(-1, 0),
                }
                for prop_index, prop in enumerate(trainer._iter_owner_property_list(memory, candidate.owner_address)):
                    bases[f"property_{prop_index}"] = prop
                for name, (wrapper, data) in trainer._selected_components(memory, candidate.owner_address).items():
                    bases[f"component_{name}_wrapper"] = wrapper
                    bases[f"component_{name}_data"] = data
                all_targets = {
                    f"x_{row['handle']:x}": row["x"] for row in native_rows
                }
                all_targets.update({
                    f"y_{row['handle']:x}": row["y"] for row in native_rows
                })
                hits = []
                for name, base in bases.items():
                    hits.extend({"region": name, **hit} for hit in scan(memory, base, 0x6000, all_targets))
                report["rows"].append({
                    "handle": hex(int(handle)),
                    "unit": hex(candidate.unit_address),
                    "owner": hex(candidate.owner_address),
                    "native": target,
                    "indexed": {
                        "x": memory.read_f32(candidate.x_address),
                        "y": memory.read_f32(candidate.y_address),
                        "x_address": hex(candidate.x_address),
                        "y_address": hex(candidate.y_address),
                    },
                    "unit_1208": {
                        "x": memory.read_f32(candidate.unit_address + 0x1208),
                        "y": memory.read_f32(candidate.unit_address + 0x120C),
                    },
                    "bases": {key: hex(value) if value else None for key, value in bases.items()},
                    "hits": hits[:256],
                })
        report["ok"] = True
    finally:
        trainer.close()
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"pid": args.pid, "rows": len(report["rows"]), "ok": report["ok"]}, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
