"""Run one reversible current-engine SetUnitPosition probe on a live build."""
import argparse
import json
import math
import sys
import traceback
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from war3_engine_24268 import Engine24268
from war3_reforged_trainer import ProcessMemory, War3Trainer
from war3_unit_action_protocol import ACTION_QUERY_POSITION


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pid", type=int)
    parser.add_argument("bridge", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = {"pid": args.pid, "bridge": str(args.bridge), "ok": False}
    trainer = None
    selected = ()
    before = []
    try:
        with patch.object(War3Trainer, "_start_persistent_bootstrap"):
            trainer = War3Trainer(pid=args.pid)
        with trainer._process_memory() as memory:
            selected = trainer._selected_candidates_snapshot(memory)
            before = [
                {
                    "unit": hex(candidate.unit_address),
                    "handle": hex(handle),
                    "rawcode": candidate.unit_type_id,
                    "level": (candidate.native_snapshot.hero_level
                               if candidate.native_snapshot is not None else None),
                    "x": memory.read_f32(candidate.x_address),
                    "y": memory.read_f32(candidate.y_address),
                    "candidate": candidate,
                }
                for candidate, handle in selected
                if candidate.x_address and candidate.y_address
            ]
        if not before:
            raise RuntimeError("No selected units with verified position fields")
        target_x = float(before[0]["x"]) + 250.0
        target_y = float(before[0]["y"]) + 250.0
        if not all(math.isfinite(value) for value in (target_x, target_y)):
            raise RuntimeError("Projected test target is not finite")
        report.update(selection=len(before), target=[target_x, target_y])
        report["before"] = [
            {key: value for key, value in row.items() if key != "candidate"}
            for row in before
        ]
        engine = Engine24268(
            args.pid,
            trainer.hwnd,
            ProcessMemory,
            image=args.bridge,
        )
        try:
            result = engine.position_batch(
                trainer._float_bits(target_x), trainer._float_bits(target_y),
            )
            report["result"] = {
                "count": result.get("count"),
                "changed": result.get("changed"),
                "completed": result.get("completed"),
                "rows": [
                    {
                        "unit": row.get("unit"),
                        "actual_x_bits": row.get("actual_x_bits"),
                        "actual_y_bits": row.get("actual_y_bits"),
                    }
                    for row in result.get("rows", ())
                ],
            }
            with trainer._process_memory() as memory:
                report["after_native_fields"] = [
                    {
                        "unit": row["unit"],
                        "x": memory.read_f32(row["candidate"].x_address),
                        "y": memory.read_f32(row["candidate"].y_address),
                    }
                    for row in before
                ]
            import time
            time.sleep(0.25)
            settled = engine.unit_action_batch(ACTION_QUERY_POSITION)
            report["settled_native_positions"] = [
                {
                    "unit": row.get("unit"),
                    "x": trainer._float_from_bits(int(row["actual_x_bits"])),
                    "y": trainer._float_from_bits(int(row["actual_y_bits"])),
                }
                for row in settled.get("rows", ())
            ]
            report["ok"] = True
        except Exception as exc:
            report["error"] = repr(exc)
            report["engine_report"] = getattr(engine, "last_report", {})
            report["traceback"] = traceback.format_exc()
    except Exception as exc:
        report["error"] = repr(exc)
        report["traceback"] = traceback.format_exc()
    finally:
        if trainer is not None and before:
            try:
                with trainer._process_memory(write=True) as memory:
                    for row in before:
                        candidate = row["candidate"]
                        memory.write_f32(candidate.x_address, row["x"])
                        memory.write_f32(candidate.y_address, row["y"])
                with trainer._process_memory() as memory:
                    report["restored"] = all(
                        memory.read_f32(row["candidate"].x_address) == row["x"]
                        and memory.read_f32(row["candidate"].y_address) == row["y"]
                        for row in before
                    )
            except Exception as exc:
                report["restore_error"] = repr(exc)
                report["restored"] = False
        if trainer is not None:
            trainer.close()
        args.output.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in {"traceback", "engine_report"}}, indent=2, default=str))
    return 0 if report.get("ok") and report.get("restored") else 1


if __name__ == "__main__":
    raise SystemExit(main())
