"""Read explicitly supplied player pointers; no discovery, injection or writes."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from war3_classic_selection import read_player_selection
from war3_reforged_trainer import ProcessMemory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int)
    parser.add_argument("players", nargs="+", type=lambda s: int(s, 0))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    with ProcessMemory(args.pid) as memory:
        for player in args.players:
            durations, snapshots = [], []
            for _ in range(10):
                start = time.perf_counter()
                snapshot = read_player_selection(memory, player)
                durations.append((time.perf_counter() - start) * 1000)
                snapshots.append(snapshot)
            rows.append({"player": hex(player), "manager": hex(snapshot.manager),
                         "count": len(snapshot.units), "units": [hex(u) for u in snapshot.units],
                         "rawcodes": [memory.read(u + 0x70, 4)[::-1].decode("ascii", "replace")
                                      for u in snapshot.units],
                         "sample_count": len(snapshots), "all_samples_equal": len(set(snapshots)) == 1,
                         "median_ms": statistics.median(durations), "max_ms": max(durations)})
    report = {"pid": args.pid, "captured_utc": datetime.now(timezone.utc).isoformat(),
              "read_only": True, "rows": rows,
              "scope": "Known-address canonical list traversal only; timing excludes player discovery, "
                       "identity resolution, UI and execution. Local player identity, 24-unit live selection "
                       "and cross-device bootstrap are not established by this report."}
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
