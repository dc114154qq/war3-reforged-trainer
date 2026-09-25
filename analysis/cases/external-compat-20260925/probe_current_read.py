"""One read-only unit-stats query using the exact bridge bundled in 2.0.7."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from war3_engine_24268 import Engine24268
from war3_reforged_trainer import ProcessMemory


engine = Engine24268(int(sys.argv[1]), int(sys.argv[2], 0), ProcessMemory,
                     image=Path(sys.argv[3]))
try:
    result = engine.unit_stats()
    print(f"query_success=True rows={len(result.get('rows', ())) }")
except Exception as exc:
    print(f"query_success=False exception={type(exc).__name__}")
finally:
    report = engine.last_report
    dispatch = report.get("dispatch", {})
    state = dispatch.get("after_cleanup") or dispatch.get("after_send") or {}
    print({
        "route": dispatch.get("image_route"),
        "stage": state.get("stage"),
        "callback_count": state.get("callback_count"),
        "query_stage": state.get("query_stage"),
        "exception_code": state.get("exception_code"),
        "fault": dispatch.get("fault"),
        "safe_to_release": dispatch.get("safe_to_release"),
        "allocations_retained": dispatch.get("allocations_retained"),
    })
    engine.close()
