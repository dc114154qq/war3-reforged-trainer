"""Exercise current public reads and optional reversible gold/lumber writes."""
import argparse
import dataclasses
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
import traceback
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from war3_reforged_trainer import ProcessMemory, War3Trainer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int)
    parser.add_argument("--write-roundtrip", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = dict(pid=args.pid, captured_utc=datetime.now(timezone.utc).isoformat(),
                  read_only=not args.write_roundtrip, ok=False,
                  scope="One live 24268 process. Writes establish field roundtrip, not engine-side "
                        "notifications. No cross-device, 24-unit or native execution claim.")
    with patch.object(War3Trainer, "_start_persistent_bootstrap"):
        trainer = War3Trainer(pid=args.pid)
    try:
        with patch.object(trainer, "_run_native_helper_ops", side_effect=AssertionError("Legacy helper used")), \
                patch.object(ProcessMemory, "regions", side_effect=AssertionError("Region scan used")):
            start = time.perf_counter()
            groups = trainer.list_resource_caches()
            report["resource_list_ms"] = (time.perf_counter() - start) * 1000
            assert len(groups) == 28
            for group in groups:
                assert trainer.read_resource_cache_addresses(group).player_value == group.player_value
            local = trainer.locate_local_player_resource_cache()
            assert trainer.validate_local_player_resource_cache(local).owner_key == local.owner_key
            report["groups"] = [dataclasses.asdict(group) for group in groups]
            report["local"] = dataclasses.asdict(local)
            start = time.perf_counter()
            panel, candidate, fields = trainer.read_selected_unit_fields()
            report["selected_fields_ms"] = (time.perf_counter() - start) * 1000
            report["selected_count"] = len(trainer._last_selected_summaries)
            report["field_count"] = len(fields)
            report["fields"] = [{"key": field.key, "value": field.value} for field in fields]
            with trainer._process_memory() as memory:
                snapshot = trainer._selected_candidates_snapshot(memory)
                report["unit_components"] = [
                    {"unit": hex(unit.unit_address), "components": trainer._selected_components(memory, unit.owner_address)}
                    for unit, _handle in snapshot
                ]
            if args.write_roundtrip:
                before = trainer.read_resource_cache_addresses(local)
                targets = dict(target_gold=before.gold + 1, target_lumber=before.lumber + 1)
                assert targets["target_gold"] <= 10_000_000 and targets["target_lumber"] <= 10_000_000
                start = time.perf_counter()
                try:
                    after = trainer.write_resource_cache(before, **targets)
                    report["write_ms"] = (time.perf_counter() - start) * 1000
                    assert (after.gold, after.lumber) == (before.gold + 1, before.lumber + 1)
                    assert (after.food_used, after.food_cap, after.food_limit) == (
                        before.food_used, before.food_cap, before.food_limit)
                    report["write_after"] = dataclasses.asdict(after)
                finally:
                    current = trainer.read_resource_cache_addresses(before)
                    restore = {"target_" + field: getattr(before, field)
                               for field in ("gold", "lumber")
                               if getattr(current, field) == getattr(before, field) + 1}
                    if restore:
                        current = trainer.write_resource_cache(current, **restore)
                    report["restored"] = (current.gold, current.lumber) == (before.gold, before.lumber)
                    report["restore_after"] = dataclasses.asdict(current)
                    assert report["restored"], "Concurrent resource changes prevented exact restoration"
            report["ok"] = True
    except Exception:
        report["traceback"] = traceback.format_exc()
    finally:
        trainer.close()
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: v for k, v in report.items()
                      if k not in ("groups", "fields", "unit_components", "local", "write_after", "restore_after")}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
