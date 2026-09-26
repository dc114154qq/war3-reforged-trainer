"""Paired same-snapshot microbenchmark against released 70446ba (not a live-game claim)."""

import json, statistics, subprocess, sys, time, types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_object_registry import RegistryFixture
from war3_object_registry import ObjectRegistry24268


def baseline_module(name, path):
    text = subprocess.check_output(["git", "show", "70446ba:" + path], encoding="utf8")
    module = types.ModuleType(name)
    sys.modules[name] = module
    exec(compile(text, path, "exec"), module.__dict__)
    return module


def measure(old, new, count=1200):
    a = []
    b = []
    for i in range(count):
        pair = ((old, a), (new, b)) if i % 2 else ((new, b), (old, a))
        for fn, out in pair:
            start = time.perf_counter_ns()
            fn()
            out.append(time.perf_counter_ns() - start)

    def stats(x):
        return {
            "median_ns": statistics.median(x),
            "p95_ns": sorted(x)[int(len(x) * 0.95)],
        }

    left, right = stats(a), stats(b)
    return {
        "baseline": left,
        "current": right,
        "ratios": {k: right[k] / left[k] for k in left},
    }


old = baseline_module("baseline_registry", "war3_object_registry.py")
selection = baseline_module("baseline_selection", "war3_classic_selection.py")
from war3_classic_selection import read_player_selection

m = RegistryFixture()
h, o, u = m.unit(3)
before = old.ObjectRegistry24268(m, m.base)
after = ObjectRegistry24268(m, m.base)
assert before.resolve_unit(m, u) == after.resolve_unit(m, u)
report = {
    "snapshot": "synthetic identical sparse memory",
    "baseline_commit": "70446ba",
    "cold_registry": measure(
        lambda: old.ObjectRegistry24268(m, m.base).resolve_unit(m, u),
        lambda: ObjectRegistry24268(m, m.base).resolve_unit(m, u),
    ),
    "warm_registry": measure(
        lambda: before.resolve_unit(m, u), lambda: after.resolve_unit(m, u)
    ),
}
m.player(0x200000, 24)
assert (
    selection.read_player_selection(m, 0x200000).units
    == read_player_selection(m, 0x200000).units
)
report["selection_24"] = measure(
    lambda: selection.read_player_selection(m, 0x200000),
    lambda: read_player_selection(m, 0x200000),
)
report["pass"] = all(
    v <= 1.1
    for value in report.values()
    if isinstance(value, dict) and "ratios" in value
    for v in value["ratios"].values()
)
Path("build/architecture-performance.json").write_text(
    json.dumps(report, indent=2), encoding="utf8"
)
print(json.dumps(report, indent=2))
raise SystemExit(0 if report["pass"] else 1)
