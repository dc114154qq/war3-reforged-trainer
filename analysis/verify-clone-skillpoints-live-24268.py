"""Run one cleaned-up 3.0 clone transaction and record hero-point validation."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from war3_engine_24268 import Engine24268
from war3_reforged_trainer import ProcessMemory, find_war3


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        raise SystemExit("usage: verify-clone-skillpoints-live-24268.py PID OUTPUT")
    pid = int(argv[1])
    output = Path(argv[2]).resolve()
    report: dict[str, object] = {
        "pid": pid,
        "keep": False,
        "copy_abilities": True,
        "copy_items": True,
        "ok": False,
    }
    try:
        hwnd, resolved_pid = find_war3(pid)
        report["hwnd"] = hwnd
        report["pid"] = resolved_pid
        engine = Engine24268(
            resolved_pid,
            hwnd,
            ProcessMemory,
            image=ROOT / "tools" / "war3_bridge_24268_2_0_1.dll",
        )
        result = engine.clone_batch(
            keep=False,
            copy_abilities=True,
            copy_items=True,
        )
        report["result"] = result
        report["engine_report"] = engine.last_report
        report["ok"] = bool(
            result.get("changed") == result.get("count")
            and all(row.get("status") == 2 for row in result.get("rows", ()))
        )
    except Exception:
        report["error"] = traceback.format_exc()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    temporary.replace(output)
    print(json.dumps({"ok": report["ok"], "output": str(output)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
