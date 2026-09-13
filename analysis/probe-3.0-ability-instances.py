"""Read-only live report for 3.0 classic ability instances."""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from war3_reforged_trainer import ProcessMemory, War3Trainer  # noqa: E402


def main() -> None:
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    trainer = War3Trainer(pid)
    report: dict[str, object] = {"pid": trainer.pid, "read_only": True, "heroes": []}
    try:
        with ProcessMemory(trainer.pid) as memory:
            selected = trainer._classic_selection_candidates(memory)
            for candidate, handle in selected:
                if "hero" not in trainer._selected_components(memory, candidate.owner_address):
                    continue
                instances = trainer._ability_instances_from_candidate(
                    memory, candidate, allow_global_scan=False,
                )
                report["heroes"].append({
                    "handle": hex(handle),
                    "unit": hex(candidate.unit_address),
                    "count": len(instances),
                    "abilities": [
                        {
                            "slot": item.slot,
                            "rawcode": hex(item.rawcode),
                            "wrapper": hex(item.wrapper_address),
                            "data": hex(item.data_address),
                            "full_handle": hex(item.handle),
                        }
                        for item in instances
                    ],
                })
    finally:
        trainer.close()
    output = ROOT / "analysis" / "native-bootstrap-24268" / "ability-instances-live.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
