"""Exercise production 3.0 selection identities with all memory scans forbidden."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from war3_reforged_trainer import ProcessMemory, War3Trainer
from war3_classic_selection import read_player_selection
from war3_object_registry import (ObjectIdentityError, ROOT_RVA, RESOLVER_RVA,
                                  GAME_STATE_SLOT_RVA, decode_game_state)


class NoScanMemory(ProcessMemory):
    def forbidden(self, *args, **kwargs):
        raise AssertionError("Legacy memory scan reached during identity verification")
    regions = scan_bytes_private_parallel = scan_bytes_private = scan_bytes = forbidden


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pid", type=int)
    parser.add_argument("player", nargs="?", type=lambda s: int(s, 0))
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    previous = json.loads(args.expected.read_text(encoding="utf-8"))
    if previous["pid"] != args.pid:
        raise ValueError("Comparison report is from another process")
    expected = {int(r["unit"], 0): (int(r["full_handle"], 0), int(r["owner"], 0)) for r in previous["rows"]}
    trainer = object.__new__(War3Trainer)
    trainer._classic_selection_layout = (args.player, 0, 0) if args.player is not None else None
    trainer._classic_selection_cache = ()
    trainer._classic_object_registry = None
    timings, samples = [], []
    with NoScanMemory(args.pid) as memory:
        for _ in range(4):
            start = time.perf_counter()
            selected = trainer._classic_selection_candidates(memory)
            timings.append((time.perf_counter() - start) * 1000)
            samples.append(tuple((c.unit_address, h, c.owner_address) for c, h in selected))
        selected_player = trainer._classic_selection_layout[0]
        selection = read_player_selection(memory, selected_player)
        registry = trainer._classic_object_registry
        encoded_state = memory.read_u64(registry.base + GAME_STATE_SLOT_RVA)
        game_state = decode_game_state(encoded_state)
        stale_rejected = 0
        for _, handle in selected:
            try:
                registry.resolve_handle(memory, handle ^ (1 << 32))
            except ObjectIdentityError:
                stale_rejected += 1
        rows = [{"unit": hex(c.unit_address), "full_handle": hex(h), "owner": hex(c.owner_address),
                 "matches_previous_index": expected.get(c.unit_address) == (h, c.owner_address)}
                for c, h in selected]
        report = {"pid": args.pid, "captured_utc": datetime.now(timezone.utc).isoformat(),
                  "game_base": hex(registry.base), "resolver_rva": hex(RESOLVER_RVA),
                  "root_slot_rva": hex(ROOT_RVA),
                  "root": hex(memory.read_u64(registry.base + ROOT_RVA)),
                  "game_state_slot_rva": hex(GAME_STATE_SLOT_RVA),
                  "encoded_game_state": hex(encoded_state), "game_state": hex(game_state),
                  "local_player_fields_u16": list(struct.unpack("<HH", memory.read(game_state + 0x262C, 4))),
                  "player": hex(selected_player), "player_supplied": args.player is not None,
                  "validated_player_count": len(registry.players(memory)),
                  "read_only": True, "memory_scans_forbidden": True,
                  "count": len(rows), "all_samples_equal": len(set(samples)) == 1,
                  "list_matches": tuple(c.unit_address for c, _ in selected) == selection.units,
                  "all_identities_match_previous_index": all(row["matches_previous_index"] for row in rows),
                  "altered_generations_rejected": stale_rejected,
                  "cold_ms": timings[0], "warm_median_ms": statistics.median(timings[1:]),
                  "timings_ms": timings, "rows": rows,
                  "scope": "Actual candidate method including profile validation, module enumeration and "
                           "object lookup; when player_supplied=false includes game-state player discovery. "
                           "Local player selection still relies on a unique nonempty canonical list. "
                           "No helper, native execution, game writes or cross-device live test."}
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
