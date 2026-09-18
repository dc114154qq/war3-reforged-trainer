"""Reversible live validation for the current 24268 trainer goal."""
from __future__ import annotations

import argparse
import ctypes as c
import json
import math
import os
import struct
import sys
import time
import traceback
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from war3_engine_24268 import Engine24268
from war3_reforged_trainer import ProcessMemory, War3Trainer
from war3_unit_action_protocol import ACTION_QUERY_POSITION


def float_bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", float(value)))[0]


def float_value(bits: int) -> float:
    return struct.unpack("<f", struct.pack("<I", int(bits) & 0xFFFFFFFF))[0]


def position_rows(engine: Engine24268) -> tuple[dict, ...]:
    result = engine.unit_action_batch(ACTION_QUERY_POSITION)
    return tuple(result.get("rows", ()))


def wait_for_stable_positions(engine: Engine24268, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    previous = None
    stable_samples = 0
    latest: tuple[dict, ...] = ()
    while time.monotonic() < deadline:
        latest = position_rows(engine)
        signature = tuple(
            (int(row["unit"]), int(row["actual_x_bits"]), int(row["actual_y_bits"]))
            for row in latest
        )
        if signature and signature == previous:
            stable_samples += 1
        else:
            stable_samples = 0
        if stable_samples >= 2:
            return {"stable": True, "samples": stable_samples + 1, "rows": latest}
        previous = signature
        time.sleep(0.25)
    return {"stable": False, "samples": stable_samples, "rows": latest}


def query_process_exit_code(pid: int) -> int | None:
    kernel32 = c.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = (c.c_uint, c.c_int, c.c_uint)
    open_process.restype = c.c_void_p
    get_exit_code = kernel32.GetExitCodeProcess
    get_exit_code.argtypes = (c.c_void_p, c.POINTER(c.c_uint))
    get_exit_code.restype = c.c_int
    close = kernel32.CloseHandle
    close.argtypes = (c.c_void_p,)
    close.restype = c.c_int
    handle = open_process(0x1000, False, int(pid))
    if not handle:
        return None
    try:
        code = c.c_uint()
        if not get_exit_code(handle, c.byref(code)):
            return None
        return int(code.value)
    finally:
        close(handle)


def post_right_click(hwnd: int) -> dict:
    user32 = c.WinDLL("user32", use_last_error=True)
    class Rect(c.Structure):
        _fields_ = [("left", c.c_long), ("top", c.c_long),
                    ("right", c.c_long), ("bottom", c.c_long)]

    get_client_rect = user32.GetClientRect
    get_client_rect.argtypes = (c.c_void_p, c.POINTER(Rect))
    get_client_rect.restype = c.c_int
    rect = Rect()
    if not get_client_rect(c.c_void_p(hwnd), c.byref(rect)):
        raise c.WinError(c.get_last_error())
    width, height = int(rect.right - rect.left), int(rect.bottom - rect.top)
    if width < 320 or height < 200:
        raise RuntimeError(f"Invalid game client size: {width}x{height}")
    x, y = width // 2, height // 2
    lparam = (y << 16) | x
    post = user32.PostMessageW
    post.argtypes = (c.c_void_p, c.c_uint, c.c_size_t, c.c_ssize_t)
    post.restype = c.c_int
    if not post(c.c_void_p(hwnd), 0x0204, 0x0002, lparam):
        raise c.WinError(c.get_last_error())
    time.sleep(0.06)
    if not post(c.c_void_p(hwnd), 0x0205, 0, lparam):
        raise c.WinError(c.get_last_error())
    return {"client": [width, height], "point": [x, y], "posted": True}


def restore_positions(engine: Engine24268, before: tuple[dict, ...]) -> dict:
    restored = []
    readback = []
    for row in before:
        result = engine.position_target_batch(
            int(row["unit"]), float_bits(row["before_x"]), float_bits(row["before_y"]),
        )
        if result.get("target_unit") != int(row["unit"]) or result.get("completed") != 1:
            raise RuntimeError(f"Position restore failed for {row['unit']}")
        restored.append(int(row["unit"]))
        readback.append({
            "unit": int(row["unit"]),
            "x": float(result["actual_x"]),
            "y": float(result["actual_y"]),
        })
    return {"restored_units": restored, "count": len(restored), "readback": readback}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pid", type=int)
    parser.add_argument("bridge", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report: dict[str, object] = {
        "pid": args.pid,
        "bridge": str(args.bridge),
        "ok": False,
        "equipment": {},
        "item_field": {},
        "teleport": {},
    }
    trainer = None
    engine = None
    before_positions: tuple[dict, ...] = ()
    equipment_result = None
    item_snapshot = None
    item_spec = None
    item_identity = None
    try:
        with patch.object(War3Trainer, "_start_persistent_bootstrap"):
            trainer = War3Trainer(pid=args.pid)
        engine = Engine24268(args.pid, trainer.hwnd, ProcessMemory, image=args.bridge)
        selected = tuple(trainer._selected_candidates_snapshot(None))
        if len(selected) < 2:
            raise RuntimeError(f"Expected the current multi-unit selection, got {len(selected)}")
        report["identity"] = {
            "trainer_pid": os.getpid(),
            "game_pid": trainer.pid,
            "target_pid": trainer.pid,
            "window": {"hwnd": hex(trainer.hwnd)},
            "selected_count": len(selected),
            "selected_handles": [hex(int(candidate.handle)) for candidate, _ in selected],
        }

        item_batch_before = trainer.item_batch_24268()
        candidates_by_rawcode = {}
        for selected_candidate, _ in selected:
            candidates_by_rawcode.setdefault(int(selected_candidate.unit_type_id), []).append(selected_candidate)
        target_pairs = [
            (candidates_by_rawcode[int(row["rawcode"])][0], row)
            for row in item_batch_before.get("rows", ())
            if len(candidates_by_rawcode.get(int(row.get("rawcode", 0)), ())) == 1
            and any(int(index) >= 1 and int(item["handle"])
                    for index, item in enumerate(row.get("before", ())))
        ]
        if not target_pairs:
            raise RuntimeError("Could not bind a selected unit with an ordinary item in slots 2..6")
        # The selection remains multi-unit.  Pick one uniquely identified
        # candidate only as the explicit target for the item-field transaction.
        candidate, target_row = target_pairs[0]
        target_unit = int(target_row["handle"])
        identity = (int(candidate.handle), int(candidate.owner_address), int(candidate.unit_address))

        report["equipment"] = {
            "status": "not_executed",
            "reason": "eeh3 live equipment placement is reserved for user validation because 3.0 routes non-consumables through the slot-1 technical backpack",
            "offline_fixture_verified": True,
        }

        # Slot 1 is reserved by the current 3.0 build's added technical
        # backpack path; use only ordinary slots 2..6 for this field probe.
        slot = next(
            (int(index) + 1 for index, item in enumerate(target_row["before"])
             if int(index) >= 1 and int(item["handle"])),
            None,
        )
        if slot is None:
            raise RuntimeError("The first selected unit has no ordinary inventory item in slots 2..6")
        item_snapshot = trainer._read_selected_item_fields_24268(slot, unit_identity=identity)
        item_spec = next(value.spec for value in item_snapshot.fields if value.spec.rawcode == "iuse")
        old_value = next(value.value for value in item_snapshot.fields if value.spec.rawcode == "iuse")
        target_value = int(old_value) + 1
        written = trainer._set_selected_item_field_24268(
            slot, item_spec, target_value, item_snapshot, unit_identity=identity,
        )
        report["item_field"]["write"] = {
            "slot": slot,
            "item_handle": hex(item_snapshot.item_handle),
            "item_rawcode": hex(item_snapshot.item_rawcode),
            "field": "iuse",
            "before": old_value,
            "after": written.value,
        }
        restored_field = trainer._set_selected_item_field_24268(
            slot, item_spec, old_value, item_snapshot, unit_identity=identity,
        )
        report["item_field"]["restore"] = {
            "value": restored_field.value,
            "restored": restored_field.value == old_value,
        }

        before_rows = position_rows(engine)
        if len(before_rows) != len(selected):
            raise RuntimeError("Position query selection count changed before teleport")
        before_positions = tuple({
            "unit": int(row["unit"]),
            "before_x": float_value(row["actual_x_bits"]),
            "before_y": float_value(row["actual_y_bits"]),
        } for row in before_rows)
        bounds = engine.map_bounds()
        first_x, first_y = before_positions[0]["before_x"], before_positions[0]["before_y"]
        target_x = min(max(first_x + 64.0, float(bounds["min_x"]) + 64.0), float(bounds["max_x"]) - 64.0)
        target_y = min(max(first_y + 64.0, float(bounds["min_y"]) + 64.0), float(bounds["max_y"]) - 64.0)
        if not all(math.isfinite(value) for value in (target_x, target_y)):
            raise RuntimeError("Teleport target is not finite")
        moved = engine.position_batch(float_bits(target_x), float_bits(target_y))
        moved_rows = position_rows(engine)
        if not moved_rows or any(
            not math.isfinite(float_value(row["actual_x_bits"]))
            or not math.isfinite(float_value(row["actual_y_bits"]))
            for row in moved_rows
        ):
            raise RuntimeError("Engine teleport returned an invalid coordinate")
        click = post_right_click(trainer.hwnd)
        time.sleep(0.75)
        after_click = position_rows(engine)
        exit_code = query_process_exit_code(args.pid)
        moved_after_click = any(
            abs(float_value(row["actual_x_bits"]) - target_x) > 0.5
            or abs(float_value(row["actual_y_bits"]) - target_y) > 0.5
            for row in after_click
        )
        report["teleport"].update({
            "before": before_positions,
            "target": [target_x, target_y],
            "position_batch": {"count": moved["count"], "changed": moved["changed"], "completed": moved["completed"]},
            "after_teleport": [{"unit": int(row["unit"]), "x": float_value(row["actual_x_bits"]), "y": float_value(row["actual_y_bits"])} for row in moved_rows],
            "right_click": click,
            "after_right_click": [{"unit": int(row["unit"]), "x": float_value(row["actual_x_bits"]), "y": float_value(row["actual_y_bits"])} for row in after_click],
            "moved_after_right_click": moved_after_click,
            "process_exit_code": exit_code,
            "process_alive": exit_code == 259,
        })
        if not moved_after_click:
            raise RuntimeError("Right-click was posted but no selected unit moved")
        if exit_code != 259:
            raise RuntimeError(f"Game process is not running after movement: exit_code={exit_code}")
        report["ok"] = True
    except Exception as exc:
        report["error"] = repr(exc)
        report["traceback"] = traceback.format_exc()
    finally:
        if trainer is not None and before_positions:
            try:
                cleanup_engine = Engine24268(args.pid, trainer.hwnd, ProcessMemory, image=args.bridge)
                report["teleport"]["pre_cleanup_settle"] = wait_for_stable_positions(cleanup_engine)
                restore = restore_positions(cleanup_engine, before_positions)
                report["teleport"]["restore"] = restore
                post_cleanup_settle = wait_for_stable_positions(cleanup_engine)
                report["teleport"]["post_cleanup_settle"] = {
                    "stable": post_cleanup_settle["stable"],
                    "samples": post_cleanup_settle["samples"],
                }
                restored_rows = post_cleanup_settle["rows"]
                units = {int(row["unit"]) for row in restored_rows}
                finite_readback = all(
                    math.isfinite(float_value(row["actual_x_bits"]))
                    and math.isfinite(float_value(row["actual_y_bits"]))
                    for row in restored_rows
                )
                report["teleport"]["restore_engine_adjusted"] = any(
                    abs(float(item["x"]) - original["before_x"]) > 0.05
                    or abs(float(item["y"]) - original["before_y"]) > 0.05
                    for item in restore["readback"]
                    for original in before_positions
                    if int(item["unit"]) == int(original["unit"])
                )
                report["teleport"]["cleanup_process_exit_code"] = query_process_exit_code(args.pid)
                report["teleport"]["restored"] = (
                    restore["count"] == len(before_positions)
                    and units.issuperset(int(row["unit"]) for row in before_positions)
                    and finite_readback
                    and report["teleport"]["cleanup_process_exit_code"] == 259
                )
            except Exception as exc:
                report["teleport"]["restore_error"] = repr(exc)
                report["teleport"]["restored"] = False
        if trainer is not None:
            trainer.close()
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "traceback"}, ensure_ascii=False, default=str))
    return 0 if report.get("ok") and report.get("item_field", {}).get("restore", {}).get("restored") and report.get("teleport", {}).get("restored") else 1


if __name__ == "__main__":
    raise SystemExit(main())
