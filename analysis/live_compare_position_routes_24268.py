"""Compare the current-engine batch with the retired per-unit helper, reversibly."""
import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from war3_engine_24268 import Engine24268
from war3_native_table import NativeTable24268
from war3_object_registry import ObjectRegistry24268
from war3_reforged_trainer import ProcessMemory, War3Trainer
from war3_thread_context import GameThreadContext24268
from war3_unit_action_protocol import ACTION_QUERY_POSITION


def positions(engine):
    result = engine.unit_action_batch(ACTION_QUERY_POSITION)
    return {
        int(row["unit"]): {
            "x": engine_bits_to_float(row["actual_x_bits"]),
            "y": engine_bits_to_float(row["actual_y_bits"]),
        }
        for row in result.get("rows", ())
    }


def engine_bits_to_float(bits):
    import struct
    return struct.unpack("<f", struct.pack("<I", int(bits)))[0]


def float_bits(value):
    import struct
    return struct.unpack("<I", struct.pack("<f", float(value)))[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pid", type=int)
    parser.add_argument("bridge", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--hwnd", type=int, required=True)
    args = parser.parse_args()
    report = {"pid": args.pid, "bridge": str(args.bridge), "ok": False}
    trainer = None
    original = {}
    helper_results = []
    try:
        with patch.object(War3Trainer, "_start_persistent_bootstrap"), \
                patch("war3_reforged_trainer.find_war3", return_value=(args.hwnd, args.pid)):
            trainer = War3Trainer(pid=args.pid)
        engine = Engine24268(args.pid, trainer.hwnd, ProcessMemory, image=args.bridge)
        original = positions(engine)
        if not original:
            raise RuntimeError("Current-engine position query returned no rows")
        first = next(iter(original.values()))
        target = (first["x"] + 250.0, first["y"] + 250.0)
        report.update(selection=len(original), target=list(target), original=original)
        with trainer._process_memory() as memory:
            selected = trainer._classic_selection_candidates(memory)
        if len(selected) != len(original):
            raise RuntimeError(f"Selection order length differs: native={len(original)} classic={len(selected)}")
        with trainer._process_memory() as memory:
            registry = ObjectRegistry24268.attach(memory)
            context = GameThreadContext24268(memory, registry.base, trainer.hwnd, trainer.pid)
            mode = context.read_mode(memory)
            context5 = memory.read_u64(mode.tls + 0x38)
            handler = NativeTable24268(memory, context5).require("SetUnitPosition")["SetUnitPosition"].handler
        trainer._native_selection_unavailable = False
        for handle, (_candidate, _full_handle) in zip(original, selected):
            results = trainer._run_native_helper_ops(
                int(handle),
                ((trainer.NATIVE_HELPER_OP_JASS_SET_UNIT_POSITION, 0, handler,
                  float_bits(target[0]), float_bits(target[1])),),
            )
            helper_results.append({"unit": handle, "result": int(results[0].result)})
        time.sleep(0.25)
        report["helper_positions"] = positions(engine)
        report["helper_results"] = helper_results
        trainer._native_selection_unavailable = False
        for handle, point in original.items():
            trainer._run_native_helper_ops(
                int(handle),
                ((trainer.NATIVE_HELPER_OP_JASS_SET_UNIT_POSITION, 0, handler,
                  float_bits(point["x"]), float_bits(point["y"])),),
            )
        time.sleep(0.25)
        report["restored_positions"] = positions(engine)
        report["restored"] = all(
            abs(report["restored_positions"][handle][axis] - original[handle][axis]) <= 0.01
            for handle in original for axis in ("x", "y")
        )
        report["ok"] = report["restored"]
    except Exception as exc:
        report["error"] = repr(exc)
        report["traceback"] = traceback.format_exc()
        report["helper_results"] = helper_results
    finally:
        if trainer is not None:
            trainer.close()
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "traceback"}, indent=2))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
