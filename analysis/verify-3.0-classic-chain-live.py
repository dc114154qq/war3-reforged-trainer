"""Read-only live check for the 3.0 classic-style handle -> unit chain.

This deliberately exercises only the existing bounded object index and the
known selection-handle candidates. It does not write the game or install a
helper. A positive result is evidence for the chain, not a product profile.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from war3_reforged_trainer import ProcessMemory, War3Trainer  # noqa: E402


def main() -> None:
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    trainer = War3Trainer(pid)
    started = time.perf_counter()
    rows: list[dict[str, object]] = []
    with ProcessMemory(trainer.pid) as memory:
        index = trainer._build_unit_object_index(memory, force_refresh=True)
        reverse = {handle: (unit, owner) for unit, (handle, owner) in index.items()}
        addresses = trainer._discover_selected_handle_addresses(memory)
        seen: set[tuple[int, int, int]] = set()
        for address in addresses:
            handle = memory.read_u64(address)
            mapped = reverse.get(handle)
            row: dict[str, object] = {
                "slot": hex(address),
                "handle": hex(handle),
                "mapped": mapped is not None,
            }
            if mapped is not None:
                unit, owner = mapped
                candidate = trainer._candidate_from_identity(
                    memory, handle, owner, unit,
                    "3.0 classic-chain live probe", 1000, address,
                )
                row.update({"unit": hex(unit), "owner": hex(owner),
                            "candidate_valid": candidate is not None})
                identity = (handle, owner, unit)
                row["duplicate_identity"] = identity in seen
                seen.add(identity)
            rows.append(row)
    report = {
        "pid": trainer.pid,
        "read_only": True,
        "unit_index_count": len(index),
        "candidate_count": len(rows),
        "mapped_count": sum(1 for row in rows if row["mapped"]),
        "validated_count": sum(1 for row in rows if row.get("candidate_valid")),
        "unique_validated_count": sum(
            1 for row in rows
            if row.get("candidate_valid") and not row.get("duplicate_identity")
        ),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "rows": rows,
    }
    output = ROOT / "analysis" / "native-bootstrap-24268" / "classic-chain-live.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
